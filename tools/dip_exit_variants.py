# BTC Dip v3 / Gold Dip with win-focused exits, judged inside the 8-EA portfolio.
import sys, numpy as np, pandas as pd
SP = sys.argv[1]
exec(open(SP + "/speed8.py").read().split("V2 = [")[0])
from portfolio_prop import resample, rsi, rma

def dip_x(raw1h, tf, rl, buy, crash_pct, mode, width=1.5, hold_mult=3):
    b = resample(raw1h, tf) if tf != "1h" else raw1h; c = b.c
    d = raw1h.c.resample("1D").last().dropna()
    crash = (d / d.shift(30) - 1 < -crash_pct).shift(1).reindex(b.index.floor("D")).fillna(False).to_numpy().astype(bool)
    sig = ((rsi(c, rl) < buy) & (c > c.ewm(span=50, adjust=False).mean())).to_numpy() & ~crash
    tr = pd.concat([b.h - b.l, (b.h - c.shift()).abs(), (b.l - c.shift()).abs()], axis=1).max(axis=1)
    atr = rma(tr, 14).to_numpy(); sma = c.rolling(20).mean().to_numpy()
    O, H, L, C, T = b.o.to_numpy(), b.h.to_numpy(), b.l.to_numpy(), c.to_numpy(), b.index
    bar = T[1] - T[0]; max_bars = int(pd.Timedelta("96h") / bar); hold = max_bars if mode in ("time", "mean") else max_bars * hold_mult
    out, i = [], 0
    while i < len(C) - 2:
        if not sig[i] or np.isnan(atr[i]): i += 1; continue
        j = i + 1; e, st = O[j], C[i] - 2 * atr[i]; a0 = atr[i]
        if e <= st: i += 1; continue
        k, px, trail = j, None, False
        while k < len(C) - 1:
            if L[k] <= st: px, xt = min(O[k], st), T[k] + bar; break
            if k - j + 1 >= hold: px, xt = O[k + 1], T[k + 1]; k += 1; break
            if mode == "mean" and C[k] >= sma[k]: px, xt = O[k + 1], T[k + 1]; k += 1; break
            if mode == "trail_mean" and C[k] >= sma[k]: trail = True
            if mode == "trail_R" and H[k] >= e + (e - C[i] + 2 * a0) * 0 + (e - st): trail = True
            if trail: st = max(st, C[k] - width * a0, e)
            k += 1
        if px is None: break
        if xt - T[j] <= pd.Timedelta(days=10 * (1 if mode in ("time", "mean") else hold_mult)): out.append((T[j], xt, e, C[i] - 2 * a0, px))
        i = k
    return out

from multiprocessing import Pool
def job(v):
    which, mode, width = v
    raw, tf, rl, buy, cr, cost = (btc, "2h", 3, 20, 0.15, P.FEE_CRYPTO) if which == "btc" else (gold, "1h", 2, 10, 0.08, P.COST["XAUUSD"])
    tr = dip_x(raw, tf, rl, buy, cr, mode, width)
    # trade_series sizes by the ORIGINAL stop (entry - 2 ATR) -> risk stays 1% per trade; exits at px
    r, lo = P.trade_series(tr, cost, raw, idx)
    k = names.index("btc" if which == "btc" else "gdip"); R2, LO2 = R.copy(), LO.copy(); R2[k], LO2[k] = r, lo
    globals()["R"], globals()["LO"] = R2, LO2
    res = []
    for s_ in est:
        h0 = idx.searchsorted(s_); a, i1 = run2(W, h0, len(idx), 0.10)
        if a != "pass": res.append((s_, a, None)); continue
        b, i2 = run2(W, h0 + i1 + 1, len(idx), 0.05); res.append((s_, b, (i1 + i2) / 24 if b == "pass" else None))
    wst = pd.date_range("2020-04-01", "2025-10-01", freq="MS", tz="UTC"); yrs = []
    for s_ in wst:
        st_, _, ret = run(W, idx.searchsorted(s_), idx.searchsorted(s_ + pd.DateOffset(years=1))); yrs.append((s_, 100 * ret, st_ == "fail"))
    wins = np.array([t[4] > t[2] for t in tr]); alone = r.sum() / ((idx[-1] - idx[0]).days / 365.25) * 100
    return dict(strategy=which, exit=mode, width=width, trades=len(tr), win=100 * wins.mean(), alone_yr=alone,
                **{f"{p}_{m}": val for p, sel in (("A", lambda s: s < split), ("B", lambda s: s >= split))
                   for m, val in (("pass", 100 * np.mean([x[1] == "pass" for x in res if sel(x[0])])), ("breach", 100 * np.mean([x[1] == "fail" for x in res if sel(x[0])])),
                                  ("days", np.median([x[2] for x in res if sel(x[0]) and x[2] is not None])),
                                  ("fund_med", np.median([y[1] for y in yrs if sel(y[0])])), ("fund_br", sum(y[2] for y in yrs if sel(y[0]))))})
V = [(w, m, wd) for w in ("btc", "gold") for m, wd in (("time", 0), ("mean", 0), ("trail_mean", 1.5), ("trail_mean", 2.5), ("trail_R", 1.5), ("trail_R", 2.5))]
with Pool(3) as p: out = p.map(job, V)
pd.set_option("display.width", 250); print(pd.DataFrame(out).round(1).to_string(index=False))
