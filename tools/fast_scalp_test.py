# Fast NQ scalps with real costs (2.5 pts, and 5 pts): opening drive / ORB break / 5m breakout, target 0.5-2R, max hold 15-60 min, 2020-2026.
import sys, numpy as np, pandas as pd
sys.path.insert(0, "/home/user/dbxfcvnbgfcn/tools")
from portfolio_prop import load_csv, rma
m1 = load_csv("fut1m/USATECHIDXUSD_1m.csv").loc["2020-01-01":]
O, H, L, C, T = m1.o.to_numpy(), m1.h.to_numpy(), m1.l.to_numpy(), m1.c.to_numpy(), m1.index
ny = T.tz_convert("America/New_York"); mins = (ny.hour * 60 + ny.minute).to_numpy(); dkey = (ny.year * 10000 + ny.month * 100 + ny.day).to_numpy(); n = len(C)
b5 = m1.resample("5min").agg(dict(o="first", h="max", l="min", c="last")).dropna()
atr5 = rma(pd.concat([b5.h - b5.l, (b5.h - b5.c.shift()).abs(), (b5.l - b5.c.shift()).abs()], axis=1).max(axis=1), 14)
ema5 = b5.c.ewm(span=800, adjust=False).mean(); hi50 = b5.h.rolling(50).max().shift(1); lo50 = b5.l.rolling(50).min().shift(1)
def first_idx(day_mask_min):
    return None
# per-day opening data
days = {}
for i in np.where(mins == 570)[0]: days[dkey[i]] = i     # 09:30 bar index
SIG = {"opening drive (09:30-09:35 candle)": [], "ORB 09:30-09:45 break": [], "5m breakout50 EMA800": []}
for dk, i0 in days.items():
    if i0 + 20 >= n or dkey[i0 + 5] != dk: continue
    h5, l5 = H[i0:i0 + 5].max(), L[i0:i0 + 5].min(); d = 1 if C[i0 + 4] > O[i0] else -1
    SIG["opening drive (09:30-09:35 candle)"].append((i0 + 5, d, l5 if d == 1 else h5))
    if i0 + 15 < n and dkey[i0 + 15] == dk:
        h15, l15 = H[i0:i0 + 15].max(), L[i0:i0 + 15].min()
        for j in range(i0 + 15, min(i0 + 120, n - 1)):
            if dkey[j] != dk: break
            if C[j] > h15: SIG["ORB 09:30-09:45 break"].append((j + 1, 1, l15)); break
            if C[j] < l15: SIG["ORB 09:30-09:45 break"].append((j + 1, -1, h15)); break
bt = b5.index; bny = bt.tz_convert("America/New_York"); bm = (bny.hour * 60 + bny.minute).to_numpy()
ok = (bm >= 570) & (bm < 720)
for k in np.where(ok & (((b5.c > hi50) & (b5.c > ema5)) | ((b5.c < lo50) & (b5.c < ema5))).to_numpy())[0]:
    d = 1 if b5.c.iloc[k] > hi50.iloc[k] else -1; i = T.searchsorted(bt[k] + pd.Timedelta("5min"))
    if i < n: SIG["5m breakout50 EMA800"].append((i, d, O[i] - d * 1.0 * atr5.iloc[k]))
def sim(sigs, tgtR, maxmin, cost):
    out, when, held, free = [], [], [], 0
    for i, d, st in sigs:
        if i < free or i >= n: continue
        e = O[i]; R = abs(e - st)
        if R < 5 or (st - e) * d >= 0: continue
        tp = e + d * tgtR * R; px = None
        for j in range(i, min(i + maxmin, n)):
            if (L[j] <= st) if d == 1 else (H[j] >= st): px = st; break
            if (H[j] >= tp) if d == 1 else (L[j] <= tp): px = tp; break
        if px is None: j = min(i + maxmin, n - 1); px = O[j]
        out.append(((px - e) * d - cost) / R); when.append(T[i]); held.append(j - i + 1); free = j + 1
    return np.array(out), pd.DatetimeIndex(when), np.array(held)
rows = []
for name, sigs in SIG.items():
    for tgtR in (0.5, 1.0, 1.5, 2.0):
        for maxmin in (15, 30, 60):
            r, w, hd = sim(sigs, tgtR, maxmin, 2.5); r2, _, _ = sim(sigs, tgtR, maxmin, 5.0)
            A = w < pd.Timestamp("2023-01-01", tz="UTC"); ya = (w[A][-1] - w[A][0]).days / 365.25; yb = (w[~A][-1] - w[~A][0]).days / 365.25
            rows.append(dict(entry=name, target=f"{tgtR}R", max_hold=f"{maxmin}m", trades_day=round(len(r) / ((w[-1] - w[0]).days * 252 / 365), 2),
                             median_hold_min=int(np.median(hd)), win=round(100 * (r > 0).mean(), 1), avgR=round(r.mean(), 3),
                             R_yr_2020_22=round(r[A].sum() / ya, 1), R_yr_2023_26=round(r[~A].sum() / yb, 1), R_yr_2x_cost=round(r2.sum() / ((w[-1] - w[0]).days / 365.25), 1)))
df = pd.DataFrame(rows); df["minhalf"] = df[["R_yr_2020_22", "R_yr_2023_26"]].min(axis=1)
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 60)
print(f"{len(df)} versions; positive both halves: {(df.minhalf > 0).sum()}; and positive with 2x cost: {((df.minhalf > 0) & (df.R_yr_2x_cost > 0)).sum()}")
print(df.sort_values("minhalf", ascending=False).drop(columns="minhalf").to_string(index=False))
df.to_pickle("fast_scalp.pkl")
