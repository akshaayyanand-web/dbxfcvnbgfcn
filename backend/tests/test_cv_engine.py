"""Computer-vision engine tests.

Accuracy tests use SYNTHETIC videos whose true radius, centre, growth rate and
extinction time are known exactly (backend/vision/synthetic.py). They validate
the measurement pipeline; they say nothing about real-flame segmentation
difficulty, which must be checked on genuine experimental footage.
"""

from __future__ import annotations

import json
import math
import shutil
import threading

import cv2
import numpy as np
import pandas as pd
import pytest

from backend.vision.calibration import Calibration, CalibrationError, DistortionCorrection
from backend.vision.cv_engine import (
    FIELD_DEFINITIONS,
    AnalysisCancelled,
    AnalysisConfig,
    FlameAnalyzer,
    VideoValidationError,
    probe_video,
)
from backend.vision.geometry import measure_contour
from backend.vision.segmentation import SegmentationConfig, SegmentationMethod, Segmenter, find_contours
from backend.vision.synthetic import SyntheticFlameSpec, write_synthetic_video
from backend.vision.tracking import DetectionStatus, FlameTracker
from backend.tests.conftest import requires_ffmpeg

CAL = dict(known_length_mm=10.0, measured_length_px=100.0, measured_length_sigma_px=1.0,
           image_width=640, image_height=480)


def merged(result, gt: pd.DataFrame) -> pd.DataFrame:
    return result.to_dataframe().merge(gt, on="frame_index", suffixes=("", "_true"))


@pytest.fixture(scope="module")
def demo_result(demo_video):
    path, gt, _ = demo_video
    return FlameAnalyzer(calibration=Calibration(**CAL)).analyze(path, "SYN-DEMO"), gt


# ------------------------------------------------------------------ ingestion

def test_probe_valid_video(demo_video):
    path, gt, spec = demo_video
    meta = probe_video(path)
    assert (meta.width, meta.height) == (spec.width, spec.height)
    assert meta.nominal_fps == pytest.approx(spec.fps)
    assert meta.reported_frame_count == len(gt)
    assert meta.duration_s == pytest.approx(spec.duration_s, abs=0.05)
    assert meta.filename == path.name and meta.container == "mp4"


def test_unsupported_format(tmp_path):
    bad = tmp_path / "flame.mkv"
    bad.write_bytes(b"\x00" * 100)
    with pytest.raises(VideoValidationError, match="Unsupported"):
        probe_video(bad)


def test_missing_file(tmp_path):
    with pytest.raises(VideoValidationError, match="not found"):
        probe_video(tmp_path / "nope.mp4")


def test_empty_file(tmp_path):
    (tmp_path / "empty.mp4").write_bytes(b"")
    with pytest.raises(VideoValidationError, match="empty"):
        probe_video(tmp_path / "empty.mp4")


def test_corrupted_file(tmp_path):
    p = tmp_path / "garbage.mp4"
    p.write_bytes(np.random.default_rng(0).integers(0, 256, 50_000, dtype=np.uint8).tobytes())
    with pytest.raises(VideoValidationError):
        probe_video(p)


def test_file_size_limit(demo_video):
    with pytest.raises(VideoValidationError, match="limit"):
        probe_video(demo_video[0], max_file_bytes=10)


def test_truncated_video_analyses_decodable_prefix(tmp_path):
    spec = SyntheticFlameSpec(duration_s=2.0, extinction_time_s=None)
    full = tmp_path / "SYNTHETIC_trunc.avi"
    write_synthetic_video(full, spec)
    data = full.read_bytes()
    cut = tmp_path / "SYNTHETIC_cut.avi"
    cut.write_bytes(data[: len(data) // 2])
    res = FlameAnalyzer().analyze(cut, "TRUNC")
    assert 0 < res.summary["frames_decoded"] < 60
    assert res.summary["detection_rate"] > 0.9


# ------------------------------------------------------------------- accuracy

def test_radius_accuracy_against_ground_truth(demo_result):
    res, gt = demo_result
    d = merged(res, gt)
    vis = d[d.flame_visible]
    assert (vis.status == "detected").all()
    err = vis.equivalent_radius_px - vis.radius_px
    assert abs(err.mean()) < 0.25          # bias, px
    assert err.abs().max() < 1.0           # worst case, px
    np.testing.assert_allclose(vis.radius_mm, vis.equivalent_radius_px * 0.1)


def test_centroid_accuracy(demo_result):
    res, gt = demo_result
    vis = merged(res, gt).query("flame_visible")
    err = np.hypot(vis.centroid_x_px - vis.center_x_px, vis.centroid_y_px - vis.center_y_px)
    assert err.max() < 0.5


def test_expansion_velocity_and_acceleration(demo_result):
    res, gt = demo_result
    vis = merged(res, gt).query("flame_visible")
    rel = (vis.expansion_velocity_px_s - vis.radius_rate_px_s) / vis.radius_rate_px_s
    assert rel.abs().median() < 0.02
    interior = vis.iloc[5:-5]  # local fits at segment ends extrapolate
    acc_err = (interior.acceleration_px_s2 - interior.radius_accel_px_s2).abs()
    assert acc_err.median() < 0.1 * interior.radius_accel_px_s2.abs().max()
    np.testing.assert_allclose(vis.expansion_velocity_mm_s, vis.expansion_velocity_px_s * 0.1)


def test_extinction_time_contains_truth(demo_result, demo_video):
    res, _ = demo_result
    ext = res.summary["extinction"]
    assert ext["status"] == "observed"
    true_t = demo_video[2].extinction_time_s
    assert abs(ext["time_s"] - true_t) <= ext["uncertainty_s"] + 1e-9


def test_derived_quantities_and_uncertainty(demo_result):
    res, _ = demo_result
    m = next(m for m in res.measurements if m.frame_index == 60)
    assert m.equivalent_volume_mm3 == pytest.approx(4 / 3 * math.pi * m.radius_mm**3)
    assert m.equivalent_volume_sigma_mm3 == pytest.approx(4 * math.pi * m.radius_mm**2 * m.radius_sigma_mm)
    assert m.radius_sigma_mm == pytest.approx(math.hypot(m.radius_sigma_random_mm, m.radius_sigma_scale_mm))
    assert m.radius_sigma_scale_mm == pytest.approx(m.radius_mm * Calibration(**CAL).relative_uncertainty)
    assert 0.85 < m.circularity <= 1.0
    assert m.eccentricity < 0.15
    assert m.area_mm2 == pytest.approx(m.area_px2 * 0.01)
    assert m.diameter_mm == pytest.approx(2 * m.radius_mm)


def test_summary_and_shape_metrics(demo_result):
    res, _ = demo_result
    s = res.summary
    assert s["timestamp_source"] == "container_pts"
    assert s["status_counts"]["detected"] == 126 and s["status_counts"]["not_detected"] == 24
    assert s["shape_stability_cv"] < 0.05
    assert s["radius_noise_check"]["observed_residual_sigma_px"] < s["radius_noise_check"]["assumed_sigma_px_median"]
    assert s["processing"]["wall_time_s"] > 0


# -------------------------------------------------------------- failure modes

def test_temporary_tracking_loss_is_not_interpolated(disturbed_video):
    path, gt, _ = disturbed_video
    res = FlameAnalyzer().analyze(path, "SYN-DIST")
    by_idx = {m.frame_index: m for m in res.measurements}
    for i in (20, 21, 22):
        assert by_idx[i].status == "not_detected"
        assert by_idx[i].equivalent_radius_px is None and by_idx[i].expansion_velocity_px_s is None
    assert by_idx[23].status == "detected"
    assert res.summary["extinction"]["status"] == "flame_present_at_end"


def test_multiple_contours_keep_tracked_flame(disturbed_video):
    path, gt, _ = disturbed_video
    res = FlameAnalyzer().analyze(path, "SYN-DIST")
    d = merged(res, gt).set_index("frame_index")
    for i in (30, 31, 40):
        assert d.loc[i, "n_candidates"] == 2
        assert d.loc[i, "status"] == "detected"
        assert abs(d.loc[i, "equivalent_radius_px"] - d.loc[i, "radius_px"]) < 1.0


def test_tracker_rejects_discontinuity_and_resets():
    seg = Segmenter()
    def blob(cx, r):
        img = np.full((200, 200, 3), 5, np.uint8)
        cv2.circle(img, (cx, 100), r, (230, 230, 230), -1)
        res = seg.segment(img)
        c, _ = find_contours(res.mask, 30)
        return measure_contour(c[0], res.intensity)
    tracker = FlameTracker()
    q = lambda g: 1.0
    assert tracker.update([blob(60, 20)], 0.0, q).status is DetectionStatus.DETECTED
    assert tracker.update([blob(61, 21)], 0.1, q).status is DetectionStatus.DETECTED
    assert tracker.update([blob(150, 21)], 0.2, q).status is DetectionStatus.REJECTED
    for k in range(tracker.config.max_missed_frames - 1):
        tracker.update([], 0.3 + 0.1 * k, q)
    assert not tracker.active  # reset after max_missed_frames
    assert tracker.update([blob(150, 21)], 2.0, q).status is DetectionStatus.DETECTED


def test_empty_black_frames(tmp_path):
    p = tmp_path / "black.avi"
    w = cv2.VideoWriter(str(p), cv2.VideoWriter_fourcc(*"MJPG"), 10, (160, 120))
    for _ in range(15):
        w.write(np.zeros((120, 160, 3), np.uint8))
    w.release()
    res = FlameAnalyzer().analyze(p, "BLACK")
    assert res.summary["status_counts"]["not_detected"] == 15
    assert res.summary["extinction"]["status"] == "never_detected"
    assert all("insufficient contrast" in m.warnings[0] for m in res.measurements)


def test_noise_only_video_has_no_detections(tmp_path):
    spec = SyntheticFlameSpec(duration_s=1.0, ignition_time_s=99.0, extinction_time_s=None)
    p = tmp_path / "SYNTHETIC_noflame.mp4"
    write_synthetic_video(p, spec)
    res = FlameAnalyzer().analyze(p, "NOISE")
    assert res.summary["status_counts"]["detected"] == 0
    assert res.summary["status_counts"]["low_confidence"] == 0


def test_flame_clipped_by_border_is_flagged(tmp_path):
    spec = SyntheticFlameSpec(duration_s=0.5, center_px=(600.0, 240.0), r0_px=80, r_max_px=90,
                              extinction_time_s=None, drift_px_s=(0, 0))
    p = tmp_path / "SYNTHETIC_clipped.mp4"
    write_synthetic_video(p, spec)
    res = FlameAnalyzer().analyze(p, "CLIP")
    assert all(m.touches_border for m in res.measurements)
    assert any(i.code == "flame_clipped" for i in res.issues)


# ----------------------------------------------------------------- timestamps

def test_variable_frame_rate_uses_true_timestamps(vfr_video):
    path, gt, _ = vfr_video
    res = FlameAnalyzer().analyze(path, "VFR")
    d = merged(res, gt)
    assert len(d) == len(gt)
    np.testing.assert_allclose(d.timestamp_s, d.timestamp_s_true, atol=1e-3)
    assert any(i.code == "variable_frame_interval" for i in res.issues)
    rel = (d.expansion_velocity_px_s - d.radius_rate_px_s) / d.radius_rate_px_s
    assert rel.abs().median() < 0.03


def test_frame_sampling(demo_video):
    path, gt, _ = demo_video
    res = FlameAnalyzer(AnalysisConfig(frame_step=3, max_frames=20)).analyze(path, "STEP")
    assert [m.frame_index for m in res.measurements] == list(range(0, 60, 3))
    d = merged(res, gt)
    np.testing.assert_allclose(d.timestamp_s, d.timestamp_s_true, atol=1e-3)


def test_time_window(demo_video):
    res = FlameAnalyzer(AnalysisConfig(start_time_s=1.0, end_time_s=2.0)).analyze(demo_video[0], "WIN")
    t = [m.timestamp_s for m in res.measurements]
    assert min(t) >= 1.0 - 1e-6 and max(t) <= 2.0 + 1e-6 and len(t) == 31


def test_processing_scale_rescales_to_original_pixels(demo_video):
    path, gt, _ = demo_video
    res = FlameAnalyzer(AnalysisConfig(processing_scale=0.5, max_frames=60)).analyze(path, "HALF")
    vis = merged(res, gt).query("flame_visible")
    assert (vis.equivalent_radius_px - vis.radius_px).abs().max() < 1.5


# --------------------------------------------------------------- segmentation

@pytest.mark.parametrize("method,extra", [
    ("otsu", {}),
    ("fixed", {"fixed_threshold": 114}),
    ("adaptive", {}),
    ("hsv", {"hsv_lower": (90, 50, 114), "hsv_upper": (130, 255, 255)}),
])
def test_segmentation_methods(demo_video, method, extra):
    path, gt, _ = demo_video
    cfg = AnalysisConfig(segmentation=SegmentationConfig(method=method, **extra), max_frames=90)
    vis = merged(FlameAnalyzer(cfg).analyze(path, method), gt).query("flame_visible")
    rel = (vis.equivalent_radius_px - vis.radius_px) / vis.radius_px
    assert (vis.status == "detected").mean() > 0.95
    assert rel.abs().median() < 0.03


def test_background_subtraction_after_ignition(tmp_path):
    spec = SyntheticFlameSpec(duration_s=1.5, ignition_time_s=0.8, extinction_time_s=None, drift_px_s=(0, 0))
    p = tmp_path / "SYNTHETIC_ignition.mp4"
    gt = pd.DataFrame(write_synthetic_video(p, spec)["frames"])
    cfg = AnalysisConfig(segmentation=SegmentationConfig(method="background_subtraction"))
    d = merged(FlameAnalyzer(cfg).analyze(p, "BG"), gt)
    before = d[d.timestamp_s < 0.75]
    after = d[(d.timestamp_s > 0.85) & (d.timestamp_s < 1.0)]
    assert (before.status != "detected").all()
    assert (after.status == "detected").all()
    # MOG2 flags any pixel ~5 sigma above the background model, i.e. the faint outer edge of the
    # emission rather than the half-maximum isophote used as ground truth: a known, bounded,
    # method-dependent offset (SCIENTIFIC_ASSUMPTIONS.md, A-CV-3). The growth rate is unaffected.
    offset = after.equivalent_radius_px - after.radius_px
    assert ((offset > 0) & (offset < 5)).all()
    assert offset.std() < 0.3
    true_growth = np.diff(after.radius_px.to_numpy())
    np.testing.assert_allclose(np.diff(after.equivalent_radius_px.to_numpy()), true_growth, atol=0.5)


def test_segmentation_config_validation():
    for bad in (dict(blur_kernel=4), dict(adaptive_block_size=2), dict(fixed_threshold=300),
                dict(max_foreground_fraction=0), dict(hsv_lower=(200, 0, 0)), dict(min_candidate_contrast=1.5)):
        with pytest.raises(ValueError):
            SegmentationConfig(**bad).validate()
    with pytest.raises(ValueError):
        SegmentationConfig(method="magic")
    with pytest.raises(ValueError):
        AnalysisConfig(frame_step=0).validate()


def test_uniform_bright_frame_is_rejected():
    res = Segmenter().segment(np.full((50, 50, 3), 200, np.uint8))
    assert res.rejected_reason and not res.mask.any()


# ---------------------------------------------------------------- calibration

def test_calibration_from_points_and_uncertainty():
    cal = Calibration.from_points((0, 0), (300, 400), known_length_mm=50.0, point_sigma_px=0.5)
    assert cal.measured_length_px == pytest.approx(500.0)
    assert cal.mm_per_px == pytest.approx(0.1)
    assert cal.relative_uncertainty == pytest.approx(math.sqrt(2) * 0.5 / 500.0)
    assert Calibration.from_dict(cal.to_dict()).mm_per_px == pytest.approx(cal.mm_per_px)


def test_invalid_calibration():
    with pytest.raises(CalibrationError):
        Calibration(known_length_mm=-1.0, measured_length_px=10.0)
    with pytest.raises(CalibrationError):
        Calibration(known_length_mm=1.0, measured_length_px=float("nan"))
    with pytest.raises(CalibrationError):
        Calibration.from_points((1, 1), (1, 1), 5.0)
    assert Calibration(known_length_mm=1.0, measured_length_px=10.0).warnings()


def test_calibration_resolution_mismatch_is_refused(demo_video):
    cal = Calibration(**{**CAL, "image_width": 1920, "image_height": 1080})
    with pytest.raises(CalibrationError, match="Recalibrate"):
        FlameAnalyzer(calibration=cal).analyze(demo_video[0], "MISMATCH")


def test_uncalibrated_results_have_no_physical_units(demo_video):
    res = FlameAnalyzer(AnalysisConfig(max_frames=10)).analyze(demo_video[0], "PX")
    assert all(m.radius_mm is None and m.equivalent_volume_mm3 is None for m in res.measurements)
    assert any(i.code == "uncalibrated" for i in res.issues)


def test_identity_distortion_correction_is_noop():
    dc = DistortionCorrection([[500, 0, 80], [0, 500, 60], [0, 0, 1]], [0, 0, 0, 0, 0])
    img = np.random.default_rng(0).integers(0, 255, (120, 160, 3), dtype=np.uint8)
    assert np.abs(dc.apply(img).astype(int) - img).max() <= 1
    with pytest.raises(CalibrationError):
        DistortionCorrection([[1, 0], [0, 1]], [0, 0, 0, 0])


# ---------------------------------------------------- telemetry, export, control

def test_progress_and_cancellation(demo_video):
    events, cancel = [], threading.Event()
    def on_progress(p):
        events.append(p)
        if p.frames_analyzed == 10:
            cancel.set()
    with pytest.raises(AnalysisCancelled):
        FlameAnalyzer().analyze(demo_video[0], "CANCEL", progress_callback=on_progress, cancel_event=cancel)
    assert len(events) == 10
    assert [e.frames_analyzed for e in events] == list(range(1, 11))
    assert 0 < events[-1].fraction < 0.2


def test_json_and_csv_export(demo_result, tmp_path):
    res, _ = demo_result
    js = res.export_json(tmp_path / "out.json")
    def reject(c):
        raise ValueError(f"non-standard JSON constant {c}")
    data = json.loads(js.read_text(), parse_constant=reject)
    assert data["experiment_id"] == "SYN-DEMO"
    assert len(data["measurements"]) == 150
    assert set(data["field_definitions"]) == set(FIELD_DEFINITIONS)
    assert data["measurements"][10]["contour_px"]
    df = pd.read_csv(res.export_csv(tmp_path / "out.csv"))
    assert list(df.columns) == list(FIELD_DEFINITIONS)
    assert len(df) == 150 and df.radius_mm.notna().sum() == 126


def test_every_field_is_documented():
    from dataclasses import fields as dc_fields
    from backend.vision.cv_engine import FrameMeasurement
    names = {f.name for f in dc_fields(FrameMeasurement)} - {"contour_px"}
    assert names == set(FIELD_DEFINITIONS)
    assert {c for _, c, _ in FIELD_DEFINITIONS.values()} <= {"metadata", "heuristic", "image_derived", "calculated"}


def test_preview_and_annotated_output(demo_video, tmp_path):
    path = demo_video[0]
    overlay, mask, m = FlameAnalyzer().preview_frame(path, 45)
    assert overlay.shape == (480, 640, 3) and mask.shape == (480, 640)
    assert m.status == "detected" and mask.any()
    out = tmp_path / "annotated.mp4"
    FlameAnalyzer(AnalysisConfig(max_frames=15)).analyze(path, "ANN", annotated_output_path=out)
    assert probe_video(out).reported_frame_count == 15
    with pytest.raises(ValueError):
        FlameAnalyzer().preview_frame(path, 10_000)


def test_experiment_id_required(demo_video):
    with pytest.raises(ValueError):
        FlameAnalyzer().analyze(demo_video[0], " ")


def test_config_roundtrip():
    cfg = AnalysisConfig(frame_step=2, segmentation=SegmentationConfig(method=SegmentationMethod.HSV))
    again = AnalysisConfig.from_dict(json.loads(json.dumps(cfg.to_dict())))
    assert again.frame_step == 2 and again.segmentation.method is SegmentationMethod.HSV


def test_data_dictionary_in_sync():
    from pathlib import Path
    text = (Path(__file__).resolve().parents[2] / "DATA_DICTIONARY.md").read_text()
    missing = [k for k in FIELD_DEFINITIONS if f"| `{k}` |" not in text]
    assert not missing, f"DATA_DICTIONARY.md is missing fields: {missing}"


@requires_ffmpeg
def test_interlaced_video_decodes_correctly(demo_video, tmp_path):
    """Regression: OpenCV can return all-black frames for interlaced H.264 (seen on real ACME
    downlink video, and process-state dependent), so FFmpeg is the default decoder."""
    from backend.vision.synthetic import write_interlaced_copy
    path, gt, _ = demo_video
    inter = write_interlaced_copy(path, tmp_path / "SYNTHETIC_interlaced.mp4")
    res = FlameAnalyzer(AnalysisConfig(max_frames=90)).analyze(inter, "AUTO")
    assert res.summary["decoder"] == "ffmpeg"
    d = merged(res, gt)
    np.testing.assert_allclose(d.timestamp_s, d.timestamp_s_true, atol=1e-3)
    vis = d.query("flame_visible")
    assert (vis.status == "detected").all()
    assert (vis.equivalent_radius_px - vis.radius_px).abs().max() < 1.0


def test_blank_decoder_output_is_reported_as_error(tmp_path):
    p = tmp_path / "zeros.avi"
    w = cv2.VideoWriter(str(p), cv2.VideoWriter_fourcc(*"MJPG"), 10, (64, 48))
    for _ in range(5):
        w.write(np.zeros((48, 64, 3), np.uint8))
    w.release()
    res = FlameAnalyzer(AnalysisConfig(decoder="opencv")).analyze(p, "ZEROS")
    assert any(i.code == "all_frames_blank" and i.severity == "error" for i in res.issues)


@pytest.mark.parametrize("decoder", ["opencv", "ffmpeg"])
def test_both_decoders_agree_on_progressive_video(demo_video, decoder):
    if decoder == "ffmpeg" and shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not installed")
    path, gt, _ = demo_video
    res = FlameAnalyzer(AnalysisConfig(decoder=decoder, max_frames=60)).analyze(path, decoder)
    assert res.summary["decoder"] == decoder
    d = merged(res, gt)
    np.testing.assert_allclose(d.timestamp_s, d.timestamp_s_true, atol=1e-3)
    assert (d.equivalent_radius_px - d.radius_px).abs().max() < 1.0


def test_decoder_validation():
    with pytest.raises(ValueError):
        AnalysisConfig(decoder="gstreamer").validate()
