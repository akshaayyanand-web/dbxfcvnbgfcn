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

cur = dict(btc=1.0, gdip=0.5, gasia=0.25, nqmom=0.25, gmom=0.25, orb15=0.5, nqdip=0.5, spxdip=0.5)
def setup(lab, drop=(), add={}):
    w = {k: v for k, v in cur.items() if k not in drop}; extra = [(k, x) for k, x in add.items()]
    return (lab, w, extra)
import orb_lab as O
s5 = O.five_min(load_csv(SP + "/fut1m/USA500IDXUSD_1m.csv"))
ORB = {"nq ORB 3R until 13:00": (nq5, (13, 0), 15, "other", 3.0, True, nq, 0.00012),
       "nq ORB to close, mid stop, until 13:00": (nq5, (13, 0), 15, "mid", None, True, nq, 0.00012),
       "nq ORB 2R until 13:00": (nq5, (13, 0), 15, "other", 2.0, True, nq, 0.00012),
       "spx ORB 60m long, mid, to close": (s5, (13, 0), 60, "mid", None, False, spx, 0.0001)}
for k, (d5, le, mins, sm, tg, both, h1, c) in ORB.items():
    x = O.orb(d5, "America/New_York", (9, 30), le, (15, 55), mins, sm, tg, both, c); SER[k] = P.trade_series([t[:5] for t in x], c, h1, idx)
NEWSET = dict(btc=1.0, gdip=0.5, gasia=0.25, gmom=0.25, orb15=0.5)
BASEX = {"nq2h": 0.25, "spx1h": 0.25, "oil1h": 0.15}
def mk(lab, drop=(), add={}, dropx=()):
    w = {k: v for k, v in NEWSET.items() if k not in drop}; ex = {k: v for k, v in BASEX.items() if k not in dropx}; ex.update(add)
    return (lab, w, list(ex.items()))
S = [mk("NEW 8 EAs (current)"),
     mk("ORB -> 3R, entries until 13:00", ("orb15",), {"nq ORB 3R until 13:00": 0.5}),
     mk("ORB -> 2R, entries until 13:00", ("orb15",), {"nq ORB 2R until 13:00": 0.5}),
     mk("ORB -> hold to close, mid stop", ("orb15",), {"nq ORB to close, mid stop, until 13:00": 0.5}),
     mk("S&P dip 1h -> S&P ORB 60m long", (), {"spx ORB 60m long, mid, to close": 0.25}, ("spx1h",)),
     mk("ORB 3R/13:00 + S&P ORB instead of S&P dip", ("orb15",), {"nq ORB 3R until 13:00": 0.5, "spx ORB 60m long, mid, to close": 0.25}, ("spx1h",))]
wst = pd.date_range("2020-04-01", "2025-10-01", freq="MS", tz="UTC")
def evaluate(v):
    lab, wd, extra = v
    Rm = np.vstack([R] + [SER[k][0] for k, _ in extra]); LOm = np.vstack([LO] + [SER[k][1] for k, _ in extra])
    w = np.array([wd.get(k, 0) for k in names] + [x for _, x in extra], float)
    res = []
    for s_ in est:
        h0 = idx.searchsorted(s_); a, i1, _ = run3(w, Rm, LOm, h0, len(idx), 0.10)
        if a != "pass": res.append((s_, a, None)); continue
        b, i2, _ = run3(w, Rm, LOm, h0 + i1 + 1, len(idx), 0.05); res.append((s_, b, (i1 + i2) / 24 if b == "pass" else None))
    yy = [(s_, *run3(w, Rm, LOm, idx.searchsorted(s_), idx.searchsorted(s_ + pd.DateOffset(years=1)), None)) for s_ in wst]
    eqc = np.cumprod(1 + (Rm * w[:, None]).sum(0)); mdd = 100 * np.max(1 - eqc / np.maximum.accumulate(eqc))
    o = dict(setup=lab, total_risk=w.sum(), maxDD=mdd)
    for p, sel in (("A", lambda s: s < split), ("B", lambda s: s >= split)):
        rr = [x for x in res if sel(x[0])]; t = [x[2] for x in rr if x[2] is not None]; y = [q for q in yy if sel(q[0])]
        o |= {f"{p}_pass": 100 * np.mean([x[1] == "pass" for x in rr]), f"{p}_breach": 100 * np.mean([x[1] == "fail" for x in rr]), f"{p}_days": np.median(t),
              f"{p}_fund": 100 * np.median([q[3] for q in y]), f"{p}_fbr": sum(q[1] == "fail" for q in y)}
    return o
with Pool(3) as p: out = p.map(evaluate, S)
pd.set_option("display.width", 260); print(pd.DataFrame(out).round(1).to_string(index=False))
