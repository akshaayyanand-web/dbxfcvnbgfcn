"""Image-sequence input, in-image disk calibration, region masks, static-object and sphericity checks.

Fixtures are SYNTHETIC 16-bit TIFF stacks named like ACME CFI files
(``YYYYMMDD_HHMMSS.mmm_INTNS_<tp>_NNNNN.tiff``) with known geometry.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import cv2
import numpy as np
import pytest

from backend.vision.calibration import CalibrationError, measure_dark_disk
from backend.vision.cv_engine import AnalysisConfig, FlameAnalyzer, VideoValidationError, probe_video
from backend.vision.image_sequence import ImageSequenceCapture, ImageSequenceConfig, frame_times, list_frames


def _write_stack(d, radii, dt_s, start=datetime(2019, 10, 31, 19, 40, 43), dark=40, peak=3000,
                 saturate=(), static=False, size=(240, 320), seed=0):
    rng = np.random.default_rng(seed)
    d.mkdir(parents=True, exist_ok=True)
    h, w = size
    yy, xx = np.mgrid[0:h, 0:w]
    t = start
    for i, r in enumerate(radii):
        img = rng.normal(dark, 6, (h, w))
        if r:
            cx, cy = (160, 120) if static else (160 + i * 0.5, 120)
            img += peak * 0.5 * (1 - np.tanh((np.hypot(xx - cx, yy - cy) - r) / 1.5))
        img[5, 5] = 60000  # a hot pixel, must be removed
        if i in saturate:
            img[100:110, 100:110] = 65535
        name = f"{t:%Y%m%d_%H%M%S}.{t.microsecond // 1000:03d}_INTNS_SYN1_{i:05d}.tiff"
        cv2.imwrite(str(d / name), np.clip(img, 0, 65535).astype(np.uint16))
        t += timedelta(seconds=dt_s[i] if isinstance(dt_s, list) else dt_s)
    return d


def test_frame_times_from_filenames(tmp_path):
    d = _write_stack(tmp_path / "s", [0] * 3 + [20] * 3, [0.043, 0.043, 0.3, 0.043, 0.043, 0.043])
    t, src = frame_times(list_frames(d))
    assert src == "filename_timestamp"
    np.testing.assert_allclose(t, [0, 0.043, 0.086, 0.386, 0.429, 0.472], atol=1e-6)


def test_capture_dark_subtraction_hot_pixels_scale_and_saturation(tmp_path):
    d = _write_stack(tmp_path / "s", [0] * 10 + [30] * 10, 0.05, saturate=(15,))
    cap = ImageSequenceCapture(d, ImageSequenceConfig(dark_frames=10, sample_every=1))
    assert not any("may contain light" in n for n in cap.notes)
    assert "1 saturated sample frame(s) excluded" in cap.notes[-1]
    cap._index = 12
    ok, frame = cap.retrieve()
    assert ok and frame.dtype == np.uint8 and frame.shape == (240, 320, 3)
    assert frame[5, 5, 0] < 10            # hot pixel removed
    assert frame[120, 160, 0] > 200       # flame centre bright after fixed scaling
    assert frame[230, 10, 0] < 10         # background near zero after dark subtraction
    cap._index = 15
    cap.retrieve()
    assert cap.last_saturated


def test_dark_frames_with_light_are_reported(tmp_path):
    d = _write_stack(tmp_path / "s", [0, 0, 40, 40, 0, 0], 0.05)
    cap = ImageSequenceCapture(d, ImageSequenceConfig(dark_frames=6))
    assert any("may contain light" in n for n in cap.notes)


def test_analyse_image_sequence_with_calibration_and_variable_intervals(tmp_path):
    radii = [0] * 10 + [10 + 3 * k for k in range(20)] + [0] * 8
    dts = [0.043] * 20 + [0.2] + [0.043] * 17
    d = _write_stack(tmp_path / "s", radii, dts)
    meta = probe_video(d)
    assert meta.container == "image-sequence" and meta.reported_frame_count == len(radii)
    res = FlameAnalyzer(AnalysisConfig()).analyze(d, "SEQ")
    assert res.summary["decoder"] == "image-sequence"
    assert res.summary["timestamp_source"] == "filename_timestamp"
    by = {m.frame_index: m for m in res.measurements}
    for k in (12, 20, 25):
        assert by[k].status == "detected"
        assert abs(by[k].equivalent_radius_px - radii[k]) < 1.0
    assert res.summary["extinction"]["status"] == "observed"
    assert any(i.code == "variable_frame_interval" for i in res.issues)


def test_image_sequence_errors(tmp_path):
    (tmp_path / "empty").mkdir()
    with pytest.raises(VideoValidationError):
        probe_video(tmp_path / "empty")
    with pytest.raises(ValueError):
        ImageSequenceConfig(dark_frames=-1).validate()


def test_static_emitter_is_flagged(tmp_path):
    d = _write_stack(tmp_path / "s", [0] * 10 + [12] * 90, 0.05, static=True)
    res = FlameAnalyzer(AnalysisConfig()).analyze(d, "STATIC")
    assert any(i.code == "static_detection" for i in res.issues)


def test_exclude_region_removes_emitter(tmp_path):
    d = _write_stack(tmp_path / "s", [0] * 10 + [12] * 20, 0.05, static=True)
    res = FlameAnalyzer(AnalysisConfig(exclude_regions=[(130, 90, 60, 60)])).analyze(d, "EXCL")
    assert res.summary["status_counts"]["detected"] == 0
    with pytest.raises(ValueError):
        AnalysisConfig(exclude_regions=[(0, 0, 0, 5)]).validate()


def test_roi_restricts_analysis(tmp_path):
    d = _write_stack(tmp_path / "s", [0] * 10 + [12] * 10, 0.05, static=True)
    res = FlameAnalyzer(AnalysisConfig(roi=(0, 0, 100, 100))).analyze(d, "ROI")
    assert res.summary["status_counts"]["detected"] == 0


def test_non_spherical_flame_has_no_equivalent_volume(tmp_path):
    from backend.vision.calibration import Calibration
    d = tmp_path / "c"
    d.mkdir()
    rng = np.random.default_rng(0)
    t = datetime(2020, 1, 1)
    for i in range(16):
        img = rng.normal(40, 6, (240, 320))
        if i >= 10:  # a C-shaped emitter: an annulus with a 120 degree gap
            yy, xx = np.mgrid[0:240, 0:320]
            r = np.hypot(xx - 160, yy - 120)
            ang = np.degrees(np.arctan2(yy - 120, xx - 160)) % 360
            img[(r > 40) & (r < 70) & ((ang < 300) & (ang > 60))] += 3000
        cv2.imwrite(str(d / f"{t:%Y%m%d_%H%M%S}.{t.microsecond // 1000:03d}_INTNS_C_{i:05d}.tiff"),
                    np.clip(img, 0, 65535).astype(np.uint16))
        t += timedelta(seconds=0.05)
    cal = Calibration(known_length_mm=10, measured_length_px=100, image_width=320, image_height=240)
    res = FlameAnalyzer(AnalysisConfig(), cal).analyze(d, "CSHAPE")
    lit = [m for m in res.measurements if m.accepted]
    assert lit and all(m.equivalent_volume_mm3 is None for m in lit)
    assert all(m.radius_mm is not None for m in lit)
    assert res.summary["frames_volume_suppressed_non_spherical"] == len(lit)


def test_measure_dark_disk_recovers_diameter_with_tube():
    rng = np.random.default_rng(1)
    h, w = 400, 500
    yy, xx = np.mgrid[0:h, 0:w]
    img = 100 + rng.normal(0, 8, (h, w))
    r = np.hypot(xx - 250, yy - 200)
    img -= 70 * 0.5 * (1 - np.tanh((r - 50) / 2.0))               # dark disk, diameter 100 px
    img[(np.abs(yy - 200) < 8) & (xx > 250)] -= 70                # supply tube towards +x
    d = measure_dark_disk(img, (245, 205), 110, excluded_angles_deg=[(340, 20)])
    assert d.diameter_px == pytest.approx(100, abs=3)
    assert math.dist(d.center_px, (250, 200)) < 2
    assert 1.0 <= d.diameter_sigma_px < 3
    with pytest.raises(CalibrationError):
        measure_dark_disk(np.zeros((50, 50)), (25, 25), 20)
