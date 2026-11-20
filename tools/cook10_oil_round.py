# Oil round (Dukascopy hourly WTI 2016-2026 + EIA weekly stocks). Pre-registered: O1 EIA-hour follow, O2 crude surprise fade (bearish build),
# O2b total-petroleum surprise, O9 API-hour follow into Wednesday. Costs 0.03% round trip.
import numpy as np, pandas as pd
exec(open("newlab.py").read().split('\nif __name__ == "__main__":')[0])
M = Mkt("WTI", load_duka("LIGHTCMDUSD"), 0.0003); NY_ = M.ny; HR = NY_.hour; DT = np.array(NY_.date)
def bar(dte, hr):
    k = np.flatnonzero((DT == dte) & (HR == hr)); return k[0] if len(k) else None
def eia(code):
    d = pd.read_csv(f"rdata/eia/{code}.csv"); d.index = pd.to_datetime(d.date); return d[code].astype(float)
def surprise(stock):
    ch = stock.diff(); wk = ch.index.isocalendar().week.astype(int)
    norm = pd.Series(np.nan, ch.index)
    for i, t in enumerate(ch.index):
        past = ch[(ch.index < t - pd.Timedelta(days=300)) & (ch.index >= t - pd.Timedelta(days=5 * 365 + 30)) & (abs(wk - wk.iloc[i]) <= 1)]
        if len(past) >= 8: norm.iloc[i] = past.mean()
    s = ch - norm; return s / s.rolling(52, min_periods=26).std().shift(1)
def release_wed(week_end):
    w = (week_end + pd.Timedelta(days=5)).date(); return w
def o1():
    out = []
    for dte in sorted(set(DT)):
        if pd.Timestamp(dte).weekday() != 2: continue
        a, b, c = bar(dte, 10), bar(dte, 11), bar(dte, 14)
        if None in (a, b, c): continue
        mv = M.c[a] - M.o[a]
        if mv == 0: continue
        tr = trade(M, b, c, int(np.sign(mv)))
        if tr: out.append(tr[:3])
    return out
def o2(z):
    out = []
    for we, v in z.dropna().items():
        if abs(v) <= 1 or we < pd.Timestamp("2016-01-01"): continue
        w = release_wed(we); i = bar(w, 11); j = bar((pd.Timestamp(w) + pd.Timedelta(days=1)).date(), 14)
        if i is None or j is None: continue
        tr = trade(M, i, j, -int(np.sign(v)))
        if tr: out.append(tr[:3])
    return out
def o9():
    out = []
    for dte in sorted(set(DT)):
        if pd.Timestamp(dte).weekday() != 1: continue
        a = bar(dte, 16); b = bar(dte, 18); c = bar((pd.Timestamp(dte) + pd.Timedelta(days=1)).date(), 10)
        if None in (a, b, c): continue
        mv = M.c[a] - M.o[a]
        if mv == 0: continue
        tr = trade(M, b, c, int(np.sign(mv)))
        if tr: out.append(tr[:3])
    return out
if __name__ == "__main__":
    crude = eia("WCESTUS1"); total = crude + eia("WGTSTUS1").reindex(crude.index) + eia("WDISTUS1").reindex(crude.index)
    S = pd.Timestamp("2022-01-01", tz="UTC"); rows = []
    for nm, fn in (("O1 EIA-hour follow 11:00->14:00 ET", o1), ("O2 crude inventory surprise fade (|z|>1), Wed 11:00 -> Thu 14:00", lambda: o2(surprise(crude))),
                   ("O2b total petroleum surprise fade (|z|>1)", lambda: o2(surprise(total))), ("O9 API-hour follow Tue 18:00 -> Wed 10:00 ET", o9)):
        rows.append(dict(test=nm, **stats(fn(), S))); print(rows[-1], flush=True)
    pd.set_option("display.width", 250); R = pd.DataFrame(rows); print(R.to_string()); R.to_csv("oillab_results.csv", index=False)
