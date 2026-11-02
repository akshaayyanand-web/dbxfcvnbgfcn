import sys, numpy as np, pandas as pd
SP = sys.argv[1]
exec(open(SP + "/speed8.py").read().split("V2 = [")[0])
r = (R * W[:, None]).sum(0); lo = (LO * W[:, None]).sum(0)
# worst intraday drawdown per UTC day (from the day's open, using each hour's worst point), no guard
dser = pd.Series(days); out = []
for d, ix in dser.groupby(dser).groups.items():
    ix = np.array(sorted(ix)); cum = np.concatenate([[0], np.cumsum(r[ix])[:-1]]); worst = np.min(cum + lo[ix])
    out.append((d, worst, r[ix].sum()))
D = pd.DataFrame(out, columns=["day", "worst_intraday", "close"]).set_index("day")
print("worst 10 days for the 8 EAs (no guard, % of balance):"); print((100 * D.sort_values("worst_intraday").head(10)).round(2).to_string())
contrib = pd.DataFrame((R * W[:, None]).T, columns=names); contrib["day"] = days
for d in D.sort_values("worst_intraday").head(3).index:
    print(f"\n{d.date()} by strategy (%):", (100 * contrib[contrib.day == d].drop(columns="day").sum()).round(2).to_dict())
# how the 2020 failures happen when a small add-on is included: replay the guarded run around those days
