# Test Report

Every result here was produced by actually running the commands shown. Nothing
is extrapolated.

## Run of 2026-10-30, increment 6 (web app and design system)

```bash
python -m pytest -q
```

**Backend: 131 passed, 1 skipped (the opt-in NASA test), 0 failed (76 s).** The
3 new tests in `test_api_extra.py` cover:
* model internals and the cross-validated predictions endpoint, including that
  R² on ln(lifetime) is reported even though it is negative;
* the documents allow-list (path traversal returns 404);
* serving the built web app, with client-route fallback and API 404s intact.

```bash
cd frontend && npm run typecheck && npm test && npm run build
```

**Frontend: typecheck clean, 11 passed, build succeeded.** The tests cover
formatting, gaps kept as gaps, mm only when calibrated, rejected limb fits
hidden, CSV quoting, design-system components, the Markdown renderer (no HTML
injection), and the app shell's 7 navigation categories with an unreachable API.

**Browser run (manual, Playwright/Chromium) against the live API** with the
synthetic demo and NASA 19254C1 analysed through `/api/analyze-sample`:
* all 13 routes at 1440 px and 390 px: no console errors and no horizontal
  overflow, after three fixes found in this run;
* prediction for 19254C1 (median 14.1 s, 80 % interval 2.9–65.8 s, observed
  16.7 s), a two-experiment comparison, and experiment and comparison reports
  generated and previewed;
* frame stepping with overlays and a segmentation preview: the preview takes
  about 11 s on the 16-bit image sequence.

The chart palette was checked with the dataviz palette validator. It passes in
light and dark mode (lightness band, chroma, colour-vision-deficiency
separation, contrast).

Defects found and fixed in this run:
* Chart lines bridged frames without a value. Each series is now drawn from its
  own points, so gaps stay gaps.
* Report figures labelled radius as "measured". It is now image-derived, per
  `FIELD_DEFINITIONS`.
* Three layout overflows at phone width.

## Run of 2026-10-30, increment 5 (interface-support API, reports, data correction)

```bash
python -m pytest -q
```

**Result: 128 passed, 1 skipped (the opt-in NASA test), 0 failed (80 s).**

New `test_api_extra.py` (7 tests) covers:
* frames: media info, JPEG frames with cache identity, out-of-range 404, 409
  without input;
* segmentation preview against the synthetic truth (91.33 px at frame 30);
* prediction history and its experiment link;
* reports: 13 sections, JSON/PDF/CSV, section subsets, unknown sections
  rejected, comparison report, missing format 404;
* dataset statistics and settings: validation, and the default analysis
  config applied to new experiments;
* archive filter, processing queue, activity feed, resource and throughput
  metrics, logs;
* migration of a schema-v1 database.

**Data correction found by these tests:** the dataset statistics reported 2
duplicate test-point IDs. Cause: NASA re-runs saved as `<tp>_1`. The builder
double-counted `19256B2` and `20176K1` and dropped their `_1` runs (A-SF-8).

After the fix:
* 289 runs, 0 duplicates;
* `20176K1_1` added (extinguished after 2.73 s);
* `19256B2_1` had no fuel flow.

The retrained lifetime model is `sflame-lifetime-ab84071f3631`. Every time ratio
moved by at most 0.01. C-index across days is 0.696 (was 0.697), within-day
0.561, and median |log error| 0.727. The interval inflation is
×1.38 (was ×1.36). The increment-3 tables
below are kept as recorded at the time.

## Run of 2026-10-30, increment 4 (FastAPI backend, persistence, Docker)

```bash
FLAME_RUN_NASA_TESTS=1 python -m pytest -q
```

**Result: 122 passed, 0 failed, 0 skipped (83 s).** Without
`FLAME_RUN_NASA_TESTS`, the one NASA end-to-end test is skipped (it needs the
580 MB 19254C1 image sequence).

`test_api.py` (14 tests) covers:
* health and status, with no path leaks;
* experiment CRUD and validation (O2 > 1, blank name, unknown field, bad
  calibration, bad analysis config);
* upload → job → telemetry paging → JSON/CSV results → WebSocket stream →
  export → reanalysis;
* upload security: wrong extension, spoofed signature, empty file,
  valid-signature-but-undecodable, path-traversal file name, size limit with
  cleanup;
* samples, cancellation of a queued job and the conflicts it causes;
* restart recovery (processing → failed, queued → completed);
* prediction (OOD warning, forbidden input, missing input, experiment
  model-version link) and model unavailable (503);
* datasets and filters;
* API key (401, reads open, WebSocket rejected) and rate limiting (429);
* NASA sample end to end (opt-in): 19254C1 through the API, 159 limb fits,
  the same as the standalone run.

### Live server and container checks

| Check | Result |
|---|---|
| `uvicorn backend.app:app` | health OK, 19 routes in OpenAPI, `/docs` 200, JSON logs |
| `docker build` (base `mirror.gcr.io/library/python:3.13-slim`, Docker Hub was rate-limited) | built, 1.5 GB |
| API container + `postgres:16-alpine` | health `healthy`; writes without key → 401; synthetic job completed (150 frames) with rows in PostgreSQL; prediction OK |
| NASA sample 19254C1 inside the container (read-only data mount) | completed in 26 s, 159 limb fits, mean R 16.04 mm, identical to local |
| Error log lines | 0 |

`docker compose up` itself and the GitHub Actions workflow
(`.github/workflows/ci.yml`) were written but **not executed** in this
environment.

## Run of 2026-10-30, increment 3 (shell-limb radius, flame-lifetime model)

```bash
python -m pytest -q
```

**Result: 108 passed, 0 failed (44.1 s).** New suites:
* `test_limb.py` (8): outer radius within 1 px on synthetic projected shells
  (full, C-shaped, half, clipped). Interior igniter and uneven shell ignored.
  Noise-only and 60° arcs rejected. Engine limb mode on a synthetic growing
  shell: radius ±1 px, growth rate within 5 %, igniter spot and saturated frame
  rejected, volume from limb radius.
* `test_ml.py` (8): AFT parameter recovery with censoring (Weibull,
  log-normal). Naive regression biased low under censoring. Kaplan–Meier and
  C-index reference values. Population selection. Forbidden-feature guard. No
  test day in its own training fold. Reproducible artifacts. Out-of-range and
  post-ignition inputs rejected.

### Real flame, shell-limb radius: PSI-23 19254C1 (C2H4/N2, ~21 % O2, constant flow)

| Check | Result |
|---|---|
| Burner calibration (this test) | 98 ± 1 px (19304A7: 103 ± 2.5 px), so ±2.5 % systematic is added |
| Limb fits accepted | 159 of 210 analysed frames (ignition flash, igniter and dim partial shells rejected) |
| Flame-shell radius | 12.1 mm (+2.4 s) → 18.6 mm (+15.3 s), monotonic growth |
| Growth rate dR/dt | ≈1.4 mm/s early, decaying to ≈0.4 mm/s (decelerating expansion) |
| Radius uncertainty | ±0.48 mm median (calibration ≈0.44 mm dominates) |
| Area-equivalent vs limb radius | −12 % median (IQR −15.7 to −8.5 %): the old method under-measures |
| Camera extinction vs OH* PMT | +16.57 ± 0.04 s vs +16.74 s (0.17 s apart) |
| Wall time | 27 s for 210 frames at 0.5 scale (limb fit ≈0.1 s per frame) |

Figure: `docs/img/PSI-23_19254C1_limb_overlay.jpg`. Yellow is the limb fit,
white the area-equivalent circle, cyan the threshold outline.

### Flame-lifetime model (constant-flow s-Flame, leave-one-test-day-out)

| Candidate | Dist | n | C (pooled) | C (within day) | median abs log error (events) | 80 % PI coverage |
|---|---|---|---|---|---|---|
| baseline_intercept_only | weibull | 144 | 0.198 | 0.500 | 0.720 | 0.96 |
| baseline_intercept_only | lognormal | 144 | 0.193 | 0.500 | 0.653 | 0.88 |
| fuel_composition | weibull | 144 | 0.599 | 0.444 | 0.630 | 0.77 |
| fuel_composition | lognormal | 144 | 0.598 | 0.430 | 0.614 | 0.82 |
| fuel_and_flow | weibull | 144 | 0.622 | 0.281 | 0.716 | 0.77 |
| fuel_and_flow | lognormal | 144 | 0.610 | 0.285 | 0.770 | 0.84 |
| fuel_flow_atmosphere | weibull | 144 | 0.688 | 0.425 | 0.805 | 0.73 |
| fuel_flow_atmosphere | lognormal | 144 | 0.693 | 0.587 | 0.772 | 0.72 |
| fuel_flow_atmosphere_order | weibull | 144 | 0.689 | 0.517 | 0.771 | 0.65 |
| fuel_flow_atmosphere_order | lognormal | 144 | 0.697 | 0.562 | 0.727 | 0.69 |
| with_o2 | weibull | 105 | 0.725 | 0.342 | 0.606 | 0.65 |
| with_o2 | lognormal | 105 | 0.738 | 0.572 | 0.605 | 0.61 |
| fuel_flow_atmosphere(O2-known rows) | weibull | 105 | 0.662 | 0.292 | 0.875 | 0.66 |
| fuel_flow_atmosphere(O2-known rows) | lognormal | 105 | 0.669 | 0.391 | 0.743 | 0.62 |

The intercept-only pooled C is below 0.5 because of fold-specific intercepts; a
constant predictor's C is 0.5 by definition. Selected: `fuel_flow_atmosphere_order`,
lognormal, model `sflame-lifetime-8c860fba8213`. Interval inflation ×1.36
takes held-out coverage from 70% to 81%.

Standardised time ratios (per 1 SD of each feature):

| Term | Time ratio | 95 % CI | p |
|---|---|---|---|
| intercept | 8.493 | [7.260, 9.936] | 2.9e-157 |
| x_H2 | 1.501 | [1.009, 2.234] | 0.045 |
| x_CH4 | 0.644 | [0.447, 0.928] | 0.018 |
| x_C2H4 | 0.894 | [0.587, 1.362] | 0.6 |
| log_total_slpm | 1.058 | [0.872, 1.284] | 0.57 |
| he_atmosphere | 0.519 | [0.421, 0.641] | 1.1e-09 |
| test_order_in_day | 0.758 | [0.647, 0.888] | 0.00061 |

**Conclusion:** the model ranks conditions (C ≈ 0.70) but does not predict
absolute lifetimes on new test days better than the baseline (median error
factor ~2). See A-ML-4.

## Run of 2026-10-30, increment 2 (s-Flame dataset and first real flame images)

```bash
python -m pytest -q
```

**Result: 92 passed, 0 failed.** New suites:
* `test_sflame.py` (9): documented unit conversions, gas-code tables, header
  and log parsing including a malformed real header, midnight rollover, flow
  programmes, OH* flame detection (gain-off level, ignition flash,
  extinguished vs censored), the experimental-table correction rule.
* `test_image_sequence.py` (10, synthetic 16-bit stacks): filename timestamps,
  dark subtraction, hot-pixel removal, saturation flag, scale excluding
  saturated frames, lit dark frames reported, end-to-end radius < 1 px,
  static-emitter warning, exclusion regions, ROI, volume suppression for a
  C-shaped emitter, burner-disk measurement (100 px truth → within 3 px).

### s-Flame dataset vs NASA's own records (all 289 test points)

| Our label (OH* PMT) | NASA "EXTINCTION DETECTED" | NASA burner-T limit | completed | no log |
|---|---|---|---|---|
| extinguished | 184 | 5 | 1 | 13 |
| burning at fuel off (censored) | 0 | 23 | 17 | 6 |
| ambiguous (excluded) | 20 | 0 | 0 | 0 |
| no sustained flame | 17 | 1 | 0 | 2 |

### First real flame image analysis: PSI-23 test 19304A7

The data is the CFI intensified camera, 248 frames of 1392×1040×16-bit TIFF
(45 % CH4/N2 fuel, ~21 % O2), analysed at 0.5 processing scale.

| Check | Result |
|---|---|
| Visible-extinction time, camera (this engine) | 19:40:47.80 ± 0.02 s |
| Flame-off time, OH* photomultiplier (independent instrument) | 19:40:47.98 |
| Agreement | **0.18 s** (different bands: CH* camera vs OH* PMT) |
| Burner-sphere calibration | 103 ± 2.5 px = 6.35 mm → 0.0617 mm/px |
| Frames detected / rejected by tracker / not detected | 57 / 9 / 19 |
| Circularity (mean, range) | 0.37 (0.13–0.88): **the flame is not spherical** |
| Equivalent volume suppressed | 56 of 57 frames |
| Wall time (85 frames analysed) | 6.3 s |

Visual inspection (`docs/img/PSI-23_19304A7_cv_overlay.jpg`):
* The first frames capture the igniter glow and the ignition kernel, not the
  flame (A-CV-13).
* On the near-spherical shell, a global threshold captures only its brighter
  part, so the radius is under-measured (A-CV-12).
* Later, the C-shaped opening flame is outlined well.

**Not validated:** a flame-shell radius. That needs a limb fit (next step).

## Run of 2026-10-30, update (real NASA data, decoder fix, PSI client)

```bash
python -m pytest -q
```

**Result: 73 passed, 0 failed, 0 skipped (33.6 s).** The 11 tests added since the first run:
* `test_interlaced_video_decodes_correctly`: regression for the blank-frame
  failure found on real ACME video. It uses a synthetic interlaced H.264 file
  with ground truth: radius error < 1 px and timestamps < 1 ms.
* `test_blank_decoder_output_is_reported_as_error`
* `test_both_decoders_agree_on_progressive_video` [opencv, ffmpeg]
* `test_decoder_validation`
* `test_data.py` (6 tests): PSI client parsing, deduplication, refusal of
  restricted or oversized files, rejection of a non-HTTPS signed URL, accession
  validation.

**Benchmark after making FFmpeg the default decoder** (same hardware, 3 repeats, median):

| Case | OpenCV decoder (before) | FFmpeg decoder (now) | Target < 3 s |
|---|---|---|---|
| 640×480 | 1.80 s | **1.92 s** | met |
| 1280×720 full res | 4.78 s | **5.20 s** | **not met** |
| 1280×720 `processing_scale=0.5` | 1.46 s | **1.78 s** | met |

Accuracy was unchanged: max radius error 0.15 / 0.17 / 0.22 px.

**First run on real NASA footage:** PSI-23 test point 19254H1, downlink MP4,
55–80 s, every 3rd frame. FFmpeg decoding worked and the timestamps came from
the container. The engine reported 240 "detected" frames, but the object was a
**static hardware glow at the image border, not a flame** (A-CV-11). This is a
recorded limitation, not a validated measurement.

## Run of 2026-10-30 (increment 1: physics and CV engine)

**Environment:** Linux 6.18 x86_64 cloud container, 4 vCPU Intel Xeon @ 2.10 GHz,
15 GiB RAM, Python 3.13.17, OpenCV 5.0.0, NumPy 2.5.3, pandas 3.0.5, FFmpeg
system binary.

```bash
python -m pytest -v
```

**Result: 62 passed, 0 failed, 0 skipped (27.2 s).**

| Suite | Tests | What is verified |
|---|---|---|
| `test_physics.py` | 20 | Area/volume/circularity/eccentricity formulas. Calibration-scale quadrature. Random vs systematic split for length¹,², ³. σ_V analytic vs numerical derivative and vs Monte Carlo (3 %). Local-polynomial derivatives exact for a quadratic on irregular timestamps. No gap bridging or filling. Derivative σ vs Monte Carlo (8 %). Non-uniform finite differences. Extinction states. Timestamp, bounds and plausibility validation. |
| `test_cv_engine.py` | 42 | Ingestion (valid, unsupported, missing, empty, corrupted, over-size, truncated). Accuracy vs ground truth. Kinematics. Extinction. Uncertainty consistency. Temporary tracking loss. Multiple contours. Tracker gating/reset. Black frames. Noise only. Border clipping. VFR timestamps. Frame sampling. Time window. Processing scale. Each of 5 segmentation methods. Config validation. Calibration handling incl. resolution-mismatch refusal. Uncalibrated mode. Undistortion. Progress events and cancellation. JSON (strict, no NaN) and CSV export. Schema/documentation sync. Preview and annotated video. |

## Accuracy on SYNTHETIC ground truth

The video is `SYNTHETIC_demo.mp4`: 640×480, 30 fps, 5 s, MPEG-4 Part 2. The flame
grows from 15 to 150 px with τ = 1.2 s, drifts (4, −2) px/s, has noise σ = 3 grey
levels and extinguishes at 4.2 s. This validates the measurement pipeline. It
does **not** validate segmentation of real flame imagery (A-DATA-3).

| Quantity | Result | Test threshold |
|---|---|---|
| Equivalent radius bias (Otsu) | +0.012 px mean | < 0.25 px |
| Equivalent radius max abs error | 0.149 px | < 1.0 px |
| Centroid max error | 0.099 px | < 0.5 px |
| dr/dt median relative error | < 2 % (median abs 0.08 px/s; truth 3.5–112 px/s) | < 2 % |
| d²r/dt² median abs error (interior) | 1.6 px/s² (truth −94 to −3 px/s²) | < 10 % of max |
| Extinction time | 4.183 ± 0.017 s (truth 4.200 s, inside interval) | truth within ± |
| VFR timestamps (9 dropped frames) | match ground truth < 1 ms; dr/dt median rel. error < 3 % | as stated |
| Background subtraction (MOG2) | +3.1–3.2 px constant offset, growth rate exact ± 0.5 px | documented, A-CV-3 |
| Observed radius residual scatter | ≪ assumed 1 px boundary σ | reported per video |

## Performance benchmark (`python -m backend.tools.benchmark_cv --repeats 3`)

Hardware is as listed above. The aspirational target is a 5 s video processed
in under 3 s.

| Case (5 s, 30 fps, 150 frames, SYNTHETIC) | Median wall time | Runs | Target met | Max radius error |
|---|---|---|---|---|
| 640×480, full resolution | **1.80 s** | 1.80 / 1.78 / 1.82 | yes | 0.15 px |
| 1280×720, full resolution | **4.78 s** | 4.83 / 4.78 / 4.74 | **no** | 0.17 px |
| 1280×720, `processing_scale=0.5` | **1.46 s** | 1.46 / 1.46 / 1.50 | yes | 0.22 px |

These times include decoding and full analysis but no annotated-video writing.
They have not been measured on the demonstration laptop. Re-run the benchmark
there before quoting any number.

## Not yet tested

* Browser end-to-end tests are not automated (the increment-6 browser run was manual).
* The two-stage Docker image (frontend build stage) has not been built.
