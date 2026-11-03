# Replace the <10%/yr EAs with dip-search winners and upgrade BTC/Gold dip; check the whole prop account.
import sys, numpy as np, pandas as pd
SP = sys.argv[1]
exec(open(SP + "/speed8.py").read().split("V2 = [")[0])
_l = open(SP + "/losers.py").read(); exec("def run3" + _l.split("def run3", 1)[1].split("wst =")[0])
from portfolio_prop import resample, rsi, rma
from multiprocessing import Pool
def dipT(raw, tf, rl, buy, ema_n, hold_h, crash):
    b = resample(raw, tf) if tf != "1h" else raw; c = b.c
    d = raw.c.resample("1D").last().dropna()
    blk = (d / d.shift(30) - 1 < -crash).shift(1).reindex(b.index.floor("D")).fillna(False).to_numpy().astype(bool)
    sig = ((rsi(c, rl) < buy) & (c > c.ewm(span=ema_n, adjust=False).mean())).to_numpy() & ~blk
    tr = pd.concat([b.h - b.l, (b.h - c.shift()).abs(), (b.l - c.shift()).abs()], axis=1).max(axis=1); atr = rma(tr, 14).to_numpy()
    O_, L, C, T = b.o.to_numpy(), b.l.to_numpy(), c.to_numpy(), b.index; bar = T[1] - T[0]; mb = max(1, int(pd.Timedelta(f"{hold_h}h") / bar))
    out = []; i = 0
    while i < len(C) - 2:
        if not sig[i] or np.isnan(atr[i]): i += 1; continue
        j = i + 1; e, st = O_[j], C[i] - 2 * atr[i]
        if e <= st: i += 1; continue
        k, px = j, None
        while k < len(C) - 1:
            if L[k] <= st: px, xt = min(O_[k], st), T[k] + bar; break
            if k - j + 1 >= mb: px, xt = O_[k + 1], T[k + 1]; k += 1; break
            k += 1
        if px is None: break
        if xt - T[j] <= pd.Timedelta(days=12 + hold_h / 24): out.append((T[j], xt, e, st, px))
        i = k
    return out
spx = load_csv(SP + "/fut/USA500IDXUSD.csv"); oil = load_csv(SP + "/fut/LIGHTCMDUSD.csv"); slv = load_csv(SP + "/fut/XAGUSD.csv")
eth = load(SP + "/kh/ETHUSDT.csv").loc["2019-06-01":]; sol = load(SP + "/kh/SOLUSDT.csv")
NEW = {"btc1h144": (btc, "1h", 3, 20, 100, 144, 0.15, P.FEE_CRYPTO), "gold1h144": (gold, "1h", 2, 20, 100, 144, 0.08, 0.0001),
       "nq2h": (nq, "2h", 2, 25, 50, 96, 0.08, 0.00012), "spx1h": (spx, "1h", 2, 15, 200, 48, 0.08, 0.0001),
       "oil1h": (oil, "1h", 2, 25, 50, 144, 0.15, 0.0003), "silver1h": (slv, "1h", 2, 15, 200, 144, 0.12, 0.00025),
       "eth1h": (eth, "1h", 3, 25, 50, 144, 0.15, P.FEE_CRYPTO), "sol1h": (sol, "1h", 2, 20, 100, 144, 0.2, P.FEE_CRYPTO)}
SER = {k: P.trade_series(dipT(*v[:7]), v[7], v[0], idx) for k, v in NEW.items()}
print("built", flush=True)
yrs = (idx[-1] - idx[0]).days / 365.25
d = pd.DataFrame({k: s[0] for k, s in SER.items()} | {k: R[names.index(k)] for k in ("btc", "gdip", "nqdip", "spxdip")}, index=idx).resample("1D").sum()
print("daily correlations:"); print(d[d.abs().sum(axis=1) > 0].corr().round(2).to_string(), flush=True)
cur = dict(btc=1.0, gdip=0.5, gasia=0.25, nqmom=0.25, gmom=0.25, orb15=0.5, nqdip=0.5, spxdip=0.5)
def setup(lab, drop=(), add={}):
    w = {k: v for k, v in cur.items() if k not in drop}; extra = [(k, x) for k, x in add.items()]
    return (lab, w, extra)
NEWSET = dict(btc=1.0, gdip=0.5, gasia=0.25, gmom=0.25, orb15=0.5)
EXTRA = [("nq2h", 0.25), ("spx1h", 0.25), ("oil1h", 0.15)]
Rm = np.vstack([R] + [SER[k][0] for k, _ in EXTRA]); LOm = np.vstack([LO] + [SER[k][1] for k, _ in EXTRA])
w = np.array([NEWSET.get(k, 0) for k in names] + [x for _, x in EXTRA], float); nm = names + [k for k, _ in EXTRA]
wst = pd.date_range("2020-04-01", "2025-10-01", freq="MS", tz="UTC")
def run_mult(m1, halt1):
    res = []
    for s_ in est:
        h0 = idx.searchsorted(s_); a, i1, _ = run3(w * m1, Rm, LOm, h0, len(idx), 0.10, halt=halt1)
        if a != "pass": res.append((s_, a, None)); continue
        b, i2, _ = run3(w, Rm, LOm, h0 + i1 + 1, len(idx), 0.05); res.append((s_, b, (i1 + i2) / 24 if b == "pass" else None))
    return res
from multiprocessing import Pool
def job(v):
    m1, halt1 = v; res = run_mult(m1, halt1); o = dict(phase1=f"x{m1}, daily stop {int(halt1*5)}%")
    for p, sel in (("A", lambda s: s < split), ("B", lambda s: s >= split), ("all", lambda s: True)):
        rr = [x for x in res if sel(x[0])]; t = np.array([x[2] for x in rr if x[2] is not None])
        o |= {f"{p}_pass": 100 * np.mean([x[1] == "pass" for x in rr]), f"{p}_breach": 100 * np.mean([x[1] == "fail" for x in rr]),
              f"{p}_days": np.median(t), f"{p}_le90": 100 * np.sum(t <= 90) / len(rr)}
    return o
with Pool(3) as p: out = p.map(job, [(1.0, 0.8), (1.25, 0.6), (1.25, 0.8), (1.5, 0.6)])
pd.set_option("display.width", 260); print(pd.DataFrame(out).round(1).to_string(index=False), flush=True)
yy = [run3(w, Rm, LOm, idx.searchsorted(s_), idx.searchsorted(s_ + pd.DateOffset(years=1)), None) for s_ in wst]
eqc = np.cumprod(1 + (Rm * w[:, None]).sum(0)); mdd = 100 * np.max(1 - eqc / np.maximum.accumulate(eqc))
cal = {y: round(100 * run3(w, Rm, LOm, idx.searchsorted(pd.Timestamp(f"{y}-01-01", tz="UTC")), idx.searchsorted(pd.Timestamp(f"{y+1}-01-01", tz="UTC")), None)[2]) for y in range(2020, 2027)}
print(f"funded year: median {100*np.median([q[2] for q in yy]):+.1f}% avg {100*np.mean([q[2] for q in yy]):+.1f}% breaches {sum(q[0]=='fail' for q in yy)}/{len(yy)} | maxDD {mdd:.1f}% | years {cal}")
yrs = (idx[-1] - idx[0]).days / 365.25
for i, k in enumerate(nm):
    if w[i] > 0:
        r = Rm[i] * w[i]; e = np.cumsum(r); y = pd.Series(r, idx).resample("YS").sum() * 100
        print(f"{k:<8} risk {w[i]:.2f}  per year {100*r.sum()/yrs:+.1f}%  at 1% risk {100*Rm[i].sum()/yrs:+.1f}%  maxDD {100*np.max(np.maximum.accumulate(e)-e):.1f}%  years {y.round(1).to_dict()}")
