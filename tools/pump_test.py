# Pump lab: after a 5/15-minute move in the top 1-3% of the last 20 days, ride or fade it (stop 0.5/1x the pump, target 1-2R or 30/60-min exit). NQ, SPX, gold (1m), BTC (5m), 2020-2026. Run: python pump_test.py NQ
import sys, glob, numpy as np, pandas as pd
sys.path.insert(0, "/home/user/dbxfcvnbgfcn/tools")
from portfolio_prop import load_csv
SYM = sys.argv[1]
CFG = {"NQ": ("fut1m/USATECHIDXUSD_1m.csv", "America/New_York", 575, 930, 1.0), "SPX": ("fut1m/USA500IDXUSD_1m.csv", "America/New_York", 575, 930, 0.5),
       "GOLD": ("fut1m/XAUUSD_1m.csv", "Europe/London", 480, 1020, 0.3), "BTC": (None, "UTC", 0, 1440, None)}
path, TZ, A0, A1, SPREAD = CFG[SYM]
if path: m = load_csv(path).loc["2020-01-01":]; step = 1
else:
    p = []
    for f in sorted(glob.glob("k5full/BTCUSDT-5m-*.csv")):
        d = pd.read_csv(f, header=None, usecols=[0, 1, 2, 3, 4], names=["t", "o", "h", "l", "c"]); d["t"] = np.where(d.t > 1e14, d.t // 1000, d.t); p.append(d)
    m = pd.concat(p); m.index = pd.to_datetime(m.t, unit="ms", utc=True); m = m[~m.index.duplicated()].sort_index().drop(columns="t").loc["2020-01-01":]; step = 5
O, H, L, C, T = (m[k].to_numpy() for k in "ohlc"), None, None, None, m.index
O, H, L, C = m.o.to_numpy(), m.h.to_numpy(), m.l.to_numpy(), m.c.to_numpy()
z = T.tz_convert(TZ); mins = (z.hour * 60 + z.minute).to_numpy(); wd = z.weekday.to_numpy(); n = len(C)
rows = []
for K in (5, 15):
    kb = max(1, K // step)
    mv = C - np.roll(C, kb); mv[:kb] = 0
    hi_k = pd.Series(H).rolling(kb).max().to_numpy(); lo_k = pd.Series(L).rolling(kb).min().to_numpy()
    look = int(20 * 1440 / step)                       # threshold from the previous ~20 days of moves (no look-ahead)
    absmv = pd.Series(np.abs(mv))
    for q in (0.97, 0.99):
        thr = absmv.rolling(look, min_periods=look // 4).quantile(q).shift(1).to_numpy()
        ok = (mins >= A0) & (mins < A1) & ((wd < 5) if SYM != "BTC" else True) & np.isfinite(thr) & (np.abs(mv) > thr)
        sig_idx = np.where(ok)[0]
        for mode in ("ride", "fade"):
            for sfrac in (0.5, 1.0):
                for tgt in (1.0, 2.0, "t30", "t60"):
                    out, when, i_free = [], [], 0
                    for i in sig_idx:
                        if i < i_free or i + 2 >= n: continue
                        d = (1 if mv[i] > 0 else -1) * (1 if mode == "ride" else -1)
                        size = hi_k[i] - lo_k[i]
                        if not size > 0: continue
                        j0 = i + 1; e = O[j0]; R = sfrac * size; st = e - d * R
                        sp = SPREAD if SPREAD is not None else 0.0006 * e
                        tp = e + d * tgt * R if not isinstance(tgt, str) else None
                        hold = int(tgt[1:]) // step if isinstance(tgt, str) else int(240 / step)
                        px = None
                        for j in range(j0, min(j0 + hold, n)):
                            if (L[j] <= st) if d == 1 else (H[j] >= st): px = st; break
                            if tp is not None and ((H[j] >= tp) if d == 1 else (L[j] <= tp)): px = tp; break
                        if px is None: j = min(j0 + hold, n - 1); px = O[j]
                        out.append(((px - e) * d - sp) / R); when.append(T[j0]); i_free = j + 1
                    if len(out) < 60: continue
                    r = np.array(out); w = pd.DatetimeIndex(when); a = w < pd.Timestamp("2023-01-01", tz="UTC")
                    ya = max((w[a][-1] - w[a][0]).days / 365.25, 0.1) if a.any() else 1; yb = max((w[~a][-1] - w[~a][0]).days / 365.25, 0.1)
                    rows.append(dict(sym=SYM, pump=f"{K}m top{int(round((1-q)*100))}%", mode=mode, stop=f"{sfrac}x pump", exit=str(tgt),
                                     trades_mo=round(len(r) / ((w[-1] - w[0]).days / 30.4), 1), win=round(100 * (r > 0).mean(), 1), avgR=round(r.mean(), 3),
                                     R_yr_2020_22=round(r[a].sum() / ya, 1), R_yr_2023_26=round(r[~a].sum() / yb, 1)))
df = pd.DataFrame(rows); df["minhalf"] = df[["R_yr_2020_22", "R_yr_2023_26"]].min(axis=1)
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 100)
print(f"{SYM}: {len(df)} versions; positive both halves: {(df.minhalf > 0).sum()}; >= +10 R/yr both: {(df.minhalf >= 10).sum()}")
print(df.groupby("mode")[["R_yr_2020_22", "R_yr_2023_26"]].median().round(1).to_string())
print(df.sort_values("minhalf", ascending=False).head(6).drop(columns="minhalf").to_string(index=False))
df.to_pickle(f"pump_{SYM}.pkl")
