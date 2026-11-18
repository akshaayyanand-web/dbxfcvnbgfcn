"""STRAT-0101..0200. Testable here: pairs distance (11), cointegration (12), basket stat-arb (13), inter-commodity spreads (20).
Families 14-19 need data not available in this environment (see BLOCKED)."""
import numpy as np, pandas as pd
from strategies.lib import *
from strategies.lib_pairs import pair_book, pca_sscore
from engine import P
FORMS = ["event-triggered", "cross-sectional", "time-series", "lead-lag", "regime-conditioned", "term-structure", "flow-based", "relative-value", "volatility-based", "execution-aware"]
def disp_gate(R, side):
    d = R.std(1).rolling(21).mean(); pr = d.rolling(252, min_periods=126).rank(pct=True); return (pr >= 0.5) if side == "high" else (pr < 0.5)
def term_gate(idx, side):
    sl = P["macro"]["T10Y3M"]; i2 = idx.tz_localize(None) if idx.tz is not None else idx
    g = sl.reindex(i2, method="ffill").shift(1); m = (g > 0) if side == "steep" else (g <= 0); m.index = idx; return m
def vol_gate_crypto(R):
    v = P["crypto_v"].reindex(R.index)[R.columns]; return (v.sum(1) < v.sum(1).rolling(20).mean())
def asset_lowvol_crypto(R):
    v = P["crypto_v"].reindex(R.index)[R.columns]; return v < v.rolling(20).mean()
U_PAIR = ["ind49", "crypto", "fx"]
BASE = {"L": [252], "T": [126], "npairs": [5, 20], "k": [1.5, 2.0]}

def fam_pairs(off, fam, sel, hedge):
    out = []
    for j, form in enumerate(FORMS):
        sid = f"STRAT-{off + j + 1:04d}"; g = dict(BASE); U = U_PAIR; extra = {}
        common = dict(sel=sel, hedge=hedge)
        if form == "event-triggered":
            fn = lambda R, p, c=common: pair_book(R, gate=nfp_mask(R.index, 10), **c, **p); d = "pair rule, positions only in the 10 days after US payrolls day"
        elif form == "cross-sectional":
            g["npairs"] = [20, 40]; g["k"] = [2.5, 3.0]; fn = lambda R, p, c=common: pair_book(R, **c, **p); d = "wider universe of formed pairs, only the most extreme divergences (k 2.5-3)"
        elif form == "time-series":
            fn = lambda R, p, c=common: pair_book(R, **c, **p); d = "formed pairs; enter when spread z > k, exit when it crosses its formation mean or at window end"
        elif form == "lead-lag":
            if sel == "coint":
                fn = lambda R, p, c=common: pair_book(R, adjust_only=True, **c, **p); d = "error-correction: trade only the leg that historically adjusts to the spread"
            else:
                g = {"L": [252], "T": [126], "npairs": [5, 20]}; fn = lambda R, p, c=common: pair_book(R, mode="catchup", **c, **p); d = "inside formed pairs: fade yesterday's 1-day divergence (laggard catches up)"
        elif form == "regime-conditioned":
            g["reg"] = ["calm", "turbulent"]; fn = lambda R, p, c=common: pair_book(R, gate=regime(R, p["reg"]), **c, **{k: v for k, v in p.items() if k != "reg"}); d = "pair rule only in calm / turbulent cross-asset vol regime"
        elif form == "term-structure":
            g["side"] = ["steep", "inverted"]; fn = lambda R, p, c=common: pair_book(R, gate=term_gate(R.index, p["side"]), **c, **{k: v for k, v in p.items() if k != "side"}); d = "pair rule gated by the 10y-3m curve sign"
        elif form == "flow-based":
            U = ["crypto"]; fn = lambda R, p, c=common: pair_book(R, gate=vol_gate_crypto(R), **c, **p); d = "pair rule only on days when total crypto volume is below its 20-day average (non-informational moves)"
        elif form == "relative-value":
            if sel == "coint":
                U = U_PAIR; fn = lambda R, p: pair_book(R, sel="coint", hedge="ols", kalman=True, **p); d = "cointegrated pairs with a Kalman-filter time-varying hedge ratio"
            else:
                U = ["ind10", "multi_recent"]; fn = lambda R, p, c=common: pair_book(R, **c, **p); g["npairs"] = [3, 6]; d = "distance pairs restricted to broad sectors / cross-asset universe"
        elif form == "volatility-based":
            g["disp"] = ["high", "low"]; fn = lambda R, p, c=common: pair_book(R, gate=disp_gate(R, p["disp"]), **c, **{k: v for k, v in p.items() if k != "disp"}); d = "pair rule only when cross-sectional return dispersion is high / low"
        else:
            fn = lambda R, p, c=common: pair_book(R, delay=1, **c, **p); d = "same rule but enter one day after the signal (removes bid-ask bounce, Gatev et al. robustness check)"
        out.append(dict(id=sid, family=fam, form=form, desc=d, universes=U, fn=fn, grid=g, sizing=False, start="1963-07-01" if "ind49" in U else None))
    return out

def fam_basket(off=120, fam="Basket statistical arbitrage"):
    out = []; G = {"k": [1, 3], "s_in": [1.25, 2.0]}; U = ["ind49", "crypto", "fx"]
    for j, form in enumerate(FORMS):
        sid = f"STRAT-{off + j + 1:04d}"; g = dict(G); U2 = U
        if form == "event-triggered": fn = lambda R, p: pca_sscore(R, **p).mul(nfp_mask(R.index, 10).astype(float), axis=0); d = "PCA residual s-score, only in the 10 days after payrolls"
        elif form == "cross-sectional": g = {"k": [1, 3]}; fn = lambda R, p: pca_sscore(R, mode="xs", **p); d = "rank 5-day PCA-residual returns; long losers / short winners (dollar-neutral)"
        elif form == "time-series": fn = lambda R, p: pca_sscore(R, **p); d = "Avellaneda-Lee: OU s-score of 60-day cumulative residual vs top-k PCs; enter |s|>s_in, exit |s|<0.5"
        elif form == "lead-lag": g = {"k": [1, 3]}; fn = lambda R, p: pca_sscore(R, mode="leadlag", **p); d = "assets that under-reacted to yesterday's first-PC (market) move vs their beta catch up"
        elif form == "regime-conditioned": g["reg"] = ["calm", "turbulent"]; fn = lambda R, p: pca_sscore(R, k=p["k"], s_in=p["s_in"]).mul(regime(R, p["reg"]).astype(float), axis=0); d = "s-score rule in one vol regime"
        elif form == "term-structure": g["side"] = ["steep", "inverted"]; fn = lambda R, p: pca_sscore(R, k=p["k"], s_in=p["s_in"]).mul(term_gate(R.index, p["side"]).astype(float), axis=0); d = "s-score rule gated by curve sign"
        elif form == "flow-based": U2 = ["crypto"]; fn = lambda R, p: pca_sscore(R, vol_filter=asset_lowvol_crypto(R), **p); d = "s-score entries only on low-volume days for that coin (non-informational divergence, Llorente et al. 2002)"
        elif form == "relative-value": g = {"N": [3, 5, 10]}; U2 = ["ind49", "crypto", "fx"]; fn = lambda R, p: (lambda s: s.sub(s.mean(1), axis=0))(np.sign(-(R.rolling(p["N"]).sum().sub(R.rolling(p["N"]).sum().mean(1), axis=0))).fillna(0)); d = "residual vs equal-weight universe mean (no PCA): fade N-day relative move"
        elif form == "volatility-based": g["disp"] = ["high", "low"]; fn = lambda R, p: pca_sscore(R, k=p["k"], s_in=p["s_in"]).mul(disp_gate(R, p["disp"]).astype(float), axis=0); d = "s-score only when dispersion is high / low"
        else: fn = lambda R, p: pca_sscore(R, **p).shift(1).fillna(0); d = "s-score rule entered one day late (bounce-robust)"
        out.append(dict(id=sid, family=fam, form=form, desc=d, universes=U2, fn=fn, grid=g, sizing=False, start="1963-07-01"))
    return out

PAIRS_C = [("WTI", "BRENT"), ("GOLD", "SILVER"), ("WTI", "HHGAS"), ("BRENT", "HHGAS"), ("GOLD", "WTI")]
def ratio_z(R, N):
    p = np.log(px(R)); out = {}
    for a, b in PAIRS_C:
        sp = p[a] - p[b]; out[(a, b)] = (sp - sp.rolling(N).mean()) / sp.rolling(N).std()
    return out
def pairs_to_w(R, sig):
    w = pd.DataFrame(0.0, index=R.index, columns=R.columns)
    for (a, b), s in sig.items(): s = s.fillna(0); w[a] += s / len(sig); w[b] -= s / len(sig)
    return w
def zrev(R, N=60, k=2.0, H=10):
    return {ab: hold((-(z > k).astype(int) + (z < -k).astype(int)).to_frame("x"), H)["x"] for ab, z in ratio_z(R, N).items()}
def fam_commod(off=190, fam="Commodity inter-commodity spread"):
    out = []; G = {"N": [60, 120], "k": [1.5, 2.5], "H": [10]}
    for j, form in enumerate(FORMS):
        sid = f"STRAT-{off + j + 1:04d}"; g = dict(G)
        if form == "event-triggered": fn = lambda R, p: pairs_to_w(R, zrev(R, **p)).mul(nfp_mask(R.index, 10).astype(float), axis=0); d = "ratio z-reversion only after payrolls"
        elif form == "cross-sectional":
            def fn(R, p):
                zs = ratio_z(R, p["N"]); Z = pd.DataFrame({k: v for k, v in zs.items()}); pick = Z.abs().fillna(-1).idxmax(axis=1)
                sig = {ab: (-np.sign(Z[ab]) * (pick == ab) * (Z[ab].abs() > p["k"])).astype(float) for ab in zs}; return pairs_to_w(R, sig)
            d = "each day trade only the most stretched of the 5 commodity spreads"
        elif form == "time-series": fn = lambda R, p: pairs_to_w(R, zrev(R, **p)); d = "log-ratio z-score > k: fade it, hold H days"
        elif form == "lead-lag":
            g = {"N": [1]}
            def fn(R, p):
                return pairs_to_w(R, {(a, b): np.sign(R[b] - R[a]).fillna(0) for a, b in PAIRS_C}); 
            d = "fade yesterday's 1-day spread move (one leg lags the other)"
        elif form == "regime-conditioned": g["reg"] = ["calm", "turbulent"]; fn = lambda R, p: pairs_to_w(R, zrev(R, p["N"], p["k"], p["H"])).mul(regime(R, p["reg"]).astype(float), axis=0); d = "z-reversion in one regime"
        elif form == "term-structure": g["side"] = ["steep", "inverted"]; fn = lambda R, p: pairs_to_w(R, zrev(R, p["N"], p["k"], p["H"])).mul(term_gate(R.index, p["side"]).astype(float), axis=0); d = "z-reversion gated by yield-curve sign (true commodity curves unavailable)"
        elif form == "flow-based": out.append(dict(id=sid, family=fam, form=form, blocked="no volume/positioning data for spot commodity series (needs futures volume or CFTC COT)")); continue
        elif form == "relative-value": g = {"N": [60, 120, 250]}; fn = lambda R, p: pairs_to_w(R, {ab: np.sign(z) for ab, z in ratio_z(R, p["N"]).items()}); d = "spread MOMENTUM (sign of z) — opposite hypothesis to reversion"
        elif form == "volatility-based": g["vside"] = ["calm", "turbulent"]; fn = lambda R, p: w_volgate(pairs_to_w(R, zrev(R, p["N"], p["k"], p["H"])), R, p["vside"]); d = "z-reversion only when leg vol below / above its median"
        else: fn = lambda R, p: pairs_to_w(R, zrev(R, **p)).shift(1).fillna(0); d = "z-reversion entered one day late"
        out.append(dict(id=sid, family=fam, form=form, desc=d, universes=["commod"], fn=fn, grid=g, sizing=False))
    return out

BLOCKED = {
    130: ("ETF versus constituents", "ETF prices + NAV/iNAV and constituent prices (intraday) - not available"),
    140: ("ADR versus local share", "ADR and home-market share prices + FX at matching timestamps - not available"),
    150: ("Dual-listed share arbitrage", "prices of both lines of dual-listed companies (e.g. Royal Dutch/Shell history) - not available"),
    160: ("Closed-end fund discount", "closed-end fund prices and NAVs - not available"),
    170: ("Index futures fair-value basis", "index futures prices + cash index + dividends/rates at the same time - only CFDs available"),
    180: ("Calendar spread term structure", "commodity futures curves (multiple maturities) - not available; crypto dated-futures version covered in 0731-0740"),
}
def specs():
    out = fam_pairs(100, "Pairs distance trading", "ssd", "1:1") + fam_pairs(110, "Cointegration spread trading", "coint", "ols") + fam_basket() + fam_commod()
    for off, (fam, why) in BLOCKED.items():
        for j, form in enumerate(FORMS): out.append(dict(id=f"STRAT-{off + j + 1:04d}", family=fam, form=form, blocked=why))
    return sorted(out, key=lambda s: s["id"])
