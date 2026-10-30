"""FLAME IN FREEFALL - FastAPI application.

Run:  uvicorn backend.app:app --reload        (OpenAPI docs at /docs)

Mutating endpoints require ``X-API-Key`` when FLAME_API_KEY is set; the WebSocket
takes ``?api_key=`` because browsers cannot set headers on WebSocket requests.
Responses never contain server filesystem paths.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import platform
import shutil
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile, WebSocket, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.websockets import WebSocketDisconnect

from backend.config import Settings
from backend.data.samples import SampleRegistry
from backend.database import Database
from backend.experiments import repository as repo
from backend.experiments.schemas import (
    AnalyzeSampleRequest,
    ExperimentCreate,
    ExperimentOut,
    ExperimentUpdate,
    ExportRequest,
    JobOut,
    PredictRequest,
)
from backend.experiments.service import Conflict, ExperimentService, NotFound, validate_calibration
from backend.jobs import TERMINAL, JobManager
from backend.ml.sflame_model import LifetimeModel
from backend.security import RateLimiter, require_api_key, save_upload
from backend.vision.cv_engine import ENGINE_VERSION, VideoValidationError, probe_video

API_VERSION = "0.4.0"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {"level": record.levelname, "logger": record.name, "msg": record.getMessage(),
               "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S")}
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out)


def _configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger("flame")
    root.handlers[:] = [handler]
    root.setLevel(level)


def _load_model(settings: Settings) -> tuple[LifetimeModel | None, str | None]:
    try:
        return LifetimeModel.load(settings.models_dir / "sflame_lifetime"), None
    except FileNotFoundError:
        return None, "No trained model found; run `python -m backend.ml.sflame_model train`."
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        return None, f"Model artifact invalid: {exc}"


def _load_dataset(settings: Settings) -> tuple[pd.DataFrame | None, dict | None]:
    base = settings.data_dir / "processed"
    try:
        df = pd.read_csv(base / "sflame_test_points.csv")
        report = json.loads((base / "sflame_quality_report.json").read_text())
        return df, report
    except FileNotFoundError:
        return None, None


def _clean(o: Any) -> Any:
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, np.integer)):
        o = o.item()
    if isinstance(o, float) and not math.isfinite(o):
        return None
    return o


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        _configure_logging(settings.log_level)
        settings.ensure_dirs()
        db = Database(settings.database_url)
        db.create_all()
        samples = SampleRegistry(settings.data_dir, settings.storage_dir)
        jobs = JobManager(db, settings, samples)
        app.state.settings, app.state.db, app.state.samples, app.state.jobs = settings, db, samples, jobs
        app.state.service = ExperimentService(db, jobs)
        app.state.model, app.state.model_error = _load_model(settings)
        app.state.dataset, app.state.quality = _load_dataset(settings)
        app.state.limiter = RateLimiter(settings.rate_limit_per_minute)
        app.state.recovery = jobs.recover()
        logging.getLogger("flame.app").info("started", extra={})
        yield
        jobs.shutdown()

    app = FastAPI(title="FLAME IN FREEFALL API", version=API_VERSION, lifespan=lifespan,
                  description="Microgravity combustion analysis: experiments, CV analysis jobs, telemetry, "
                              "flame-lifetime prediction and NASA ACME s-Flame data.")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                       allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Content-Type", "X-API-Key"])

    # -- errors --------------------------------------------------------------------------

    def _err(code: int, kind: str, message: str) -> JSONResponse:
        return JSONResponse(status_code=code, content={"error": {"code": kind, "message": message}})

    @app.exception_handler(NotFound)
    async def _nf(_: Request, exc: NotFound):
        return _err(404, "not_found", f"Not found: {exc}")

    @app.exception_handler(Conflict)
    async def _cf(_: Request, exc: Conflict):
        return _err(409, "conflict", str(exc))

    @app.exception_handler(ValueError)
    async def _ve(_: Request, exc: ValueError):
        return _err(422, "invalid", str(exc))

    @app.exception_handler(HTTPException)
    async def _he(_: Request, exc: HTTPException):
        return _err(exc.status_code, "http_error", str(exc.detail))

    def svc(request: Request) -> ExperimentService:
        return request.app.state.service

    def limited(request: Request) -> None:
        request.app.state.limiter.check(request.client.host if request.client else "unknown")

    write = [Depends(require_api_key)]

    # -- system --------------------------------------------------------------------------

    @app.get("/api/health", tags=["system"])
    def health(request: Request):
        return {"status": "ok" if request.app.state.db.ping() else "degraded", "api_version": API_VERSION}

    @app.get("/api/system/status", tags=["system"])
    def system_status(request: Request):
        st = request.app.state
        with st.db.session() as s:
            exp_counts = repo.count_experiments_by_status(s)
            job_counts = repo.count_jobs_by_status(s)
        usage = shutil.disk_usage(st.settings.storage_dir)
        stored = sum(p.stat().st_size for p in st.settings.storage_dir.rglob("*") if p.is_file())
        return {
            "api_version": API_VERSION, "engine_version": ENGINE_VERSION,
            "database": {"ok": st.db.ping(), "backend": st.db.engine.dialect.name},
            "experiments": {"total": sum(exp_counts.values()), "by_status": exp_counts},
            "jobs": {"by_status": job_counts, "active": job_counts.get("processing", 0) + job_counts.get("queued", 0),
                     "workers": st.settings.max_workers},
            "model": {"loaded": st.model is not None, "version": st.model.a["model_version"] if st.model else None,
                      "error": st.model_error},
            "datasets": {"sflame_test_points": None if st.dataset is None else int(len(st.dataset))},
            "samples": {"available": sum(1 for x in st.samples.list() if x["available"]), "total": len(st.samples.list())},
            "storage": {"used_by_app_bytes": stored, "disk_free_bytes": usage.free},
            "runtime": {"python": platform.python_version(), "opencv": cv2.__version__,
                        "ffmpeg": shutil.which("ffmpeg") is not None, "platform": platform.platform()},
            "auth_required_for_writes": st.settings.api_key is not None,
            "recovery_on_startup": st.recovery,
        }

    # -- experiments ----------------------------------------------------------------------

    @app.post("/api/experiments", response_model=ExperimentOut, status_code=201, tags=["experiments"],
              dependencies=write)
    def create_experiment(body: ExperimentCreate, request: Request):
        return svc(request).create(body)

    @app.get("/api/experiments", response_model=list[ExperimentOut], tags=["experiments"])
    def list_experiments(request: Request, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0),
                         status_filter: str | None = Query(None, alias="status", max_length=16)):
        with request.app.state.db.session() as s:
            return repo.list_experiments(s, limit, offset, status_filter)

    @app.get("/api/experiments/{experiment_id}", response_model=ExperimentOut, tags=["experiments"])
    def get_experiment(experiment_id: str, request: Request):
        with request.app.state.db.session() as s:
            exp = repo.get_experiment(s, experiment_id)
            if exp is None:
                raise NotFound(experiment_id)
            return exp

    @app.patch("/api/experiments/{experiment_id}", response_model=ExperimentOut, tags=["experiments"],
               dependencies=write)
    def update_experiment(experiment_id: str, body: ExperimentUpdate, request: Request):
        return svc(request).update(experiment_id, body)

    @app.delete("/api/experiments/{experiment_id}", status_code=204, tags=["experiments"], dependencies=write)
    def delete_experiment(experiment_id: str, request: Request):
        svc(request).delete(experiment_id)
        return Response(status_code=204)

    @app.post("/api/experiments/{experiment_id}/duplicate", response_model=ExperimentOut, status_code=201,
              tags=["experiments"], dependencies=write)
    def duplicate_experiment(experiment_id: str, request: Request):
        return svc(request).duplicate(experiment_id)

    @app.get("/api/experiments/{experiment_id}/jobs", response_model=list[JobOut], tags=["experiments"])
    def experiment_jobs(experiment_id: str, request: Request):
        with request.app.state.db.session() as s:
            if repo.get_experiment(s, experiment_id) is None:
                raise NotFound(experiment_id)
            return repo.list_jobs(s, experiment_id)

    @app.post("/api/experiments/{experiment_id}/reanalyze", response_model=JobOut, status_code=202,
              tags=["analysis"], dependencies=write + [Depends(limited)])
    def reanalyze(experiment_id: str, request: Request, body: dict[str, Any] | None = None):
        return svc(request).reanalyze(experiment_id, (body or {}).get("analysis_config"))

    # -- analysis ---------------------------------------------------------------------------

    @app.post("/api/analyze-video", response_model=JobOut, status_code=202, tags=["analysis"],
              dependencies=write + [Depends(limited)])
    async def analyze_video(request: Request, file: UploadFile = File(...),
                            experiment_id: str | None = Form(None, max_length=32),
                            name: str | None = Form(None, max_length=200),
                            analysis_config: str | None = Form(None, max_length=20000),
                            calibration: str | None = Form(None, max_length=5000)):
        st = request.app.state
        try:
            cfg = json.loads(analysis_config) if analysis_config else None
            cal = validate_calibration(json.loads(calibration)) if calibration else None
        except json.JSONDecodeError as exc:
            raise ValueError(f"analysis_config/calibration must be JSON: {exc}") from exc
        path, original, _ = await save_upload(file, st.settings.uploads_dir, st.settings.max_upload_bytes)
        try:
            probe_video(path, st.settings.max_upload_bytes)
        except VideoValidationError as exc:
            path.unlink(missing_ok=True)
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
        service = svc(request)
        try:
            if experiment_id is None:
                exp = service.create(ExperimentCreate(name=name or Path(original).stem or "Uploaded video"))
                experiment_id = exp.id
            return service.start_analysis(experiment_id, f"upload:{path.name}", original, cfg, cal)
        except Exception:
            path.unlink(missing_ok=True)
            raise

    @app.get("/api/samples", tags=["analysis"])
    def samples(request: Request):
        return request.app.state.samples.list()

    @app.post("/api/analyze-sample", response_model=JobOut, status_code=202, tags=["analysis"],
              dependencies=write + [Depends(limited)])
    def analyze_sample(body: AnalyzeSampleRequest, request: Request):
        st = request.app.state
        sample = st.samples.get(body.sample_id)
        if sample is None:
            raise NotFound(f"sample {body.sample_id}")
        if not st.samples.available(sample):
            raise Conflict(f"Sample {body.sample_id} is not downloaded on this server. {sample.get('download_hint', '')}")
        cfg = {**(sample.get("analysis_config") or {}), **(body.analysis_config or {})}
        cal = validate_calibration(body.calibration) if body.calibration else validate_calibration(sample.get("calibration"))
        service = svc(request)
        experiment_id = body.experiment_id
        if experiment_id is None:
            cond = sample.get("conditions") or {}
            exp = service.create(ExperimentCreate(
                name=sample["title"], description=f"Source: {sample['source']}",
                fuel_type=cond.get("fuel_type"), oxygen_fraction=cond.get("oxygen_fraction"),
                dataset_ref=sample["id"]), data_class=sample["data_class"])
            experiment_id = exp.id
        return service.start_analysis(experiment_id, f"sample:{sample['id']}", sample["id"], cfg, cal)

    # -- jobs ---------------------------------------------------------------------------------

    def _job(request: Request, job_id: str):
        with request.app.state.db.session() as s:
            job = repo.get_job(s, job_id)
            if job is None:
                raise NotFound(job_id)
            return job

    @app.get("/api/jobs/{job_id}", response_model=JobOut, tags=["jobs"])
    def get_job(job_id: str, request: Request):
        return _job(request, job_id)

    @app.post("/api/jobs/{job_id}/cancel", tags=["jobs"], dependencies=write)
    def cancel_job(job_id: str, request: Request):
        try:
            return {"job_id": job_id, "status": request.app.state.jobs.cancel(job_id)}
        except KeyError as exc:
            raise NotFound(job_id) from exc

    @app.get("/api/jobs/{job_id}/telemetry", tags=["jobs"])
    def job_telemetry(job_id: str, request: Request, after: int = Query(-1, ge=-1), limit: int = Query(500, ge=1, le=2000)):
        job = _job(request, job_id)
        events = request.app.state.jobs.events_since(job_id, after, limit)
        return {"job_id": job_id, "status": job.status, "progress": job.progress,
                "events": _clean(events), "last_seq": events[-1]["seq"] if events else after}

    @app.get("/api/jobs/{job_id}/result", tags=["jobs"])
    def job_result(job_id: str, request: Request, format: str = Query("json", pattern="^(json|csv)$"),
                   contours: bool = Query(False)):
        job = _job(request, job_id)
        json_path, csv_path = svc(request).result_files(job)
        if format == "csv":
            return Response(csv_path.read_bytes(), media_type="text/csv",
                            headers={"Content-Disposition": f'attachment; filename="{job_id}.csv"'})
        data = json.loads(json_path.read_text())
        if not contours:
            for m in data.get("measurements", []):
                m.pop("contour_px", None)
        return JSONResponse(data)

    @app.websocket("/api/jobs/{job_id}/ws")
    async def job_ws(websocket: WebSocket, job_id: str, after: int = -1, api_key: str | None = None):
        st = websocket.app.state
        if st.settings.api_key is not None and api_key != st.settings.api_key:
            await websocket.close(code=4401)
            return
        await websocket.accept()
        seq = after
        try:
            while True:
                with st.db.session() as s:
                    job = repo.get_job(s, job_id)
                if job is None:
                    await websocket.send_json({"type": "error", "message": f"job {job_id} not found"})
                    break
                events = st.jobs.events_since(job_id, seq, 200)
                if events:
                    seq = events[-1]["seq"]
                    await websocket.send_json({"type": "telemetry", "status": job.status,
                                               "progress": job.progress, "events": _clean(events)})
                if job.status in TERMINAL and not st.jobs.events_since(job_id, seq, 1):
                    await websocket.send_json(_clean({"type": "done", "status": job.status, "error": job.error,
                                                      "summary": job.summary}))
                    break
                await asyncio.sleep(0.2)
        except WebSocketDisconnect:
            return
        await websocket.close()

    # -- prediction and models ---------------------------------------------------------------------

    @app.post("/api/predict", tags=["prediction"], dependencies=[Depends(limited)])
    def predict(body: PredictRequest, request: Request):
        st = request.app.state
        if st.model is None:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, st.model_error or "Model unavailable.")
        result = st.model.predict(body.inputs, body.interval)
        if body.experiment_id:
            with st.db.session() as s:
                exp = repo.get_experiment(s, body.experiment_id)
                if exp is None:
                    raise NotFound(body.experiment_id)
                exp.model_version = result["model_version"]
                s.commit()
        return result

    @app.get("/api/models", tags=["prediction"])
    def models(request: Request):
        st = request.app.state
        if st.model is None:
            return {"models": [], "error": st.model_error}
        a = st.model.a
        keys = ("model_version", "created_at", "population", "target", "training_data", "distribution",
                "features", "feature_ranges", "coefficient_table_standardized", "interval_inflation", "limitations")
        sel = a["validation"]["selected"]
        return _clean({"models": [{**{k: a[k] for k in keys},
                                   "validation": {"scheme": a["validation"]["scheme"], "selected": sel,
                                                  "baseline_intercept_only": a["validation"]["baseline_intercept_only"],
                                                  "baseline_note": a["validation"].get("baseline_note"),
                                                  "candidates": a["validation"]["all_candidates"]}}]})

    # -- datasets ----------------------------------------------------------------------------------

    @app.get("/api/datasets", tags=["data"])
    def datasets(request: Request):
        st = request.app.state
        out = []
        if st.dataset is not None:
            out.append({"id": "sflame_test_points", "title": "NASA ACME s-Flame test points (PSI-23)",
                        "data_class": "nasa_psi", "rows": int(len(st.dataset)),
                        "provenance": {"source": "NASA Physical Sciences Informatics, PSI-23", "license": "CC0-1.0",
                                       "doi": "10.60555/k57n-p030",
                                       "build": "python -m backend.data.sflame_dataset"},
                        "quality_report": st.quality, "columns": list(st.dataset.columns)})
        return {"datasets": out}

    @app.get("/api/datasets/sflame/test-points", tags=["data"])
    def sflame_rows(request: Request, outcome: str | None = Query(None, max_length=40),
                    flow_programme: str | None = Query(None, max_length=20),
                    test_day: str | None = Query(None, max_length=5), limit: int = Query(500, ge=1, le=1000)):
        df = request.app.state.dataset
        if df is None:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Dataset not built.")
        if outcome:
            df = df[df["outcome"] == outcome]
        if flow_programme:
            df = df[df["flow_programme"] == flow_programme]
        if test_day:
            df = df[df["test_day"].astype(str) == test_day]
        rows = df.head(limit).to_dict("records")
        return {"total": int(len(df)), "rows": _clean(rows)}

    # -- export ---------------------------------------------------------------------------------------

    @app.post("/api/export", tags=["export"])
    def export(body: ExportRequest, request: Request):
        content, media, filename = svc(request).export(body.experiment_id, body.format)
        return Response(content, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"'})

    return app


app = create_app()
