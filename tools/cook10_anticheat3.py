# BTC #448 (M15 |bar| > 4 sigma, follow; 2ATR stop, 3ATR trail): random entry, double costs, delay, nearby, best days out. Cost = real 0.09%.
import sys, numpy as np, pandas as pd
sys.argv = sys.argv[:1]
import cat1000 as K, cat2000 as K2
b = K2.bars2("BTC", "M15"); Xp = K.X(b, "BTC", "M15", False, {"tb": b.tb.to_numpy()}); Xn = K.X(b, "BTC", "M15", True, {"tb": b.tb.to_numpy()})
O, H, L, C = (b[c].to_numpy() for c in "ohlc"); A = Xp.atr(); shl, _, _, sll, _, _ = Xp.sw(); T = b.index
r1 = np.diff(C, prepend=np.nan); sd = pd.Series(r1).rolling(200).std().to_numpy()
def sigs(th):
    up = r1 > th * sd; dn = r1 < -th * sd; up[-3:] = dn[-3:] = False; ks = np.r_[np.where(up)[0], np.where(dn)[0]]; ds = np.r_[np.ones(up.sum()), -np.ones(dn.sum())]
    o = np.argsort(ks, kind="stable"); return ks[o].astype(np.int64), ds[o]
def run(ks, ds, cost=0.0009, delay=0):
    ks2 = ks + delay; st = np.zeros(len(ks)); R, XK = K.nb_exit(O, H, L, C, A, sll, shl, ks2, ds, st, cost, 0.15 / 365 * 0.25 / 24, 2, 0.0, 50)
    keep = K.nb_nonoverlap(ks2, XK, np.isfinite(R)); return R[keep], ks2[keep]
ks, ds = sigs(4.0); r, kk = run(ks, ds); m0 = r.mean(); fmt = lambda r: f"{r.mean():+.3f}R (t {r.mean()/r.std()*np.sqrt(len(r)):.2f}, {len(r)} trades)"
print("BTC #448 base:", fmt(r))
rng = np.random.default_rng(3); rnd = []
for s in range(40):
    rk = np.sort(rng.choice(np.arange(300, len(C) - 60), len(ks), replace=False)).astype(np.int64); rd = rng.choice([-1.0, 1.0], len(ks)); rnd.append(run(rk, rd)[0].mean())
print(f"  random entry (40 runs): random mean {np.mean(rnd):+.3f}R, strategy beats {100*np.mean(np.array(rnd) < m0):.0f}%")
print("  double costs (0.18%):", fmt(run(ks, ds, cost=0.0018)[0])); print("  enter one bar later:", fmt(run(ks, ds, delay=1)[0]))
print("  nearby:", "; ".join(f"{th} sigma {run(*sigs(th))[0].mean():+.3f}" for th in (3.5, 4.5, 5.0)))
dd = pd.Series(r, T[kk].normalize()).groupby(level=0).sum(); print(f"  best days out: top 1% removed {dd[dd < dd.quantile(.99)].sum()/len(r):+.3f}R/trade, top 5% removed {dd[dd < dd.quantile(.95)].sum()/len(r):+.3f}R/trade")
