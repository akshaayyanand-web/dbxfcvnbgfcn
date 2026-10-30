# Architecture

## Guiding principle

Build a smaller, scientifically validated engine rather than a large AI system
whose predictions cannot be checked. Each subsystem is shipped only with tests
that verify it against known references.

## Seven subsystems

```
                 ┌────────────────────────────────────────────────────────────┐
                 │ 7. Enterprise infrastructure (FastAPI, PostgreSQL, jobs,   │
                 │    auth, logging, Docker, CI)                       [done] │
                 └───────────────┬───────────────────────────┬────────────────┘
                                 │                           │
┌────────────────────┐   ┌───────▼──────────┐   ┌────────────▼──────────┐   ┌──────────────────┐
│ 1. Scientific data │   │ 2. Computer      │──▶│ 4. Physics engine     │──▶│ 6. Reporting     │
│    (ingestion,     │   │    vision  [done]│   │  geometry, kinematics,│   │  PDF/CSV/JSON    │
│    provenance,     │   │  segmentation,   │   │  uncertainty,         │   │ [JSON/CSV done,  │
│    registry)       │   │  tracking,       │   │  validation    [done] │   │   PDF planned]   │
│          [s-Flame] │   │  calibration,    │   │                       │   └──────────────────┘
│                    │   │  limb fit [done] │   └────────────┬──────────┘            ▲
└─────────┬──────────┘   └───────┬──────────┘                │                       │
          │                      │ per-frame events          │                       │
          ▼                      ▼                           ▼                       │
┌────────────────────┐   ┌──────────────────┐   ┌───────────────────────┐            │
│ 3. Predictive      │   │ 5. Real-time     │   │ Experiment "digital   │────────────┘
│    intelligence    │   │    telemetry     │   │ twin" record (DB)     │
│  [s-Flame AFT done]│   │  (WebSocket)     │   │                [done] │
└────────────────────┘   │  [callback + WS  │   └───────────────────────┘
                         │   done]          │
                         └──────────────────┘
```
Status as of increment 4. Reporting (PDF) and the React frontend remain.

## Module map (implemented)

| Module | Responsibility | Depends on |
|---|---|---|
| `backend/physics/uncertainty.py` | First-order propagation, random vs systematic split | stdlib |
| `backend/physics/physics_engine.py` | Geometry formulas, timestamp-aware local-polynomial kinematics, extinction estimate | numpy |
| `backend/physics/validation.py` | Timestamp, bounds, plausibility, uncertainty checks → `ValidationIssue` | numpy |
| `backend/vision/calibration.py` | Reference-length calibration, compatibility check, optional undistortion | physics.uncertainty, OpenCV |
| `backend/vision/segmentation.py` | Otsu / fixed / adaptive / HSV / MOG2 segmentation, morphology, contours | OpenCV |
| `backend/vision/geometry.py` | Per-contour area, centroid, circles, ellipse, roughness, local contrast | physics_engine, OpenCV |
| `backend/vision/tracking.py` | Gated constant-velocity tracker, explicit failure states | geometry |
| `backend/vision/cv_engine.py` | `FlameAnalyzer`: orchestration, timestamps, telemetry, exports, overlay | all of the above, pandas |
| `backend/vision/synthetic.py` | SYNTHETIC ground-truth videos (CFR and VFR) | OpenCV, ffmpeg (VFR only) |
| `backend/tools/analyze_video.py` | CLI | cv_engine |
| `backend/tools/benchmark_cv.py` | Timing and accuracy benchmark | cv_engine, synthetic |

## Dependency map and contracts

Downstream layers must use only these contracts:

1. **`FIELD_DEFINITIONS`** (`cv_engine.py`) is the telemetry schema. API models,
   database columns, frontend types and report tables are generated from it or
   tested against it. `test_every_field_is_documented` and
   `test_data_dictionary_in_sync` enforce this in both directions.
2. **`AnalysisResult.to_json_dict()`** with `schema = flame-in-freefall/cv-analysis/v1`
   is the persisted analysis record. Any breaking change must bump the schema version.
3. **`AnalysisProgress`** is the telemetry event. The planned WebSocket layer will
   serialise `measurement.to_dict()` together with `frames_decoded`,
   `frames_analyzed`, `fraction` and `elapsed_s`.
4. **`AnalysisConfig.to_dict()/from_dict()`** is the reproducibility contract.
   Storing it with a result is enough to re-run the analysis.
5. Errors: `VideoValidationError` maps to HTTP 422, `VideoDecodeError` to 422,
   `CalibrationError` to 422, `AnalysisCancelled` to job state `cancelled`, and
   any other `FlameAnalysisError` to job state `failed` with its message.

## Processing pipeline (per frame, streaming)

```
grab → POS_MSEC timestamp → [time window / frame_step filter] → retrieve
  → [undistort] → [resize by processing_scale]
  → Gaussian blur → channel (max/gray/B/G/R) → contrast gate
  → threshold (Otsu+offset | fixed | adaptive | HSV | MOG2) → open/close
  → external contours ≥ min area → measure each → local-contrast filter
  → tracker selects / rejects → rescale to original px → calibrate (mm ± σ)
  → emit AnalysisProgress → [write annotated frame]
after last frame:
  → timestamp validation/fallback → local-polynomial kinematics on accepted samples
  → centroid displacement → extinction estimate → validation checks → summary
```

Memory use is O(frames × fields): frames are not retained. Only a simplified
contour of ≤ 72 vertices is stored per frame, and that can be disabled.

## Planned layout (remaining subsystems)

Follows the master specification, Part XVII. The directories `backend/data`,
`backend/ml`, `backend/experiments` and `backend/reports` exist as empty packages.
Their status is tracked in `PROJECT_STATUS.md`. Frontend (React + Vite + TS) and
deployment files will be added in later increments.

## Backend modules (increment 4)

| Module | Responsibility |
|---|---|
| `backend/app.py` | FastAPI routes, error mapping, CORS, auth/rate-limit dependencies, WebSocket |
| `backend/config.py` | Environment settings |
| `backend/database.py` | SQLAlchemy models `Experiment`, `AnalysisJob`, `SchemaVersion` |
| `backend/experiments/` | Pydantic schemas, repository, service (create/update/duplicate/analyse/export) |
| `backend/jobs.py` | Thread-pool job runner, telemetry ring buffer, cancellation, restart recovery |
| `backend/security.py` | Upload validation, API key, rate limiter |
| `backend/data/samples.py` | Server-side sample registry (NASA presets, synthetic demo) |
