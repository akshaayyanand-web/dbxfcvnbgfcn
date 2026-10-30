# Test Report

Every result here was produced by actually running the commands shown. Nothing
is extrapolated.

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

* Flame-size measurement on real ACME science-camera images (needs an image-sequence loader and a successful test point).
* API, database, WebSocket, ML, reports and frontend: not yet implemented.
