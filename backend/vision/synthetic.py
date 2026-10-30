"""SYNTHETIC demonstration and validation videos of an idealised spherical flame.

!!! Everything produced by this module is SIMULATED. It is NOT NASA data and
!!! NOT an experimental observation. Files are prefixed ``SYNTHETIC_``, carry a
!!! visible on-frame watermark, and are accompanied by a ``.groundtruth.json``
!!! sidecar whose ``data_class`` is ``"simulated"``.

Purpose: the radius of every rendered frame is known exactly, so the computer-
vision pipeline can be validated quantitatively (bias, noise, derivative
accuracy, extinction timing) - something a real video cannot provide.

Model: a luminous disc whose radius follows a saturating growth law
``r(t) = r_max - (r_max - r0) * exp(-(t - t_ign) / tau)`` (a qualitative stand-in for a
burner-supported spherical diffusion flame approaching a quasi-steady size),
with a smooth ``tanh`` edge of width ``edge_width_px``, slow centroid drift,
additive Gaussian sensor noise and abrupt disappearance at ``extinction_time_s``.
The ground-truth radius is the iso-contour midway between background and peak
intensity. These parameters are illustrative and are not fitted to any
experiment.
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np

WATERMARK = "SYNTHETIC DEMO - NOT NASA DATA"


@dataclass
class SyntheticFlameSpec:
    width: int = 640
    height: int = 480
    fps: float = 30.0
    duration_s: float = 5.0
    center_px: tuple[float, float] = (320.0, 240.0)
    drift_px_s: tuple[float, float] = (4.0, -2.0)
    r0_px: float = 15.0
    r_max_px: float = 150.0
    growth_tau_s: float = 1.2
    ignition_time_s: float = 0.0               # flame absent before this time
    extinction_time_s: float | None = 4.2
    edge_width_px: float = 1.5
    background: float = 8.0
    peak_intensity: float = 220.0
    color_bgr: tuple[float, float, float] = (1.0, 0.55, 0.25)  # blue-dominant, soot-free-like
    noise_sigma: float = 3.0
    dropout_frames: tuple[int, ...] = ()      # frames rendered without flame (simulated detection loss)
    distractor_frames: tuple[int, ...] = ()   # frames with an extra bright blob (multiple contours)
    watermark: bool = True
    seed: int = 0
    mm_per_px: float = 0.1  # nominal scale for the demo (10 px = 1 mm); simulated, not measured

    def radius_px(self, t: float) -> float:
        age = t - self.ignition_time_s
        return self.r_max_px - (self.r_max_px - self.r0_px) * math.exp(-age / self.growth_tau_s)

    def radius_rate_px_s(self, t: float) -> float:
        age = t - self.ignition_time_s
        return (self.r_max_px - self.r0_px) / self.growth_tau_s * math.exp(-age / self.growth_tau_s)

    def radius_accel_px_s2(self, t: float) -> float:
        return -self.radius_rate_px_s(t) / self.growth_tau_s

    def center_at(self, t: float) -> tuple[float, float]:
        return (self.center_px[0] + self.drift_px_s[0] * t, self.center_px[1] + self.drift_px_s[1] * t)

    def flame_visible(self, t: float, frame_index: int) -> bool:
        if frame_index in self.dropout_frames or t < self.ignition_time_s:
            return False
        return self.extinction_time_s is None or t < self.extinction_time_s


def render_frame(spec: SyntheticFlameSpec, t: float, frame_index: int, rng: np.random.Generator) -> np.ndarray:
    yy, xx = np.mgrid[0 : spec.height, 0 : spec.width].astype(np.float32)
    profile = np.zeros((spec.height, spec.width), np.float32)
    if spec.flame_visible(t, frame_index):
        cx, cy = spec.center_at(t)
        rho = np.hypot(xx - cx, yy - cy)
        profile = 0.5 * (1.0 - np.tanh((rho - spec.radius_px(t)) / spec.edge_width_px))
    if frame_index in spec.distractor_frames:
        rho2 = np.hypot(xx - 60.0, yy - 60.0)
        profile = np.maximum(profile, 0.5 * (1.0 - np.tanh((rho2 - 12.0) / 1.5)))
    amp = spec.peak_intensity - spec.background
    frame = np.empty((spec.height, spec.width, 3), np.float32)
    for c in range(3):
        frame[:, :, c] = spec.background + amp * spec.color_bgr[c] * profile
    frame += rng.normal(0.0, spec.noise_sigma, frame.shape).astype(np.float32)
    out = np.clip(frame, 0, 255).astype(np.uint8)
    if spec.watermark:
        cv2.putText(out, WATERMARK, (10, spec.height - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (40, 40, 40), 1, cv2.LINE_AA)
    return out


def ground_truth(spec: SyntheticFlameSpec, timestamps: np.ndarray) -> dict:
    frames = []
    for i, t in enumerate(timestamps):
        visible = spec.flame_visible(float(t), i)
        cx, cy = spec.center_at(float(t))
        frames.append({
            "frame_index": i,
            "timestamp_s": float(t),
            "flame_visible": visible,
            "radius_px": spec.radius_px(float(t)) if visible else None,
            "radius_rate_px_s": spec.radius_rate_px_s(float(t)) if visible else None,
            "radius_accel_px_s2": spec.radius_accel_px_s2(float(t)) if visible else None,
            "center_x_px": cx if visible else None,
            "center_y_px": cy if visible else None,
        })
    return {
        "data_class": "simulated",
        "disclaimer": "SIMULATED data generated by backend/vision/synthetic.py. Not NASA data; not an experiment.",
        "generator": "backend.vision.synthetic",
        "spec": asdict(spec),
        "frames": frames,
    }


def write_synthetic_video(path: str | Path, spec: SyntheticFlameSpec | None = None) -> dict:
    """Write a constant-frame-rate synthetic MP4/AVI plus ``<name>.groundtruth.json``."""
    spec = spec or SyntheticFlameSpec()
    path = Path(path)
    if not path.name.startswith("SYNTHETIC_"):
        raise ValueError("Synthetic video filenames must start with 'SYNTHETIC_' to prevent confusion with real data.")
    path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*("MJPG" if path.suffix.lower() == ".avi" else "mp4v"))
    writer = cv2.VideoWriter(str(path), fourcc, spec.fps, (spec.width, spec.height))
    if not writer.isOpened():
        raise RuntimeError(f"OpenCV could not open a video writer for {path.suffix}.")
    n = int(round(spec.duration_s * spec.fps))
    timestamps = np.arange(n) / spec.fps
    rng = np.random.default_rng(spec.seed)
    try:
        for i, t in enumerate(timestamps):
            writer.write(render_frame(spec, float(t), i, rng))
    finally:
        writer.release()
    gt = ground_truth(spec, timestamps)
    path.with_suffix(".groundtruth.json").write_text(json.dumps(gt, indent=1))
    return gt


def write_vfr_synthetic_video(path: str | Path, spec: SyntheticFlameSpec, drop_frames: list[int]) -> dict:
    """Write a variable-frame-rate synthetic MP4 by dropping frames from a CFR timeline.

    Frames are rendered on the ``spec.fps`` timeline; those listed in
    ``drop_frames`` are removed while every remaining frame keeps its exact
    presentation timestamp, producing irregular intervals (the way dropped
    frames create variable frame rate in real recordings). Requires ``ffmpeg``.
    Ground-truth ``frame_index`` values refer to the frames in the output file.
    """
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg executable not found; variable-frame-rate generation unavailable.")
    path = Path(path)
    if not path.name.startswith("SYNTHETIC_"):
        raise ValueError("Synthetic video filenames must start with 'SYNTHETIC_'.")
    n = int(round(spec.duration_s * spec.fps))
    drop = sorted({int(i) for i in drop_frames if 0 < int(i) < n})
    keep = [i for i in range(n) if i not in set(drop)]
    select = "not(" + "+".join(f"eq(n\\,{i})" for i in drop) + ")" if drop else "1"
    cmd = [
        ffmpeg, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24",
        "-s", f"{spec.width}x{spec.height}", "-framerate", str(spec.fps), "-i", "-",
        "-vf", f"select='{select}'", "-fps_mode", "passthrough", "-c:v", "libx264", "-crf", "12",
        "-pix_fmt", "yuv420p", "-metadata", f"comment={WATERMARK}", str(path),
    ]
    rng = np.random.default_rng(spec.seed)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for i in range(n):
            proc.stdin.write(render_frame(spec, i / spec.fps, i, rng).tobytes())
        proc.stdin.close()
        stderr = proc.stderr.read().decode(errors="replace")
        if proc.wait(timeout=120) != 0:
            raise RuntimeError(f"ffmpeg failed: {stderr.strip()}")
    finally:
        if proc.poll() is None:
            proc.kill()
    # Ground truth is computed on the original timeline, then restricted to kept frames.
    full = ground_truth(spec, np.arange(n) / spec.fps)
    frames = [dict(full["frames"][src], frame_index=out_i, source_frame_index=src) for out_i, src in enumerate(keep)]
    gt = dict(full, frames=frames, variable_frame_rate=True, dropped_source_frames=drop)
    path.with_suffix(".groundtruth.json").write_text(json.dumps(gt, indent=1))
    return gt


if __name__ == "__main__":  # pragma: no cover - convenience entry point
    import argparse

    parser = argparse.ArgumentParser(description="Generate a SYNTHETIC spherical-flame video with ground truth.")
    parser.add_argument("--out", default="samples/SYNTHETIC_spherical_flame_demo.mp4")
    parser.add_argument("--duration", type=float, default=5.0)
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--seed", type=int, default=0)
    ns = parser.parse_args()
    info = write_synthetic_video(ns.out, SyntheticFlameSpec(duration_s=ns.duration, fps=ns.fps, seed=ns.seed))
    print(f"Wrote {ns.out} ({len(info['frames'])} frames) and its .groundtruth.json  [SIMULATED DATA]")
