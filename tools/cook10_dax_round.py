# DAX round (1m 2021-2026). Pre-registered: X1 NQ US-open spillover, X2 Xetra-open gap fade, X5 morning->last-hour momentum, X8 14:30 US-data follow.
import numpy as np, pandas as pd
exec(open("newlab3.py").read().split('\nif __name__ == "__main__":')[0])
D = M1("DAX", "eu1m/DEUIDXEUR_1m.csv", 0.00015); NQ = M1("NQ", "fut1m/USATECHIDXUSD_1m.csv", 0.00015)
TZ = "Europe/Berlin"; S = pd.Timestamp("2024-01-01", tz="UTC")
def ts(dte, hm): return pd.Timestamp(f"{dte} {hm}", tz=TZ).tz_convert("UTC")
def px_open(m, t):
    k = m.at(t, "3min"); return (k, m.o[k]) if k is not None else (None, np.nan)
def days(): return [d for d in pd.bdate_range("2021-01-05", "2026-11-03")]
def x1():
    mv = {}
    for d in days():
        a, pa = px_open(NQ, ts(d.date(), "15:30")); b, pb = px_open(NQ, ts(d.date(), "16:00"))
        if a is not None and b is not None: mv[d] = np.log(pb / pa)
    s = pd.Series(mv); z = s / s.rolling(60).std().shift(1); out = []
    for d, v in z.dropna().items():
        if abs(v) > 1.5:
            tr = trade(D, ts(d.date(), "16:00"), ts(d.date(), "17:25"), int(np.sign(v)))
            if tr: out.append(tr)
    return out
def x2():
    out = []; prev = None
    for d in days():
        k9, o9 = px_open(D, ts(d.date(), "09:00")); kc = D.at(ts(d.date(), "17:29"), "3min")
        if prev is not None and k9 is not None:
            g = o9 / prev - 1; i = D.at(ts(d.date(), "09:05"), "3min"); j = D.at(ts(d.date(), "12:00"), "3min")
            if abs(g) > 0.004 and i is not None and j is not None:
                dr = -int(np.sign(g)); e = D.o[i]; tgt = prev; st = e - dr * abs(g) * prev
                if (tgt - e) * dr > 0:
                    x = None
                    for q in range(i, j):
                        if (dr > 0 and D.l[q] <= st) or (dr < 0 and D.h[q] >= st): x = st; break
                        if (dr > 0 and D.h[q] >= tgt) or (dr < 0 and D.l[q] <= tgt): x = tgt; break
                    x = D.o[j] if x is None else x; risk = abs(e - st)
                    out.append((D.t[i], D.t[min(q, j)], dr * (x - e) / risk - D.cost * e / risk))
        prev = D.c[kc] if kc is not None else None
    return out
def x5():
    out = []
    for d in days():
        a, pa = px_open(D, ts(d.date(), "09:00")); b, pb = px_open(D, ts(d.date(), "10:00"))
        if a is None or b is None or pb == pa: continue
        tr = trade(D, ts(d.date(), "16:30"), ts(d.date(), "17:25"), int(np.sign(pb - pa)))
        if tr: out.append(tr)
    return out
def x8():
    mv = {}
    for d in days():
        a, pa = px_open(D, ts(d.date(), "14:30")); b, pb = px_open(D, ts(d.date(), "14:35"))
        if a is not None and b is not None: mv[d] = np.log(pb / pa)
    s = pd.Series(mv); z = s / s.rolling(60).std().shift(1); out = []
    for d, v in z.dropna().items():
        if abs(v) > 2:
            tr = trade(D, ts(d.date(), "14:36"), ts(d.date(), "15:25"), int(np.sign(v)))
            if tr: out.append(tr)
    return out
if __name__ == "__main__":
    rows = []
    for nm, fn in (("X1 NQ US-open spillover -> DAX 16:00-17:25", x1), ("X2 Xetra-open gap fade >0.4%", x2), ("X5 09-10 momentum -> 16:30-17:25", x5), ("X8 14:30 US-data follow (|z|>2) -> 15:25", x8)):
        trs = fn(); rows.append(dict(test=nm, **stats(trs, S)))
        r = pd.Series([x[2] for x in trs], index=pd.DatetimeIndex([x[0] for x in trs])).sort_index() if trs else pd.Series(dtype=float)
        rows[-1]["R_by_year"] = r.groupby(r.index.year).sum().round(1).to_dict() if len(r) else {}; print(rows[-1], flush=True)
    pd.set_option("display.width", 300); R = pd.DataFrame(rows); print(R.drop(columns="R_by_year").to_string()); R.to_csv("daxlab2_results.csv", index=False)
    for r in rows: print(r["test"], r["R_by_year"])
