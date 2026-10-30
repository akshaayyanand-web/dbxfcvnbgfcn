"""Physics calculation engine: geometry, timestamp-aware kinematics and extinction estimation.

Quantity classes (see DATA_DICTIONARY.md) used throughout the platform:

* ``image_derived``  measured directly from pixels of a 2-D image (area, perimeter, ...)
* ``calculated``     computed from image-derived values with a stated model
                     (mm conversion, equivalent spherical volume, derivatives)
* ``predicted``      produced by a machine-learning model
* ``simulated``      produced by a synthetic generator or numerical simulation

Nothing in this module is a direct three-dimensional measurement. In particular
the equivalent spherical volume ``V_eq = 4/3 pi r**3`` is a *model* that assumes a
spherically symmetric flame observed in projection.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

# --------------------------------------------------------------------------- geometry


def circle_area(radius: float) -> float:
    """``A = pi r**2``."""
    return math.pi * radius * radius


def equivalent_radius_from_area(area: float) -> float:
    """Radius of the circle with the same area: ``r = sqrt(A / pi)``."""
    if area < 0:
        raise ValueError("Area must be non-negative.")
    return math.sqrt(area / math.pi)


def equivalent_spherical_volume(radius: float) -> float:
    """``V_eq = (4/3) pi r**3`` -- an estimate that assumes spherical symmetry."""
    return 4.0 / 3.0 * math.pi * radius**3


def circularity(area: float, perimeter: float) -> float:
    """Isoperimetric quotient ``4 pi A / P**2`` (1 for a perfect circle).

    Note: perimeters measured on pixel grids are biased high, so digitised
    circles typically score ~0.85-0.95 rather than exactly 1.
    """
    if perimeter <= 0:
        return math.nan
    return 4.0 * math.pi * area / (perimeter * perimeter)


def eccentricity(major_axis: float, minor_axis: float) -> float:
    """Ellipse eccentricity ``sqrt(1 - (b/a)**2)`` with ``a >= b`` (0 for a circle)."""
    a, b = max(major_axis, minor_axis), min(major_axis, minor_axis)
    if a <= 0:
        return math.nan
    return math.sqrt(max(0.0, 1.0 - (b / a) ** 2))


# ------------------------------------------------------------------------- kinematics


@dataclass(frozen=True)
class DerivativeConfig:
    """Settings for timestamp-aware local-polynomial differentiation.

    ``window`` points (odd) are fitted with a polynomial of order ``polyorder``
    by least squares in *actual time*, so variable frame intervals are handled
    exactly. This is the non-uniform generalisation of a Savitzky-Golay filter.
    A segment boundary is placed wherever the gap between consecutive valid
    samples exceeds ``max_gap_factor`` times the median sample interval; fits
    never span such a gap and no value is interpolated into missing frames.
    """

    window: int = 7
    polyorder: int = 2
    max_gap_factor: float = 3.0

    def validate(self) -> None:
        if self.window < 3 or self.window % 2 == 0:
            raise ValueError("Derivative window must be an odd integer >= 3.")
        if not 1 <= self.polyorder < self.window:
            raise ValueError("polyorder must satisfy 1 <= polyorder < window.")
        if self.max_gap_factor <= 1.0:
            raise ValueError("max_gap_factor must be > 1.")


@dataclass
class KinematicsResult:
    """Smoothed value and first/second time derivatives with 1-sigma random uncertainty.

    All arrays align with the input samples; entries are ``nan`` where the
    input was invalid or where too few neighbouring samples were available.
    """

    smoothed: np.ndarray
    smoothed_sigma: np.ndarray
    first_derivative: np.ndarray
    first_derivative_sigma: np.ndarray
    second_derivative: np.ndarray
    second_derivative_sigma: np.ndarray
    segment_id: np.ndarray
    notes: list[str] = field(default_factory=list)


def split_segments(t: np.ndarray, valid: np.ndarray, max_gap_factor: float) -> np.ndarray:
    """Assign a segment id to every valid sample (``-1`` for invalid samples)."""
    seg = np.full(t.shape, -1, dtype=int)
    idx = np.flatnonzero(valid)
    if idx.size == 0:
        return seg
    if idx.size == 1:
        seg[idx] = 0
        return seg
    dt = np.diff(t[idx])
    positive = dt[dt > 0]
    median_dt = float(np.median(positive)) if positive.size else math.inf
    breaks = (dt <= 0) | (dt > max_gap_factor * median_dt)
    seg[idx] = np.concatenate(([0], np.cumsum(breaks)))
    return seg


def _local_poly_weights(tau: np.ndarray, polyorder: int) -> np.ndarray:
    """Rows of the least-squares hat matrix: coefficient ``k`` = ``weights[k] @ y``."""
    design = np.vander(tau, polyorder + 1, increasing=True)
    return np.linalg.pinv(design)


def local_polynomial_kinematics(
    t: np.ndarray,
    y: np.ndarray,
    sigma_y: np.ndarray | float,
    config: DerivativeConfig | None = None,
) -> KinematicsResult:
    """Smoothed value, ``dy/dt`` and ``d2y/dt2`` from irregularly timed samples.

    Each estimate is a linear combination ``sum_j w_j y_j`` of the samples in its
    window, so its random uncertainty is propagated exactly as
    ``sqrt(sum_j w_j**2 sigma_j**2)`` assuming independent sample errors.
    At segment edges the window is shifted (not shrunk) to stay inside the
    segment; segments shorter than the window use all of their samples if that
    is at least ``polyorder + 1`` samples, otherwise the outputs are ``nan``.
    The second derivative requires ``polyorder >= 2``.
    """
    config = config or DerivativeConfig()
    config.validate()
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    sig = np.broadcast_to(np.asarray(sigma_y, dtype=float), y.shape).astype(float)
    if t.shape != y.shape:
        raise ValueError("t and y must have the same shape.")

    n = y.size
    out = {k: np.full(n, np.nan) for k in ("s", "ss", "d1", "d1s", "d2", "d2s")}
    notes: list[str] = []
    valid = np.isfinite(t) & np.isfinite(y)
    sig_valid = np.where(np.isfinite(sig), sig, 0.0)
    if np.any(valid & ~np.isfinite(sig)):
        notes.append("Some samples had no uncertainty estimate; they contribute zero variance.")
    seg = split_segments(t, valid, config.max_gap_factor)

    for s_id in np.unique(seg[seg >= 0]):
        idx = np.flatnonzero(seg == s_id)
        m = idx.size
        win = min(config.window, m)
        order = min(config.polyorder, win - 1)
        if m < config.polyorder + 1 or win < 2:
            notes.append(f"Segment {s_id} has {m} sample(s); too short for differentiation.")
            continue
        if order < config.polyorder:
            notes.append(f"Segment {s_id} has {m} samples; polynomial order reduced to {order}.")
        ts, ys, ss = t[idx], y[idx], sig_valid[idx]
        h = float(np.median(np.diff(ts))) if m > 1 else 1.0
        half = win // 2
        for local_i in range(m):
            start = min(max(local_i - half, 0), m - win)
            sl = slice(start, start + win)
            tau = (ts[sl] - ts[local_i]) / h
            w = _local_poly_weights(tau, order)
            gi = idx[local_i]
            var_w = ss[sl] ** 2
            out["s"][gi] = w[0] @ ys[sl]
            out["ss"][gi] = math.sqrt(float((w[0] ** 2) @ var_w))
            if order >= 1:
                out["d1"][gi] = (w[1] @ ys[sl]) / h
                out["d1s"][gi] = math.sqrt(float((w[1] ** 2) @ var_w)) / h
            if order >= 2:
                out["d2"][gi] = 2.0 * (w[2] @ ys[sl]) / h**2
                out["d2s"][gi] = 2.0 * math.sqrt(float((w[2] ** 2) @ var_w)) / h**2

    return KinematicsResult(
        smoothed=out["s"],
        smoothed_sigma=out["ss"],
        first_derivative=out["d1"],
        first_derivative_sigma=out["d1s"],
        second_derivative=out["d2"],
        second_derivative_sigma=out["d2s"],
        segment_id=seg,
        notes=notes,
    )


def finite_difference_derivatives(t: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Unsmoothed, timestamp-aware second-order finite differences (``numpy.gradient``).

    Provided as a transparent reference for the smoothed estimates. Requires
    finite, strictly increasing ``t`` and finite ``y`` (no gaps).
    """
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    if t.size < 3:
        raise ValueError("At least three samples are required.")
    if not (np.all(np.isfinite(t)) and np.all(np.isfinite(y))):
        raise ValueError("finite_difference_derivatives does not accept missing samples.")
    if np.any(np.diff(t) <= 0):
        raise ValueError("Timestamps must be strictly increasing.")
    d1 = np.gradient(y, t, edge_order=2)
    d2 = np.gradient(d1, t, edge_order=2)
    return d1, d2


# ------------------------------------------------------------------------- extinction


@dataclass(frozen=True)
class ExtinctionEstimate:
    """Estimate of when a visible flame disappeared from the recording.

    ``status`` is one of:
    * ``observed`` -- the flame was detected, then not detected for at least
      ``min_consecutive_missing`` sampled frames until the end of the video.
    * ``flame_present_at_end`` -- the flame was still detected in the final frames.
    * ``insufficient_trailing_frames`` -- the flame vanished but too few frames
      followed to distinguish extinction from a temporary detection failure.
    * ``never_detected`` -- no frame contained an accepted detection.

    ``time_s`` is the midpoint between the last detected and the first
    subsequently missing frame; ``uncertainty_s`` is half that interval
    (temporal resolution only). This is *visible-emission* extinction as seen by
    this camera; it is not a measurement of chemical extinction and depends on
    camera sensitivity and segmentation threshold.
    """

    status: str
    time_s: float | None
    uncertainty_s: float | None
    last_detected_time_s: float | None
    first_missing_time_s: float | None
    message: str


def estimate_extinction(
    t: np.ndarray, detected: np.ndarray, min_consecutive_missing: int = 5
) -> ExtinctionEstimate:
    """Estimate visible-flame extinction from a detection time series."""
    t = np.asarray(t, dtype=float)
    detected = np.asarray(detected, dtype=bool)
    if t.shape != detected.shape:
        raise ValueError("t and detected must have the same shape.")
    hits = np.flatnonzero(detected)
    if hits.size == 0:
        return ExtinctionEstimate("never_detected", None, None, None, None, "No accepted flame detection.")
    last = int(hits[-1])
    trailing = t.size - 1 - last
    t_last = float(t[last])
    if trailing == 0:
        return ExtinctionEstimate(
            "flame_present_at_end", None, None, t_last, None,
            "Flame still detected in the final analysed frame; extinction not observed.",
        )
    t_first_missing = float(t[last + 1])
    if trailing < min_consecutive_missing:
        return ExtinctionEstimate(
            "insufficient_trailing_frames", None, None, t_last, t_first_missing,
            f"Only {trailing} non-detected frame(s) after the last detection "
            f"(< {min_consecutive_missing}); cannot distinguish extinction from detection loss.",
        )
    mid = 0.5 * (t_last + t_first_missing)
    return ExtinctionEstimate(
        "observed", mid, 0.5 * (t_first_missing - t_last), t_last, t_first_missing,
        f"Flame not detected in the final {trailing} analysed frames.",
    )
