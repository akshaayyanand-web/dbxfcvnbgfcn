"""Physics, uncertainty and validation tests (analytical references, no video I/O)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from backend.physics import validation as pv
from backend.physics.physics_engine import (
    DerivativeConfig,
    circle_area,
    circularity,
    eccentricity,
    equivalent_radius_from_area,
    equivalent_spherical_volume,
    estimate_extinction,
    finite_difference_derivatives,
    local_polynomial_kinematics,
    split_segments,
)
from backend.physics.uncertainty import (
    calibration_scale,
    circle_area_sigma,
    px_to_physical,
    radius_sigma_from_boundary,
    sphere_volume_sigma,
)


# ------------------------------------------------------------------- geometry

def test_circle_area_and_equivalent_radius_roundtrip():
    assert circle_area(2.0) == pytest.approx(4.0 * math.pi)
    assert equivalent_radius_from_area(circle_area(7.3)) == pytest.approx(7.3)
    with pytest.raises(ValueError):
        equivalent_radius_from_area(-1.0)


def test_equivalent_spherical_volume():
    assert equivalent_spherical_volume(3.0) == pytest.approx(36.0 * math.pi)


def test_circularity_and_eccentricity():
    r = 5.0
    assert circularity(math.pi * r * r, 2 * math.pi * r) == pytest.approx(1.0)
    assert circularity(1.0, 4.0) == pytest.approx(math.pi / 4)  # unit square
    assert math.isnan(circularity(1.0, 0.0))
    assert eccentricity(10.0, 10.0) == pytest.approx(0.0)
    assert eccentricity(5.0, 3.0) == pytest.approx(0.8)
    assert eccentricity(3.0, 5.0) == pytest.approx(0.8)  # order-independent


# ---------------------------------------------------------------- uncertainty

def test_calibration_scale_quadrature():
    s, ss = calibration_scale(10.0, 0.1, 100.0, 1.0)
    assert s == pytest.approx(0.1)
    assert ss == pytest.approx(0.1 * math.hypot(0.01, 0.01))
    with pytest.raises(ValueError):
        calibration_scale(0.0, 0.0, 100.0, 1.0)
    with pytest.raises(ValueError):
        calibration_scale(10.0, -1.0, 100.0, 1.0)


@pytest.mark.parametrize("power", [1, 2, 3])
def test_px_to_physical_separates_random_and_systematic(power):
    q = px_to_physical(50.0, 0.5, 0.1, 0.002, power)
    assert q.value == pytest.approx(50.0 * 0.1**power)
    assert q.random == pytest.approx(0.5 * 0.1**power)
    assert q.systematic == pytest.approx(power * q.value * 0.02)
    assert q.total == pytest.approx(math.hypot(q.random, q.systematic))


def test_volume_sigma_matches_numerical_derivative():
    r, sr = 4.0, 0.01
    numeric = (equivalent_spherical_volume(r + 1e-6) - equivalent_spherical_volume(r - 1e-6)) / 2e-6 * sr
    assert sphere_volume_sigma(r, sr) == pytest.approx(numeric, rel=1e-6)
    assert circle_area_sigma(r, sr) == pytest.approx(2 * math.pi * r * sr)


def test_volume_sigma_first_order_against_monte_carlo():
    rng = np.random.default_rng(0)
    r, sr = 10.0, 0.1  # 1 % relative: first order should agree within a few %
    v = 4 / 3 * np.pi * rng.normal(r, sr, 200_000) ** 3
    assert np.std(v) == pytest.approx(sphere_volume_sigma(r, sr), rel=0.03)


def test_radius_sigma_from_boundary_reduces_to_edge_sigma_for_circle():
    r = 20.0
    assert radius_sigma_from_boundary(2 * math.pi * r, r, 0.7) == pytest.approx(0.7)
    assert math.isnan(radius_sigma_from_boundary(10.0, 0.0, 1.0))


# ----------------------------------------------------------------- kinematics

def test_local_polynomial_exact_for_quadratic_on_irregular_timestamps():
    rng = np.random.default_rng(1)
    t = np.cumsum(rng.uniform(0.02, 0.05, 60))
    y = 3.0 + 2.0 * t - 4.0 * t**2
    k = local_polynomial_kinematics(t, y, 0.0, DerivativeConfig(window=7, polyorder=2))
    np.testing.assert_allclose(k.smoothed, y, atol=1e-9)
    np.testing.assert_allclose(k.first_derivative, 2.0 - 8.0 * t, atol=1e-7)
    np.testing.assert_allclose(k.second_derivative, -8.0, atol=1e-5)


def test_local_polynomial_does_not_bridge_gaps_or_fill_missing():
    t = np.concatenate((np.arange(0, 1, 0.1), np.arange(3, 4, 0.1)))
    y = 5.0 * t
    y[4] = np.nan
    k = local_polynomial_kinematics(t, y, 0.1, DerivativeConfig(window=5, polyorder=2))
    assert np.isnan(k.first_derivative[4])           # missing sample stays missing
    assert k.segment_id[4] == -1
    assert len(set(k.segment_id[k.segment_id >= 0])) == 2  # time gap creates two segments
    np.testing.assert_allclose(k.first_derivative[np.isfinite(y)], 5.0, atol=1e-9)


def test_short_segment_reports_note_and_nan():
    t = np.array([0.0, 0.1, 5.0, 5.1, 5.2, 5.3, 5.4])
    k = local_polynomial_kinematics(t, t * 2, 0.1, DerivativeConfig(window=5, polyorder=2))
    assert np.isnan(k.first_derivative[:2]).all()
    assert any("too short" in n for n in k.notes)


def test_derivative_sigma_matches_monte_carlo():
    rng = np.random.default_rng(2)
    t = np.cumsum(rng.uniform(0.02, 0.04, 40))
    truth = 1.0 + 0.5 * t
    sigma = 0.05
    cfg = DerivativeConfig(window=9, polyorder=2)
    predicted = local_polynomial_kinematics(t, truth, sigma, cfg).first_derivative_sigma[20]
    draws = [local_polynomial_kinematics(t, truth + rng.normal(0, sigma, t.size), sigma, cfg).first_derivative[20]
             for _ in range(1500)]
    assert np.std(draws) == pytest.approx(predicted, rel=0.08)


def test_finite_differences_nonuniform():
    t = np.array([0.0, 0.1, 0.25, 0.3, 0.5, 0.65])
    d1, d2 = finite_difference_derivatives(t, t**2)
    np.testing.assert_allclose(d1, 2 * t, atol=1e-12)
    np.testing.assert_allclose(d2, 2.0, atol=1e-9)
    with pytest.raises(ValueError):
        finite_difference_derivatives(np.array([0.0, 0.0, 1.0]), np.zeros(3))
    with pytest.raises(ValueError):
        finite_difference_derivatives(t, np.array([0, np.nan, 0, 0, 0, 0.0]))


def test_split_segments():
    t = np.array([0, 1, 2, 10, 11, 12], dtype=float)
    seg = split_segments(t, np.ones(6, bool), 3.0)
    assert list(seg) == [0, 0, 0, 1, 1, 1]


def test_derivative_config_validation():
    for bad in (DerivativeConfig(window=4), DerivativeConfig(window=5, polyorder=5), DerivativeConfig(max_gap_factor=1)):
        with pytest.raises(ValueError):
            bad.validate()


# ----------------------------------------------------------------- extinction

def test_extinction_states():
    t = np.arange(20) * 0.1
    det = np.ones(20, bool)
    assert estimate_extinction(t, det).status == "flame_present_at_end"
    assert estimate_extinction(t, np.zeros(20, bool)).status == "never_detected"
    det[17:] = False
    assert estimate_extinction(t, det, 5).status == "insufficient_trailing_frames"
    det[10:] = False
    est = estimate_extinction(t, det, 5)
    assert est.status == "observed"
    assert est.time_s == pytest.approx(0.95)
    assert est.uncertainty_s == pytest.approx(0.05)


# ----------------------------------------------------------------- validation

def test_timestamp_validation():
    codes = {i.code for i in pv.validate_timestamps(np.array([0.0, 0.1, 0.1, 0.3]))}
    assert "timestamps_not_increasing" in codes
    codes = {i.code for i in pv.validate_timestamps(np.array([0.0, 0.1, 0.2, 0.4, 0.5]))}
    assert codes == {"variable_frame_interval"}
    assert pv.validate_timestamps(np.arange(10) / 30.0) == []
    assert pv.validate_timestamps(np.array([]))[0].severity == "error"


def test_physical_plausibility_checks():
    idx = np.arange(3)
    issues = pv.check_expansion_velocity(np.array([10.0, 9000.0, np.nan]), idx, 5000.0)
    assert len(issues) == 1 and issues[0].frame_index == 1
    assert pv.check_radius_bounds(np.array([-1.0, 5.0, 1e6]), 100, 100, idx)[0].code == "negative_radius"
    assert len(pv.check_radius_bounds(np.array([-1.0, 5.0, 1e6]), 100, 100, idx)) == 2
    assert pv.check_relative_uncertainty(np.array([1.0, 1.0]), np.array([0.5, 0.5]), "r")[0].severity == "warning"
