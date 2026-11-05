# Run from the scratchpad.
# Crypto timing edges on BTC / ETH hourly (2020-2026): CME weekend gap fill, weekend fade/follow, session drift.
import numpy as np, pandas as pd
COST = 0.0012
def load(sym):
    d = pd.read_csv(f"kh/{sym}USDT.csv", header=None, usecols=[0, 1, 2, 3, 4], names=["t", "o", "h", "l", "c"])
    d.t = np.where(d.t > 1e14, d.t // 1000, d.t); d.index = pd.to_datetime(d.t, unit="ms", utc=True); d = d[~d.index.duplicated()]; return d.drop(columns="t").sort_index()
def atr(d, n=14):
    c = d.c; tr = pd.concat([d.h - d.l, (d.h - c.shift()).abs(), (d.l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()
def trade(d, et, xt, dr, st, tg=None):
    """Enter at the open of the bar at et, exit at the stop, the target or the open of the bar at xt."""
    seg = d.loc[et:xt]
    if len(seg) < 2: return None
    e = seg.o.iloc[0]
    if (st - e) * dr >= 0: return None
    for t, r in seg.iloc[:-1].iterrows():
        if (r.l <= st) if dr == 1 else (r.h >= st): return (et, t, e, st, (min(r.o, st) if dr == 1 else max(r.o, st)))
        if tg is not None and ((r.h >= tg) if dr == 1 else (r.l <= tg)): return (et, t, e, st, (max(r.o, tg) if dr == 1 else min(r.o, tg)))
    return (et, seg.index[-1], e, st, seg.o.iloc[-1])
def stats(tr, name):
    tr = [x for x in tr if x]; r = np.array([(px - e) / abs(e - st) * np.sign(e - st) - COST * e / abs(e - st) for et, xt, e, st, px in tr])
    t = pd.DatetimeIndex([x[0] for x in tr]); A = t < pd.Timestamp("2023-01-01", tz="UTC")
    ya = (t[A][-1] - t[A][0]).days / 365.25; yb = (t[~A][-1] - t[~A][0]).days / 365.25
    r2 = r - np.array([COST * e / abs(e - st) for et, xt, e, st, px in tr])
    return dict(edge=name, n=len(r), win=100 * (r > 0).mean(), avgR=r.mean(), yrA=r[A].sum() / ya, yrB=r[~A].sum() / yb, yrB_cost2=r2[~A].sum() / yb)
rows = []
for sym in ("BTC", "ETH"):
    d = load(sym); a = atr(d)
    ct = d.index.tz_convert("America/Chicago")
    # CME close Fri 16:00 CT, reopen Sun 17:00 CT
    fri = d.index[(ct.weekday == 4) & (ct.hour == 16)]; sun = d.index[(ct.weekday == 6) & (ct.hour == 17)]
    pairs = [(f, s) for f in fri for s in sun[(sun > f) & (sun < f + pd.Timedelta("3D"))][:1]]
    for thr in (0.01, 0.02, 0.03):
        for mode in ("fill", "follow"):
            for sk in (1.5, 3.0):
                for hold in ("48h", "96h"):
                    tr = []
                    for f, s in pairs:
                        pf = d.c.asof(f - pd.Timedelta("1min")); ps = d.o.get(s, np.nan)
                        if not np.isfinite(ps) or not np.isfinite(pf): continue
                        g = ps / pf - 1
                        if abs(g) < thr: continue
                        dr = (-1 if g > 0 else 1) * (1 if mode == "fill" else -1)
                        st = ps - dr * sk * a.asof(s)
                        tr.append(trade(d, s, s + pd.Timedelta(hold), dr, st, pf if mode == "fill" else None))
                    if len([x for x in tr if x]) >= 20: rows.append(stats(tr, f"{sym} CME-gap {mode} gap>{thr:.0%} stop{sk}ATR hold{hold}"))
    # US-hours vs Asia-hours drift, long only above the 200-day trend
    dc = d.c.resample("1D").last(); tr200 = (dc > dc.rolling(200).mean()).shift(1)
    ny = d.index.tz_convert("America/New_York")
    for lab, h0, h1 in (("US 09:30-16 NY", 9, 16), ("Asia 20-03 NY", 20, 3), ("Europe 03-09 NY", 3, 9)):
        for filt in (False, True):
            for dr in (1, -1):
                tr = []
                days = pd.date_range(d.index[0].normalize(), d.index[-1].normalize(), freq="1D")
                for day in days[1:-1]:
                    nyd = day.tz_convert("America/New_York").normalize()
                    et = (nyd + pd.Timedelta(hours=h0)).tz_convert("UTC").floor("h")
                    xt = (nyd + pd.Timedelta(hours=h1 + (24 if h1 < h0 else 0))).tz_convert("UTC").floor("h")
                    if et not in d.index: continue
                    if filt:
                        k = tr200.asof(et)
                        if not (k == True if dr == 1 else k == False): continue
                    st = d.o[et] - dr * 1.0 * a.asof(et) * 3
                    tr.append(trade(d, et, xt, dr, st))
                if len([x for x in tr if x]) >= 50: rows.append(stats(tr, f"{sym} {lab} {'long' if dr == 1 else 'short'} trendfilter{filt}"))
df = pd.DataFrame(rows); df["minhalf"] = df[["yrA", "yrB"]].min(axis=1)
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 300)
print(f"{len(df)} versions; >=10%/yr both halves: {(df.minhalf >= 10).sum()}; positive both: {(df.minhalf > 0).sum()}")
print(df.sort_values("minhalf", ascending=False).round(2).head(30).to_string(index=False))
df.to_pickle("crypto_time_lab.pkl")
