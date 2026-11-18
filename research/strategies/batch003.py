"""STRAT-0201..0300. Testable: crack spread (21), location basis (24), currency carry (26), FX value (27), FX fixing window (28, intraday, run_fix.py),
Treasury term premium (30). Blocked: crush (22), spark (23), futures-curve carry (25), FX intervention (29)."""
import numpy as np, pandas as pd
from strategies.lib import *
from engine import P, fx_rate_diff
from data import _fred
FORMS = ["event-triggered", "cross-sectional", "time-series", "lead-lag", "regime-conditioned", "term-structure", "flow-based", "relative-value", "volatility-based", "execution-aware"]
def term_gate(idx, side):
    sl = P["macro"]["T10Y3M"]; g = sl.reindex(idx, method="ffill").shift(1); return (g > 0) if side == "steep" else (g <= 0)
def zs(R, pairs, N):
    p = np.log(px(R)); return {(a, b): ((p[a] - p[b]) - (p[a] - p[b]).rolling(N).mean()) / (p[a] - p[b]).rolling(N).std() for a, b in pairs}
def to_w(R, sig):
    w = pd.DataFrame(0.0, index=R.index, columns=R.columns)
    for (a, b), s in sig.items(): s = s.fillna(0); w[a] += s / len(sig); w[b] -= s / len(sig)
    return w
def zrev(R, pairs, N=60, k=2.0, H=10):
    return {ab: hold((-(z > k).astype(int) + (z < -k).astype(int)).to_frame("x"), H)["x"] for ab, z in zs(R, pairs, N).items()}
def season(idx, months): return pd.Series(idx.month.isin(months), index=idx)

def spread_family(off, fam, pairs, seasonal, lead_leg):
    """seasonal: {pair: (long_months, short_months)}; lead_leg: which leg leads (crude for cracks, Brent for WTI-Brent)."""
    out = []; G = {"N": [60, 120], "k": [1.5, 2.5], "H": [10]}
    for j, form in enumerate(FORMS):
        sid = f"STRAT-{off + j + 1:04d}"; g = dict(G)
        if form == "event-triggered":
            g = {"x": [1]}
            def fn(R, p, pairs=pairs):
                sig = {}
                for ab in pairs:
                    lm, sm = seasonal.get(ab, ((), ()))
                    sig[ab] = season(R.index, lm).astype(float) - season(R.index, sm).astype(float)
                return to_w(R, sig)
            d = "seasonal calendar: long the spread in its strong-demand months, short in its weak months (fixed from industry seasonality, not fitted)"
        elif form == "cross-sectional":
            def fn(R, p, pairs=pairs):
                Z = pd.DataFrame(zs(R, pairs, p["N"])); pick = Z.abs().fillna(-1).idxmax(axis=1)
                return to_w(R, {ab: (-np.sign(Z[ab]) * (pick == ab) * (Z[ab].abs() > p["k"])).astype(float) for ab in Z.columns})
            d = "trade only the most stretched spread of the set each day"
        elif form == "time-series": fn = lambda R, p, pairs=pairs: to_w(R, zrev(R, pairs, **p)); d = "log-spread z-score beyond k: fade it, hold H days"
        elif form == "lead-lag":
            g = {"N": [1, 5, 10]}
            fn = lambda R, p, pairs=pairs: to_w(R, {(a, b): np.sign(R[lead_leg(a, b)].rolling(p["N"]).sum()) * (1 if lead_leg(a, b) == b else -1) for a, b in pairs})
            d = "leading leg's last-N-day move predicts the lagging leg catching up (spread long the laggard's direction)"
        elif form == "regime-conditioned": g["reg"] = ["calm", "turbulent"]; fn = lambda R, p, pairs=pairs: to_w(R, zrev(R, pairs, p["N"], p["k"], p["H"])).mul(regime(R, p["reg"]).astype(float), axis=0); d = "z-reversion in one regime"
        elif form == "term-structure": g["side"] = ["steep", "inverted"]; fn = lambda R, p, pairs=pairs: to_w(R, zrev(R, pairs, p["N"], p["k"], p["H"])).mul(term_gate(R.index, p["side"]).astype(float), axis=0); d = "z-reversion gated by yield-curve sign (futures curves unavailable)"
        elif form == "flow-based": out.append(dict(id=sid, family=fam, form=form, blocked="needs futures volume / open interest or CFTC positioning; spot series have no flow data")); continue
        elif form == "relative-value": g = {"N": [60, 120, 250]}; fn = lambda R, p, pairs=pairs: to_w(R, {ab: np.sign(z) for ab, z in zs(R, pairs, p["N"]).items()}); d = "spread momentum (sign of z) - the opposite hypothesis"
        elif form == "volatility-based": g["vside"] = ["calm", "turbulent"]; fn = lambda R, p, pairs=pairs: w_volgate(to_w(R, zrev(R, pairs, p["N"], p["k"], p["H"])), R, p["vside"]); d = "z-reversion only when leg vol is below / above median"
        else: fn = lambda R, p, pairs=pairs: to_w(R, zrev(R, pairs, **p)).shift(1).fillna(0); d = "z-reversion entered one day late"
        out.append(dict(id=sid, family=fam, form=form, desc=d, universes=["energy"], fn=fn, grid=g, sizing=False))
    return out

CRACK = [("GAS_NYH", "WTI"), ("HO_NYH", "WTI"), ("JET_GULF", "WTI"), ("GAS_NYH", "BRENT"), ("HO_NYH", "BRENT")]
CRACK_SEAS = {("GAS_NYH", "WTI"): ((2, 3, 4), (9, 10)), ("GAS_NYH", "BRENT"): ((2, 3, 4), (9, 10)), ("HO_NYH", "WTI"): ((9, 10, 11), (3, 4)), ("HO_NYH", "BRENT"): ((9, 10, 11), (3, 4))}
LOC = [("GAS_NYH", "GAS_GULF"), ("WTI", "BRENT")]
LOC_SEAS = {("GAS_NYH", "GAS_GULF"): ((8, 9, 10), ())}     # hurricane season: Gulf supply disruptions widen NYH premium? (pre-registered sign)

# ---------- currency carry & FX value ----------
def carry(R): return fx_rate_diff().reindex(R.index, method="ffill")[R.columns.intersection(fx_rate_diff().columns)].reindex(columns=R.columns)
def xs_rank(score, q=0.25, monthly=True):
    r = score.rank(axis=1, pct=True); s = (r > 1 - q).astype(float) - (r <= q).astype(float); s = s.where(score.notna(), 0)
    if monthly: s = s.loc[s.index.is_month_end | (s.index.to_series().shift(-1).dt.month != s.index.month)].reindex(s.index).ffill()
    return s.fillna(0)
def cpi_cum5(R):
    """5-year cumulative inflation differential (foreign minus US), from YoY CPI, published with 2-month lag."""
    m = {"UK": "GB", "JP": "JP", "CA": "CA", "SZ": "CH", "NO": "NO", "SD": "SE", "MX": "MX", "KO": "KR", "IN": "IN", "SF": "ZA"}
    us = _fred("CPALTT01USM659N"); out = {}
    for c, k in m.items():
        try: f = _fred(f"CPALTT01{k}M659N")
        except Exception: continue
        dif = (np.log1p(f / 100) - np.log1p(us / 100)).dropna()
        cum = sum(dif.shift(12 * i) for i in range(5)); cum.index = cum.index + pd.offsets.MonthEnd(2) + pd.Timedelta(days=1); out[c] = cum
    return pd.DataFrame(out).resample("1D").ffill().reindex(R.index, method="ffill").reindex(columns=R.columns)
def value_score(R):   # cheap = real currency fell over 5 years: -(log spot change + inflation differential)
    ls = np.log(px(R)); return -((ls - ls.shift(1260)) + cpi_cum5(R))

def fx_family(off, fam, score_fn, desc_core, ts_rule):
    out = []
    for j, form in enumerate(FORMS):
        sid = f"STRAT-{off + j + 1:04d}"; g = {"q": [0.2, 0.33]}; U = ["fx_tr"]
        if form == "event-triggered": fn = lambda R, p: xs_rank(score_fn(R), p["q"]).mul(nfp_mask(R.index, 10).astype(float), axis=0); d = desc_core + "; held only in the 10 days after payrolls"
        elif form == "cross-sectional": fn = lambda R, p: xs_rank(score_fn(R), p["q"]); d = desc_core + "; long top / short bottom quantile, monthly"
        elif form == "time-series": g = {"x": [1]}; fn = lambda R, p: ts_rule(R); d = "each currency on its own: " + ts_rule.__doc__
        elif form == "lead-lag":
            g = {"L": [63, 126]}
            fn = lambda R, p: xs_rank(score_fn(R) - score_fn(R).shift(p["L"]), 0.33); d = "change in the score over L days (e.g. relative policy-rate momentum) predicts the currency"
        elif form == "regime-conditioned": g["reg"] = ["calm", "turbulent"]; fn = lambda R, p: xs_rank(score_fn(R), p["q"]).mul(regime(R, p["reg"]).astype(float), axis=0); d = desc_core + "; only in calm / turbulent FX vol regime"
        elif form == "term-structure": g["side"] = ["steep", "inverted"]; fn = lambda R, p: xs_rank(score_fn(R), p["q"]).mul(term_gate(R.index, p["side"]).astype(float), axis=0); d = desc_core + "; gated by US curve sign"
        elif form == "flow-based": out.append(dict(id=sid, family=fam, form=form, blocked="needs FX positioning/flow data (CFTC COT, custody flows) - not available")); continue
        elif form == "relative-value": g = {"q": [0.33]}; fn = lambda R, p: xs_rank(score_fn(R) - score_fn(R).rolling(1260, min_periods=500).mean(), p["q"]); d = desc_core + " measured against each currency's own 5-year average"
        elif form == "volatility-based": fn = lambda R, p: xs_rank(score_fn(R) / (R.rolling(63).std() * np.sqrt(252) * 100), p["q"]); d = desc_core + " divided by the currency's volatility (risk-adjusted)"
        else: fn = lambda R, p: xs_rank(score_fn(R), p["q"]).shift(5).fillna(0); d = desc_core + "; executed with a one-week delay (slow execution robustness)"
        out.append(dict(id=sid, family=fam, form=form, desc=d, universes=U, fn=fn, grid=g))
    return out
def carry_ts(R):
    """long if its short rate is above the US rate, short if below"""
    return np.sign(carry(R))
def value_ts(R):
    """long if the real exchange rate is below its 5-year level, short if above"""
    return np.sign(value_score(R))

# ---------- Treasury term premium ----------
Y = P["yields"]
def bond_family(off=290, fam="Interest-rate term premium"):
    out = []; U = ["bonds"]
    def slope(idx): return (Y["DGS10"] - Y["DGS3MO"]).reindex(idx, method="ffill").shift(1)
    def ts_core(R, N=1260):
        s = slope(R.index); hi = s > s.rolling(N, min_periods=250).median(); return pd.DataFrame({c: np.where(hi, 1.0, -1.0) for c in R.columns}, index=R.index)
    def carry_per_dur(R):
        yy = Y.reindex(R.index, method="ffill").shift(1); D = {"UST2Y": 1.9, "UST5Y": 4.6, "UST10Y": 8.6, "UST30Y": 18.0}
        return pd.DataFrame({c: (yy[{"UST2Y": "DGS2", "UST5Y": "DGS5", "UST10Y": "DGS10", "UST30Y": "DGS30"}[c]] - yy["DGS3MO"]) / D[c] for c in R.columns})
    for j, form in enumerate(FORMS):
        sid = f"STRAT-{off + j + 1:04d}"; g = {"N": [756, 1260]}
        if form == "event-triggered": fn = lambda R, p: ts_core(R, p["N"]).mul(nfp_mask(R.index, 5).astype(float), axis=0); d = "term-premium duration call only in the 5 days after payrolls"
        elif form == "cross-sectional": g = {"x": [1]}; fn = lambda R, p: xs_rank(carry_per_dur(R), 0.25, monthly=True); d = "long the maturity with the highest carry per unit duration, short the lowest (vol-sized)"
        elif form == "time-series": fn = lambda R, p: ts_core(R, p["N"]); d = "long duration when 10y-3m slope is above its N-day median (high term premium), short otherwise"
        elif form == "lead-lag":
            g = {"L": [21, 63]}
            def fn(R, p):
                nq = P["macro"]["NASDAQCOM"].reindex(R.index, method="ffill"); dd = nq / nq.rolling(p["L"]).max() - 1
                return pd.DataFrame({c: np.where(dd < -0.05, 1.0, 0.0) for c in R.columns}, index=R.index)
            d = "equity drawdown > 5% over L days leads bond rallies (flight to quality): long duration"
        elif form == "regime-conditioned": g["reg"] = ["calm", "turbulent"]; fn = lambda R, p: ts_core(R, p["N"]).mul(regime(R, p["reg"]).astype(float), axis=0); d = "term-premium rule in one bond-vol regime"
        elif form == "term-structure":
            g = {"L": [63, 126]}
            fn = lambda R, p: pd.DataFrame({c: -np.sign(slope(R.index) - slope(R.index).shift(p["L"])) for c in R.columns}, index=R.index); d = "curve-slope momentum: steepening (bear) -> short duration, flattening -> long"
        elif form == "flow-based": out.append(dict(id=sid, family=fam, form=form, blocked="needs Treasury auction / dealer positioning / fund-flow data - not available")); continue
        elif form == "relative-value":
            g = {"N": [252, 756]}
            def fn(R, p):
                s = slope(R.index); z = (s - s.rolling(p["N"]).mean()) / s.rolling(p["N"]).std()
                w = pd.DataFrame(0.0, index=R.index, columns=R.columns); w["UST10Y"] = -np.sign(z) / 8.6; w["UST2Y"] = np.sign(z) / 1.9
                return w.fillna(0)
            d = "duration-neutral 2s10s: when the curve is unusually steep bet on flattening and vice versa (z-score reversion)"
        elif form == "volatility-based":
            g = {"x": [1]}; fn = lambda R, p: pd.DataFrame({c: (0.05 / (R[c].rolling(21).std() * np.sqrt(252))).clip(upper=5) for c in R.columns}, index=R.index); d = "vol-managed long duration: exposure inversely proportional to 1-month realised bond vol"
        else: g = {"N": [1260]}; fn = lambda R, p: ts_core(R, p["N"]).loc[lambda x: x.index.is_month_end].reindex(R.index).ffill().fillna(0); d = "term-premium rule rebalanced monthly only"
        out.append(dict(id=sid, family=fam, form=form, desc=d, universes=U, fn=fn, grid=g, sizing=form not in ("relative-value", "volatility-based")))
    return out

BLOCKED = {210: ("Commodity crush spread", "soybean / meal / oil daily prices - not available"),
           220: ("Spark spread", "power and natural-gas prices by hub - not available"),
           240: ("Futures curve carry", "commodity futures curves (front and deferred contracts) - not available"),
           280: ("FX intervention reaction", "official intervention records (MoF/SNB) - not reachable from this environment")}
def specs():
    out = (spread_family(200, "Commodity crack spread", CRACK, CRACK_SEAS, lambda a, b: b) + spread_family(230, "Location basis convergence", LOC, LOC_SEAS, lambda a, b: "BRENT" if "BRENT" in (a, b) else b)
           + fx_family(250, "Currency carry", carry, "rank currencies by short-rate differential vs USD", carry_ts)
           + fx_family(260, "FX value reversion", value_score, "rank currencies by 5-year real-exchange-rate cheapness", value_ts) + bond_family())
    for off, (fam, why) in BLOCKED.items():
        for j, form in enumerate(FORMS): out.append(dict(id=f"STRAT-{off + j + 1:04d}", family=fam, form=form, blocked=why))
    return sorted(out, key=lambda s: s["id"])
