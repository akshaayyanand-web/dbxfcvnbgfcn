# Gold round (1m XAUUSD + EURUSD, 2019-2026). Pre-registered: G3 USD-residual reversion, G5 pre-FOMC, G7 overnight reversal of the US session,
# G10 weekend-gap fade (entry +30 min), G12 NFP 5-minute follow.
import numpy as np, pandas as pd
exec(open("newlab3.py").read().split('\nif __name__ == "__main__":')[0])
G = M1("XAU", "fut1m/XAUUSD_1m.csv", 0.00012); E = M1("EUR", "fx1m/EURUSD_1m.csv", 0.00008)
def at_close(m, ts):
    k = m.t.searchsorted(ts) - 1
    return m.c[k] if k >= 0 and ts - m.t[k] <= pd.Timedelta("10min") else np.nan
def g3():
    days = pd.date_range("2019-03-01", "2026-10-28", freq="B", tz="UTC") + pd.Timedelta(hours=20)
    g = pd.Series([at_close(G, t) for t in days], days); e = pd.Series([at_close(E, t) for t in days], days)
    j = pd.concat([g, e], axis=1, keys=['g', 'e']).dropna(); g, e = j.g, j.e
    rg, re = np.log(g).diff(), np.log(e).diff(); beta = (rg.rolling(120).cov(re) / re.rolling(120).var()).shift(1)
    res = rg - beta * re; z = res / res.rolling(60).std().shift(1); out = []
    for t, v in z.dropna().items():
        if abs(v) > 2:
            tr = trade(G, t, t + pd.Timedelta(hours=24), -int(np.sign(v)))
            if tr: out.append(tr)
    return out
def g5():
    dates = [pd.Timestamp(x.strip()).date() for x in open("news/fomc_dates.txt") if x.strip()]; out = []
    for fd in dates:
        t1 = pd.Timestamp(f"{fd} 14:00", tz="America/New_York"); t0 = t1 - pd.Timedelta(days=1)
        while t0.weekday() >= 5: t0 -= pd.Timedelta(days=1)
        tr = trade(G, t0.tz_convert("UTC"), t1.tz_convert("UTC"), +1)
        if tr: out.append(tr)
    return out
def g7():
    days = pd.date_range("2019-03-01", "2026-10-28", freq="B", tz="UTC"); mv = {}
    for dte in days:
        if dte.weekday() > 3: continue
        a, b = at_close(G, dte + pd.Timedelta(hours=13, minutes=30)), at_close(G, dte + pd.Timedelta(hours=20))
        if np.isfinite(a) and np.isfinite(b): mv[dte] = np.log(b / a)
    s = pd.Series(mv); z = s / s.rolling(60).std().shift(1); out = []
    for dte, v in z.dropna().items():
        if abs(v) > 1.5:
            tr = trade(G, dte + pd.Timedelta(hours=23, minutes=30), dte + pd.Timedelta(hours=30), -int(np.sign(v)))
            if tr: out.append(tr)
    return out
def g10():
    gaps = np.flatnonzero(pd.Series(G.t).diff().dt.total_seconds().to_numpy()[1:] > 30 * 3600) + 1
    dd = pd.DataFrame({"h": G.h, "l": G.l}, index=G.t).resample("1D").agg({"h": "max", "l": "min"}).dropna(); atr = (dd.h - dd.l).rolling(14).mean().shift(1)
    out = []
    for g in gaps:
        fc, so, t0 = G.c[g - 1], G.o[g], G.t[g]; a = atr.asof(t0.normalize())
        if not np.isfinite(a) or abs(so - fc) < 0.3 * a: continue
        dr = -int(np.sign(so - fc)); i = G.at(t0 + pd.Timedelta(minutes=30))
        if i is None: continue
        e = G.o[i]
        if (fc - e) * dr <= 0: continue
        st = e - dr * abs(so - fc); tout = pd.Timestamp(f"{(t0 + pd.Timedelta(days=1)).date()} 08:00", tz="Europe/London").tz_convert("UTC"); j = G.at(tout, "30min")
        if j is None or j <= i: continue
        x = None
        for q in range(i, j):
            if (dr > 0 and G.l[q] <= st) or (dr < 0 and G.h[q] >= st): x = st; break
            if (dr > 0 and G.h[q] >= fc) or (dr < 0 and G.l[q] <= fc): x = fc; break
        x = G.o[j] if x is None else x; risk = abs(e - st)
        out.append((G.t[i], G.t[min(q, j)], dr * (x - e) / risk - G.cost * e / risk))
    return out
def g12():
    out = []
    for y in range(2019, 2027):
        for mth in range(1, 13):
            fri = pd.Timestamp(y, mth, 1) + pd.offsets.Week(weekday=4)
            if fri.month != mth: fri = pd.Timestamp(y, mth, 1)
            t0 = pd.Timestamp(f"{fri.date()} 08:30", tz="America/New_York").tz_convert("UTC"); i0 = G.at(t0, "2min")
            if i0 is None or i0 + 66 >= len(G.t): continue
            hi, lo = G.h[i0:i0 + 5].max(), G.l[i0:i0 + 5].min(); mv = G.c[i0 + 4] - G.o[i0]
            if mv == 0: continue
            dr = int(np.sign(mv)); e = G.o[i0 + 6]; sl = lo if dr > 0 else hi
            if (e - sl) * dr <= 0: continue
            x = None
            for q in range(i0 + 6, i0 + 66):
                if (dr > 0 and G.l[q] <= sl) or (dr < 0 and G.h[q] >= sl): x = sl; break
            x = G.c[i0 + 65] if x is None else x
            out.append((G.t[i0 + 6], G.t[q], dr * (x - e) / abs(e - sl) - G.cost * e / abs(e - sl)))
    return out
if __name__ == "__main__":
    S = pd.Timestamp("2023-01-01", tz="UTC"); rows = []
    for nm, fn in (("G3 gold vs USD residual reversion (24h)", g3), ("G5 pre-FOMC gold drift", g5), ("G7 overnight reversal of big US-session move", g7),
                   ("G10 gold weekend-gap fade (+30 min)", g10), ("G12 NFP 5-min follow on gold", g12)):
        rows.append(dict(test=nm, **stats(fn(), S))); print(rows[-1], flush=True)
    pd.set_option("display.width", 250); R = pd.DataFrame(rows); print(R.to_string()); R.to_csv("goldlab_results.csv", index=False)
