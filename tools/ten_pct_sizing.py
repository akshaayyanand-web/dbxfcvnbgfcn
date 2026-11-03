# Size every EA so it makes >=10%/yr on its own (at its own risk), then check prop compliance of the whole account.
import sys, numpy as np, pandas as pd
SP = sys.argv[1]
exec(open(SP + "/speed8.py").read().split("V2 = [")[0])
_l = open(SP + "/losers.py").read(); exec("def run3" + _l.split("def run3", 1)[1].split("wst =")[0])
from multiprocessing import Pool
yrs = (idx[-1] - idx[0]).days / 365.25
at1 = {k: 100 * R[names.index(k)].sum() / yrs for k in names}          # %/yr at 1% risk
need = {k: 10.0 / at1[k] for k in ("btc", "gdip", "gasia", "gmom", "nqmom", "orb15", "nqdip", "spxdip")}
print("risk needed for 10%/yr each:", {k: round(v, 2) for k, v in need.items()}, flush=True)
cur = dict(btc=1.0, gdip=0.5, gasia=0.25, nqmom=0.25, gmom=0.25, orb15=0.5, nqdip=0.5, spxdip=0.5)
def vec(d): return np.array([d.get(k, 0) for k in names], float)
ten_all = {k: max(cur[k], need[k]) for k in cur}
ten_no_grids = {k: v for k, v in ten_all.items() if k not in ("nqdip", "spxdip")}
ten_6_scaled = {k: v * 0.75 for k, v in ten_no_grids.items()}
SETS = [("current 8 EAs", vec(cur)), ("every EA sized to 10%/yr (8 EAs)", vec(ten_all)),
        ("6 EAs sized to 10%/yr (grids dropped)", vec(ten_no_grids)), ("6 EAs at 75% of that", vec(ten_6_scaled))]
wst = pd.date_range("2020-04-01", "2025-10-01", freq="MS", tz="UTC")
def evaluate(v):
    lab, w = v; res = []
    for s_ in est:
        h0 = idx.searchsorted(s_); a, i1, _ = run3(w, R, LO, h0, len(idx), 0.10)
        if a != "pass": res.append((s_, a, None)); continue
        b, i2, _ = run3(w, R, LO, h0 + i1 + 1, len(idx), 0.05); res.append((s_, b, (i1 + i2) / 24 if b == "pass" else None))
    yy = [(s_, *run3(w, R, LO, idx.searchsorted(s_), idx.searchsorted(s_ + pd.DateOffset(years=1)), None)) for s_ in wst]
    t = [x[2] for x in res if x[2] is not None]
    return dict(setup=lab, total_risk=w.sum(), pass_=100 * np.mean([x[1] == "pass" for x in res]), breach=100 * np.mean([x[1] == "fail" for x in res]),
                halted=100 * np.mean([x[1] == "stopped" for x in res]), days=np.median(t), funded_med=100 * np.median([q[3] for q in yy]),
                funded_breaches=f"{sum(q[1] == 'fail' for q in yy)}/{len(yy)}", per_year_simple=100 * (R * w[:, None]).sum() / yrs)
with Pool(3) as p: out = p.map(evaluate, SETS)
pd.set_option("display.width", 250); print(pd.DataFrame(out).round(2).to_string(index=False))
