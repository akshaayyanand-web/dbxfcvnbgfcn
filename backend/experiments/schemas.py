"""Pydantic request/response models for the API (validation of units and ranges)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

JOB_STATES = ("queued", "processing", "completed", "failed", "cancelled")


class CalibrationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    known_length_mm: float = Field(gt=0, le=10_000)
    measured_length_px: float = Field(gt=0, le=100_000)
    measured_length_sigma_px: float = Field(default=1.0, ge=0, le=10_000)
    known_length_sigma_mm: float = Field(default=0.0, ge=0, le=10_000)
    image_width: int | None = Field(default=None, gt=0, le=100_000)
    image_height: int | None = Field(default=None, gt=0, le=100_000)
    camera_id: str | None = Field(default=None, max_length=200)
    lens: str | None = Field(default=None, max_length=200)
    configuration: str | None = Field(default=None, max_length=200)
    method: str = Field(default="manual_reference_length", max_length=200)
    notes: str = Field(default="", max_length=2000)


class ExperimentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    fuel_type: str | None = Field(default=None, max_length=200)
    oxygen_fraction: float | None = Field(default=None, ge=0, le=1, description="mole fraction, 0-1")
    chamber_pressure_kpa: float | None = Field(default=None, gt=0, le=1000)
    burn_duration_s: float | None = Field(default=None, gt=0, le=3600)
    camera: dict[str, Any] | None = None
    calibration: CalibrationIn | None = None
    analysis_config: dict[str, Any] | None = None
    dataset_ref: str | None = Field(default=None, max_length=200)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank")
        return v


class ExperimentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=200)
    archived: bool | None = None
    description: str | None = Field(default=None, max_length=5000)
    fuel_type: str | None = Field(default=None, max_length=200)
    oxygen_fraction: float | None = Field(default=None, ge=0, le=1)
    chamber_pressure_kpa: float | None = Field(default=None, gt=0, le=1000)
    burn_duration_s: float | None = Field(default=None, gt=0, le=3600)
    camera: dict[str, Any] | None = None
    calibration: CalibrationIn | None = None
    analysis_config: dict[str, Any] | None = None
    dataset_ref: str | None = Field(default=None, max_length=200)


class ExperimentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: str
    data_class: str
    created_at: datetime
    updated_at: datetime
    fuel_type: str | None
    oxygen_fraction: float | None
    chamber_pressure_kpa: float | None
    burn_duration_s: float | None
    camera: dict[str, Any] | None
    calibration: dict[str, Any] | None
    analysis_config: dict[str, Any] | None
    dataset_ref: str | None
    video_ref: str | None
    video_filename: str | None
    status: str
    model_version: str | None
    latest_job_id: str | None
    archived: bool = False


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    experiment_id: str
    status: Literal["queued", "processing", "completed", "failed", "cancelled"]
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    progress: float
    frames_processed: int
    message: str
    error: str | None
    input_ref: str
    config: dict[str, Any] | None
    calibration: dict[str, Any] | None
    summary: dict[str, Any] | None
    issues: list[dict[str, Any]] | None


class AnalyzeSampleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sample_id: str = Field(min_length=1, max_length=100)
    experiment_id: str | None = Field(default=None, max_length=32)
    analysis_config: dict[str, Any] | None = None
    calibration: CalibrationIn | None = None


class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inputs: dict[str, float]
    interval: float = Field(default=0.8, gt=0.5, lt=0.99)
    experiment_id: str | None = Field(default=None, max_length=32)


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    experiment_id: str = Field(max_length=32)
    format: Literal["json", "csv"] = "json"
