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
MULT = {"NQ": 2.0, "GC": 10.0, "ES": 5.0}          # MNQ $2/pt, MGC $10/$1, MES $5/pt
FEE = 1.6                                           # $ per micro contract round trip (commission + exchange fees, approx.)
SRC = {"nq_orb": (TR["orb15"][0], "NQ"), "nq_mom": (TR["nqmom"][0], "NQ"), "gold_mom": (TR["gmom"][0], "GC"),
       "gold_asia": (TR["gasia"][0], "GC"), "es_orb": (es_orb, "ES")}
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
                if profit >= target and best_day <= cons * profit: return "pass", days
                days += 1
                if days > max_days: return "open", days
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
        if worst <= floor: return "fail", days
        pnl = n * MULT[TM[i]] * d * (X[i] - E[i]) - n * FEE
        open_tr.append((TX[i], n * dist))
        bal += pnl; day_pnl += pnl
        if bal <= floor: return "fail", days
    return "open", days
starts = pd.date_range("2020-04-01", "2025-09-01", freq="7D", tz="UTC"); split = pd.Timestamp("2023-01-01", tz="UTC")
sidx = [int(np.searchsorted(TE, np.datetime64(s.tz_convert(None)))) for s in starts]
SETS = {"NQ ORB + NQ mom + Gold mom + Gold Asia": ("nq_orb", "nq_mom", "gold_mom", "gold_asia"),
        "4 above + ES ORB": ("nq_orb", "nq_mom", "gold_mom", "gold_asia", "es_orb"),
        "NQ ORB + Gold mom + ES ORB": ("nq_orb", "gold_mom", "es_orb"),
        "NQ ORB only": ("nq_orb",)}
rows = []
for (sn, st), base, ds in itertools.product(SETS.items(), (100, 150, 200, 250, 300, 400), (None, 600)):
    risk = {k: base for k in SRC}
    res = [combine(i, risk, set(st), ds) for i in sidx]
    for part, sel in (("A 2020-22", [s < split for s in starts]), ("B 2023-25", [s >= split for s in starts])):
        rr = [r for r, k in zip(res, sel) if k]; t = np.array([d for r, d in rr if r == "pass"])
        rows.append(dict(set=sn, risk_per_trade=base, day_stop=ds or "none", part=part, pass_=100 * np.mean([r == "pass" for r, _ in rr]),
                         fail=100 * np.mean([r == "fail" for r, _ in rr]), med_days=np.median(t) if len(t) else np.nan,
                         le20=100 * np.sum(t <= 20) / len(rr), le40=100 * np.sum(t <= 40) / len(rr)))
df = pd.DataFrame(rows); df.to_pickle(SP + "/topstep_sim.pkl")
pv = df.pivot_table(index=["set", "risk_per_trade", "day_stop"], columns="part", values=["pass_", "fail", "med_days", "le40"]).round(0)
pv.columns = [f"{a}_{b[:1]}" for a, b in pv.columns]
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 100)
print(pv.sort_values("pass__A", ascending=False).to_string())
