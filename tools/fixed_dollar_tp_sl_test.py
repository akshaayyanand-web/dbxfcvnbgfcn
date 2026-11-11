# Run from the scratchpad (needs fut1m data).
# Fixed-dollar take-profit $1,000 / stop-loss $2,000 per trade on a $100K account (TP = half the SL distance in price).
import sys, numpy as np, pandas as pd
sys.path.insert(0, "/home/user/dbxfcvnbgfcn/tools")
from portfolio_prop import load_csv
rng = np.random.default_rng(7)
MK = {"Nasdaq": ("fut1m/USATECHIDXUSD_1m.csv", 1.5, [4, 10, 25, 60]),      # spread in points; SL distances in points
      "Gold": ("fut1m/XAUUSD_1m.csv", 0.25, [0.5, 1.5, 4, 10])}           # spread in $; SL distances in $
rows = []
for mk, (f, spread, sls) in MK.items():
    d = load_csv(f).loc["2019-03-01":]; T = d.index; ny = T.tz_convert("America/New_York"); m = (ny.hour * 60 + ny.minute).to_numpy()
    O, H, L = d.o.to_numpy(), d.h.to_numpy(), d.l.to_numpy()
    cand = np.flatnonzero((m >= 570) & (m < 900) & (ny.weekday < 5))
    entries = np.sort(rng.choice(cand, 6000, replace=False))
    trend = pd.Series(d.c.to_numpy()).ewm(span=600).mean().to_numpy()
    for sl in sls:
        tp = sl / 2
        for mode in ("random direction", "with the trend"):
            res = []
            for j in entries:
                dr = rng.choice([-1, 1]) if mode == "random direction" else (1 if d.c.iloc[j - 1] > trend[j - 1] else -1)
                e = O[j] + dr * spread / 2      # pay half the spread on entry ...
                tgt, stp = e + dr * tp, e - dr * sl
                out = 0
                for k in range(j, min(j + 2000, len(O))):
                    hit_sl = (L[k] - spread / 2 <= stp) if dr == 1 else (H[k] + spread / 2 >= stp)
                    hit_tp = (H[k] - spread / 2 >= tgt) if dr == 1 else (L[k] + spread / 2 <= tgt)
                    if hit_sl: out = -2000; break          # if both in the same minute, assume the stop came first
                    if hit_tp: out = 1000; break
                res.append((T[j], out))
            s = pd.Series([r[1] for r in res], index=[r[0] for r in res]); done = s[s != 0]
            A = done.index < pd.Timestamp("2023-01-01", tz="UTC")
            rows.append(dict(market=mk, SL=f"{sl} ({'pts' if mk == 'Nasdaq' else '$'})", spread_share_of_TP=f"{spread / tp:.0%}", entries=mode,
                             win_rate=100 * (done > 0).mean(), avg_per_trade_usd=done.mean(), avg_2019_22=done[A].mean(), avg_2023_26=done[~A].mean()))
df = pd.DataFrame(rows); pd.set_option("display.width", 250); print(df.round(1).to_string(index=False))
print("\nbreak-even win rate before costs: 66.7%")
