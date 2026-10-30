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

## Remaining (in planned order)

1. **Data layer** (`backend/data/`): ingestion, preprocessing, validation,
   provenance (checksums, URLs, retrieval dates), dataset registry, and the
   quality report. **Blocked on NASA PSI access.**
2. **ML layer** (`backend/ml/`): baselines (linear, RF, XGBoost), grouped CV,
   SHAP, conformal or quantile intervals, OOD warnings, and the model registry.
   This trains only on targets marked **A** in the availability matrix.
3. **Experiments and persistence**: SQLAlchemy models, Alembic migrations, and
   the experiment "digital twin" record.
4. **FastAPI**: endpoints from the spec, background jobs, WebSocket telemetry,
   upload validation (MIME, size, safe names), auth, rate limiting.
5. **Reports**: PDF/CSV/JSON with methodology, calibration, charts, limitations.
6. **Frontend**: React + Vite + TS mission-control UI (9 pages + presentation mode).
7. **Deployment**: Dockerfile, docker-compose (API, Postgres, Redis, web),
   `.env.example`, CI workflow, `DEPLOYMENT_GUIDE.md`.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| ACME data inaccessible (network policy now; PSI registration may be required) | No real targets, so no honest ML | Allow NASA hosts or get the files manually. Until then the demo uses labelled SYNTHETIC data and makes no NASA-trained claims. |
| Real footage harder to segment (glare, soot, dim blue edges, burner) | Radius bias or dropouts | 5 configurable methods, preview tool, contrast floor, per-frame quality/flags. Must be checked on real video. |
| Too few experiments for ML (ACME ≈ 1,500 flames across 6 investigations; per-target labels unknown) | Overfitting, wide intervals | Experiment-grouped CV, simple baselines first, report intervals and limitations |
| Temperature/soot targets may not exist in accessible data | Spec pages show nothing | Show "no validated model for this target" instead of a fabricated output |
| 1280×720 full-resolution analysis is 4.8 s per 5 s clip on the test container | Misses the 3 s target | Use `processing_scale=0.5` (1.46 s, ≤ 0.22 px extra error). Benchmark on the demo laptop. |
| Schedule (15 days) | Incomplete integration | Vertical slices with tests at every step |

## Known issues and limitations

* Reported uncertainty is a lower bound (A-UQ-3). It excludes the
  method-dependent boundary offset, which was +3.2 px for MOG2 vs Otsu on
  synthetic data.
* `frame_error` handling depends on OpenCV continuing to decode after a bad
  frame. Many containers stop at the first unreadable packet, and the run then
  reports `decoding_ended_early`.
* The tracker follows a single flame. Split or multiple flames are reduced to
  the best-matching contour.
* The VFR test needs the `ffmpeg` executable and is skipped without it.

## Dependencies

Runtime: numpy, pandas, opencv-python-headless (pinned in `backend/requirements.txt`).
Optional: ffmpeg/ffprobe. Test: pytest. Further dependencies will be added only
when their subsystem is implemented.
