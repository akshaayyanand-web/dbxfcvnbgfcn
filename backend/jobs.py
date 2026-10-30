"""Background analysis jobs with persisted state, cancellation, telemetry and restart recovery.

A thread pool runs ``FlameAnalyzer`` jobs (CPU-bound OpenCV/NumPy work releases the
GIL for most of the time). Job state lives in the database; per-frame telemetry is
kept in a bounded in-memory ring buffer per job for live streaming (WebSocket or
polling) and is persisted in full only as the final result files.

Recovery: on startup, jobs left ``processing`` by a crash are marked ``failed``
("interrupted"), because a partial analysis cannot be resumed exactly. ``queued``
jobs are resubmitted.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select

from backend.config import Settings
from backend.data.samples import SampleRegistry
from backend.database import AnalysisJob, Database, Experiment, utcnow
from backend.vision.calibration import Calibration, CalibrationError
from backend.vision.cv_engine import (
    AnalysisCancelled,
    AnalysisConfig,
    AnalysisProgress,
    FlameAnalysisError,
    FlameAnalyzer,
)

logger = logging.getLogger("flame.jobs")
TERMINAL = {"completed", "failed", "cancelled"}


@dataclass
class _Runtime:
    cancel: threading.Event = field(default_factory=threading.Event)
    events: deque = field(default_factory=lambda: deque(maxlen=2000))
    seq: int = 0
    status: str = "queued"
    lock: threading.Lock = field(default_factory=threading.Lock)


def telemetry_event(p: AnalysisProgress, seq: int) -> dict:
    m = p.measurement
    return {
        "seq": seq,
        "frame_index": m.frame_index,
        "timestamp_s": m.timestamp_s,
        "status": m.status,
        "fraction": round(p.fraction, 4),
        "frames_analyzed": p.frames_analyzed,
        "elapsed_s": round(p.elapsed_s, 3),
        "equivalent_radius_px": m.equivalent_radius_px,
        "radius_mm": m.radius_mm,
        "limb_fit_ok": m.limb_fit_ok,
        "limb_radius_px": m.limb_radius_px,
        "limb_radius_mm": m.limb_radius_mm,
        "limb_center_px": [m.limb_center_x_px, m.limb_center_y_px] if m.limb_center_x_px is not None else None,
        "centroid_px": [m.centroid_x_px, m.centroid_y_px] if m.centroid_x_px is not None else None,
        "confidence": m.confidence,
        "circularity": m.circularity,
        "contour_px": m.contour_px,
        "warnings": m.warnings[:3],
    }


class JobManager:
    def __init__(self, db: Database, settings: Settings, samples: SampleRegistry):
        self.db = db
        self.settings = settings
        self.samples = samples
        self.pool = ThreadPoolExecutor(max_workers=settings.max_workers, thread_name_prefix="flame-job")
        self._rt: dict[str, _Runtime] = {}
        self._lock = threading.Lock()

    # -- runtime bookkeeping ---------------------------------------------------------

    def _runtime(self, job_id: str) -> _Runtime:
        with self._lock:
            rt = self._rt.get(job_id)
            if rt is None:
                rt = self._rt[job_id] = _Runtime(events=deque(maxlen=self.settings.telemetry_buffer))
            return rt

    def resolve_input(self, input_ref: str) -> Path:
        kind, _, ref = input_ref.partition(":")
        if kind == "upload":
            path = (self.settings.uploads_dir / Path(ref).name).resolve()
            if not path.is_file():
                raise FileNotFoundError("Uploaded video is no longer available.")
            return path
        if kind == "sample":
            return self.samples.resolve(ref)
        raise ValueError(f"Unknown input reference kind: {kind!r}")

    # -- public API --------------------------------------------------------------------

    def submit(self, job_id: str) -> None:
        self._runtime(job_id)
        self.pool.submit(self._run, job_id)

    def cancel(self, job_id: str) -> str:
        with self.db.session() as s:
            job = s.get(AnalysisJob, job_id)
            if job is None:
                raise KeyError(job_id)
            if job.status in TERMINAL:
                return job.status
            if job.status == "queued":
                job.status, job.finished_at, job.message = "cancelled", utcnow(), "cancelled before start"
                exp = s.get(Experiment, job.experiment_id)
                if exp and exp.latest_job_id == job_id:
                    exp.status = "cancelled"
                s.commit()
        self._runtime(job_id).cancel.set()
        return "cancelling"

    def events_since(self, job_id: str, after_seq: int = -1, limit: int = 500) -> list[dict]:
        rt = self._runtime(job_id)
        with rt.lock:
            return [e for e in rt.events if e["seq"] > after_seq][:limit]

    def recover(self) -> dict:
        failed = requeued = 0
        with self.db.session() as s:
            for job in s.scalars(select(AnalysisJob).where(AnalysisJob.status.in_(["queued", "processing"]))):
                if job.status == "processing":
                    job.status, job.finished_at = "failed", utcnow()
                    job.error = "Interrupted by a server restart; partial analyses cannot be resumed. Re-run it."
                    exp = s.get(Experiment, job.experiment_id)
                    if exp and exp.latest_job_id == job.id:
                        exp.status = "failed"
                    failed += 1
                else:
                    requeued += 1
            s.commit()
            queued = [j.id for j in s.scalars(select(AnalysisJob).where(AnalysisJob.status == "queued"))]
        for jid in queued:
            self.submit(jid)
        return {"failed_interrupted": failed, "requeued": requeued}

    def shutdown(self) -> None:
        for rt in self._rt.values():
            rt.cancel.set()
        self.pool.shutdown(wait=True, cancel_futures=True)

    # -- worker ------------------------------------------------------------------------

    def _set(self, job_id: str, **fields) -> None:
        with self.db.session() as s:
            job = s.get(AnalysisJob, job_id)
            for k, v in fields.items():
                setattr(job, k, v)
            exp = s.get(Experiment, job.experiment_id)
            if exp and exp.latest_job_id == job_id and "status" in fields:
                exp.status = fields["status"]
            s.commit()

    def _run(self, job_id: str) -> None:
        rt = self._runtime(job_id)
        with self.db.session() as s:
            job = s.get(AnalysisJob, job_id)
            if job is None or job.status != "queued":
                return
            config, calibration, input_ref, experiment_id = job.config, job.calibration, job.input_ref, job.experiment_id
        if rt.cancel.is_set():
            self._set(job_id, status="cancelled", finished_at=utcnow(), message="cancelled before start")
            return
        self._set(job_id, status="processing", started_at=utcnow(), message="analysing")
        last_db = [0.0]

        def on_progress(p: AnalysisProgress) -> None:
            with rt.lock:
                rt.seq += 1
                rt.events.append(telemetry_event(p, rt.seq))
            now = time.monotonic()
            if now - last_db[0] > 0.5:
                last_db[0] = now
                self._set(job_id, progress=p.fraction, frames_processed=p.frames_analyzed)

        try:
            path = self.resolve_input(input_ref)
            cfg = AnalysisConfig.from_dict(config or {})
            cal = Calibration.from_dict(calibration) if calibration else None
            result = FlameAnalyzer(cfg, cal).analyze(path, experiment_id, on_progress, rt.cancel)
            out_dir = self.settings.results_dir / job_id
            out_dir.mkdir(parents=True, exist_ok=True)
            result.export_json(out_dir / "analysis.json")
            result.export_csv(out_dir / "measurements.csv")
            self._set(job_id, status="completed", finished_at=utcnow(), progress=1.0,
                      frames_processed=result.summary["frames_analyzed"], message="completed",
                      summary=json.loads(json.dumps(result.summary, default=str)),
                      issues=[i.to_dict() for i in result.issues], result_dir=str(out_dir))
        except AnalysisCancelled as exc:
            self._set(job_id, status="cancelled", finished_at=utcnow(), message=str(exc))
        except (FlameAnalysisError, CalibrationError, ValueError, FileNotFoundError, KeyError) as exc:
            self._set(job_id, status="failed", finished_at=utcnow(), error=str(exc), message="failed")
        except Exception:  # noqa: BLE001 - unexpected errors are logged in full but not leaked to clients
            logger.exception("job %s crashed", job_id)
            self._set(job_id, status="failed", finished_at=utcnow(), message="failed",
                      error="Internal error during analysis (logged on the server).")
        finally:
            with self._lock:
                rt.status = "done"
