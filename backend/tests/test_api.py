"""API tests (FastAPI TestClient, temporary SQLite database and storage)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import REPO_ROOT, Settings
from backend.database import AnalysisJob, Database, Experiment
from backend.vision.synthetic import SyntheticFlameSpec, write_synthetic_video

PRED = {"x_H2": 0.0, "x_CH4": 0.0, "x_C2H4": 0.25, "log_total_slpm": -1.2, "he_atmosphere": 0.0,
        "test_order_in_day": 3.0}


def _settings(tmp: Path, **kw) -> Settings:
    base = dict(database_url=f"sqlite:///{tmp / 'test.db'}", storage_dir=tmp / "storage",
                data_dir=REPO_ROOT / "data", models_dir=REPO_ROOT / "models", max_upload_bytes=50 * 1024 * 1024,
                max_workers=1, cors_origins=["http://localhost:5173"], api_key=None, rate_limit_per_minute=0,
                telemetry_buffer=5000, log_level="WARNING")
    base.update(kw)
    return Settings(**base)


@pytest.fixture()
def client(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as c:
        yield c


@pytest.fixture(scope="module")
def small_video(tmp_path_factory) -> Path:
    p = tmp_path_factory.mktemp("v") / "SYNTHETIC_small.mp4"
    write_synthetic_video(p, SyntheticFlameSpec(duration_s=1.0, extinction_time_s=None))
    return p


def _wait(c: TestClient, job_id: str, timeout: float = 60) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = c.get(f"/api/jobs/{job_id}").json()
        if j["status"] in ("completed", "failed", "cancelled"):
            return j
        time.sleep(0.1)
    raise TimeoutError(job_id)


def _upload(c, path: Path, name: str | None = None, **form):
    with open(path, "rb") as fh:
        return c.post("/api/analyze-video", files={"file": (name or path.name, fh, "video/mp4")}, data=form)


# --------------------------------------------------------------------------- system

def test_health_and_status(client):
    assert client.get("/api/health").json()["status"] == "ok"
    st = client.get("/api/system/status").json()
    assert st["database"]["ok"] and st["model"]["loaded"]
    assert st["datasets"]["sflame_test_points"] == 289
    assert "/home" not in json.dumps(st) and "/tmp" not in json.dumps(st)


# ---------------------------------------------------------------------- experiments

def test_experiment_crud_and_validation(client):
    r = client.post("/api/experiments", json={"name": "  Run 1 ", "oxygen_fraction": 0.21, "chamber_pressure_kpa": 101.3,
                                              "calibration": {"known_length_mm": 6.35, "measured_length_px": 98}})
    assert r.status_code == 201
    exp = r.json()
    assert exp["name"] == "Run 1" and exp["status"] == "draft"
    assert exp["calibration"]["mm_per_px"] == pytest.approx(6.35 / 98)
    eid = exp["id"]
    assert client.get(f"/api/experiments/{eid}").json()["id"] == eid
    assert client.patch(f"/api/experiments/{eid}", json={"fuel_type": "C2H4/N2"}).json()["fuel_type"] == "C2H4/N2"
    dup = client.post(f"/api/experiments/{eid}/duplicate").json()
    assert dup["name"] == "Run 1 (copy)" and dup["calibration"] == exp["calibration"] and dup["id"] != eid
    assert len(client.get("/api/experiments").json()) == 2
    assert client.delete(f"/api/experiments/{dup['id']}").status_code == 204
    assert client.get(f"/api/experiments/{dup['id']}").status_code == 404

    bad = [{"name": "x", "oxygen_fraction": 1.5}, {"name": "   "}, {"name": "x", "unknown": 1},
           {"name": "x", "calibration": {"known_length_mm": 1, "measured_length_px": 0}},
           {"name": "x", "analysis_config": {"frame_step": 0}},
           {"name": "x", "analysis_config": {"segmentation": {"method": "magic"}}}]
    for body in bad:
        r = client.post("/api/experiments", json=body)
        assert r.status_code == 422, body


# --------------------------------------------------------------------------- analysis

def test_upload_analysis_results_telemetry_and_export(client, small_video):
    r = _upload(client, small_video, name="my flame.mp4",
                calibration=json.dumps({"known_length_mm": 10, "measured_length_px": 100,
                                        "image_width": 640, "image_height": 480}))
    assert r.status_code == 202, r.text
    job = _wait(client, r.json()["id"])
    assert job["status"] == "completed" and job["summary"]["status_counts"]["detected"] == 30
    exp = client.get(f"/api/experiments/{job['experiment_id']}").json()
    assert exp["status"] == "completed" and exp["video_filename"] == "my flame.mp4"
    assert exp["video_ref"].startswith("upload:") and "/" not in exp["video_ref"].split(":", 1)[1]

    tel = client.get(f"/api/jobs/{job['id']}/telemetry").json()
    assert len(tel["events"]) == 30 and tel["events"][0]["radius_mm"] is not None
    page = client.get(f"/api/jobs/{job['id']}/telemetry", params={"after": 25}).json()
    assert [e["seq"] for e in page["events"]] == list(range(26, 31))

    res = client.get(f"/api/jobs/{job['id']}/result").json()
    assert len(res["measurements"]) == 30 and "contour_px" not in res["measurements"][3]
    assert "contour_px" in client.get(f"/api/jobs/{job['id']}/result", params={"contours": True}).json()["measurements"][3]
    csv = client.get(f"/api/jobs/{job['id']}/result", params={"format": "csv"})
    assert csv.headers["content-type"].startswith("text/csv") and csv.text.count("\n") == 31

    with client.websocket_connect(f"/api/jobs/{job['id']}/ws") as ws:
        msgs = []
        while not msgs or msgs[-1]["type"] != "done":
            msgs.append(ws.receive_json())
    assert msgs[-1]["status"] == "completed"
    assert sum(len(m.get("events", [])) for m in msgs) == 30

    e = client.post("/api/export", json={"experiment_id": exp["id"], "format": "json"})
    rec = json.loads(e.content)
    assert rec["experiment"]["id"] == exp["id"] and len(rec["latest_analysis"]["measurements"]) == 30
    assert "result_dir" not in json.dumps(rec["jobs"])
    assert client.post("/api/export", json={"experiment_id": exp["id"], "format": "csv"}).status_code == 200

    re = client.post(f"/api/experiments/{exp['id']}/reanalyze", json={"analysis_config": {"frame_step": 2}})
    assert re.status_code == 202
    assert _wait(client, re.json()["id"])["frames_processed"] == 15
    assert len(client.get(f"/api/experiments/{exp['id']}/jobs").json()) == 2


def test_upload_validation(client, tmp_path, small_video):
    txt = tmp_path / "a.txt"
    txt.write_text("hello")
    assert _upload(client, txt).status_code == 415
    fake = tmp_path / "fake.mp4"
    fake.write_bytes(b"\x00" * 64)
    assert _upload(client, fake).status_code == 415                     # signature mismatch
    empty = tmp_path / "empty.mp4"
    empty.write_bytes(b"")
    assert _upload(client, empty).status_code == 422
    corrupt = tmp_path / "corrupt.mp4"
    corrupt.write_bytes(b"\x00\x00\x00\x18ftypmp42" + os.urandom(4000))  # valid signature, undecodable
    assert _upload(client, corrupt).status_code == 422
    r = _upload(client, small_video, name="../../../../etc/evil.mp4")    # traversal attempt
    assert r.status_code == 202
    uploads = Path(client.app.state.settings.uploads_dir)
    assert all(p.parent == uploads for p in uploads.iterdir())
    assert not (uploads.parent.parent / "etc").exists()
    _wait(client, r.json()["id"])
    stored = [p for p in uploads.iterdir()]
    assert len(stored) == 1                                              # rejected uploads were deleted


def test_upload_size_limit(tmp_path, small_video):
    with TestClient(create_app(_settings(tmp_path, max_upload_bytes=1000))) as c:
        assert _upload(c, small_video).status_code == 413
        assert list(Path(c.app.state.settings.uploads_dir).iterdir()) == []


def test_sample_analysis_and_unavailable_samples(client):
    samples = {s["id"]: s for s in client.get("/api/samples").json()}
    assert samples["SYNTHETIC/demo"]["data_class"] == "synthetic"
    assert all("directory" not in s for s in samples.values())
    assert client.post("/api/analyze-sample", json={"sample_id": "nope"}).status_code == 404
    r = client.post("/api/analyze-sample", json={"sample_id": "SYNTHETIC/demo", "analysis_config": {"max_frames": 20}})
    job = _wait(client, r.json()["id"])
    assert job["status"] == "completed" and job["frames_processed"] == 20
    exp = client.get(f"/api/experiments/{job['experiment_id']}").json()
    assert exp["data_class"] == "synthetic" and exp["dataset_ref"] == "SYNTHETIC/demo"


@pytest.mark.skipif(not (REPO_ROOT / "data/raw/PSI-23/img/19254C1").is_dir() or not os.environ.get("FLAME_RUN_NASA_TESTS"),
                    reason="NASA image sequence not downloaded or FLAME_RUN_NASA_TESTS not set")
def test_nasa_sample_end_to_end(client):
    r = client.post("/api/analyze-sample", json={"sample_id": "PSI-23/19254C1"})
    job = _wait(client, r.json()["id"], timeout=300)
    assert job["status"] == "completed"
    assert job["summary"]["radius_method"] == "limb" and job["summary"]["limb_fits_ok"] > 120
    assert 15 < job["summary"]["limb_radius_mm"]["mean"] < 17


def test_cancel_queued_job_and_conflicts(tmp_path, small_video):
    with TestClient(create_app(_settings(tmp_path, max_workers=1))) as c:
        long = tmp_path / "SYNTHETIC_long.mp4"
        write_synthetic_video(long, SyntheticFlameSpec(duration_s=6.0))
        first = _upload(c, long).json()
        second = _upload(c, small_video).json()
        assert c.post(f"/api/jobs/{second['id']}/cancel").json()["status"] in ("cancelling", "cancelled")
        assert _wait(c, second["id"])["status"] == "cancelled"
        exp = first["experiment_id"]
        if c.get(f"/api/jobs/{first['id']}").json()["status"] in ("queued", "processing"):
            assert c.post(f"/api/experiments/{exp}/reanalyze").status_code == 409
            assert c.delete(f"/api/experiments/{exp}").status_code == 409
        c.post(f"/api/jobs/{first['id']}/cancel")
        assert _wait(c, first["id"])["status"] in ("cancelled", "completed")
        assert c.post("/api/jobs/JOB-unknown/cancel").status_code == 404


def test_restart_recovery(tmp_path, small_video):
    s = _settings(tmp_path)
    s.ensure_dirs()
    db = Database(s.database_url)
    db.create_all()
    up = s.uploads_dir / "abc.mp4"
    up.write_bytes(small_video.read_bytes())
    with db.session() as sess:
        e = Experiment(name="x")
        sess.add(e)
        sess.flush()
        sess.add_all([AnalysisJob(id="JOB-processing1", experiment_id=e.id, status="processing", input_ref="upload:abc.mp4"),
                      AnalysisJob(id="JOB-queued00001", experiment_id=e.id, status="queued", input_ref="upload:abc.mp4")])
        sess.commit()
    with TestClient(create_app(s)) as c:
        assert c.get("/api/system/status").json()["recovery_on_startup"] == {"failed_interrupted": 1, "requeued": 1}
        assert "restart" in c.get("/api/jobs/JOB-processing1").json()["error"]
        assert _wait(c, "JOB-queued00001")["status"] == "completed"


# ---------------------------------------------------------------- prediction, data

def test_predict_and_models(client):
    p = client.post("/api/predict", json={"inputs": PRED}).json()
    assert p["quantity_class"] == "predicted" and p["interval"]["lower_s"] < p["median_lifetime_s"] < p["interval"]["upper_s"]
    assert p["warnings"] == [] and p["limitations"]
    ood = client.post("/api/predict", json={"inputs": {**PRED, "x_H2": 0.95}}).json()
    assert any("outside the training range" in w for w in ood["warnings"])
    assert client.post("/api/predict", json={"inputs": {**PRED, "flame_duration_s": 3}}).status_code == 422
    missing = dict(PRED)
    missing.pop("x_H2")
    assert client.post("/api/predict", json={"inputs": missing}).status_code == 422
    exp = client.post("/api/experiments", json={"name": "p"}).json()
    client.post("/api/predict", json={"inputs": PRED, "experiment_id": exp["id"]})
    assert client.get(f"/api/experiments/{exp['id']}").json()["model_version"] == p["model_version"]
    m = client.get("/api/models").json()["models"][0]
    assert m["validation"]["scheme"] == "leave-one-test-day-out" and m["limitations"]


def test_model_unavailable(tmp_path):
    with TestClient(create_app(_settings(tmp_path, models_dir=tmp_path / "none"))) as c:
        assert c.post("/api/predict", json={"inputs": PRED}).status_code == 503
        assert c.get("/api/models").json()["models"] == []


def test_datasets(client):
    d = client.get("/api/datasets").json()["datasets"][0]
    assert d["rows"] == 289 and d["provenance"]["license"] == "CC0-1.0"
    r = client.get("/api/datasets/sflame/test-points", params={"outcome": "extinguished", "flow_programme": "constant"}).json()
    assert r["total"] == 113 and all(row["outcome"] == "extinguished" for row in r["rows"])
    assert client.post("/api/export", json={"experiment_id": "EXP-none"}).status_code == 404


# ----------------------------------------------------------------- auth, rate limit

def test_api_key_required_for_writes(tmp_path):
    with TestClient(create_app(_settings(tmp_path, api_key="s3cret"))) as c:
        assert c.post("/api/experiments", json={"name": "x"}).status_code == 401
        assert c.post("/api/experiments", json={"name": "x"}, headers={"X-API-Key": "wrong"}).status_code == 401
        r = c.post("/api/experiments", json={"name": "x"}, headers={"X-API-Key": "s3cret"})
        assert r.status_code == 201
        assert c.get("/api/experiments").status_code == 200              # reads stay open
        from starlette.websockets import WebSocketDisconnect
        with pytest.raises(WebSocketDisconnect):
            with c.websocket_connect("/api/jobs/JOB-x/ws") as ws:
                ws.receive_json()


def test_rate_limit(tmp_path):
    with TestClient(create_app(_settings(tmp_path, rate_limit_per_minute=2))) as c:
        codes = [c.post("/api/predict", json={"inputs": PRED}).status_code for _ in range(3)]
        assert codes == [200, 200, 429]
