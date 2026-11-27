# Replications of QuantLab's two survivors (rules fixed before running).
# NOISE BAND (Zarattini, Aziz & Barbon 2024): sigma(t, m) = mean over the previous 14 sessions of |close(m)/open - 1| at minute m of the session.
#   UB = max(open, prev close) * (1 + k*sigma), LB = min(open, prev close) * (1 - k*sigma). Checks every 30 min from open+30:
#   flat & close > UB -> long; close < LB -> short. In a trade: exit at a check if close < max(UB, VWAP) (long) / > min(LB, VWAP) (short),
#   hard stop one band width (k*sigma*open) from entry, flat 5 min before the session close. 1R = the hard-stop distance. k in {1, 2}.
# SESSION OPEN MOMENTUM (NQ): first 5-min candle 09:30-09:35 NY; trade its direction at 09:35; stop = the candle's other extreme
#   (x1 or x2 the range); exit after 6 h or at 15:55. Costs 0.015% of price round trip. Train < 2023, holdout 2023+.
import numpy as np, pandas as pd
from multiprocessing import Pool
def m1(path):
    d = pd.read_csv(path, index_col=0); d.index = pd.to_datetime(d.index, utc=True); d = d[~d.index.duplicated()].sort_index()
    d = d.iloc[:, :5]; d.columns = ["o", "h", "l", "c", "v"]; return d
SRC = {"NQ": ("fut1m/USATECHIDXUSD_1m.csv", "America/New_York", 570, 960), "SPX": ("fut1m/USA500IDXUSD_1m.csv", "America/New_York", 570, 960),
       "DAX": ("eu1m/DEUIDXEUR_1m.csv", "Europe/Berlin", 540, 1050)}
COST = 0.00015
def sessions(sym):
    path, tz, o_, c_ = SRC[sym]; d = m1(path); d.index = d.index.tz_convert(tz); d = d[d.index.dayofweek < 5]
    mn = d.index.hour * 60 + d.index.minute; d = d[(mn >= o_) & (mn < c_)]; d["m"] = (d.index.hour * 60 + d.index.minute) - o_
    out = {}
    for day, x in d.groupby(d.index.normalize()):
        if len(x) > 0.8 * (c_ - o_) and x.m.iloc[0] <= 2: out[day] = x
    return out, c_ - o_
def noise_band(args):
    sym, k = args; S, L = sessions(sym); days = sorted(S); res = []; prev_close = None; hist = []
    for day in days:
        x = S[day]; m = x.m.to_numpy(); o = x.o.to_numpy(); h = x.h.to_numpy(); l = x.l.to_numpy(); c = x.c.to_numpy(); v = x.v.to_numpy()
        op = o[0]; mv = np.full(L, np.nan); mv[m] = np.abs(c / op - 1)
        if len(hist) >= 14 and prev_close is not None:
            sig = np.nanmean(np.vstack(hist[-14:]), axis=0); ub = max(op, prev_close) * (1 + k * sig); lb = min(op, prev_close) * (1 - k * sig)
            tp = (h + l + c) / 3; w = np.where(v > 0, v, 1.0); vwap = np.cumsum(tp * w) / np.cumsum(w)
            pos = 0; e = stop = risk = None
            for i in range(len(c)):
                mi = m[i]
                if pos:
                    if (pos > 0 and l[i] <= stop) or (pos < 0 and h[i] >= stop):
                        res.append((day, (pos * (stop - e) - COST * e) / risk)); pos = 0; continue
                    if mi >= L - 5:
                        res.append((day, (pos * (c[i] - e) - COST * e) / risk)); pos = 0; break
                    if mi >= 30 and mi % 30 == 29:
                        b = max(ub[mi], vwap[i]) if pos > 0 else min(lb[mi], vwap[i])
                        if (pos > 0 and c[i] < b) or (pos < 0 and c[i] > b): res.append((day, (pos * (c[i] - e) - COST * e) / risk)); pos = 0
                    continue
                if mi >= 30 and mi % 30 == 29 and mi < L - 35 and i + 1 < len(c) and np.isfinite(ub[mi]):
                    d = 1 if c[i] > ub[mi] else (-1 if c[i] < lb[mi] else 0)
                    if d:
                        e = o[i + 1]; risk = k * sig[mi] * op if np.isfinite(sig[mi]) else None
                        if risk and risk > 3 * COST * e: pos = d; stop = e - d * risk
        hist.append(mv); prev_close = c[-1]
    return ("NoiseBand", sym, f"k={k}", res)
def som(args):
    sym, sx, ex = args; S, L = sessions(sym); res = []
    for day, x in S.items():
        m = x.m.to_numpy(); o = x.o.to_numpy(); h = x.h.to_numpy(); l = x.l.to_numpy(); c = x.c.to_numpy()
        f = np.where(m < 5)[0]
        if len(f) < 4: continue
        fo, fc, fh, fl = o[f[0]], c[f[-1]], h[f].max(), l[f].min(); d = 1 if fc > fo else (-1 if fc < fo else 0)
        if not d: continue
        i0 = f[-1] + 1; e = o[i0]; risk = sx * (fh - fl)
        if risk <= 3 * COST * e: continue
        stop = e - d * risk; endm = 5 + 360 if ex == "6h" else L - 5; xp = None
        for i in range(i0, len(c)):
            if (d > 0 and l[i] <= stop) or (d < 0 and h[i] >= stop): xp = min(o[i], stop) if d > 0 else max(o[i], stop); break
            if m[i] >= endm: xp = c[i]; break
        if xp is None: xp = c[-1]
        res.append((day, (d * (xp - e) - COST * e) / risk))
    return ("SessionOpenMom", sym, f"stop {sx}x candle, exit {ex}", res)
if __name__ == "__main__":
    jobs = [(noise_band, (s, k)) for s in ("NQ", "SPX", "DAX") for k in (1.0, 2.0)] + [(som, (s, sx, ex)) for s in ("NQ", "SPX") for sx in (1.0, 2.0) for ex in ("6h", "close")]

    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(4) as ex_: futs = [ex_.submit(f, a) for f, a in jobs]; out = [fu.result() for fu in futs]
    rows = []; keep = {}
    for name, sym, var, res in out:
        D = pd.DataFrame(res, columns=["day", "R"]); D["day"] = pd.to_datetime(D.day).dt.tz_localize(None); keep[(name, sym, var)] = D
        tt = lambda v: round(v.mean() / v.std(ddof=1) * np.sqrt(len(v)), 2) if len(v) > 2 else np.nan
        A, B = D[D.day < "2023-01-01"].R, D[D.day >= "2023-01-01"].R; yrs = D.groupby(D.day.dt.year).R.sum(); span = max((D.day.max() - D.day.min()).days / 365, 1)
        rows.append(dict(system=name, market=sym, variant=var, trades=len(D), per_week=round(len(D) / span / 52, 1), win=round(100 * (D.R > 0).mean()),
                         pf=round(D.R[D.R > 0].sum() / -D.R[D.R < 0].sum(), 2), R_yr=round(D.R.sum() / span, 1), avgR_train=round(A.mean(), 3), t_train=tt(A),
                         avgR_hold=round(B.mean(), 3), t_hold=tt(B), pos_years=f"{(yrs > 0).sum()}/{len(yrs)}", by_year=" ".join(f"{y % 100}:{v:+.0f}" for y, v in yrs.items())))
    R = pd.DataFrame(rows); R.to_csv("ql.csv", index=False); pd.to_pickle(keep, "ql_trades.pkl"); pd.set_option("display.width", 260); pd.set_option("display.max_colwidth", 70)
    print(R.to_string(index=False))
