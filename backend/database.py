"""SQLAlchemy persistence: experiments ("digital twin" records) and analysis jobs.

SQLite is the zero-configuration default; set ``FLAME_DATABASE_URL`` to a
PostgreSQL URL (``postgresql+psycopg://...``) for deployment. Schema creation
uses ``create_all`` plus a ``schema_version`` row; see DEPLOYMENT_GUIDE.md for the
migration policy.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, event, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

SCHEMA_VERSION = 1


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class Base(DeclarativeBase):
    pass


class SchemaVersion(Base):
    __tablename__ = "schema_version"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[int] = mapped_column(Integer)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Experiment(Base):
    __tablename__ = "experiments"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("EXP"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    data_class: Mapped[str] = mapped_column(String(32), default="user")  # user | nasa_psi | synthetic
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    fuel_type: Mapped[str | None] = mapped_column(String(200), nullable=True)
    oxygen_fraction: Mapped[float | None] = mapped_column(Float, nullable=True)
    chamber_pressure_kpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    burn_duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    camera: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    calibration: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    analysis_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    dataset_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    video_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)   # "upload:<id>" or "sample:<id>"
    video_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latest_job_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    jobs: Mapped[list["AnalysisJob"]] = relationship(back_populates="experiment", cascade="all, delete-orphan")


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: new_id("JOB"))
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(16), default="queued")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    frames_processed: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_ref: Mapped[str] = mapped_column(String(200))
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    calibration: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    issues: Mapped[list | None] = mapped_column(JSON, nullable=True)
    result_dir: Mapped[str | None] = mapped_column(String(500), nullable=True)  # internal, never returned by the API
    experiment: Mapped[Experiment] = relationship(back_populates="jobs")


class Database:
    def __init__(self, url: str):
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self.engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
        if url.startswith("sqlite"):
            @event.listens_for(self.engine, "connect")
            def _fk_on(dbapi_conn, _):  # noqa: ANN001 - SQLAlchemy callback signature
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA foreign_keys=ON")
                cur.execute("PRAGMA journal_mode=WAL")
                cur.close()
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_all(self) -> None:
        Base.metadata.create_all(self.engine)
        with self.session() as s:
            if s.scalar(select(SchemaVersion).limit(1)) is None:
                s.add(SchemaVersion(id=1, version=SCHEMA_VERSION))
                s.commit()

    def session(self) -> Session:
        return self.SessionLocal()

    def ping(self) -> bool:
        try:
            with self.engine.connect() as c:
                c.exec_driver_sql("SELECT 1")
            return True
        except Exception:  # noqa: BLE001 - health check must not raise
            return False
