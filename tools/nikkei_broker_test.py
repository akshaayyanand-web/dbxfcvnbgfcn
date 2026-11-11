# Nikkei breakout on broker JP225 M5 data (Jun 2025 - Nov 2026): server clock check + 8 breakout variants.
import sys, numpy as np, pandas as pd
sys.argv = ["x", "JPNIDXJPY"]
exec(open("world_lab.py").read().split("rows, TR = [], {}")[0])
duk5 = bars("5min").c
br = pd.read_csv("/root/.claude/uploads/0ea82c59-9b45-5b6c-b663-efd40f90c87c/8b9b3a9f-.JP225Cash_M5_202506110745_202611111820.csv", sep="\t")
br.columns = [c.strip("<>").lower() for c in br.columns]
naive = pd.to_datetime(br.date + " " + br.time, format="%Y.%m.%d %H:%M:%S")
# find the server offset: compare with Dukascopy (UTC) over the 2026 overlap, allowing a US-DST-style shift
best = []
for off in range(0, 6):
    idx_ = (naive - pd.Timedelta(hours=off)).dt.tz_localize("UTC")
    s = pd.Series(br.close.values, idx_); j = pd.concat([s, duk5], axis=1, join="inner").dropna()
    if len(j) > 500: best.append((off, len(j), float(np.median(np.abs(j.iloc[:, 0] / j.iloc[:, 1] - 1)) * 1e4)))
print("offset hours, overlap bars, median gap (bp):", best)
ny = naive.dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT")
dst = np.array([bool(x.dst()) if x is not pd.NaT else True for x in ny])
off = np.where(dst, 3, 2)
utc = (naive - pd.to_timedelta(off, unit="h")).dt.tz_localize("UTC")
s = pd.Series(br.close.values, utc); j = pd.concat([s.rename("b"), duk5.rename("d")], axis=1, join="inner").dropna()
w = ~np.array([bool(x.dst()) for x in j.index.tz_convert("America/New_York")])
print("check after DST rule: summer gap bp", float(np.median(np.abs(j.b[~w] / j.d[~w] - 1)) * 1e4), "winter gap bp", float(np.median(np.abs(j.b[w] / j.d[w] - 1)) * 1e4) if w.sum() else None, "winter bars", int(w.sum()))
b = pd.DataFrame({"o": br.open.values, "h": br.high.values, "l": br.low.values, "c": br.close.values}, index=utc).sort_index()
b = b[~b.index.duplicated()]
print("broker bars", len(b), b.index[0], b.index[-1])
T = b.index; C = b.c.to_numpy(); atr = atr_of(b)
rows = []; TRB = {}
for nb in (20, 50):
    hi = b.h.rolling(nb).max().shift(1).to_numpy(); lo = b.l.rolling(nb).min().shift(1).to_numpy()
    for en in (200, 800):
        e_ = b.c.ewm(span=en, adjust=False).mean().to_numpy()
        for sm in (1.0, 2.0):
            def sig(i): return 1 if (C[i] > hi[i] and C[i] > e_[i]) else (-1 if (C[i] < lo[i] and C[i] < e_[i]) else 0)
            def stp(i, d, e, sm=sm): return e - d * sm * atr[i] if np.isfinite(atr[i]) else None
            tr = intraday_sim(b, sig, stp, 0, FLAT, OPEN, WEND, one_per_day=False)
            r = np.array([(px - e) / abs(e - st) * np.sign(e - st) - COST * e / abs(e - st) for et, xt, e, st, px in tr])
            r2 = r - np.array([COST * e / abs(e - st) for et, xt, e, st, px in tr])
            t = pd.DatetimeIndex([x[0] for x in tr]); yrs = (T[-1] - T[0]).days / 365.25
            q = pd.Series(r, t).groupby(t.tz_convert(None).to_period("Q")).sum().round(1)
            nm = f"breakout{nb} EMA{en} stop{sm}ATR"; TRB[nm] = tr
            rows.append(dict(edge=nm, trades=len(r), win=100 * (r > 0).mean(), avgR=r.mean(), R_per_yr=r.sum() / yrs, R_per_yr_2xcost=r2.sum() / yrs,
                             worst_q=q.min(), pos_quarters=f"{(q > 0).sum()}/{len(q)}"))
pd.set_option("display.width", 250)
old = pd.read_pickle("world_JPNIDXJPY.pkl")[0].set_index("edge")
df = pd.DataFrame(rows); df["old 2021-22 R/yr"] = [old.loc["JPN 5min " + e, "yrA"] for e in df.edge]; df["old 2023 R/yr"] = [old.loc["JPN 5min " + e, "yrB"] for e in df.edge]
print(df.round(2).to_string(index=False))
nm = "breakout20 EMA800 stop2.0ATR"; tr = TRB[nm]; r = pd.Series([(px - e) / abs(e - st) * np.sign(e - st) - COST * e / abs(e - st) for et, xt, e, st, px in tr], pd.DatetimeIndex([x[0] for x in tr]))
print(nm, "by quarter (R):", r.groupby(r.index.tz_convert(None).to_period("Q")).sum().round(1).to_dict())
pd.to_pickle(TRB, "jp_broker_trades.pkl")
