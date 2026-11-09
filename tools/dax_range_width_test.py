# Run from the scratchpad.
# Does the width of the DAX opening range (vs. the daily ATR) predict how good the breakout is?
import sys, numpy as np, pandas as pd
sys.argv = ["x", "DEUIDXEUR"]; exec(open("world_lab.py").read().split("rows, TR = [], {}")[0])
_, TRD = pd.read_pickle("dax_lab.pkl"); tr = TRD["DAX 15min ORB30 trend50 target0 stop-mid"]
b = bars("15min"); fr = b.index.tz_convert(TZ); fm = fr.hour * 60 + fr.minute; fday = fr.normalize()
inr = (fm >= 540) & (fm < 570)
g = pd.DataFrame({"h": np.where(inr, b.h, np.nan), "l": np.where(inr, b.l, np.nan), "d": fday}).groupby("d").agg(h=("h", "max"), l=("l", "min"))
dr = (b.h.resample("1D").max() - b.l.resample("1D").min()).dropna(); datr = dr.ewm(alpha=1 / 14, adjust=False).mean().shift(1)
rows = []
for et, xt, e, st, px in tr:
    d = et.tz_convert(TZ).normalize(); w = (g.h.get(d, np.nan) - g.l.get(d, np.nan)); a = datr.asof(et.normalize())
    R = (px - e) / abs(e - st) * np.sign(e - st) - COST * e / abs(e - st)
    rows.append(dict(t=et, R=R, width=w / a if a else np.nan, wd=et.tz_convert(TZ).weekday()))
df = pd.DataFrame(rows).dropna(); df["half"] = np.where(df.t < pd.Timestamp("2023-01-01", tz="UTC"), "2021-22", "2023-26")
df["width_q"] = pd.qcut(df.width, 4, labels=["narrowest 25%", "25-50%", "50-75%", "widest 25%"])
print(df.pivot_table(index="width_q", columns="half", values="R", aggfunc=["mean", "count"], observed=True).round(2).to_string())
print(df.pivot_table(index="wd", columns="half", values="R", aggfunc="mean").round(2).rename(index=dict(enumerate(["Mon", "Tue", "Wed", "Thu", "Fri"]))).to_string())
