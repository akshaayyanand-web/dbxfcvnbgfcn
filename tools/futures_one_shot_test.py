# Futures evals that allow a one-day pass (50K: +3,000 target, 2,000 EOD trailing max loss): BTC/SOL dip one-shots (1.5-3R) with account resets.
import numpy as np, pandas as pd
exec(open("one_trade_test.py").read().split("rows = []")[0])
TPS = (1.5, 2.0, 3.0)   # 50K: +$3,000 target vs $2,000 (1.5R), $1,500 (2R) or $1,000 (3R) risk
ev = {k: [] for k in SETS}
for lab, (sym, pk, nm, cost) in SETS.items():
    df, TR = pd.read_pickle(pk)
    if nm is None: nm = df[df.edge.str.contains("dip")].sort_values("minhalf", ascending=False).edge.iloc[0]
    bars = h1(sym); H, L, T = bars.h.to_numpy(), bars.l.to_numpy(), bars.index
    for et, xt, e, st, px in TR[nm]:
        R = e - st; k = T.searchsorted(et); res = {}
        for tpR in TPS:
            tp = e + tpR * R + cost * e; out = (False, T[min(k + 720, len(T) - 1)])
            for j in range(k, min(k + 720, len(T))):
                if L[j] <= st: out = (False, T[j]); break
                if H[j] >= tp: out = (True, T[j]); break
            res[tpR] = out
        ev[lab].append((pd.Timestamp(et), res))
rows = []
for which in (["BTC Dip 1h"], ["SOL Dip 1h (best add-on)"], list(SETS)):
    E = sorted([x for k in which for x in ev[k]], key=lambda x: x[0]); ET = pd.DatetimeIndex([x[0] for x in E]).as_unit("ns")
    for tpR in TPS:
        D, A = [], []
        for s in pd.date_range("2020-10-01", "2026-03-01", freq="1D", tz="UTC"):
            t = s; acc = 1
            while True:
                k = ET.searchsorted(pd.Timestamp(t).as_unit("ns"))
                if k >= len(E): acc = None; break
                win, done = E[k][1][tpR]
                if win: break
                acc += 1; t = done + pd.Timedelta("1h")
            if acc: D.append(max((done - s).total_seconds() / 86400, 2.0 if False else 0)); A.append(acc)
        D, A = np.array(D), np.array(A)
        w = np.mean([E[i][1][tpR][0] for i in range(len(E))])
        rows.append(dict(entries="+".join(x.split()[0] for x in which), risk=f"${int(3000 / tpR):,} (TP {tpR}R)", win_per_trade=f"{100 * w:.0f}%",
                         median_days=round(np.median(D), 1), within_7d=f"{100 * (D <= 7).mean():.0f}%", within_14d=f"{100 * (D <= 14).mean():.0f}%",
                         within_30d=f"{100 * (D <= 30).mean():.0f}%", mean_accounts=round(A.mean(), 2), p90_accounts=int(np.percentile(A, 90))))
pd.set_option("display.width", 250); print(pd.DataFrame(rows).to_string(index=False))
