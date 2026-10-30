"""Survival model: parameter recovery on simulated censored data, metrics, leakage guard, artifact."""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import pytest

from backend.ml.survival import AFTModel, concordance_index, kaplan_meier, km_median, simulate_aft
from backend.ml import sflame_model as sm


@pytest.mark.parametrize("dist", ["weibull", "lognormal"])
def test_aft_recovers_parameters_with_censoring(dist):
    rng = np.random.default_rng(0)
    X = rng.normal(size=(600, 2))
    beta = np.array([2.0, 0.5, -0.3])
    t, e = simulate_aft(X, beta, 0.6, 12.0, dist, seed=1)
    assert 0.05 < 1 - e.mean() < 0.4                     # a real share of censoring
    m = AFTModel(dist).fit(X, t, e)
    assert m.converged_
    se = np.sqrt(np.diag(m.cov_))
    assert np.all(np.abs(m.coef_ - beta) < 3.5 * se[:-1])
    assert m.sigma_ == pytest.approx(0.6, rel=0.12)


def test_ignoring_censoring_biases_lifetimes_low():
    rng = np.random.default_rng(2)
    X = rng.normal(size=(800, 1))
    t, e = simulate_aft(X, np.array([2.5, 0.0]), 0.5, 10.0, "lognormal", seed=3)
    naive = np.exp(np.mean(np.log(t)))                   # treats censored times as lifetimes
    m = AFTModel("lognormal").fit(X, t, e)
    assert naive < math.exp(2.5) * 0.95                  # biased low
    assert m.coef_[0] == pytest.approx(2.5, abs=0.06)    # AFT recovers the true log-scale intercept


def test_kaplan_meier_and_concordance():
    times, surv = kaplan_meier(np.array([1, 2, 2, 3, 4.0]), np.array([1, 1, 0, 1, 0]))
    np.testing.assert_allclose(times, [1, 2, 3])
    np.testing.assert_allclose(surv, [0.8, 0.6, 0.3])
    assert km_median(np.array([1, 2, 2, 3, 4.0]), np.array([1, 1, 0, 1, 0])) == 3
    t = np.array([1.0, 2, 3, 4])
    e = np.array([1, 1, 1, 0], bool)
    assert concordance_index(t, e, t) == 1.0
    assert concordance_index(t, e, -t) == 0.0
    assert concordance_index(t, e, np.ones(4)) == 0.5


def test_aft_rejects_bad_inputs():
    with pytest.raises(ValueError):
        AFTModel("gamma").fit(np.zeros((3, 0)), np.ones(3), np.ones(3, bool))
    with pytest.raises(ValueError):
        AFTModel().fit(np.zeros((3, 0)), np.array([1.0, -1, 2]), np.ones(3, bool))


def _synthetic_table(n_days=8, per_day=10, seed=0):
    """A SYNTHETIC test-point table with the columns used by prepare() (not NASA data)."""
    rng = np.random.default_rng(seed)
    rows = []
    for d in range(n_days):
        h2 = rng.choice([0.0, 0.3, 0.45])
        he = int(d >= n_days // 2)
        for k in range(per_day):
            ch4 = 0.45 - h2 if h2 < 0.45 else 0.0
            flow = rng.uniform(0.1, 1.0)
            mu = 2.0 + 1.5 * h2 - 0.6 * he - 0.05 * k
            t = math.exp(mu + 0.5 * rng.normal())
            event = t < 30
            rows.append({"test_point": f"{20000 + d}A{k}", "test_day": 20000 + d, "flow_programme": "constant",
                         "outcome": "extinguished" if event else "burning_at_fuel_off",
                         "flame_duration_s": min(t, 30.0), "initial_x_H2": h2, "initial_x_CH4": ch4,
                         "initial_x_C2H4": 0.0, "initial_total_slpm": flow, "atmosphere_inert": "He" if he else "N2",
                         "o2_nominal": 0.21, "test_order_in_day": k + 1})
    rows.append({**rows[0], "test_point": "RAMP", "flow_programme": "ramp_up"})
    rows.append({**rows[0], "test_point": "AMB", "outcome": "ambiguous_nasa_extinction"})
    return pd.DataFrame(rows)


def test_prepare_selects_population_and_never_uses_forbidden_columns():
    d = sm.prepare(_synthetic_table())
    assert "RAMP" not in set(d.test_point) and "AMB" not in set(d.test_point)
    for feats in sm.CANDIDATES.values():
        assert not set(feats) & sm.FORBIDDEN_FEATURES
    assert set(d.group) == {str(20000 + i) for i in range(8)}


def test_leave_one_day_out_has_no_day_leakage(monkeypatch):
    seen = []
    real_fit = sm._fit

    def spy(train, feats, dist, l2):
        seen.append(set(train["group"]))
        return real_fit(train, feats, dist, l2)

    monkeypatch.setattr(sm, "_fit", spy)
    d = sm.prepare(_synthetic_table())
    sm.leave_one_day_out(d, ["x_H2", "he_atmosphere"], "lognormal")
    groups = sorted(d.group.unique())
    assert len(seen) == len(groups)
    for g, train_groups in zip(groups, seen):
        assert g not in train_groups


def test_train_artifact_roundtrip_reproducible_and_ood(tmp_path):
    p = tmp_path / "table.csv"
    _synthetic_table().to_csv(p, index=False)
    a1 = sm.train(p, tmp_path / "m1")
    a2 = sm.train(p, tmp_path / "m2")
    assert a1["coef"] == a2["coef"] and a1["model_version"] == a2["model_version"]   # reproducible
    assert a1["interval_inflation"]["coverage_after"] >= 0.8 or a1["interval_inflation"]["factor"] == 5.0
    m = sm.LifetimeModel.load(tmp_path / "m1")
    x = {f: float(np.mean([r["min"], r["max"]])) for f, r in a1["feature_ranges"].items()}
    for f, r in a1["feature_ranges"].items():
        if r.get("observed_values"):
            x[f] = r["observed_values"][0]
    out = m.predict(x)
    assert out["quantity_class"] == "predicted" and out["warnings"] == []
    assert out["interval"]["lower_s"] < out["median_lifetime_s"] < out["interval"]["upper_s"]
    far = dict(x, **{next(iter(x)): 99.0})
    assert m.predict(far)["warnings"]
    with pytest.raises(ValueError):
        m.predict({k: v for k, v in list(x.items())[1:]})               # missing feature
    with pytest.raises(ValueError):
        m.predict(dict(x, flame_duration_s=3.0))                         # post-ignition quantity
    json.loads((tmp_path / "m1" / "feature_schema.json").read_text())
    with pytest.raises(ValueError):
        sm.LifetimeModel({"schema": "other"})
