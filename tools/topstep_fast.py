import sys, numpy as np, pandas as pd
SP = sys.argv[1]
src = open(SP + "/topstep_sim.py").read().split("starts = pd.date_range")[0]
src = src.replace('return "pass", days', 'return "pass", days, i').replace('return "fail", days', 'return "fail", days, i').replace('return "open", days', 'return "open", days, i')
exec(src)
# trading-day index of each trade (all strategies) to measure calendar trading days
day_list = sorted(set(D)); day_pos = {d: k for k, d in enumerate(day_list)}
starts = pd.date_range("2020-04-01", "2025-09-01", freq="7D", tz="UTC")
sidx = [int(np.searchsorted(TE, np.datetime64(s.tz_convert(None)))) for s in starts]
SETS = {"NQ ORB only": ("nq_orb",), "NQ ORB + Gold mom + ES ORB": ("nq_orb", "gold_mom", "es_orb"),
        "All 4 intraday + ES ORB": ("nq_orb", "nq_mom", "gold_mom", "gold_asia", "es_orb")}
rows = []
for sn, st in SETS.items():
    for base in (150, 200, 250, 300, 400, 500):
        risk = {k: base for k in SRC}; out = []
        for i0 in sidx:
            i, resets, t0 = i0, 0, day_pos[D[i0]]
            while True:
                r, days, iend = combine(i, risk, set(st), None, max_days=260)
                if r == "pass": out.append((day_pos[D[min(iend, len(D) - 1)]] - t0, resets)); break
                if r != "fail" or iend + 1 >= len(D) or resets > 30: out.append((None, resets)); break
                resets += 1; i = iend + 1
                while i < len(D) and D[i] == D[iend]: i += 1          # restart the next trading day
        t = np.array([o[0] for o in out if o[0] is not None]); rs = np.array([o[1] for o in out if o[0] is not None])
        n = len(out)
        rows.append(dict(set=sn, risk_per_trade=base, first_try_pass=None, funded_within_1m=100 * np.sum(t <= 21) / n, within_2m=100 * np.sum(t <= 42) / n,
                         within_3m=100 * np.sum(t <= 63) / n, median_trading_days=np.median(t), median_resets=np.median(rs), avg_resets=rs.mean()))
pd.set_option("display.width", 220); print(pd.DataFrame(rows).drop(columns="first_try_pass").round(1).to_string(index=False))
