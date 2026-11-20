# S&P round (1m 2019-2026). Pre-registered: P3 opening-drive follow, P5 FOMC 14:00-14:15 follow, P8 afternoon fade of >1% days, P9 overnight Asia-move fade.
import numpy as np, pandas as pd
exec(open("newlab3.py").read().split('\nif __name__ == "__main__":')[0])
X = M1("SPX", "fut1m/USA500IDXUSD_1m.csv", 0.00015); TZ = "America/New_York"; S = pd.Timestamp("2023-01-01", tz="UTC")
def ts(dte, hm): return pd.Timestamp(f"{dte} {hm}", tz=TZ).tz_convert("UTC")
def po(t):
    k = X.at(t, "3min"); return X.o[k] if k is not None else np.nan
DAYS = pd.bdate_range("2019-01-03", "2026-10-29")
def zmove(a_hm, b_hm, shift_prev=False):
    mv = {}
    for d in DAYS:
        a_d = (d - pd.offsets.BDay(1)).date() if shift_prev else d.date()
        pa, pb = po(ts(a_d, a_hm)), po(ts(d.date(), b_hm))
        if np.isfinite(pa) and np.isfinite(pb): mv[d] = np.log(pb / pa)
    s = pd.Series(mv); return s, s / s.rolling(60).std().shift(1)
def p3():
    _, z = zmove("09:30", "09:35"); out = []
    for d, v in z.dropna().items():
        if abs(v) > 2:
            tr = trade(X, ts(d.date(), "09:36"), ts(d.date(), "10:30"), int(np.sign(v)))
            if tr: out.append(tr)
    return out
def p5():
    out = []
    for fd in [pd.Timestamp(x.strip()).date() for x in open("news/fomc_dates.txt") if x.strip()]:
        pa, pb = po(ts(fd, "14:00")), po(ts(fd, "14:15"))
        if np.isfinite(pa) and np.isfinite(pb) and pb != pa:
            tr = trade(X, ts(fd, "14:16"), ts(fd, "15:55"), int(np.sign(pb - pa)))
            if tr: out.append(tr)
    return out
def p8():
    out = []
    for d in DAYS:
        pa, pb = po(ts(d.date(), "09:30")), po(ts(d.date(), "14:00"))
        if np.isfinite(pa) and np.isfinite(pb) and abs(pb / pa - 1) > 0.01:
            tr = trade(X, ts(d.date(), "14:00"), ts(d.date(), "15:55"), -int(np.sign(pb - pa)))
            if tr: out.append(tr)
    return out
def p9():
    s, z = zmove("18:00", "03:00", shift_prev=True); out = []
    for d, v in z.dropna().items():
        if abs(v) > 1.5:
            tr = trade(X, ts(d.date(), "03:00"), ts(d.date(), "09:25"), -int(np.sign(v)))
            if tr: out.append(tr)
    return out
if __name__ == "__main__":
    rows = []
    for nm, fn in (("P3 opening-drive follow (5-min z>2) to 10:30", p3), ("P5 FOMC 14:00-14:15 follow to 15:55", p5), ("P8 afternoon fade of >1% days 14:00-15:55", p8),
                   ("P9 overnight Asia-move fade 03:00-09:25 (z>1.5)", p9)):
        trs = fn(); rows.append(dict(test=nm, **stats(trs, S)))
        r = pd.Series([x[2] for x in trs], index=pd.DatetimeIndex([x[0] for x in trs])).sort_index() if trs else pd.Series(dtype=float)
        rows[-1]["R_by_year"] = r.groupby(r.index.year).sum().round(1).to_dict() if len(r) else {}; print(rows[-1], flush=True)
    pd.set_option("display.width", 300); R = pd.DataFrame(rows); print(R.drop(columns="R_by_year").to_string()); R.to_csv("spxlab_results.csv", index=False)
    for r in rows: print(r["test"], r["R_by_year"])
