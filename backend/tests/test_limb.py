"""Limb (shell-edge) fit: synthetic projected spherical shells with known outer radius."""

from __future__ import annotations

from datetime import datetime, timedelta

import cv2
import numpy as np
import pytest

from backend.vision.calibration import Calibration
from backend.vision.cv_engine import AnalysisConfig, FlameAnalyzer
from backend.vision.limb import LimbConfig, fit_limb


def shell(h=480, w=640, c=(320, 240), r=150.0, th=4.0, blur=1.5, amp=200.0, noise=5.0, gap=None, seed=0):
    """Line-of-sight projection of a thin uniform spherical shell (chord length through the shell)."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    rho = np.hypot(xx - c[0], yy - c[1])
    img = np.sqrt(np.clip(r ** 2 - rho ** 2, 0, None)) - np.sqrt(np.clip((r - th) ** 2 - rho ** 2, 0, None))
    if gap:
        ang = np.degrees(np.arctan2(yy - c[1], xx - c[0])) % 360
        img[(ang >= gap[0]) & (ang <= gap[1])] = 0
    img = cv2.GaussianBlur(img / img.max() * amp, (0, 0), blur)
    return img + np.random.default_rng(seed).normal(10, noise, (h, w))


@pytest.mark.parametrize("kw,min_cov", [({}, 0.95), ({"gap": (300, 360)}, 0.75), ({"gap": (200, 360)}, 0.5),
                                        ({"c": (120, 240)}, 0.7)])
def test_limb_recovers_outer_radius(kw, min_cov):
    c = kw.get("c", (320, 240))
    f = fit_limb(shell(**kw), (c[0] + 15, c[1] - 10))
    assert f.sufficient
    assert f.radius_px == pytest.approx(150, abs=1.0)        # outer half-max edge within 1 px of the true radius
    assert np.hypot(f.center_px[0] - c[0], f.center_px[1] - c[1]) < 1.0
    assert f.coverage >= min_cov


def test_limb_ignores_bright_interior_source_and_uneven_shell():
    img = shell(noise=8)
    yy, xx = np.mgrid[0:480, 0:640]
    img = 10 + (img - 10) * (0.65 + 0.35 * np.sin(np.arctan2(yy - 240, xx - 320)))
    img += 1000 * np.exp(-((xx - 260) ** 2 + (yy - 190) ** 2) / (2 * 12 ** 2))   # igniter, 5x brighter than shell
    img[np.hypot(xx - 320, yy - 240) < 30] = 10                                   # dark burner
    f = fit_limb(img, (300, 230))
    assert f.sufficient and f.radius_px == pytest.approx(150, abs=1.0)


def test_limb_noise_only_and_short_arc():
    rng = np.random.default_rng(3)
    f = fit_limb(rng.normal(10, 5, (240, 320)), (160, 120))
    assert f is None or not f.sufficient
    f = fit_limb(shell(gap=(60, 360)), (320, 240))        # only 60 degrees lit
    assert f is None or not f.sufficient


def test_limb_config_validation():
    with pytest.raises(ValueError):
        LimbConfig(n_sectors=4).validate()
    with pytest.raises(ValueError):
        AnalysisConfig(radius_method="magic").validate()


def _shell_stack(d, radii, dt=0.05, igniter_frames=(), saturate=()):
    d.mkdir(parents=True, exist_ok=True)
    t = datetime(2019, 9, 11, 22, 10, 58)
    for i, r in enumerate(radii):
        img = np.random.default_rng(i).normal(40, 6, (240, 320))
        if r:
            img += shell(240, 320, (160, 120), r, th=3, amp=2500, noise=0, seed=i) - 10
        if i in igniter_frames:
            yy, xx = np.mgrid[0:240, 0:320]
            img += 3000 * np.exp(-((xx - 120) ** 2 + (yy - 100) ** 2) / (2 * 3.0 ** 2))
        if i in saturate:
            img[110:130, 150:170] = 65535
        cv2.imwrite(str(d / f"{t:%Y%m%d_%H%M%S}.{t.microsecond // 1000:03d}_INTNS_SH_{i:05d}.tiff"),
                    np.clip(img, 0, 65535).astype(np.uint16))
        t += timedelta(seconds=dt)
    return d


def test_engine_limb_mode_measures_growth_and_rejects_igniter_and_saturation(tmp_path):
    radii = [0] * 10 + [0, 0] + [40 + 1.5 * k for k in range(30)] + [0] * 8
    d = _shell_stack(tmp_path / "s", radii, igniter_frames=(10, 11), saturate=(15,))
    cal = Calibration(known_length_mm=10, measured_length_px=100, image_width=320, image_height=240)
    cfg = AnalysisConfig(radius_method="limb", limb_center_hint=(160, 120), limb_min_radius_mm=1.0)
    res = FlameAnalyzer(cfg, cal).analyze(d, "LIMB")
    by = {m.frame_index: m for m in res.measurements}
    for i in (10, 11):                                    # igniter spot (r ~ 0.5 mm) is not a flame
        assert not by[i].limb_fit_ok
    assert not by[15].limb_fit_ok                         # saturated frame rejected
    for i in (20, 30, 40):
        assert by[i].limb_fit_ok
        assert by[i].limb_radius_px == pytest.approx(radii[i], abs=1.0)
        assert by[i].equivalent_volume_mm3 == pytest.approx(4 / 3 * np.pi * by[i].limb_radius_mm ** 3)
    v = [by[i].expansion_velocity_px_s for i in range(20, 38)]
    assert np.nanmedian(v) == pytest.approx(1.5 / 0.05, rel=0.05)   # 1.5 px per 50 ms = 30 px/s
    assert res.summary["radius_method"] == "limb" and res.summary["extinction"]["status"] == "observed"
