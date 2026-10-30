"""Scientific validation checks applied to measurement series.

Each check returns ``ValidationIssue`` objects instead of raising, so that an
analysis can be completed and its problems reported side by side with the data.
Thresholds are deliberately conservative and configurable; a warning is a
prompt for human review, not an automatic rejection.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    severity: str  # "info" | "warning" | "error"
    message: str
    frame_index: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def validate_timestamps(t: np.ndarray, vfr_tolerance: float = 0.05) -> list[ValidationIssue]:
    """Check that timestamps are finite and strictly increasing; report variable frame rate."""
    t = np.asarray(t, dtype=float)
    issues: list[ValidationIssue] = []
    if t.size == 0:
        return [ValidationIssue("timestamps_empty", "error", "No timestamps available.")]
    if not np.all(np.isfinite(t)):
        issues.append(ValidationIssue("timestamps_non_finite", "error", "Non-finite timestamps present."))
        return issues
    if t.size < 2:
        return issues
    dt = np.diff(t)
    bad = np.flatnonzero(dt <= 0)
    for i in bad[:20]:
        issues.append(ValidationIssue(
            "timestamps_not_increasing", "error",
            f"Timestamp does not increase between samples {i} and {i + 1} "
            f"({t[i]:.6f} s -> {t[i + 1]:.6f} s).", int(i + 1)))
    pos = dt[dt > 0]
    if pos.size >= 2:
        med = float(np.median(pos))
        spread = float(np.max(np.abs(pos - med)) / med)
        if spread > vfr_tolerance:
            issues.append(ValidationIssue(
                "variable_frame_interval", "info",
                f"Frame intervals vary by up to {spread:.1%} of the median ({med * 1e3:.3f} ms); "
                "per-frame timestamps are used for all time derivatives."))
    return issues


def check_radius_bounds(
    radius_px: np.ndarray, frame_width: int, frame_height: int, frame_index: np.ndarray
) -> list[ValidationIssue]:
    """Radii must be non-negative and the flame must fit inside the image."""
    issues: list[ValidationIssue] = []
    r = np.asarray(radius_px, dtype=float)
    limit = 0.5 * float(np.hypot(frame_width, frame_height))
    for i in np.flatnonzero(np.isfinite(r) & (r < 0)):
        issues.append(ValidationIssue("negative_radius", "error", "Negative radius.", int(frame_index[i])))
    for i in np.flatnonzero(np.isfinite(r) & (r > limit)):
        issues.append(ValidationIssue(
            "radius_exceeds_frame", "error", "Radius exceeds half the image diagonal.", int(frame_index[i])))
    return issues


def check_expansion_velocity(
    velocity_mm_s: np.ndarray, frame_index: np.ndarray, max_abs_mm_s: float = 5000.0
) -> list[ValidationIssue]:
    """Flag implausibly fast boundary motion.

    The default 5 m/s is well above typical laminar flame propagation speeds
    (order 0.1-3 m/s) and far above the mm/s-cm/s growth rates expected for
    microgravity diffusion flames; exceeding it most likely indicates a
    segmentation or calibration problem rather than physics.
    """
    v = np.asarray(velocity_mm_s, dtype=float)
    hits = np.flatnonzero(np.isfinite(v) & (np.abs(v) > max_abs_mm_s))
    issues = [
        ValidationIssue(
            "implausible_expansion_velocity", "warning",
            f"|dr/dt| = {abs(v[i]):.1f} mm/s exceeds plausibility limit {max_abs_mm_s:.0f} mm/s.",
            int(frame_index[i]))
        for i in hits[:20]
    ]
    if hits.size > 20:
        issues.append(ValidationIssue(
            "implausible_expansion_velocity", "warning", f"{hits.size - 20} further frames exceed the limit."))
    return issues


def check_relative_uncertainty(
    value: np.ndarray, sigma: np.ndarray, name: str, max_relative: float = 0.25
) -> list[ValidationIssue]:
    """Report when the median relative uncertainty of a series is large."""
    value = np.asarray(value, dtype=float)
    sigma = np.asarray(sigma, dtype=float)
    ok = np.isfinite(value) & np.isfinite(sigma) & (value != 0)
    if not np.any(ok):
        return []
    rel = float(np.median(np.abs(sigma[ok] / value[ok])))
    if rel > max_relative:
        return [ValidationIssue(
            "large_relative_uncertainty", "warning",
            f"Median relative uncertainty of {name} is {rel:.1%} (> {max_relative:.0%}).")]
    return []
