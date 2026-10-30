"""Scientific image-sequence input (e.g. NASA ACME CFI intensified camera TIFF stacks).

ACME science cameras store one 16-bit TIFF per frame, with the capture time in
the file name (``20191031_194043.001_INTNS_19304A7_00345.tiff``), at frame rates
that vary with exposure [s-Flame Data Interpretation §4.B]. This module exposes
such a directory through the same minimal ``VideoCapture``-style interface as
``FFmpegCapture``, so ``FlameAnalyzer`` processes it like a video.

Preprocessing (all documented in SCIENTIFIC_ASSUMPTIONS.md, A-IMG-*):

1. **Dark subtraction**: per-pixel median of the first ``dark_frames`` frames.
   These must be flame-free (e.g. pre-ignition); this is checked and reported.
2. **Hot-pixel removal**: 3x3 median filter. Radiation damage on orbit produced
   isolated hot pixels ("a star field") in ACME cameras.
3. **Fixed 16 -> 8 bit scaling** for the whole sequence (never per frame, which
   would move the segmentation threshold between frames).
4. **Saturation flag** for frames whose raw maximum reaches ``saturation_level``.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

IMAGE_EXTENSIONS = (".tif", ".tiff", ".png")
_STAMP = re.compile(r"(\d{8}_\d{6}\.\d{3})")


@dataclass
class ImageSequenceConfig:
    dark_frames: int = 10              # leading frames used for the dark frame; 0 disables
    hot_pixel_filter: bool = True
    full_scale_counts: float | None = None  # dark-subtracted counts mapped to 255; None = auto
    auto_percentile: float = 99.95     # percentile over sampled frames used when full_scale_counts is None
    saturation_level: int = 65000      # raw counts at/above which a pixel is treated as saturated
    sample_every: int = 10             # frame stride used for the auto scale estimate

    def validate(self) -> None:
        if self.dark_frames < 0 or self.sample_every < 1:
            raise ValueError("dark_frames must be >= 0 and sample_every >= 1.")
        if self.full_scale_counts is not None and self.full_scale_counts <= 0:
            raise ValueError("full_scale_counts must be positive.")
        if not 50 <= self.auto_percentile <= 100:
            raise ValueError("auto_percentile must be within 50-100.")


def list_frames(directory: str | Path) -> list[Path]:
    d = Path(directory)
    if not d.is_dir():
        raise FileNotFoundError(f"Image-sequence directory not found: {d.name}")
    files = sorted(p for p in d.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS and p.is_file())
    if not files:
        raise FileNotFoundError(f"No TIFF/PNG frames in {d.name}")
    return files


def frame_times(files: list[Path]) -> tuple[np.ndarray | None, str]:
    """Seconds since the first frame from timestamps embedded in file names, if all frames have one."""
    stamps = []
    for f in files:
        m = _STAMP.search(f.name)
        if not m:
            return None, "none"
        stamps.append(datetime.strptime(m.group(1), "%Y%m%d_%H%M%S.%f"))
    t = np.array([(s - stamps[0]).total_seconds() for s in stamps])
    return t, "filename_timestamp"


def read_raw(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Unreadable image: {path.name}")
    if img.ndim == 3:
        img = img.max(axis=2)
    return img


class ImageSequenceCapture:
    """``VideoCapture``-style reader over a directory of frames with fixed preprocessing."""

    def __init__(self, directory: str | Path, config: ImageSequenceConfig | None = None, fps_hint: float = 0.0):
        self.config = config or ImageSequenceConfig()
        self.config.validate()
        self.files = list_frames(directory)
        self.times, self.time_source = frame_times(self.files)
        self._fps = fps_hint
        self._index = -1
        self._current: np.ndarray | None = None
        self.last_saturated = False
        self.notes: list[str] = []
        first = read_raw(self.files[0])
        self.shape = first.shape
        self.bit_depth = 16 if first.dtype == np.uint16 else 8
        self.dark = self._dark_frame()
        self.full_scale = self._full_scale()

    def _prep(self, raw: np.ndarray) -> np.ndarray:
        img = raw.astype(np.float32)
        if self.dark is not None:
            img = np.clip(img - self.dark, 0, None)
        if self.config.hot_pixel_filter:
            img = cv2.medianBlur(img, 3)
        return img

    def _dark_frame(self) -> np.ndarray | None:
        n = min(self.config.dark_frames, len(self.files))
        if n == 0:
            return None
        stack = np.stack([read_raw(f).astype(np.float32) for f in self.files[:n]])
        dark = np.median(stack, axis=0)
        # Flame-free check on whole-frame mean brightness: intensified cameras have large
        # per-pixel noise, but light from a flame raises the mean of the frame.
        means = stack.reshape(n, -1).mean(axis=1)
        ref = float(np.median(means))
        if np.max(np.abs(means - ref)) > max(0.5 * ref, 5.0):
            self.notes.append(
                f"dark-frame mean brightness varies from {means.min():.1f} to {means.max():.1f} counts; "
                "the leading frames may contain light. Choose flame-free leading frames.")
        self.notes.append(f"dark frame = median of first {n} frames")
        return dark

    def _full_scale(self) -> float:
        if self.config.full_scale_counts is not None:
            return float(self.config.full_scale_counts)
        sample, skipped = [], 0
        for f in self.files[:: self.config.sample_every]:
            raw = read_raw(f)
            if self.bit_depth == 16 and raw.max() >= self.config.saturation_level:
                skipped += 1  # a saturated burst (e.g. ignition) must not set the scale for the flame
                continue
            sample.append(self._prep(raw))
        if not sample:
            sample = [self._prep(read_raw(f)) for f in self.files[:: self.config.sample_every]]
        value = max(float(np.percentile(np.stack(sample), self.config.auto_percentile)), 1.0)
        self.notes.append(f"8-bit scale: {value:.0f} dark-subtracted counts = 255 "
                          f"({self.config.auto_percentile} percentile over every {self.config.sample_every}th frame, "
                          f"{skipped} saturated sample frame(s) excluded)")
        return value

    # --- VideoCapture-like API ------------------------------------------------------------

    def isOpened(self) -> bool:  # noqa: N802
        return True

    def grab(self) -> bool:
        if self._index + 1 >= len(self.files):
            return False
        self._index += 1
        self._current = None
        return True

    def retrieve(self) -> tuple[bool, np.ndarray | None]:
        if self._index < 0:
            return False, None
        try:
            raw = read_raw(self.files[self._index])
        except ValueError:
            return False, None
        self.last_saturated = bool(raw.max() >= self.config.saturation_level) if self.bit_depth == 16 else bool(raw.max() >= 255)
        img = self._prep(raw)
        img8 = np.clip(img * (255.0 / self.full_scale), 0, 255).astype(np.uint8)
        return True, cv2.cvtColor(img8, cv2.COLOR_GRAY2BGR)

    def read(self) -> tuple[bool, np.ndarray | None]:
        return self.retrieve() if self.grab() else (False, None)

    def get(self, prop: int) -> float:
        if prop == cv2.CAP_PROP_POS_MSEC:
            if self.times is not None and 0 <= self._index < len(self.times):
                return float(self.times[self._index] * 1000.0)
            return self._index / self._fps * 1000.0 if self._fps > 0 else math.nan
        return 0.0

    def release(self) -> None:
        self._current = None
