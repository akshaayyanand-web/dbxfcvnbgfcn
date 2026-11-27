# Cross-asset and unusual-calendar round. Rules fixed before running. Stops = 1.5 ATR14 of the traded bars unless noted; R per trade after costs (+swap).
#  X1 BTC weekend -> NQ   : BTC return Fri 16:00 NY -> NQ's Sunday reopen; |ret| > 2% -> trade NQ that way from the reopen, hold 22 h (to Monday's US session)
#  X1b                    : same, every weekend (no threshold)
#  X2 BTC overnight -> NQ : BTC return 16:00 -> 09:30 NY, z (60 days) > 1.5 -> NQ at 09:30 that way, hold 60 min
#  X3 Hong Kong -> DAX    : Hang Seng session return (09:30-16:00 HK), z (60 days) > 1.5 -> DAX at 09:00 Frankfurt that way, hold 60 min / hold to 17:25
#  X4 oil -> CAD          : Brent 1h return z (500 h) > 2.5 -> USDCAD opposite way next hour (oil up = CAD up), hold 4 h
#  X5 VIX9D / VIX > 1.10  : short-term panic -> buy S&P at the close, hold 5 days, stop 2 daily ATR (CBOE closes; signal day known at 16:15 NY)
#  X6 lunar (Dichev-Janes): long S&P / Nasdaq / BTC / gold from 3.5 days before to 3.5 days after each new moon; X6c control = same around full moon
# Baselines: random direction at the same times (X1-X4); random start days with the same hold (X5, X6). Train < 2023, holdout 2023+.
import numpy as np, pandas as pd, sys
exec(open("transfer.py").read().split("JOBS = ")[0])
COST.update(NQ=.00015, SPX=.00015, DAX=.00015, XAU=.00012, BTC=.0009, USDCAD=.00009)
SWAP.update(USDCAD=.02)
S = pd.Timestamp("2023-01-01", tz="UTC"); RNG = np.random.default_rng(5)
tt = lambda v: round(v.mean() / v.std(ddof=1) * np.sqrt(len(v)), 2) if len(v) > 2 else np.nan
def sim(b, ev, sym, stopx=1.5, A=None, bar_h=1.0, cm=1.0):
    O, H, L, C = (b[c].to_numpy() for c in "ohlc"); T = b.index; A = atr(b) if A is None else A; out = []; busy = -1
    for k, d, hold in ev:
        if k <= busy or k + 1 + hold >= len(C) or not np.isfinite(A[k]) or A[k] <= 0: continue
        e = O[k + 1]; risk = stopx * A[k]; x, q = walk(O, H, L, C, k + 1, k + 1 + hold, d, e, e - d * risk, None)
        out.append((T[k], (d * (x - e) - cm * COST[sym] * e - SWAP.get(sym, .05) / 365 * (q - k) * bar_h / 24 * e) / risk)); busy = q
    return out
def report(name, tr, base):
    D = pd.DataFrame(tr, columns=["t", "R"])
    if len(D) < 20: return dict(test=name, trades=len(D))
    a, h = D[D.t < S].R, D[D.t >= S].R; y = D.groupby(D.t.dt.year).R.sum()
    r = dict(test=name, trades=len(D), win=round(100 * (D.R > 0).mean()), avgR=round(D.R.mean(), 3), t_train=tt(a), avgR_hold=round(h.mean(), 3), t_hold=tt(h),
             baseline=round(np.nanmean(base), 3), beats_base=round(100 * np.mean(np.array(base) < D.R.mean())), pos_years=f"{(y > 0).sum()}/{len(y)}")
    print(r, flush=True); return r
def rand_dir(ev, s): g = np.random.default_rng(s); return [(k, 1 if g.random() < .5 else -1, h) for k, d, h in ev]
rows = []
# ---- X1 / X1b
nq = K.rs(m5("NQ"), "1h").dropna(); btc = K.rs(m5("BTC"), "1h").dropna(); bc = btc.c
ny = nq.index.tz_convert("America/New_York"); gap = np.r_[np.inf, (nq.index[1:] - nq.index[:-1]).total_seconds().to_numpy() / 3600]
reopen = np.where((gap > 30) & (ny.dayofweek == 6))[0]
for nm, thr in (("X1 BTC weekend >2% -> NQ from Sunday reopen, 22h", .02), ("X1b BTC weekend (all) -> NQ, 22h", 0.0)):
    ev = []
    for k in reopen:
        t = nq.index[k]; fri = (t.tz_convert("America/New_York").normalize() - pd.Timedelta(days=2) + pd.Timedelta(hours=16)).tz_convert("UTC")
        p0 = bc.asof(fri); p1 = bc.asof(t)
        if np.isfinite(p0) and np.isfinite(p1) and abs(p1 / p0 - 1) > thr: ev.append((k - 1, 1 if p1 > p0 else -1, 22))   # k-1 -> entry at the reopen bar's open
    tr = sim(nq, ev, "NQ"); rows.append(report(nm, tr, [np.mean([x[1] for x in sim(nq, rand_dir(ev, s), "NQ")]) for s in range(40)]))
# ---- X2
n5 = m5("NQ"); mins, day = session(n5, "NY"); A5 = pd.Series(atr(K.rs(n5, "1h").dropna()), K.rs(n5, "1h").dropna().index).shift(1).reindex(n5.index, method="ffill").to_numpy()
b5 = m5("BTC").c; ev = []; vals = []
for k in np.where(mins == 0)[0]:
    t = n5.index[k]; t0 = (t.tz_convert("America/New_York").normalize() - pd.Timedelta(hours=8)).tz_convert("UTC")
    p0, p1 = b5.asof(t0), b5.asof(t - pd.Timedelta(minutes=1))
    if not (np.isfinite(p0) and np.isfinite(p1)): continue
    r_ = np.log(p1 / p0); hist = vals[-60:]; vals.append(r_)
    if len(hist) >= 40 and abs(r_) > 1.5 * np.std(hist): ev.append((k - 1, 1 if r_ > 0 else -1, 12))
tr = sim(n5, ev, "NQ", A=A5, bar_h=1 / 12); rows.append(report("X2 BTC overnight z>1.5 -> NQ 09:30, 60 min", tr, [np.mean([x[1] for x in sim(n5, rand_dir(ev, s), "NQ", A=A5, bar_h=1 / 12)]) for s in range(40)]))
# ---- X3
hk = K.rs(K.hd("HKXHKD"), "5min"); hl = hk.index.tz_convert("Asia/Hong_Kong"); hm = hl.hour * 60 + hl.minute
hkd = pd.DataFrame({"o": np.where(hm == 570, hk.o, np.nan), "c": np.where(hm == 955, hk.c, np.nan)}, index=hl.normalize()).groupby(level=0).agg({"o": "first", "c": "last"}).dropna()
hkr = np.log(hkd.c / hkd.o); hz = (hkr / hkr.rolling(60, min_periods=40).std().shift(1)); hz.index = hz.index.date
dx = m5("DAX"); dm, dd = session(dx, "FRA"); A_d = pd.Series(atr(K.rs(dx, "1h").dropna()), K.rs(dx, "1h").dropna().index).shift(1).reindex(dx.index, method="ffill").to_numpy()
dl = dx.index.tz_convert("Europe/Berlin")
for nm, hold in (("X3 Hong Kong z>1.5 -> DAX 09:00, 60 min", 12), ("X3b Hong Kong z>1.5 -> DAX 09:00 to 17:25", 101)):
    ev = []
    for k in np.where(dm == 0)[0]:
        z_ = hz.get(dl[k].date(), np.nan)
        if np.isfinite(z_) and abs(z_) > 1.5: ev.append((k - 1, 1 if z_ > 0 else -1, hold))
    tr = sim(dx, ev, "DAX", A=A_d, bar_h=1 / 12); rows.append(report(nm, tr, [np.mean([x[1] for x in sim(dx, rand_dir(ev, s), "DAX", A=A_d, bar_h=1 / 12)]) for s in range(40)]))
# ---- X4
bco = K.rs(K.hd("BCOUSD"), "1h").dropna(); cad = K.rs(K.hd("USDCAD"), "1h").dropna()
br = np.log(bco.c).diff(); bz = (br / br.rolling(500, min_periods=250).std().shift(1)).reindex(cad.index)
ev = [(k, -1 if bz.iloc[k] > 0 else 1, 4) for k in np.where(np.abs(bz.to_numpy()) > 2.5)[0]]
tr = sim(cad, ev, "USDCAD"); rows.append(report("X4 Brent 1h z>2.5 -> USDCAD opposite, 4h", tr, [np.mean([x[1] for x in sim(cad, rand_dir(ev, s), "USDCAD")]) for s in range(40)]))
# ---- daily bars for X5 / X6 (close = last bar before 16:00 NY for indices; 00:00 UTC for BTC; 17:00 NY for gold)
def daily(sym):
    b = K.rs(m5(sym), "1h").dropna(); lt = b.index.tz_convert("America/New_York") if sym != "BTC" else b.index.tz_convert("UTC")
    key = lt.normalize() if sym in ("SPX", "NQ", "BTC") else (lt + pd.Timedelta(hours=7)).normalize()
    if sym in ("SPX", "NQ"): b = b[(lt.hour >= 9) & (lt.hour < 16)]; key = key[(lt.hour >= 9) & (lt.hour < 16)]
    d = b.groupby(key.date).agg({"o": "first", "h": "max", "l": "min", "c": "last"}); d.index = pd.DatetimeIndex(d.index).tz_localize("UTC") + pd.Timedelta(hours=21); return d
def vix(n): v = pd.read_csv(f"rdata/cboe/{n}.csv"); v.index = pd.DatetimeIndex(pd.to_datetime(v.DATE, format="%m/%d/%Y")).tz_localize("UTC") + pd.Timedelta(hours=21); return v.CLOSE
spx = daily("SPX"); ratio = (vix("VIX9D") / vix("VIX")).reindex(spx.index).to_numpy()
ev = [(k - 1, 1, 5) for k in np.where(ratio > 1.10)[0] if k >= 1]                        # k-1 -> entry at the next bar's open ~ the signal day's close
ev = [(k, 1, 5) for k, _, _ in [(k + 1 - 1, 1, 5) for k, _, _ in ev]]
evs = [(k, 1, 5) for k in np.where(ratio > 1.10)[0]]
def rand_days(n, N, hold, s): g = np.random.default_rng(s); return [(int(k), 1, hold) for k in np.sort(g.choice(np.arange(20, N - hold - 2), n, replace=False))]
tr = sim(spx, evs, "SPX", stopx=2.0, bar_h=24); rows.append(report("X5 VIX9D/VIX > 1.10 -> buy S&P, hold 5 days", tr, [np.mean([x[1] for x in sim(spx, rand_days(len(evs), len(spx), 5, s), "SPX", stopx=2.0, bar_h=24)]) for s in range(40)]))
# ---- X6 lunar
def moon_age(idx): return ((idx - pd.Timestamp("2000-01-06 18:14", tz="UTC")).total_seconds() / 86400) % 29.530588853
for sym in ("SPX", "NQ", "BTC", "XAU"):
    d = daily(sym); age = moon_age(d.index)
    for nm, centre in (("X6 lunar: long around NEW moon", 0.0), ("X6c control: long around FULL moon", 14.765)):
        dist = np.minimum(np.abs(age - centre), 29.530588853 - np.abs(age - centre)); inwin = dist <= 3.5
        starts = np.where(inwin & ~np.r_[False, inwin[:-1]])[0]; ev = []
        for k in starts:
            j = k
            while j + 1 < len(d) and inwin[j + 1]: j += 1
            ev.append((k - 1, 1, j - k + 1))
        tr = sim(d, ev, sym, stopx=3.0, bar_h=24)
        rows.append(report(f"{nm} ({sym})", tr, [np.mean([x[1] for x in sim(d, rand_days(len(ev), len(d), 7, s), sym, stopx=3.0, bar_h=24)]) for s in range(40)]))
R = pd.DataFrame(rows); pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 60); print(R.to_string(index=False)); R.to_csv("xa.csv", index=False)
R["ok"] = (R.t_train >= 2) & (R.t_hold >= 1.5) & (R.beats_base >= 95); print("\nSURVIVORS:", R[R.ok].test.tolist() if R.ok.any() else "none")
