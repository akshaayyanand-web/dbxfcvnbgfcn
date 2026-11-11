# Run from the scratchpad (needs topstep_sim.py chain). LucidDaily prices: $90 first attempt, $120 per retry.
# Topstep / Lucid $50K: fastest way to get funded with real edges. Chance of passing within 5 / 10 trading days per attempt,
# and the cost and time to a funded account including resets.
import sys, numpy as np, pandas as pd, itertools
sys.argv = ["x", "."]
TSRC = open("topstep_sim.py").read()
exec(TSRC.split("ALL = []")[0].replace('return "pass", days', 'return "pass", days, i').replace('return "fail", days', 'return "fail", days, i').replace('return "open", days', 'return "open", days, i'))
src2 = open("lowtf_port.py").read(); exec("def bars1" + src2.split("def bars1", 1)[1].split("def cands")[0])
from portfolio_prop import rma
def bo(path, tf, N, en, sm):
    b = bars1(path, tf); c = b.c; C = c.to_numpy(); a = rma(pd.concat([b.h - b.l, (b.h - c.shift()).abs(), (b.l - c.shift()).abs()], axis=1).max(axis=1), 14).to_numpy()
    ny = b.index.tz_convert("America/New_York"); m = ny.hour * 60 + ny.minute; w = (m >= 570) & (m < 720)
    hi = b.h.rolling(N).max().shift(1).to_numpy(); lo = b.l.rolling(N).min().shift(1).to_numpy(); e = c.ewm(span=en, adjust=False).mean().to_numpy()
    return simT(b, w & (C > hi) & (C > e), w & (C < lo) & (C < e), sm * a, 10 ** 6, m >= 950)
SRC["nq_bo15"] = (bo("fut1m/USATECHIDXUSD_1m.csv", "15min", 20, 200, 1.0), "NQ")
SRC["nq_bo5"] = (bo("fut1m/USATECHIDXUSD_1m.csv", "5min", 50, 800, 2.0), "NQ")
SRC["es_bo5"] = (bo("fut1m/USA500IDXUSD_1m.csv", "5min", 50, 200, 2.0), "ES")
exec(("ALL = []" + TSRC.split("ALL = []")[1].split("starts = pd.date_range")[0]).replace('return "pass", days', 'return "pass", days, i').replace('return "fail", days', 'return "fail", days, i').replace('return "open", days', 'return "open", days, i'))
days_all = sorted(set(D)); dpos = {d: k for k, d in enumerate(days_all)}
first_i = {}
for i, d in enumerate(D): first_i.setdefault(d, i)
SETS = {"current 4 scripts": ("nq_orb", "nq_mom", "gold_mom", "es_orb"), "NQ ORB + ES ORB + Gold mom": ("nq_orb", "es_orb", "gold_mom")}
rows = []
for (sn, st), base in itertools.product(SETS.items(), (150, 200, 250, 300, 400, 500)):
    risk = {k: base for k in SRC}; st = set(st)
    one = []
    for d in days_all[:-15]:
        if pd.Timestamp(d) < pd.Timestamp("2020-04-01") or pd.Timestamp(d) > pd.Timestamp("2025-10-01"): continue
        r, days, iend = combine(first_i[d], risk, st, None, max_days=400); one.append((r, days))
    passers = [dd for r, dd in one if r == "pass"]
    tt, cc = [], []
    for d in days_all[:-15:3]:
        if pd.Timestamp(d) < pd.Timestamp("2020-04-01") or pd.Timestamp(d) > pd.Timestamp("2025-10-01"): continue
        i, res, t0 = first_i[d], 0, dpos[d]
        while res < 60:
            r, days, iend = combine(i, risk, st, None, max_days=400)
            if r == "pass": tt.append(dpos[D[min(iend, len(D) - 1)]] - t0); cc.append(90 + 120 * res); break
            if r != "fail": tt.append(np.nan); cc.append(90 + 120 * res); break
            res += 1; i = iend + 1
            while i < len(D) and D[i] == D[iend]: i += 1
    tt = np.array(tt, float)
    rows.append(dict(setup=sn, risk_per_trade=base, one_account_pass_pct=100 * len(passers) / len(one), one_account_median_days=np.median(passers),
                     with_resets_80pct_funded_by_day=np.nanpercentile(tt, 80), with_resets_median_days=np.nanmedian(tt), avg_cost_usd=np.mean(cc), cost_80th_pct=np.percentile(cc, 80)))
pd.set_option("display.width", 250); print(pd.DataFrame(rows).round(1).to_string(index=False))
