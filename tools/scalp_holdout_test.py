# Scalp search with a holdout: 177 NQ short-hold versions picked on 2020-2023, top 5 tested once on 2024-2026 (futures 1pt and CFD 2.1pt costs).
import sys, numpy as np, pandas as pd
sys.path.insert(0, "/home/user/dbxfcvnbgfcn/tools")
from portfolio_prop import load_csv, rma
m1 = load_csv("fut1m/USATECHIDXUSD_1m.csv").loc["2020-01-01":]
O, H, L, C, T = m1.o.to_numpy(), m1.h.to_numpy(), m1.l.to_numpy(), m1.c.to_numpy(), m1.index
ny = T.tz_convert("America/New_York"); mins = (ny.hour * 60 + ny.minute).to_numpy(); dkey = (ny.year * 10000 + ny.month * 100 + ny.day).to_numpy(); n = len(C)
b5 = m1.resample("5min").agg(dict(o="first", h="max", l="min", c="last")).dropna()
atr5 = rma(pd.concat([b5.h - b5.l, (b5.h - b5.c.shift()).abs(), (b5.l - b5.c.shift()).abs()], axis=1).max(axis=1), 14)
ema800 = b5.c.ewm(span=800, adjust=False).mean(); hi50 = b5.h.rolling(50).max().shift(1); lo50 = b5.l.rolling(50).min().shift(1)
reg = (atr5 / atr5.rolling(78 * 20).median()).shift(1)          # volatility regime vs the last ~20 days
bt = b5.index; bm = (bt.tz_convert("America/New_York").hour * 60 + bt.tz_convert("America/New_York").minute).to_numpy()
def regime_ok(ts, rg):
    v = reg.asof(ts)
    return True if rg == "any" else (v > 1 if rg == "high" else v <= 1)
FAM = {}
WIN = {"09:30-10:30": (570, 630), "10:30-12:00": (630, 720), "13:30-15:30": (810, 930)}
for wn, (a, z) in WIN.items():
    for filt in ("EMA800", "none"):
        cond_l = (b5.c > hi50) & ((b5.c > ema800) if filt == "EMA800" else True); cond_s = (b5.c < lo50) & ((b5.c < ema800) if filt == "EMA800" else True)
        idxs = np.where(((bm >= a) & (bm < z)) & (cond_l | cond_s).to_numpy())[0]
        FAM[f"5m breakout {wn} {filt}"] = [(bt[k], 1 if cond_l.iloc[k] else -1, "atr", atr5.iloc[k]) for k in idxs]
days = {}
for i in np.where(mins == 570)[0]: days[dkey[i]] = i
od, orb = [], []
for dk, i0 in days.items():
    if i0 + 16 >= n or dkey[i0 + 15] != dk: continue
    h5, l5 = H[i0:i0 + 5].max(), L[i0:i0 + 5].min(); d = 1 if C[i0 + 4] > O[i0] else -1
    od.append((T[i0 + 5], d, "px", l5 if d == 1 else h5))
    h15, l15 = H[i0:i0 + 15].max(), L[i0:i0 + 15].min()
    for j in range(i0 + 15, min(i0 + 120, n - 1)):
        if dkey[j] != dk: break
        if C[j] > h15: orb.append((T[j + 1], 1, "px", l15)); break
        if C[j] < l15: orb.append((T[j + 1], -1, "px", h15)); break
FAM["opening drive"] = od; FAM["ORB 15m break"] = orb
def sim(sigs, rg, tgtR, maxmin, cost, period):
    out, when, free = [], [], 0
    for ts, d, kind, v in sigs:
        if not (period[0] <= ts < period[1]) or not regime_ok(ts, rg): continue
        i = T.searchsorted(ts + (pd.Timedelta("5min") if kind == "atr" else pd.Timedelta(0)))
        if i < free or i >= n: continue
        e = O[i]; st = e - d * v if kind == "atr" else v; R = abs(e - st)
        if R < 5 or (st - e) * d >= 0: continue
        tp = e + d * tgtR * R; px = None
        for j in range(i, min(i + maxmin, n)):
            if (L[j] <= st) if d == 1 else (H[j] >= st): px = st; break
            if (H[j] >= tp) if d == 1 else (L[j] <= tp): px = tp; break
        if px is None: j = min(i + maxmin, n - 1); px = O[j]
        out.append(((px - e) * d - cost) / R); when.append(ts); free = j + 1
    return np.array(out), when
TRAIN = (pd.Timestamp("2020-01-01", tz="UTC"), pd.Timestamp("2024-01-01", tz="UTC")); TEST = (pd.Timestamp("2024-01-01", tz="UTC"), pd.Timestamp("2026-11-01", tz="UTC"))
rows = []
for fam, sigs in FAM.items():
    for rg in ("any", "high", "low"):
        for tgtR in (0.5, 1.0, 2.0):
            for maxmin in (15, 30, 60):
                r, w = sim(sigs, rg, tgtR, maxmin, 1.0, TRAIN)
                if len(r) < 150: continue
                rows.append(dict(entry=fam, vol=rg, target=tgtR, max_hold=maxmin, train_trades=len(r), train_avgR=r.mean(), train_R_yr=r.sum() / 4.0))
df = pd.DataFrame(rows).sort_values("train_R_yr", ascending=False)
print(f"versions searched on 2020-2023: {len(df)}; positive in training: {(df.train_R_yr > 0).sum()}")
top = df.head(5).copy()
for k, row in top.iterrows():
    for cost, lab in ((1.0, "futures 1pt"), (2.1, "CFD 2.1pt")):
        r, w = sim(FAM[row.entry], row.vol, row.target, row.max_hold, cost, TEST)
        top.loc[k, f"TEST R/yr {lab}"] = round(r.sum() / 2.83, 1); top.loc[k, f"TEST avgR {lab}"] = round(r.mean(), 3)
    top.loc[k, "test_trades"] = len(r)
pd.set_option("display.width", 300)
print(top.round(3).to_string(index=False))
