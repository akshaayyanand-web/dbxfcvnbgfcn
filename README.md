# FLAME IN FREEFALL

Microgravity combustion intelligence platform. It turns combustion video and
experiment records into traceable measurements, predictions and reports.

> **Status: increment 1 of 7.** The physics engine and computer-vision engine are
> implemented and tested. The data, ML, API, frontend and deployment layers are
> planned (see `PROJECT_STATUS.md`). **No NASA data has been ingested yet**
> (see `docs/DATA_AVAILABILITY_MATRIX.md`). All sample videos are SYNTHETIC and
> labelled as such.

## Quick start

Requires Python 3.11+. FFmpeg is optional.

```bash
python -m pip install -r backend/requirements.txt
```

```bash
python -m pytest
```

Generate a SYNTHETIC demonstration video with ground truth:

```bash
python -m backend.vision.synthetic --out samples/SYNTHETIC_spherical_flame_demo.mp4
```

Analyse it (10 mm reference spanning 100 px), writing JSON, CSV and an annotated video:

```bash
python -m backend.tools.analyze_video samples/SYNTHETIC_spherical_flame_demo.mp4 --experiment-id DEMO-001 --known-mm 10 --measured-px 100 --annotate --out results/
```

Benchmark on your hardware:

```bash
python -m backend.tools.benchmark_cv --repeats 3
```

## Python API

```python
from backend.vision.calibration import Calibration
from backend.vision.cv_engine import AnalysisConfig, FlameAnalyzer
from backend.vision.segmentation import SegmentationConfig

cal = Calibration(known_length_mm=10.0, measured_length_px=100.0, measured_length_sigma_px=1.0,
                  image_width=640, image_height=480, camera_id="CIR-cam-1")
cfg = AnalysisConfig(segmentation=SegmentationConfig(method="otsu", threshold_offset=0))
result = FlameAnalyzer(cfg, calibration=cal).analyze(
    "run.mp4", experiment_id="EXP-001",
    progress_callback=lambda p: print(p.measurement.frame_index, p.measurement.radius_mm))
df = result.to_dataframe()          # one row per frame, units in DATA_DICTIONARY.md
result.export_json("EXP-001.json")  # full reproducible record (config, calibration, issues, contours)
print(result.summary["extinction"])
```

## What it measures

Per frame:
* centroid, bounding box and minimum enclosing circle
* area-equivalent radius and diameter, projected area and perimeter
* circularity, ellipse axes and eccentricity, boundary roughness
* radius, area and perimeter in mm with random and calibration uncertainty
* equivalent *spherical* volume ± σ

Over time:
* smoothed radius, expansion velocity dr/dt and acceleration d²r/dt² ± σ,
  computed with timestamp-aware local-polynomial fits, so variable frame rate
  is handled correctly
* centroid displacement, shape stability
* visible-extinction time ± temporal resolution

Missing detections stay missing. Nothing is interpolated.

## Documents

| File | Content |
|---|---|
| `ARCHITECTURE.md` | Subsystems, module map, contracts, pipeline |
| `SCIENTIFIC_ASSUMPTIONS.md` | Every modelling assumption, with an ID, plus its limitations |
| `DATA_DICTIONARY.md` | Every output field with unit and quantity class |
| `docs/DATA_AVAILABILITY_MATRIX.md` | What NASA ACME data is known or unknown |
| `TEST_REPORT.md` | Executed test results, accuracy and benchmarks |
| `PROJECT_STATUS.md` | Done, remaining, risks, known issues |
