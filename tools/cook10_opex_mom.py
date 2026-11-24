# Post-hoc mirror of P2: follow the 14:00->15:00 move into the close (exit 15:55, take profit at +1x the move), costs paid.
import numpy as np, pandas as pd
exec(open("smc.py").read().split("def run_symbol(")[0])
COST = 0.00015; out = []
for sym, path in (("SPX", "fut1m/USA500IDXUSD_1m.csv"), ("NQ", "fut1m/USATECHIDXUSD_1m.csv")):
    m = m1_csv(path); m.index = m.index.tz_convert("America/New_York"); m = m[(m.index.dayofweek < 5) & (m.index.hour >= 14) & (m.index.hour < 16)]
    for d, x in m.groupby(m.index.date):
        t = x.index.hour * 60 + x.index.minute; c, h, l = x.c.to_numpy(), x.h.to_numpy(), x.l.to_numpy()
        k = [np.searchsorted(t, v) for v in (840, 900, 955)]
        if any(i >= len(t) for i in k) or abs(t[k[0]] - 840) > 2 or abs(t[k[1]] - 900) > 2 or abs(t[k[2]] - 955) > 2: continue
        mv = c[k[1]] - c[k[0]]; e = c[k[1]]
        if abs(mv) <= 3 * COST * e: continue
        dn = np.sign(mv); tp = e + dn * abs(mv); x_ = c[k[2]]
        for q in range(k[1] + 1, k[2] + 1):
            if (dn > 0 and h[q] >= tp) or (dn < 0 and l[q] <= tp): x_ = tp; break
        out.append((sym, pd.Timestamp(d), (dn * (x_ - e) - COST * e) / abs(mv), (dn * (x_ - e)) / e))
D = pd.DataFrame(out, columns=["sym", "d", "R", "ret"])
for (s, per), g in D.groupby(["sym", np.where(D.d < "2023-01-01", "pre2023", "2023on")]):
    print(s, per, "n", len(g), "win", round(100 * (g.R > 0).mean()), "avgR", round(g.R.mean(), 3), "t", round(g.R.mean() / g.R.std() * np.sqrt(len(g)), 2), "avg net bp", round(1e4 * (g.ret.mean() - COST), 2))
print("years:", D.groupby(D.d.dt.year).R.sum().round(1).to_dict(), "first day", D.d.min().date())
