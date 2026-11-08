# Run from the scratchpad (needs world_lab.py and DAX day files).
import sys, numpy as np, pandas as pd
sys.argv = ["x", "DEUIDXEUR"]; exec(open("world_lab.py").read().split("rows, TR = [], {}")[0])
b = bars("15min"); T = b.index; fr = T.tz_convert(TZ); fm = (fr.hour * 60 + fr.minute).to_numpy(); fday = fr.normalize()
H, L, C = b.h.to_numpy(), b.l.to_numpy(), b.c.to_numpy(); dc = b.c.resample("1D").last().dropna()
ema = dc.ewm(span=50, adjust=False).mean().shift(1).reindex(T.floor("D"), method="ffill").to_numpy()
inr = (fm >= 540) & (fm < 570)
g = pd.DataFrame({"h": np.where(inr, H, np.nan), "l": np.where(inr, L, np.nan), "d": fday}).groupby("d").agg(h=("h", "max"), l=("l", "min"))
orh = g.h.reindex(fday).to_numpy(); orl = g.l.reindex(fday).to_numpy()
def sig(i):
    if not np.isfinite(orh[i]): return 0
    d = 1 if C[i] > orh[i] else (-1 if C[i] < orl[i] else 0)
    return d if d and (C[i] - ema[i]) * d > 0 else 0
rows = []
for fl, lab in ((1045, "17:25 (current)"), (1140, "19:00"), (1230, "20:30"), (1315, "21:55")):
    tr = intraday_sim(b, sig, lambda i, d, e: (orh[i] + orl[i]) / 2, 0, fl, 570, 720)
    s = stats(tr, f"DAX ORB, flat at {lab}"); s["maxDD_R"] = None
    R = np.array([(px - e) / abs(e - st) * np.sign(e - st) - COST * e / abs(e - st) for et, xt, e, st, px in tr]); eq = np.cumsum(R); s["maxDD_R"] = np.max(np.maximum.accumulate(eq) - eq)
    rows.append(s)
pd.set_option("display.width", 250); print(pd.DataFrame(rows).round(2).to_string(index=False))
