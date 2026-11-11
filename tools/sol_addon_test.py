# SOL dip added to the 12 EAs in Pass Mode under FTMO's exact rule, hourly mark-to-market, 2020-2026.
import os, numpy as np, pandas as pd
src = open('/home/user/dbxfcvnbgfcn/tools/ftmo_balance_rule_test.py').read().split("def ev(args)")[0]
exec(src.replace('print(f"check', 'pass  # print(f"check'))
import glob
p = []
for f in sorted(glob.glob("k5full/SOLUSDT-5m-*.csv")):
    d = pd.read_csv(f, header=None, usecols=[0, 2, 3, 4], names=["t", "h", "l", "c"]); d["t"] = np.where(d.t > 1e14, d.t // 1000, d.t); p.append(d)
s5 = pd.concat(p); s5.index = pd.to_datetime(s5.t, unit="ms", utc=True); s5 = s5[~s5.index.duplicated()].sort_index()
h1 = s5.resample("1h").agg(dict(h="max", l="min", c="last")).dropna()
TRS = pd.read_pickle("world_SOLUSDT.pkl")[1]; COST = 0.0015
def series(nm):
    R = np.zeros(len(idx)); L = np.zeros(len(idx)); real = np.zeros(len(idx)); n = 0
    for et, xt, e, st, px in TRS[nm]:
        if et < idx[0] or xt > idx[-1]: continue
        risk = e - st; seg = h1.loc[et:xt]; prev = e; n += 1
        for t, row in seg.iloc[:-1].iterrows():
            k = idx.searchsorted(t.floor("h"))
            if k >= len(idx): break
            L[k] += (row.l - prev) / risk; R[k] += (row.c - prev) / risk; prev = row.c
        k = min(idx.searchsorted(pd.Timestamp(xt).floor("h")), len(idx) - 1)
        R[k] += (px - prev) / risk - COST * e / risk; L[k] += min(0, (px - prev) / risk - COST * e / risk)
        real[k] += (px - e) / risk - COST * e / risk
    return R, L, real, n
BASE_R, BASE_L, BASE_FLT = np.array(EQ_R, float).copy(), np.array(EQ_L, float).copy(), np.array(FLT, float).copy()
SER = {nm: series(nm) for nm in ("SOL 1h dip RSI2<15 EMA200 hold144", "SOL 2h dip RSI2<25 EMA50 hold144")}
for nm, (R, L, rl, n) in SER.items(): print(nm, "trades", n, "total R", round(R.sum(), 1), "check booked", round(rl.sum(), 1), flush=True)
def ev(cfg):
    global CFG, EQ_R, EQ_L, FLT
    nm, w = cfg; CFG = (0.09, 0.905, (0.04, 0.02)); out = dict(sol=nm[4:30] if w else "none", risk=w)
    if w:
        R, L, rl, n = SER[nm]; EQ_R = BASE_R + w / 100 * R; EQ_L = BASE_L + w / 100 * L; FLT = BASE_FLT + w / 100 * (np.cumsum(R) - np.cumsum(rl))
    else: EQ_R, EQ_L, FLT = BASE_R, BASE_L, BASE_FLT
    yrs = (idx[-1] - idx[0]).days / 365.25; out["profit %/yr (x1)"] = 100 * EQ_R.sum() / yrs
    for lab, a, z in (("A", "2020-09-01", "2022-12-31"), ("B", "2023-01-01", "2025-09-01"), ("C", "2026-01-01", "2026-08-15")):
        res = []
        for s in pd.date_range(a, z, freq="1D", tz="UTC"):
            if s.weekday() >= 5: continue
            h0 = idx.searchsorted(s); p1, i1 = attempt(h0, 0.10, 1.5, "balance", True, 0.04, brake="equity")
            if p1 != "pass": res.append((p1, None)); continue
            p2, i2 = attempt(i1 + 1, 0.05, 1.5, "balance", True, 0.04, brake="equity"); res.append((p2, (i2 - h0) / 24 if p2 == "pass" else None))
        n = len([x for x in res if x[0] != "open"]); t = [x[1] for x in res if x[1] is not None]
        out[f"{lab}pass"] = 100 * sum(x[0] == "pass" for x in res) / n; out[f"{lab}breach"] = 100 * sum(x[0] == "breach" for x in res) / n; out[f"{lab}days"] = np.median(t)
    return out
cfgs = [("x", 0.0)] + [(nm, w) for nm in SER for w in (0.1, 0.2, 0.3)] + [("SOL 1h dip RSI2<15 EMA200 hold144", w) for w in (0.4, 0.5, 0.6)]
with Pool(os.cpu_count()) as p: rows = p.map(ev, cfgs)
pd.set_option("display.width", 300); print(pd.DataFrame(rows).round(1).to_string(index=False))
