# NASA ACME Data Availability Matrix

**Status as of 2026-10-30: catalogue VERIFIED from NASA PSI. Contents partially inspected.**
Network access to `psi.nasa.gov` was enabled on 2026-10-30. All facts below come
from PSI's own metadata service, or from files downloaded and opened in this
environment. They are marked **A** (verified), **P** (partly verified) or
**U** (still unverified).

## 1. ACME in NASA PSI (verified)

All six ACME investigations are in PSI. They are free to download without login
(pre-signed S3 links), and **no file is marked restricted**.

| Accession | Investigation | Licence | DOI | Files | Notes |
|---|---|---|---|---|---|
| PSI-23 | **s-Flame**: Structure and Response of Spherical Diffusion Flames | CC0-1.0 | 10.60555/k57n-p030 | 10,979 | 291 test points; video, telemetry, science-camera images |
| PSI-10 | Flame Design | (none listed) | 10.60555/w4zy-bt45 | 3,814 | ~2.2 TB of raw-data archives; naming not yet mapped |
| PSI-159 | Cool Flames Investigation with Gases (CFI-G) | CC0-1.0 | 10.60555/cyt1-kh64 | 3,760 | ~2.1 TB; naming not yet mapped |
| PSI-20 | Burning Rate Emulator (BRE) | CC0-1.0 | 10.60555/vb93-3y72 | 3 | experimental table + metadata only |
| PSI-21 | Coflow Laminar Diffusion Flame (CLD Flame) | CC0-1.0 | 10.60555/23e1-9950 | 3 | experimental table + metadata only |
| PSI-22 | E-FIELD Flames | CC0-1.0 | 10.60555/se5a-8c73 | 6 | table, metadata, 4 images |

The client in `backend/data/psi_client.py` reproduces these queries and writes a
provenance file (DOI, licence, URL, SHA-256, retrieval time) for each download.

## 2. s-Flame (PSI-23) file inventory, per test point

Test points are named `YYDDD<letter><n>` (e.g. `19254H1` = 2019, day 254, point H1).
This is the natural grouping key for experiment-aware train/test splits.

| Content | Files | Total | Inspected? | What it is |
|---|---|---|---|---|
| `<tp>_TP.txt` test-point log | 267 | < 1 MB | **A** (19254H1) | Script event times: ignition, flame stabilisation, MFCs off, **"Extinction detected"**, failure reason; camera frame counts; full test-point configuration |
| `<tp>_data.csv` telemetry | 289 | 0.77 GB | **A** (19254H1) | ~5,800 rows × 39 channels: 3 mass-flow controllers, ion current, 3 pressure transducers, 3 PMTs, 8 thermocouples, 6 radiometer channels, E-field. **Values are raw sensor voltages**; conversion factors are in the engineering documents (**U**) |
| `<tp>_mfcSetpoints.csv` | 289 | < 1 MB | **A** | Timed flow-controller setpoints (V) plus a header with gas IDs and full-scale ranges |
| Downlink colour video `.mp4` | 290 | 9.6 GB | **A** (1 file) | 1280×720, 29.97 fps, interlaced H.264, ~1–2 min of recording each. In the file inspected, **no flame was visible**. Only the glowing igniter and hardware glow appear after the lights go off. Not suitable for flame-size measurement on its own (§4) |
| `<tp>B_LLL-UV.zip` | 286 | 34.6 GB | **A** (1 file) | 273 × 512×512 16-bit TIFF + a frame log with **microsecond per-frame timestamps** (≈30 fps). Some frames saturate (65,520) |
| `<tp>_INTNS.zip` intensified camera | 264 | 124 GB | U | Expected: low-light visible imagery of the flame (the most likely flame-size source) |
| `<tp>_ACME.zip` science camera | 323 | 69.6 GB | U | |
| `<tp>A_HiBMS.zip` hi-res B/W | 283 | 129.7 GB | U | |
| Experimental table (CSV) | 1 | 2 KB | **A** | 31 test days: test type, date, atmosphere, fuel bottle, flames ignited |

Per-investigation totals (s-Flame): about 1.5 TB of zip archives. **Selective download only.**

## 3. Target-availability matrix

Legend: **A** = available and inspected, **P** = present but not yet parsed or converted,
**U** = unverified, **N** = confirmed not available.

| Variable | Role | Unit | Source | Status | Coverage | Notes |
|---|---|---|---|---|---|---|
| Test-point ID | key | – | file names, `_TP.txt` | **A** | 291 test points | Use for grouped CV |
| Fuel composition | condition | mole fraction | MFC gas codes [IDD Table 34] + indicated flows | **A** (nominal) | 289 | Gas conversion factors not applied (A-SF-4) |
| O₂ fraction | condition | mole fraction | experimental table (day level) | **A** for 197 tests, **unknown** for 92 | day level | "N3–N6" defect corrected by rule SFLAME-T1. Mixed-O₂ days have no per-test value (A-SF-5) |
| Chamber pressure | condition | V → kPa | `PTA1–3` in `_data.csv` | **P** | per test point | Calibration factor U. The table notes "~1 atm, pressure rises and O₂ drops with vitiation" |
| Fuel / diluent flow | condition | SLPM (N2-equiv.) | setpoints, conversion [NIDD] | **A** (indicated) | 289 | |
| Flame on/off times | outcome anchor | UTC (8 ms) | OH* photomultiplier PMT1 in `_data.csv` | **A** | 289 tests | `data/processed/sflame_test_points.csv` (A-SF-1) |
| **Flame lifetime (with censoring)** | **outcome** | s | PMT1 emission onset → end | **A** | 203 extinctions + 46 censored | Best ML target. 20 ambiguous and 20 no-flame tests excluded (A-SF-2) |
| Commanded flow at extinction | outcome | SLPM (N2-equiv.) | setpoints at flame-off | **A** | 203 | Radiative (ramp-up) vs kinetic (ramp-down) limits per the final report |
| NASA stop reason | metadata / check | category | `_TP.txt` | **A** | 267 logs | "EXTINCTION DETECTED" is the normal stop path, not a failure. Used only as a cross-check |
| Flame radius vs time | outcome | mm | science-camera TIFFs → this CV engine | P | ≤ 286 | Needs a successful test point, an image-sequence loader and pixel scale (camera docs) |
| Flame temperature | outcome | V → K | thermocouples `TCA–TCD`, `TC200A/B` | **P** (raw V) | per test point | Thermocouple type, position and cold-junction handling must come from the docs. **Do not train or report temperatures until the conversion is verified** |
| Radiative emission | outcome | V → W | radiometer channels | **P** (raw V) | per test point | Calibration U |
| Soot | outcome | – | Flame Design (PSI-10) | U | – | |

## 4. Findings from the first real files

1. **OpenCV decodes the ACME downlink MP4s as all-black frames** (interlaced H.264)
   and still reports success. Worse, whether this happens depended on unrelated
   process state. FFmpeg is now the default decoder, and an all-blank guard is
   in place (`SCIENTIFIC_ASSUMPTIONS.md` A-CV-10).
2. In the downlink video of 19254H1 the CV engine "detected" an object in 240
   frames. It was a **static hardware glow at the image border**, not a flame
   (A-CV-11). Downlink video must not be used for flame size without a region of
   interest and visual confirmation.
3. 19254H1 is an **ignition failure**, which corrects an earlier reading of
   "early extinction". The OH* photomultiplier shows only a 0.6 s flash at
   18:38:29.3, *before* fuel reached the burner (fuel flow rises at 18:38:30.9).
   NASA's log says "EXTINCTION DETECTED" because that is the script's generic stop
   path. 19254H3 used identical setpoints and burned for 42.8 s. Labels must
   therefore come from the sensor signals, not the stop reason (A-SF-2, A-SF-7).

## 5. Rules that follow

1. No variable is used for modelling until its row is **A** with a provenance
   record, and its unit conversion is documented in `DATA_DICTIONARY.md`.
2. Raw voltages are never presented as physical quantities.
3. Corrections to NASA records (e.g. the "N3…N6" atmosphere entries) are applied
   by documented, versioned rules that keep the original value alongside.
4. Splits are grouped by test point (and checked by test day) to prevent leakage.
