"""Additional API routes for the web interface: queue, activity, frames, previews, predictions,
reports, dataset statistics, settings, logs and resource metrics."""

from __future__ import annotations

import collections
import json
import logging
import math
import os
import resource
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from backend.database import AnalysisJob, AppSetting, Experiment, Prediction, Report, utcnow
from backend.experiments.service import NotFound, validate_analysis_config
from backend.media import frame_jpeg, media_info, segmentation_preview
from backend.reports.pdf_export import write_report_files
from backend.reports.report_generator import SECTION_IDS, build_comparison_report, build_experiment_report
from backend.security import require_api_key
from backend.vision.cv_engine import AnalysisConfig

router = APIRouter()
write = [Depends(require_api_key)]


# ------------------------------------------------------------------ log buffer

class BufferHandler(logging.Handler):
    """Keeps the latest WARNING+ records in memory for the System page."""

    def __init__(self, size: int = 500):
        super().__init__(level=logging.WARNING)
        self.records: collections.deque = collections.deque(maxlen=size)
        self.lock2 = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        with self.lock2:
            self.records.append({"time": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
                                 "level": record.levelname, "logger": record.name, "message": record.getMessage()[:2000]})


LOG_BUFFER = BufferHandler()


def _clean(o: Any) -> Any:
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, np.integer)):
        o = o.item()
    if isinstance(o, float) and not math.isfinite(o):
        return None
    if isinstance(o, datetime):
        return o.isoformat()
    return o


def _row(obj, exclude=("result_dir", "file_dir")) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns if c.name not in exclude}


def _exp_input(request: Request, experiment_id: str) -> tuple[Experiment, Path]:
    st = request.app.state
    with st.db.session() as s:
        exp = s.get(Experiment, experiment_id)
        if exp is None:
            raise NotFound(experiment_id)
        if not exp.video_ref:
            raise HTTPException(status.HTTP_409_CONFLICT, "This experiment has no video or image sequence yet.")
        ref = exp.video_ref
    try:
        return exp, st.jobs.resolve_input(ref)
    except (FileNotFoundError, KeyError) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, f"The experiment's input is not available: {exc}") from exc


# --------------------------------------------------------------- jobs & activity

@router.get("/api/jobs", tags=["jobs"])
def list_jobs(request: Request, status_filter: str | None = Query(None, alias="status", max_length=16),
              limit: int = Query(100, ge=1, le=500)):
    with request.app.state.db.session() as s:
        q = select(AnalysisJob).order_by(AnalysisJob.created_at.desc()).limit(limit)
        if status_filter:
            q = q.where(AnalysisJob.status == status_filter)
        out = []
        for j in s.scalars(q):
            dur = (j.finished_at - j.started_at).total_seconds() if j.finished_at and j.started_at else None
            out.append({"id": j.id, "experiment_id": j.experiment_id, "type": "video_analysis", "status": j.status,
                        "created_at": j.created_at, "started_at": j.started_at, "finished_at": j.finished_at,
                        "duration_s": dur, "progress": j.progress, "frames_processed": j.frames_processed,
                        "input_ref": j.input_ref, "error": j.error})
    return _clean(out)


@router.get("/api/activity", tags=["system"])
def activity(request: Request, limit: int = Query(30, ge=1, le=200)):
    events = []
    with request.app.state.db.session() as s:
        for e in s.scalars(select(Experiment).order_by(Experiment.created_at.desc()).limit(limit)):
            events.append({"time": e.created_at, "kind": "experiment_created", "experiment_id": e.id, "title": f"Experiment created: {e.name}"})
        for j in s.scalars(select(AnalysisJob).order_by(AnalysisJob.created_at.desc()).limit(limit)):
            if j.status in ("completed", "failed", "cancelled") and j.finished_at:
                events.append({"time": j.finished_at, "kind": f"analysis_{j.status}", "experiment_id": j.experiment_id,
                               "job_id": j.id, "title": f"Video analysis {j.status} ({j.frames_processed} frames)"})
            elif j.started_at:
                events.append({"time": j.started_at, "kind": "analysis_started", "experiment_id": j.experiment_id,
                               "job_id": j.id, "title": "Video analysis started"})
        for p in s.scalars(select(Prediction).order_by(Prediction.created_at.desc()).limit(limit)):
            events.append({"time": p.created_at, "kind": "prediction", "experiment_id": p.experiment_id, "prediction_id": p.id,
                           "title": f"Prediction run: median lifetime {p.result.get('median_lifetime_s', 0):.2f} s"})
        for r in s.scalars(select(Report).order_by(Report.created_at.desc()).limit(limit)):
            events.append({"time": r.created_at, "kind": "report", "experiment_id": r.experiment_id, "report_id": r.id,
                           "title": f"Report generated: {r.title}"})
    ds = request.app.state.quality
    if ds:
        man = request.app.state.settings.data_dir / "processed" / "sflame_manifest.json"
        if man.exists():
            built = json.loads(man.read_text()).get("built_at")
            if built:
                events.append({"time": datetime.fromisoformat(built), "kind": "dataset_import",
                               "title": f"Dataset built: NASA s-Flame test points ({ds.get('test_points')} rows)"})
    events.sort(key=lambda e: e["time"] if e["time"].tzinfo else e["time"].replace(tzinfo=timezone.utc), reverse=True)
    return _clean(events[:limit])


# ------------------------------------------------------------------- media

@router.get("/api/experiments/{experiment_id}/media", tags=["media"])
def experiment_media(experiment_id: str, request: Request):
    _, path = _exp_input(request, experiment_id)
    return _clean(media_info(path))


@router.get("/api/experiments/{experiment_id}/frames/{index}.jpg", tags=["media"])
def experiment_frame(experiment_id: str, index: int, request: Request, max_width: int = Query(1400, ge=200, le=4000)):
    exp, path = _exp_input(request, experiment_id)
    cfg = AnalysisConfig.from_dict(exp.analysis_config or {})
    try:
        data = frame_jpeg(path, index, request.app.state.settings.storage_dir / "frame_cache", cfg, max_width)
    except IndexError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


class PreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    frame_index: int = Field(ge=0)
    analysis_config: dict[str, Any] | None = None
    calibration: dict[str, Any] | None = None


@router.post("/api/experiments/{experiment_id}/preview", tags=["media"])
def experiment_preview(experiment_id: str, body: PreviewRequest, request: Request):
    request.app.state.limiter.check(request.client.host if request.client else "unknown")
    exp, path = _exp_input(request, experiment_id)
    cfg = validate_analysis_config(body.analysis_config if body.analysis_config is not None else exp.analysis_config)
    for k in ("start_time_s", "end_time_s", "max_frames"):
        cfg[k] = None
    try:
        return _clean(segmentation_preview(path, body.frame_index, cfg, body.calibration or exp.calibration))
    except (IndexError, ValueError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


# -------------------------------------------------------------- predictions

@router.get("/api/predictions", tags=["prediction"])
def list_predictions(request: Request, experiment_id: str | None = Query(None, max_length=32), limit: int = Query(50, ge=1, le=500)):
    with request.app.state.db.session() as s:
        q = select(Prediction).order_by(Prediction.created_at.desc()).limit(limit)
        if experiment_id:
            q = q.where(Prediction.experiment_id == experiment_id)
        return _clean([_row(p) for p in s.scalars(q)])


@router.get("/api/predictions/{prediction_id}", tags=["prediction"])
def get_prediction(prediction_id: str, request: Request):
    with request.app.state.db.session() as s:
        p = s.get(Prediction, prediction_id)
        if p is None:
            raise NotFound(prediction_id)
        return _clean(_row(p))


# ------------------------------------------------------------------ reports

class ReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    experiment_id: str | None = Field(default=None, max_length=32)
    comparison_ids: list[str] | None = Field(default=None, max_length=8)
    sections: list[str] | None = None
    title: str | None = Field(default=None, max_length=200)


def _latest_analysis(s, request: Request, exp: Experiment) -> dict | None:
    if not exp.latest_job_id:
        return None
    job = s.get(AnalysisJob, exp.latest_job_id)
    if job is None or job.status != "completed" or not job.result_dir:
        return None
    p = Path(job.result_dir) / "analysis.json"
    return json.loads(p.read_text()) if p.exists() else None


@router.post("/api/reports", status_code=201, tags=["reports"], dependencies=write)
def create_report(body: ReportRequest, request: Request):
    st = request.app.state
    bad = set(body.sections or []) - set(SECTION_IDS)
    if bad:
        raise ValueError(f"Unknown report sections: {sorted(bad)}. Valid: {SECTION_IDS}")
    with st.db.session() as s:
        if body.comparison_ids:
            if len(body.comparison_ids) < 2:
                raise ValueError("A comparison report needs at least two experiments.")
            items = []
            for eid in body.comparison_ids:
                exp = s.get(Experiment, eid)
                if exp is None:
                    raise NotFound(eid)
                items.append((_clean(_row(exp)), _latest_analysis(s, request, exp)))
            content, rtype, exp_id, measurements = build_comparison_report(items), "comparison", None, None
        else:
            if not body.experiment_id:
                raise ValueError("experiment_id or comparison_ids is required.")
            exp = s.get(Experiment, body.experiment_id)
            if exp is None:
                raise NotFound(body.experiment_id)
            analysis = _latest_analysis(s, request, exp)
            preds = [_clean(_row(p)) for p in s.scalars(select(Prediction).where(Prediction.experiment_id == exp.id)
                                                         .order_by(Prediction.created_at.desc()).limit(10))]
            model = st.model.a if st.model is not None else None
            content = build_experiment_report(_clean(_row(exp)), analysis, preds, model, body.sections or SECTION_IDS)
            rtype, exp_id, measurements = "experiment", exp.id, (analysis or {}).get("measurements")
        if body.title:
            content["title"] = body.title
        rep = Report(experiment_id=exp_id, title=content["title"], report_type=rtype,
                     sections=[sec["id"] for sec in content["sections"]], content=_clean(content), formats=[])
        s.add(rep)
        s.flush()
        out_dir = st.settings.storage_dir / "reports" / rep.id
        try:
            rep.formats = write_report_files(_clean(content), out_dir, measurements)
            rep.file_dir = str(out_dir)
        except Exception as exc:  # noqa: BLE001 - recorded on the report and logged
            logging.getLogger("flame.reports").exception("report %s failed", rep.id)
            rep.status, rep.error = "failed", f"Report rendering failed: {type(exc).__name__}"
        s.commit()
        return _clean(_row(rep))


@router.get("/api/reports", tags=["reports"])
def list_reports(request: Request, experiment_id: str | None = Query(None, max_length=32), limit: int = Query(100, ge=1, le=500)):
    with request.app.state.db.session() as s:
        q = select(Report).order_by(Report.created_at.desc()).limit(limit)
        if experiment_id:
            q = q.where(Report.experiment_id == experiment_id)
        return _clean([{k: v for k, v in _row(r).items() if k != "content"} for r in s.scalars(q)])


@router.get("/api/reports/{report_id}", tags=["reports"])
def get_report(report_id: str, request: Request):
    with request.app.state.db.session() as s:
        r = s.get(Report, report_id)
        if r is None:
            raise NotFound(report_id)
        return _clean(_row(r))


@router.get("/api/reports/{report_id}/download", tags=["reports"])
def download_report(report_id: str, request: Request, format: Literal["pdf", "json", "csv"] = "pdf"):
    with request.app.state.db.session() as s:
        r = s.get(Report, report_id)
        if r is None:
            raise NotFound(report_id)
        if format not in (r.formats or []) or not r.file_dir:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"This report has no {format} file.")
        name = {"pdf": "report.pdf", "json": "report.json", "csv": "measurements.csv"}[format]
        media = {"pdf": "application/pdf", "json": "application/json", "csv": "text/csv"}[format]
        return FileResponse(Path(r.file_dir) / name, media_type=media, filename=f"{report_id}.{format}")


# ------------------------------------------------------------ dataset stats

UNITS = {"initial_total_slpm": "SLPM (N2-eq.)", "initial_fuel_slpm": "SLPM (N2-eq.)", "initial_diluent_slpm": "SLPM (N2-eq.)",
         "max_total_slpm": "SLPM (N2-eq.)", "min_total_slpm": "SLPM (N2-eq.)", "flame_duration_s": "s", "fuel_duration_s": "s",
         "ignition_delay_s": "s", "detection_lag_s": "s", "time_since_last_flow_change_s": "s", "planned_constant_flow_s": "s",
         "pmt1_peak_v": "V", "pmt1_baseline_v": "V", "o2_nominal": "mole fraction", "pta3_kpa_at_ignition_low_confidence": "kPa",
         "burner_temperature_limit_c": "°C", "total_slpm_at_extinction": "SLPM (N2-eq.)"}


@router.get("/api/datasets/sflame/stats", tags=["data"])
def sflame_stats(request: Request):
    df: pd.DataFrame | None = request.app.state.dataset
    if df is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Dataset not built.")
    variables = []
    for col in df.columns:
        s = df[col]
        miss = float(s.isna().mean())
        entry: dict[str, Any] = {"name": col, "missing_fraction": miss, "unit": UNITS.get(col)}
        if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
            v = s.dropna().astype(float)
            entry["kind"] = "numeric"
            if len(v):
                q1, q3 = np.percentile(v, [25, 75])
                iqr = q3 - q1
                entry.update(min=v.min(), max=v.max(), mean=v.mean(), std=v.std(ddof=1) if len(v) > 1 else 0.0,
                             median=v.median(), outliers_iqr=int(((v < q1 - 1.5 * iqr) | (v > q3 + 1.5 * iqr)).sum()),
                             histogram=dict(zip(("counts", "edges"), (lambda h: (h[0].tolist(), h[1].tolist()))(np.histogram(v, bins=min(20, max(5, int(len(v) ** 0.5))))))))
        else:
            entry["kind"] = "categorical"
            entry["top_values"] = [[str(k), int(c)] for k, c in s.astype(str).value_counts().head(12).items()]
        variables.append(entry)
    return _clean({
        "rows": int(len(df)), "columns": int(len(df.columns)),
        "duplicate_rows": int(df.duplicated().sum()),
        "duplicate_test_points": int(df["test_point"].duplicated().sum()) if "test_point" in df else None,
        "completeness": float(1 - df.isna().mean().mean()),
        "variables": variables,
        "quality_report": request.app.state.quality,
    })


# ------------------------------------------------------------------ settings

SETTINGS_DEFAULTS: dict[str, Any] = {
    "workspace_name": "Combustion research workspace",
    "units": "mm",
    "date_format": "iso",
    "default_analysis_config": {},
    "default_model": "sflame_lifetime",
    "export_format": "csv",
}


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace_name: str | None = Field(default=None, min_length=1, max_length=100)
    units: Literal["mm", "px"] | None = None
    date_format: Literal["iso", "local"] | None = None
    default_analysis_config: dict[str, Any] | None = None
    default_model: Literal["sflame_lifetime"] | None = None
    export_format: Literal["csv", "json"] | None = None


def load_settings(db) -> dict:
    out = dict(SETTINGS_DEFAULTS)
    with db.session() as s:
        for row in s.scalars(select(AppSetting)):
            out[row.key] = row.value.get("v")
    return out


@router.get("/api/settings", tags=["settings"])
def get_settings(request: Request):
    st = request.app.state
    return {"settings": load_settings(st.db), "server": {
        "max_upload_mb": st.settings.max_upload_bytes // (1024 * 1024), "max_workers": st.settings.max_workers,
        "rate_limit_per_minute": st.settings.rate_limit_per_minute, "auth_required_for_writes": st.settings.api_key is not None,
        "database_backend": st.db.engine.dialect.name, "telemetry_buffer": st.settings.telemetry_buffer}}


@router.put("/api/settings", tags=["settings"], dependencies=write)
def put_settings(body: SettingsUpdate, request: Request):
    data = body.model_dump(exclude_none=True)
    if "default_analysis_config" in data:
        data["default_analysis_config"] = validate_analysis_config(data["default_analysis_config"]) if data["default_analysis_config"] else {}
    with request.app.state.db.session() as s:
        for k, v in data.items():
            row = s.get(AppSetting, k)
            if row is None:
                s.add(AppSetting(key=k, value={"v": v}))
            else:
                row.value = {"v": v}
                row.updated_at = utcnow()
        s.commit()
    return get_settings(request)


# --------------------------------------------------------------- logs, resources

@router.get("/api/logs", tags=["system"])
def logs(request: Request, q: str | None = Query(None, max_length=200), limit: int = Query(200, ge=1, le=1000)):
    with LOG_BUFFER.lock2:
        recs = list(LOG_BUFFER.records)
    with request.app.state.db.session() as s:
        for j in s.scalars(select(AnalysisJob).where(AnalysisJob.status == "failed").order_by(AnalysisJob.created_at.desc()).limit(200)):
            recs.append({"time": (j.finished_at or j.created_at).isoformat(), "level": "ERROR", "logger": "analysis-job",
                         "message": f"{j.id} ({j.experiment_id}): {j.error}"})
    if q:
        recs = [r for r in recs if q.lower() in json.dumps(r).lower()]
    recs.sort(key=lambda r: r["time"], reverse=True)
    return recs[:limit]


def resources() -> dict:
    """Only metrics this process can actually read; anything else is reported as not collected."""
    out: dict[str, Any] = {"cpu_count": os.cpu_count(), "gpu": None, "gpu_note": "GPU metrics are not collected (CPU-only analysis)."}
    try:
        la = os.getloadavg()
        out["load_average"] = {"1m": la[0], "5m": la[1], "15m": la[2]}
        out["cpu_load_fraction_1m"] = la[0] / (os.cpu_count() or 1)
    except OSError:
        out["load_average"] = None
    try:
        mem = {}
        with open("/proc/meminfo") as fh:
            for line in fh:
                k, v = line.split(":", 1)
                mem[k] = int(v.strip().split()[0]) * 1024
        out["memory"] = {"total_bytes": mem.get("MemTotal"), "available_bytes": mem.get("MemAvailable"),
                         "used_fraction": 1 - mem["MemAvailable"] / mem["MemTotal"]}
    except (OSError, KeyError, ValueError):
        out["memory"] = None
    out["process_max_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    return out


def job_stats(db) -> dict:
    with db.session() as s:
        done = list(s.scalars(select(AnalysisJob).where(AnalysisJob.status == "completed")))
    durs = [(j.finished_at - j.started_at).total_seconds() for j in done if j.finished_at and j.started_at]
    frames = sum(j.frames_processed for j in done if j.finished_at and j.started_at)
    return {"completed_jobs_timed": len(durs), "average_duration_s": (sum(durs) / len(durs)) if durs else None,
            "throughput_frames_per_s": (frames / sum(durs)) if durs and sum(durs) > 0 else None}


# ----------------------------------------------------------- model evaluation

@router.get("/api/models/cv-predictions", tags=["prediction"])
def model_cv_predictions(request: Request):
    """Held-out-day predictions of the selected model for every training test point, plus metrics.

    R² and RMSE are computed on log(lifetime) over OBSERVED extinctions only (censored tests excluded), and
    MAE in seconds on the same set; with censoring these are descriptive, the C-index is the primary metric.
    """
    st = request.app.state
    if st.model is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, st.model_error or "Model unavailable.")
    path = st.settings.models_dir / "sflame_lifetime" / "cv_predictions.csv"
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No cross-validation predictions stored with the model.")
    df = pd.read_csv(path, dtype={"test_point": str, "group": str})
    ev = df[df["event"].astype(bool) & df["pred_median_s"].notna()]
    lt, lp = np.log(ev["time_s"].to_numpy()), np.log(ev["pred_median_s"].to_numpy())
    resid = lt - lp
    ss_res, ss_tot = float(np.sum(resid ** 2)), float(np.sum((lt - lt.mean()) ** 2))
    metrics = {"n_events": int(len(ev)), "n_censored": int((~df["event"].astype(bool)).sum()),
               "r2_log": 1 - ss_res / ss_tot if ss_tot > 0 else None, "rmse_log": float(np.sqrt(np.mean(resid ** 2))),
               "mae_s": float(np.mean(np.abs(ev["time_s"] - ev["pred_median_s"]))),
               "median_abs_error_s": float(np.median(np.abs(ev["time_s"] - ev["pred_median_s"]))),
               "note": "Held-out-day predictions; R² and RMSE on ln(lifetime) for observed extinctions only."}
    return _clean({"metrics": metrics, "rows": df.to_dict("records")})


# ------------------------------------------------------------------ documents

DOCS = {"readme": "README.md", "assumptions": "SCIENTIFIC_ASSUMPTIONS.md", "dictionary": "DATA_DICTIONARY.md",
        "architecture": "ARCHITECTURE.md", "api": "API_DOCUMENTATION.md", "tests": "TEST_REPORT.md",
        "status": "PROJECT_STATUS.md", "deployment": "DEPLOYMENT_GUIDE.md", "data-availability": "docs/DATA_AVAILABILITY_MATRIX.md"}


@router.get("/api/docs", tags=["system"])
def list_docs():
    return [{"id": k, "file": v} for k, v in DOCS.items()]


@router.get("/api/docs/{doc_id}", tags=["system"])
def get_doc(doc_id: str):
    """Project documents by fixed id (an allow-list; no client-supplied paths)."""
    from backend.config import REPO_ROOT
    if doc_id not in DOCS:
        raise NotFound(doc_id)
    path = REPO_ROOT / DOCS[doc_id]
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{DOCS[doc_id]} is not available in this deployment.")
    return Response(path.read_text(), media_type="text/markdown; charset=utf-8")
