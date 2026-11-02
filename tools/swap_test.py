# Swap a weak EA for a stronger reject (same total risk budget). Picked on 2020-22 starts, judged on 2023-25.
import sys, numpy as np, pandas as pd
SP = sys.argv[1]
exec(open(SP + "/speed8.py").read().split("V2 = [")[0])
_l = open(SP + "/losers.py").read(); exec("def run3" + _l.split("def run3", 1)[1].split("wst =")[0])
src3 = open(SP + "/cook3.py").read(); exec("from portfolio_prop import resample, rsi, rma\ndef dip2" + src3.split("def dip2", 1)[1].split("spx = load_csv")[0])
import orb_lab as O
from multiprocessing import Pool
spx = load_csv(SP + "/fut/USA500IDXUSD.csv"); slv = load_csv(SP + "/fut/XAGUSD.csv"); oil = load_csv(SP + "/fut/LIGHTCMDUSD.csv")
s5 = O.five_min(load_csv(SP + "/fut1m/USA500IDXUSD_1m.csv"))
CAND = {"silver dip 1h": P.trade_series(dip2(slv, "1h", 2, 10, 0.12, 1), 0.00025, slv, idx),
        "nasdaq dip 1h": P.trade_series(dip2(nq, "1h", 2, 10, 0.08, 1), 0.00012, nq, idx),
        "s&p dip 2h": P.trade_series(dip2(spx, "2h", 3, 20, 0.08, 1), 0.0001, spx, idx),
        "oil dip 2h": P.trade_series(dip2(oil, "2h", 3, 20, 0.15, 1), 0.0003, oil, idx),
        "s&p ORB 30m 3R long": P.trade_series([t[:5] for t in O.orb(s5, "America/New_York", (9, 30), (11, 30), (15, 55), 30, "other", 3.0, False, 0.0001)], 0.0001, spx, idx)}
print("candidates built", flush=True)
wst = pd.date_range("2020-04-01", "2025-10-01", freq="MS", tz="UTC")
def evaluate(v):
    lab, out_k, cand, wt = v
    Rm, LOm, w = R.copy(), LO.copy(), W.copy()
    if out_k: w[names.index(out_k)] = 0.0
    if cand: Rm = np.vstack([Rm, CAND[cand][0]]); LOm = np.vstack([LOm, CAND[cand][1]]); w = np.append(w, wt)
    res = []
    for s_ in est:
        h0 = idx.searchsorted(s_); a, i1, _ = run3(w, Rm, LOm, h0, len(idx), 0.10)
        if a != "pass": res.append((s_, a, None)); continue
        b, i2, _ = run3(w, Rm, LOm, h0 + i1 + 1, len(idx), 0.05); res.append((s_, b, (i1 + i2) / 24 if b == "pass" else None))
    yy = [(s_, *run3(w, Rm, LOm, idx.searchsorted(s_), idx.searchsorted(s_ + pd.DateOffset(years=1)), None)) for s_ in wst]
    o = dict(variant=lab)
    for p, sel in (("A", lambda s: s < split), ("B", lambda s: s >= split)):
        rr = [x for x in res if sel(x[0])]; t = [x[2] for x in rr if x[2] is not None]; y = [q for q in yy if sel(q[0])]
        o |= {f"{p}_pass": 100 * np.mean([x[1] == "pass" for x in rr]), f"{p}_breach": 100 * np.mean([x[1] == "fail" for x in rr]), f"{p}_days": np.median(t),
              f"{p}_fund": 100 * np.median([q[3] for q in y]), f"{p}_fbr": sum(q[1] == "fail" for q in y)}
    return o
jobs = [("8 EAs as now", None, None, 0)]
for out_k in ("nqdip", "nqmom", "gmom", "gasia", "spxdip"):
    jobs.append((f"drop {out_k}", out_k, None, 0))
    for c in CAND:
        for wt in (0.25, 0.5):
            jobs.append((f"{out_k} -> {c} {wt}", out_k, c, wt))
with Pool(3) as p: out = p.map(evaluate, jobs)
df = pd.DataFrame(out); pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
base = df.iloc[0]
print(df.round(1).to_string(index=False))
ok = df[(df.A_breach == 0) & (df.A_fbr == 0)]
ok = ok[(ok.A_pass >= base.A_pass - 2)].sort_values(["A_days"])
print("\nPicked on 2020-22 only (no breaches, pass rate within 2 pts, fastest) -> how they did on 2023-25:")
print(ok.head(6).round(1).to_string(index=False))
