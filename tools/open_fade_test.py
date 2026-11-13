# Opening fade as real one-at-a-time trades: S&P and NQ, per year, double spread, with / without a stop.
import sys, numpy as np, pandas as pd
sys.path.insert(0, "/home/user/dbxfcvnbgfcn/tools")
from portfolio_prop import load_csv
def run(path, spread, look, q, hold, trend_filter, stop_mult, first_only):
    m1 = load_csv(path).loc["2020-01-01":]
    O, H, L, C = m1.o.to_numpy(), m1.h.to_numpy(), m1.l.to_numpy(), m1.c.to_numpy(); T = m1.index
    ny = T.tz_convert("America/New_York"); mins = (ny.hour * 60 + ny.minute).to_numpy(); wd = ny.weekday.to_numpy(); yr = ny.year.to_numpy()
    dk = (ny.year * 10000 + ny.month * 100 + ny.day).to_numpy()
    cs = pd.Series(C); ret = (cs - cs.shift(look)).to_numpy()
    tr = np.sign(cs.ewm(span=800, adjust=False).mean().diff(30).to_numpy())
    base = (wd < 5) & (mins >= 570) & (mins < 600)
    th = np.quantile(np.abs(ret[(yr <= 2022) & base & np.isfinite(ret)]), q)       # threshold from 2020-22 only
    out = []; free = 0; last_day = None
    for i in np.where(base & np.isfinite(ret) & (np.abs(ret) >= th))[0]:
        if i < free or i + 1 + hold >= len(O): continue
        if first_only and dk[i] == last_day: continue
        s = np.sign(ret[i])
        if trend_filter and tr[i] != s: continue
        d = -s; e = O[i + 1] + d * spread / 2; size = abs(ret[i]); st = e - d * stop_mult * size if stop_mult else None; px = None
        for j in range(i + 1, i + 1 + hold):
            if st is not None and ((L[j] <= st) if d == 1 else (H[j] >= st)): px = st; break
        if px is None: j = i + 1 + hold; px = O[j]
        out.append((T[i], yr[i], (px - e) * d - spread / 2)); free = j + 1; last_day = dk[i]
    return pd.DataFrame(out, columns=["t", "yr", "pts"])
rows = []
for name, path, sp in (("S&P", "fut1m/USA500IDXUSD_1m.csv", 0.6), ("NQ", "fut1m/USATECHIDXUSD_1m.csv", 2.1)):
    for look, q, hold, tf in ((15, 0.98, 30, True), (10, 0.98, 30, True), (30, 0.95, 30, False), (15, 0.98, 15, True)):
        for stop in (None, 1.0):
            for mult in (1, 2):
                r = run(path, sp * mult, look, q, hold, tf, stop, True)
                if len(r) < 30: continue
                by = r.groupby("yr").pts.mean().round(2)
                rows.append(dict(market=name, signal=f"{look}m move top {round((1-q)*100)}%{' with trend' if tf else ''}", hold=f"{hold}m", stop="1x move" if stop else "none",
                                 spread=sp * mult, trades=len(r), per_year=round(len(r) / 6.8, 1), win=round(100 * (r.pts > 0).mean(), 1), avg_pts=round(r.pts.mean(), 2),
                                 years_positive=f"{(by > 0).sum()}/{len(by)}", by_year=by.to_dict()))
pd.set_option("display.width", 320); pd.set_option("display.max_colwidth", 120); print(pd.DataFrame(rows).to_string(index=False))
