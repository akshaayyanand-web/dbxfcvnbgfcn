"""Command-line flame analysis.

Example:
    python -m backend.tools.analyze_video run.mp4 --experiment-id EXP-001 \\
        --known-mm 10 --measured-px 100 --out results/

Writes ``<id>.json`` (full record incl. contours), ``<id>.csv`` (per-frame
table) and optionally ``<id>_annotated.mp4``.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from backend.vision.calibration import Calibration
from backend.vision.cv_engine import AnalysisConfig, FlameAnalysisError, FlameAnalyzer, probe_video
from backend.vision.segmentation import Channel, SegmentationConfig, SegmentationMethod


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Analyse a combustion video with the FLAME IN FREEFALL CV engine.")
    p.add_argument("video", type=Path)
    p.add_argument("--experiment-id", required=True)
    p.add_argument("--out", type=Path, default=Path("results"))
    p.add_argument("--known-mm", type=float, help="Known reference length in mm (enables calibration).")
    p.add_argument("--measured-px", type=float, help="Measured reference length in pixels.")
    p.add_argument("--measured-px-sigma", type=float, default=1.0)
    p.add_argument("--known-mm-sigma", type=float, default=0.0)
    p.add_argument("--method", choices=[m.value for m in SegmentationMethod], default="otsu")
    p.add_argument("--channel", choices=[c.value for c in Channel], default="max")
    p.add_argument("--threshold-offset", type=float, default=0.0)
    p.add_argument("--fixed-threshold", type=float, default=127.0)
    p.add_argument("--blur", type=int, default=5)
    p.add_argument("--min-area", type=float, default=30.0)
    p.add_argument("--frame-step", type=int, default=1)
    p.add_argument("--scale", type=float, default=1.0, help="Processing scale in (0, 1].")
    p.add_argument("--annotate", action="store_true", help="Also write an annotated MP4.")
    p.add_argument("--config", type=Path, help="JSON AnalysisConfig (overrides the flags above).")
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ns = build_parser().parse_args(argv)
    if ns.config:
        config = AnalysisConfig.from_dict(json.loads(ns.config.read_text()))
    else:
        config = AnalysisConfig(
            segmentation=SegmentationConfig(
                method=ns.method, channel=ns.channel, threshold_offset=ns.threshold_offset,
                fixed_threshold=ns.fixed_threshold, blur_kernel=ns.blur, min_contour_area_px=ns.min_area),
            frame_step=ns.frame_step, processing_scale=ns.scale)
    calibration = None
    if (ns.known_mm is None) != (ns.measured_px is None):
        print("error: --known-mm and --measured-px must be given together", file=sys.stderr)
        return 2
    try:
        if ns.known_mm is not None:
            meta = probe_video(ns.video)
            calibration = Calibration(
                known_length_mm=ns.known_mm, measured_length_px=ns.measured_px,
                measured_length_sigma_px=ns.measured_px_sigma, known_length_sigma_mm=ns.known_mm_sigma,
                image_width=meta.width, image_height=meta.height)
        ns.out.mkdir(parents=True, exist_ok=True)
        annotated = ns.out / f"{ns.experiment_id}_annotated.mp4" if ns.annotate else None

        def progress(p):
            if p.frames_analyzed % 25 == 0:
                logging.info("frame %d (%.0f%%) status=%s", p.measurement.frame_index, 100 * p.fraction,
                             p.measurement.status)

        result = FlameAnalyzer(config, calibration).analyze(
            ns.video, ns.experiment_id, progress_callback=progress, annotated_output_path=annotated)
    except (FlameAnalysisError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    result.export_json(ns.out / f"{ns.experiment_id}.json")
    result.export_csv(ns.out / f"{ns.experiment_id}.csv")
    s = result.summary
    print(json.dumps({k: s[k] for k in ("frames_decoded", "status_counts", "detection_rate", "timestamp_source",
                                         "peak_radius", "extinction")}, indent=2))
    for issue in result.issues:
        print(f"[{issue.severity}] {issue.code}: {issue.message}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
