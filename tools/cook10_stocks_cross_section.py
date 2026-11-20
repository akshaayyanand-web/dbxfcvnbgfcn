# Stock round on 40 US large caps (Polygon daily, Nov 2024 - Nov 2026). Pre-registered: S1 weekly reversal (long 5 losers / short 5 winners),
# S4 non-earnings gap fade (open->close), S6 market-residual stat-arb. Costs 0.1% round trip, financing 6%/yr long, 3%/yr short.
import json, glob, os, sys, numpy as np, pandas as pd
RAW = sys.argv[1]; P = {}
for f in sorted(glob.glob(f"{RAW}/*.json")):
    t = os.path.basename(f)[:-5]
    if t == "t": continue
    r = json.load(open(f)).get("results") or []
    if len(r) > 200: d = pd.DataFrame(r); d.index = pd.DatetimeIndex(pd.to_datetime(d.t, unit="ms")).normalize(); P[t] = d
O = pd.DataFrame({t: d.o for t, d in P.items()}); C = pd.DataFrame({t: d.c for t, d in P.items()}); V = pd.DataFrame({t: d.v for t, d in P.items()})
COST, FL, FS = 0.001, 0.06 / 365, 0.03 / 365; SPLIT = pd.Timestamp("2025-11-20")
def summarize(name, rets):
    s = pd.Series(rets).dropna(); a, b = s[s.index < SPLIT], s[s.index >= SPLIT]
    t_ = lambda v: round(v.mean() / v.std(ddof=1) * np.sqrt(len(v)), 2) if len(v) > 2 and v.std() > 0 else np.nan
    return dict(test=name, periods=len(s), avg_pct=round(100 * s.mean(), 3), win=round(100 * (s > 0).mean()), t_all=t_(s), t_yr1=t_(a), t_yr2=t_(b))
rows = []
# S1: weekly, Monday close... use Monday open entry, next Monday open exit; 5-day lookback on closes up to Friday
mondays = [d for d in O.index if d.weekday() == 0]; r1 = {}
for k in range(1, len(mondays) - 1):
    m0, m1 = mondays[k], mondays[k + 1]; prev = C.index[C.index < m0]
    if len(prev) < 6: continue
    lb = C.loc[prev[-1]] / C.loc[prev[-6]] - 1; lb = lb.dropna()
    if len(lb) < 20: continue
    los, win = lb.nsmallest(5).index, lb.nlargest(5).index
    days = (m1 - m0).days
    lr = (O.loc[m1, los] / O.loc[m0, los] - 1).mean() - COST - FL * days
    sr = -(O.loc[m1, win] / O.loc[m0, win] - 1).mean() - COST - FS * days
    r1[m0] = (lr + sr) / 2
rows.append(summarize("S1 weekly reversal: long 5 losers / short 5 winners (per week)", r1))
# S4: non-earnings gap fade, open->close same day, equal-weight all signals that day
avgv = V.rolling(50).mean().shift(1); gap = O / C.shift(1) - 1; r4 = {}
for d in O.index[51:]:
    g = gap.loc[d]; ok = (g.abs() > 0.02) & (g.abs() < 0.05) & (V.loc[d] < 2 * avgv.loc[d])
    if not ok.any(): continue
    side = -np.sign(g[ok]); rr = side * (C.loc[d, ok.index[ok]] / O.loc[d, ok.index[ok]] - 1) - COST
    r4[d] = rr.mean()
rows.append(summarize("S4 non-earnings gap fade 2-5%, open->close (per day with signals)", r4))
# S6: residual vs equal-weight market, 5-day, z>2 fade, hold until z back inside 0.5 or 10 days (per-trade returns booked on entry day)
ret = np.log(C).diff(); mkt = ret.mean(axis=1); beta = ret.rolling(60).cov(mkt).div(mkt.rolling(60).var(), axis=0).shift(1)
res = ret.sub(beta.mul(mkt, axis=0)); cum5 = res.rolling(5).sum(); z = cum5 / (res.rolling(60).std().shift(1) * np.sqrt(5))
r6 = {}; trades = []
for tkr in C.columns:
    zz, busy = z[tkr], None
    for i in range(70, len(C) - 11):
        d = C.index[i]
        if busy is not None and i <= busy or not np.isfinite(zz.iloc[i]) or abs(zz.iloc[i]) <= 2: continue
        side = -np.sign(zz.iloc[i]); j = i + 1
        for j in range(i + 1, min(i + 11, len(C) - 1)):
            if abs(zz.iloc[j]) < 0.5: break
        e, x = O[tkr].iloc[i + 1], O[tkr].iloc[j + 1]
        stock = side * (x / e - 1); hedge = -side * beta[tkr].iloc[i] * (mkt.iloc[i + 1:j + 1].sum())
        days = (C.index[j + 1] - C.index[i + 1]).days
        trades.append((d, stock + hedge - 2 * COST - (FL + FS) * days)); busy = j
s6 = pd.Series({d: v for d, v in trades}).groupby(level=0).mean()
rows.append(summarize("S6 market-residual stat-arb z>2, beta-hedged (per day with entries)", s6)); rows[-1]["trades"] = len(trades)
pd.set_option("display.width", 250); out = pd.DataFrame(rows); print(out.to_string()); out.to_csv("stocks_results.csv", index=False)
