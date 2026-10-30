"""Flame-lifetime model for NASA ACME s-Flame constant-flow tests.

Usage:
    python -m backend.ml.sflame_model train --data data/processed/sflame_test_points.csv --out models/sflame_lifetime
    python -m backend.ml.sflame_model predict --model models/sflame_lifetime --x-c2h4 0.25 --total-slpm 0.3 ...

Scope (SCIENTIFIC_ASSUMPTIONS.md §9):
* Population: constant-flow s-Flame tests with a sustained flame (OH* PMT); ramped tests excluded,
  because their lifetime is set by the commanded ramp.
* Target: flame lifetime (emission onset to emission end) in seconds, right-censored when the flame
  was still burning at fuel shut-off.
* Features: only quantities fixed *before* ignition (leakage guard ``FORBIDDEN_FEATURES``).
* Validation: leave-one-test-day-out. Tests on a day share bottle, atmosphere and vitiation history.
* Model: AFT (Weibull or log-normal) with candidate feature sets, compared with an intercept-only
  baseline. The artifact is plain JSON, so no executable deserialisation is needed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from backend.ml.survival import AFTModel, _eps_quantile, concordance_index, km_median

MODEL_SCHEMA = "flame-in-freefall/sflame-lifetime-model/v1"
POPULATION = "constant-flow s-Flame tests with a sustained OH* flame (PSI-23)"

# Quantities measured during/after the burn: never allowed as features (target leakage).
FORBIDDEN_FEATURES = {
    "flame_on_utc", "flame_off_utc", "flame_duration_s", "ignition_delay_s", "pmt1_peak_v",
    "pmt1_baseline_v", "outcome", "event_observed", "total_slpm_at_extinction",
    "fuel_species_fraction_at_extinction", "detection_lag_s", "time_since_last_flow_change_s",
    "fuel_off_utc", "fuel_duration_s", "nasa_stop_reason", "nasa_extinction_detected_utc",
    "pta3_kpa_at_ignition_low_confidence", "quality_flags",
}


@dataclass(frozen=True)
class Feature:
    name: str
    description: str
    unit: str


FEATURES = {
    "x_H2": Feature("x_H2", "H2 mole fraction in the delivered fuel-line mixture (nominal)", "-"),
    "x_CH4": Feature("x_CH4", "CH4 mole fraction in the delivered fuel-line mixture (nominal)", "-"),
    "x_C2H4": Feature("x_C2H4", "C2H4 mole fraction in the delivered fuel-line mixture (nominal)", "-"),
    "log_total_slpm": Feature("log_total_slpm", "ln of total fuel-line flow, indicated N2-equivalent SLPM", "ln(SLPM)"),
    "he_atmosphere": Feature("he_atmosphere", "1 if the chamber inert was helium (round 2), else 0", "-"),
    "o2_30": Feature("o2_30", "1 if nominal chamber O2 was ~30 %, 0 if ~21 % (requires known O2)", "-"),
    "test_order_in_day": Feature("test_order_in_day", "order of the test within its day (vitiation proxy)", "-"),
}

CANDIDATES = {
    "baseline_intercept_only": [],
    "fuel_composition": ["x_H2", "x_CH4", "x_C2H4"],
    "fuel_and_flow": ["x_H2", "x_CH4", "x_C2H4", "log_total_slpm"],
    "fuel_flow_atmosphere": ["x_H2", "x_CH4", "x_C2H4", "log_total_slpm", "he_atmosphere"],
    "fuel_flow_atmosphere_order": ["x_H2", "x_CH4", "x_C2H4", "log_total_slpm", "he_atmosphere", "test_order_in_day"],
    "with_o2": ["x_H2", "x_CH4", "x_C2H4", "log_total_slpm", "he_atmosphere", "o2_30"],
}


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Select the modelling population and derive features. Never uses forbidden columns as inputs."""
    d = df[(df["flow_programme"] == "constant") & df["outcome"].isin(["extinguished", "burning_at_fuel_off"])].copy()
    d = d[d["flame_duration_s"] > 0]
    d["time_s"] = d["flame_duration_s"].astype(float)
    d["event"] = d["outcome"].eq("extinguished")
    d["x_H2"], d["x_CH4"], d["x_C2H4"] = d["initial_x_H2"], d["initial_x_CH4"], d["initial_x_C2H4"]
    d["log_total_slpm"] = np.log(d["initial_total_slpm"].astype(float))
    d["he_atmosphere"] = d["atmosphere_inert"].eq("He").astype(float)
    d["o2_30"] = np.where(d["o2_nominal"].isna(), np.nan, (d["o2_nominal"] > 0.25).astype(float))
    d["group"] = d["test_day"].astype(str)
    return d.reset_index(drop=True)


@dataclass
class Standardizer:
    mean: np.ndarray
    std: np.ndarray

    @classmethod
    def fit(cls, X: np.ndarray) -> "Standardizer":
        sd = X.std(axis=0)
        return cls(X.mean(axis=0), np.where(sd > 0, sd, 1.0))

    def transform(self, X: np.ndarray) -> np.ndarray:
        return (X - self.mean) / self.std


def _fit(d: pd.DataFrame, feats: list[str], dist: str, l2: float) -> tuple[AFTModel, Standardizer | None]:
    if feats:
        X = d[feats].to_numpy(float)
        st = Standardizer.fit(X)
        return AFTModel(dist, l2=l2).fit(st.transform(X), d["time_s"], d["event"]), st
    return AFTModel(dist, l2=l2).fit(np.empty((len(d), 0)), d["time_s"], d["event"]), None


def _predict(m: AFTModel, st: Standardizer | None, d: pd.DataFrame, feats: list[str]) -> np.ndarray:
    X = st.transform(d[feats].to_numpy(float)) if feats else np.empty((len(d), 0))
    return m.predict_quantiles(X, (0.1, 0.5, 0.9))


def leave_one_day_out(d: pd.DataFrame, feats: list[str], dist: str, l2: float = 0.0) -> dict:
    """Pooled out-of-day predictions and metrics (C-index, events-only log error, 80 % interval coverage)."""
    preds = np.full((len(d), 3), np.nan)
    failures = 0
    for g in sorted(d["group"].unique()):
        test = d["group"] == g
        train = d[~test]
        if train["event"].sum() < 2:
            failures += 1
            continue
        m, st = _fit(train, feats, dist, l2)
        if not m.converged_:
            failures += 1
        preds[test.to_numpy()] = _predict(m, st, d[test], feats)
    t, e = d["time_s"].to_numpy(), d["event"].to_numpy()
    med = preds[:, 1]
    # Within-day ranking: concordance computed separately inside each held-out day, averaged
    # (weighted by comparable pairs). Unaffected by between-fold intercept shifts.
    within_num = within_den = 0.0
    for g in d["group"].unique():
        idx = (d["group"] == g).to_numpy() & np.isfinite(med)
        tt, ee, pp = t[idx], e[idx], med[idx]
        pairs = sum(int(np.sum(tt > tt[i])) for i in np.flatnonzero(ee))
        if pairs:
            within_num += concordance_index(tt, ee, pp) * pairs
            within_den += pairs
    ev = e & np.isfinite(med)
    cens = ~e & np.isfinite(med)
    inside = (t >= preds[:, 0]) & (t <= preds[:, 2])
    return {
        "distribution": dist,
        "features": feats,
        "n": int(len(d)),
        "n_events": int(e.sum()),
        "n_groups": int(d["group"].nunique()),
        "c_index": concordance_index(t[np.isfinite(med)], e[np.isfinite(med)], med[np.isfinite(med)]),
        "c_index_within_day": within_num / within_den if within_den else math.nan,
        "events_median_abs_log_error": float(np.median(np.abs(np.log(med[ev]) - np.log(t[ev])))),
        "events_median_abs_error_s": float(np.median(np.abs(med[ev] - t[ev]))),
        "events_80pct_interval_coverage": float(np.mean(inside[ev])),
        "censored_upper_bound_consistent": float(np.mean(preds[cens, 2] >= t[cens])) if cens.any() else math.nan,
        "fold_failures": failures,
        "_pred": preds,
    }


def calibrate_interval_inflation(cv_pred: np.ndarray, d: pd.DataFrame, model: AFTModel, level: float = 0.8) -> dict:
    """Smallest factor k >= 1 on sigma such that held-out-day events fall in the central ``level`` interval
    at the nominal rate.

    Uses the leave-one-day-out medians: mu = log(median) - sigma * eps_0.5, and an event is covered when
    ``k * eps_lo <= (log t - mu) / sigma <= k * eps_hi``. Censored tests are not used (their true lifetime
    is unknown). Coverage before and after is reported.
    """
    lo_q, hi_q = (1 - level) / 2, 1 - (1 - level) / 2
    eps_lo, eps_mid, eps_hi = (float(_eps_quantile(q, model.distribution)) for q in (lo_q, 0.5, hi_q))
    sigma = model.sigma_
    ev = d["event"].to_numpy() & np.isfinite(cv_pred[:, 1])
    u = (np.log(d["time_s"].to_numpy()[ev]) - (np.log(cv_pred[ev, 1]) - sigma * eps_mid)) / sigma

    def coverage(k: float) -> float:
        return float(np.mean((u >= k * eps_lo) & (u <= k * eps_hi)))

    k = 1.0
    while coverage(k) < level and k < 5.0:
        k = round(k + 0.01, 2)
    return {"level": level, "factor": k, "coverage_before": coverage(1.0), "coverage_after": coverage(k),
            "n_events": int(ev.sum()), "method": "leave-one-day-out event residuals, sigma scaled by k"}


def _ranges(d: pd.DataFrame, feats: list[str]) -> dict:
    return {f: {"min": float(d[f].min()), "max": float(d[f].max()),
                "observed_values": sorted(map(float, d[f].unique())) if d[f].nunique() <= 6 else None} for f in feats}


def train(data_csv: Path, out_dir: Path, l2: float = 0.0) -> dict:
    raw = pd.read_csv(data_csv)
    d_all = prepare(raw)
    d_o2 = d_all[d_all["o2_30"].notna()].reset_index(drop=True)
    results = []
    for name, feats in CANDIDATES.items():
        for dist in ("weibull", "lognormal"):
            d = d_o2 if "o2_30" in feats else d_all
            r = leave_one_day_out(d, feats, dist, l2)
            r["candidate"] = name
            results.append(r)
    # Fair comparison of the O2 model against the same feature set without O2 on identical rows.
    for dist in ("weibull", "lognormal"):
        r = leave_one_day_out(d_o2, CANDIDATES["fuel_flow_atmosphere"], dist, l2)
        r["candidate"] = "fuel_flow_atmosphere(O2-known rows)"
        results.append(r)

    eligible = [r for r in results if "O2-known" not in r["candidate"] and r["candidate"] != "with_o2"
                and r["fold_failures"] == 0 and r["features"]]
    best = max(eligible, key=lambda r: (round(r["c_index"], 3), -r["events_median_abs_log_error"]))
    feats, dist = best["features"], best["distribution"]
    model, st = _fit(d_all, feats, dist, l2)
    inflation = calibrate_interval_inflation(best["_pred"], d_all, model, level=0.8)
    baseline = next(r for r in results if r["candidate"] == "baseline_intercept_only" and r["distribution"] == dist)

    raw_bytes = Path(data_csv).read_bytes()
    artifact = {
        "schema": MODEL_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_version": "sflame-lifetime-" + hashlib.sha256(
            json.dumps([feats, dist, model.coef_.tolist(), model.log_sigma_]).encode()).hexdigest()[:12],
        "population": POPULATION,
        "target": {"name": "flame_lifetime_s", "definition": "OH* emission onset to emission end",
                   "censoring": "right-censored when burning at fuel shut-off"},
        "training_data": {"file": Path(data_csv).name, "sha256": hashlib.sha256(raw_bytes).hexdigest(),
                          "n": model.n_, "n_events": model.n_events_, "test_days": sorted(d_all["group"].unique()),
                          "source": "NASA PSI-23 ACME s-Flame, CC0-1.0, DOI 10.60555/k57n-p030"},
        "distribution": dist,
        "l2": l2,
        "features": [FEATURES[f].__dict__ for f in feats],
        "standardizer": {"mean": st.mean.tolist(), "std": st.std.tolist()},
        "coef": model.coef_.tolist(),
        "log_sigma": model.log_sigma_,
        "cov": model.cov_.tolist(),
        "converged": model.converged_,
        "interval_inflation": inflation,
        "coefficient_table_standardized": model.summary(feats),
        "feature_ranges": _ranges(d_all, feats),
        "validation": {
            "scheme": "leave-one-test-day-out",
            "selected": {k: v for k, v in best.items() if not k.startswith("_")},
            "baseline_intercept_only": {k: v for k, v in baseline.items() if not k.startswith("_")},
            "baseline_note": ("A constant predictor has C-index 0.5 by definition. Its pooled leave-one-day-out "
                              "C-index is below 0.5 because each fold's intercept is fitted without the held-out "
                              "day (long-lived days get lower predictions); compare error metrics, not C, with it."),
            "all_candidates": [{k: v for k, v in r.items() if not k.startswith("_")} for r in results],
        },
        "limitations": [
            "Associational model of the s-Flame constant-flow test matrix; not a causal or physics model.",
            "Compositions and flows are nominal (no gas conversion factors).",
            "O2 is unknown for mixed-O2 days, so the selected model does not use O2.",
            "Possible informative censoring: some flames were stopped by a burner temperature limit.",
            "Outside the training ranges (feature_ranges), predictions are extrapolations and are flagged.",
            "On held-out test days the median lifetime is typically off by a factor of ~2; the model ranks "
            "conditions (C-index ~0.7) better than it predicts absolute lifetimes.",
            "Prediction intervals are widened by a factor calibrated on the same leave-one-day-out "
            "predictions used for model selection (in-sample calibration; mildly optimistic).",
        ],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "model.json").write_text(json.dumps(artifact, indent=2, default=_json_default))
    (out_dir / "evaluation_metrics.json").write_text(json.dumps(artifact["validation"], indent=2, default=_json_default))
    (out_dir / "feature_schema.json").write_text(json.dumps(
        {"features": artifact["features"], "ranges": artifact["feature_ranges"],
         "forbidden_inputs": sorted(FORBIDDEN_FEATURES)}, indent=2, default=_json_default))
    preds = pd.DataFrame(best["_pred"], columns=["pred_q10_s", "pred_median_s", "pred_q90_s"])
    pd.concat([d_all[["test_point", "group", "time_s", "event"] + feats], preds], axis=1).to_csv(
        out_dir / "cv_predictions.csv", index=False)
    return artifact


def _json_default(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, float) and not math.isfinite(o):
        return None
    raise TypeError(type(o))


# ------------------------------------------------------------------------- inference


class LifetimeModel:
    """Load a JSON artifact and predict lifetime quantiles with out-of-range warnings."""

    def __init__(self, artifact: dict):
        if artifact.get("schema") != MODEL_SCHEMA:
            raise ValueError("Unsupported model artifact schema.")
        self.a = artifact
        self.feats = [f["name"] for f in artifact["features"]]
        self.model = AFTModel(artifact["distribution"], l2=artifact.get("l2", 0.0))
        self.model.coef_ = np.array(artifact["coef"], float)
        self.model.log_sigma_ = float(artifact["log_sigma"])
        cov = np.array(artifact["cov"], dtype=float)
        self.model.cov_ = cov
        self.st = Standardizer(np.array(artifact["standardizer"]["mean"]), np.array(artifact["standardizer"]["std"]))
        self.inflation = float((artifact.get("interval_inflation") or {}).get("factor", 1.0))

    @classmethod
    def load(cls, model_dir: str | Path) -> "LifetimeModel":
        return cls(json.loads((Path(model_dir) / "model.json").read_text()))

    def check_inputs(self, x: dict[str, float]) -> list[str]:
        warnings = []
        for f in self.feats:
            if f not in x or x[f] is None or not math.isfinite(float(x[f])):
                raise ValueError(f"Missing or non-finite input: {f}")
            r = self.a["feature_ranges"][f]
            v = float(x[f])
            if v < r["min"] - 1e-9 or v > r["max"] + 1e-9:
                warnings.append(f"{f}={v:g} is outside the training range [{r['min']:g}, {r['max']:g}]: extrapolation")
            elif r.get("observed_values") and min(abs(v - o) for o in r["observed_values"]) > 1e-6:
                warnings.append(f"{f}={v:g} was never observed in training (observed: {r['observed_values']})")
        unknown = set(x) - set(self.feats)
        forbidden = unknown & FORBIDDEN_FEATURES
        if forbidden:
            raise ValueError(f"Post-ignition quantities are not valid inputs: {sorted(forbidden)}")
        return warnings

    def predict(self, x: dict[str, float], interval: float = 0.8) -> dict:
        warnings = self.check_inputs(x)
        X = self.st.transform(np.array([[float(x[f]) for f in self.feats]]))
        lo = (1 - interval) / 2
        median = float(self.model.predict_quantiles(X, (0.5,))[0, 0])
        # Interval: predictive distribution with sigma widened by the cross-validated inflation factor,
        # centred on the MLE median so the point prediction is unchanged by the widening.
        widened = AFTModel(self.model.distribution)
        widened.coef_ = self.model.coef_.copy()
        widened.log_sigma_ = self.model.log_sigma_ + math.log(self.inflation)
        widened.cov_ = self.model.cov_
        shift = (math.log(median) - math.log(float(widened.predict_quantiles(X, (0.5,))[0, 0])))
        q = widened.predictive_quantiles(X, (lo, 0.5, 1 - lo)) * math.exp(shift)
        q = q[0]
        return {
            "quantity_class": "predicted",
            "model_version": self.a["model_version"],
            "median_lifetime_s": median,
            "interval": {"level": interval, "lower_s": float(q[0]), "upper_s": float(q[2]),
                         "includes_parameter_uncertainty": True,
                         "sigma_inflation_cross_validated": self.inflation},
            "warnings": warnings,
            "population": self.a["population"],
            "limitations": self.a["limitations"],
        }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("train")
    t.add_argument("--data", type=Path, default=Path("data/processed/sflame_test_points.csv"))
    t.add_argument("--out", type=Path, default=Path("models/sflame_lifetime"))
    t.add_argument("--l2", type=float, default=0.0)
    pr = sub.add_parser("predict")
    pr.add_argument("--model", type=Path, default=Path("models/sflame_lifetime"))
    pr.add_argument("--inputs", type=str, required=True, help='JSON, e.g. \'{"x_C2H4": 0.2, ...}\'')
    ns = p.parse_args()
    if ns.cmd == "train":
        a = train(ns.data, ns.out, ns.l2)
        v = a["validation"]
        print(json.dumps({"selected": {k: v["selected"][k] for k in ("candidate", "distribution", "c_index",
                                                                    "events_median_abs_log_error",
                                                                    "events_80pct_interval_coverage")},
                          "reference_c_index_constant_predictor": 0.5,
                          "baseline_events_median_abs_log_error":
                              v["baseline_intercept_only"]["events_median_abs_log_error"],
                          "interval_inflation": a["interval_inflation"],
                          "model_version": a["model_version"]}, indent=2, default=_json_default))
    else:
        print(json.dumps(LifetimeModel.load(ns.model).predict(json.loads(ns.inputs)), indent=2))


if __name__ == "__main__":
    main()
