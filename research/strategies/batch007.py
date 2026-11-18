"""STRAT-0601..0700. Testable: correlation (61, realised-correlation signals), gamma scalping (62, synthetic delta-hedged straddles),
vol event premium (70, 9-day variance swaps on VIX9D). Merged: calendar options spread (63) = same synthetic instrument/data as STRAT-0573.
Blocked: diagonal (64), option butterflies (65), risk reversals (66), dealer gamma (67), OI pinning (68), sector dispersion (69)."""
import numpy as np, pandas as pd
from math import erf
from vol import UND, varswap, trail_rv, cboe
from data import _fred
from engine import P
from strategies.lib import nfp_mask
from strategies.batch006 import VIX3M, VVIX, VIX9D, frame, _ts, _vixpct
def mkt_ex(): return P["ff3"]["Mkt-RF"]
def timing(sig, start="1930"):
    m = mkt_ex(); s = sig.reindex(m.index, method="ffill").shift(1).fillna(0); return frame({"MKT": (s * m).loc[start:]})
IND = P["ind10"]
def avg_corr(n):
    X = IND.loc["1927":]; out = []; idx = []
    for e in range(n, len(X), 5):
        c = np.corrcoef(X.iloc[e - n:e].T.values); out.append(c[np.triu_indices(10, 1)].mean()); idx.append(X.index[e - 1])
    return pd.Series(out, index=idx).reindex(X.index, method="ffill")
AC21, AC63, AC126 = avg_corr(21), avg_corr(63), avg_corr(126)
def pr(x, n=252): return x.rolling(n, min_periods=n // 2).rank(pct=True)
def sb_corr(n=63):
    m = mkt_ex(); b = P["bonds_ret"]["UST10Y"]; j = pd.concat([m, b], axis=1).dropna(); return j.iloc[:, 0].rolling(n).corr(j.iloc[:, 1])
F61 = [
    ("STRAT-0601", "event-triggered", "after a correlation spike (avg industry correlation +0.2 in 5 days) go long the market for H days (post-panic rebound)",
     lambda p: timing(((AC21 - AC21.shift(5)) > 0.2).astype(float).replace(0, np.nan).ffill(limit=p["H"] - 1).fillna(0)), {"H": [10, 20]}),
    ("STRAT-0602", "cross-sectional", "industry short-term reversal only when average correlation is low (high dispersion) / high",
     lambda p: _xsrev(p["side"]), {"side": ["low", "high"]}),
    ("STRAT-0603", "time-series", "market timing on average industry correlation: long when it is above (sgn=+1) / below (sgn=-1) its 1-year median (Pollet-Wilson)",
     lambda p: timing(((pr(AC63) > 0.5) if p["sgn"] == 1 else (pr(AC63) <= 0.5)).astype(float)), {"sgn": [1, -1]}),
    ("STRAT-0604", "lead-lag", "falling correlation leads lower realised vol: short S&P variance only when 21-day correlation fell over the last month",
     lambda p: frame({"SPX": varswap("SPX", lambda j, r: ((AC21 - AC21.shift(21)).reindex(j.index, method="ffill").values[r] < 0).astype(int))}), {"x": [1]}),
    ("STRAT-0605", "regime-conditioned", "correlation timing (long when correlation high) only in calm / turbulent markets",
     lambda p: timing(((pr(AC63) > 0.5) & (((pr(mkt_ex().rolling(21).std()) < 0.5)) if p["reg"] == "calm" else (pr(mkt_ex().rolling(21).std()) >= 0.5))).astype(float)), {"reg": ["calm", "turbulent"]}),
    ("STRAT-0606", "term-structure", "correlation term structure: long the market when 21-day correlation exceeds 126-day correlation (short-term stress) / the reverse",
     lambda p: timing(((AC21 > AC126) if p["sgn"] == 1 else (AC21 <= AC126)).astype(float)), {"sgn": [1, -1]}),
    ("STRAT-0608", "relative-value", "stock-bond correlation regime: hold a risk-parity stock+10y book when the 3-month stock-bond correlation is negative, only stocks... (flat bonds) when positive",
     lambda p: _sbrp(p["n"]), {"n": [63, 126]}),
    ("STRAT-0609", "volatility-based", "diversification ratio (avg industry vol / market vol): long the market when diversification is high (low correlation) vs low",
     lambda p: timing(((pr(IND.rolling(63).std().mean(1) / mkt_ex().rolling(63).std()) > 0.5) if p["side"] == "high" else (pr(IND.rolling(63).std().mean(1) / mkt_ex().rolling(63).std()) <= 0.5)).astype(float)), {"side": ["high", "low"]}),
    ("STRAT-0610", "execution-aware", "correlation timing rebalanced monthly only", lambda p: timing((pr(AC63) > 0.5).astype(float).loc[lambda x: x.index.is_month_end].reindex(mkt_ex().index).ffill()), {"x": [1]}),
]
def _xsrev(side):
    R = P["ind49"].loc["1930":]; sc = -(R.rolling(5).sum()); rk = sc.rank(axis=1, pct=True); w = (rk >= 0.7).astype(float) - (rk <= 0.3).astype(float)
    g = (pr(AC63) <= 0.5) if side == "low" else (pr(AC63) > 0.5); w = w.mul(g.reindex(R.index).fillna(False).astype(float), axis=0)
    pnl = (w.shift(1) * R).sum(1) / w.abs().sum(1).shift(1).replace(0, np.nan) - (w.diff().abs().sum(1) / w.abs().sum(1).replace(0, np.nan)) * 5e-4
    return frame({"XSREV": pnl.fillna(0)})
def _sbrp(n):
    m = mkt_ex(); b = (P["bonds_ret"]["UST10Y"] - P["ff3"]["RF"].reindex(P["bonds_ret"].index).fillna(0)).reindex(m.index)
    c = sb_corr(n).reindex(m.index).shift(1); vm, vb = m.rolling(63).std().shift(1), b.rolling(63).std().shift(1)
    wb = ((vm / vb).clip(upper=5)).where(c < 0, 0.0).fillna(0)
    return frame({"SB": (m + wb * b.fillna(0)).loc["1965":]})
# ---------- gamma scalping: synthetic delta-hedged ATM straddle (Black-Scholes, r=q=0, IV = vol index) ----------
def ncdf(x): return 0.5 * (1 + np.vectorize(erf)(x / np.sqrt(2)))
def npdf(x): return np.exp(-x * x / 2) / np.sqrt(2 * np.pi)
def straddle(j, sign_fn, T=21, hedge_every=1, cost_vp=0.5):
    S = (1 + j.r).cumprod().values; sig = (j.iv.values / 100); n = len(S); rolls = np.arange(0, n - 1, T); sg = sign_fn(j, rolls); pnl = np.zeros(n)
    for q, s in enumerate(rolls):
        if sg[q] == 0: continue
        e = min(s + T, n - 1); K = S[s]
        def val(t):
            tau = max((s + T - t) / 252, 1e-6); v = sig[t] * np.sqrt(tau); d1 = (np.log(S[t] / K) + 0.5 * v * v) / v
            return S[t] * ncdf(d1) - K * ncdf(d1 - v) + (K * ncdf(-(d1 - v)) - S[t] * ncdf(-d1)), 2 * ncdf(d1) - 1, S[t] * npdf(d1) * np.sqrt(tau)
        V0, D, vega = val(s); prev = V0; pnl[s + 1] -= abs(sg[q]) * vega * 2 * cost_vp / 100 / K
        for t in range(s + 1, e + 1):
            V, Dn, _ = val(t) if t < e else (abs(S[t] - K), 0.0, 0.0)
            pnl[t] += sg[q] * ((V - prev) - D * (S[t] - S[t - 1])) / K
            if (t - s) % hedge_every == 0: pnl[t] -= abs(sg[q]) * abs(Dn - D) * S[t] * 1e-4 / K; D = Dn
            prev = V
    return pd.Series(pnl, index=j.index)
ALL = ["SPX", "NDX", "GOLD", "EUR"]
J9 = pd.DataFrame({"r": UND["SPX"].r, "iv": VIX9D.reindex(UND["SPX"].index)}).dropna()
F62 = [
    ("STRAT-0611", "event-triggered", "buy a 9-day delta-hedged S&P straddle (IV = VIX9D) only when the window contains payrolls day",
     lambda p: frame({"SPX": straddle(J9, lambda j, r: np.array([nfp_mask(j.index, 7).values[x] or nfp_mask(j.index, 1).values[min(x + 7, len(j) - 1)] for x in r]).astype(int), T=7)}), {"x": [1]}),
    ("STRAT-0612", "cross-sectional", "each month buy the delta-hedged straddle on the underlying with the LOWEST implied/realised ratio (cheapest gamma)",
     lambda p: _xs_cheap(), {"x": [1]}),
    ("STRAT-0613", "time-series", "always long one-month delta-hedged ATM straddles (pure gamma scalping), daily hedge",
     lambda p: frame({k: straddle(UND[k], lambda j, r: np.ones(len(r))) for k in p["set"]}), {"set": [("SPX",), tuple(ALL)]}),
    ("STRAT-0614", "lead-lag", "buy gamma only when 5-day realised vol is above 21-day realised vol (vol momentum)",
     lambda p: frame({k: straddle(UND[k], lambda j, r: (trail_rv(j, 5).values[r] > trail_rv(j, 21).values[r]).astype(int)) for k in ALL}), {"x": [1]}),
    ("STRAT-0615", "regime-conditioned", "buy gamma only when VIX is in its top half (turbulent) / bottom half",
     lambda p: frame({k: straddle(UND[k], lambda j, r: ((_vixpct(j) >= 0.5) if p["reg"] == "turbulent" else (_vixpct(j) < 0.5)).values[r].astype(int)) for k in ALL}), {"reg": ["turbulent", "calm"]}),
    ("STRAT-0616", "term-structure", "buy gamma only when VIX is in backwardation (VIX > VIX3M)",
     lambda p: frame({k: straddle(UND[k], lambda j, r: (_ts(j).values[r] > 1).astype(int)) for k in ALL}), {"x": [1]}),
    ("STRAT-0618", "relative-value", "buy gamma when implied < trailing realised (cheap), sell when implied > realised x1.5 (rich)",
     lambda p: frame({k: straddle(UND[k], lambda j, r: np.where((j.iv.values[r] / 100) ** 2 < trail_rv(j, 21).values[r], 1, np.where((j.iv.values[r] / 100) ** 2 > 1.5 * trail_rv(j, 21).values[r], -1, 0))) for k in ALL}), {"x": [1]}),
    ("STRAT-0619", "volatility-based", "straddle sign and size from the realised/implied ratio (long when > 1, short when < 0.7)",
     lambda p: frame({k: straddle(UND[k], lambda j, r: np.where(trail_rv(j, 21).values[r] / (j.iv.values[r] / 100) ** 2 > 1, 1, np.where(trail_rv(j, 21).values[r] / (j.iv.values[r] / 100) ** 2 < 0.7, -1, 0))) for k in ALL}), {"x": [1]}),
    ("STRAT-0620", "execution-aware", "always-long straddle but hedged weekly instead of daily (hedging frequency)", lambda p: frame({k: straddle(UND[k], lambda j, r: np.ones(len(r)), hedge_every=5) for k in ALL}), {"x": [1]}),
]
def _xs_cheap():
    R = pd.DataFrame({k: ((UND[k].iv / 100) ** 2 / trail_rv(UND[k], 21)) for k in ALL}); best = R.replace([np.inf, -np.inf], np.nan).fillna(99).idxmin(axis=1)
    return frame({k: straddle(UND[k], lambda j, r, k=k: (best.reindex(j.index, method="ffill").values[r] == k).astype(int)) for k in ALL})
# ---------- vol event premium: 7-trading-day variance swaps struck at VIX9D ----------
def vs9(fn): return varswap("SPX", fn, T=7, iv_override=J9)
NFP9 = lambda j, r: np.array([nfp_mask(j.index, 7).values[min(x + 7, len(j) - 1)] for x in r])   # window [x, x+7] contains a payrolls day
F70 = [
    ("STRAT-0691", "event-triggered", "sell 9-day variance only on windows that contain US payrolls day (event premium)", lambda p: frame({"SPX": vs9(lambda j, r: NFP9(j, r).astype(int))}), {"x": [1]}),
    ("STRAT-0692", "cross-sectional", "across windows: sell variance on non-event windows, buy it on event windows", lambda p: frame({"SPX": vs9(lambda j, r: np.where(NFP9(j, r), -1, 1))}), {"x": [1]}),
    ("STRAT-0693", "time-series", "always short 9-day variance (short-tenor variance risk premium)", lambda p: frame({"SPX": vs9(lambda j, r: np.ones(len(r)))}), {"x": [1]}),
    ("STRAT-0694", "lead-lag", "sell 9-day variance only when VIX9D/VIX > q (near-term event priced richly)", lambda p: frame({"SPX": vs9(lambda j, r: ((VIX9D / _fred("VIXCLS")).reindex(j.index, method="ffill").values[r] > p["q"]).astype(int))}), {"q": [1.0, 1.05]}),
    ("STRAT-0695", "regime-conditioned", "short 9-day variance only when VIX below / above its 1-year median", lambda p: frame({"SPX": vs9(lambda j, r: ((_vixpct(j) < 0.5) if p["reg"] == "calm" else (_vixpct(j) >= 0.5)).values[r].astype(int))}), {"reg": ["calm", "turbulent"]}),
    ("STRAT-0696", "term-structure", "short 9-day variance only when the whole curve is upward sloping (VIX9D < VIX < VIX3M)",
     lambda p: frame({"SPX": vs9(lambda j, r: ((VIX9D.reindex(j.index, method="ffill") < _fred("VIXCLS").reindex(j.index, method="ffill")) & (_ts(j) < 1)).values[r].astype(int))}), {"x": [1]}),
    ("STRAT-0698", "relative-value", "short 9-day variance against long one-month variance (event premium term spread)",
     lambda p: (lambda a, b: frame({"SP": (a - b.reindex(a.index).fillna(0) * p["h"]).loc["2011":]}))(vs9(lambda j, r: np.ones(len(r))), varswap("SPX", lambda j, r: np.ones(len(r)))), {"h": [0.5, 1.0]}),
    ("STRAT-0699", "volatility-based", "short 9-day variance only when VVIX is below its median", lambda p: frame({"SPX": vs9(lambda j, r: (VVIX.reindex(j.index, method="ffill") < VVIX.rolling(252).median().reindex(j.index, method="ffill")).values[r].astype(int))}), {"x": [1]}),
    ("STRAT-0700", "execution-aware", "always short 9-day variance, entered one day after the scheduled start", lambda p: frame({"SPX": vs9(lambda j, r: np.ones(len(r))).shift(1).fillna(0)}), {"x": [1]}),
]
FAMS = {"F61": ("Correlation trading", F61), "F62": ("Gamma scalping", F62), "F70": ("Volatility event premium", F70)}
BLOCKED = {630: ("Diagonal options spread", "option chains across strikes and expiries"), 640: ("Butterfly options volatility", "implied-vol smiles by strike"),
           650: ("Risk reversal positioning", "25-delta risk reversals"), 660: ("Dealer gamma exposure", "open interest by strike and dealer positioning"),
           670: ("Options open-interest pinning", "open interest by strike"), 680: ("Dispersion by sector", "sector ETF and constituent implied vols")}
EXTRA_BLOCK = {"STRAT-0607": "flow data on correlation products (index vs single-stock option volume)", "STRAT-0617": "options order-flow / dealer positioning data",
               "STRAT-0697": "event-option volume / positioning data"}
MERGED = {f"STRAT-{620 + j + 1:04d}": "STRAT-0573" for j in range(10)}   # calendar options spread = same synthetic calendar instrument as 0573
