# Score the 1000-strategy catalogue run. Pass rules fixed before looking at results:
#   train (< 2023): t >= 2.5 and >= 100 trades;  holdout (2023+): t >= 2.0, avg >= +0.05R, >= 50 trades;  >= 70% profitable years.
import numpy as np, pandas as pd
from math import erf, sqrt
D = pd.read_pickle("cat1000/results.pkl"); D = D[D.n > 0].copy()
CAT = pd.read_excel("cat1000/cat.xlsx", sheet_name=0)
M = len(D[D.n_train >= 100])
pnorm = lambda z: 0.5 * (1 + erf(z / sqrt(2)))
p_tr, p_ho = 1 - pnorm(2.5), 1 - pnorm(2.0)
D["pass_train"] = (D.t_train >= 2.5) & (D.n_train >= 100)
D["pass_all"] = D.pass_train & (D.t_hold >= 2.0) & (D.avgR_hold >= 0.05) & (D.n_hold >= 50) & (D.pos_years >= 0.7 * D.years)
print(f"tests with >= 100 train trades: {M:,}  (of {len(D):,} non-empty results)")
print(f"passed train: {D.pass_train.sum():,}  (luck alone would give about {M * p_tr:,.0f})")
print(f"passed train AND holdout: {D.pass_all.sum():,}  (luck alone, if tests were independent: about {M * p_tr * p_ho:,.1f})")
print(f"\nholdout result of everything that passed train: median avgR {D[D.pass_train].avgR_hold.median():+.3f}, share positive {100*(D[D.pass_train].avgR_hold > 0).mean():.0f}%")
print(f"all tests: median avgR train {D.avgR_train.median():+.3f}, holdout {D.avgR_hold.median():+.3f}; share positive in both {100*((D.avgR_train>0)&(D.avgR_hold>0)).mean():.0f}%")
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200); pd.set_option("display.max_colwidth", 60)
cols = ["ID", "base", "sym", "tf", "exit", "n_train", "n_hold", "avgR_train", "avgR_hold", "t_train", "t_hold", "win", "pf", "pos_years", "years"]
P = D[D.pass_all].sort_values("t_hold", ascending=False)
names = CAT.set_index("ID")["Strategy hypothesis"]
P["name"] = P.ID.map(names)
print("\nSURVIVORS (pass train and holdout):"); print(P[["name"] + cols].round(3).to_string(index=False) if len(P) else "none")
# family view: per base setup, across every market/timeframe/filter/exit cell
fam = D.groupby("base").agg(cells=("ID", "size"), med_avgR_train=("avgR_train", "median"), med_avgR_hold=("avgR_hold", "median"),
                            pass_train=("pass_train", "sum"), pass_all=("pass_all", "sum"))
fam["name"] = [CAT[CAT.ID == f"CFD-{(b - 1) * 10 + 1:04d}"]["Strategy hypothesis"].iloc[0].split(" + ")[0] for b in fam.index]
fam["family"] = [CAT[CAT.ID == f"CFD-{(b - 1) * 10 + 1:04d}"]["Family"].iloc[0] for b in fam.index]
print("\nBASE SETUPS ranked by median holdout avgR (all cells):"); print(fam.sort_values("med_avgR_hold", ascending=False).round(3).to_string())
print("\nBY FAMILY:"); print(D.assign(family=D.base.map(fam.family)).groupby("family").agg(cells=("ID", "size"), med_train=("avgR_train", "median"), med_hold=("avgR_hold", "median"),
      pass_train=("pass_train", "sum"), pass_all=("pass_all", "sum")).round(3).to_string())
print("\nBY MARKET:"); print(D.groupby(["sym"]).agg(cells=("ID", "size"), med_train=("avgR_train", "median"), med_hold=("avgR_hold", "median"), pass_all=("pass_all", "sum")).round(3).to_string())
# write the user's catalogue back with results
best = D.sort_values("t_hold", ascending=False).groupby("ID").head(1).set_index("ID")
agg = D.groupby("ID").agg(cells=("sym", "size"), passed_train=("pass_train", "sum"), passed_both=("pass_all", "sum"), med_avgR_hold=("avgR_hold", "median"))
out = CAT.copy()
out["Cells tested (market x TF x exit)"] = out.ID.map(agg.cells).fillna(0).astype(int)
out["Passed train"] = out.ID.map(agg.passed_train).fillna(0).astype(int); out["Passed train + holdout"] = out.ID.map(agg.passed_both).fillna(0).astype(int)
out["Median holdout R/trade"] = out.ID.map(agg.med_avgR_hold).round(3)
for c, src in (("Best cell", None), ("Best holdout R/trade", "avgR_hold"), ("Best holdout t", "t_hold"), ("Best cell train t", "t_train")):
    if src: out[c] = out.ID.map(best[src]).round(3)
    else: out[c] = out.ID.map(best.sym + " " + best.tf + " / " + best.exit)
out["Status"] = np.where(out["Passed train + holdout"] > 0, "Tested - candidate (needs prop sim)", np.where(out["Cells tested (market x TF x exit)"] > 0, "Tested - rejected", "Not testable with this data"))
out.to_excel("cat1000/CFD_Prop_Firm_1000_Strategy_Catalogue_RESULTS.xlsx", index=False); D.to_csv("cat1000/all_results.csv", index=False)
print("\nStatus counts:", out.Status.value_counts().to_dict())
