# Topstep $50K Combine simulation: intraday futures strategies, integer micro contracts, trailing MLL, consistency rule.
import sys, numpy as np, pandas as pd, itertools
SP = sys.argv[1]
import portfolio_prop as P
REC = []; _orig = P.trade_series
def _rec(trades, cost, h1, idx_):
    REC.append((list(trades), cost)); return _orig(trades, cost, h1, idx_)
P.trade_series = _rec
exec(open(SP + "/speed8.py").read().split("V2 = [")[0])
P.trade_series = _orig
TR = {k: REC[i] for i, k in enumerate(names[:12])}
import orb_lab as O
spx5 = O.five_min(load_csv(SP + "/fut1m/USA500IDXUSD_1m.csv"))
es_orb = [t[:5] for t in O.orb(spx5, "America/New_York", (9, 30), (11, 30), (15, 55), 30, "other", 3.0, True, 0.0001)]
es_orb60L = [t[:5] for t in O.orb(spx5, "America/New_York", (9, 30), (13, 0), (15, 55), 60, "mid", None, False, 0.0001)]
nq_orb3R = [t[:5] for t in O.orb(nq5, "America/New_York", (9, 30), (13, 0), (15, 55), 15, "other", 3.0, True, 0.00012)]
nq_orbC = [t[:5] for t in O.orb(nq5, "America/New_York", (9, 30), (13, 0), (15, 55), 15, "mid", None, True, 0.00012)]
MULT = {"NQ": 2.0, "GC": 10.0, "ES": 5.0}          # MNQ $2/pt, MGC $10/$1, MES $5/pt
FEE = 1.6                                           # $ per micro contract round trip (commission + exchange fees, approx.)
SRC = {"nq_orb": (TR["orb15"][0], "NQ"), "nq_mom": (TR["nqmom"][0], "NQ"), "gold_mom": (TR["gmom"][0], "GC"),
       "gold_asia": (TR["gasia"][0], "GC"), "es_orb": (es_orb, "ES"), "es_orb60L": (es_orb60L, "ES"), "nq_orb3R": (nq_orb3R, "NQ"), "nq_orbC": (nq_orbC, "NQ")}
ALL = []
for k, (trs, mk) in SRC.items():
    for et, xt, e, st, px in trs:
        if e == st: continue
        ALL.append((pd.Timestamp(et), pd.Timestamp(xt), k, mk, e, st, px))
ALL.sort(key=lambda t: t[0])
T = pd.DataFrame(ALL, columns=["et", "xt", "strat", "mk", "e", "st", "px"])
T = T[(T.et >= pd.Timestamp("2020-04-01", tz="UTC")) & (T.et < pd.Timestamp("2026-10-30", tz="UTC"))].reset_index(drop=True)
# Topstep trading day: 17:00 CT to 17:00 CT
ct = T.et.dt.tz_convert("America/Chicago"); T["day"] = (ct + pd.Timedelta(hours=7)).dt.date
print("trades per strategy:", T.strat.value_counts().to_dict(), flush=True)
TE, TX, TS, TM = T.et.values, T.xt.values, T.strat.values, T.mk.values
E, S, X, D = T.e.values, T.st.values, T.px.values, T.day.values
def combine(start_i, risk, strats, day_stop=None, target=3000.0, mll=2000.0, cons=0.5, max_days=400, start_bal=50000.0):
    bal = start_bal; eod_high = start_bal; floor = start_bal - mll; day = None; day_pnl = 0.0; days = 0; best_day = 0.0
    open_tr = []   # (exit_time, max_loss)
    for i in range(start_i, len(TE)):
        if TS[i] not in strats: continue
        if D[i] != day:
            if day is not None:                      # close the previous trading day
                best_day = max(best_day, day_pnl)
                eod_high = max(eod_high, bal); floor = min(start_bal, eod_high - mll)
                profit = bal - start_bal
                if profit >= target and best_day <= cons * profit: return "pass", days, i
                days += 1
                if days > max_days: return "open", days, i
            day = D[i]; day_pnl = 0.0
        if day_stop is not None and day_pnl <= -day_stop: continue
        r = risk[TS[i]]; dist = abs(E[i] - S[i]) * MULT[TM[i]]
        n = int(r // dist)
        if n == 0:
            if dist <= 1.5 * r: n = 1
            else: continue
        d = 1 if S[i] < E[i] else -1
        open_tr = [o for o in open_tr if o[0] > TE[i]]
        worst = bal - sum(o[1] for o in open_tr) - n * dist - n * FEE
        if worst <= floor: return "fail", days, i
        pnl = n * MULT[TM[i]] * d * (X[i] - E[i]) - n * FEE
        open_tr.append((TX[i], n * dist))
        bal += pnl; day_pnl += pnl
        if bal <= floor: return "fail", days, i
    return "open", days, i

from multiprocessing import Pool
import itertools
day_list = sorted(set(D)); day_pos = {d: k for k, d in enumerate(day_list)}
starts = pd.date_range("2020-04-01", "2025-09-01", freq="7D", tz="UTC"); split = pd.Timestamp("2023-01-01", tz="UTC")
sidx = [int(np.searchsorted(TE, np.datetime64(x.tz_convert(None)))) for x in starts]
def run_cfg(cfg):
    st, base = cfg; risk = {k: base for k in SRC}; out = []
    for i0 in sidx:
        i, resets, t0 = i0, 0, day_pos[D[i0]]
        while True:
            r, days, iend = combine(i, risk, set(st), None, max_days=260)
            if r == "pass": out.append((day_pos[D[min(iend, len(D) - 1)]] - t0, resets)); break
            if r != "fail" or iend + 1 >= len(D) or resets > 30: out.append((None, resets)); break
            resets += 1; i = iend + 1
            while i < len(D) and D[i] == D[iend]: i += 1
    o = dict(set=" + ".join(st), risk=base)
    for p, sel in (("A", [x < split for x in starts]), ("B", [x >= split for x in starts])):
        oo = [q for q, k in zip(out, sel) if k]; t = np.array([q[0] for q in oo if q[0] is not None]); rs = np.array([q[1] for q in oo if q[0] is not None]); n = len(oo)
        o |= {f"{p}_1m": 100 * np.sum(t <= 21) / n, f"{p}_2m": 100 * np.sum(t <= 42) / n, f"{p}_3m": 100 * np.sum(t <= 63) / n,
              f"{p}_days": np.median(t), f"{p}_resets": rs.mean(), f"{p}_first_try": 100 * np.sum(rs == 0) / n}
    return o
pool = ["nq_orb", "nq_orb3R", "nq_orbC", "es_orb", "es_orb60L", "gold_mom", "gold_asia", "nq_mom"]
cfgs = []
for k in (1, 2, 3, 4):
    for st in itertools.combinations(pool, k):
        if sum(x.startswith("nq_orb") for x in st) > 1 or sum(x.startswith("es_orb") for x in st) > 1: continue   # one version per market
        for base in (300, 400, 500):
            cfgs.append((st, base))
print(len(cfgs), "configs", flush=True)
with Pool(4) as p: res = p.map(run_cfg, cfgs)
df = pd.DataFrame(res); df.to_pickle(SP + "/topstep_cook.pkl")
pd.set_option("display.width", 260); pd.set_option("display.max_rows", 100)
df["scoreA"] = df.A_2m - 8 * df.A_resets
print("Top 15 picked on 2020-22 (score = funded within 2 months minus 8 x average resets), with 2023-25:")
print(df.sort_values("scoreA", ascending=False).head(15).round(1).to_string(index=False))
print("\nCurrent fast plan:"); print(df[(df.set == "nq_orb + es_orb + gold_mom") & (df.risk == 400)].round(1).to_string(index=False))
