"""Database access for experiments and jobs (no business rules here)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.database import AnalysisJob, Experiment


def get_experiment(s: Session, experiment_id: str) -> Experiment | None:
    return s.get(Experiment, experiment_id)


def list_experiments(s: Session, limit: int = 100, offset: int = 0, status: str | None = None) -> list[Experiment]:
    q = select(Experiment).order_by(Experiment.created_at.desc()).limit(limit).offset(offset)
    if status:
        q = q.where(Experiment.status == status)
    return list(s.scalars(q))


def count_experiments_by_status(s: Session) -> dict[str, int]:
    return {k: v for k, v in s.execute(select(Experiment.status, func.count()).group_by(Experiment.status))}


def get_job(s: Session, job_id: str) -> AnalysisJob | None:
    return s.get(AnalysisJob, job_id)


def list_jobs(s: Session, experiment_id: str) -> list[AnalysisJob]:
    return list(s.scalars(select(AnalysisJob).where(AnalysisJob.experiment_id == experiment_id)
                          .order_by(AnalysisJob.created_at.desc())))


def count_jobs_by_status(s: Session) -> dict[str, int]:
    return {k: v for k, v in s.execute(select(AnalysisJob.status, func.count()).group_by(AnalysisJob.status))}
