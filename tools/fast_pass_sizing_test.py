# Run from the scratchpad (needs topstep_sim.py chain).
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
def combine2(start_i, strats, target, mll, start_bal, mode, k, max_days=400, cons=0.5):
    """mode 'fixed': risk k dollars per trade. mode 'cushion': risk k x (balance - max-loss line) per trade."""
    bal = start_bal; eod_high = start_bal; floor = start_bal - mll; day = None; day_pnl = 0.0; days = 0; best_day = 0.0; open_tr = []
    for i in range(start_i, len(TE)):
        if TS[i] not in strats: continue
        if D[i] != day:
            if day is not None:
                best_day = max(best_day, day_pnl); eod_high = max(eod_high, bal); floor = min(start_bal, eod_high - mll)
                profit = bal - start_bal
                if profit >= target and best_day <= cons * profit: return "pass", days
                days += 1
                if days > max_days: return "open", days
            day = D[i]; day_pnl = 0.0
        r = k if mode == "fixed" else k * (bal - floor)
        dist = abs(E[i] - S[i]) * MULT[TM[i]]; n = int(r // dist)
        if n == 0:
            if dist <= 1.5 * r: n = 1
            else: continue
        d = 1 if S[i] < E[i] else -1
        open_tr = [o for o in open_tr if o[0] > TE[i]]
        if bal - sum(o[1] for o in open_tr) - n * dist - n * FEE <= floor: return "fail", days
        pnl = n * MULT[TM[i]] * d * (X[i] - E[i]) - n * FEE; open_tr.append((TX[i], n * dist)); bal += pnl; day_pnl += pnl
        if bal <= floor: return "fail", days
    return "open", days
ST = set(("nq_orb", "nq_mom", "gold_mom", "es_orb")); ST3 = set(("nq_orb", "es_orb", "gold_mom"))
ACC = {"50K ($3,000 / $2,000)": (3000, 2000, 50000), "25K ($1,250 / $1,000)": (1250, 1000, 25000), "25K ($1,500 / $1,000)": (1500, 1000, 25000)}
rows = []
for (an, (tg, ml, sb)), (sn, st), (mode, ks) in itertools.product(ACC.items(), (("4 scripts", ST), ("3 scripts", ST3)),
        (("fixed", (0.075, 0.1, 0.15, 0.2)), ("cushion", (0.1, 0.15, 0.2, 0.3)))):
    for k in ks:
        kk = k * ml if mode == "fixed" else k
        one = []
        for d in days_all[:-15:2]:
            if pd.Timestamp(d) < pd.Timestamp("2020-04-01") or pd.Timestamp(d) > pd.Timestamp("2025-10-01"): continue
            one.append(combine2(first_i[d], st, tg, ml, sb, mode, kk))
        pas = [dd for r, dd in one if r == "pass"]
        rows.append(dict(account=an, scripts=sn, sizing=(f"${kk:.0f}/trade" if mode == "fixed" else f"{k:.0%} of room"), pass_one_try=100 * len(pas) / len(one),
                         within_10d=100 * sum(dd <= 10 for dd in pas) / len(one), within_20d=100 * sum(dd <= 20 for dd in pas) / len(one), median_days=np.median(pas) if pas else np.nan))
df = pd.DataFrame(rows); pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
print(df.round(1).to_string(index=False)); df.to_pickle("fastpass.pkl")
