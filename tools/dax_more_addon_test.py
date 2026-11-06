# Run from the scratchpad (needs dax_port.py, dax_lab.pkl, dax_more.pkl).
import sys, numpy as np, pandas as pd
src = open('dax_port.py').read().split('RULE = ("room"')[0]
exec(src.replace('dfd, TRD = pd.read_pickle("dax_lab.pkl")', 'dfd, TRD = pd.read_pickle("dax_lab.pkl"); dfm, TRM = pd.read_pickle("dax_more.pkl"); TRD.update(TRM)')
         .replace('PICK = [', 'PICK = ["DAX 15min pre-market range trend50 stop-mid", "DAX 15min ORB30 second-chance trend50", "DAX 5min ORB30 second-chance trend50", '))
orb = S[("DAX 15min ORB30 trend50 target0 stop-mid", 1)]
TEN = (NEW9[0] + 0.2 * orb[0], NEW9[1] + 0.2 * orb[1]); RB["10 core"] = TEN
pm = S[("DAX 15min pre-market range trend50 stop-mid", 1)]
dd = pd.DataFrame({"pm": pm[0], "orb": orb[0]}, index=idx).resample("1D").sum(); dd = dd[dd.abs().sum(axis=1) > 0]
print("corr pre-market vs ORB:", round(dd.corr().iloc[0, 1], 2), flush=True)
RULE = ("room", 1.0, 1.0, 0.03, 0.905, -1); C = [("10 core", RULE, "10 core EAs (DAX ORB @0.2)")]
for w in (0.1, 0.15, 0.2):
    for cm in ((1, 2) if w == 0.15 else (1,)):
        p_ = S[("DAX 15min pre-market range trend50 stop-mid", cm)]; nm = f"10 core + pre-market range @{w} costs x{cm}"
        RB[nm] = (TEN[0] + w * p_[0], TEN[1] + w * p_[1]); C.append((nm, RULE, nm))
for k in ("DAX 15min ORB30 second-chance trend50", "DAX 5min ORB30 second-chance trend50"):
    for w in (0.15, 0.2):
        nm = f"9 core + {k.replace('DAX ', '')} @{w} (replaces ORB)"; RB[nm] = (NEW9[0] + w * S[(k, 1)][0], NEW9[1] + w * S[(k, 1)][1]); C.append((nm, RULE, nm))
if __name__ == "__main__":
    with Pool(4) as p: rows = p.map(job, C)
    pd.set_option("display.width", 300); print(pd.DataFrame(rows).round(1).to_string(index=False), flush=True)
