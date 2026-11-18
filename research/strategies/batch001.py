"""STRAT-0001..0100 (families 1-10 except 5): concrete, pre-registered rules for every formulation."""
import numpy as np, pandas as pd
from strategies.lib import *

FORMS = ["event-triggered", "cross-sectional", "time-series", "lead-lag", "regime-conditioned", "term-structure", "flow-based", "relative-value", "volatility-based", "execution-aware"]
def c_dual(R, L=252, q=0.3, **k):            # F3 dual momentum: relative winner AND positive absolute momentum, long-only
    sc = s_xsmom(R, L, 0); rk = sc.rank(axis=1, pct=True)
    s = ((rk >= 1 - q) & (sc > 0)).astype(float).where(sc.notna()); return s.loc[s.index.dayofweek == 4].reindex(s.index).ffill()
def x_tsmom(R, L=126, **k): return px(R) / px(R).shift(L) - 1
def x_chanpos(R, N=252, **k):                # 52-week-high closeness (George & Hwang 2004)
    p = px(R); hi = p.rolling(N).max(); lo = p.rolling(N).min(); return (p - lo) / (hi - lo)
def x_squeeze(R, N=20, **k):
    v = R.rolling(N).std(); pr = v.rolling(252, min_periods=126).rank(pct=True); return np.sign(px(R) / px(R).shift(N) - 1) * (1 - pr)
def x_pullback(R, T=200, **k):
    p = px(R); tr = np.sign(p - sma(p, T)); z = (p / p.shift(3) - 1) / (R.rolling(60).std() * np.sqrt(3)); return tr * (-z)
def x_reversal(R, N=5, **k):                 # short-term reversal (Lehmann 1990 / Jegadeesh 1990)
    return -(px(R) / px(R).shift(N) - 1)
def x_madist(R, N=200, **k): p = px(R); return p / sma(p, N) - 1

FAM = {  # id offset: (family, ts core, core grid, xs score, xs grid, ts universes)
    0:  ("Time-series momentum", c_tsmom, {"L": [21, 63, 126, 252]}, x_tsmom, {"L": [63, 126, 252]}, ["macro_long", "cfd", "crypto"]),
    10: ("Cross-sectional momentum", c_tsmom, {"L": [63, 126, 252]}, s_xsmom, {"L": [126, 252], "skip": [5, 21]}, ["ind49", "crypto", "fx"]),
    20: ("Dual momentum", lambda R, L=252, **k: c_tsmom(R, L).clip(lower=0), {"L": [126, 252]}, None, {"L": [126, 252], "q": [0.2, 0.3]}, ["ind10", "crypto", "multi_recent"]),
    30: ("Breakout continuation", c_breakout_hold, {"N": [20, 50, 100], "H": [10, 40]}, x_chanpos, {"N": [126, 252]}, ["macro_long", "cfd", "crypto"]),
    50: ("Volatility compression breakout", c_squeeze, {"N": [10, 20], "H": [5, 20], "pct": [0.2]}, x_squeeze, {"N": [10, 20]}, ["macro_long", "cfd", "crypto"]),
    60: ("Trend pullback entry", c_pullback, {"T": [100, 200], "x": [1.0, 2.0], "H": [5]}, x_pullback, {"T": [100, 200]}, ["cfd", "crypto", "ind10"]),
    70: ("Trend exhaustion reversal", c_exhaust, {"N": [10, 20], "k": [2.0, 3.0], "H": [5]}, x_reversal, {"N": [3, 5, 10]}, ["macro_long", "cfd", "crypto"]),
    80: ("Moving-average regime allocation", c_maregime, {"N": [50, 100, 200]}, x_madist, {"N": [100, 200]}, ["ind10", "cfd", "crypto"]),
    90: ("Donchian channel trend", c_donchian, {"N": [20, 55, 100], "M": [10, 20]}, x_chanpos, {"N": [55, 100]}, ["macro_long", "cfd", "crypto"]),
}
XS_U = ["ind49", "crypto", "fx"]; RV_U = ["pairs_cfd", "pairs_crypto", "pairs_macro"]

def specs():
    out = []
    for off, (fam, core, cg, xs, xg, tsu) in FAM.items():
        for j, form in enumerate(FORMS):
            sid = f"STRAT-{off + j + 1:04d}"; g = dict(cg)
            if form == "event-triggered":
                g["Hev"] = [5, 10]; fn = lambda R, p, core=core: w_event(core(R, **p), p["Hev"]); U = tsu
                desc = "core signal, but positions only held in the H days after US payrolls day (first Friday)"
            elif form == "cross-sectional":
                if off == 20: fn = lambda R, p: c_dual(R, **p); g = xg
                else: fn = lambda R, p, xs=xs: w_xs(xs(R, **p)); g = xg
                U = XS_U; desc = "rank the family score across the universe; long top 30% / short bottom 30%, weekly"
            elif form == "time-series":
                fn = lambda R, p, core=core: core(R, **p); U = tsu; desc = "the family's own-asset rule, every asset independently"
            elif form == "lead-lag":
                fn = lambda R, p, core=core: w_leadlag(core(R, **p), R); U = tsu; desc = "leader asset's signal (BTC / SPX / NASDAQ / market) applied to the other assets"
            elif form == "regime-conditioned":
                g["reg"] = ["calm", "turbulent", "uptrend", "downtrend"]; fn = lambda R, p, core=core: w_regime(core(R, **p), R, p["reg"]); U = tsu
                desc = "core signal only inside one pre-listed market regime (cross-asset vol percentile or 200d trend)"
            elif form == "term-structure":
                g["side"] = ["steep", "inverted"]; fn = lambda R, p, core=core: w_term(core(R, **p), p["side"]); U = tsu
                desc = "core signal gated by the US 10y-3m yield-curve slope sign (lagged 1 day)"
            elif form == "flow-based":
                fn = lambda R, p, core=core: w_flow(core(R, **p), R, "crypto"); U = ["crypto"]
                desc = "core signal only when 10-day taker-buy share confirms the direction (Binance spot taker flow)"
            elif form == "relative-value":
                fn = lambda R, p, core=core: core(R, **p); U = RV_U; desc = "core rule applied to dollar-neutral pair spreads (A minus B)"
            elif form == "volatility-based":
                g["vside"] = ["calm", "turbulent"]; fn = lambda R, p, core=core: w_volgate(core(R, **p), R, p["vside"]); U = tsu
                desc = "core signal only when the asset's own 20d vol is below / above its 1-year median"
            else:
                fn = lambda R, p, core=core: w_exec(core(R, **p)); U = tsu; desc = "core rule decided weekly (Friday close) to cut turnover"
            if off == 20 and form not in ("cross-sectional",): desc += " (absolute-momentum leg, long/flat)"
            out.append(dict(id=sid, family=fam, form=form, desc=desc, universes=U, fn=fn, grid=g))
    return out
