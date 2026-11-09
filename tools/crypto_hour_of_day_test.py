# Run from the scratchpad (Binance 5m files in k5full/).
import glob, numpy as np, pandas as pd
for sym in ("BTCUSDT", "ETHUSDT"):
    p = []
    for f in sorted(glob.glob(f"k5full/{sym}-5m-*.csv")):
        d = pd.read_csv(f, header=None, usecols=[0, 1, 4], names=["t", "o", "c"]); d["t"] = np.where(d.t > 1e14, d.t // 1000, d.t); p.append(d)
    d = pd.concat(p); d.index = pd.to_datetime(d.t, unit="ms", utc=True); d = d[~d.index.duplicated()].sort_index()
    h = d.c.resample("1h").last().dropna(); r = np.log(h).diff().dropna()
    ny = r.index.tz_convert("America/New_York"); tab = (r.groupby([ny.year, ny.hour]).mean() * 1e4).unstack(0)   # basis points per hour
    cost_bp = 6   # ~0.06% round trip per trade
    cons = tab.apply(lambda row: (row > 0).all() or (row < 0).all(), axis=1)
    print(f"\n{sym}: average return per NY hour, in basis points (0.01%), by year. Hours with the SAME sign every year:")
    print(tab[cons].round(1).to_string())
    print(f"(a 1-hour trade costs ~{cost_bp} bp round trip)")
