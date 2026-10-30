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
| Fuel composition | condition | mole % | experimental table (per day), mfc header gas IDs | **P** | 31 test days | Gas-ID code meaning needs the engineering docs |
| O₂ fraction | condition | mole % | experimental table | **P** | "~21 %" / "~30 %" | **Data-quality defect:** the atmosphere column reads "with N2, N3, N4, N5, N6", most likely spreadsheet autofill of "N2". Must be corrected with a documented rule, not silently |
| Chamber pressure | condition | V → kPa | `PTA1–3` in `_data.csv` | **P** | per test point | Calibration factor U. The table notes "~1 atm, pressure rises and O₂ drops with vitiation" |
| Fuel / oxidiser flow | condition | V → sccm | `MFCA1–3` in `_data.csv`, setpoints | **P** | per test point | Full-scale ranges are in the setpoint header |
| Ignition time | outcome anchor | UTC | `_TP.txt` "Ignition and retraction" | **A** (1) / P | 267 logs | |
| **Extinction time / flame lifetime** | **outcome** | s | `_TP.txt` "Extinction detected" − ignition | **A** (1) / P | ≤ 267 | 19254H1: ignition 18:38:28, extinction 18:38:32, **"Test Point Failure: EXTINCTION DETECTED"**. Detection method and resolution need the docs. **Best candidate ML target** |
| Test outcome (nominal vs failure + reason) | outcome | category | `_TP.txt` | **A** (1) / P | ≤ 267 | Possible classification target |
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
3. 19254H1 is a **failed test point**: early extinction about 4 s after ignition.
   Test outcomes therefore vary and must be modelled, not assumed.

## 5. Rules that follow

1. No variable is used for modelling until its row is **A** with a provenance
   record, and its unit conversion is documented in `DATA_DICTIONARY.md`.
2. Raw voltages are never presented as physical quantities.
3. Corrections to NASA records (e.g. the "N3…N6" atmosphere entries) are applied
   by documented, versioned rules that keep the original value alongside.
4. Splits are grouped by test point (and checked by test day) to prevent leakage.
