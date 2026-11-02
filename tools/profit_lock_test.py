# Profit lock on BTC Dip / Gold Dip to shrink crash-day givebacks, then retry the add-ons that only failed on breaches.
import sys, numpy as np, pandas as pd
SP = sys.argv[1]
exec(open(SP + "/speed8.py").read().split("V2 = [")[0])
_l = open(SP + "/losers.py").read(); exec("def run3" + _l.split("def run3", 1)[1].split("wst =")[0])
from portfolio_prop import resample, rsi, rma
from multiprocessing import Pool
def dip_lock(raw1h, tf, rl, buy, crash_pct, lock_at, lock_to):
    b = resample(raw1h, tf) if tf != "1h" else raw1h; c = b.c
    d = raw1h.c.resample("1D").last().dropna()
    crash = (d / d.shift(30) - 1 < -crash_pct).shift(1).reindex(b.index.floor("D")).fillna(False).to_numpy().astype(bool)
    sig = ((rsi(c, rl) < buy) & (c > c.ewm(span=50, adjust=False).mean())).to_numpy() & ~crash
    tr = pd.concat([b.h - b.l, (b.h - c.shift()).abs(), (b.l - c.shift()).abs()], axis=1).max(axis=1); atr = rma(tr, 14).to_numpy()
    O_, H, L, C, T = b.o.to_numpy(), b.h.to_numpy(), b.l.to_numpy(), c.to_numpy(), b.index
    bar = T[1] - T[0]; mb = int(pd.Timedelta("96h") / bar); out, i = [], 0
    while i < len(C) - 2:
        if not sig[i] or np.isnan(atr[i]): i += 1; continue
        j = i + 1; e, st0 = O_[j], C[i] - 2 * atr[i]; st = st0
        if e <= st: i += 1; continue
        R1 = e - st0; k, px = j, None
        while k < len(C) - 1:
            if L[k] <= st: px, xt = min(O_[k], st), T[k] + bar; break
            if k - j + 1 >= mb: px, xt = O_[k + 1], T[k + 1]; k += 1; break
            if lock_at and H[k] >= e + lock_at * R1: st = max(st, e + lock_to * R1)       # lock part of the gain (from the next bar)
            k += 1
        if px is None: break
        if xt - T[j] <= pd.Timedelta(days=10): out.append((T[j], xt, e, st0, px))
        i = k
    return out
def worst_day(Rm, LOm, w):
    r = (Rm * w[:, None]).sum(0); lo = (LOm * w[:, None]).sum(0); ds = pd.Series(days); worst = []
    for d, ix in ds.groupby(ds).groups.items():
        ix = np.array(sorted(ix)); cum = np.concatenate([[0], np.cumsum(r[ix])[:-1]]); worst.append(np.min(cum + lo[ix]))
    worst = np.sort(np.array(worst)); return 100 * worst[0], 100 * worst[2]
wst = pd.date_range("2020-04-01", "2025-10-01", freq="MS", tz="UTC")
def evaluate(args):
    lab, Rm, LOm, w = args; res = []
    for s_ in est:
        h0 = idx.searchsorted(s_); a, i1, _ = run3(w, Rm, LOm, h0, len(idx), 0.10)
        if a != "pass": res.append((s_, a, None)); continue
        b2, i2, _ = run3(w, Rm, LOm, h0 + i1 + 1, len(idx), 0.05); res.append((s_, b2, (i1 + i2) / 24 if b2 == "pass" else None))
    yy = [(s_, *run3(w, Rm, LOm, idx.searchsorted(s_), idx.searchsorted(s_ + pd.DateOffset(years=1)), None)) for s_ in wst]
    w1, w3 = worst_day(Rm, LOm, w); out = dict(variant=lab, worst_day=w1, third_worst=w3)
    for p, sel in (("A", lambda s: s < split), ("B", lambda s: s >= split)):
        rr = [x for x in res if sel(x[0])]; t = [x[2] for x in rr if x[2] is not None]; y = [v for v in yy if sel(v[0])]
        out |= {f"{p}_pass": 100 * np.mean([x[1] == "pass" for x in rr]), f"{p}_breach": 100 * np.mean([x[1] == "fail" for x in rr]), f"{p}_days": np.median(t),
                f"{p}_fund": 100 * np.median([v[3] for v in y]), f"{p}_fbr": sum(v[1] == "fail" for v in y)}
    return out
ib, ig = names.index("btc"), names.index("gdip"); yrs = (idx[-1] - idx[0]).days / 365.25
LOCKS = [(None, None), (2, 0.5), (2, 1.0), (3, 1.0), (3, 2.0), (4, 2.0)]
SER = {}
for la, lt in LOCKS:
    SER[(la, lt)] = (P.trade_series(dip_lock(btc, "2h", 3, 20, 0.15, la, lt), P.FEE_CRYPTO, btc, idx), P.trade_series(dip_lock(gold, "1h", 2, 10, 0.08, la, lt), P.COST["XAUUSD"], gold, idx))
    (rb, _), (rg, _) = SER[(la, lt)]
    print(f"lock {la}->{lt}: BTC Dip alone {100*rb.sum()/yrs:+.1f}%/yr, Gold Dip alone {100*rg.sum()/yrs:+.1f}%/yr", flush=True)
jobs = []
for la, lt in LOCKS:
    Rm, LOm = R.copy(), LO.copy(); (Rm[ib], LOm[ib]), (Rm[ig], LOm[ig]) = SER[(la, lt)]
    jobs.append((f"8 EAs, lock {la}->{lt}" if la else "8 EAs as now", Rm, LOm, W))
with Pool(3) as p: out = p.map(evaluate, jobs)
df = pd.DataFrame(out); pd.set_option("display.width", 250); print(df.round(1).to_string(index=False), flush=True)
# retry the blocked add-ons on the best lock (largest worst-day improvement with funded B within 3 points of baseline)
base = df.iloc[0]; ok = df.iloc[1:][(df.iloc[1:].B_fund >= base.B_fund - 3) & (df.iloc[1:].A_breach == 0) & (df.iloc[1:].B_breach == 0)]
if len(ok):
    best = ok.sort_values("worst_day", ascending=False).iloc[0]; key = LOCKS[1 + ok.sort_values("worst_day", ascending=False).index[0] - 1]
    print(f"\nbest lock: {best.variant}; retrying add-ons on it")
    Rm, LOm = R.copy(), LO.copy(); (Rm[ib], LOm[ib]), (Rm[ig], LOm[ig]) = SER[key]
    slv = load_csv(SP + "/fut/XAGUSD.csv"); spx = load_csv(SP + "/fut/USA500IDXUSD.csv")
    exec(open(SP + "/cook3.py").read().split("def dip2")[1].join(["def dip2", ""]).split("spx = load_csv")[0]) if False else None
    src3 = open(SP + "/cook3.py").read(); exec("def dip2" + src3.split("def dip2", 1)[1].split("spx = load_csv")[0])
    adds = {"silver dip 1h": P.trade_series(dip2(slv, "1h", 2, 10, 0.12, 1), 0.00025, slv, idx), "nq dip 1h": P.trade_series(dip2(nq, "1h", 2, 10, 0.08, 1), 0.00012, nq, idx)}
    jobs2 = [(f"{best.variant} + {k} {wt}", np.vstack([Rm, v[0]]), np.vstack([LOm, v[1]]), np.append(W, wt)) for k, v in adds.items() for wt in (0.25, 0.5)]
    with Pool(3) as p: out2 = p.map(evaluate, jobs2)
    print(pd.DataFrame(out2).round(1).to_string(index=False))
else:
    print("\nno lock kept the funded return within 3 points without breaches")
