# Portfolio test of the best 5m/15m candidates with the new 8 EAs; plus a 2x-cost check.
import sys, numpy as np, pandas as pd
SP = sys.argv[1]
exec(open(SP + "/replace.py").read().split("S = [setup(")[0])
_l = open(SP + "/losers.py").read(); exec("def run3" + _l.split("def run3", 1)[1].split("wst =")[0])
from portfolio_prop import rsi, rma
from multiprocessing import Pool
def bars1(path, rule): d = load_csv(SP + "/" + path); return d.resample(rule).agg(dict(o="first", h="max", l="min", c="last")).dropna().loc["2019-03-01":]
def simT(b, L, S, sd, hold, flat=None):
    O, H, Lo, C, T = b.o.to_numpy(), b.h.to_numpy(), b.l.to_numpy(), b.c.to_numpy(), b.index; n = len(C); out = []; i = 0
    while i < n - 2:
        d = 1 if L[i] else (-1 if S is not None and S[i] else 0)
        if d == 0 or not np.isfinite(sd[i]) or sd[i] <= 0: i += 1; continue
        j = i + 1; e = O[j]; st = e - d * sd[i]; k = j; px = None
        while k < n - 1:
            if (Lo[k] <= st) if d == 1 else (H[k] >= st): px, xt = (min(O[k], st) if d == 1 else max(O[k], st)), T[k] + (T[1] - T[0]); break
            gap = T[k + 1] - T[k] > pd.Timedelta(hours=6)
            if k - j + 1 >= hold or (flat is not None and flat[k]) or gap: px, xt = (C[k], T[k] + (T[1] - T[0])) if gap else (O[k + 1], T[k + 1]); k += 1; break
            k += 1
        if px is None: break
        out.append((T[j], xt, e, st, px)); i = k
    return out
def cands(costmult=1.0):
    C_ = {}
    nq5 = bars1("fut1m/USATECHIDXUSD_1m.csv", "5min"); g5 = bars1("fut1m/XAUUSD_1m.csv", "5min"); nq15 = bars1("fut1m/USATECHIDXUSD_1m.csv", "15min")
    for nm, b, kind in (("NQ 5m breakout", nq5, "bo50"), ("NQ 5m dip", nq5, "dip"), ("Gold 5m dip", g5, "dipg"), ("NQ 15m breakout", nq15, "bo20")):
        c = b.c; Cc = c.to_numpy(); atr = rma(pd.concat([b.h - b.l, (b.h - c.shift()).abs(), (b.l - c.shift()).abs()], axis=1).max(axis=1), 14).to_numpy()
        ny = b.index.tz_convert("America/New_York"); nym = ny.hour * 60 + ny.minute; flat = nym >= 950
        bpd = 288 if b is not nq15 else 96
        if kind.startswith("bo"):
            N, en = (50, 800) if kind == "bo50" else (20, 200)
            hi = b.h.rolling(N).max().shift(1).to_numpy(); lo_ = b.l.rolling(N).min().shift(1).to_numpy(); e = c.ewm(span=en, adjust=False).mean().to_numpy()
            win = (nym >= 570) & (nym < 720)
            tr = simT(b, win & (Cc > hi) & (Cc > e), win & (Cc < lo_) & (Cc < e), 1.0 * atr, 10 ** 6, flat)
        else:
            en = 800 if kind == "dip" else 200
            r = rsi(c, 2).to_numpy(); e = c.ewm(span=en, adjust=False).mean().to_numpy()
            tr = simT(b, (r < 10) & (Cc > e), None, 2 * atr, bpd)
        h1 = nq if "NQ" in nm else gold; cost = (0.00012 if "NQ" in nm else 0.0001) * costmult
        C_[nm] = (P.trade_series(tr, cost, h1, idx), len(tr))
    return C_
CND = cands(1.0); CND2 = cands(2.0)
yrs = (idx[-1] - idx[0]).days / 365.25
for k, ((r, lo), n) in CND.items():
    r2 = CND2[k][0][0]
    print(f"{k}: {n / (yrs * 12):.0f} trades/month | %/yr at 1% risk: costs as tested {100 * r.sum() / yrs:+.1f}, costs x2 {100 * r2.sum() / yrs:+.1f}", flush=True)
W8 = {"btc": 1.0, "gdip": 0.5, "gasia": 0.25, "gmom": 0.25, "orb15": 0.5, "nq2h": 0.25, "spx1h": 0.25, "oil1h": 0.15}
RM = np.vstack([R[names.index(k)] if k in names else SER[k][0] for k in W8]); LM = np.vstack([LO[names.index(k)] if k in names else SER[k][1] for k in W8]); WB = np.array(list(W8.values()))
d = pd.DataFrame({k: v[0][0] for k, v in CND.items()} | {k: RM[i] for i, k in enumerate(W8)}, index=idx).resample("1D").sum()
print("daily correlation of candidates with the 8 EAs:"); print(d[d.abs().sum(axis=1) > 0].corr().round(2).loc[list(CND), list(W8)].to_string(), flush=True)
wst = pd.date_range("2020-04-01", "2025-10-01", freq="MS", tz="UTC")
def evaluate(v):
    lab, adds, drop, cm = v
    src = CND if cm == 1 else CND2
    w = WB.copy()
    for k in drop: w[list(W8).index(k)] = 0
    Rm = np.vstack([RM] + [src[k][0][0] for k, _ in adds]); Lm = np.vstack([LM] + [src[k][0][1] for k, _ in adds]); w = np.append(w, [x for _, x in adds])
    res = []
    for s_ in est:
        h0 = idx.searchsorted(s_); a, i1, _ = run3(w, Rm, Lm, h0, len(idx), 0.10)
        if a != "pass": res.append((s_, a, None)); continue
        b, i2, _ = run3(w, Rm, Lm, h0 + i1 + 1, len(idx), 0.05); res.append((s_, b, (i1 + i2) / 24 if b == "pass" else None))
    yy = [(s_, *run3(w, Rm, Lm, idx.searchsorted(s_), idx.searchsorted(s_ + pd.DateOffset(years=1)), None)) for s_ in wst]
    o = dict(setup=lab, costs=f"x{cm}")
    for p, sel in (("A", lambda s: s < split), ("B", lambda s: s >= split)):
        rr = [x for x in res if sel(x[0])]; t = [x[2] for x in rr if x[2] is not None]; y = [q for q in yy if sel(q[0])]
        o |= {f"{p}_pass": 100 * np.mean([x[1] == "pass" for x in rr]), f"{p}_breach": 100 * np.mean([x[1] == "fail" for x in rr]), f"{p}_days": np.median(t),
              f"{p}_fund": 100 * np.median([q[3] for q in y]), f"{p}_fbr": sum(q[1] == "fail" for q in y)}
    return o
jobs = [("NEW 8 EAs", [], [], 1)]
for k in CND:
    for wt in (0.15, 0.25):
        jobs.append((f"+ {k} {wt}", [(k, wt)], [], 1))
jobs += [("NQ ORB -> NQ 5m breakout 0.25", [("NQ 5m breakout", 0.25)], ["orb15"], 1),
         ("+ NQ 5m breakout 0.15 + Gold 5m dip 0.15", [("NQ 5m breakout", 0.15), ("Gold 5m dip", 0.15)], [], 1),
         ("+ NQ 5m breakout 0.15 (costs x2)", [("NQ 5m breakout", 0.15)], [], 2), ("+ Gold 5m dip 0.15 (costs x2)", [("Gold 5m dip", 0.15)], [], 2)]
with Pool(3) as p: out = p.map(evaluate, jobs)
pd.set_option("display.width", 260); print(pd.DataFrame(out).round(1).to_string(index=False))
