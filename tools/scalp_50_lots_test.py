# 50-lot Nasdaq scalps: take-profit 3-10 points vs stop 5-40 points, spread 1-2 points, on NQ ORB entries and random NY-hours entries (1m data 2020-2026).
import sys, numpy as np, pandas as pd
sys.path.insert(0, "/home/user/dbxfcvnbgfcn/tools")
from portfolio_prop import load_csv
m1 = load_csv("fut1m/USATECHIDXUSD_1m.csv").loc["2020-01-01":]
O, H, L, T = m1.o.to_numpy(), m1.h.to_numpy(), m1.l.to_numpy(), m1.index
ny = T.tz_convert("America/New_York"); mins = (ny.hour * 60 + ny.minute).to_numpy(); wd = ny.weekday.to_numpy()
orb = pd.read_pickle("ea_trades.pkl")["NQ_Opening_Range"][0]
E1 = [(T.searchsorted(et), 1 if e > st else -1) for et, xt, e, st, px in orb if et >= T[0]]
rng = np.random.default_rng(7); cand = np.where((mins >= 575) & (mins < 900) & (wd < 5))[0]
E2 = [(int(i), int(rng.choice([-1, 1]))) for i in rng.choice(cand, 6000, replace=False)]
def run(entries, tp, sl, spread):
    out = []
    for i, d in entries:
        e = O[i] + d * spread / 2; res = None            # pay half the spread on entry, half on exit
        for j in range(i, min(i + 390, len(O))):
            if (L[j] <= e - sl) if d == 1 else (H[j] >= e + sl): res = -sl; break      # stop first if both in one minute
            if (H[j] >= e + tp) if d == 1 else (L[j] <= e - tp): res = tp; break
        if res is None: res = (O[min(i + 390, len(O) - 1)] - e) * d
        out.append(res - spread / 2)
    return np.array(out)
rows = []
for name, ents in (("NQ ORB entries", E1), ("random entries NY hours", E2)):
    for spread in (1.0, 2.0):
        for tp in (3, 6, 10):
            for sl in (5, 10, 20, 40):
                r = run(ents, tp, sl, spread)
                rows.append(dict(entries=name, spread_pts=spread, tp_pts=tp, sl_pts=sl, trades=len(r), win_pct=round(100 * (r > 0).mean(), 1),
                                 avg_pts=round(r.mean(), 2), usd_per_trade_50lots=round(50 * r.mean()), breakeven_win_pct=round(100 * (sl + spread / 2) / (tp - spread / 2 + sl + spread / 2), 1)))
df = pd.DataFrame(rows); pd.set_option("display.width", 250); pd.set_option("display.max_rows", 100)
print(df.to_string(index=False))
print("\nprofitable combinations:", (df.avg_pts > 0).sum(), "of", len(df))
