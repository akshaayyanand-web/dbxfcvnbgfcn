# Crypto round (Binance 1h, 2020-2026). Pre-registered: C7 4h volatility-squeeze breakout (6 coins pooled), C10 turn-of-month long (BTC, ETH),
# C11 funding-time pressure (BTC, ETH). Costs per coin; split 2023-01-01.
import glob, numpy as np, pandas as pd
exec(open("newlab.py").read().split('\nif __name__ == "__main__":')[0])
CC = {"BTC": 0.0006, "ETH": 0.001, "SOL": 0.0015, "XRP": 0.002, "ADA": 0.0025, "LTC": 0.002}
S = pd.Timestamp("2023-01-01", tz="UTC")
def c7(sym):
    b = load_crypto(sym).resample("4h").agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()
    O, H, L, C, T = (b[k].to_numpy(float) for k in "ohlc"), None, None, None, b.index
    O, H, L, C = (b[k].to_numpy(float) for k in "ohlc")
    mid = b.c.rolling(20).mean().to_numpy(); sd = b.c.rolling(20).std().to_numpy(); up, dn = mid + 2 * sd, mid - 2 * sd
    width = pd.Series((up - dn) / mid); squeeze = (width <= width.rolling(120).quantile(0.10)).to_numpy()
    out, i, cost = [], 140, CC[sym]
    while i < len(C) - 2:
        recent = squeeze[max(0, i - 6):i + 1].any()
        d = 1 if (recent and C[i] > up[i]) else (-1 if (recent and C[i] < dn[i]) else 0)
        if not d: i += 1; continue
        j = i + 1; e = O[j]; st = mid[i]; risk = abs(e - st)
        if risk <= 0 or (e - st) * d <= 0: i += 1; continue
        x = None
        for k in range(j, min(j + 30, len(C) - 1)):
            if (d > 0 and L[k] <= st) or (d < 0 and H[k] >= st): x = st if (O[k] - st) * d > 0 else O[k]; break
            if (C[k] - mid[k]) * d < 0: x = C[k]; break
        if x is None: k = min(j + 30, len(C) - 1); x = C[k]
        out.append((b.index[j], b.index[k], d * (x - e) / risk - cost * e / risk)); i = k + 1
    return out
def c10(sym):
    m = Mkt(sym, load_crypto(sym), CC[sym]); out = []
    for me in pd.date_range("2020-02-01", "2026-11-01", freq="ME", tz="UTC"):
        t0, t1 = me.normalize(), me.normalize() + pd.Timedelta(days=3)
        i, j = m.t.searchsorted(t0), m.t.searchsorted(t1)
        if j < len(m.t) and j > i:
            tr = trade(m, i, j, +1)
            if tr: out.append(tr[:3])
    return out
def c11(sym):
    m = Mkt(sym, load_crypto(sym), CC[sym]); parts = []
    for f in sorted(glob.glob(f"kf/{sym}USDT-fundingRate-*.csv")) + sorted(glob.glob(f"funding/{sym}USDT-fundingRate-*.csv")):
        d = pd.read_csv(f); col = [c for c in d.columns if "funding" in c.lower() and "rate" in c.lower()]; tcol = [c for c in d.columns if "time" in c.lower()]
        if col and tcol: parts.append(pd.DataFrame({"t": d[tcol[0]], "r": d[col[0]]}))
    fr = pd.concat(parts); t = fr.t.astype("int64"); fr.index = pd.to_datetime(np.where(t > 1e14, t // 1000, t), unit="ms", utc=True).floor("h")
    fr = fr.r.astype(float).groupby(level=0).last().sort_index()
    pos = {tt: k for k, tt in enumerate(m.t)}; out = []
    for k in range(1, len(fr)):
        last, nxt = fr.iloc[k - 1], fr.index[k]
        d = -1 if last > 0.0003 else (1 if last < -0.0001 else 0)
        i = pos.get(nxt - pd.Timedelta(hours=1))
        if d and i is not None and i + 1 < len(m.t):
            tr = trade(m, i, i + 1, d)
            if tr: out.append(tr[:3])
    return out
if __name__ == "__main__":
    rows = []; allc7 = []
    for s in CC:
        t = c7(s); allc7 += t; rows.append(dict(test=f"C7 squeeze breakout {s}", **stats(t, S)))
    rows.append(dict(test="C7 squeeze breakout, 6 coins POOLED", **stats(sorted(allc7, key=lambda x: x[0]), S)))
    for s in ("BTC", "ETH"):
        rows.append(dict(test=f"C10 turn-of-month long {s}", **stats(c10(s), S)))
        rows.append(dict(test=f"C11 funding-time pressure {s}", **stats(c11(s), S)))
    pd.set_option("display.width", 250); R = pd.DataFrame(rows); print(R.to_string()); R.to_csv("cryptolab_results.csv", index=False)
