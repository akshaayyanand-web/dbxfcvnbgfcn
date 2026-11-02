# New candidates vs the 8-EA portfolio. Standalone (1% risk) by halves, then portfolio add-on at 0.25 / 0.5.
import sys, numpy as np, pandas as pd
SP = sys.argv[1]
exec(open(SP + "/speed8.py").read().split("V2 = [")[0])
from multiprocessing import Pool
R0, LO0 = R.copy(), LO.copy()
from portfolio_prop import rma
CAND = {}
spx = load_csv(SP + "/fut/USA500IDXUSD.csv"); slv = load_csv(SP + "/fut/XAGUSD.csv"); oil = load_csv(SP + "/fut/LIGHTCMDUSD.csv")
eth = load(SP + "/kh/ETHUSDT.csv").loc["2019-06-01":]
MK = {"gold": (gold, 0.0001, False), "silver": (slv, 0.00025, False), "nq": (nq, 0.00012, False), "spx": (spx, 0.0001, False),
      "oil": (oil, 0.0003, False), "btc": (btc, 0.0012, True), "eth": (eth, 0.0012, True)}
def daily_frame(df, crypto):
    """daily bars + the hourly position of each day's last bar (NY 16:00 close for markets, UTC midnight for crypto)"""
    loc = df.index.tz_convert("UTC" if crypto else "America/New_York")
    key = pd.Index(loc.date) if crypto else pd.Index((loc - pd.Timedelta(hours=16)).date)   # NY trading day ends 16:00
    pos = pd.Series(np.arange(len(df)), index=key)
    g = pd.DataFrame({"h": df.h.to_numpy(), "l": df.l.to_numpy(), "c": df.c.to_numpy(), "p": np.arange(len(df))}, index=key).groupby(level=0)
    D = pd.DataFrame({"h": g.h.max(), "l": g.l.min(), "c": g.c.last(), "first": g.p.first(), "last": g.p.last()})
    D = D[g.p.count() >= (20 if crypto else 15)]
    pc = D.c.shift(); D["atr"] = rma(pd.concat([D.h - D.l, (D.h - pc).abs(), (D.l - pc).abs()], axis=1).max(axis=1), 20)
    return D
def walk(df, entries, cost):
    """entries: list of (hourly index to enter at open, dir, stop, exit_fn(k)->bool checked on each hourly close, trailing fn or None)"""
    O_, H, L, C, T = (df[k].to_numpy() for k in "ohlc") + (df.index,) if False else (df.o.to_numpy(), df.h.to_numpy(), df.l.to_numpy(), df.c.to_numpy(), df.index)
    out = []; busy = -1
    for a, d, st, ex, trail in entries:
        if a <= busy or a >= len(C) - 1: continue
        e = O_[a]
        if d * (e - st) <= 0: continue
        st0 = st; k = a; px = None
        while k < len(C) - 1:
            if (L[k] <= st) if d == 1 else (H[k] >= st): px, xt = (min(O_[k], st) if d == 1 else max(O_[k], st)), T[k] + pd.Timedelta(hours=1); break
            if ex(k): px, xt = O_[k + 1], T[k + 1]; k += 1; break
            if trail is not None: st = trail(k, st)
            k += 1
        if px is None: break
        busy = k
        if xt - T[a] <= pd.Timedelta(days=60): out.append((T[a], xt, e, st0, px))
    return out
for nm, (df, c, crypto) in MK.items():
    D = daily_frame(df, crypto); last = D["last"].to_numpy(); first = D["first"].to_numpy(); Dh, Dl, Dc, atr = D.h.to_numpy(), D.l.to_numpy(), D.c.to_numpy(), D.atr.to_numpy()
    lastset = {p: j for j, p in enumerate(last)}
    # 1) Donchian trend following: 20-day breakout on the daily close, exit on a 10-day opposite close or 2 ATR stop
    for N, M in ((20, 10), (55, 20)):
        hi = pd.Series(Dh).rolling(N).max().shift(1).to_numpy(); lo_ = pd.Series(Dl).rolling(N).min().shift(1).to_numpy()
        xl = pd.Series(Dl).rolling(M).min().to_numpy(); xh = pd.Series(Dh).rolling(M).max().to_numpy()
        ent = []
        for j in range(N + 1, len(D) - 1):
            if np.isnan(atr[j]): continue
            d = 1 if Dc[j] > hi[j] else (-1 if Dc[j] < lo_[j] else 0)
            if d == 0: continue
            def ex(k, d=d):
                jj = lastset.get(k)
                return jj is not None and ((d == 1 and Dc[jj] < xl[jj - 1]) or (d == -1 and Dc[jj] > xh[jj - 1]))
            ent.append((last[j] + 1, d, Dc[j] - d * 2 * atr[j], ex, None))
        CAND[f"{nm} trend {N}/{M}d"] = P.trade_series(walk(df, ent, c), c, df, idx)
    # 2) volatility breakout: enter when price moves 0.5 x yesterday's range from today's first bar open; flat at day end; stop = today's open
    ent = []
    O_ = df.o.to_numpy()
    for j in range(2, len(D)):
        rng = Dh[j - 1] - Dl[j - 1]; f0, l0 = int(first[j]), int(last[j]); op = O_[f0]
        for k in range(f0, l0):
            d = 1 if df.h.iat[k] >= op + 0.5 * rng else (-1 if df.l.iat[k] <= op - 0.5 * rng else 0)
            if d != 0 and k + 1 <= l0:
                ent.append((k + 1, d, op, (lambda k, l0=l0: k >= l0 - 1), None)); break
    CAND[f"{nm} vol-breakout"] = P.trade_series(walk(df, ent, c), c, df, idx)
    # 3) NR7: narrowest range of 7 days -> next day trade the break of that day's high/low, flat at day end, stop other side
    rngs = Dh - Dl; ent = []
    for j in range(7, len(D) - 1):
        if rngs[j] > np.min(rngs[j - 6:j + 1]) or rngs[j] <= 0: continue
        f0, l0 = int(first[j + 1]), int(last[j + 1])
        for k in range(f0, l0):
            d = 1 if df.h.iat[k] > Dh[j] else (-1 if df.l.iat[k] < Dl[j] else 0)
            if d != 0 and k + 1 <= l0:
                ent.append((k + 1, d, Dl[j] if d == 1 else Dh[j], (lambda k, l0=l0: k >= l0 - 1), None)); break
    CAND[f"{nm} NR7 breakout"] = P.trade_series(walk(df, ent, c), c, df, idx)
    print(nm, "built", flush=True)
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
