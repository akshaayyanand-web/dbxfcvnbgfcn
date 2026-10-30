# API Documentation

Base URL: `http://<host>:8000`. The interactive OpenAPI docs are at `/docs`, and
the machine-readable schema is at `/openapi.json`. Every route below is
implemented and covered by `backend/tests/test_api.py`.

## Conventions

* **Auth:** if `FLAME_API_KEY` is set, `POST`/`PATCH`/`DELETE` require the
  header `X-API-Key: <key>`. The WebSocket takes `?api_key=<key>`. `GET` routes
  are open.
* **Errors:** `{"error": {"code": "...", "message": "..."}}` with these codes:

  | Code | Meaning |
  |---|---|
  | 401 | missing or invalid API key |
  | 404 | not found |
  | 409 | conflict (e.g. an analysis is already running) |
  | 413 | upload too large |
  | 415 | wrong file type or signature |
  | 422 | invalid input |
  | 429 | rate limit |
  | 503 | model or dataset unavailable |
* **Quantity classes:** every value is labelled per `DATA_DICTIONARY.md`.
  Predictions carry `"quantity_class": "predicted"`.
* **No server paths** appear in any response. Uploads are referenced as
  `upload:<random id>.<ext>`, samples as `sample:<id>`.
* **Rate limit:** `FLAME_RATE_LIMIT_PER_MINUTE` per client address on
  `/api/analyze-*`, `/api/experiments/{id}/reanalyze` and `/api/predict`.

## System

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | `{"status": "ok" \| "degraded", "api_version"}` (database ping) |
| GET | `/api/system/status` | Versions, database backend, experiment/job counts, workers, model, datasets, samples, storage, ffmpeg availability, auth mode, startup recovery result |

## Experiments (digital-twin records)

| Method | Path | Description |
|---|---|---|
| POST | `/api/experiments` | Create (201). The body is `ExperimentCreate`: `name`, `description`, `fuel_type`, `oxygen_fraction` (0–1), `chamber_pressure_kpa` (0–1000], `burn_duration_s`, `camera`, `calibration`, `analysis_config`, `dataset_ref`. Unknown fields → 422 |
| GET | `/api/experiments?limit&offset&status` | List, newest first |
| GET | `/api/experiments/{id}` | Read |
| PATCH | `/api/experiments/{id}` | Partial update (validated like create) |
| DELETE | `/api/experiments/{id}` | 204. Returns 409 while an analysis is queued or processing |
| POST | `/api/experiments/{id}/duplicate` | Copies the configuration (conditions, calibration, analysis settings), not the results |
| GET | `/api/experiments/{id}/jobs` | All analysis jobs of the experiment |
| POST | `/api/experiments/{id}/reanalyze` | 202. Optional body `{"analysis_config": {...}}`. Re-runs on the stored video or sample |

`calibration`: `known_length_mm`, `measured_length_px` (required);
`measured_length_sigma_px`, `known_length_sigma_mm`, `image_width`,
`image_height`, `camera_id`, `lens`, `configuration`, `method`, `notes`. The
stored record adds `mm_per_px` and `mm_per_px_sigma`. A calibration whose image
size differs from the video's fails the job (A-CAL-1).

`analysis_config`: any field of `AnalysisConfig` (see
`backend/vision/cv_engine.py`), e.g. `segmentation`, `frame_step`,
`start_time_s`, `end_time_s`, `processing_scale`, `radius_method`
(`equivalent` or `limb`), `limb_center_hint`, `limb_min_radius_mm`, `roi`,
`exclude_regions`, `decoder`. It is validated at submission (422 on error).

## Analysis

| Method | Path | Description |
|---|---|---|
| POST | `/api/analyze-video` | `multipart/form-data`: `file` (.mp4/.mov/.avi; signature-checked; size ≤ `FLAME_MAX_UPLOAD_MB`), optional `experiment_id`, `name`, `analysis_config` (JSON string), `calibration` (JSON string). Creates an experiment if none is given. → 202 `JobOut` |
| GET | `/api/samples` | Server-side samples with provenance, conditions, calibration preset and `available` |
| POST | `/api/analyze-sample` | `{"sample_id", "experiment_id"?, "analysis_config"?, "calibration"?}` → 202 `JobOut`. NASA samples need their image sequence downloaded (409 otherwise). `SYNTHETIC/demo` is generated on demand |

## Jobs

States: `queued → processing → completed | failed | cancelled`.

| Method | Path | Description |
|---|---|---|
| GET | `/api/jobs/{id}` | `JobOut`: status, progress (0–1), frames_processed, message, error, config, calibration, summary, issues |
| POST | `/api/jobs/{id}/cancel` | `{"status": "cancelled" \| "cancelling" \| <terminal state>}` |
| GET | `/api/jobs/{id}/telemetry?after=<seq>&limit` | Per-frame events newer than `seq` (ring buffer of `FLAME_TELEMETRY_BUFFER`) |
| WS | `/api/jobs/{id}/ws?after=<seq>&api_key=` | Streams `{"type": "telemetry", "events": [...]}`, then `{"type": "done", "status", "summary", "error"}` |
| GET | `/api/jobs/{id}/result?format=json\|csv&contours=false` | Full analysis record (JSON; contours optional) or per-frame CSV. Returns 409 if not completed |

Telemetry event fields: `seq`, `frame_index`, `timestamp_s`, `status`,
`fraction`, `frames_analyzed`, `elapsed_s`, `equivalent_radius_px`,
`radius_mm`, `limb_fit_ok`, `limb_radius_px`, `limb_radius_mm`,
`limb_center_px`, `centroid_px`, `confidence`, `circularity`, `contour_px`
(≤ 72 points), `warnings`.

## Prediction

| Method | Path | Description |
|---|---|---|
| POST | `/api/predict` | `{"inputs": {...}, "interval": 0.8, "experiment_id"?}`. Inputs: `x_H2`, `x_CH4`, `x_C2H4` (mole fractions), `log_total_slpm`, `he_atmosphere` (0/1), `test_order_in_day`. Returns the median lifetime, interval (parameter uncertainty + cross-validated inflation), `warnings` (out-of-range/unseen values), population and limitations. Post-ignition inputs → 422 |
| GET | `/api/models` | Model card: version, population, target, training-data hash, features and ranges, coefficient table (time ratios + 95 % CI), validation (all candidates, baseline), interval calibration, limitations |

## Data and export

| Method | Path | Description |
|---|---|---|
| GET | `/api/datasets` | Dataset cards (NASA s-Flame test points: provenance, licence, quality report, columns) |
| GET | `/api/datasets/sflame/test-points?outcome&flow_programme&test_day&limit` | Filtered rows |
| POST | `/api/export` | `{"experiment_id", "format": "json" \| "csv"}`. JSON gives the full experiment record (experiment, jobs, latest analysis); CSV gives the per-frame measurements (409 without a completed analysis) |

## Example

```bash
curl -X POST localhost:8000/api/analyze-sample -H 'Content-Type: application/json' -d '{"sample_id": "PSI-23/19254C1"}'
```
