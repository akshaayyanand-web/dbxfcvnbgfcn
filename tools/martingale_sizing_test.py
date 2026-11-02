# Martingale sizing on the six-strategy preset (per-strategy loss streaks), same account engine as eval_speed.py
import sys, numpy as np, pandas as pd
import portfolio_prop as P
REC = []
_orig = P.trade_series
def rec(trades, cost, h1, idx):
    REC.append((list(trades), cost, h1)); return _orig(trades, cost, h1, idx)
P.trade_series = rec
exec(open(sys.argv[1] + "/portfolio5.py").read().split("evalw=")[0])
TR = dict(zip(names, REC))

def series_mult(trades, cost, h1, idx, mode, f, steps):
    """Same as trade_series, but each trade is scaled by a multiplier set from the strategy's own previous results."""
    r, lo = np.zeros(len(idx)), np.zeros(len(idx))
    Cc, L, H = (h1[k].reindex(idx).ffill().to_numpy() for k in ("c", "l", "h"))
    trades = sorted(trades, key=lambda t: t[0]); done = []; streak = 0; last_exit = None
    for et, xt, e, st, px in trades:
        a, z = idx.searchsorted(et), idx.searchsorted(xt)
        if a >= len(idx) or xt <= idx[0]: continue
        z = max(z, a + 1); dr = 1 if st < e else -1
        m = f ** min(streak, steps) if mode != "flat" else 1.0
        n = m * 0.01 / (abs(e - st) / e); prev = e; tot = -n * cost
        for h in range(a, min(z, len(idx))):
            cur = px if h == min(z, len(idx)) - 1 else Cc[h]
            r[h] += n * dr * (cur / prev - 1); tot += n * dr * (cur / prev - 1)
            adv = max(min(L[h], cur), st) if dr == 1 else min(max(H[h], cur), st)
            lo[h] += n * dr * (adv / prev - 1); prev = cur
        r[a] -= n * cost
        bad = tot < 0
        if mode == "martingale":   # double after a loss, reset after a win or after the last step loses
            streak = 0 if (not bad or streak >= steps) else streak + 1
        elif mode == "anti":       # size up after a win, reset after a loss
            streak = 0 if (bad or streak >= steps) else streak + 1
    return r, lo

w = np.array([dict(btc=1.0, gdip=0.5, gasia=0.25, nqmom=0.25, gmom=0.25, orb15=0.5).get(k, 0) for k in names], float)
use = [k for k in names if w[names.index(k)] > 0]
variants = [("Flat (current)", "flat", 1, 0, 1.0),
            ("Martingale x2, up to 3 doublings (1-2-4-8)", "martingale", 2, 3, 1.0),
            ("Martingale x2, up to 2 doublings (1-2-4)", "martingale", 2, 2, 1.0),
            ("Martingale x1.5, up to 3 steps", "martingale", 1.5, 3, 1.0),
            ("Martingale x2 (1-2-4), base risk /4 = same max", "martingale", 2, 2, 0.25),
            ("Martingale x2 (1-2-4), base risk /2", "martingale", 2, 2, 0.5),
            ("Anti-martingale x1.5 after a win, 2 steps", "anti", 1.5, 2, 1.0)]
wst = pd.date_range("2020-04-01", "2025-10-01", freq="MS", tz="UTC"); est = pd.date_range("2020-04-01", "2025-09-01", freq="7D", tz="UTC")
R0, LO0 = R.copy(), LO.copy()
print(f"\n{'variant':<48} | {'2-step pass':>11}{'breach':>7}{'halted':>7}{'median':>8} | {'funded yr med':>13}{'avg':>7}{'breach':>8}{'worst':>7}")
for nm, mode, f, steps, scale in variants:
    R, LO = R0.copy(), LO0.copy()
    for k in use:
        tr, c, h1 = TR[k]; i = names.index(k); R[i], LO[i] = series_mult(tr, c, h1, idx, mode, f, steps)
    ww = w * scale
    res = []; tot = []
    for s in est:
        h0 = idx.searchsorted(s); a_, i1, _ = run(ww, h0, len(idx), 0.10)
        if a_ != "pass": res.append(a_); continue
        b_, i2, _ = run(ww, h0 + i1 + 1, len(idx), 0.05)
        res.append(b_)
        if b_ == "pass": tot.append((i1 + i2) / 24)
    yr = []; br = 0
    for s in wst:
        st_, _, ret = run(ww, idx.searchsorted(s), idx.searchsorted(s + pd.DateOffset(years=1))); yr.append(100 * ret); br += st_ == "fail"
    rr = pd.Series(res)
    print(f"{nm:<48} | {100*(rr=='pass').mean():10.0f}%{100*(rr=='fail').mean():6.0f}%{100*(rr=='stopped').mean():6.0f}%{np.median(tot) if tot else np.nan:7.0f}d | "
          f"{np.median(yr):+12.1f}%{np.mean(yr):+6.1f}%{br:5d}/{len(wst)}{min(yr):+6.0f}%")
