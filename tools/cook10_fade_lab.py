# Open Fade (S&P / Nasdaq) replica + improvement grid. 1-minute bars, New York clock.
# Base EA: signal bar 09:30-09:59; mv = close[t] - close[t-L]; |mv| >= M; EMA(800) slope over 30 bars has the same sign as mv;
# enter against the move at the next bar's open; stop = |mv|; close after H minutes; one trade per day.
# Variants (pre-registered): stop x {0.5,0.75,1,1.5}; target {none, 0.5x move, 1x move}; hold {15,30,60}; move threshold x {1,1.4,2};
# confirm (wait for a 1-minute bar closing in the fade direction, within 5 min); session-only look-back (t-L >= 09:30); EMA filter {same, off};
# skip days with an opening gap > 0.5%. Costs 0.015% of price round trip. Train 2019-2022, holdout 2023-2026, recent 2025-2026.
import numpy as np, pandas as pd, itertools
from multiprocessing import Pool
def m1(path):
    d = pd.read_csv(path, index_col=0); d.index = pd.to_datetime(d.index, utc=True); d = d[~d.index.duplicated()].sort_index().iloc[:, :4]; d.columns = list("ohlc"); return d
SYM = {"SPX": ("fut1m/USA500IDXUSD_1m.csv", 15, 25.0), "NQ": ("fut1m/USATECHIDXUSD_1m.csv", 10, 98.0)}
COST = 0.00015
DATA = {}
def prep(sym):
    d = m1(SYM[sym][0]); e = d.c.ewm(span=800, adjust=False).mean(); d["slope"] = np.sign(e - e.shift(30)); d.index = d.index.tz_convert("America/New_York")
    d = d[d.index.dayofweek < 5]; mins = d.index.hour * 60 + d.index.minute; d["m"] = mins; d["day"] = d.index.normalize()
    pc = d[(mins >= 945) & (mins < 960)].groupby("day").c.last().shift(1)          # previous 16:00 close
    op = d[mins == 570].groupby("day").o.first(); gap = (op / pc - 1)
    days = {}
    for day, x in d[(mins >= 540) & (mins < 690)].groupby("day"): days[day] = x
    return days, gap
def run_variant(args):
    sym, sx, tgt, H, mmult, confirm, sess_only, ema, gapskip = args
    days, gap = DATA[sym]; L, M = SYM[sym][1], SYM[sym][2] * mmult; out = []
    for day, x in days.items():
        if gapskip and abs(gap.get(day, 0)) > 0.005: continue
        m = x.m.to_numpy(); c = x.c.to_numpy(); o = x.o.to_numpy(); h = x.h.to_numpy(); l = x.l.to_numpy(); s = x.slope.to_numpy(); T = len(c)
        for k in range(L, T - 2):
            if m[k] < 570 or m[k] >= 600: continue
            if sess_only and m[k - L] < 570: continue
            if m[k] - m[k - L] != L: continue                                   # need L contiguous minutes
            mv = c[k] - c[k - L]
            if abs(mv) < M: continue
            sg = 1 if mv > 0 else -1
            if ema == "same" and s[k] != sg: continue
            d = -sg; j = k
            if confirm:
                j = next((q for q in range(k + 1, min(k + 6, T - 1)) if (c[q] - o[q]) * d > 0), None)
                if j is None: break
            e = o[j + 1]; stop_d = sx * abs(mv); stop = e - d * stop_d; tp = e + d * tgt * abs(mv) if tgt > 0 else None
            end = min(j + 1 + H, T - 1); xpx = c[end]; hit = "time"
            for q in range(j + 1, end + 1):
                if (d > 0 and l[q] <= stop) or (d < 0 and h[q] >= stop): xpx = min(o[q], stop) if d > 0 else max(o[q], stop); hit = "stop"; break
                if tp is not None and ((d > 0 and h[q] >= tp) or (d < 0 and l[q] <= tp)): xpx = tp; hit = "tp"; break
            out.append((day, (d * (xpx - e) - COST * e) / stop_d, hit)); break    # one trade per day
    D = pd.DataFrame(out, columns=["day", "R", "hit"])
    if len(D) < 30: return None
    tt = lambda v: round(v.mean() / v.std(ddof=1) * np.sqrt(len(v)), 2) if len(v) > 2 else np.nan
    A, B, Cr = D[D.day < "2023-01-01"].R, D[D.day >= "2023-01-01"].R, D[D.day >= "2025-01-01"].R
    yrs = D.groupby(D.day.dt.year).R.sum()
    return dict(sym=sym, stop_x=sx, target=tgt, hold=H, move_x=mmult, confirm=confirm, session_only=sess_only, ema=ema, gap_skip=gapskip, trades=len(D), per_yr=round(len(D) / 7.8, 1),
                win=round(100 * (D.R > 0).mean()), avgR=round(D.R.mean(), 3), R_yr=round(D.R.sum() / 7.8, 1), avgR_train=round(A.mean(), 3), t_train=tt(A), avgR_hold=round(B.mean(), 3), t_hold=tt(B),
                avgR_2025on=round(Cr.mean(), 3), n_2025on=len(Cr), pos_years=f"{(yrs > 0).sum()}/{len(yrs)}", worst_yr=round(yrs.min(), 1))
if __name__ == "__main__":
    for s in SYM: DATA[s] = prep(s)
    grid = list(itertools.product(SYM, (0.5, 0.75, 1.0, 1.5), (0, 0.5, 1.0), (15, 30, 60), (1.0, 1.4, 2.0), (False, True), (False, True), ("same", "off"), (False, True)))
    with Pool(4) as p: res = [r for r in p.map(run_variant, grid, chunksize=8) if r]
    R = pd.DataFrame(res); R.to_csv("fade_lab.csv", index=False); pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
    base = R[(R.stop_x == 1) & (R.target == 0) & (R.hold == 30) & (R.move_x == 1) & ~R.confirm & ~R.session_only & (R.ema == "same") & ~R.gap_skip]
    print("CURRENT EA SETTINGS (replica):"); print(base.to_string(index=False))
    print(f"\n{len(R)} variants. Pre-registered pick rule: best train t per symbol, then check holdout.")
    for s in SYM:
        r = R[R.sym == s].sort_values("t_train", ascending=False)
        print(f"\n{s}: top 12 by TRAIN t (2019-22):"); print(r.head(12).to_string(index=False))
    # same rule must work for both symbols: rank by min(train t) across symbols
    key = ["stop_x", "target", "hold", "move_x", "confirm", "session_only", "ema", "gap_skip"]
    J = R.pivot_table(index=key, columns="sym", values=["t_train", "t_hold", "avgR_train", "avgR_hold", "avgR_2025on", "R_yr", "per_yr"]); J.columns = [f"{a}_{b}" for a, b in J.columns]
    J["min_train_t"] = J[["t_train_SPX", "t_train_NQ"]].min(axis=1); J = J.sort_values("min_train_t", ascending=False)
    print("\nSAME RULE FOR BOTH (top 15 by the weaker symbol's train t):"); print(J.head(15).round(3).to_string())
