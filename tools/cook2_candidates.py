# New candidates vs the 8-EA portfolio. Standalone (1% risk) by halves, then portfolio add-on at 0.25 / 0.5.
import sys, numpy as np, pandas as pd
SP = sys.argv[1]
exec(open(SP + "/speed8.py").read().split("V2 = [")[0])
from multiprocessing import Pool
R0, LO0 = R.copy(), LO.copy()
import orb_lab as O
from portfolio_prop import rsi, rma
CAND = {}
def daily_rsi2(df, buy, exit_, maxdays, stop_atr, cost, tz="America/New_York"):
    loc = df.index.tz_convert(tz); O_, H, L, C, T = tuple(df[k].to_numpy() for k in "ohlc") + (df.index,)
    pos = np.flatnonzero(loc.hour == 15); D = pd.Series(C[pos], index=df.index[pos])
    nd = pd.Index(loc.date); gh = pd.Series(H, index=nd).groupby(level=0).max(); gl = pd.Series(L, index=nd).groupby(level=0).min()
    dd = pd.Index(loc[pos].date); dh, dl = gh.reindex(dd).to_numpy(), gl.reindex(dd).to_numpy()
    prev = np.r_[np.nan, D.to_numpy()[:-1]]
    tr = np.maximum(dh - dl, np.maximum(np.abs(dh - prev), np.abs(dl - prev))); atr = rma(pd.Series(tr), 14).to_numpy()
    r2 = rsi(D, 2).to_numpy(); s200 = D.rolling(200).mean().to_numpy(); s5 = D.rolling(5).mean().to_numpy(); Dv = D.to_numpy()
    out = []; j = 200
    while j < len(pos) - 1:
        if not (r2[j] < buy and Dv[j] > s200[j]) or np.isnan(atr[j]): j += 1; continue
        a = pos[j] + 1; e = O_[a]; st = Dv[j] - stop_atr * atr[j]
        if e <= st: j += 1; continue
        k, j2, px = a, j, None
        while k < len(C) - 1:
            if L[k] <= st: px, xt = min(O_[k], st), T[k] + pd.Timedelta(hours=1); break
            if j2 + 1 < len(pos) and k == pos[j2 + 1]:
                j2 += 1
                if (exit_ == "sma5" and Dv[j2] > s5[j2]) or (exit_ == "up" and Dv[j2] > Dv[j2 - 1]) or j2 - j >= maxdays:
                    px, xt = O_[k + 1], T[k + 1]; break
            k += 1
        if px is None: break
        if xt - T[a] <= pd.Timedelta(days=12): out.append((T[a], xt, e, st, px))
        j = max(j2, j + 1)
    return out
mk = {"spx": ("fut/USA500IDXUSD.csv", 0.0001), "nq": ("fut/USATECHIDXUSD.csv", 0.00012), "dow": ("fut/USA30IDXUSD.csv", 0.00012), "rut": ("fut/USSC2000IDXUSD.csv", 0.0002)}
HD = {k: load_csv(SP + "/" + f) for k, (f, c) in mk.items()}
for k, (f, c) in mk.items():
    for buy, ex, md in ((10, "sma5", 5), (5, "sma5", 5), (10, "up", 5)):
        tr = daily_rsi2(HD[k], buy, ex, md, 3.0, c); CAND[f"{k}_rsi2d b{buy} {ex}"] = P.trade_series(tr, c, HD[k], idx)
g5 = O.five_min(load_csv(SP + "/fut1m/XAUUSD_1m.csv"))
for nm, tz, st_, le, fl in (("NY930", "America/New_York", (9, 30), (11, 30), (15, 55)), ("NY820", "America/New_York", (8, 20), (10, 30), (15, 55)), ("LDN8", "Europe/London", (8, 0), (10, 0), (16, 0))):
    for mins in (15, 30):
        x = O.orb(g5, tz, st_, le, fl, mins, "other", 2.0, True, O.COST["XAUUSD"]); CAND[f"gold_orb {nm} {mins}m"] = P.trade_series([t[:5] for t in x], O.COST["XAUUSD"], gold, idx)
def gap_fade(df5, lo_g, hi_g, flat=(11, 30), cost=0.00012):
    loc = df5.index.tz_convert("America/New_York"); m = loc.hour * 60 + loc.minute; day = pd.Index(loc.date)
    O_, H, L, C, T = tuple(df5[k].to_numpy() for k in "ohlc") + (df5.index,); out = []; prev_close = None
    for d, ix in pd.Series(np.arange(len(df5)), index=day).groupby(level=0):
        ix = ix.to_numpy(); mm = m[ix]
        op = ix[mm == 570]; cl = ix[mm == 955]; fx = ix[mm >= flat[0] * 60 + flat[1]]
        if len(op) and prev_close is not None and len(fx):
            a = op[0]; e = O_[a]; g = e / prev_close - 1
            if lo_g <= abs(g) <= hi_g:
                dr = -1 if g > 0 else 1; tg = prev_close; st = e - dr * abs(e - prev_close); px = None
                for k in range(a, fx[0] + 1):
                    if (L[k] <= st if dr == 1 else H[k] >= st): px, xt = st, T[k] + pd.Timedelta(minutes=5); break
                    if (H[k] >= tg if dr == 1 else L[k] <= tg): px, xt = tg, T[k] + pd.Timedelta(minutes=5); break
                    if k == fx[0]: px, xt = O_[k], T[k]
                if px is not None: out.append((T[a], xt, e, st, px))
        prev_close = C[cl[0]] if len(cl) else None
    return out
for lo_g, hi_g in ((0.001, 0.004), (0.002, 0.006), (0.003, 0.01)):
    CAND[f"nq_gapfade {lo_g}-{hi_g}"] = P.trade_series(gap_fade(nq5, lo_g, hi_g), 0.00012, nq, idx)
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
