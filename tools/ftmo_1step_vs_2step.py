# FTMO $10K: 2-Step (+10%/+5%, 5% daily, 10% static) vs 1-Step (+10%, 3% daily, 10% EOD trailing, best-day 50%) with the new 8 EAs.
import sys, numpy as np, pandas as pd
SP = sys.argv[1]
exec(open(SP + "/replace.py").read().split("S = [setup(")[0])
_l = open(SP + "/losers.py").read(); exec("def run3" + _l.split("def run3", 1)[1].split("wst =")[0])
from multiprocessing import Pool
W8 = {"btc": 1.0, "gdip": 0.5, "gasia": 0.25, "gmom": 0.25, "orb15": 0.5, "nq2h": 0.25, "spx1h": 0.25, "oil1h": 0.15}
RM = np.vstack([R[names.index(k)] if k in names else SER[k][0] for k in W8]); LM = np.vstack([LO[names.index(k)] if k in names else SER[k][1] for k in W8])
WB = np.array(list(W8.values()))
def one_step(w, h0, h1, target=0.10, daily=0.03, maxl=0.10, halt=0.8, buf=0.02, best=0.5):
    r = (RM[:, h0:h1] * w[:, None]).sum(0); lo = (LM[:, h0:h1] * w[:, None]).sum(0)
    eq = 1.0; day = None; hd = None; eodhigh = 1.0; floor = 1 - maxl; dpos = []; dopen = 1.0
    for i in range(len(r)):
        d_ = days[h0 + i]
        if d_ != day:
            if day is not None:
                dpos.append(eq - dopen); eodhigh = max(eodhigh, eq); floor = min(1.0, eodhigh - maxl)
                prof = eq - 1; posd = [x for x in dpos if x > 0]
                if target and prof >= target and max(posd) <= best * sum(posd): return "pass", i, eq - 1
            day = d_; dopen = eq
        if hd == d_: continue
        if eq * (1 + lo[i]) <= floor or eq * (1 + lo[i]) <= dopen - daily: return "fail", i, eq - 1
        eq *= 1 + r[i]
        if dopen - eq >= halt * daily: hd = d_
        if eq <= floor + buf: return "stopped", i, eq - 1
    return "open", len(r), eq - 1
est = pd.date_range("2020-04-01", "2025-09-01", freq="7D", tz="UTC"); wst = pd.date_range("2020-04-01", "2025-10-01", freq="MS", tz="UTC")
def job(v):
    kind, m = v; w = WB * m; res = []
    for s_ in est:
        h0 = idx.searchsorted(s_)
        if kind == "2-Step":
            a, i1, _ = run3(w, RM, LM, h0, len(idx), 0.10, halt=0.8 if m <= 1 else 0.6)
            if a != "pass": res.append((a, None)); continue
            b, i2, _ = run3(WB, RM, LM, h0 + i1 + 1, len(idx), 0.05); res.append((b, (i1 + i2) / 24 if b == "pass" else None))
        else:
            a, i1, _ = one_step(w, h0, len(idx)); res.append((a, i1 / 24 if a == "pass" else None))
    t = np.array([x[1] for x in res if x[1] is not None]); n = len(res)
    # funded year after passing (same rules as the challenge type), simple 12-month windows
    fy = []
    for s_ in wst:
        h0, h1 = idx.searchsorted(s_), idx.searchsorted(s_ + pd.DateOffset(years=1))
        st, _, ret = (run3(WB, RM, LM, h0, h1, None) if kind == "2-Step" else one_step(w, h0, h1, target=None))
        fy.append((st, ret))
    return dict(type=kind, risk_mult=m, pass_=100 * np.mean([x[0] == "pass" for x in res]), breach=100 * np.mean([x[0] == "fail" for x in res]),
                stopped=100 * np.mean([x[0] == "stopped" for x in res]), median_days=np.median(t), le30=100 * np.sum(t <= 30) / n,
                le60=100 * np.sum(t <= 60) / n, le90=100 * np.sum(t <= 90) / n, funded_median=100 * np.median([x[1] for x in fy]),
                funded_breach=f"{sum(x[0] == 'fail' for x in fy)}/{len(fy)}", funded_worst=100 * min(x[1] for x in fy))
cfg = [("2-Step", 1.0), ("2-Step", 1.25), ("1-Step", 0.5), ("1-Step", 0.6), ("1-Step", 0.75), ("1-Step", 1.0)]
with Pool(3) as p: out = p.map(job, cfg)
pd.set_option("display.width", 250); print(pd.DataFrame(out).round(1).to_string(index=False))
