"""Temporal flame tracking with explicit handling of detection failures.

For each frame the tracker chooses one contour among the segmentation
candidates. With no active track the largest candidate is taken. With an
active track, centroid and radius are predicted by constant-velocity
extrapolation (in actual time) from the last two accepted detections, and the
candidate with the lowest normalised deviation from that prediction is chosen.

Candidates that deviate more than the configured gates are *rejected*: their
geometry is still recorded for inspection, but they do not enter kinematic
calculations. Missing or rejected frames are never filled in. After
``max_missed_frames`` consecutive frames without an accepted detection the
track is reset, so a genuinely relocated or re-ignited flame can be acquired.

Scores reported here (``continuity``, ``confidence``) are transparent
heuristics in [0, 1] for ranking and flagging. They are not calibrated
probabilities of a correct detection.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from enum import Enum

from backend.vision.geometry import ContourGeometry


class DetectionStatus(str, Enum):
    DETECTED = "detected"
    LOW_CONFIDENCE = "low_confidence"
    NOT_DETECTED = "not_detected"
    REJECTED = "rejected_discontinuity"
    FRAME_ERROR = "frame_error"

    @property
    def accepted(self) -> bool:
        return self in (DetectionStatus.DETECTED, DetectionStatus.LOW_CONFIDENCE)


@dataclass
class TrackingConfig:
    max_centroid_jump_radii: float = 1.0      # gate on centroid deviation, in predicted radii
    min_centroid_gate_px: float = 10.0        # absolute floor of the centroid gate
    max_relative_radius_change: float = 0.5   # gate on |r - r_pred| / r_pred
    min_radius_gate_px: float = 5.0           # absolute floor of the radius gate
    max_missed_frames: int = 10               # consecutive misses before the track resets
    min_confidence: float = 0.25              # below this an accepted detection is LOW_CONFIDENCE

    def validate(self) -> None:
        if min(self.max_centroid_jump_radii, self.max_relative_radius_change) <= 0:
            raise ValueError("Tracking gates must be positive.")
        if self.min_centroid_gate_px < 0 or self.min_radius_gate_px < 0:
            raise ValueError("Gate floors must be non-negative.")
        if self.max_missed_frames < 1:
            raise ValueError("max_missed_frames must be >= 1.")
        if not 0 <= self.min_confidence <= 1:
            raise ValueError("min_confidence must be within [0, 1].")

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TrackDecision:
    chosen: ContourGeometry | None
    status: DetectionStatus
    continuity: float
    notes: list[str] = field(default_factory=list)


@dataclass
class _Obs:
    t: float
    x: float
    y: float
    r: float


class FlameTracker:
    def __init__(self, config: TrackingConfig | None = None) -> None:
        self.config = config or TrackingConfig()
        self.config.validate()
        self._history: list[_Obs] = []
        self._missed = 0

    @property
    def active(self) -> bool:
        return bool(self._history)

    def reset(self) -> None:
        self._history.clear()
        self._missed = 0

    def predict(self, t: float) -> tuple[float, float, float] | None:
        if not self._history:
            return None
        last = self._history[-1]
        if len(self._history) < 2:
            return last.x, last.y, last.r
        prev = self._history[-2]
        dt = last.t - prev.t
        if dt <= 0:
            return last.x, last.y, last.r
        k = (t - last.t) / dt
        return (
            last.x + k * (last.x - prev.x),
            last.y + k * (last.y - prev.y),
            max(0.0, last.r + k * (last.r - prev.r)),
        )

    def _register_miss(self, notes: list[str]) -> None:
        self._missed += 1
        if self.active and self._missed >= self.config.max_missed_frames:
            notes.append(f"track reset after {self._missed} consecutive frames without accepted detection")
            self.reset()

    def update(self, candidates: list[ContourGeometry], t: float, quality_of) -> TrackDecision:
        """Choose a candidate for time ``t``.

        ``quality_of`` maps a candidate to its segmentation-quality score in [0, 1].
        """
        notes: list[str] = []
        if not candidates:
            self._register_miss(notes)
            return TrackDecision(None, DetectionStatus.NOT_DETECTED, 0.0, notes)

        pred = self.predict(t)
        if pred is None:
            chosen = candidates[0]  # largest
            continuity = 1.0
            if len(candidates) > 1:
                notes.append(f"{len(candidates)} candidate contours; largest selected to start track")
        else:
            px, py, pr = pred
            c_gate = max(self.config.max_centroid_jump_radii * pr, self.config.min_centroid_gate_px)
            r_gate = max(self.config.max_relative_radius_change * pr, self.config.min_radius_gate_px)

            def cost(c: ContourGeometry) -> tuple[float, float, float]:
                dc = math.hypot(c.centroid_x_px - px, c.centroid_y_px - py) / c_gate
                dr = abs(c.equivalent_radius_px - pr) / r_gate
                return math.hypot(dc, dr), dc, dr

            scored = sorted(((cost(c), c) for c in candidates), key=lambda s: s[0][0])
            (total, dc, dr), chosen = scored[0]
            if len(candidates) > 1:
                notes.append(f"{len(candidates)} candidate contours; closest to track prediction selected")
            continuity = math.exp(-0.5 * total * total)
            if dc > 1.0 or dr > 1.0:
                notes.append(
                    f"discontinuity: centroid deviation {dc:.2f} gate(s), radius deviation {dr:.2f} gate(s)")
                self._register_miss(notes)
                return TrackDecision(chosen, DetectionStatus.REJECTED, continuity, notes)

        self._history.append(_Obs(t, chosen.centroid_x_px, chosen.centroid_y_px, chosen.equivalent_radius_px))
        del self._history[:-2]
        self._missed = 0
        confidence = quality_of(chosen) * continuity
        status = DetectionStatus.DETECTED if confidence >= self.config.min_confidence else DetectionStatus.LOW_CONFIDENCE
        return TrackDecision(chosen, status, continuity, notes)
