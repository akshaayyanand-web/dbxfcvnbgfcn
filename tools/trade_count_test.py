# Run from the scratchpad.
import sys, numpy as np, pandas as pd
exec(open('readd_full.py').read().split("CAND = {")[0])
hiq = None
bq = bars1("fut1m/USATECHIDXUSD_1m.csv", "15min"); cq = bq.c; Cq = cq.to_numpy()
aq = rma(pd.concat([bq.h - bq.l, (bq.h - cq.shift()).abs(), (bq.l - cq.shift()).abs()], axis=1).max(axis=1), 14).to_numpy()
nyq = bq.index.tz_convert("America/New_York"); mq = nyq.hour * 60 + nyq.minute; wq = (mq >= 570) & (mq < 720)
BO = simT(bq, wq & (Cq > bq.h.rolling(20).max().shift(1).to_numpy()) & (Cq > cq.ewm(span=200, adjust=False).mean().to_numpy()), wq & (Cq < bq.l.rolling(20).min().shift(1).to_numpy()) & (Cq < cq.ewm(span=200, adjust=False).mean().to_numpy()), aq, 10 ** 6, mq >= 950)
SB = simT(b5, w5 & (C5 > hi) & (C5 > e5), w5 & (C5 < lo5) & (C5 < e5), 2 * a5, 10 ** 6, m5 >= 950)
TRL = pd.read_pickle("ea_trades.pkl"); TRL["NQ_Breakout_15m"] = (BO, 0, 0); TRL["SPX_Breakout_5m (optional)"] = (SB, 0, 0)
rows = []
for nm, (tr, c, r) in TRL.items():
    t = pd.DatetimeIndex([x[0] for x in tr]); t = t[(t >= "2025-01-01") & (t < "2026-10-30")]
    wd = pd.bdate_range("2025-01-01", "2026-10-29").size
    rows.append(dict(EA=nm, trades_per_weekday=len(t) / wd))
df = pd.DataFrame(rows); print(df.round(2).to_string(index=False))
core = df[~df.EA.str.contains("optional")].trades_per_weekday.sum()
print(f"11 core EAs: {core:.1f} trades per weekday | with SPX_Breakout_5m: {df.trades_per_weekday.sum():.1f}")
