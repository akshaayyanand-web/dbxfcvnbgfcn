# Run from the scratchpad (needs recent_check.py chain).
import sys, numpy as np, pandas as pd
exec(open('recent_check.py').read().split('RULE = ("room", 1.0, 1.0, 0.03, 0.905, -1)\ngap')[0])
import orb_lab as O
nq5 = O.five_min(load_csv("fut1m/USATECHIDXUSD_1m.csv")); cost = O.COST["USATECHIDXUSD"]
old = (RM[KEYS.index("orb15")], LM[KEYS.index("orb15")]); W = 0.625
VAR = {}
for stop in ("other", "mid"):
    for tg in (2.0, 3.0, 4.0, None):
        x = O.orb(nq5, "America/New_York", (9, 30), (11, 30), (15, 55), 15, stop, tg, True, cost)
        for cm in (1, 2):
            VAR[(stop, tg, cm)] = P.trade_series([a[:5] for a in x], cost * cm, nq, idx)
        r = VAR[(stop, tg, 1)][0]; r2 = VAR[(stop, tg, 2)][0]; A = idx < split; yrs = (idx[-1] - idx[0]).days / 365.25
        print(f"NQ ORB15 stop-{stop} target {tg}: %/yr@1% A {100*r[A].sum()/(yrs*A.mean()):+.1f} B {100*r[~A].sum()/(yrs*(1-A.mean())):+.1f} costs x2 {100*r2.sum()/yrs:+.1f}", flush=True)
print("check: current ORB series equals rebuilt one:", np.allclose(old[0], VAR[("other", 2.0, 1)][0]), flush=True)
RULE = ("room", 1.0, 1.0, 0.03, 0.905, -1)
GAP = V[(0.02, "48h")]; CUR = (TEN[0] - 0.25 * GAP[0], TEN[1] - 0.25 * GAP[1]); RB["current 10 (gap 0.25)"] = CUR
C = [("current 10 (gap 0.25)", RULE, "current 10 EAs (NQ ORB: other-side stop, 2R target)")]
for k in VAR:
    if k[:2] == ("other", 2.0) and k[2] == 1: continue
    if k[2] == 2 and k[:2] not in (("other", 3.0), ("other", None), ("other", 2.0), ("mid", None)): continue
    nm = f"NQ ORB stop-{k[0]} target {k[1]} costs x{k[2]}"
    base_old = old
    RB[nm] = (CUR[0] + W * (VAR[k][0] - base_old[0]), CUR[1] + W * (VAR[k][1] - base_old[1])); C.append((nm, RULE, nm))
if __name__ == "__main__":
    with Pool(4) as p: rows = p.map(job, C)
    pd.set_option("display.width", 300); print(pd.DataFrame(rows).round(1).to_string(index=False), flush=True)
