# Run from the scratchpad.
import numpy as np, pandas as pd
TRL = pd.read_pickle("ea_trades.pkl")
DIPS = ["BTC_Dip_v3", "Gold_Dip", "NQ_Dip_2h", "SPX_Dip_1h", "Oil_Dip_1h"]
rows = []
allt = [(nm, et, xt, e, st, px, cost) for nm in DIPS for (et, xt, e, st, px) in TRL[nm][0] for cost in [TRL[nm][1]]]
for nm, et, xt, e, st, px, cost in allt:
    R = (px - e) / abs(e - st) * np.sign(e - st) - cost * e / abs(e - st)
    n_open = sum(1 for nm2, et2, xt2, *_ in allt if nm2 != nm and et2 < et < xt2)
    rows.append(dict(ea=nm, t=et, R=R, others_open=n_open))
df = pd.DataFrame(rows); df["grp"] = pd.cut(df.others_open, [-1, 0, 1, 2, 9], labels=["0 others", "1 other", "2 others", "3+ others"])
df["half"] = np.where(df.t < pd.Timestamp("2023-01-01", tz="UTC"), "2020-22", "2023-26")
print(df.groupby(["half", "grp"], observed=True).R.agg(trades="count", avgR="mean", winrate=lambda x: 100 * (x > 0).mean()).round(2).to_string())
print(df.groupby("grp", observed=True).R.agg(trades="count", avgR="mean", worst="min").round(2).to_string())
