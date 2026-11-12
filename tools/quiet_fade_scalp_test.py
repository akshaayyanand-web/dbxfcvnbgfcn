# Quiet-hours limit-order fade scalps (NQ / S&P overnight, gold Asia): limit at the 30/60-min range edge, target the range middle, strict fills.
import sys, numpy as np, pandas as pd
sys.path.insert(0, "/home/user/dbxfcvnbgfcn/tools")
from portfolio_prop import load_csv
SETS = {"NQ overnight 20:00-03:00 NY": ("fut1m/USATECHIDXUSD_1m.csv", "America/New_York", 1200, 180, 2.1, 0.25),
        "S&P overnight 20:00-03:00 NY": ("fut1m/USA500IDXUSD_1m.csv", "America/New_York", 1200, 180, 0.6, 0.1),
        "Gold Asia 00:00-06:00 London": ("fut1m/XAUUSD_1m.csv", "Europe/London", 0, 360, 0.3, 0.01)}
rows = []
for name, (path, tz, a0, a1, spread, tick) in SETS.items():
    m = load_csv(path).loc["2020-01-01":]; O, H, L, C, T = m.o.to_numpy(), m.h.to_numpy(), m.l.to_numpy(), m.c.to_numpy(), m.index
    z = T.tz_convert(tz); mins = (z.hour * 60 + z.minute).to_numpy(); wd = z.weekday.to_numpy(); n = len(C)
    inwin = ((mins >= a0) | (mins < a1)) if a0 > a1 else ((mins >= a0) & (mins < a1))
    for look in (30, 60):
        rh = pd.Series(H).rolling(look).max().shift(1).to_numpy(); rl = pd.Series(L).rolling(look).min().shift(1).to_numpy()
        for ext in (0.0, 0.25):           # limit placed at the range edge, or 25% of the range beyond it
            for stopx in (0.5, 1.0):      # stop this many range-widths beyond the entry
                out, when, free = [], [], 0
                for i in range(look + 1, n - 1):
                    if i < free or not inwin[i] or wd[i] >= 5: continue
                    rng_ = rh[i] - rl[i]
                    if not rng_ > 4 * spread: continue
                    mid = (rh[i] + rl[i]) / 2; hs = spread / 2
                    buy = rl[i] - ext * rng_; sell = rh[i] + ext * rng_
                    d = 1 if L[i] < buy - hs - tick else (-1 if H[i] > sell + hs + tick else 0)   # strict fill: traded through by a tick
                    if d == 0: continue
                    e = buy if d == 1 else sell; st = e - d * stopx * rng_; tp = mid; R = abs(e - st); px = None
                    for j in range(i + 1, min(i + 120, n)):
                        if (L[j] <= st - hs) if d == 1 else (H[j] >= st + hs): px = st; break
                        if (H[j] >= tp + hs) if d == 1 else (L[j] <= tp - hs): px = tp; break
                    if px is None: j = min(i + 120, n - 1); px = O[j] - d * hs
                    out.append(((px - e) * d - spread / 2) / R); when.append(T[i]); free = j + 1     # limit entry: half spread paid on exit only
                if len(out) < 100: continue
                r = np.array(out); w = pd.DatetimeIndex(when); A = w < pd.Timestamp("2023-01-01", tz="UTC")
                ya = (w[A][-1] - w[A][0]).days / 365.25; yb = (w[~A][-1] - w[~A][0]).days / 365.25
                rows.append(dict(setup=name, range=f"{look}m", limit=f"edge+{int(ext*100)}%", stop=f"{stopx}x range", trades_day=round(len(r) / ((w[-1] - w[0]).days * 252 / 365), 1),
                                 win=round(100 * (r > 0).mean(), 1), avgR=round(r.mean(), 3), R_yr_2020_22=round(r[A].sum() / ya, 1), R_yr_2023_26=round(r[~A].sum() / yb, 1)))
df = pd.DataFrame(rows); df["minhalf"] = df[["R_yr_2020_22", "R_yr_2023_26"]].min(axis=1)
pd.set_option("display.width", 250)
print(f"{len(df)} versions; positive in both halves: {(df.minhalf > 0).sum()}")
print(df.sort_values("minhalf", ascending=False).drop(columns="minhalf").to_string(index=False))
