# Anti-cheat battery ("The Claude Trading Lab", ch. 5) on the 6 add-on candidates.
# Tests: crazy-future (look-ahead), random entry (same count, same exits), double costs, one-bar delay, nearby settings, best days out.
import sys, numpy as np, pandas as pd
from multiprocessing import Pool
exec(open("transfer.py").read().split("JOBS = ")[0])
COST.update(NQ=.00015, SPX=.00015, BTC=.0009, XAU=.00012)
RNG = np.random.default_rng(11)
def dip_core(b, sym, rsi_th=15, stopx=2.0, hold_h=96, bh=1, costm=1.0, delay=0, rand=None, fix_lookahead=False):
    O, H, L, C = (b[c].to_numpy() for c in "ohlc"); T = b.index; A = atr(b); E = ema(C, 200)
    dc = pd.Series(C, T).resample("1D").last().dropna()
    ok30 = (dc >= 0.92 * dc.shift(30))
    if fix_lookahead: ok30 = ok30.shift(1)                       # use yesterday's completed daily close only
    crash = ok30.reindex(T, method="ffill").fillna(False).to_numpy().astype(bool)
    dl = np.diff(C, prepend=np.nan); up = pd.Series(np.where(dl > 0, dl, 0)).ewm(alpha=.5, adjust=False).mean(); dn = pd.Series(np.where(dl < 0, -dl, 0)).ewm(alpha=.5, adjust=False).mean()
    rsi2 = (100 - 100 / (1 + up / dn.replace(0, np.nan))).to_numpy(); sig = (rsi2 < rsi_th) & (C > E) & crash
    if rand is not None:
        p = sig[250:].mean(); sig = rand.random(len(C)) < p
    hold = int(hold_h / bh); out = []; busy = -1
    for k in range(250, len(C) - 2 - delay):
        if k <= busy or not sig[k]: continue
        e = O[k + 1 + delay]; stop = C[k] - stopx * A[k]; risk = e - stop
        if risk <= 3 * COST[sym] * e: continue
        x, q = walk(O, H, L, C, k + 1 + delay, min(k + 1 + delay + hold, len(C)), 1, e, stop, None)
        out.append((T[k], T[q], (x - e - costm * COST[sym] * e - SWAP.get(sym, .05) / 365 * (q - k) * bh / 24 * e) / risk)); busy = q
    return out
def orb_core(b, sym, home, n=30, tgt=2.0, costm=1.0, delay=0, rand=None):
    mins, day = session(b, home); O, H, L, C = (b[c].to_numpy() for c in "ohlc"); T = b.index; out = []
    for d_ in np.unique(day):
        ix = np.where(day == d_)[0]; m = mins[ix]; rng = ix[(m >= 0) & (m < n)]
        if len(rng) < n // 5 * 0.6: continue
        hi, lo = H[rng].max(), L[rng].min(); win = ix[(m >= n) & (m < n + 120)]; ek = ix[m < 385]
        if not len(ek) or not len(win): continue
        endk = ek[-1]
        if rand is not None:
            if rand.random() > 0.93: continue
            k = rand.choice(win); dr = 1 if rand.random() < 0.5 else -1
            cand = [(k, dr)]
        else:
            cand = []
            for k in win:
                dr = 1 if C[k] > hi else (-1 if C[k] < lo else 0)
                if dr: cand = [(k, dr)]; break
        for k, dr in cand:
            if k + 1 + delay > endk: continue
            e = O[k + 1 + delay]; stop = lo if dr > 0 else hi; risk = dr * (e - stop)
            if risk <= 3 * COST[sym] * e: continue
            x, q = walk(O, H, L, C, k + 1 + delay, endk + 1, dr, e, stop, e + dr * tgt * risk); out.append((T[k], T[q], (dr * (x - e) - costm * COST[sym] * e) / risk))
    return out
def crazy(b, cut):
    b2 = b.copy(); m = b2.index >= cut; n = m.sum(); base = b2.c[~m].iloc[-1]
    path = base * np.exp(np.cumsum(RNG.normal(0, 0.03, n)) + RNG.choice([0, 0.2, -0.2], n, p=[.9, .05, .05]))
    b2.loc[m, "o"] = path; b2.loc[m, "c"] = path * np.exp(RNG.normal(0, .01, n)); b2.loc[m, "h"] = np.maximum(b2.o[m], b2.c[m]) * 1.02; b2.loc[m, "l"] = np.minimum(b2.o[m], b2.c[m]) * 0.98
    return b2
def same_before(t1, t2, cut):
    a = [(x[0], x[1], round(x[2], 9)) for x in t1 if x[1] < cut]; b = [(x[0], x[1], round(x[2], 9)) for x in t2 if x[1] < cut]; return a == b
def summ(tr):
    if not tr: return np.nan, np.nan, 0
    r = np.array([x[2] for x in tr]); return r.mean(), r.mean() / r.std(ddof=1) * np.sqrt(len(r)), len(r)
def drop_best(tr, frac):
    D = pd.DataFrame(tr, columns=["t", "tx", "R"]); d = D.groupby(D.t.dt.date).R.sum(); cut = d.quantile(1 - frac); return d[d < cut].sum() / len(D)
CANDS = {"Dip 1h BTC": ("dip", "BTC", "1h", 1), "Dip 4h gold": ("dip", "XAU", "4h", 4), "Dip 1h NQ": ("dip", "NQ", "1h", 1), "ORB-30 NQ": ("orb", "NQ", None, None)}
def battery(name):
    kind, sym, rule, bh = CANDS[name]; rows = []
    b = K.rs(m5(sym), rule).dropna() if kind == "dip" else m5(sym)
    f = (lambda bb, **kw: dip_core(bb, sym, bh=bh, **kw)) if kind == "dip" else (lambda bb, **kw: orb_core(bb, sym, "NY", **kw))
    base = f(b); m0, t0, n0 = summ(base); R0 = n0 * m0
    leak = []
    for cut in pd.date_range("2021-03-01", "2025-09-01", periods=5, tz="UTC"):
        leak.append(same_before(base, f(crazy(b, cut)), cut))
    rows.append(dict(candidate=name, test="1 crazy future (5 cut dates)", result="CLEAN" if all(leak) else f"LEAK at {sum(not x for x in leak)} of 5 cuts"))
    if kind == "dip":
        fixed = f(b, fix_lookahead=True); mf, tf_, nf = summ(fixed); rows.append(dict(candidate=name, test="   after fixing the daily-close leak", result=f"{nf} trades, avg {mf:+.3f}R (t {tf_:.2f})"))
        base, m0, t0 = fixed, mf, tf_; kw0 = dict(fix_lookahead=True)
    else: kw0 = {}
    rand = [summ(f(b, rand=np.random.default_rng(s), **kw0))[0] for s in range(40)]
    rows.append(dict(candidate=name, test="2 random entry (40 runs)", result=f"strategy {m0:+.3f}R vs random mean {np.nanmean(rand):+.3f}R; beats {100*np.mean(np.array(rand) < m0):.0f}% of random runs"))
    md, td, _ = summ(f(b, costm=2.0, **kw0)); rows.append(dict(candidate=name, test="3 double costs", result=f"{md:+.3f}R (t {td:.2f})"))
    my, ty, _ = summ(f(b, delay=1, **kw0)); rows.append(dict(candidate=name, test="5 enter one bar later", result=f"{my:+.3f}R (t {ty:.2f})"))
    near = []
    if kind == "dip":
        for kw in (dict(rsi_th=10), dict(rsi_th=20), dict(stopx=1.5), dict(stopx=2.5), dict(hold_h=72), dict(hold_h=120)): near.append((str(kw), summ(f(b, **kw, **kw0))[0]))
    else:
        for kw in (dict(n=25), dict(n=35), dict(tgt=1.5), dict(tgt=2.5)): near.append((str(kw), summ(f(b, **kw))[0]))
    rows.append(dict(candidate=name, test="6 nearby settings", result="; ".join(f"{k} {v:+.3f}" for k, v in near)))
    rows.append(dict(candidate=name, test="7 best days out", result=f"top 1% of days removed: {drop_best(base, .01):+.3f}R/trade; top 5%: {drop_best(base, .05):+.3f}R/trade"))
    print(pd.DataFrame(rows).to_string(index=False), flush=True); return rows
if __name__ == "__main__":
    with Pool(4) as p: res = p.map(battery, list(CANDS))
    R = pd.DataFrame([r for o in res for r in o]); R.to_csv("anticheat.csv", index=False)
