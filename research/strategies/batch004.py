"""STRAT-0301..0400. Testable: yield-curve slope (31), butterflies (32), swap spreads 2000-2016 (33), credit spreads (36).
Blocked: Treasury cash-futures basis (34), mortgage basis (35), capital-structure arb (37), convertible arb (38), preferred-common (39), merger spreads (40)."""
import numpy as np, pandas as pd
from strategies.lib import *
from data import _fred
from engine import P
FORMS = ["event-triggered", "cross-sectional", "time-series", "lead-lag", "regime-conditioned", "term-structure", "flow-based", "relative-value", "volatility-based", "execution-aware"]
DUR = {1: 0.97, 2: 1.9, 3: 2.8, 5: 4.4, 7: 6.0, 10: 8.0, 20: 13.5, 30: 17.5}
YC = pd.DataFrame({n: _fred(f"DGS{n}") for n in DUR}); YC[20] = YC[20].combine_first((YC[10] + YC[30]) / 2)
def yc(idx): return YC.reindex(idx, method="ffill")
def z(x, N): return (x - x.rolling(N, min_periods=N // 2).mean()) / x.rolling(N, min_periods=N // 2).std()
def legs(R, spec):
    """spec: list of (series signal, {tenor: dv01 units}) -> weights; one unit = 1 DV01 (weight 1/duration)."""
    w = pd.DataFrame(0.0, index=R.index, columns=R.columns)
    for sig, lg in spec:
        for n, u in lg.items(): w[f"T{n}"] += sig.fillna(0) * u / DUR[n]
    return w / len(spec)
SLOPES = [(2, 10), (2, 5), (5, 30), (10, 30), (1, 7)]
def steep(a, b): return {a: 1.0, b: -1.0}                    # long short-end / short long-end DV01 = profits when curve steepens
def slope_s(idx, a, b): Y = yc(idx); return Y[b] - Y[a]
def gate(w, m): return w.mul(m.reindex(w.index).fillna(False).astype(float), axis=0)
def term_gate(idx, side): g = (YC[10] - YC[1]).reindex(idx, method="ffill"); return (g > 0) if side == "steep" else (g <= 0)
def rates_vol(idx): return YC[10].diff().rolling(21).std().reindex(idx, method="ffill")

def slope_family(off=300, fam="Yield-curve slope trades"):
    out = []
    for j, form in enumerate(FORMS):
        sid = f"STRAT-{off + j + 1:04d}"; g = {"N": [252, 756]}
        rev = lambda R, N: legs(R, [(-np.sign(z(slope_s(R.index, a, b), N)) * (z(slope_s(R.index, a, b), N).abs() > 1), steep(a, b)) for a, b in SLOPES])
        if form == "event-triggered": fn = lambda R, p: gate(rev(R, p["N"]), nfp_mask(R.index, 5)); d = "slope z-reversion held only in the 5 days after payrolls"
        elif form == "cross-sectional":
            def fn(R, p):
                Z = pd.DataFrame({ab: z(slope_s(R.index, *ab), p["N"]) for ab in SLOPES}); pick = Z.abs().fillna(-1).idxmax(axis=1)
                return legs(R, [(-np.sign(Z[ab]) * (pick == ab), steep(*ab)) for ab in SLOPES])
            d = "each day trade only the most stretched of 5 curve slopes (DV01-neutral)"
        elif form == "time-series": g = {"L": [21, 63, 126]}; fn = lambda R, p: legs(R, [(np.sign(slope_s(R.index, a, b) - slope_s(R.index, a, b).shift(p["L"])), steep(a, b)) for a, b in SLOPES]); d = "slope momentum: keep the steepener/flattener in the direction of the last L-day slope change"
        elif form == "lead-lag":
            g = {"L": [63, 126]}
            def fn(R, p):
                ff = P["yields"]["DFF"].reindex(R.index, method="ffill"); hike = np.sign(ff - ff.shift(p["L"]))
                return legs(R, [(-hike, steep(a, b)) for a, b in SLOPES])
            d = "Fed funds changes lead the curve: after hikes hold flatteners, after cuts steepeners"
        elif form == "regime-conditioned": g["reg"] = ["calm", "turbulent"]; fn = lambda R, p: gate(rev(R, p["N"]), regime(R, p["reg"])); d = "slope z-reversion in one rates-vol regime"
        elif form == "term-structure":
            g = {"x": [1]}
            def fn(R, p):
                Y = yc(R.index); sig = []
                for a, b in SLOPES:   # carry + roll-down per DV01 of a steepener: short leg earns y_a - y_cash... approximated by (y_a - y_1) - (y_b - y_1)*D_a/D_b sign
                    sig.append((np.sign((Y[a] - Y[1]) / DUR[a] - (Y[b] - Y[1]) / DUR[b]), steep(a, b)))
                return legs(R, sig)
            d = "hold the steepener or flattener with positive carry per unit DV01 (curve term-structure carry)"
        elif form == "flow-based": out.append(dict(id=sid, family=fam, form=form, blocked="needs Treasury auction sizes, dealer positioning or fund-flow data")); continue
        elif form == "relative-value":
            g = {"N": [756, 1260]}
            def fn(R, p):
                Y = yc(R.index); sig = []
                for a, b in SLOPES:
                    s = Y[b] - Y[a]; lvl = Y[10]; beta = (s.rolling(p["N"]).cov(lvl) / lvl.rolling(p["N"]).var()); fit = s.rolling(p["N"]).mean() + beta * (lvl - lvl.rolling(p["N"]).mean())
                    res = s - fit; sig.append((-np.sign(z(res, 252)) * (z(res, 252).abs() > 1), steep(a, b)))
                return legs(R, sig)
            d = "slope vs the slope implied by the rate level (rolling regression); fade the residual"
        elif form == "volatility-based": g["vs"] = ["low", "high"]; fn = lambda R, p: gate(rev(R, p["N"]), (rates_vol(R.index) < rates_vol(R.index).rolling(756, min_periods=250).median()) if p["vs"] == "low" else (rates_vol(R.index) >= rates_vol(R.index).rolling(756, min_periods=250).median())); d = "slope z-reversion only when rates vol is low / high"
        else: fn = lambda R, p: rev(R, p["N"]).loc[lambda x: x.index.is_month_end].reindex(R.index).ffill().fillna(0); d = "slope z-reversion rebalanced monthly"
        out.append(dict(id=sid, family=fam, form=form, desc=d, universes=["curve"], fn=fn, grid=g, sizing=False))
    return out

FLIES = [(2, 5, 10), (5, 10, 30), (1, 3, 7), (2, 7, 20), (3, 10, 30)]
def fly_y(idx, a, b, c): Y = yc(idx); return 2 * Y[b] - Y[a] - Y[c]
def fly_legs(a, b, c): return {a: 0.5, b: -1.0, c: 0.5}           # long wings / short body DV01: profits when body cheapens vs wings (fly yield rises)
def fly_family(off=310, fam="Butterfly curve trades"):
    out = []
    for j, form in enumerate(FORMS):
        sid = f"STRAT-{off + j + 1:04d}"; g = {"N": [126, 504]}
        rev = lambda R, N: legs(R, [(-np.sign(z(fly_y(R.index, *f), N)) * (z(fly_y(R.index, *f), N).abs() > 1), fly_legs(*f)) for f in FLIES])
        if form == "event-triggered": fn = lambda R, p: gate(rev(R, p["N"]), nfp_mask(R.index, 5)); d = "fly z-reversion held only after payrolls"
        elif form == "cross-sectional":
            def fn(R, p):
                Z = pd.DataFrame({f: z(fly_y(R.index, *f), p["N"]) for f in FLIES}); pick = Z.abs().fillna(-1).idxmax(axis=1)
                return legs(R, [(-np.sign(Z[f]) * (pick == f), fly_legs(*f)) for f in FLIES])
            d = "trade only the most dislocated of 5 butterflies each day"
        elif form == "time-series": fn = lambda R, p: rev(R, p["N"]); d = "butterfly yield z > 1: receive the cheap point vs wings (DV01-neutral), exit when |z| < 1"
        elif form == "lead-lag":
            g = {"L": [5, 21]}
            fn = lambda R, p: legs(R, [(np.sign(slope_s(R.index, f[0], f[2]) - slope_s(R.index, f[0], f[2]).shift(p["L"])), fly_legs(*f)) for f in FLIES]); d = "slope changes lead the butterfly (steepening cheapens the body)"
        elif form == "regime-conditioned": g["reg"] = ["calm", "turbulent"]; fn = lambda R, p: gate(rev(R, p["N"]), regime(R, p["reg"])); d = "fly z-reversion in one regime"
        elif form == "term-structure":
            g = {"x": [1]}; fn = lambda R, p: legs(R, [(np.sign(fly_y(R.index, *f)), fly_legs(*f)) for f in FLIES]); d = "hold the fly in the direction of its carry (body yield above wings average -> receive body)"
        elif form == "flow-based": out.append(dict(id=sid, family=fam, form=form, blocked="needs auction/issuance and positioning data")); continue
        elif form == "relative-value":
            g = {"N": [252]}
            def fn(R, p):
                dY = yc(R.index).diff(); idx = R.index; W = pd.DataFrame(0.0, index=idx, columns=R.columns); cols = list(DUR)
                lv = yc(idx)
                for s in range(504, len(idx), 21):
                    X = dY.iloc[s - 504:s].dropna()
                    if len(X) < 300: continue
                    U, S_, Vt = np.linalg.svd(X - X.mean(), full_matrices=False); B = Vt[:3]
                    L = lv.iloc[s - 252:s + 21]; F = (L - L.iloc[:252].mean()) @ B.T; fit = F @ B + L.iloc[:252].mean(); res = (L - fit)
                    zz = (res - res.iloc[:252].mean()) / res.iloc[:252].std()
                    for n in cols: W.iloc[s:s + 21, W.columns.get_loc(f"T{n}")] = (np.sign(zz[n].iloc[252:]) * (zz[n].iloc[252:].abs() > 1.5) / DUR[n]).values[:len(W.iloc[s:s + 21])]
                return W.sub(W.mean(1), axis=0)
            d = "3-factor PCA curve model; receive tenors whose yield is >1.5 sd above the model fit, pay the rich ones"
        elif form == "volatility-based": g["vs"] = ["low", "high"]; fn = lambda R, p: gate(rev(R, p["N"]), (rates_vol(R.index) < rates_vol(R.index).rolling(756, min_periods=250).median()) if p["vs"] == "low" else (rates_vol(R.index) >= rates_vol(R.index).rolling(756, min_periods=250).median())); d = "fly reversion only in low / high rates vol"
        else: fn = lambda R, p: rev(R, p["N"]).shift(1).fillna(0); d = "fly reversion entered one day late"
        out.append(dict(id=sid, family=fam, form=form, desc=d, universes=["curve"], fn=fn, grid=g, sizing=False))
    return out

SW = {n: (_fred(f"DSWP{n}"), _fred(f"DGS{n}")) for n in (2, 5, 10, 30)}
def ss(idx, n): s, t = SW[n]; return (s - t).reindex(idx, method="ffill")
def ss_legs(R, sigs):
    w = pd.DataFrame(0.0, index=R.index, columns=R.columns)
    for n, sg in sigs.items(): w[f"T{n}"] += sg.fillna(0) / DUR[n]; w[f"SW{n}"] -= sg.fillna(0) / DUR[n]     # +1 = long Treasury / short swap-bond: gains when swap spread widens
    return w / len(sigs)
def swap_family(off=320, fam="Swap spread relative value"):
    out = []
    for j, form in enumerate(FORMS):
        sid = f"STRAT-{off + j + 1:04d}"; g = {"N": [126, 252]}
        rev = lambda R, N: ss_legs(R, {n: -np.sign(z(ss(R.index, n), N)) * (z(ss(R.index, n), N).abs() > 1) for n in SW})
        if form == "event-triggered": fn = lambda R, p: gate(rev(R, p["N"]), nfp_mask(R.index, 5)); d = "swap-spread reversion only after payrolls"
        elif form == "cross-sectional":
            def fn(R, p):
                Z = pd.DataFrame({n: z(ss(R.index, n), p["N"]) for n in SW}); pick = Z.abs().fillna(-1).idxmax(axis=1)
                return ss_legs(R, {n: -np.sign(Z[n]) * (pick == n) for n in SW})
            d = "trade only the most stretched tenor's swap spread"
        elif form == "time-series": fn = lambda R, p: rev(R, p["N"]); d = "swap spread z beyond 1: bet on reversion (DV01-matched Treasury vs swap-bond)"
        elif form == "lead-lag": g = {"L": [5, 21]}; fn = lambda R, p: ss_legs(R, {n: np.sign(ss(R.index, 2) - ss(R.index, 2).shift(p["L"])) for n in (5, 10, 30)}); d = "2-year swap-spread moves (funding stress) lead longer tenors"
        elif form == "regime-conditioned": g["reg"] = ["calm", "turbulent"]; fn = lambda R, p: gate(rev(R, p["N"]), regime(R, p["reg"])); d = "reversion in one regime"
        elif form == "term-structure": g = {"N": [252]}; fn = lambda R, p: ss_legs(R, {10: -np.sign(z(ss(R.index, 10) - ss(R.index, 2), p["N"]))}); d = "swap-spread curve (10y minus 2y spread) z-reversion"
        elif form == "flow-based": out.append(dict(id=sid, family=fam, form=form, blocked="needs dealer balance-sheet / repo / issuance flow data")); continue
        elif form == "relative-value": g = {"L": [63, 126]}; fn = lambda R, p: ss_legs(R, {n: np.sign(ss(R.index, n) - ss(R.index, n).shift(p["L"])) for n in SW}); d = "swap-spread momentum (opposite hypothesis)"
        elif form == "volatility-based": g["vs"] = ["low", "high"]; fn = lambda R, p: gate(rev(R, p["N"]), (rates_vol(R.index) < rates_vol(R.index).rolling(504, min_periods=200).median()) if p["vs"] == "low" else (rates_vol(R.index) >= rates_vol(R.index).rolling(504, min_periods=200).median())); d = "reversion by rates-vol regime"
        else: fn = lambda R, p: rev(R, p["N"]).shift(1).fillna(0); d = "reversion entered one day late"
        out.append(dict(id=sid, family=fam, form=form, desc=d, universes=["swaps"], fn=fn, grid=g, sizing=False))
    return out

def cs(idx, a="DBAA", b=None):
    x = _fred(a) - (_fred("DGS20").combine_first((_fred("DGS10") + _fred("DGS30")) / 2) if b is None else _fred(b)); return x.reindex(idx, method="ffill")
def cr_w(R, sig, pair=("BAA", "T20")):
    w = pd.DataFrame(0.0, index=R.index, columns=R.columns); w[pair[0]] = sig.fillna(0); w[pair[1]] = -sig.fillna(0); return w
def credit_family(off=350, fam="Credit spread mean reversion"):
    out = []
    for j, form in enumerate(FORMS):
        sid = f"STRAT-{off + j + 1:04d}"; g = {"N": [252, 756]}
        rev = lambda R, N: cr_w(R, np.sign(z(cs(R.index), N)) * (z(cs(R.index), N).abs() > 1))
        if form == "event-triggered": fn = lambda R, p: gate(rev(R, p["N"]), nfp_mask(R.index, 5)); d = "credit-spread reversion only after payrolls"
        elif form == "cross-sectional": fn = lambda R, p: cr_w(R, np.sign(z(cs(R.index, "DBAA", "DAAA"), p["N"])) * (z(cs(R.index, "DBAA", "DAAA"), p["N"]).abs() > 1), ("BAA", "AAA")); d = "quality spread Baa-Aaa: long Baa vs Aaa when wide, reverse when tight"
        elif form == "time-series": fn = lambda R, p: rev(R, p["N"]); d = "Baa-Treasury spread z > 1: long credit duration-hedged (wide spreads mean-revert); z < -1 short"
        elif form == "lead-lag":
            g = {"L": [21, 63]}
            def fn(R, p):
                nq = P["macro"]["NASDAQCOM"].reindex(R.index, method="ffill"); return cr_w(R, np.sign(nq / nq.shift(p["L"]) - 1))
            d = "equity momentum leads credit: long hedged credit after stocks rose over L days, short after they fell"
        elif form == "regime-conditioned": g["reg"] = ["calm", "turbulent"]; fn = lambda R, p: gate(rev(R, p["N"]), regime(R, p["reg"])); d = "reversion in one regime"
        elif form == "term-structure": g["side"] = ["steep", "inverted"]; fn = lambda R, p: gate(cr_w(R, pd.Series(1.0, index=R.index)), term_gate(R.index, p["side"])); d = "long hedged credit only when the 10y-1y curve is steep / inverted (cycle phase)"
        elif form == "flow-based": out.append(dict(id=sid, family=fam, form=form, blocked="needs credit fund flows / dealer inventory data")); continue
        elif form == "relative-value": g = {"L": [63, 126]}; fn = lambda R, p: cr_w(R, -np.sign(cs(R.index) - cs(R.index).shift(p["L"]))); d = "credit-spread momentum: stay long hedged credit while spreads tighten, short while they widen"
        elif form == "volatility-based":
            g = {"q": [0.5, 0.8]}
            def fn(R, p):
                v = P["macro"]["VIXCLS"].reindex(R.index, method="ffill"); pr = v.rolling(756, min_periods=250).rank(pct=True); return cr_w(R, (pr < p["q"]).astype(float))
            d = "carry: long hedged credit only when VIX is below its q-percentile"
        else: fn = lambda R, p: rev(R, p["N"]).loc[lambda x: x.index.is_month_end].reindex(R.index).ffill().fillna(0); d = "reversion rebalanced monthly"
        out.append(dict(id=sid, family=fam, form=form, desc=d, universes=["credit"], fn=fn, grid=g, sizing=False))
    return out

BLOCKED = {330: ("Treasury cash-futures basis", "Treasury futures prices, CTD baskets and repo rates - not available"),
           340: ("Mortgage basis trading", "TBA/MBS prices or current-coupon OAS - not available (only primary mortgage rate)"),
           360: ("Capital structure arbitrage", "single-name CDS spreads + equity prices - not available"),
           370: ("Convertible bond arbitrage", "convertible bond prices, terms and stock borrow - not available"),
           380: ("Preferred-common relative value", "preferred share prices and terms - not available"),
           390: ("Merger spread event trading", "M&A deal announcements, terms and target/acquirer prices - not available")}
def specs():
    out = slope_family() + fly_family() + swap_family() + credit_family()
    for off, (fam, why) in BLOCKED.items():
        for j, form in enumerate(FORMS): out.append(dict(id=f"STRAT-{off + j + 1:04d}", family=fam, form=form, blocked=why))
    return sorted(out, key=lambda s: s["id"])
