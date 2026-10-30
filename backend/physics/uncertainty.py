"""First-order measurement-uncertainty propagation for image-derived flame quantities.

Conventions
-----------
* Every uncertainty is a one-standard-deviation (1-sigma) value.
* Propagation is linearised (first-order Taylor expansion). It is accurate when
  the relative uncertainty is small (roughly < 10 %); for larger relative
  uncertainties the non-linear terms of e.g. ``r**3`` become significant and the
  reported value should be treated as an approximation.
* Uncertainty is split into two components because they behave differently
  over time:

  ``random``
      Frame-to-frame independent error, e.g. boundary localisation noise in a
      single image. It averages down when many frames are combined and it is
      the component that drives scatter in time derivatives.
  ``systematic``
      Error that is fully correlated across all frames of one video, e.g. the
      pixel-to-millimetre calibration scale. It does not average down and it
      scales every derived length by the same unknown factor.

* Sources that are *not* modelled here (and therefore not contained in any
  reported uncertainty): segmentation-threshold bias, optical depth / line-of-
  sight integration effects, lens distortion that was not corrected, motion
  blur, camera exposure/saturation effects and the deviation of a real flame
  from the sphericity assumed by equivalent-volume estimates.
  See SCIENTIFIC_ASSUMPTIONS.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class UncertainQuantity:
    """A value with separated random and systematic 1-sigma uncertainty."""

    value: float
    random: float = 0.0
    systematic: float = 0.0

    @property
    def total(self) -> float:
        """Random and systematic components combined in quadrature."""
        return math.hypot(self.random, self.systematic)

    @property
    def relative_total(self) -> float:
        """Total uncertainty divided by ``|value|`` (``nan`` for zero values)."""
        return self.total / abs(self.value) if self.value else math.nan


def calibration_scale(
    known_length_mm: float,
    known_length_sigma_mm: float,
    measured_length_px: float,
    measured_length_sigma_px: float,
) -> tuple[float, float]:
    """Return ``(mm_per_px, sigma_mm_per_px)`` for a reference-length calibration.

    ``s = L / p`` so ``sigma_s / s = sqrt((sigma_L / L)**2 + (sigma_p / p)**2)``.
    """
    if known_length_mm <= 0 or measured_length_px <= 0:
        raise ValueError("Calibration lengths must be positive.")
    if known_length_sigma_mm < 0 or measured_length_sigma_px < 0:
        raise ValueError("Calibration uncertainties must be non-negative.")
    scale = known_length_mm / measured_length_px
    rel = math.hypot(
        known_length_sigma_mm / known_length_mm,
        measured_length_sigma_px / measured_length_px,
    )
    return scale, scale * rel


def radius_sigma_from_boundary(perimeter_px: float, radius_px: float, edge_sigma_px: float) -> float:
    """Radius uncertainty (px) of an area-equivalent radius from boundary localisation error.

    A boundary displaced outward by ``delta`` changes the enclosed area by
    ``dA ~= P * delta``. With ``r = sqrt(A / pi)``, ``dr = dA / (2 pi r)``, hence
    ``sigma_r = P * sigma_edge / (2 pi r)``. The displacement is conservatively
    assumed to be coherent around the whole boundary (a threshold shift moves
    the entire edge), so it is not averaged over boundary points. For a circle
    ``P = 2 pi r`` and the result reduces to ``sigma_edge``.
    """
    if radius_px <= 0:
        return math.nan
    return perimeter_px * edge_sigma_px / (2.0 * math.pi * radius_px)


def circle_area_sigma(radius: float, radius_sigma: float) -> float:
    """``sigma_A = 2 pi r sigma_r`` for ``A = pi r**2``."""
    return 2.0 * math.pi * abs(radius) * radius_sigma


def sphere_volume_sigma(radius: float, radius_sigma: float) -> float:
    """``sigma_V = 4 pi r**2 sigma_r`` for ``V = (4/3) pi r**3``."""
    return 4.0 * math.pi * radius * radius * radius_sigma


def px_to_physical(
    value_px: float,
    sigma_px_random: float,
    mm_per_px: float,
    mm_per_px_sigma: float,
    length_power: int = 1,
) -> UncertainQuantity:
    """Convert a pixel-domain quantity of dimension ``length**k`` to millimetre units.

    ``Q_mm = Q_px * s**k``.
    * random component: ``sigma_Qpx * s**k`` (pixel noise, independent per frame)
    * systematic component: ``k * |Q_mm| * sigma_s / s`` (calibration, correlated)
    """
    factor = mm_per_px**length_power
    value = value_px * factor
    random = abs(sigma_px_random) * factor if math.isfinite(sigma_px_random) else math.nan
    systematic = abs(length_power) * abs(value) * (mm_per_px_sigma / mm_per_px)
    return UncertainQuantity(value=value, random=random, systematic=systematic)
