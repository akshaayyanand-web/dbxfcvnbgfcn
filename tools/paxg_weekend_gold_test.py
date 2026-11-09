# Run from the scratchpad (Binance PAXGUSDT 1h files in paxg/, gold hourly in fut/).
# Weekend PAXG (tokenised gold, trades 24/7) move vs real gold after the Sunday reopen.
import glob, sys, numpy as np, pandas as pd
sys.path.insert(0, "/home/user/dbxfcvnbgfcn/tools")
from portfolio_prop import load_csv
p = pd.concat([pd.read_csv(f, header=None, usecols=[0, 1, 2, 3, 4], names=["t", "o", "h", "l", "c"]) for f in sorted(glob.glob("paxg/*.csv"))])
p["t"] = np.where(p.t > 1e14, p.t // 1000, p.t); p.index = pd.to_datetime(p.t, unit="ms", utc=True); p = p[~p.index.duplicated()].sort_index()
g = load_csv("fut/XAUUSD.csv").loc["2020-08-01":]; gny = g.index.tz_convert("America/New_York")
tr_atr = pd.concat([g.h - g.l, (g.h - g.c.shift()).abs(), (g.l - g.c.shift()).abs()], axis=1).max(axis=1).ewm(alpha=1 / 14, adjust=False).mean().shift(1)
reopen = g.index[(gny.weekday == 6) | ((gny.weekday == 0) & (gny.hour < 2))]
firsts = pd.Series(reopen).groupby(pd.Series(reopen).dt.tz_convert("America/New_York").dt.to_period("W-SAT")).first()
rows = []
for wk, t0 in firsts.items():
    fri = g.index[(g.index < t0) & (g.index > t0 - pd.Timedelta("3D"))]
    if not len(fri): continue
    gf = g.c.loc[fri[-1]]; pf = p.c.asof(fri[-1] + pd.Timedelta("59min")); ps = p.c.asof(t0 - pd.Timedelta("1min"))
    if not (np.isfinite(pf) and np.isfinite(ps)): continue
    pm = ps / pf - 1; go = g.o.loc[t0]; gap = go / gf - 1
    seg = g.loc[t0:t0 + pd.Timedelta("48h")]
    rows.append(dict(t=t0, paxg_move=pm, gold_gap=gap, after_24h=g.c.asof(t0 + pd.Timedelta("24h")) / go - 1, after_48h=g.c.asof(t0 + pd.Timedelta("48h")) / go - 1, atr=tr_atr.asof(t0) / go))
df = pd.DataFrame(rows).dropna()
print(f"{len(df)} weekends. corr(PAXG weekend move, gold reopen gap) = {df.paxg_move.corr(df.gold_gap):.2f}")
print(f"corr(PAXG weekend move, gold move in the 24h AFTER reopen) = {df.paxg_move.corr(df.after_24h):.2f}; 48h: {df.paxg_move.corr(df.after_48h):.2f}")
df["resid"] = df.paxg_move - df.gold_gap
print(f"corr(PAXG move not yet in the gap, gold next 24h) = {df.resid.corr(df.after_24h):.2f}")
for thr in (0.003, 0.006, 0.01):
    s = df[df.paxg_move.abs() > thr]; d = np.sign(s.paxg_move)
    r24 = (d * s.after_24h - 0.0002) / (1.5 * s.atr); r48 = (d * s.after_48h - 0.0002) / (1.5 * s.atr)
    A = s.t < pd.Timestamp("2023-01-01", tz="UTC")
    print(f"follow PAXG > {thr:.1%}: {len(s)} trades, avg R (no stop) 24h {r24.mean():+.2f} [2020-22 {r24[A].mean():+.2f}, 2023-26 {r24[~A].mean():+.2f}], 48h {r48.mean():+.2f}")
