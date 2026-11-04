# Breakout (crypto) Classic 1-Step: +10% target, 6% static max loss, 3% daily loss. Crypto dip strategies, guard on.
import sys, numpy as np, pandas as pd, itertools
SP = sys.argv[1]
exec(open(SP + "/replace.py").read().split("S = [setup(")[0])
_l = open(SP + "/losers.py").read(); exec("def run3" + _l.split("def run3", 1)[1].split("wst =")[0])
from multiprocessing import Pool
CR = {"BTC Dip v3 (2h)": R[names.index("btc")], "BTC Dip 1h 6-day": SER["btc1h144"][0], "ETH Dip 1h": SER["eth1h"][0], "SOL Dip 1h": SER["sol1h"][0]}
CL = {"BTC Dip v3 (2h)": LO[names.index("btc")], "BTC Dip 1h 6-day": SER["btc1h144"][1], "ETH Dip 1h": SER["eth1h"][1], "SOL Dip 1h": SER["sol1h"][1]}
keys = list(CR); RM = np.vstack([CR[k] for k in keys]); LM = np.vstack([CL[k] for k in keys])
d = pd.DataFrame(RM.T, index=idx, columns=keys).resample("1D").sum(); print("daily correlation:"); print(d[d.abs().sum(axis=1) > 0].corr().round(2).to_string(), flush=True)
SETS = {"BTC v3 only": ["BTC Dip v3 (2h)"], "BTC 1h 6-day only": ["BTC Dip 1h 6-day"], "BTC v3 + ETH": ["BTC Dip v3 (2h)", "ETH Dip 1h"],
        "BTC v3 + ETH + SOL": ["BTC Dip v3 (2h)", "ETH Dip 1h", "SOL Dip 1h"], "BTC 1h + ETH + SOL": ["BTC Dip 1h 6-day", "ETH Dip 1h", "SOL Dip 1h"],
        "BTC v3 + BTC 1h": ["BTC Dip v3 (2h)", "BTC Dip 1h 6-day"]}
est2 = pd.date_range("2020-10-01", "2025-09-01", freq="7D", tz="UTC")
def job(v):
    sn, r = v; w = np.array([r if k in SETS[sn] else 0.0 for k in keys])
    res = []
    for s_ in est2:
        h0 = idx.searchsorted(s_); a, i1, _ = run3(w, RM, LM, h0, len(idx), 0.10, maxl=0.06, daily=0.03)
        res.append((s_, a, i1 / 24 if a == "pass" else None))
    o = dict(setup=sn, risk_each=r)
    for p, sel in (("A", lambda s: s < split), ("B", lambda s: s >= split)):
        rr = [x for x in res if sel(x[0])]; t = np.array([x[2] for x in rr if x[2] is not None]); n = len(rr)
        o |= {f"{p}_pass": 100 * np.mean([x[1] == "pass" for x in rr]), f"{p}_breach": 100 * np.mean([x[1] == "fail" for x in rr]),
              f"{p}_halted": 100 * np.mean([x[1] == "stopped" for x in rr]), f"{p}_days": np.median(t) if len(t) else np.nan,
              f"{p}_le60": 100 * np.sum(t <= 60) / n}
    return o
cfgs = [(s, r) for s in SETS for r in (0.5, 0.75, 1.0, 1.25)]
with Pool(3) as p: out = p.map(job, cfgs)
pd.set_option("display.width", 250); print(pd.DataFrame(out).round(1).to_string(index=False))
