"""Benchmark the computer-vision engine on SYNTHETIC 5-second videos and check accuracy.

Usage:
    python -m backend.tools.benchmark_cv [--repeats 3] [--out benchmark.json]

Reports median wall time per configuration together with the hardware it ran
on, and the radius error against the synthetic ground truth. Numbers are only
valid for the machine that produced them.
"""

from __future__ import annotations

import argparse
import json
import statistics
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd

from backend.vision.calibration import Calibration
from backend.vision.cv_engine import AnalysisConfig, FlameAnalyzer, _system_info
from backend.vision.synthetic import SyntheticFlameSpec, write_synthetic_video

CASES = [
    ("640x480 full resolution", dict(width=640, height=480), dict()),
    ("1280x720 full resolution", dict(width=1280, height=720, center_px=(640.0, 360.0), r_max_px=250.0), dict()),
    ("1280x720 processing_scale=0.5", dict(width=1280, height=720, center_px=(640.0, 360.0), r_max_px=250.0),
     dict(processing_scale=0.5)),
]


def run(repeats: int) -> dict:
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        for name, spec_kw, cfg_kw in CASES:
            spec = SyntheticFlameSpec(duration_s=5.0, fps=30.0, **spec_kw)
            path = Path(tmp) / f"SYNTHETIC_bench_{spec.width}x{spec.height}.mp4"
            gt = pd.DataFrame(write_synthetic_video(path, spec)["frames"])
            cal = Calibration(known_length_mm=10.0, measured_length_px=100.0,
                              image_width=spec.width, image_height=spec.height)
            analyzer = FlameAnalyzer(AnalysisConfig(**cfg_kw), calibration=cal)
            times, res = [], None
            for _ in range(repeats):
                t0 = time.perf_counter()
                res = analyzer.analyze(path, "BENCH")
                times.append(time.perf_counter() - t0)
            d = res.to_dataframe().merge(gt, on="frame_index").query("flame_visible")
            err = (d.equivalent_radius_px - d.radius_px).to_numpy()
            results.append({
                "case": name,
                "video_duration_s": spec.duration_s,
                "frames": len(gt),
                "wall_time_s_median": statistics.median(times),
                "wall_time_s_all": times,
                "meets_aspirational_target_3s": statistics.median(times) < 3.0,
                "radius_error_px": {"mean": float(np.mean(err)), "max_abs": float(np.max(np.abs(err)))},
            })
    return {"data_class": "simulated", "system": _system_info(), "repeats": repeats, "results": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--out", type=Path, default=None)
    ns = parser.parse_args()
    report = run(ns.repeats)
    text = json.dumps(report, indent=2)
    if ns.out:
        ns.out.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
