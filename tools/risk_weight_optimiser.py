# Risk-weight optimisation for the 9 EAs: picked on 2020-22 starts, judged on 2023-25.
import sys, numpy as np, pandas as pd
SP = sys.argv[1]
exec(open(SP + "/replace.py").read().split("S = [setup(")[0])
_l = open(SP + "/losers.py").read(); exec("def run3" + _l.split("def run3", 1)[1].split("wst =")[0])
src = open(SP + "/lowtf_port.py").read(); exec("def bars1" + src.split("def bars1", 1)[1].split("def cands")[0])
from portfolio_prop import rsi, rma
from multiprocessing import Pool
b = bars1("fut1m/USATECHIDXUSD_1m.csv", "15min"); c = b.c; Cc = c.to_numpy()
atr = rma(pd.concat([b.h - b.l, (b.h - c.shift()).abs(), (b.l - c.shift()).abs()], axis=1).max(axis=1), 14).to_numpy()
ny = b.index.tz_convert("America/New_York"); nym = ny.hour * 60 + ny.minute
hi = b.h.rolling(20).max().shift(1).to_numpy(); lo_ = b.l.rolling(20).min().shift(1).to_numpy(); e = c.ewm(span=200, adjust=False).mean().to_numpy(); win = (nym >= 570) & (nym < 720)
bo = P.trade_series(simT(b, win & (Cc > hi) & (Cc > e), win & (Cc < lo_) & (Cc < e), atr, 10 ** 6, nym >= 950), 0.00012, nq, idx)
KEYS = ["btc", "gdip", "gasia", "gmom", "orb15", "nq2h", "spx1h", "oil1h", "nqbo15"]
BASE = np.array([1.0, 0.5, 0.25, 0.25, 0.5, 0.25, 0.25, 0.15, 0.1])
RM = np.vstack([R[names.index(k)] if k in names else (SER[k][0] if k in SER else bo[0]) for k in KEYS])
LM = np.vstack([LO[names.index(k)] if k in names else (SER[k][1] if k in SER else bo[1]) for k in KEYS])
wst = pd.date_range("2020-04-01", "2025-10-01", freq="MS", tz="UTC")
def ev(w, part):
    sel = [s for s in est if (s < split) == (part == "A")]
    res = []
    for s_ in sel:
        h0 = idx.searchsorted(s_); a, i1, _ = run3(w, RM, LM, h0, len(idx), 0.10)
        if a != "pass": res.append((a, None)); continue
        b2, i2, _ = run3(w, RM, LM, h0 + i1 + 1, len(idx), 0.05); res.append((b2, (i1 + i2) / 24 if b2 == "pass" else None))
    ws = [s for s in wst if (s < split) == (part == "A")]
    yy = [run3(w, RM, LM, idx.searchsorted(s_), idx.searchsorted(s_ + pd.DateOffset(years=1)), None) for s_ in ws]
    t = [x[1] for x in res if x[1] is not None]
    return dict(pass_=100 * np.mean([x[0] == "pass" for x in res]), breach=100 * np.mean([x[0] == "fail" for x in res]),
                days=np.median(t) if t else 999, fund=100 * np.median([y[2] for y in yy]), fbr=sum(y[0] == "fail" for y in yy))
def jobA(m): return (m, ev(BASE * np.array(m), "A"))
rng = np.random.default_rng(11); levels = np.array([0.5, 0.75, 1.0, 1.25, 1.5])
cands = [tuple([1.0] * 9)] + [tuple(rng.choice(levels, 9)) for _ in range(200)]
with Pool(3) as p: resA = p.map(jobA, cands)
ok = [(m, r) for m, r in resA if r["breach"] == 0 and r["fbr"] == 0 and r["pass_"] >= 93]
ok.sort(key=lambda x: (x[1]["days"], -x[1]["pass_"]))
print(f"{len(ok)} of {len(cands)} mixes kept 2020-22 at >=93% pass, 0 breaches", flush=True)
base_A = resA[0][1]; print("current (A):", {k: round(v, 1) for k, v in base_A.items()}, flush=True)
top = [cands[0]] + [m for m, _ in ok[:6] if m != cands[0]]
with Pool(3) as p: resB = p.map(lambda m: None, [])  if False else None
rows = []
for m in top:
    a = [r for mm, r in resA if mm == m][0]; bB = ev(BASE * np.array(m), "B")
    rows.append(dict(weights=" ".join(f"{k}={BASE[i] * m[i]:.3g}" for i, k in enumerate(KEYS)), total=round(float((BASE * np.array(m)).sum()), 2),
                     A_pass=a["pass_"], A_days=a["days"], A_fund=a["fund"], B_pass=bB["pass_"], B_breach=bB["breach"], B_days=bB["days"], B_fund=bB["fund"], B_fbr=bB["fbr"]))
    print(rows[-1], flush=True)
pd.set_option("display.width", 300); pd.set_option("display.max_colwidth", 140); print(pd.DataFrame(rows).round(1).to_string(index=False))
