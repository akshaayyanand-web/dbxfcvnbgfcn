"""Geometric measurement of a single segmented flame contour (pixel units).

Area is the number of pixels inside the filled contour, not the polygon area
through boundary-pixel centres: the polygon area of a digitised disc of radius
``R`` is approximately ``pi (R - 0.5)**2``, which would bias the equivalent
radius low by about half a pixel. The equivalent radius ``sqrt(A / pi)`` is the
primary size measure because it uses every boundary pixel; the minimum
enclosing circle is reported as well but is sensitive to single outlying
boundary points.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

from backend.physics.physics_engine import circularity, eccentricity, equivalent_radius_from_area

# Width of the annulus outside the contour used as the local background reference.
_BACKGROUND_RING_PX = 5


@dataclass
class ContourGeometry:
    area_px2: float
    perimeter_px: float
    centroid_x_px: float
    centroid_y_px: float
    bbox: tuple[int, int, int, int]
    enclosing_center_x_px: float
    enclosing_center_y_px: float
    enclosing_radius_px: float
    equivalent_radius_px: float
    circularity: float
    ellipse_major_px: float | None
    ellipse_minor_px: float | None
    ellipse_angle_deg: float | None
    eccentricity: float | None
    boundary_roughness: float
    touches_border: bool
    contrast: float
    contour: np.ndarray

    @property
    def equivalent_diameter_px(self) -> float:
        return 2.0 * self.equivalent_radius_px


def measure_contour(contour: np.ndarray, intensity: np.ndarray) -> ContourGeometry:
    """Compute all pixel-domain geometry for ``contour`` on the image ``intensity``."""
    h, w = intensity.shape[:2]
    x, y, bw, bh = cv2.boundingRect(contour)

    # Local region of interest with a margin for the background annulus.
    m = _BACKGROUND_RING_PX + 1
    x0, y0 = max(x - m, 0), max(y - m, 0)
    x1, y1 = min(x + bw + m, w), min(y + bh + m, h)
    roi_mask = np.zeros((y1 - y0, x1 - x0), np.uint8)
    cv2.drawContours(roi_mask, [contour - np.array([x0, y0])], -1, 255, thickness=cv2.FILLED)
    area = float(np.count_nonzero(roi_mask))

    moments = cv2.moments(roi_mask, binaryImage=True)
    if moments["m00"] > 0:
        cx = moments["m10"] / moments["m00"] + x0
        cy = moments["m01"] / moments["m00"] + y0
    else:
        cx, cy = x + bw / 2.0, y + bh / 2.0

    perimeter = float(cv2.arcLength(contour, closed=True))
    (ecx, ecy), er = cv2.minEnclosingCircle(contour)
    r_eq = equivalent_radius_from_area(area)

    major = minor = angle = ecc = None
    if len(contour) >= 5:
        (_, _), (ax1, ax2), angle = cv2.fitEllipse(contour)
        major, minor = float(max(ax1, ax2)), float(min(ax1, ax2))
        ecc = eccentricity(major, minor)
        angle = float(angle)

    pts = contour.reshape(-1, 2).astype(float)
    radial = np.hypot(pts[:, 0] - cx, pts[:, 1] - cy)
    roughness = float(np.std(radial) / np.mean(radial)) if radial.size and np.mean(radial) > 0 else math.nan

    touches = bool(x <= 0 or y <= 0 or x + bw >= w or y + bh >= h)

    roi_int = intensity[y0:y1, x0:x1]
    ring = cv2.dilate(roi_mask, np.ones((3, 3), np.uint8), iterations=_BACKGROUND_RING_PX)
    ring = cv2.subtract(ring, roi_mask)
    inside = roi_int[roi_mask > 0]
    outside = roi_int[ring > 0]
    contrast = (
        float(np.clip((inside.mean() - outside.mean()) / 255.0, 0.0, 1.0))
        if inside.size and outside.size else 0.0
    )

    return ContourGeometry(
        area_px2=area,
        perimeter_px=perimeter,
        centroid_x_px=float(cx),
        centroid_y_px=float(cy),
        bbox=(int(x), int(y), int(bw), int(bh)),
        enclosing_center_x_px=float(ecx),
        enclosing_center_y_px=float(ecy),
        enclosing_radius_px=float(er),
        equivalent_radius_px=r_eq,
        circularity=circularity(area, perimeter),
        ellipse_major_px=major,
        ellipse_minor_px=minor,
        ellipse_angle_deg=angle,
        eccentricity=ecc,
        boundary_roughness=roughness,
        touches_border=touches,
        contrast=contrast,
        contour=contour,
    )


def simplify_contour(contour: np.ndarray, max_points: int = 72) -> list[list[float]]:
    """Down-sample a contour to at most ``max_points`` vertices for telemetry/overlays."""
    pts = contour.reshape(-1, 2)
    if len(pts) > max_points:
        idx = np.linspace(0, len(pts), max_points, endpoint=False).astype(int)
        pts = pts[idx]
    return pts.astype(float).tolist()
