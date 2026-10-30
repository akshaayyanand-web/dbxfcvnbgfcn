# Project Status

_Last updated: 2026-10-30. Submission target: 2026-11-14/15._

## Completed (increment 1)

| Component | Files | Verified by |
|---|---|---|
| Requirements analysis, risks, architecture | `ARCHITECTURE.md`, this file | review |
| Scientific assumptions register | `SCIENTIFIC_ASSUMPTIONS.md` | review |
| Data availability matrix (unverified, network-blocked) | `docs/DATA_AVAILABILITY_MATRIX.md` | review |
| Data dictionary, generated from code | `DATA_DICTIONARY.md` | `test_data_dictionary_in_sync` |
| Physics: geometry, kinematics, extinction | `backend/physics/physics_engine.py` | 20 physics tests |
| Physics: uncertainty propagation | `backend/physics/uncertainty.py` | analytic and Monte Carlo tests |
| Physics: validation checks | `backend/physics/validation.py` | tests |
| CV: calibration, segmentation (5 methods), geometry, tracking | `backend/vision/*.py` | 42 CV tests |
| CV: `FlameAnalyzer` engine with telemetry, cancellation, JSON/CSV, overlays | `backend/vision/cv_engine.py` | tests, CLI run |
| SYNTHETIC ground-truth video generator (CFR and VFR) | `backend/vision/synthetic.py` | used by tests |
| CLI and benchmark | `backend/tools/` | executed, see `TEST_REPORT.md` |

## Completed (increment 1b, after NASA access was enabled)

| Component | Files | Verified by |
|---|---|---|
| ACME catalogue verified in NASA PSI: 6 investigations, CC0, unrestricted | `docs/DATA_AVAILABILITY_MATRIX.md` | live queries, files opened |
| PSI client with provenance (DOI, licence, SHA-256) | `backend/data/psi_client.py` | live download, 6 offline tests |
| FFmpeg decoder (default) + blank-frame guard | `backend/vision/cv_engine.py` | regression tests on synthetic interlaced video |

## Completed (increment 2)

| Component | Files | Verified by |
|---|---|---|
| s-Flame test-point dataset (289 tests, labels with censoring, quality report, input manifest) | `backend/data/sflame*.py`, `data/processed/sflame_*` | 9 tests, cross-check vs NASA stop reasons |
| Image-sequence input (16-bit TIFF, filename times, dark/hot-pixel/saturation handling) | `backend/vision/image_sequence.py` | 10 tests |
| ROI / exclusion masks, static-emitter warning, non-spherical volume suppression | `backend/vision/cv_engine.py` | tests |
| In-image burner calibration | `backend/vision/calibration.py::measure_dark_disk` | synthetic test, applied to 19304A7 |
| First real flame analysis (19304A7) | `data/processed/19304A7_cv_analysis.*`, `docs/img/` | extinction within 0.18 s of the PMT |

## Completed (increment 3)

| Component | Files | Verified by |
|---|---|---|
| Shell-limb radius (RANSAC circle fit to outer half-max edges) + engine `radius_method="limb"` | `backend/vision/limb.py`, `cv_engine.py` | 8 tests, real flame 19254C1 |
| Flame-lifetime survival model (AFT, leave-one-day-out, calibrated intervals, OOD and leakage guards, JSON artifacts) | `backend/ml/survival.py`, `backend/ml/sflame_model.py`, `models/sflame_lifetime/` | 8 tests, validation table |

## Completed (increment 4)

| Component | Files | Verified by |
|---|---|---|
| FastAPI backend: 19 routes incl. experiments CRUD/duplicate/reanalyze, upload and sample analysis, jobs, telemetry polling and WebSocket, results, predict, models, datasets, export | `backend/app.py`, `backend/experiments/`, `backend/jobs.py` | 14 API tests, live uvicorn |
| Persistence (SQLAlchemy; SQLite default, PostgreSQL) and job recovery after restart | `backend/database.py`, `backend/jobs.py` | tests; Postgres in Docker |
| Security: upload signature/size/traversal checks, optional API key, rate limit, no path leaks | `backend/security.py` | tests |
| Server-side samples with measured calibration presets (2 NASA, 1 synthetic) | `data/presets/samples.json`, `backend/data/samples.py` | tests |
| Docker image, compose (API + Postgres), `.env.example`, CI workflow, API and deployment docs | `Dockerfile`, `docker-compose.yml`, `.github/workflows/ci.yml`, `API_DOCUMENTATION.md`, `DEPLOYMENT_GUIDE.md` | image built and run with Postgres (compose and CI not executed) |

## Completed (increment 5)

| Component | Files | Verified by |
|---|---|---|
| Interface-support API: frames, previews, jobs, activity, predictions, reports, dataset stats, settings, logs | `backend/api_extra.py`, `backend/media.py` | `test_api_extra.py` |
| Scientific reports: 13 sections, PDF (ReportLab + Matplotlib), JSON, CSV; experiment and comparison reports | `backend/reports/` | tests (PDF, JSON and CSV downloads) |
| Schema v2 migration (archive flag, predictions, reports, settings) | `backend/database.py` | migration test from a v1 database |

## Completed (increment 6)

| Component | Files | Verified by |
|---|---|---|
| Design system: tokens, 21 React components plus 4 chart components and the frame viewer, chart palette validated for colour-vision deficiency (light and dark) | `frontend/src/design-system/`, `frontend/src/styles/`, published design-system artifact | frontend tests; palette validator |
| Web app: app shell and 12 pages plus a 15-step guided demo, on live API data only | `frontend/src/` | typecheck, build, 11 vitest tests, browser run against the live API at 1440 px and 390 px |
| API additions for the web app: model CV predictions and metrics (incl. negative R²), model internals, dataset manifest fields, project docs, SPA serving | `backend/app.py`, `backend/api_extra.py` | 3 new tests |
| Docker: two-stage build (Node builds the frontend; the Python image serves it) | `Dockerfile` | not built in this increment |

## Remaining

1. **Data layer:** a general dataset registry for the other ACME
   investigations (PSI-10 Flame Design and PSI-159 CFI-G use different file
   naming), CIR chamber pressure/O2 if obtainable (per-test O2 is currently
   unknown on mixed days), and thermocouple conversion (type K/B, NIST
   polynomials + cold junction).
2. **CV on real imagery:** igniter-period handling and validation on more test
   points (19254C1 and 19304A7 so far; day 19256 camera data is incomplete).
   Segmentation preview on 16-bit image sequences takes about 10 s per frame.
3. **ML:** alternative model families and conformal intervals; the current
   model ranks conditions but does not beat the mean on absolute lifetime.
4. **Deployment:** run `docker compose` and the CI workflow end to end; build
   the two-stage image; Alembic if migrations stop being additive.
5. **Frontend:** browser end-to-end tests in CI (the browser run was manual),
   and upload of image-sequence archives through the web app (CLI only today).
