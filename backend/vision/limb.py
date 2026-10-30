"""Limb (outer-edge) circle fit for shell-like flames.

A spherical diffusion flame is a thin luminous shell. Seen in projection, its
brightness peaks near the limb, and threshold-based area measures capture only
the brighter part of it (A-CV-12). The flame radius used in the s-Flame
literature is the radius of the luminous shell. This module estimates it
directly:

1. Polar resampling of the frame around a centre estimate (``cv2.warpPolar``).
2. Per angular sector: a radial profile, and the **outermost** local maximum
   above ``bg + k * noise`` (the limb; brighter interior sources such as the
   igniter tip are deliberately ignored). The **outer half-maximum edge** is
   where the profile falls to halfway between that peak and the background,
   searching outward. Sectors whose edge would lie outside the
   image are rejected as clipped. They are not extrapolated.
3. RANSAC circle fit (inlier tolerance ``max(2 px, 2 % R)``) followed by an
   algebraic (Kasa) least-squares refit on the inliers. Edge points from
   non-shell structures (interior features, faint emission below 20 % of the
   frame's brightest limb) are not on the circle and are rejected. The centre is
   refined by repeating step 2 around the fitted centre. A fit is *sufficient*
   only if its inliers lie on a circle (RMS ≤ max(2 px, 3 % R)), span ≥ 90° and
   cover ≥ 40 % of sectors.
4. Uncertainty: a bootstrap (fixed seed) over edge points, so it grows
   automatically when only a short arc is lit.

Reported coverage is the fraction of sectors that contributed an edge. A
C-shaped (partially extinguished) or clipped flame therefore yields a radius
*with* its coverage, and callers decide whether the arc is sufficient
(``min_coverage``).

Edge definition: for a shell of thickness ``d`` blurred by the optics, the
outer half-maximum point lies within about ``d/2`` plus the blur half-width
inside the true outer radius. The validation on synthetic projected shells is
in ``test_limb.py``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class LimbConfig:
    n_sectors: int = 72
    k_noise: float = 6.0             # sector peak must exceed bg + k_noise * noise
    smooth_px: int = 5               # radial moving-average window
    min_radius_px: float = 3.0       # ignore the centre (burner silhouette, igniter)
    min_points: int = 8
    min_arc_deg: float = 90.0        # angular span of edge points required for a fit
    min_coverage: float = 0.4        # fits below this coverage are reported but marked insufficient.
                                     # 0.4 from real data (PSI-23 19254C1): lower-coverage fits deviated
                                     # from neighbouring frames by up to 0.8 mm.
    min_peak_fraction: float = 0.2   # sector limb peak must reach this fraction of the frame's brightest limb
    inlier_tol_px: float = 2.0       # RANSAC inlier tolerance: max(inlier_tol_px, inlier_tol_frac * R)
    inlier_tol_frac: float = 0.02
    max_rms_frac: float = 0.03       # sufficient only if inlier RMS <= max(inlier_tol_px, max_rms_frac * R)
    ransac_iterations: int = 400
    refine_iterations: int = 2
    bootstrap: int = 200
    seed: int = 0

    def validate(self) -> None:
        if self.n_sectors < 8 or self.min_points < 5 or self.bootstrap < 0:
            raise ValueError("n_sectors >= 8, min_points >= 5 and bootstrap >= 0 are required.")
        if not 0 < self.min_coverage <= 1 or not 0 < self.min_arc_deg <= 360:
            raise ValueError("min_coverage in (0, 1] and min_arc_deg in (0, 360] are required.")


@dataclass
class LimbFit:
    radius_px: float
    radius_sigma_px: float
    center_px: tuple[float, float]
    coverage: float                  # fraction of sectors with a flame edge
    arc_deg: float                   # angular span of the edge points
    rms_residual_px: float
    n_points: int
    sufficient: bool
    edge_points: list[tuple[float, float]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _kasa(pts: np.ndarray) -> tuple[float, float, float]:
    a = np.c_[2 * pts[:, 0], 2 * pts[:, 1], np.ones(len(pts))]
    b = (pts ** 2).sum(axis=1)
    (cx, cy, c), *_ = np.linalg.lstsq(a, b, rcond=None)
    return float(cx), float(cy), float(math.sqrt(max(c + cx * cx + cy * cy, 0.0)))


def _circle3(p: np.ndarray) -> tuple[float, float, float] | None:
    (x1, y1), (x2, y2), (x3, y3) = p
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if abs(d) < 1e-9:
        return None
    s1, s2, s3 = x1 * x1 + y1 * y1, x2 * x2 + y2 * y2, x3 * x3 + y3 * y3
    ux = (s1 * (y2 - y3) + s2 * (y3 - y1) + s3 * (y1 - y2)) / d
    uy = (s1 * (x3 - x2) + s2 * (x1 - x3) + s3 * (x2 - x1)) / d
    return ux, uy, math.hypot(x1 - ux, y1 - uy)


def _ransac_fit(pts: np.ndarray, cfg: LimbConfig, rng: np.random.Generator) -> tuple[float, float, float, np.ndarray]:
    """RANSAC circle: maximise inliers |d - r| <= max(tol_px, tol_frac * r), then least-squares refit on inliers."""
    best_keep, best_score = np.ones(len(pts), bool), (-1, math.inf)
    for _ in range(cfg.ransac_iterations):
        c = _circle3(pts[rng.choice(len(pts), 3, replace=False)])
        if c is None or c[2] <= 0:
            continue
        res = np.abs(np.hypot(pts[:, 0] - c[0], pts[:, 1] - c[1]) - c[2])
        keep = res <= max(cfg.inlier_tol_px, cfg.inlier_tol_frac * c[2])
        score = (int(keep.sum()), float(np.mean(res[keep] ** 2)) if keep.any() else math.inf)
        if score[0] > best_score[0] or (score[0] == best_score[0] and score[1] < best_score[1]):
            best_keep, best_score = keep, score
    cx, cy, r = _kasa(pts[best_keep])
    for _ in range(3):  # re-evaluate inliers against the refined circle
        res = np.abs(np.hypot(pts[:, 0] - cx, pts[:, 1] - cy) - r)
        keep = res <= max(cfg.inlier_tol_px, cfg.inlier_tol_frac * r)
        if keep.sum() < 3 or np.array_equal(keep, best_keep):
            break
        best_keep = keep
        cx, cy, r = _kasa(pts[best_keep])
    return cx, cy, r, best_keep


def _arc_span(angles_deg: np.ndarray) -> float:
    if angles_deg.size < 2:
        return 0.0
    a = np.sort(angles_deg % 360)
    gaps = np.diff(np.r_[a, a[0] + 360])
    return float(360 - gaps.max())


def _ray_exit(cx: float, cy: float, theta: float, w: int, h: int) -> float:
    """Distance from (cx, cy) along direction theta to the border of a w x h image (0 if outside)."""
    if not (0 <= cx <= w - 1 and 0 <= cy <= h - 1):
        return 0.0
    dx, dy = math.cos(theta), math.sin(theta)
    ts = []
    if dx > 1e-12:
        ts.append((w - 1 - cx) / dx)
    elif dx < -1e-12:
        ts.append(-cx / dx)
    if dy > 1e-12:
        ts.append((h - 1 - cy) / dy)
    elif dy < -1e-12:
        ts.append(-cy / dy)
    return min(ts) if ts else 0.0


def _edges(img: np.ndarray, center: tuple[float, float], bg: float, noise: float, cfg: LimbConfig):
    h, w = img.shape
    cx, cy = center
    max_r = float(np.hypot(max(cx, w - cx), max(cy, h - cy)))
    n_r = int(math.ceil(max_r))
    rows = cfg.n_sectors * 4
    polar = cv2.warpPolar(img, (n_r, rows), (cx, cy), max_r, cv2.WARP_POLAR_LINEAR + cv2.INTER_LINEAR)
    polar = np.nan_to_num(polar, nan=0.0, posinf=0.0, neginf=0.0)
    r_scale = max_r / n_r
    kernel = np.ones(cfg.smooth_px) / cfg.smooth_px
    r0 = int(cfg.min_radius_px / r_scale)
    row_angles = np.radians(np.arange(rows) * 360.0 / rows)  # warpPolar: row k at angle k*360/rows from +x towards +y
    out = []
    for s in range(cfg.n_sectors):
        prof = polar[s * 4:(s + 1) * 4].mean(axis=0)
        # Exact distance along each ray to the image border (warpPolar does not mark outside samples reliably).
        exits = [_ray_exit(cx, cy, th, w, h) for th in row_angles[s * 4:(s + 1) * 4]]
        last = int(math.floor(min(exits) / r_scale)) - 2
        if last <= r0 + cfg.smooth_px:
            continue
        p = np.convolve(prof[: last + 1], kernel, mode="same")
        # Anchor on the OUTERMOST significant local maximum: the shell limb is the outermost luminous
        # structure, while brighter interior sources (igniter tip, ignition kernel) must not set the edge.
        seg = p[r0:]
        level = bg + cfg.k_noise * noise
        peaks = np.flatnonzero((seg[1:-1] >= seg[:-2]) & (seg[1:-1] >= seg[2:]) & (seg[1:-1] > level)) + 1
        if peaks.size == 0:
            continue
        i_pk = int(peaks[-1]) + r0
        peak = float(p[i_pk])
        half = bg + 0.5 * (peak - bg)
        below = np.flatnonzero(p[i_pk:] < half)
        if below.size == 0:
            continue  # profile still bright at the image edge: clipped sector, no extrapolation
        j = i_pk + int(below[0])
        if j >= last - cfg.smooth_px // 2:
            continue
        frac = (p[j - 1] - half) / (p[j - 1] - p[j]) if p[j - 1] != p[j] else 0.0
        r_edge = (j - 1 + frac) * r_scale
        ang = (s * 4 + 1.5) * 360.0 / rows
        out.append((ang, cx + r_edge * math.cos(math.radians(ang)), cy + r_edge * math.sin(math.radians(ang)),
                    peak - bg))
    # Relative floor: faint structures must not compete with a clearly brighter limb in the same frame.
    if out:
        top = max(e[3] for e in out)
        out = [e for e in out if e[3] >= cfg.min_peak_fraction * top]
    return out


def fit_limb(image: np.ndarray, center_hint: tuple[float, float], config: LimbConfig | None = None,
             background: float | None = None, noise: float | None = None) -> LimbFit | None:
    """Fit the luminous-shell limb. Returns ``None`` when no sector contains flame."""
    cfg = config or LimbConfig()
    cfg.validate()
    img = np.asarray(image, dtype=np.float32)
    if img.ndim == 3:
        img = img.max(axis=2)
    bg = float(np.median(img)) if background is None else background
    nz = float(1.4826 * np.median(np.abs(img - np.median(img)))) if noise is None else noise
    nz = max(nz, 1.0)
    center = center_hint
    notes: list[str] = []
    fit = None
    best_key = (-1, 0)
    for it in range(cfg.refine_iterations + 1):
        edges = _edges(img, center, bg, nz, cfg)
        if len(edges) < max(cfg.min_points, 3):
            if fit is None:
                return None if not edges else LimbFit(
                    math.nan, math.nan, center, len(edges) / cfg.n_sectors, 0.0, math.nan, len(edges), False,
                    [(e[1], e[2]) for e in edges], [f"only {len(edges)} edge points"])
            break
        pts = np.array([(e[1], e[2]) for e in edges])
        angs = np.array([e[0] for e in edges])
        cx, cy, r, keep = _ransac_fit(pts, cfg, np.random.default_rng(cfg.seed))
        res = np.abs(np.hypot(pts[keep, 0] - cx, pts[keep, 1] - cy) - r)
        key = (int(keep.sum()), -float(np.sqrt(np.mean(res ** 2))))
        # Keep the best fit over centre refinements; a refinement must not replace a better fit.
        if key > best_key:
            best_key, fit = key, (cx, cy, r, pts, keep, angs)
        elif fit is not None:
            break
        if math.hypot(cx - center[0], cy - center[1]) < 0.5:
            break
        center = (cx, cy)
    cx, cy, r, pts, keep, angs = fit
    res = np.hypot(pts[keep, 0] - cx, pts[keep, 1] - cy) - r
    rng = np.random.default_rng(cfg.seed)
    kp = pts[keep]
    boots = []
    for _ in range(cfg.bootstrap):
        sample = kp[rng.integers(0, len(kp), len(kp))]
        if len(np.unique(sample, axis=0)) >= 3:
            boots.append(_kasa(sample)[2])
    sigma = float(np.std(boots, ddof=1)) if len(boots) > 2 else math.nan
    arc = _arc_span(angs[keep])
    coverage = float(keep.sum()) / cfg.n_sectors
    rms = float(np.sqrt(np.mean(res ** 2)))
    circular = rms <= max(cfg.inlier_tol_px, cfg.max_rms_frac * r)
    sufficient = bool(keep.sum() >= cfg.min_points and arc >= cfg.min_arc_deg and coverage >= cfg.min_coverage
                      and circular)
    if not sufficient:
        notes.append(f"insufficient: {keep.sum()} inliers, span {arc:.0f} deg, coverage {coverage:.0%}, "
                     f"rms {rms:.1f} px")
    if (~keep).sum():
        notes.append(f"{int((~keep).sum())} of {len(keep)} edge points are not on the fitted circle")
    return LimbFit(r, sigma, (cx, cy), coverage, arc, rms, int(keep.sum()),
                   sufficient, [tuple(map(float, p)) for p in kp], notes)
