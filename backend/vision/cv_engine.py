"""FLAME IN FREEFALL - computer-vision engine.

``FlameAnalyzer`` turns a combustion video into a per-frame measurement table:

    video -> validation/metadata -> [undistort] -> [resize] -> segmentation
          -> contour candidates -> temporal tracking -> pixel geometry
          -> calibration (mm) + uncertainty -> timestamp-aware kinematics
          -> extinction estimate -> validation checks -> JSON / CSV / DataFrame

Design rules (see SCIENTIFIC_ASSUMPTIONS.md):

* Frames are decoded one at a time; no frame is kept after it is processed.
* Per-frame timestamps come from the container's presentation timestamps
  (OpenCV ``CAP_PROP_POS_MSEC``); a nominal ``index / fps`` timeline is used
  only if those are unusable, and the source is always reported.
* A frame without an accepted detection has ``None``/``NaN`` measurements.
  Nothing is interpolated.
* Every output column has a unit and a quantity class (``image_derived`` or
  ``calculated``); millimetre quantities exist only when a calibration is given.
* The equivalent spherical volume is a model estimate from a 2-D projection,
  not a 3-D measurement.
"""

from __future__ import annotations

import json
import logging
import math
import os
import platform
import shutil
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Callable, Iterable

import cv2
import numpy as np
import pandas as pd

from backend.physics import validation as pv
from backend.physics.physics_engine import (
    DerivativeConfig,
    ExtinctionEstimate,
    equivalent_spherical_volume,
    estimate_extinction,
    local_polynomial_kinematics,
)
from backend.physics.uncertainty import (
    circle_area_sigma,
    px_to_physical,
    radius_sigma_from_boundary,
    sphere_volume_sigma,
)
from backend.vision.calibration import Calibration, DistortionCorrection
from backend.vision.geometry import ContourGeometry, measure_contour, simplify_contour
from backend.vision.segmentation import SegmentationConfig, SegmentationMethod, Segmenter, find_contours
from backend.vision.tracking import DetectionStatus, FlameTracker, TrackingConfig

__all__ = [
    "AnalysisCancelled",
    "AnalysisConfig",
    "AnalysisProgress",
    "AnalysisResult",
    "FIELD_DEFINITIONS",
    "FlameAnalysisError",
    "FlameAnalyzer",
    "FrameMeasurement",
    "VideoDecodeError",
    "VideoMetadata",
    "VideoValidationError",
    "probe_video",
    "render_overlay",
]

ENGINE_VERSION = "0.1.0"
SUPPORTED_EXTENSIONS = {".mp4", ".avi", ".mov"}
DEFAULT_MAX_FILE_BYTES = 2 * 1024**3

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------------- errors


class FlameAnalysisError(Exception):
    """Base class for computer-vision engine errors."""


class VideoValidationError(FlameAnalysisError):
    """The file is missing, unsupported, empty or not decodable."""


class VideoDecodeError(FlameAnalysisError):
    """Decoding failed in a way that prevents analysis."""


class AnalysisCancelled(FlameAnalysisError):
    """The caller requested cancellation."""


# --------------------------------------------------------------------------- metadata


@dataclass
class VideoMetadata:
    filename: str
    container: str
    codec_fourcc: str
    codec_name: str | None
    width: int
    height: int
    nominal_fps: float
    reported_frame_count: int
    duration_s: float | None
    file_size_bytes: int
    opencv_first_frame_blank: bool = False  # OpenCV decoded frame 0 as all zeros (e.g. interlaced H.264)

    def to_dict(self) -> dict:
        return asdict(self)


def _fourcc_to_str(value: float) -> str:
    code = int(value)
    chars = "".join(chr((code >> (8 * i)) & 0xFF) for i in range(4))
    return chars if chars.isprintable() and chars.strip() else f"0x{code:08x}"


def _ffprobe_stream(path: Path) -> dict | None:
    exe = shutil.which("ffprobe")
    if exe is None:
        return None
    try:
        out = subprocess.run(
            [exe, "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=codec_name,avg_frame_rate,nb_frames,duration", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=30, check=True,
        )
        streams = json.loads(out.stdout).get("streams", [])
        return streams[0] if streams else None
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError) as exc:
        logger.warning("ffprobe failed for %s: %s", path.name, exc)
        return None


def probe_video(path: str | Path, max_file_bytes: int = DEFAULT_MAX_FILE_BYTES) -> VideoMetadata:
    """Validate a video file and extract its metadata without decoding all frames."""
    path = Path(path)
    if not path.is_file():
        raise VideoValidationError(f"Video file not found: {path.name}")
    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise VideoValidationError(
            f"Unsupported video format '{ext}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}.")
    size = path.stat().st_size
    if size == 0:
        raise VideoValidationError("Video file is empty.")
    if size > max_file_bytes:
        raise VideoValidationError(f"Video file is {size} bytes; the limit is {max_file_bytes} bytes.")

    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            raise VideoValidationError("Video could not be opened (corrupted file or unsupported codec).")
        ok, frame = cap.read()
        if not ok or frame is None or frame.size == 0:
            raise VideoValidationError("No decodable frame found (corrupted file or unsupported codec).")
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or frame.shape[1]
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or frame.shape[0]
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fourcc = _fourcc_to_str(cap.get(cv2.CAP_PROP_FOURCC))
        first_blank = not frame.any()
    finally:
        cap.release()

    info = _ffprobe_stream(path) or {}
    codec_name = info.get("codec_name")
    duration = None
    try:
        duration = float(info["duration"]) if "duration" in info else None
    except (TypeError, ValueError):
        duration = None
    if (not math.isfinite(fps) or fps <= 0) and info.get("avg_frame_rate", "0/0") != "0/0":
        num, den = info["avg_frame_rate"].split("/")
        fps = float(num) / float(den) if float(den) else 0.0
    if duration is None and fps > 0 and count > 0:
        duration = count / fps
    return VideoMetadata(
        filename=path.name, container=ext.lstrip("."), codec_fourcc=fourcc, codec_name=codec_name,
        width=width, height=height, nominal_fps=fps if math.isfinite(fps) else 0.0,
        reported_frame_count=count, duration_s=duration, file_size_bytes=size,
        opencv_first_frame_blank=first_blank,
    )


# ----------------------------------------------------------------------------- decoding

DECODERS = ("auto", "opencv", "ffmpeg")


class FFmpegCapture:
    """Minimal ``cv2.VideoCapture``-compatible reader that decodes through the ``ffmpeg`` executable.

    Needed because OpenCV's FFmpeg backend can return *successfully decoded but
    all-black* frames for interlaced H.264 (observed on NASA ACME s-Flame
    downlink recordings). Frames flagged as interlaced are deinterlaced with
    ``yadif`` (one output frame per input frame, so frame indices are preserved).
    Presentation timestamps come from the stream's packet PTS (via ``ffprobe``),
    sorted into presentation order; if they cannot be read, ``index / fps`` is used.
    Supports only the subset of the VideoCapture API used by ``FlameAnalyzer``.
    """

    def __init__(self, path: str | Path, width: int, height: int, fps: float) -> None:
        ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
        if ffmpeg is None:
            raise VideoDecodeError("The ffmpeg executable is required for decoder='ffmpeg'.")
        self._w, self._h, self._fps = width, height, fps
        self._frame_bytes = width * height * 3
        self._buf: bytes | None = None
        self._index = -1
        self._pts: list[float] = []
        if ffprobe is not None:
            try:
                out = subprocess.run(
                    [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=pts_time",
                     "-of", "csv=p=0", str(path)], capture_output=True, text=True, timeout=120, check=True)
                pts = sorted(float(x) for x in out.stdout.split() if x.strip() not in ("", "N/A"))
                self._pts = pts
            except (subprocess.SubprocessError, ValueError, OSError) as exc:
                logger.warning("ffprobe packet timestamps unavailable: %s", exc)
        self._proc = subprocess.Popen(
            [ffmpeg, "-v", "error", "-i", str(path), "-map", "0:v:0", "-vf", "yadif=0:-1:1",
             "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def isOpened(self) -> bool:  # noqa: N802 - mirrors the OpenCV API
        return self._proc.poll() is None or self._buf is not None

    def grab(self) -> bool:
        data = self._proc.stdout.read(self._frame_bytes) if self._proc.stdout else b""
        if len(data) < self._frame_bytes:
            self._buf = None
            return False
        self._buf = data
        self._index += 1
        return True

    def retrieve(self) -> tuple[bool, np.ndarray | None]:
        if self._buf is None:
            return False, None
        return True, np.frombuffer(self._buf, np.uint8).reshape(self._h, self._w, 3).copy()

    def read(self) -> tuple[bool, np.ndarray | None]:
        return self.retrieve() if self.grab() else (False, None)

    def get(self, prop: int) -> float:
        if prop == cv2.CAP_PROP_POS_MSEC:
            if 0 <= self._index < len(self._pts):
                return (self._pts[self._index] - self._pts[0]) * 1000.0
            return self._index / self._fps * 1000.0 if self._fps > 0 else math.nan
        return 0.0

    def release(self) -> None:
        if self._proc.stdout:
            self._proc.stdout.close()
        if self._proc.poll() is None:
            self._proc.kill()
        self._proc.wait()


def open_capture(path: str | Path, meta: VideoMetadata, decoder: str = "auto") -> tuple[Any, str, list[str]]:
    """Open a frame reader. Returns ``(capture, decoder_used, notes)``.

    ``auto`` uses FFmpeg whenever the executable is installed. OpenCV's decoding
    of interlaced H.264 was found to be unreliable in a way that depends on
    unrelated process state (identical files decoded correctly or as all-black
    frames depending on what had been imported or opened before), so it cannot
    be validated per file and is used only as a fallback.
    """
    if decoder not in DECODERS:
        raise ValueError(f"decoder must be one of {DECODERS}.")
    notes: list[str] = []
    use_ffmpeg = decoder == "ffmpeg" or (decoder == "auto" and shutil.which("ffmpeg") is not None)
    if decoder == "auto" and not use_ffmpeg:
        notes.append("ffmpeg is not installed; decoding with OpenCV, which can return blank frames for "
                     "interlaced video. Install ffmpeg for reliable decoding.")
    if use_ffmpeg:
        return FFmpegCapture(path, meta.width, meta.height, meta.nominal_fps), "ffmpeg", notes
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise VideoDecodeError("Video could not be opened for decoding.")
    return cap, "opencv", notes


# ----------------------------------------------------------------------------- config


@dataclass
class AnalysisConfig:
    segmentation: SegmentationConfig = field(default_factory=SegmentationConfig)
    tracking: TrackingConfig = field(default_factory=TrackingConfig)
    derivatives: DerivativeConfig = field(default_factory=DerivativeConfig)
    frame_step: int = 1                     # analyse every Nth decoded frame
    max_frames: int | None = None           # stop after this many analysed frames
    start_time_s: float | None = None
    end_time_s: float | None = None
    processing_scale: float = 1.0           # resize factor applied before segmentation (0, 1]
    edge_sigma_px: float = 1.0              # boundary localisation 1-sigma, processing pixels
    extinction_min_missing_frames: int = 5
    max_consecutive_decode_failures: int = 5
    store_contours: bool = True
    contour_max_points: int = 72
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES
    max_plausible_velocity_mm_s: float = 5000.0
    decoder: str = "auto"                   # auto | opencv | ffmpeg

    def validate(self) -> None:
        if self.decoder not in DECODERS:
            raise ValueError(f"decoder must be one of {DECODERS}.")
        self.segmentation.validate()
        self.tracking.validate()
        self.derivatives.validate()
        if self.frame_step < 1:
            raise ValueError("frame_step must be >= 1.")
        if self.max_frames is not None and self.max_frames < 1:
            raise ValueError("max_frames must be >= 1 when given.")
        if not 0 < self.processing_scale <= 1:
            raise ValueError("processing_scale must be in (0, 1].")
        if self.edge_sigma_px < 0:
            raise ValueError("edge_sigma_px must be non-negative.")
        if (self.start_time_s is not None and self.end_time_s is not None
                and self.end_time_s <= self.start_time_s):
            raise ValueError("end_time_s must be greater than start_time_s.")
        if self.extinction_min_missing_frames < 1 or self.max_consecutive_decode_failures < 1:
            raise ValueError("Frame-count limits must be >= 1.")

    def to_dict(self) -> dict:
        d = {f.name: getattr(self, f.name) for f in fields(self)}
        d["segmentation"] = self.segmentation.to_dict()
        d["tracking"] = self.tracking.to_dict()
        d["derivatives"] = asdict(self.derivatives)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "AnalysisConfig":
        data = dict(data)
        seg = SegmentationConfig.from_dict(data.pop("segmentation", {}) or {})
        trk = TrackingConfig(**(data.pop("tracking", {}) or {}))
        der = DerivativeConfig(**(data.pop("derivatives", {}) or {}))
        allowed = {f.name for f in fields(cls)}
        return cls(segmentation=seg, tracking=trk, derivatives=der,
                   **{k: v for k, v in data.items() if k in allowed})


# ------------------------------------------------------------------------ measurements

# name -> (unit, quantity class, description). Shared with DATA_DICTIONARY.md.
FIELD_DEFINITIONS: dict[str, tuple[str, str, str]] = {
    "experiment_id": ("-", "metadata", "Experiment identifier supplied by the caller."),
    "frame_index": ("-", "metadata", "Zero-based index of the decoded frame in the video."),
    "timestamp_s": ("s", "metadata", "Presentation time relative to the first decoded frame."),
    "status": ("-", "metadata", "detected | low_confidence | not_detected | rejected_discontinuity | frame_error."),
    "confidence": ("0-1", "heuristic", "segmentation_quality x tracking continuity (not a probability)."),
    "segmentation_quality": ("0-1", "heuristic", "contour dominance x clipped local contrast (not a probability)."),
    "contrast": ("0-1", "image_derived", "(mean inside - mean of 5 px outer ring) / 255."),
    "n_candidates": ("-", "image_derived", "Contours passing the minimum-area and local-contrast filters."),
    "threshold": ("0-255", "image_derived", "Global threshold used (Otsu/fixed); empty for local/colour methods."),
    "centroid_x_px": ("px", "image_derived", "Area centroid x of the filled flame region."),
    "centroid_y_px": ("px", "image_derived", "Area centroid y of the filled flame region."),
    "bbox_x_px": ("px", "image_derived", "Bounding box left."),
    "bbox_y_px": ("px", "image_derived", "Bounding box top."),
    "bbox_w_px": ("px", "image_derived", "Bounding box width."),
    "bbox_h_px": ("px", "image_derived", "Bounding box height."),
    "enclosing_center_x_px": ("px", "image_derived", "Minimum enclosing circle centre x."),
    "enclosing_center_y_px": ("px", "image_derived", "Minimum enclosing circle centre y."),
    "enclosing_radius_px": ("px", "image_derived", "Minimum enclosing circle radius."),
    "equivalent_radius_px": ("px", "image_derived", "sqrt(area / pi); primary size measure."),
    "equivalent_radius_sigma_px": ("px", "calculated", "1-sigma random uncertainty of the equivalent radius."),
    "equivalent_diameter_px": ("px", "image_derived", "2 x equivalent radius."),
    "area_px2": ("px^2", "image_derived", "Projected flame area (pixel count of the filled contour)."),
    "perimeter_px": ("px", "image_derived", "Contour arc length."),
    "circularity": ("-", "image_derived", "4 pi A / P^2 (digitised circles score ~0.85-0.95)."),
    "ellipse_major_px": ("px", "image_derived", "Major axis length of the least-squares ellipse."),
    "ellipse_minor_px": ("px", "image_derived", "Minor axis length of the least-squares ellipse."),
    "ellipse_angle_deg": ("deg", "image_derived", "Ellipse orientation (OpenCV convention)."),
    "eccentricity": ("-", "image_derived", "sqrt(1 - (b/a)^2) of the fitted ellipse."),
    "boundary_roughness": ("-", "image_derived", "std / mean of boundary distance from centroid."),
    "touches_border": ("bool", "image_derived", "Flame region touches the image edge (size underestimated)."),
    "radius_mm": ("mm", "calculated", "Equivalent radius x calibration scale."),
    "radius_sigma_random_mm": ("mm", "calculated", "Frame-independent (pixel) uncertainty of radius_mm."),
    "radius_sigma_scale_mm": ("mm", "calculated", "Calibration (systematic, correlated) uncertainty of radius_mm."),
    "radius_sigma_mm": ("mm", "calculated", "Random and scale uncertainty combined in quadrature."),
    "diameter_mm": ("mm", "calculated", "2 x radius_mm."),
    "area_mm2": ("mm^2", "calculated", "Projected area x scale^2."),
    "area_sigma_mm2": ("mm^2", "calculated", "2 pi r sigma_r (total)."),
    "perimeter_mm": ("mm", "calculated", "Perimeter x scale."),
    "equivalent_volume_mm3": ("mm^3", "calculated", "(4/3) pi r^3 - equivalent SPHERICAL estimate, not a 3-D measurement."),
    "equivalent_volume_sigma_mm3": ("mm^3", "calculated", "4 pi r^2 sigma_r (total, first order)."),
    "radius_smoothed_px": ("px", "calculated", "Local-polynomial smoothed equivalent radius."),
    "expansion_velocity_px_s": ("px/s", "calculated", "dr/dt from timestamp-aware local polynomial fit."),
    "expansion_velocity_sigma_px_s": ("px/s", "calculated", "1-sigma random uncertainty of dr/dt."),
    "acceleration_px_s2": ("px/s^2", "calculated", "d2r/dt2 from the same fit."),
    "acceleration_sigma_px_s2": ("px/s^2", "calculated", "1-sigma random uncertainty of d2r/dt2."),
    "expansion_velocity_mm_s": ("mm/s", "calculated", "dr/dt in physical units."),
    "expansion_velocity_sigma_mm_s": ("mm/s", "calculated", "Random + scale uncertainty in quadrature."),
    "acceleration_mm_s2": ("mm/s^2", "calculated", "d2r/dt2 in physical units."),
    "acceleration_sigma_mm_s2": ("mm/s^2", "calculated", "Random + scale uncertainty in quadrature."),
    "centroid_displacement_px": ("px", "calculated", "Distance of centroid from the first accepted centroid."),
    "centroid_displacement_mm": ("mm", "calculated", "centroid_displacement_px x scale."),
    "warnings": ("-", "metadata", "Per-frame notes and warnings, '; '-separated in CSV."),
}


@dataclass
class FrameMeasurement:
    experiment_id: str
    frame_index: int
    timestamp_s: float
    status: str
    confidence: float = 0.0
    segmentation_quality: float = 0.0
    contrast: float | None = None
    n_candidates: int = 0
    threshold: float | None = None
    centroid_x_px: float | None = None
    centroid_y_px: float | None = None
    bbox_x_px: float | None = None
    bbox_y_px: float | None = None
    bbox_w_px: float | None = None
    bbox_h_px: float | None = None
    enclosing_center_x_px: float | None = None
    enclosing_center_y_px: float | None = None
    enclosing_radius_px: float | None = None
    equivalent_radius_px: float | None = None
    equivalent_radius_sigma_px: float | None = None
    equivalent_diameter_px: float | None = None
    area_px2: float | None = None
    perimeter_px: float | None = None
    circularity: float | None = None
    ellipse_major_px: float | None = None
    ellipse_minor_px: float | None = None
    ellipse_angle_deg: float | None = None
    eccentricity: float | None = None
    boundary_roughness: float | None = None
    touches_border: bool | None = None
    radius_mm: float | None = None
    radius_sigma_random_mm: float | None = None
    radius_sigma_scale_mm: float | None = None
    radius_sigma_mm: float | None = None
    diameter_mm: float | None = None
    area_mm2: float | None = None
    area_sigma_mm2: float | None = None
    perimeter_mm: float | None = None
    equivalent_volume_mm3: float | None = None
    equivalent_volume_sigma_mm3: float | None = None
    radius_smoothed_px: float | None = None
    expansion_velocity_px_s: float | None = None
    expansion_velocity_sigma_px_s: float | None = None
    acceleration_px_s2: float | None = None
    acceleration_sigma_px_s2: float | None = None
    expansion_velocity_mm_s: float | None = None
    expansion_velocity_sigma_mm_s: float | None = None
    acceleration_mm_s2: float | None = None
    acceleration_sigma_mm_s2: float | None = None
    centroid_displacement_px: float | None = None
    centroid_displacement_mm: float | None = None
    warnings: list[str] = field(default_factory=list)
    contour_px: list[list[float]] | None = None

    @property
    def accepted(self) -> bool:
        return DetectionStatus(self.status).accepted

    def to_dict(self, include_contour: bool = True) -> dict:
        d = asdict(self)
        if not include_contour:
            d.pop("contour_px", None)
        return d


@dataclass
class AnalysisProgress:
    """Telemetry event emitted after each analysed frame."""

    experiment_id: str
    frames_decoded: int
    frames_analyzed: int
    estimated_total_frames: int
    measurement: FrameMeasurement
    elapsed_s: float

    @property
    def fraction(self) -> float:
        if self.estimated_total_frames <= 0:
            return 0.0
        return min(1.0, self.frames_decoded / self.estimated_total_frames)


def _clean(value: Any) -> Any:
    """Recursively convert NaN/inf to None and numpy scalars to Python types for JSON."""
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _system_info() -> dict:
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "cpu_count": os.cpu_count(),
        "python": platform.python_version(),
        "opencv": cv2.__version__,
        "numpy": np.__version__,
    }


@dataclass
class AnalysisResult:
    experiment_id: str
    video: VideoMetadata
    config: AnalysisConfig
    calibration: Calibration | None
    measurements: list[FrameMeasurement]
    summary: dict
    issues: list[pv.ValidationIssue]
    timestamp_source: str

    def to_dataframe(self) -> pd.DataFrame:
        rows = [m.to_dict(include_contour=False) for m in self.measurements]
        df = pd.DataFrame(rows, columns=[k for k in FIELD_DEFINITIONS])
        df["warnings"] = df["warnings"].apply(lambda w: "; ".join(w) if isinstance(w, list) else "")
        return df

    def to_json_dict(self, include_contours: bool = True) -> dict:
        return _clean({
            "schema": "flame-in-freefall/cv-analysis/v1",
            "engine_version": ENGINE_VERSION,
            "experiment_id": self.experiment_id,
            "video": self.video.to_dict(),
            "timestamp_source": self.timestamp_source,
            "calibration": self.calibration.to_dict() if self.calibration else None,
            "config": self.config.to_dict(),
            "summary": self.summary,
            "issues": [i.to_dict() for i in self.issues],
            "field_definitions": {
                k: {"unit": u, "quantity_class": c, "description": d} for k, (u, c, d) in FIELD_DEFINITIONS.items()
            },
            "measurements": [m.to_dict(include_contour=include_contours) for m in self.measurements],
        })

    def export_json(self, path: str | Path, include_contours: bool = True) -> Path:
        path = Path(path)
        path.write_text(json.dumps(self.to_json_dict(include_contours), indent=1))
        return path

    def export_csv(self, path: str | Path) -> Path:
        path = Path(path)
        self.to_dataframe().to_csv(path, index=False)
        return path


# ----------------------------------------------------------------------------- overlay

_CYAN, _AMBER, _RED, _WHITE = (255, 255, 0), (0, 191, 255), (60, 60, 230), (255, 255, 255)


def render_overlay(frame: np.ndarray, m: FrameMeasurement, contour: np.ndarray | None = None) -> np.ndarray:
    """Draw contour, centroid, equivalent-radius circle and a status line onto a copy of ``frame``."""
    out = frame.copy()
    colour = _CYAN if m.status == DetectionStatus.DETECTED.value else _AMBER
    if m.status in (DetectionStatus.NOT_DETECTED.value, DetectionStatus.FRAME_ERROR.value):
        colour = _RED
    if contour is None and m.contour_px:
        contour = np.asarray(m.contour_px, dtype=np.int32).reshape(-1, 1, 2)
    if contour is not None:
        cv2.drawContours(out, [contour.astype(np.int32)], -1, colour, 1, cv2.LINE_AA)
    if m.centroid_x_px is not None and m.equivalent_radius_px is not None:
        c = (int(round(m.centroid_x_px)), int(round(m.centroid_y_px)))
        cv2.drawMarker(out, c, colour, cv2.MARKER_CROSS, 12, 1, cv2.LINE_AA)
        cv2.circle(out, c, int(round(m.equivalent_radius_px)), _WHITE, 1, cv2.LINE_AA)
    size = (f"r={m.radius_mm:.2f} mm" if m.radius_mm is not None
            else f"r={m.equivalent_radius_px:.1f} px" if m.equivalent_radius_px is not None else "r=--")
    text = f"#{m.frame_index}  t={m.timestamp_s:.3f}s  {m.status}  {size}"
    cv2.putText(out, text, (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, colour, 1, cv2.LINE_AA)
    return out


# ---------------------------------------------------------------------------- analyzer


class FlameAnalyzer:
    """Configurable, memory-efficient flame analysis for one video at a time.

    Example::

        cal = Calibration(known_length_mm=10.0, measured_length_px=100.0)
        analyzer = FlameAnalyzer(AnalysisConfig(), calibration=cal)
        result = analyzer.analyze("run_042.mp4", experiment_id="EXP-042")
        result.export_csv("run_042.csv")
    """

    def __init__(
        self,
        config: AnalysisConfig | None = None,
        calibration: Calibration | None = None,
        distortion: DistortionCorrection | None = None,
    ) -> None:
        self.config = config or AnalysisConfig()
        self.config.validate()
        self.calibration = calibration
        self.distortion = distortion

    # -- per-frame ---------------------------------------------------------------

    def _prepare(self, frame: np.ndarray) -> np.ndarray:
        if self.distortion is not None:
            frame = self.distortion.apply(frame)
        s = self.config.processing_scale
        if s < 1.0:
            frame = cv2.resize(frame, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        return frame

    def _measure_frame(
        self, frame: np.ndarray, segmenter: Segmenter, tracker: FlameTracker,
        experiment_id: str, index: int, t: float,
    ) -> tuple[FrameMeasurement, np.ndarray | None, np.ndarray]:
        """Measure one frame; returns ``(measurement, full-resolution contour or None, mask)``."""
        cfg = self.config
        seg = segmenter.segment(self._prepare(frame))
        m = FrameMeasurement(experiment_id, index, t, DetectionStatus.NOT_DETECTED.value, threshold=seg.threshold)
        if seg.rejected_reason:
            m.warnings.append(seg.rejected_reason)
        contours, fg_total = find_contours(seg.mask, cfg.segmentation.min_contour_area_px)
        measured = [measure_contour(c, seg.intensity) for c in contours]
        candidates = [g for g in measured if g.contrast >= cfg.segmentation.min_candidate_contrast]
        m.n_candidates = len(candidates)
        if len(candidates) < len(measured):
            m.warnings.append(
                f"{len(measured) - len(candidates)} contour(s) below local-contrast floor "
                f"{cfg.segmentation.min_candidate_contrast:.2f} ignored")

        def quality(g: ContourGeometry) -> float:
            dominance = g.area_px2 / fg_total if fg_total else 0.0
            return float(min(1.0, dominance) * min(1.0, g.contrast / 0.25))

        decision = tracker.update(candidates, t, quality)
        m.status = decision.status.value
        m.warnings.extend(decision.notes)
        g = decision.chosen
        if g is None:
            return m, None, seg.mask

        inv = 1.0 / cfg.processing_scale
        m.segmentation_quality = quality(g)
        m.confidence = m.segmentation_quality * decision.continuity
        m.contrast = g.contrast
        m.centroid_x_px, m.centroid_y_px = g.centroid_x_px * inv, g.centroid_y_px * inv
        bx, by, bw, bh = g.bbox
        m.bbox_x_px, m.bbox_y_px, m.bbox_w_px, m.bbox_h_px = bx * inv, by * inv, bw * inv, bh * inv
        m.enclosing_center_x_px = g.enclosing_center_x_px * inv
        m.enclosing_center_y_px = g.enclosing_center_y_px * inv
        m.enclosing_radius_px = g.enclosing_radius_px * inv
        m.equivalent_radius_px = g.equivalent_radius_px * inv
        m.equivalent_radius_sigma_px = radius_sigma_from_boundary(
            g.perimeter_px, g.equivalent_radius_px, cfg.edge_sigma_px) * inv
        m.equivalent_diameter_px = g.equivalent_diameter_px * inv
        m.area_px2 = g.area_px2 * inv * inv
        m.perimeter_px = g.perimeter_px * inv
        m.circularity = g.circularity
        if g.ellipse_major_px is not None:
            m.ellipse_major_px = g.ellipse_major_px * inv
            m.ellipse_minor_px = g.ellipse_minor_px * inv
            m.ellipse_angle_deg = g.ellipse_angle_deg
            m.eccentricity = g.eccentricity
        m.boundary_roughness = g.boundary_roughness
        m.touches_border = g.touches_border
        if g.touches_border:
            m.warnings.append("flame region touches the image border; size is underestimated")
        if m.n_candidates > 1 and m.segmentation_quality < 0.5:
            m.warnings.append("foreground is fragmented across several contours")

        if self.calibration is not None:
            s, ss = self.calibration.mm_per_px, self.calibration.mm_per_px_sigma
            r = px_to_physical(m.equivalent_radius_px, m.equivalent_radius_sigma_px, s, ss, 1)
            m.radius_mm, m.radius_sigma_random_mm, m.radius_sigma_scale_mm = r.value, r.random, r.systematic
            m.radius_sigma_mm = r.total
            m.diameter_mm = 2.0 * r.value
            m.area_mm2 = m.area_px2 * s * s
            m.area_sigma_mm2 = circle_area_sigma(r.value, r.total)
            m.perimeter_mm = m.perimeter_px * s
            m.equivalent_volume_mm3 = equivalent_spherical_volume(r.value)
            m.equivalent_volume_sigma_mm3 = sphere_volume_sigma(r.value, r.total)

        full_res_contour = (g.contour.astype(float) * inv)
        if cfg.store_contours:
            m.contour_px = simplify_contour(full_res_contour, cfg.contour_max_points)
        return m, full_res_contour, seg.mask

    # -- whole video ---------------------------------------------------------------

    def analyze(
        self,
        video_path: str | Path,
        experiment_id: str,
        progress_callback: Callable[[AnalysisProgress], None] | None = None,
        cancel_event: threading.Event | None = None,
        annotated_output_path: str | Path | None = None,
    ) -> AnalysisResult:
        """Analyse a whole video. Raises ``VideoValidationError``/``VideoDecodeError``/``AnalysisCancelled``."""
        if not experiment_id or not str(experiment_id).strip():
            raise ValueError("experiment_id is required.")
        cfg = self.config
        path = Path(video_path)
        meta = probe_video(path, cfg.max_file_bytes)
        issues: list[pv.ValidationIssue] = []
        if self.calibration is not None:
            for w in self.calibration.check_compatible(meta.width, meta.height) + self.calibration.warnings():
                issues.append(pv.ValidationIssue("calibration", "warning", w))
        else:
            issues.append(pv.ValidationIssue(
                "uncalibrated", "info", "No calibration supplied; results are reported in pixels only."))

        started = time.perf_counter()
        measurements: list[FrameMeasurement] = []
        pos_ms: list[float] = []
        segmenter = Segmenter(cfg.segmentation)
        tracker = FlameTracker(cfg.tracking)
        writer = None
        est_total = meta.reported_frame_count

        cap, decoder_used, decoder_notes = open_capture(path, meta, cfg.decoder)
        issues.extend(pv.ValidationIssue("decoder", "warning", n) for n in decoder_notes)
        if decoder_used == "opencv" and meta.opencv_first_frame_blank:
            issues.append(pv.ValidationIssue(
                "decoder", "warning", "OpenCV decoded the first frame as all zeros; check for a decoder failure."))
        blank_frames = 0
        try:
            if annotated_output_path is not None:
                writer = cv2.VideoWriter(
                    str(annotated_output_path), cv2.VideoWriter_fourcc(*"mp4v"),
                    meta.nominal_fps or 30.0, (meta.width, meta.height))
                if not writer.isOpened():
                    raise FlameAnalysisError("Could not open the annotated-video writer.")

            index, decoded, analyzed, failures = -1, 0, 0, 0
            pending_errors: list[int] = []
            t0_ms: float | None = None
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    raise AnalysisCancelled(f"Analysis of {experiment_id} cancelled after {decoded} frames.")
                if cfg.max_frames is not None and analyzed >= cfg.max_frames:
                    break
                index += 1
                if not cap.grab():
                    failures += 1
                    if est_total and index < est_total and failures < cfg.max_consecutive_decode_failures:
                        pending_errors.append(index)
                        continue
                    break
                # A frame decoded after failures: the failed indices were genuine decode errors.
                for bad in pending_errors:
                    measurements.append(FrameMeasurement(
                        experiment_id, bad, math.nan, DetectionStatus.FRAME_ERROR.value,
                        warnings=["frame could not be decoded"]))
                    pos_ms.append(math.nan)
                pending_errors.clear()
                failures = 0
                decoded += 1

                ms = float(cap.get(cv2.CAP_PROP_POS_MSEC))
                if t0_ms is None:
                    t0_ms = ms
                t_container = (ms - t0_ms) / 1000.0
                if cfg.start_time_s is not None and t_container < cfg.start_time_s:
                    continue
                if cfg.end_time_s is not None and t_container > cfg.end_time_s:
                    break
                if index % cfg.frame_step:
                    continue

                ok, frame = cap.retrieve()
                pos_ms.append(ms)
                if not ok or frame is None or frame.size == 0:
                    measurements.append(FrameMeasurement(
                        experiment_id, index, t_container, DetectionStatus.FRAME_ERROR.value,
                        warnings=["frame could not be retrieved"]))
                    continue
                if not frame.any():
                    blank_frames += 1
                m, contour, _ = self._measure_frame(frame, segmenter, tracker, experiment_id, index, t_container)
                measurements.append(m)
                analyzed += 1
                if writer is not None:
                    writer.write(render_overlay(frame, m, contour))
                if progress_callback is not None:
                    progress_callback(AnalysisProgress(
                        experiment_id, decoded, analyzed, est_total, m, time.perf_counter() - started))

            if pending_errors:
                issues.append(pv.ValidationIssue(
                    "decoding_ended_early", "warning",
                    f"Decoding stopped at frame {pending_errors[0]} although the container reports "
                    f"{est_total} frames; trailing frames may be corrupted or the count may be approximate."))
        finally:
            cap.release()
            if writer is not None:
                writer.release()

        if decoded == 0:
            raise VideoDecodeError("No frames could be decoded.")
        if analyzed and blank_frames == analyzed:
            issues.append(pv.ValidationIssue(
                "all_frames_blank", "error",
                f"All {analyzed} analysed frames are exactly zero, which real sensors almost never produce. "
                f"This usually indicates a decoder failure (decoder used: {decoder_used}); verify with "
                f"decoder='ffmpeg' before trusting any result."))
        timestamp_source = self._finalise_timestamps(measurements, pos_ms, meta, issues)
        self._compute_kinematics(measurements)
        summary = self._summarise(measurements, meta, issues, decoded, time.perf_counter() - started, timestamp_source)
        summary["decoder"] = decoder_used
        return AnalysisResult(
            experiment_id, meta, cfg, self.calibration, measurements, summary, issues, timestamp_source)

    # -- post-processing -------------------------------------------------------------

    def _finalise_timestamps(
        self, ms: list[FrameMeasurement], pos_ms: list[float], meta: VideoMetadata,
        issues: list[pv.ValidationIssue],
    ) -> str:
        """Keep container timestamps if they are usable; otherwise fall back to index / fps."""
        t = np.array([m.timestamp_s for m in ms], dtype=float)
        ok = np.isfinite(t)
        usable = ok.sum() < 2 or bool(np.all(np.diff(t[ok]) > 0))
        if usable:
            source = "container_pts"
        elif meta.nominal_fps > 0:
            source = "nominal_fps"
            for m in ms:
                m.timestamp_s = m.frame_index / meta.nominal_fps
            issues.append(pv.ValidationIssue(
                "timestamps_fallback", "warning",
                "Container timestamps were not strictly increasing; using frame_index / nominal fps."))
        else:
            raise VideoDecodeError("No usable timestamps and no frame rate; cannot build a time axis.")
        # Frame errors with unknown time: assign the nominal time for display only.
        for m in ms:
            if not math.isfinite(m.timestamp_s) and meta.nominal_fps > 0:
                m.timestamp_s = m.frame_index / meta.nominal_fps
                m.warnings.append("timestamp approximated from nominal frame rate")
        issues.extend(pv.validate_timestamps(np.array([m.timestamp_s for m in ms if m.status != "frame_error"])))
        return source

    def _compute_kinematics(self, ms: list[FrameMeasurement]) -> None:
        if not ms:
            return
        t = np.array([m.timestamp_s for m in ms], dtype=float)
        acc = np.array([m.accepted for m in ms])
        r = np.array([m.equivalent_radius_px if m.accepted else np.nan for m in ms], dtype=float)
        sr = np.array([m.equivalent_radius_sigma_px if m.accepted else np.nan for m in ms], dtype=float)
        if acc.sum() >= self.config.derivatives.polyorder + 1:
            kin = local_polynomial_kinematics(t, r, sr, self.config.derivatives)
            cal = self.calibration
            for i, m in enumerate(ms):
                if not acc[i]:
                    continue
                m.radius_smoothed_px = _f(kin.smoothed[i])
                m.expansion_velocity_px_s = _f(kin.first_derivative[i])
                m.expansion_velocity_sigma_px_s = _f(kin.first_derivative_sigma[i])
                m.acceleration_px_s2 = _f(kin.second_derivative[i])
                m.acceleration_sigma_px_s2 = _f(kin.second_derivative_sigma[i])
                if cal is not None:
                    s, ss = cal.mm_per_px, cal.mm_per_px_sigma
                    if m.expansion_velocity_px_s is not None:
                        v = px_to_physical(m.expansion_velocity_px_s, kin.first_derivative_sigma[i], s, ss, 1)
                        m.expansion_velocity_mm_s, m.expansion_velocity_sigma_mm_s = v.value, _f(v.total)
                    if m.acceleration_px_s2 is not None:
                        a = px_to_physical(m.acceleration_px_s2, kin.second_derivative_sigma[i], s, ss, 1)
                        m.acceleration_mm_s2, m.acceleration_sigma_mm_s2 = a.value, _f(a.total)
            if kin.notes:
                ms[0].warnings.extend(f"kinematics: {n}" for n in kin.notes)
        first = next((m for m in ms if m.accepted), None)
        if first is not None:
            for m in ms:
                if m.accepted:
                    d = math.hypot(m.centroid_x_px - first.centroid_x_px, m.centroid_y_px - first.centroid_y_px)
                    m.centroid_displacement_px = d
                    if self.calibration is not None:
                        m.centroid_displacement_mm = d * self.calibration.mm_per_px

    def _summarise(
        self, ms: list[FrameMeasurement], meta: VideoMetadata, issues: list[pv.ValidationIssue],
        decoded: int, elapsed: float, timestamp_source: str,
    ) -> dict:
        cfg = self.config
        counts = {s.value: 0 for s in DetectionStatus}
        for m in ms:
            counts[m.status] += 1
        valid = [m for m in ms if m.status != DetectionStatus.FRAME_ERROR.value]
        acc = [m for m in valid if m.accepted]
        idx = np.array([m.frame_index for m in valid])
        t = np.array([m.timestamp_s for m in valid])
        ext: ExtinctionEstimate = estimate_extinction(
            t, np.array([m.accepted for m in valid], dtype=bool), cfg.extinction_min_missing_frames)

        issues.extend(pv.check_radius_bounds(
            np.array([m.equivalent_radius_px if m.accepted else np.nan for m in valid], dtype=float),
            meta.width, meta.height, idx))
        if self.calibration is not None:
            issues.extend(pv.check_expansion_velocity(
                np.array([_nan(m.expansion_velocity_mm_s) for m in valid]), idx, cfg.max_plausible_velocity_mm_s))
            issues.extend(pv.check_relative_uncertainty(
                np.array([_nan(m.radius_mm) for m in acc]), np.array([_nan(m.radius_sigma_mm) for m in acc]),
                "radius_mm"))
        if any(m.touches_border for m in acc):
            issues.append(pv.ValidationIssue(
                "flame_clipped", "warning", "The flame touches the image border in at least one frame."))

        def stat(values: Iterable[float | None]) -> dict | None:
            arr = np.array([v for v in values if v is not None and math.isfinite(v)], dtype=float)
            if arr.size == 0:
                return None
            return {"min": float(arr.min()), "max": float(arr.max()), "mean": float(arr.mean()),
                    "std": float(arr.std(ddof=1)) if arr.size > 1 else 0.0, "n": int(arr.size)}

        circ = stat(m.circularity for m in acc)
        # Observed scatter of the radius about its local-polynomial smooth (robust MAD estimate),
        # reported next to the *assumed* boundary uncertainty so that the assumption can be checked.
        resid = np.array([m.equivalent_radius_px - m.radius_smoothed_px for m in acc
                          if m.radius_smoothed_px is not None], dtype=float)
        observed_noise = float(1.4826 * np.median(np.abs(resid - np.median(resid)))) if resid.size >= 5 else None
        assumed_noise = stat(m.equivalent_radius_sigma_px for m in acc)
        peak = max(acc, key=lambda m: m.equivalent_radius_px, default=None)
        video_duration = float(t[-1] - t[0]) if t.size > 1 else 0.0
        return _clean({
            "frames_decoded": decoded,
            "frames_analyzed": len(valid),
            "status_counts": counts,
            "detection_rate": len(acc) / len(valid) if valid else 0.0,
            "timestamp_source": timestamp_source,
            "analysed_time_span_s": video_duration,
            "calibrated": self.calibration is not None,
            "equivalent_radius_px": stat(m.equivalent_radius_px for m in acc),
            "radius_mm": stat(m.radius_mm for m in acc),
            "peak_radius": None if peak is None else {
                "frame_index": peak.frame_index, "timestamp_s": peak.timestamp_s,
                "equivalent_radius_px": peak.equivalent_radius_px, "radius_mm": peak.radius_mm,
                "radius_sigma_mm": peak.radius_sigma_mm},
            "radius_noise_check": {
                "assumed_sigma_px_median": None if assumed_noise is None else assumed_noise["mean"],
                "observed_residual_sigma_px": observed_noise,
                "note": "Observed value is the robust scatter of r about its smoothed curve; it underestimates "
                        "noise slightly because the smoother absorbs some of it, and it excludes systematic bias.",
            },
            "expansion_velocity_px_s": stat(m.expansion_velocity_px_s for m in acc),
            "expansion_velocity_mm_s": stat(m.expansion_velocity_mm_s for m in acc),
            "circularity": circ,
            "shape_stability_cv": (circ["std"] / circ["mean"]) if circ and circ["mean"] else None,
            "eccentricity": stat(m.eccentricity for m in acc),
            "boundary_roughness": stat(m.boundary_roughness for m in acc),
            "max_centroid_displacement_px": max((m.centroid_displacement_px or 0.0 for m in acc), default=None),
            "max_centroid_displacement_mm": (
                max((m.centroid_displacement_mm or 0.0 for m in acc), default=None) if self.calibration else None),
            "extinction": asdict(ext),
            "processing": {
                "wall_time_s": elapsed,
                "frames_per_second": decoded / elapsed if elapsed > 0 else None,
                "realtime_factor": video_duration / elapsed if elapsed > 0 and video_duration else None,
                "processing_scale": cfg.processing_scale,
                "frame_step": cfg.frame_step,
                "system": _system_info(),
            },
            "quantity_notes": [
                "Pixel quantities are image-derived from a 2-D projection.",
                "Millimetre quantities are calculated with the supplied calibration scale.",
                "equivalent_volume_mm3 assumes a spherical flame; it is not a 3-D measurement.",
                "Uncertainties include boundary localisation and calibration scale only.",
            ],
        })

    # -- inspection helpers --------------------------------------------------------------

    def preview_frame(
        self, video_path: str | Path, frame_index: int, experiment_id: str = "preview"
    ) -> tuple[np.ndarray, np.ndarray, FrameMeasurement]:
        """Segment a single frame: returns ``(overlay_bgr, mask, measurement)`` for parameter tuning.

        The mask is at processing resolution (``processing_scale``).

        Tracking continuity is not available for a single frame; background
        subtraction needs prior frames and is therefore primed with all frames
        before ``frame_index``.
        """
        meta = probe_video(video_path, self.config.max_file_bytes)
        if frame_index < 0 or (meta.reported_frame_count and frame_index >= meta.reported_frame_count):
            raise ValueError(f"frame_index must be within 0-{meta.reported_frame_count - 1}.")
        segmenter = Segmenter(self.config.segmentation)
        cap, _, _ = open_capture(video_path, meta, self.config.decoder)
        try:
            frame, t0, ms = None, None, 0.0
            for i in range(frame_index + 1):
                ok, frame = cap.read()
                if not ok:
                    raise VideoDecodeError(f"Frame {i} could not be decoded.")
                ms = float(cap.get(cv2.CAP_PROP_POS_MSEC))
                t0 = ms if t0 is None else t0
                if i < frame_index and self.config.segmentation.method is SegmentationMethod.BACKGROUND_SUBTRACTION:
                    segmenter.segment(self._prepare(frame))
        finally:
            cap.release()
        m, contour, mask = self._measure_frame(
            frame, segmenter, FlameTracker(self.config.tracking), experiment_id, frame_index, (ms - t0) / 1000.0)
        return render_overlay(frame, m, contour), mask, m


def _f(x: float) -> float | None:
    return float(x) if x is not None and math.isfinite(x) else None


def _nan(x: float | None) -> float:
    return math.nan if x is None else float(x)
