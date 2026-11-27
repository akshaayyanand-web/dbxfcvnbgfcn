# Noise Band NQ (k=1) and BTC #448: random entry, double costs, one-bar delay, nearby settings, best days out, crazy future (cuts at 14:00 UTC).
import sys, numpy as np, pandas as pd
sys.argv = sys.argv[:1]
src = open("ql.py").read(); exec(src.split("def noise_band")[0])
def nb(S, L, k=1.0, look=14, costm=1.0, delay=0, rand=None, p=None):
    days = sorted(S); res = []; prev_close = None; hist = []
    for day in days:
        x = S[day]; m = x.m.to_numpy(); o = x.o.to_numpy(); h = x.h.to_numpy(); l = x.l.to_numpy(); c = x.c.to_numpy(); v = x.v.to_numpy(); op = o[0]
        mv = np.full(L, np.nan); mv[m] = np.abs(c / op - 1)
        if len(hist) >= look and prev_close is not None:
            sig = np.nanmean(np.vstack(hist[-look:]), axis=0); ub = max(op, prev_close) * (1 + k * sig); lb = min(op, prev_close) * (1 - k * sig)
            tp = (h + l + c) / 3; w = np.where(v > 0, v, 1.0); vwap = np.cumsum(tp * w) / np.cumsum(w); pos = 0
            for i in range(len(c)):
                mi = m[i]
                if pos:
                    if (pos > 0 and l[i] <= stop) or (pos < 0 and h[i] >= stop): res.append((day, (pos * (stop - e) - costm * COST * e) / risk)); pos = 0; continue
                    if mi >= L - 5: res.append((day, (pos * (c[i] - e) - costm * COST * e) / risk)); pos = 0; break
                    if mi >= 30 and mi % 30 == 29:
                        bb = max(ub[mi], vwap[i]) if pos > 0 else min(lb[mi], vwap[i])
                        if (pos > 0 and c[i] < bb) or (pos < 0 and c[i] > bb): res.append((day, (pos * (c[i] - e) - costm * COST * e) / risk)); pos = 0
                    continue
                if mi >= 30 and mi % 30 == 29 and mi < L - 35 and i + 1 + delay < len(c) and np.isfinite(ub[mi]):
                    d = 1 if c[i] > ub[mi] else (-1 if c[i] < lb[mi] else 0)
                    if rand is not None: d = (1 if rand.random() < 0.5 else -1) if rand.random() < p else 0
                    if d:
                        e = o[i + 1 + delay]; risk = k * sig[mi] * op if np.isfinite(sig[mi]) else None
                        if risk and risk > 3 * COST * e: pos = d; stop = e - d * risk
        hist.append(mv); prev_close = c[-1]
    return res
S, L = sessions("NQ"); base = nb(S, L); r0 = np.array([x[1] for x in base]); m0 = r0.mean()
checks = sum(1 for d in S for mm in S[d].m.to_numpy() if mm >= 30 and mm % 30 == 29 and mm < L - 35); p = len(base) / checks
T = lambda tr: (lambda r: f"{r.mean():+.3f}R (t {r.mean()/r.std()*np.sqrt(len(r)):.2f}, {len(r)} trades)")(np.array([x[1] for x in tr]))
print("NOISE BAND NQ k=1 base:", T(base))
rnd = [np.mean([x[1] for x in nb(S, L, rand=np.random.default_rng(s), p=p)]) for s in range(30)]
print(f"  random entry (30 runs): random mean {np.mean(rnd):+.3f}R, strategy beats {100*np.mean(np.array(rnd) < m0):.0f}%")
print("  double costs:", T(nb(S, L, costm=2.0))); print("  enter one bar later:", T(nb(S, L, delay=1)))
print("  nearby:", "; ".join(f"{lab} {np.mean([x[1] for x in nb(S, L, **kw)]):+.3f}" for lab, kw in (("k=0.8", dict(k=0.8)), ("k=1.2", dict(k=1.2)), ("look 10", dict(look=10)), ("look 20", dict(look=20)))))
dd = pd.Series(r0, [x[0] for x in base]).groupby(level=0).sum(); print(f"  best days out: top 1% removed {dd[dd < dd.quantile(.99)].sum()/len(r0):+.3f}R/trade, top 5% removed {dd[dd < dd.quantile(.95)].sum()/len(r0):+.3f}R/trade")
