# Scalp search: 3 entry signals x spread 0.5/1 x market or limit(-1pt) entry x TP 3/6/10 x SL 3/6/10/20, fair (stop first) and best-case (target first) on 1m NQ 2020-2026.
import sys, numpy as np, pandas as pd
sys.path.insert(0, "/home/user/dbxfcvnbgfcn/tools")
from portfolio_prop import load_csv
m1 = load_csv("fut1m/USATECHIDXUSD_1m.csv").loc["2020-01-01":]
O, H, L, C, T = m1.o.to_numpy(), m1.h.to_numpy(), m1.l.to_numpy(), m1.c.to_numpy(), m1.index
ny = T.tz_convert("America/New_York"); mins = (ny.hour * 60 + ny.minute).to_numpy(); day = ny.normalize()
ema = pd.Series(C).ewm(span=200, adjust=False).mean().to_numpy()
hi20 = pd.Series(H).rolling(20).max().shift(1).to_numpy(); lo20 = pd.Series(L).rolling(20).min().shift(1).to_numpy()
mom5 = C - np.roll(C, 5)
# entry signals: (index of the bar to enter on, direction)
S = {}
orb = pd.read_pickle("ea_trades.pkl")["NQ_Opening_Range"][0]
S["ORB direction"] = [(T.searchsorted(et), 1 if e > st else -1) for et, xt, e, st, px in orb if et >= T[0]]
def spaced(mask_long, mask_short, gap=15):
    out, last = [], -10**9
    for i in np.where(mask_long | mask_short)[0]:
        if i - last >= gap and i + 1 < len(O): out.append((i + 1, 1 if mask_long[i] else -1)); last = i
    return out
win = (mins >= 575) & (mins < 690)
S["1m breakout of 20-min high/low + EMA200"] = spaced(win & (C > hi20) & (C > ema), win & (C < lo20) & (C < ema))
big = pd.Series(np.abs(mom5)).rolling(390).quantile(0.9).to_numpy()
S["strong 5-min thrust (top 10%)"] = spaced(win & (mom5 > big), win & (mom5 < -big))
def run(entries, tp, sl, spread, limit_off, optimistic):
    out, when = [], []
    for i, d in entries:
        if limit_off > 0:   # limit order limit_off points better than the next open, valid 5 minutes; no spread paid on entry
            lim = O[i] - d * limit_off; f = None
            for j in range(i, min(i + 5, len(O))):
                if (L[j] <= lim) if d == 1 else (H[j] >= lim): f = j; break
            if f is None: continue
            e, i0, cost_in = lim, f, 0.0
        else: e, i0, cost_in = O[i] + d * spread / 2, i, 0.0
        res = None
        for j in range(i0, min(i0 + 390, len(O))):
            hs = (L[j] <= e - sl) if d == 1 else (H[j] >= e + sl); ht = (H[j] >= e + tp) if d == 1 else (L[j] <= e - tp)
            if hs and ht: res = tp if optimistic else -sl; break
            if hs: res = -sl; break
            if ht: res = tp; break
        if res is None: res = (O[min(i0 + 390, len(O) - 1)] - e) * d
        out.append(res - spread / 2 - cost_in); when.append(T[i0])
    return np.array(out), pd.DatetimeIndex(when)
rows = []
for name, ents in S.items():
    for spread in (0.5, 1.0):
        for lim in (0, 1.0):
            for tp in (3, 6, 10):
                for sl in (3, 6, 10, 20):
                    for opt in (False, True):
                        r, w = run(ents, tp, sl, spread, lim, opt)
                        if len(r) < 100: continue
                        A = w < pd.Timestamp("2023-01-01", tz="UTC")
                        rows.append(dict(signal=name, spread=spread, entry="limit -1pt" if lim else "market", tp=tp, sl=sl, case="best-case" if opt else "fair",
                                         trades=len(r), win=round(100 * (r > 0).mean(), 1), avg_pts=round(r.mean(), 2),
                                         pts_2020_22=round(r[A].mean(), 2), pts_2023_26=round(r[~A].mean(), 2), usd_50lots=round(50 * r.mean())))
df = pd.DataFrame(rows); pd.set_option("display.width", 250); pd.set_option("display.max_rows", 60)
print(f"{len(df)} versions; profitable (fair): {((df.case=='fair') & (df.avg_pts > 0)).sum()}; profitable in both halves (fair): {((df.case=='fair') & (df.pts_2020_22 > 0) & (df.pts_2023_26 > 0)).sum()}; profitable even best-case: {((df.case=='best-case') & (df.avg_pts > 0)).sum()}")
print("\nbest 12 (fair):"); print(df[df.case == "fair"].sort_values("avg_pts", ascending=False).head(12).to_string(index=False))
print("\nbest 8 (best-case):"); print(df[df.case == "best-case"].sort_values("avg_pts", ascending=False).head(8).to_string(index=False))
df.to_pickle("scalp_search.pkl")
