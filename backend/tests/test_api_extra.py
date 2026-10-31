"""Tests for the interface-support endpoints: frames, previews, predictions, reports, stats, settings, queue, logs."""

from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.database import Database, Experiment
from backend.tests.test_api import PRED, _settings, _wait


def _demo(c: TestClient) -> dict:
    j = c.post("/api/analyze-sample", json={"sample_id": "SYNTHETIC/demo", "analysis_config": {"max_frames": 60}}).json()
    return _wait(c, j["id"])


def test_frames_media_and_preview(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as c:
        job = _demo(c)
        eid = job["experiment_id"]
        media = c.get(f"/api/experiments/{eid}/media").json()
        assert media["kind"] == "video" and media["reported_frame_count"] == 150 and "filename" in media
        f = c.get(f"/api/experiments/{eid}/frames/30.jpg")
        assert f.status_code == 200 and f.headers["content-type"] == "image/jpeg" and f.content[:2] == b"\xff\xd8"
        assert c.get(f"/api/experiments/{eid}/frames/30.jpg").content == f.content            # cached, identical
        assert c.get(f"/api/experiments/{eid}/frames/500.jpg").status_code == 404
        pv = c.post(f"/api/experiments/{eid}/preview", json={"frame_index": 30}).json()
        m = pv["measurement"]
        assert m["status"] == "detected" and abs(m["equivalent_radius_px"] - 91.33) < 1.5   # synthetic truth at t=1 s: 150-135*exp(-1/1.2)
        assert pv["overlay_jpeg_base64"] and pv["mask_png_base64"]
        bad = c.post(f"/api/experiments/{eid}/preview", json={"frame_index": 30, "analysis_config": {"frame_step": 0}})
        assert bad.status_code == 422
        empty = c.post("/api/experiments", json={"name": "no video"}).json()
        assert c.get(f"/api/experiments/{empty['id']}/frames/0.jpg").status_code == 409


def test_prediction_history(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as c:
        exp = c.post("/api/experiments", json={"name": "p"}).json()
        p1 = c.post("/api/predict", json={"inputs": PRED, "experiment_id": exp["id"]}).json()
        c.post("/api/predict", json={"inputs": {**PRED, "x_C2H4": 0.3}})
        hist = c.get("/api/predictions").json()
        assert len(hist) == 2 and hist[1]["id"] == p1["prediction_id"]
        assert hist[1]["inputs"] == PRED and hist[1]["result"]["quantity_class"] == "predicted"
        assert len(c.get("/api/predictions", params={"experiment_id": exp["id"]}).json()) == 1
        assert c.get(f"/api/predictions/{p1['prediction_id']}").json()["experiment_id"] == exp["id"]
        assert c.get("/api/predictions/PRD-nope").status_code == 404


def test_reports_experiment_and_comparison(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as c:
        a = _demo(c)
        b = _demo(c)
        c.post("/api/predict", json={"inputs": PRED, "experiment_id": a["experiment_id"]})
        r = c.post("/api/reports", json={"experiment_id": a["experiment_id"]})
        assert r.status_code == 201
        rep = r.json()
        assert rep["status"] == "completed" and set(rep["formats"]) == {"json", "pdf", "csv"} and len(rep["sections"]) == 13
        assert "file_dir" not in rep
        pdf = c.get(f"/api/reports/{rep['id']}/download", params={"format": "pdf"})
        assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-"
        content = c.get(f"/api/reports/{rep['id']}").json()["content"]
        unc = next(s for s in content["sections"] if s["id"] == "uncertainty")
        assert any(b.get("type") == "table" and "predicted" in b.get("title", "") for b in unc["blocks"])
        lim = next(s for s in content["sections"] if s["id"] == "limitations")
        assert "SYNTHETIC" in lim["blocks"][0]["items"][0]
        sub = c.post("/api/reports", json={"experiment_id": a["experiment_id"], "sections": ["overview", "conclusions"]}).json()
        assert sub["sections"] == ["overview", "conclusions"] and "csv" in sub["formats"]
        assert c.post("/api/reports", json={"experiment_id": a["experiment_id"], "sections": ["bogus"]}).status_code == 422
        cmp = c.post("/api/reports", json={"comparison_ids": [a["experiment_id"], b["experiment_id"]]}).json()
        assert cmp["report_type"] == "comparison" and cmp["formats"] == ["json", "pdf"]
        assert c.post("/api/reports", json={"comparison_ids": [a["experiment_id"]]}).status_code == 422
        assert len(c.get("/api/reports").json()) == 3
        assert c.get(f"/api/reports/{cmp['id']}/download", params={"format": "csv"}).status_code == 404


def test_dataset_stats():
    import tempfile
    from pathlib import Path
    with TestClient(create_app(_settings(Path(tempfile.mkdtemp())))) as c:
        st = c.get("/api/datasets/sflame/stats").json()
        assert st["rows"] == 289 and st["duplicate_test_points"] == 0
        v = {x["name"]: x for x in st["variables"]}
        assert v["flame_duration_s"]["kind"] == "numeric" and v["flame_duration_s"]["unit"] == "s"
        assert sum(v["flame_duration_s"]["histogram"]["counts"]) == round(289 * (1 - v["flame_duration_s"]["missing_fraction"]))
        assert v["outcome"]["kind"] == "categorical" and v["outcome"]["top_values"][0] == ["extinguished", 202]


def test_settings_drive_behaviour(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as c:
        s = c.get("/api/settings").json()
        assert s["settings"]["units"] == "mm" and s["server"]["max_upload_mb"] == 50
        assert c.put("/api/settings", json={"units": "inches"}).status_code == 422
        assert c.put("/api/settings", json={"default_analysis_config": {"frame_step": 0}}).status_code == 422
        c.put("/api/settings", json={"default_analysis_config": {"frame_step": 3}, "workspace_name": "Lab A"})
        assert c.get("/api/settings").json()["settings"]["workspace_name"] == "Lab A"
        exp = c.post("/api/experiments", json={"name": "x"}).json()
        assert exp["analysis_config"]["frame_step"] == 3


def test_archive_queue_activity_status_logs(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as c:
        job = _demo(c)
        eid = job["experiment_id"]
        assert c.patch(f"/api/experiments/{eid}", json={"archived": True}).json()["archived"] is True
        assert c.get("/api/experiments").json() == []
        assert len(c.get("/api/experiments", params={"include_archived": True}).json()) == 1
        q = c.get("/api/jobs").json()
        assert q[0]["status"] == "completed" and q[0]["duration_s"] > 0 and "result_dir" not in q[0]
        kinds = [a["kind"] for a in c.get("/api/activity").json()]
        assert "analysis_completed" in kinds and "experiment_created" in kinds
        st = c.get("/api/system/status").json()
        assert st["resources"]["cpu_count"] >= 1 and st["resources"]["gpu"] is None
        assert st["processing"]["completed_jobs_timed"] == 1 and st["processing"]["throughput_frames_per_s"] > 0
        assert isinstance(c.get("/api/logs").json(), list)


def test_v1_database_is_migrated(tmp_path):
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.executescript("""
    CREATE TABLE schema_version (id INTEGER PRIMARY KEY, version INTEGER, applied_at TIMESTAMP);
    INSERT INTO schema_version VALUES (1, 1, '2026-10-30');
    CREATE TABLE experiments (id VARCHAR(32) PRIMARY KEY, name VARCHAR(200), description TEXT, data_class VARCHAR(32),
      created_at TIMESTAMP, updated_at TIMESTAMP, fuel_type VARCHAR(200), oxygen_fraction FLOAT, chamber_pressure_kpa FLOAT,
      burn_duration_s FLOAT, camera JSON, calibration JSON, analysis_config JSON, dataset_ref VARCHAR(200), video_ref VARCHAR(200),
      video_filename VARCHAR(255), status VARCHAR(32), model_version VARCHAR(64), latest_job_id VARCHAR(32));
    INSERT INTO experiments (id, name, description, data_class, status) VALUES ('EXP-old', 'old', '', 'user', 'draft');
    """)
    con.commit()
    con.close()
    db = Database(f"sqlite:///{path}")
    assert db.create_all() == ["experiments.archived"]
    assert db.create_all() == []
    with db.session() as s:
        assert s.get(Experiment, "EXP-old").archived is False


def test_model_evidence_endpoints(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as c:
        m = c.get("/api/models").json()["models"][0]
        assert len(m["coef"]) == len(m["features"]) + 1 and len(m["standardizer"]["mean"]) == len(m["features"])
        assert isinstance(m["converged"], bool)
        cv = c.get("/api/models/cv-predictions").json()
        met, rows = cv["metrics"], cv["rows"]
        assert met["n_events"] + met["n_censored"] == len(rows) == m["training_data"]["n"]
        assert met["r2_log"] is not None and met["r2_log"] < 0          # reported as is, not hidden
        assert all(r["pred_q10_s"] <= r["pred_median_s"] <= r["pred_q90_s"] for r in rows)
        ds = c.get("/api/datasets").json()["datasets"][0]
        assert ds["built_at"] and ds["source_files"] > 0 and ds["detection_config"]["channel"] == "PMT1"


def test_docs_allow_list(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as c:
        ids = {d["id"] for d in c.get("/api/docs").json()}
        assert {"readme", "assumptions", "api"} <= ids
        r = c.get("/api/docs/assumptions")
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/markdown") and "A-ML-4" in r.text
        assert c.get("/api/docs/..%2F..%2Fetc%2Fpasswd").status_code == 404
        assert c.get("/api/docs/unknown").status_code == 404


def test_frontend_served_with_spa_fallback(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><div id=root></div>")
    (dist / "assets" / "app.js").write_text("console.log(1)")
    monkeypatch.setenv("FLAME_FRONTEND_DIST", str(dist))
    with TestClient(create_app(_settings(tmp_path))) as c:
        assert "id=root" in c.get("/experiments/EXP-1").text                  # client-side route
        assert c.get("/assets/app.js").text == "console.log(1)"
        assert c.get("/api/does-not-exist").status_code == 404                 # API 404s are not masked
        assert c.get("/api/health").json()["status"] == "ok"


def test_resource_metrics_without_unix_modules(monkeypatch):
    """On Windows there is no `resource` module, no os.getloadavg and no /proc: report, don't crash."""
    import builtins

    import backend.api_extra as ax
    monkeypatch.setattr(ax, "resource", None)
    monkeypatch.delattr(ax.os, "getloadavg", raising=False)
    real_open = builtins.open
    monkeypatch.setattr(builtins, "open", lambda f, *a, **k: (_ for _ in ()).throw(OSError("no /proc")) if str(f).startswith("/proc") else real_open(f, *a, **k))
    out = ax.resources()
    assert out["process_max_rss_bytes"] is None and out["load_average"] is None and out["memory"] is None
    assert out["cpu_count"] == ax.os.cpu_count()
