# Run from the scratchpad (needs cmegap_nolook.py, fund_check.py, dax_lab.pkl).
import sys, numpy as np, pandas as pd
exec(open('cmegap_nolook.py').read().split("RULE = (")[0])
dfd, TRD = pd.read_pickle("dax_lab.pkl")
raw = load_csv("eu1m/DEUIDXEUR_1m.csv"); dh1 = raw.resample("1h").agg(dict(o="first", h="max", l="min", c="last")).dropna()
NEW9 = (RB["8|btc0.75|x1.25"][0] + 0.5 * V[(0.02, "48h")][0], RB["8|btc0.75|x1.25"][1] + 0.5 * V[(0.02, "48h")][1]); RB["9 core"] = NEW9
PICK = ["DAX 15min ORB30 trend50 target0 stop-mid", "DAX 15min ORB60 trend50 target0 stop-mid", "DAX 15min ORB30 trend20 target0 stop-mid"]  #
S = {}
for k in PICK:
    for cm in (1, 2): S[(k, cm)] = P.trade_series(TRD[k], 0.0001 * cm, dh1, idx)
    dd = pd.DataFrame({"dax": S[(k, 1)][0], "orb15": RM[KEYS.index("orb15")], "port": NEW9[0]}, index=idx).resample("1D").sum()
    cc = dd[dd.abs().sum(axis=1) > 0].corr(); print(f"{k}: corr NQ ORB {cc.loc['dax','orb15']:.2f}, 9-EA portfolio {cc.loc['dax','port']:.2f}", flush=True)
RULE = ("room", 1.0, 1.0, 0.03, 0.905, -1); C = [("9 core", RULE, "9 core EAs")]
for k in PICK:
    for w in (0.15, 0.2, 0.25):
        for cm in ((1, 2) if w == 0.25 else (1,)):
            nm = f"+{k.replace('DAX ', '')} @{w} costs x{cm}"; RB[nm] = (NEW9[0] + w * S[(k, cm)][0], NEW9[1] + w * S[(k, cm)][1]); C.append((nm, RULE, nm))
if __name__ == "__main__":
    with Pool(4) as p: rows = p.map(job, C)
    pd.set_option("display.width", 300); print(pd.DataFrame(rows).round(1).to_string(index=False), flush=True)
