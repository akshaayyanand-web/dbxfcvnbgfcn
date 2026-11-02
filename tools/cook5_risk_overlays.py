# Portfolio risk upgrades for the 8 EAs: volatility targeting and per-strategy equity-curve filters.
import sys, numpy as np, pandas as pd
SP = sys.argv[1]
exec(open(SP + "/speed8.py").read().split("V2 = [")[0])
from multiprocessing import Pool
dayidx = pd.DatetimeIndex(days); udays = dayidx.unique(); dpos = udays.get_indexer(dayidx)
contrib = R * W[:, None]; clo = LO * W[:, None]
port_d = pd.Series(contrib.sum(0)).groupby(dpos).sum().to_numpy()                       # portfolio daily return
strat_d = np.vstack([pd.Series(contrib[k]).groupby(dpos).sum().to_numpy() for k in range(len(names))])
cutd = np.searchsorted(udays, split)
def vt_mult(n, lo_c, hi_c):
    v = pd.Series(port_d).rolling(n, min_periods=n // 2).std().shift(1).to_numpy()      # known before the day starts
    target = np.nanmedian(v[:cutd])                                                       # target picked on 2020-22
    return np.clip(target / v, lo_c, hi_c)
def ec_mult(n, scale):
    s = pd.DataFrame(strat_d.T).rolling(n, min_periods=n // 2).sum().shift(1).to_numpy().T
    return np.where(np.nan_to_num(s, nan=1.0) < 0, scale, 1.0)                            # strategy-by-day multiplier
def series(kind, a, b, c):
    if kind == "base": return contrib.sum(0), clo.sum(0)
    if kind == "vt": m = vt_mult(a, b, c)[dpos]; return contrib.sum(0) * m, clo.sum(0) * m
    m = ec_mult(a, b)[:, dpos]; return (contrib * m).sum(0), (clo * m).sum(0)
def run4(r_all, lo_all, h0, h1, target, halt=0.8, maxl=0.10, daily=0.05):
    r = r_all[h0:h1]; lo = lo_all[h0:h1]; eq = 1.0; day = None; hd = None
    for i in range(len(r)):
        dd_ = days[h0 + i]
        if dd_ != day: day = dd_; dopen = eq
        if hd == dd_: continue
        if eq * (1 + lo[i]) <= 1 - maxl or eq * (1 + lo[i]) <= dopen * (1 - daily): return "fail", i, eq - 1
        eq *= 1 + r[i]
        if target and eq >= 1 + target: return "pass", i, eq - 1
        if 1 - eq / dopen >= halt * daily: hd = dd_
        if eq <= 1 - 0.8 * maxl: return "stopped", i, eq - 1
    return "open", len(r), eq - 1
wst = pd.date_range("2020-04-01", "2025-10-01", freq="MS", tz="UTC")
def job(v):
    lab, kind, a, b, c = v; r_all, lo_all = series(kind, a, b, c); res = []
    for s_ in est:
        h0 = idx.searchsorted(s_); x, i1, _ = run4(r_all, lo_all, h0, len(idx), 0.10)
        if x != "pass": res.append((s_, x, None)); continue
        y, i2, _ = run4(r_all, lo_all, h0 + i1 + 1, len(idx), 0.05); res.append((s_, y, (i1 + i2) / 24 if y == "pass" else None))
    yy = [(s_, *run4(r_all, lo_all, idx.searchsorted(s_), idx.searchsorted(s_ + pd.DateOffset(years=1)), None)) for s_ in wst]
    eqc = np.cumprod(1 + r_all); out = dict(variant=lab)
    for p, sel, rng in (("A", lambda s: s < split, slice(0, idx.searchsorted(split))), ("B", lambda s: s >= split, slice(idx.searchsorted(split), None))):
        rr = [q for q in res if sel(q[0])]; t = [q[2] for q in rr if q[2] is not None]; y = [q for q in yy if sel(q[0])]
        e = eqc[rng] / eqc[rng][0]
        out |= {f"{p}_pass": 100 * np.mean([q[1] == "pass" for q in rr]), f"{p}_breach": 100 * np.mean([q[1] == "fail" for q in rr]), f"{p}_days": np.median(t),
                f"{p}_fund": 100 * np.median([q[3] for q in y]), f"{p}_fbr": sum(q[1] == "fail" for q in y), f"{p}_maxDD": 100 * np.max(1 - e / np.maximum.accumulate(e))}
    return out
V = [("8 EAs as now", "base", 0, 0, 0)]
V += [(f"vol target {n}d, x{lo_c}-{hi_c}", "vt", n, lo_c, hi_c) for n in (20, 60) for lo_c, hi_c in ((0.5, 1.5), (0.75, 1.25), (0.5, 1.0))]
V += [(f"equity-curve filter {n}d -> x{sc}", "ec", n, sc, 0) for n in (30, 60, 90) for sc in (0.0, 0.5)]
with Pool(3) as p: out = p.map(job, V)
pd.set_option("display.width", 250); print(pd.DataFrame(out).round(1).to_string(index=False))
