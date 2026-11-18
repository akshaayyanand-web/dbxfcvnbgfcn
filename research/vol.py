"""Synthetic variance-swap streams from volatility indices (strike = index^2) and realised variance of the underlying.
Daily mark-to-market: long value V_t = N[ realised-so-far*252/T + (T-k)/T * IV_t^2 - K ], capped at 2.5x strike vol; N = 1/K.
Cost: 0.5 vol point bid/ask per roll. Positions (sign) are fixed at each roll date with information up to that close."""
import numpy as np, pandas as pd
from data import _fred, RDATA, SCR
from engine import P, _rets
def cboe(name):
    d = pd.read_csv(f"{RDATA}/cboe/{name}.csv"); d.columns = [c.upper() for c in d.columns]
    d.index = pd.to_datetime(d["DATE"], format="%m/%d/%Y"); col = "CLOSE" if "CLOSE" in d.columns else d.columns[-1]; return d[col].astype(float)
def mkt():
    f = P["ff3"]; return f["Mkt-RF"] + f["RF"]
def underlyings():
    cf = P["cfd"].copy(); cf.index = cf.index.tz_localize(None)
    U = {"SPX": (mkt(), _fred("VIXCLS")), "NDX": (_rets(P["macro"]["NASDAQCOM"]), _fred("VXNCLS")),
         "RUT": (_rets(cf["RUT"]), _fred("RVXCLS")), "GOLD": (_rets(cf["GOLD"]), _fred("GVZCLS")),
         "OIL": (_rets(P["macro"]["DCOILWTICO"].where(P["macro"]["DCOILWTICO"] > 0)).clip(-0.3, 0.3), _fred("OVXCLS")), "EUR": (_rets(P["fx"]["EU"]), _fred("EVZCLS"))}
    out = {}
    for k, (r, iv) in U.items():
        j = pd.concat([r.rename("r"), iv.rename("iv")], axis=1).dropna(); j = j[j.index.dayofweek < 5]; out[k] = j
    return out
UND = underlyings()
def roll_dates(idx, T): return idx[::T]
def varswap(name, sign_fn, T=21, cost_vp=0.5, iv_override=None, ann=252):
    """sign_fn(j, roll_index_positions) -> array of +1 (short var) / -1 (long var) / 0 per roll. Returns daily P&L Series (per unit N=1/K)."""
    j = UND[name] if iv_override is None else iv_override; r = j.r.values; iv = (j.iv.values / 100) ** 2; n = len(j)
    rolls = np.arange(0, n - 1, T); sg = sign_fn(j, rolls); pnl = np.zeros(n)
    for q, s in enumerate(rolls):
        if sg[q] == 0: continue
        e = min(s + T, n - 1); K = iv[s]; N = 1 / K; cap = 6.25 * K; prev = 0.0; acc = 0.0
        for t in range(s + 1, e + 1):
            acc += r[t] ** 2; k = t - s
            V = N * (min(acc * ann / T + (T - k) / T * iv[t], cap) - K) if t < e else N * (min(acc * ann / T, cap) - K)
            pnl[t] += -sg[q] * (V - prev); prev = V
        pnl[s + 1] -= abs(sg[q]) * N * 2 * np.sqrt(K) * (cost_vp / 100)    # bid/ask in variance terms
    return pd.Series(pnl, index=j.index)
def trail_rv(j, n=21): return (j.r ** 2).rolling(n).mean() * 252
