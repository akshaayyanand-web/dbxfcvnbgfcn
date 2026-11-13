# Crypto short-term mean reversion as real one-at-a-time trades (SOL / BTC 5m), 1x-3x cost, per year.
import glob, numpy as np, pandas as pd
def load(sym):
    p = []
    for f in sorted(glob.glob(f"k5full/{sym}-5m-*.csv")):
        d = pd.read_csv(f, header=None, usecols=[0, 1, 2, 3, 4], names=["t", "o", "h", "l", "c"]); d["t"] = np.where(d.t > 1e14, d.t // 1000, d.t); p.append(d)
    m = pd.concat(p); m.index = pd.to_datetime(m.t, unit="ms", utc=True); return m[~m.index.duplicated()].sort_index().drop(columns="t").loc["2020-01-01":]
def run(sym, feat, k, q, hold, trend_mode, cost, stopx, weekdays=True):
    m = load(sym); O, H, L, C = m.o.to_numpy(), m.h.to_numpy(), m.l.to_numpy(), m.c.to_numpy(); T = m.index
    wd = T.weekday.to_numpy(); yr = T.year.to_numpy(); cs = pd.Series(C)
    f = (cs - cs.shift(k)).to_numpy() if feat == "ret" else (cs - cs.ewm(span=200, adjust=False).mean()).to_numpy()
    f = f / C                                                           # relative, so thresholds work across price levels
    tr = np.sign(cs.ewm(span=800, adjust=False).mean().diff(30).to_numpy())
    base = (wd < 5) if weekdays else np.ones(len(C), bool)
    th = np.quantile(np.abs(f[(yr <= 2022) & base & np.isfinite(f)]), q)
    out, free = [], 0
    for i in np.where(base & np.isfinite(f) & (np.abs(f) >= th))[0]:
        if i < free or i + 1 + hold >= len(O): continue
        s = np.sign(f[i])
        if trend_mode == "with" and tr[i] != s: continue
        d = -s; e = O[i + 1]; size = abs(f[i]) * C[i]; st = e - d * stopx * size if stopx else None; px = None
        for j in range(i + 1, i + 1 + hold):
            if st is not None and ((L[j] <= st) if d == 1 else (H[j] >= st)): px = st; break
        if px is None: j = i + 1 + hold; px = O[j]
        R = stopx * size if stopx else size
        out.append((T[i], yr[i], ((px - e) * d - cost * e) / R)); free = j + 1
    return pd.DataFrame(out, columns=["t", "yr", "R"])
CASES = [("SOLUSDT", "ret", 5, 0.98, 12, "with", 0.001), ("SOLUSDT", "ret", 10, 0.98, 6, "with", 0.001), ("SOLUSDT", "ret", 5, 0.995, 6, "with", 0.001),
         ("BTCUSDT", "ema", 0, 0.995, 12, "with", 0.0004), ("BTCUSDT", "ema", 0, 0.995, 12, "any", 0.0004), ("BTCUSDT", "ret", 1, 0.95, 12, "with", 0.0004)]
rows = []
for sym, feat, k, q, hold, tm, c in CASES:
    for stopx in (None, 2.0):
        for mult in (1, 2, 3):
            r = run(sym, feat, k, q, hold, tm, c * mult, stopx)
            by = r.groupby("yr").R.sum().round(1)
            rows.append(dict(market=sym[:3], signal=f"{'move over '+str(k*5)+'m' if feat=='ret' else 'stretch from EMA200'} top {round((1-q)*100,1)}% {tm} trend", hold=f"{hold*5}m",
                             stop="2x move" if stopx else "none", cost=f"{c*mult*100:.2f}%", trades_yr=round(len(r) / 6.8), win=round(100 * (r.R > 0).mean()), avgR=round(r.R.mean(), 3),
                             R_yr=round(r.R.sum() / 6.8, 1), years_pos=f"{(by > 0).sum()}/{len(by)}", by_year=by.to_dict()))
pd.set_option("display.width", 330); pd.set_option("display.max_colwidth", 110); pd.set_option("display.max_rows", 50)
print(pd.DataFrame(rows).to_string(index=False))
