# Nexural-style test: delta only as CONFIRMATION at a level marked in advance; compare trades where delta agreed vs not (BTC/ETH, real taker buy/sell volume).
# Levels (fixed before the day): previous UTC day's volume-profile VAL/VAH (70%), previous day low/high, and today's running VWAP.
# Event (long; shorts mirrored): a 15-min bar trades through the level and closes back above it (rejection). Entry next bar open,
# stop 0.1 ATR beyond the bar's extreme, target 2R, time exit 16 bars (4h). One position per market at a time.
# Delta z = bar delta (taker buy - taker sell) / rolling 96-bar stdev.  Groups: ALL touches | delta AGREES (z >= +1.5 for longs) |
# ABSORPTION (z <= -1.5, sellers hit but price held) | NEUTRAL (|z| < 1.5). Costs BTC 0.09%, ETH 0.227% round trip. Train < 2023.
import glob, numpy as np, pandas as pd
def crypto_tb(sym):
    p = []
    for f in sorted(glob.glob(f"k5full/{sym}USDT-5m-*.csv")):
        x = pd.read_csv(f, header=None, usecols=[0, 1, 2, 3, 4, 5, 9], names=["t", "o", "h", "l", "c", "v", "tb"]); x["t"] = np.where(x.t > 1e14, x.t // 1000, x.t); p.append(x)
    x = pd.concat(p); x.index = pd.to_datetime(x.t, unit="ms", utc=True); return x[["o", "h", "l", "c", "v", "tb"]].astype(float).sort_index().loc[lambda z: ~z.index.duplicated()]
COST = {"BTC": .0009, "ETH": .00227}
def prof(tp, v, c0):
    bs = c0 * 0.001; k = np.floor(tp / bs).astype(int); k -= k.min(); cnt = np.bincount(k, v); p = cnt.argmax(); i = j = p; s = cnt[p]; tot = cnt.sum()
    while s < 0.7 * tot:
        up = cnt[j + 1] if j + 1 < len(cnt) else -1; dn = cnt[i - 1] if i > 0 else -1
        if up >= dn: j += 1; s += up
        else: i -= 1; s += dn
    base = np.floor(tp / bs).astype(int).min(); return (base + j + 1) * bs, (base + i) * bs
def run(sym):
    m = crypto_tb(sym); m["tp"] = (m.h + m.l + m.c) / 3; day = m.index.floor("1D")
    lv = {}
    for d, g in m.groupby(day):
        if len(g) > 250: vah, val = prof(g.tp.to_numpy(), g.v.to_numpy(), g.c.iloc[0]); lv[d] = (vah, val, g.h.max(), g.l.min())
    L = pd.DataFrame(lv, index=["vah", "val", "pdh", "pdl"]).T; L.index = L.index + pd.Timedelta(days=1)          # yesterday's levels apply today
    pv = (m.tp * m.v).groupby(day).cumsum(); vv = m.v.groupby(day).cumsum(); m["vwap"] = pv / vv
    b = m.resample("15min").agg({"o": "first", "h": "max", "l": "min", "c": "last", "v": "sum", "tb": "sum", "vwap": "last"}).dropna(subset=["c"])
    b = b.join(L.reindex(b.index.floor("1D")).set_index(b.index)); b["vwap_prev"] = b.vwap.shift(1)                   # VWAP known at the bar's start
    O, H, Lo, C = (b[c].to_numpy() for c in ("o", "h", "l", "c")); pc = np.r_[C[0], C[:-1]]
    A = pd.Series(np.maximum(H - Lo, np.maximum(abs(H - pc), abs(Lo - pc)))).ewm(alpha=1 / 14, adjust=False).mean().to_numpy()
    dl = (2 * b.tb - b.v); z = (dl / dl.rolling(96, min_periods=48).std()).to_numpy(); T = b.index; out = []
    for name, lvl_long, lvl_short in (("VA edge", "val", "vah"), ("prev-day extreme", "pdl", "pdh"), ("VWAP", "vwap_prev", "vwap_prev")):
        ll, ls = b[lvl_long].to_numpy(), b[lvl_short].to_numpy(); busy = -1
        for k in range(100, len(C) - 18):
            if k <= busy or not np.isfinite(z[k]) or not np.isfinite(ll[k]): continue
            d = 1 if (Lo[k] < ll[k] < C[k] and O[k] > ll[k]) else (-1 if (H[k] > ls[k] > C[k] and O[k] < ls[k]) else 0)
            if not d: continue
            zz = d * z[k]; grp = "AGREES" if zz >= 1.5 else ("ABSORPTION" if zz <= -1.5 else "NEUTRAL")
            e = O[k + 1]; stop = (Lo[k] - .1 * A[k]) if d > 0 else (H[k] + .1 * A[k]); risk = d * (e - stop)
            if risk <= 3 * COST[sym] * e: continue
            tp = e + d * 2 * risk; x = None
            for q in range(k + 1, k + 17):
                if (d > 0 and Lo[q] <= stop) or (d < 0 and H[q] >= stop): x = min(O[q], stop) if d > 0 else max(O[q], stop); break
                if (d > 0 and H[q] >= tp) or (d < 0 and Lo[q] <= tp): x = tp; break
            if x is None: x, q = C[k + 16], k + 16
            out.append(dict(sym=sym, level=name, group=grp, t=T[k], R=(d * (x - e) - COST[sym] * e) / risk, R2=(d * (x - e) - 2 * COST[sym] * e) / risk)); busy = q
    return out
if __name__ == "__main__":
    from multiprocessing import Pool
    with Pool(2) as p: res = p.map(run, ["BTC", "ETH"])
    D = pd.DataFrame([r for o in res for r in o]); D.to_pickle("levelflow_trades.pkl"); S = pd.Timestamp("2023-01-01", tz="UTC")
    tt = lambda v: round(v.mean() / v.std(ddof=1) * np.sqrt(len(v)), 2) if len(v) > 2 else np.nan
    def agg(g):
        a, h = g[g.t < S].R, g[g.t >= S].R
        return pd.Series(dict(trades=len(g), win=round(100 * (g.R > 0).mean()), avgR=round(g.R.mean(), 3), t_train=tt(a), avgR_hold=round(h.mean(), 3), t_hold=tt(h), dbl_cost=round(g.R2.mean(), 3)))
    rows = []
    for (s, l), g in D.groupby(["sym", "level"]):
        rows.append(dict(sym=s, level=l, group="ALL touches", **agg(g)))
        for gr in ("AGREES", "NEUTRAL", "ABSORPTION"): rows.append(dict(sym=s, level=l, group=gr, **agg(g[g.group == gr])))
    R = pd.DataFrame(rows); pd.set_option("display.width", 220); print(R.to_string(index=False)); R.to_csv("levelflow.csv", index=False)
