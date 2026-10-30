"""Configurable flame segmentation.

Every method produces a binary foreground mask from one BGR frame. The mask is
then cleaned with morphological opening (removes isolated noise pixels) and
closing (bridges small gaps in the luminous zone), and external contours are
extracted.

Choice of intensity channel matters for flames: a soot-free (blue) flame is
dim in a standard luma conversion (Y = 0.299 R + 0.587 G + 0.114 B), so the
default channel is the per-pixel maximum of B, G and R (HSV "value"), which
treats blue, yellow and white emission alike.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum

import cv2
import numpy as np


class SegmentationMethod(str, Enum):
    OTSU = "otsu"
    ADAPTIVE = "adaptive"
    FIXED = "fixed"
    HSV = "hsv"
    BACKGROUND_SUBTRACTION = "background_subtraction"


class Channel(str, Enum):
    MAX = "max"
    GRAY = "gray"
    BLUE = "blue"
    GREEN = "green"
    RED = "red"


@dataclass
class SegmentationConfig:
    """User-adjustable segmentation parameters (all intensities on a 0-255 scale)."""

    method: SegmentationMethod = SegmentationMethod.OTSU
    channel: Channel = Channel.MAX
    blur_kernel: int = 5                 # Gaussian kernel size (odd); 0 or 1 disables blurring
    threshold_offset: float = 0.0        # added to the Otsu threshold; >0 = stricter (sensitivity)
    fixed_threshold: float = 127.0
    adaptive_block_size: int = 51        # odd neighbourhood size for adaptive thresholding
    adaptive_c: float = -5.0             # pixel must exceed local mean by -C to be foreground
    hsv_lower: tuple[int, int, int] = (0, 0, 80)
    hsv_upper: tuple[int, int, int] = (180, 255, 255)
    morph_kernel: int = 5                # elliptical structuring element size; 0 disables
    open_iterations: int = 1
    close_iterations: int = 2
    min_contour_area_px: float = 30.0
    min_contrast: float = 12.0           # minimum (max - min) of the blurred channel to attempt detection
    min_candidate_contrast: float = 0.06 # minimum local contrast (0-1) of a contour vs its 5 px outer ring
    max_foreground_fraction: float = 0.9 # a "flame" covering more of the image is rejected
    bg_history: int = 120
    bg_var_threshold: float = 25.0
    bg_learning_rate: float = -1.0       # -1 = automatic (OpenCV default)

    def __post_init__(self) -> None:
        self.method = SegmentationMethod(self.method)
        self.channel = Channel(self.channel)
        self.hsv_lower = tuple(int(v) for v in self.hsv_lower)
        self.hsv_upper = tuple(int(v) for v in self.hsv_upper)

    def validate(self) -> None:
        if self.blur_kernel not in (0, 1) and (self.blur_kernel < 3 or self.blur_kernel % 2 == 0):
            raise ValueError("blur_kernel must be 0, 1 or an odd integer >= 3.")
        if self.adaptive_block_size < 3 or self.adaptive_block_size % 2 == 0:
            raise ValueError("adaptive_block_size must be an odd integer >= 3.")
        if self.morph_kernel < 0 or self.open_iterations < 0 or self.close_iterations < 0:
            raise ValueError("Morphology parameters must be non-negative.")
        if not 0 <= self.fixed_threshold <= 255:
            raise ValueError("fixed_threshold must be within 0-255.")
        if self.min_contour_area_px < 0 or self.min_contrast < 0:
            raise ValueError("min_contour_area_px and min_contrast must be non-negative.")
        if not 0 <= self.min_candidate_contrast < 1:
            raise ValueError("min_candidate_contrast must be within [0, 1).")
        if not 0 < self.max_foreground_fraction <= 1:
            raise ValueError("max_foreground_fraction must be in (0, 1].")
        if len(self.hsv_lower) != 3 or len(self.hsv_upper) != 3:
            raise ValueError("HSV bounds must have three components.")
        if not (0 <= self.hsv_lower[0] <= 180 and 0 <= self.hsv_upper[0] <= 180):
            raise ValueError("HSV hue bounds must be within 0-180 (OpenCV convention).")
        if self.bg_history < 1 or self.bg_var_threshold <= 0:
            raise ValueError("Background-subtraction parameters must be positive.")

    def to_dict(self) -> dict:
        d = asdict(self)
        d["method"] = self.method.value
        d["channel"] = self.channel.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "SegmentationConfig":
        allowed = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in allowed})


@dataclass
class SegmentationResult:
    mask: np.ndarray                 # uint8, 0 or 255
    intensity: np.ndarray            # blurred single-channel image used for thresholding
    threshold: float | None          # global threshold used (None for local/colour methods)
    dynamic_range: float
    rejected_reason: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def foreground_fraction(self) -> float:
        return float(np.count_nonzero(self.mask)) / self.mask.size


def extract_channel(frame_bgr: np.ndarray, channel: Channel) -> np.ndarray:
    if frame_bgr.ndim == 2:
        return frame_bgr
    if channel is Channel.MAX:
        return frame_bgr.max(axis=2)
    if channel is Channel.GRAY:
        return cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    return frame_bgr[:, :, {Channel.BLUE: 0, Channel.GREEN: 1, Channel.RED: 2}[channel]]


class Segmenter:
    """Stateful segmenter (state is only used by background subtraction)."""

    def __init__(self, config: SegmentationConfig | None = None) -> None:
        self.config = config or SegmentationConfig()
        self.config.validate()
        k = self.config.morph_kernel
        self._kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)) if k > 1 else None
        self._bg: cv2.BackgroundSubtractor | None = None
        self.reset()

    def reset(self) -> None:
        if self.config.method is SegmentationMethod.BACKGROUND_SUBTRACTION:
            self._bg = cv2.createBackgroundSubtractorMOG2(
                history=self.config.bg_history,
                varThreshold=self.config.bg_var_threshold,
                detectShadows=False,
            )

    def _blur(self, img: np.ndarray) -> np.ndarray:
        k = self.config.blur_kernel
        return cv2.GaussianBlur(img, (k, k), 0) if k > 1 else img

    def segment(self, frame_bgr: np.ndarray) -> SegmentationResult:
        cfg = self.config
        if frame_bgr is None or frame_bgr.size == 0:
            raise ValueError("Empty frame.")
        if frame_bgr.dtype != np.uint8:
            raise ValueError(f"Expected an 8-bit frame, got {frame_bgr.dtype}.")
        blurred_bgr = self._blur(frame_bgr)
        intensity = extract_channel(blurred_bgr, cfg.channel)
        lo, hi = (float(v) for v in cv2.minMaxLoc(intensity)[:2])
        dynamic_range = hi - lo
        empty = np.zeros(intensity.shape, np.uint8)

        if cfg.method is SegmentationMethod.BACKGROUND_SUBTRACTION:
            # The model must keep learning even on frames where nothing is detected.
            mask = self._bg.apply(blurred_bgr, learningRate=cfg.bg_learning_rate)
            mask = np.where(mask > 0, 255, 0).astype(np.uint8)
            threshold = None
        elif dynamic_range < cfg.min_contrast:
            return SegmentationResult(
                empty, intensity, None, dynamic_range,
                rejected_reason=f"insufficient contrast ({dynamic_range:.1f} < {cfg.min_contrast:.1f})")
        elif cfg.method is SegmentationMethod.OTSU:
            otsu, _ = cv2.threshold(intensity, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
            threshold = float(np.clip(otsu + cfg.threshold_offset, 0, 255))
            _, mask = cv2.threshold(intensity, threshold, 255, cv2.THRESH_BINARY)
        elif cfg.method is SegmentationMethod.FIXED:
            threshold = float(cfg.fixed_threshold)
            _, mask = cv2.threshold(intensity, threshold, 255, cv2.THRESH_BINARY)
        elif cfg.method is SegmentationMethod.ADAPTIVE:
            threshold = None
            mask = cv2.adaptiveThreshold(
                intensity, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY,
                cfg.adaptive_block_size, cfg.adaptive_c)
        else:  # HSV
            threshold = None
            hsv = cv2.cvtColor(blurred_bgr, cv2.COLOR_BGR2HSV)
            lo_b, hi_b = np.array(cfg.hsv_lower), np.array(cfg.hsv_upper)
            if lo_b[0] <= hi_b[0]:
                mask = cv2.inRange(hsv, lo_b, hi_b)
            else:  # hue range wraps around red (e.g. 170 -> 10)
                mask = cv2.bitwise_or(
                    cv2.inRange(hsv, lo_b, np.array([180, hi_b[1], hi_b[2]])),
                    cv2.inRange(hsv, np.array([0, lo_b[1], lo_b[2]]), hi_b))

        if self._kernel is not None:
            if cfg.open_iterations:
                mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self._kernel, iterations=cfg.open_iterations)
            if cfg.close_iterations:
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self._kernel, iterations=cfg.close_iterations)

        result = SegmentationResult(mask, intensity, threshold, dynamic_range)
        if result.foreground_fraction > cfg.max_foreground_fraction:
            result.rejected_reason = (
                f"foreground covers {result.foreground_fraction:.0%} of the image "
                f"(> {cfg.max_foreground_fraction:.0%}); segmentation not meaningful")
            result.mask = empty
        return result


def find_contours(mask: np.ndarray, min_area_px: float) -> tuple[list[np.ndarray], float]:
    """External contours with polygon area >= ``min_area_px``, largest first.

    Returns the contours and the total foreground pixel count of the mask.
    """
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    kept = [c for c in contours if len(c) >= 3 and cv2.contourArea(c) >= min_area_px]
    kept.sort(key=cv2.contourArea, reverse=True)
    return kept, float(np.count_nonzero(mask))
