"""Frame access for the video viewer: metadata, single frames as JPEG, segmentation previews.

Browsers cannot display ACME's 16-bit TIFF frames, and a ``<video>`` element cannot
step to an exact frame index reliably, so the viewer shows server-rendered frames.
Frame ``i`` here is the same decoded frame ``i`` that the analysis measured, so
overlays drawn from results line up with the image.

* Image sequences: the analysis preprocessing (dark subtraction, hot-pixel filter,
  fixed 8-bit scale) is applied, exactly as analysed.
* Videos: frames are decoded with the configured decoder (FFmpeg by default).

Rendered JPEGs are cached on disk per input, frame and preprocessing settings.
"""

from __future__ import annotations

import base64
import hashlib
import json
import shutil
import subprocess
import threading
from dataclasses import asdict
from pathlib import Path

import cv2
import numpy as np

from backend.vision.calibration import Calibration
from backend.vision.cv_engine import AnalysisConfig, FlameAnalyzer, probe_video
from backend.vision.image_sequence import ImageSequenceCapture

_SEQ_CACHE: dict[str, ImageSequenceCapture] = {}
_LOCK = threading.Lock()


def media_info(path: Path) -> dict:
    meta = probe_video(path)
    info = meta.to_dict()
    info.pop("opencv_first_frame_blank", None)
    info["kind"] = "image-sequence" if meta.container == "image-sequence" else "video"
    if info["kind"] == "image-sequence":
        cap = _sequence(path, AnalysisConfig())
        info["frame_times_s"] = [round(float(t), 6) for t in cap.times] if cap.times is not None else None
    return info


def _sequence(path: Path, cfg: AnalysisConfig) -> ImageSequenceCapture:
    key = f"{path}|{json.dumps(asdict(cfg.image_sequence), sort_keys=True)}"
    with _LOCK:
        cap = _SEQ_CACHE.get(key)
        if cap is None:
            cap = _SEQ_CACHE[key] = ImageSequenceCapture(path, cfg.image_sequence)
            if len(_SEQ_CACHE) > 8:
                _SEQ_CACHE.pop(next(iter(_SEQ_CACHE)))
        return cap


def read_frame(path: Path, index: int, cfg: AnalysisConfig | None = None) -> np.ndarray:
    """Decoded BGR frame ``index`` (0-based), preprocessed as the analysis sees it."""
    cfg = cfg or AnalysisConfig()
    meta = probe_video(path)
    if index < 0 or (meta.reported_frame_count and index >= meta.reported_frame_count):
        raise IndexError(f"Frame {index} is outside 0-{meta.reported_frame_count - 1}.")
    if meta.container == "image-sequence":
        cap = _sequence(path, cfg)
        with _LOCK:
            cap._index = index  # noqa: SLF001 - random access into the sequence reader
            ok, frame = cap.retrieve()
        if not ok:
            raise IndexError(f"Frame {index} could not be read.")
        return frame
    if shutil.which("ffmpeg") and cfg.decoder != "opencv":
        out = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:v:0", "-vf", f"yadif=0:-1:1,select=eq(n\\,{index})",
             "-fps_mode", "passthrough", "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
            capture_output=True, timeout=120)
        frame = cv2.imdecode(np.frombuffer(out.stdout, np.uint8), cv2.IMREAD_COLOR) if out.stdout else None
    else:
        cap = cv2.VideoCapture(str(path))
        cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = cap.read()
        cap.release()
        frame = frame if ok else None
    if frame is None:
        raise IndexError(f"Frame {index} could not be decoded.")
    return frame


def frame_jpeg(path: Path, index: int, cache_dir: Path, cfg: AnalysisConfig | None = None,
               max_width: int = 1400, quality: int = 85) -> bytes:
    cfg = cfg or AnalysisConfig()
    key = hashlib.sha256(f"{path}|{index}|{json.dumps(asdict(cfg.image_sequence), sort_keys=True)}|{max_width}|{quality}"
                         .encode()).hexdigest()[:24]
    cached = cache_dir / f"{key}.jpg"
    if cached.exists():
        return cached.read_bytes()
    frame = read_frame(path, index, cfg)
    h, w = frame.shape[:2]
    if w > max_width:
        frame = cv2.resize(frame, (max_width, int(h * max_width / w)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError("JPEG encoding failed.")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(buf.tobytes())
    return buf.tobytes()


def segmentation_preview(path: Path, index: int, config: dict | None, calibration: dict | None) -> dict:
    """Run the analysis on one frame; returns the measurement and a PNG of the mask (base64)."""
    cfg = AnalysisConfig.from_dict(config or {})
    cfg.validate()
    cal = Calibration.from_dict(calibration) if calibration else None
    overlay, mask, m = FlameAnalyzer(cfg, cal).preview_frame(path, index, "preview")
    data = m.to_dict()
    out = {"measurement": data, "mask_png_base64": None, "overlay_jpeg_base64": None}
    if mask is not None:
        ok, buf = cv2.imencode(".png", mask)
        if ok:
            out["mask_png_base64"] = base64.b64encode(buf.tobytes()).decode()
    h, w = overlay.shape[:2]
    if w > 1400:
        overlay = cv2.resize(overlay, (1400, int(h * 1400 / w)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", overlay, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if ok:
        out["overlay_jpeg_base64"] = base64.b64encode(buf.tobytes()).decode()
    return out
