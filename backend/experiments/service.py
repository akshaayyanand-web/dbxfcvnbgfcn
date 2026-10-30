"""Experiment orchestration: create/update/duplicate experiments, start analyses, exports.

An experiment is the platform's "digital twin" record: conditions, calibration,
input reference, analysis configuration, every analysis job and its results,
the model version used for predictions, and provenance (``data_class``).
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from backend.database import AnalysisJob, AppSetting, Database, Experiment, utcnow
from backend.experiments import repository as repo
from backend.experiments.schemas import CalibrationIn, ExperimentCreate, ExperimentUpdate
from backend.jobs import JobManager
from backend.vision.calibration import Calibration, CalibrationError
from backend.vision.cv_engine import AnalysisConfig


class NotFound(LookupError):
    pass


class Conflict(RuntimeError):
    pass


def validate_analysis_config(cfg: dict | None) -> dict:
    """Round-trip through AnalysisConfig so invalid settings fail at submission, not in the worker."""
    try:
        config = AnalysisConfig.from_dict(cfg or {})
        config.validate()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid analysis_config: {exc}") from exc
    return json.loads(json.dumps(config.to_dict(), default=str))


def validate_calibration(cal: CalibrationIn | dict | None) -> dict | None:
    if cal is None:
        return None
    data = cal.model_dump() if isinstance(cal, CalibrationIn) else dict(cal)
    try:
        return Calibration.from_dict(data).to_dict()
    except (CalibrationError, TypeError) as exc:
        raise ValueError(f"Invalid calibration: {exc}") from exc


class ExperimentService:
    def __init__(self, db: Database, jobs: JobManager):
        self.db = db
        self.jobs = jobs

    def default_analysis_config(self) -> dict | None:
        """The workspace default from Settings (used when an experiment brings no configuration)."""
        with self.db.session() as s:
            row = s.get(AppSetting, "default_analysis_config")
            value = (row.value or {}).get("v") if row else None
        return value or None

    def create(self, body: ExperimentCreate, data_class: str = "user") -> Experiment:
        with self.db.session() as s:
            exp = Experiment(
                name=body.name, description=body.description, data_class=data_class,
                fuel_type=body.fuel_type, oxygen_fraction=body.oxygen_fraction,
                chamber_pressure_kpa=body.chamber_pressure_kpa, burn_duration_s=body.burn_duration_s,
                camera=body.camera, calibration=validate_calibration(body.calibration),
                analysis_config=validate_analysis_config(body.analysis_config or self.default_analysis_config())
                if (body.analysis_config or self.default_analysis_config()) else None,
                dataset_ref=body.dataset_ref,
            )
            s.add(exp)
            s.commit()
            return exp

    def update(self, experiment_id: str, body: ExperimentUpdate) -> Experiment:
        with self.db.session() as s:
            exp = repo.get_experiment(s, experiment_id)
            if exp is None:
                raise NotFound(experiment_id)
            data = body.model_dump(exclude_unset=True)
            if "calibration" in data:
                data["calibration"] = validate_calibration(body.calibration)
            if data.get("analysis_config") is not None:
                data["analysis_config"] = validate_analysis_config(data["analysis_config"])
            for k, v in data.items():
                setattr(exp, k, v)
            exp.updated_at = utcnow()
            s.commit()
            return exp

    def duplicate(self, experiment_id: str) -> Experiment:
        """Copy the configuration (conditions, calibration, analysis settings), not the results or video."""
        with self.db.session() as s:
            src = repo.get_experiment(s, experiment_id)
            if src is None:
                raise NotFound(experiment_id)
            exp = Experiment(
                name=f"{src.name} (copy)", description=src.description, data_class=src.data_class,
                fuel_type=src.fuel_type, oxygen_fraction=src.oxygen_fraction,
                chamber_pressure_kpa=src.chamber_pressure_kpa, burn_duration_s=src.burn_duration_s,
                camera=src.camera, calibration=src.calibration, analysis_config=src.analysis_config,
                dataset_ref=src.dataset_ref,
            )
            s.add(exp)
            s.commit()
            return exp

    def delete(self, experiment_id: str) -> None:
        with self.db.session() as s:
            exp = repo.get_experiment(s, experiment_id)
            if exp is None:
                raise NotFound(experiment_id)
            if exp.status in ("queued", "processing"):
                raise Conflict("Cancel the running analysis before deleting the experiment.")
            s.delete(exp)
            s.commit()

    def start_analysis(self, experiment_id: str, input_ref: str, filename: str | None,
                       analysis_config: dict | None = None, calibration: dict | None = None) -> AnalysisJob:
        with self.db.session() as s:
            exp = repo.get_experiment(s, experiment_id)
            if exp is None:
                raise NotFound(experiment_id)
            if exp.status in ("queued", "processing"):
                raise Conflict(f"Experiment {experiment_id} already has an analysis in progress.")
            cfg = validate_analysis_config(analysis_config if analysis_config is not None else exp.analysis_config)
            cal = calibration if calibration is not None else exp.calibration
            job = AnalysisJob(experiment_id=exp.id, input_ref=input_ref, config=cfg, calibration=cal)
            s.add(job)
            s.flush()
            exp.latest_job_id, exp.status, exp.video_ref = job.id, "queued", input_ref
            exp.analysis_config, exp.calibration = cfg, cal
            if filename:
                exp.video_filename = filename
            exp.updated_at = utcnow()
            s.commit()
            job_id = job.id
        self.jobs.submit(job_id)
        with self.db.session() as s:
            return repo.get_job(s, job_id)

    def reanalyze(self, experiment_id: str, analysis_config: dict | None = None) -> AnalysisJob:
        with self.db.session() as s:
            exp = repo.get_experiment(s, experiment_id)
            if exp is None:
                raise NotFound(experiment_id)
            if not exp.video_ref:
                raise Conflict("The experiment has no video or sample to analyse.")
            ref, name = exp.video_ref, exp.video_filename
        return self.start_analysis(experiment_id, ref, name, analysis_config)

    # -- results and export ----------------------------------------------------------

    def result_files(self, job: AnalysisJob) -> tuple[Path, Path]:
        if job.status != "completed" or not job.result_dir:
            raise Conflict(f"Job {job.id} has no results (status: {job.status}).")
        d = Path(job.result_dir)
        return d / "analysis.json", d / "measurements.csv"

    def export(self, experiment_id: str, fmt: str) -> tuple[bytes, str, str]:
        """Return ``(content, media_type, filename)`` for a complete experiment record."""
        with self.db.session() as s:
            exp = repo.get_experiment(s, experiment_id)
            if exp is None:
                raise NotFound(experiment_id)
            job = repo.get_job(s, exp.latest_job_id) if exp.latest_job_id else None
            record = {c.name: getattr(exp, c.name) for c in Experiment.__table__.columns}
            jobs = [{c.name: getattr(j, c.name) for c in AnalysisJob.__table__.columns if c.name != "result_dir"}
                    for j in repo.list_jobs(s, experiment_id)]
        if fmt == "csv":
            if job is None or job.status != "completed":
                raise Conflict("CSV export needs a completed analysis.")
            _, csv_path = self.result_files(job)
            return csv_path.read_bytes(), "text/csv", f"{experiment_id}_measurements.csv"
        analysis = None
        if job is not None and job.status == "completed":
            json_path, _ = self.result_files(job)
            analysis = json.loads(json_path.read_text())
        payload = {"schema": "flame-in-freefall/experiment-record/v1", "experiment": record, "jobs": jobs,
                   "latest_analysis": analysis}
        return json.dumps(payload, indent=1, default=str).encode(), "application/json", f"{experiment_id}.json"


def rows_to_csv(rows: list[dict]) -> str:
    if not rows:
        return ""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()
