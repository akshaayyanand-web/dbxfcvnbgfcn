# New candidates vs the 8-EA portfolio. Standalone (1% risk) by halves, then portfolio add-on at 0.25 / 0.5.
import sys, numpy as np, pandas as pd
SP = sys.argv[1]
exec(open(SP + "/speed8.py").read().split("V2 = [")[0])
from multiprocessing import Pool
R0, LO0 = R.copy(), LO.copy()
import orb_lab as O
CAND = {}
spx = load_csv(SP + "/fut/USA500IDXUSD.csv"); s5 = O.five_min(load_csv(SP + "/fut1m/USA500IDXUSD_1m.csv"))
for mins in (15, 30):
    for tg in (2.0, 1.5, 3.0, None):
        for both in (True, False):
            x = O.orb(s5, "America/New_York", (9, 30), (11, 30), (15, 55), mins, "other", tg, both, 0.0001)
            CAND[f"spx_orb {mins}m tgt{tg} {'both' if both else 'long'}"] = P.trade_series([t[:5] for t in x], 0.0001, spx, idx)
yrs = (idx[-1] - idx[0]).days / 365.25; cut = idx.searchsorted(split); f = cut / len(idx)
d = pd.DataFrame({k: v[0] for k, v in CAND.items()} | {k: R0[names.index(k)] for k in names}, index=idx).resample("1D").sum(); d = d[d.abs().sum(axis=1) > 0]
rows = []
for k, (r, lo) in CAND.items():
    eq = np.cumsum(r); rows.append(dict(cand=k, yr=100 * r.sum() / yrs, yr_2020_22=100 * r[:cut].sum() / (f * yrs), yr_2023_26=100 * r[cut:].sum() / ((1 - f) * yrs),
                                        maxdd=100 * np.max(np.maximum.accumulate(eq) - eq), max_corr=d.corr().loc[k, names].abs().max()))
st = pd.DataFrame(rows); pd.set_option("display.width", 250); print("STANDALONE at 1% risk:"); print(st.round(2).to_string(index=False), flush=True)
good = st[(st.yr_2020_22 > 0) & (st.yr_2023_26 > 0)].cand.tolist()
def run3(w, Rm, LOm, h0, h1, target, halt=0.8, maxl=0.10, daily=0.05):
    r = (Rm[:, h0:h1] * w[:, None]).sum(0); lo = (LOm[:, h0:h1] * w[:, None]).sum(0); eq = 1.0; day = None; hd = None
    for i in range(len(r)):
        dd_ = days[h0 + i]
        if dd_ != day: day = dd_; dopen = eq
        if hd == dd_: continue
        if eq * (1 + lo[i]) <= 1 - maxl or eq * (1 + lo[i]) <= dopen * (1 - daily): return "fail", i, eq - 1
        eq *= 1 + r[i]
        if target and eq >= 1 + target: return "pass", i, eq - 1
        if 1 - eq / dopen >= halt * daily: hd = dd_
        if eq <= 1 - 0.8 * maxl: return "stopped", i, eq - 1
    return "open", len(r), eq - 1
wst = pd.date_range("2020-04-01", "2025-10-01", freq="MS", tz="UTC")
def job(v):
    k, wt = v
    if k is None: Rm, LOm, w = R0, LO0, W
    else: Rm = np.vstack([R0, CAND[k][0]]); LOm = np.vstack([LO0, CAND[k][1]]); w = np.append(W, wt)
    res = []
    for s_ in est:
        h0 = idx.searchsorted(s_); a, i1, _ = run3(w, Rm, LOm, h0, len(idx), 0.10)
        if a != "pass": res.append((s_, a, None)); continue
        b, i2, _ = run3(w, Rm, LOm, h0 + i1 + 1, len(idx), 0.05); res.append((s_, b, (i1 + i2) / 24 if b == "pass" else None))
    yrs_ = [(s_, *run3(w, Rm, LOm, idx.searchsorted(s_), idx.searchsorted(s_ + pd.DateOffset(years=1)), None)) for s_ in wst]
    out = dict(add=k or "8 EAs (current)", weight=wt)
    for p, sel in (("A", lambda s: s < split), ("B", lambda s: s >= split)):
        rr = [x for x in res if sel(x[0])]; t = [x[2] for x in rr if x[2] is not None]; yy = [y for y in yrs_ if sel(y[0])]
        out |= {f"{p}_pass": 100 * np.mean([x[1] == "pass" for x in rr]), f"{p}_breach": 100 * np.mean([x[1] == "fail" for x in rr]), f"{p}_days": np.median(t),
                f"{p}_fund": 100 * np.median([y[3] for y in yy]), f"{p}_fbr": sum(y[1] == "fail" for y in yy)}
    return out
jobs = [(None, 0)] + [(k, wt) for k in good for wt in (0.25, 0.5)]
print(f"\nportfolio tests for {good}", flush=True)
with Pool(3) as p: out = p.map(job, jobs)
print(pd.DataFrame(out).round(1).to_string(index=False))
