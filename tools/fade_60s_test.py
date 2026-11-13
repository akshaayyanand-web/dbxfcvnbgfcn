# 6-year check of the one tick signal that beat the spread: fade a top-2% 1-minute NQ move (busy tape), hold 1-5 min, 2020-2026.
import sys, numpy as np, pandas as pd
sys.path.insert(0, "/home/user/dbxfcvnbgfcn/tools")
from portfolio_prop import load_csv
m1 = load_csv("fut1m/USATECHIDXUSD_1m.csv").loc["2020-01-01":]
O, C, V, T = m1.o.to_numpy(), m1.c.to_numpy(), m1.v.to_numpy(), m1.index
ny = T.tz_convert("America/New_York"); mins = (ny.hour * 60 + ny.minute).to_numpy(); wd = ny.weekday.to_numpy()
mv = C - O                                             # the 1-minute move
look = 390 * 20
thr = pd.Series(np.abs(mv)).rolling(look, min_periods=2000).quantile(0.98).shift(1).to_numpy()
vthr = pd.Series(V).rolling(look, min_periods=2000).quantile(0.8).shift(1).to_numpy()
rows = []
for busy in (True, False):
    sig = np.where((mins >= 575) & (mins < 955) & (wd < 5) & np.isfinite(thr) & (np.abs(mv) >= thr) & ((V >= vthr) if busy else True))[0]
    for hold in (1, 2, 3, 5):
        for spread in (2.1, 1.0):
            res, when, free = [], [], 0
            for i in sig:
                if i < free or i + 1 + hold >= len(O): continue
                d = -1 if mv[i] > 0 else 1                       # fade
                e = O[i + 1]; x = O[i + 1 + hold]
                res.append((x - e) * d - spread); when.append(T[i]); free = i + 1 + hold
            r = np.array(res); w = pd.DatetimeIndex(when); A = w < pd.Timestamp("2023-01-01", tz="UTC")
            rows.append(dict(busy_tape=busy, hold_min=hold, spread=spread, trades=len(r), trades_day=round(len(r) / 1700, 1), win=round(100 * (r > 0).mean(), 1),
                             avg_pts=round(r.mean(), 2), pts_2020_22=round(r[A].mean(), 2), pts_2023_26=round(r[~A].mean(), 2), usd_per_trade_50lots=round(50 * r.mean())))
pd.set_option("display.width", 250); print(pd.DataFrame(rows).to_string(index=False))
