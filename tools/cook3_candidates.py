# New candidates vs the 8-EA portfolio. Standalone (1% risk) by halves, then portfolio add-on at 0.25 / 0.5.
import sys, numpy as np, pandas as pd
SP = sys.argv[1]
exec(open(SP + "/speed8.py").read().split("V2 = [")[0])
from multiprocessing import Pool
R0, LO0 = R.copy(), LO.copy()
from portfolio_prop import resample, rsi, rma
CAND = {}
def dip2(raw1h, tf, rl, thr, crash_pct, d, hold_h=96):
    """d=+1: buy RSI<thr above EMA50 (skip after a >crash% 30-day drop). d=-1: mirror: short RSI>100-thr below EMA50 (skip after a >crash% 30-day rise)."""
    b = resample(raw1h, tf) if tf != "1h" else raw1h; c = b.c
    dd = raw1h.c.resample("1D").last().dropna(); ch = (dd / dd.shift(30) - 1)
    block = ((ch < -crash_pct) if d == 1 else (ch > crash_pct)).shift(1).reindex(b.index.floor("D")).fillna(False).to_numpy().astype(bool)
    rs = rsi(c, rl); ema = c.ewm(span=50, adjust=False).mean()
    sig = (((rs < thr) & (c > ema)) if d == 1 else ((rs > 100 - thr) & (c < ema))).to_numpy() & ~block
    tr = pd.concat([b.h - b.l, (b.h - c.shift()).abs(), (b.l - c.shift()).abs()], axis=1).max(axis=1); atr = rma(tr, 14).to_numpy()
    O_, H, L, C, T = b.o.to_numpy(), b.h.to_numpy(), b.l.to_numpy(), c.to_numpy(), b.index
    bar = T[1] - T[0]; mb = int(pd.Timedelta(f"{hold_h}h") / bar); out, i = [], 0
    while i < len(C) - 2:
        if not sig[i] or np.isnan(atr[i]): i += 1; continue
        j = i + 1; e, st = O_[j], C[i] - d * 2 * atr[i]
        if d * (e - st) <= 0: i += 1; continue
        k, px = j, None
        while k < len(C) - 1:
            if (L[k] <= st) if d == 1 else (H[k] >= st): px, xt = (min(O_[k], st) if d == 1 else max(O_[k], st)), T[k] + bar; break
            if k - j + 1 >= mb: px, xt = O_[k + 1], T[k + 1]; k += 1; break
            k += 1
        if px is None: break
        if xt - T[j] <= pd.Timedelta(days=10): out.append((T[j], xt, e, st, px))
        i = k
    return out
spx = load_csv(SP + "/fut/USA500IDXUSD.csv"); dow = load_csv(SP + "/fut/USA30IDXUSD.csv"); rut = load_csv(SP + "/fut/USSC2000IDXUSD.csv")
slv = load_csv(SP + "/fut/XAGUSD.csv"); oil = load_csv(SP + "/fut/LIGHTCMDUSD.csv")
eth = load(SP + "/kh/ETHUSDT.csv").loc["2019-06-01":]; sol = load(SP + "/kh/SOLUSDT.csv")
M = {"btc": (btc, P.FEE_CRYPTO, 0.15), "eth": (eth, P.FEE_CRYPTO, 0.15), "sol": (sol, P.FEE_CRYPTO, 0.2), "gold": (gold, 0.0001, 0.08), "nq": (nq, 0.00012, 0.08),
     "spx": (spx, 0.0001, 0.08), "dow": (dow, 0.00012, 0.08), "rut": (rut, 0.0002, 0.1), "silver": (slv, 0.00025, 0.12), "oil": (oil, 0.0003, 0.15)}
# 1) short mirror (rally fade in downtrends) on the main markets
for k in ("btc", "gold", "nq", "spx"):
    raw, c, cr = M[k]
    for tf, rl, thr in (("2h", 3, 20), ("1h", 2, 10)):
        CAND[f"{k} SHORT rally-fade {tf} rsi{rl}>{100-thr}"] = P.trade_series(dip2(raw, tf, rl, thr, cr, -1), c, raw, idx)
# 2) the proven long dip rules on new markets
for k in ("eth", "sol", "spx", "nq", "dow", "rut", "silver", "oil"):
    raw, c, cr = M[k]
    for tf, rl, thr in (("2h", 3, 20), ("1h", 2, 10)):
        CAND[f"{k} long dip {tf} rsi{rl}<{thr}"] = P.trade_series(dip2(raw, tf, rl, thr, cr, 1), c, raw, idx)
yrs = (idx[-1] - idx[0]).days / 365.25; cut = idx.searchsorted(split); f = cut / len(idx)
d = pd.DataFrame({k: v[0] for k, v in CAND.items()} | {k: R0[names.index(k)] for k in names}, index=idx).resample("1D").sum(); d = d[d.abs().sum(axis=1) > 0]
rows = []
for k, (r, lo) in CAND.items():
    eq = np.cumsum(r); rows.append(dict(cand=k, yr=100 * r.sum() / yrs, yr_2020_22=100 * r[:cut].sum() / (f * yrs), yr_2023_26=100 * r[cut:].sum() / ((1 - f) * yrs),
                                        maxdd=100 * np.max(np.maximum.accumulate(eq) - eq), max_corr=d.corr().loc[k, names].abs().max()))
st = pd.DataFrame(rows); pd.set_option("display.width", 250); print("STANDALONE at 1% risk:"); print(st.round(2).to_string(index=False), flush=True)
good = st[(st.yr_2020_22 > 0) & (st.yr_2023_26 > 0)].cand.tolist()
def run3(w, Rm, LOm, h0, h1, target, halt=0.8, maxl=0.10, daily=0.05):
    r = (Rm[:, h0:h1] * w[:, None]).sum(0); lo = (LOm[:, h0:h1] * w[:, None]).sum(0); eq = 1.0; day = None; hd = None
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
    k, wt = v
    if k is None: Rm, LOm, w = R0, LO0, W
    else: Rm = np.vstack([R0, CAND[k][0]]); LOm = np.vstack([LO0, CAND[k][1]]); w = np.append(W, wt)
    res = []
    for s_ in est:
        h0 = idx.searchsorted(s_); a, i1, _ = run3(w, Rm, LOm, h0, len(idx), 0.10)
        if a != "pass": res.append((s_, a, None)); continue
        b, i2, _ = run3(w, Rm, LOm, h0 + i1 + 1, len(idx), 0.05); res.append((s_, b, (i1 + i2) / 24 if b == "pass" else None))
    yrs_ = [(s_, *run3(w, Rm, LOm, idx.searchsorted(s_), idx.searchsorted(s_ + pd.DateOffset(years=1)), None)) for s_ in wst]
    out = dict(add=k or "8 EAs (current)", weight=wt)
    for p, sel in (("A", lambda s: s < split), ("B", lambda s: s >= split)):
        rr = [x for x in res if sel(x[0])]; t = [x[2] for x in rr if x[2] is not None]; yy = [y for y in yrs_ if sel(y[0])]
        out |= {f"{p}_pass": 100 * np.mean([x[1] == "pass" for x in rr]), f"{p}_breach": 100 * np.mean([x[1] == "fail" for x in rr]), f"{p}_days": np.median(t),
                f"{p}_fund": 100 * np.median([y[3] for y in yy]), f"{p}_fbr": sum(y[1] == "fail" for y in yy)}
    return out
jobs = [(None, 0)] + [(k, wt) for k in good for wt in (0.25, 0.5)]
print(f"\nportfolio tests for {good}", flush=True)
with Pool(3) as p: out = p.map(job, jobs)
print(pd.DataFrame(out).round(1).to_string(index=False))
