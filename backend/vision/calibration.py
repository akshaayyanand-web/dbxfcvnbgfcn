"""Pixel-to-millimetre calibration and optional lens-distortion correction.

A calibration is valid only for the exact camera, lens, zoom/focus setting,
image resolution and object distance at which the reference length was
imaged. It is *not* transferable between experimental configurations; the
``camera_id``/``lens``/``configuration`` fields exist so that this can be
checked rather than assumed.

The reference object must lie at the same distance from the camera as the
flame plane of interest. For a spherical flame centred on a burner, measuring
a reference of known size at the burner (e.g. the burner diameter) satisfies
this; a reference elsewhere introduces a perspective (magnification) error
that is not included in the reported uncertainty.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

import cv2
import numpy as np

from backend.physics.uncertainty import calibration_scale


class CalibrationError(ValueError):
    """Raised for physically invalid or unusable calibration input."""


# A reference shorter than this many pixels has >= 5 % relative error at 1 px precision.
MIN_RECOMMENDED_REFERENCE_PX = 20.0


@dataclass
class Calibration:
    """Manual reference-length calibration: ``mm_per_px = known_length_mm / measured_length_px``."""

    known_length_mm: float
    measured_length_px: float
    measured_length_sigma_px: float = 1.0
    known_length_sigma_mm: float = 0.0
    image_width: int | None = None
    image_height: int | None = None
    camera_id: str | None = None
    lens: str | None = None
    configuration: str | None = None
    method: str = "manual_reference_length"
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        for name in ("known_length_mm", "measured_length_px", "measured_length_sigma_px", "known_length_sigma_mm"):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise CalibrationError(f"{name} must be a finite number.")
        if self.known_length_mm <= 0 or self.measured_length_px <= 0:
            raise CalibrationError("Reference lengths must be positive.")
        if self.measured_length_sigma_px < 0 or self.known_length_sigma_mm < 0:
            raise CalibrationError("Calibration uncertainties must be non-negative.")

    @classmethod
    def from_points(
        cls,
        p1: tuple[float, float],
        p2: tuple[float, float],
        known_length_mm: float,
        point_sigma_px: float = 0.5,
        **kwargs,
    ) -> "Calibration":
        """Build a calibration from two image points spanning a known length.

        Each endpoint has independent localisation uncertainty ``point_sigma_px``
        along the measurement direction, so the length uncertainty is
        ``sqrt(2) * point_sigma_px``.
        """
        length = float(math.dist(p1, p2))
        if length <= 0:
            raise CalibrationError("Calibration points must be distinct.")
        return cls(
            known_length_mm=known_length_mm,
            measured_length_px=length,
            measured_length_sigma_px=math.sqrt(2.0) * point_sigma_px,
            **kwargs,
        )

    @property
    def mm_per_px(self) -> float:
        return calibration_scale(
            self.known_length_mm, self.known_length_sigma_mm,
            self.measured_length_px, self.measured_length_sigma_px)[0]

    @property
    def mm_per_px_sigma(self) -> float:
        return calibration_scale(
            self.known_length_mm, self.known_length_sigma_mm,
            self.measured_length_px, self.measured_length_sigma_px)[1]

    @property
    def relative_uncertainty(self) -> float:
        return self.mm_per_px_sigma / self.mm_per_px

    def warnings(self) -> list[str]:
        out = []
        if self.measured_length_px < MIN_RECOMMENDED_REFERENCE_PX:
            out.append(
                f"Reference spans only {self.measured_length_px:.1f} px "
                f"(< {MIN_RECOMMENDED_REFERENCE_PX:.0f} px recommended); scale uncertainty is "
                f"{self.relative_uncertainty:.1%}.")
        if self.measured_length_sigma_px == 0 and self.known_length_sigma_mm == 0:
            out.append("Calibration uncertainty is zero; scale error will be omitted from all results.")
        return out

    def check_compatible(self, width: int, height: int) -> list[str]:
        """Return problems that make this calibration unsuitable for a video of this size."""
        if self.image_width is None or self.image_height is None:
            return ["Calibration has no recorded image size; resolution compatibility not verified."]
        if (self.image_width, self.image_height) != (width, height):
            raise CalibrationError(
                f"Calibration was made at {self.image_width}x{self.image_height} px but the video is "
                f"{width}x{height} px. Recalibrate for this camera configuration.")
        return []

    def to_dict(self) -> dict:
        d = asdict(self)
        d.update(mm_per_px=self.mm_per_px, mm_per_px_sigma=self.mm_per_px_sigma)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Calibration":
        allowed = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in allowed})


@dataclass
class DistortionCorrection:
    """Optional pinhole-camera undistortion using OpenCV intrinsics.

    ``camera_matrix`` is the 3x3 intrinsic matrix and ``dist_coeffs`` the
    OpenCV distortion vector (k1, k2, p1, p2[, k3...]) obtained from a prior
    chessboard calibration of the same camera configuration.
    """

    camera_matrix: list[list[float]]
    dist_coeffs: list[float]
    _maps: tuple | None = field(default=None, init=False, repr=False)
    _size: tuple[int, int] | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        k = np.asarray(self.camera_matrix, dtype=float)
        if k.shape != (3, 3) or not np.all(np.isfinite(k)):
            raise CalibrationError("camera_matrix must be a finite 3x3 matrix.")
        d = np.asarray(self.dist_coeffs, dtype=float).ravel()
        if d.size not in (4, 5, 8, 12, 14) or not np.all(np.isfinite(d)):
            raise CalibrationError("dist_coeffs must have 4, 5, 8, 12 or 14 finite values.")

    def apply(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        if self._maps is None or self._size != (w, h):
            k = np.asarray(self.camera_matrix, dtype=float)
            d = np.asarray(self.dist_coeffs, dtype=float)
            self._maps = cv2.initUndistortRectifyMap(k, d, None, k, (w, h), cv2.CV_16SC2)
            self._size = (w, h)
        return cv2.remap(frame, self._maps[0], self._maps[1], cv2.INTER_LINEAR)

    def to_dict(self) -> dict:
        return {"camera_matrix": self.camera_matrix, "dist_coeffs": self.dist_coeffs}


@dataclass
class DiskMeasurement:
    """Result of measuring a dark circular reference object (e.g. a burner sphere) in an image."""

    diameter_px: float
    diameter_sigma_px: float
    center_px: tuple[float, float]
    sector_radii_px: list[float]
    method: str = "radial half-depth edge, per angular sector"


def measure_dark_disk(
    image: np.ndarray,
    center_guess: tuple[float, float],
    max_radius_px: float,
    excluded_angles_deg: list[tuple[float, float]] | None = None,
    n_sectors: int = 24,
    refine_center: bool = True,
) -> DiskMeasurement:
    """Measure the diameter of a dark disk silhouetted against a brighter surround.

    For each angular sector (skipping ``excluded_angles_deg``, e.g. the burner's
    supply tube; 0 deg = +x, angles increase towards +y), the radial intensity
    profile is averaged and the edge is taken where it first rises past the
    midpoint between the inner dark level (median inside 30 % of
    ``max_radius_px``) and the outer level (median of the outer 30 %). The
    diameter is twice the median sector radius. Its 1-sigma uncertainty is
    ``2 * 1.4826 * MAD / sqrt(n)`` of the sector radii, plus 1 px for edge
    localisation, combined in quadrature. With ``refine_center`` the centre is
    re-estimated once from opposing sector edges.

    Limitations: a soft or partially filled silhouette (emission in front of the
    object) biases the half-depth edge. Report the reference as an *in-image*
    calibration with this method named.
    """
    img = np.asarray(image, dtype=np.float32)
    if img.ndim == 3:
        img = img.max(axis=2)
    excluded = excluded_angles_deg or []

    def is_excluded(a: float) -> bool:
        for lo, hi in excluded:
            lo, hi = lo % 360, hi % 360
            if (lo <= hi and lo <= a <= hi) or (lo > hi and (a >= lo or a <= hi)):
                return True
        return False

    def sector_edges(cx: float, cy: float) -> dict[float, float]:
        h, w = img.shape
        yy, xx = np.mgrid[0:h, 0:w]
        dx, dy = xx - cx, yy - cy
        rr = np.hypot(dx, dy)
        ang = (np.degrees(np.arctan2(dy, dx)) + 360) % 360
        near = rr <= max_radius_px
        edges = {}
        width = 360.0 / n_sectors
        nbins = int(max_radius_px)
        for k in range(n_sectors):
            a0 = k * width
            mid = a0 + width / 2
            if is_excluded(mid):
                continue
            sel = near & (ang >= a0) & (ang < a0 + width)
            if sel.sum() < 50:
                continue
            r = rr[sel]
            v = img[sel]
            bins = np.clip(r.astype(int), 0, nbins - 1)
            prof = np.bincount(bins, weights=v, minlength=nbins) / np.maximum(np.bincount(bins, minlength=nbins), 1)
            prof = np.convolve(prof, np.ones(5) / 5, mode="same")
            inner = np.median(prof[: max(3, int(0.3 * nbins))])
            outer = np.median(prof[int(0.7 * nbins):])
            if outer - inner <= 0:
                continue
            half = inner + 0.5 * (outer - inner)
            above = np.flatnonzero(prof[int(0.05 * nbins):] > half)
            if above.size:
                edges[mid] = float(above[0] + int(0.05 * nbins))
        return edges

    cx, cy = center_guess
    edges = sector_edges(cx, cy)
    if refine_center and len(edges) >= 6:
        pts = np.array([[cx + r * np.cos(np.radians(a)), cy + r * np.sin(np.radians(a))] for a, r in edges.items()])
        # Algebraic circle fit (Kasa) to the edge points.
        A = np.c_[2 * pts[:, 0], 2 * pts[:, 1], np.ones(len(pts))]
        b = (pts ** 2).sum(axis=1)
        sol, *_ = np.linalg.lstsq(A, b, rcond=None)
        cx, cy = float(sol[0]), float(sol[1])
        edges = sector_edges(cx, cy)
    if len(edges) < 4:
        raise CalibrationError("Too few usable sectors to measure the disk; check the centre guess and radius.")
    radii = np.array(list(edges.values()))
    med = float(np.median(radii))
    mad = float(np.median(np.abs(radii - med))) * 1.4826
    sigma_d = float(np.hypot(2 * mad / np.sqrt(len(radii)), 1.0))
    return DiskMeasurement(2 * med, sigma_d, (cx, cy), radii.tolist())
