# Trailing stops on all 21 EAs (5-minute bars; oil hourly). Pre-registered uniform variants: T1 act +1R trail 1R, T2 act +1R trail 1.5R,
# T3 act +2R trail 1R, T4 trail 1.5R from entry. Original targets/time exits kept; stop checked before the trail moves (conservative).
# New R = original R + direction * (new exit - original exit) / stop distance  (costs unchanged).
import glob, io, numpy as np, pandas as pd
exec(open("margin_check.py").read().split("def margin_series")[0])
def rr(e, st, px, cost): return (px - e) / abs(e - st) * np.sign(e - st) - cost * e / abs(e - st)
def m1_to5(path):
    d = pd.read_csv(path, index_col=0); d.index = pd.to_datetime(d.index, utc=True); d = d[~d.index.duplicated()].sort_index()
    d = d.iloc[:, :4]; d.columns = list("ohlc"); return d.resample("5min").agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()
def crypto5(sym):
    p = []
    for f in sorted(glob.glob(f"k5full/{sym}USDT-5m-*.csv")):
        x = pd.read_csv(f, header=None, usecols=[0, 1, 2, 3, 4], names=["t", "o", "h", "l", "c"]); x["t"] = np.where(x.t > 1e14, x.t // 1000, x.t); p.append(x)
    x = pd.concat(p); x.index = pd.to_datetime(x.t, unit="ms", utc=True); return x[["o", "h", "l", "c"]].astype(float).sort_index().loc[lambda z: ~z.index.duplicated()]
def jpn5():
    parts = [pd.read_csv(io.StringIO(open(f).read().strip()), header=None, names=["t", "o", "h", "l", "c", "v"]) for f in sorted(glob.glob("world1m/JPNIDXJPY/*.csv")) if open(f).read().strip()]
    x = pd.concat(parts); x.index = pd.to_datetime(x.t, unit="s", utc=True); x = x[~x.index.duplicated()].sort_index()[["o", "h", "l", "c"]]
    return x.resample("5min").agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()
BARS = {"NQ": m1_to5("fut1m/USATECHIDXUSD_1m.csv"), "SPX": m1_to5("fut1m/USA500IDXUSD_1m.csv"), "XAU": m1_to5("fut1m/XAUUSD_1m.csv"), "DAX": m1_to5("eu1m/DEUIDXEUR_1m.csv"),
        "BTC": crypto5("BTC"), "SOL": crypto5("SOL"), "XRP": crypto5("XRP"), "OIL": load_duka("LIGHTCMDUSD") if "load_duka" in globals() else None}
if BARS["OIL"] is None:
    exec(open("newlab.py").read().split('\nif __name__ == "__main__":')[0].split("class Mkt")[0]); BARS["OIL"] = load_duka("LIGHTCMDUSD")
try: BARS["JPN"] = jpn5()
except Exception as ex: print("no JPN bars:", ex)
INS = {"btc": "BTC", "btcgap": "BTC", "btcrev": "BTC", "sol": "SOL", "solrev": "SOL", "xrprev": "XRP", "gdip": "XAU", "gasia": "XAU", "gmom": "XAU", "goldvwap": "XAU",
       "nq2h": "NQ", "orb15": "NQ", "nqbo15": "NQ", "nqfade": "NQ", "spx1h": "SPX", "spxbo5": "SPX", "spxfade": "SPX", "daxorb": "DAX", "daxpm": "DAX", "oil1h": "OIL", "nikkei": "JPN"}
TR = {}   # ea -> list of (et, xt, e, sd, d, r)
for c, k in MAP.items(): TR[c] = [(pd.Timestamp(et), pd.Timestamp(xt), e, abs(e - st), 1 if e > st else -1, rr(e, st, px, TRL[k][1]), px) for et, xt, e, st, px in TRL[k][0]]
for c, tl, cost in (("nqbo15", simT(bq, wq & (Cq > bq.h.rolling(20).max().shift(1).to_numpy()) & (Cq > cq.ewm(span=200, adjust=False).mean().to_numpy()), wq & (Cq < bq.l.rolling(20).min().shift(1).to_numpy()) & (Cq < cq.ewm(span=200, adjust=False).mean().to_numpy()), aq, 10 ** 6, mq >= 950), 0.00012),
                    ("spxbo5", simT(b5, w5 & (C5 > hi) & (C5 > e5), w5 & (C5 < lo5) & (C5 < e5), 2 * a5, 10 ** 6, m5 >= 950), 0.0001), ("daxpm", dtr, 0.0001)):
    TR[c] = [(pd.Timestamp(et), pd.Timestamp(xt), e, abs(e - st), 1 if e > st else -1, rr(e, st, px, cost), px) for et, xt, e, st, px in tl]
def from_r(c, lst):   # (et, xt, r) only: rebuild entry, direction and stop distance from the bars
    B = BARS[INS[c]]; out = []
    for et, xt, r in lst:
        et, xt = pd.Timestamp(et), pd.Timestamp(xt); i, j = B.index.searchsorted(et), B.index.searchsorted(xt)
        if i >= len(B) or j >= len(B) or j <= i or abs(r) < 0.05: continue
        e, px = B.o.iloc[i], B.o.iloc[j]
        if px == e: continue
        d = int(np.sign(r * (px - e))); sd = abs(px - e) / abs(r); out.append((et, xt, e, sd, d, r, px))
    return out
for c, lst in (("goldvwap", AT["gold"]), ("spxfade", AT["spx_fade"]), ("nikkei", nk), ("nqfade", MT["nqfade"]), ("xrprev", MT["xrprev"]), ("solrev", CT["solrev"]), ("btcrev", CT["btcrev"])):
    if INS[c] in BARS: TR[c] = from_r(c, lst)
TR["sol"] = from_r("sol", [(et, xt, r) for et, xt, r, path in ns["dip_trades"]("SOL")])
def trail(c, act, dist):
    B = BARS[INS[c]]; T = B.index; O, H, L = B.o.to_numpy(), B.h.to_numpy(), B.l.to_numpy(); out = []
    for et, xt, e, sd, d, r, px in TR[c]:
        i, j = T.searchsorted(et), T.searchsorted(xt)
        if i >= len(T) or j > len(T): continue
        s = e - d * sd; best = e; newx = None
        for k in range(i, j):
            if (d > 0 and L[k] <= s) or (d < 0 and H[k] >= s):
                if s != e - d * sd: newx = (min(O[k], s) if d > 0 else max(O[k], s))
                break
            best = max(best, H[k]) if d > 0 else min(best, L[k])
            if (best - e) * d >= act * sd: s = (max(s, best - dist * sd) if d > 0 else min(s, best + dist * sd))
        if newx is None: out.append((et, r)); continue
        cost_r = d * (px - e) / sd - r                        # cost part of the original result
        out.append((et, d * (newx - e) / sd - cost_r))
    return out
VAR = {"current": None, "T1 +1R / trail 1R": (1.0, 1.0), "T2 +1R / trail 1.5R": (1.0, 1.5), "T3 +2R / trail 1R": (2.0, 1.0), "T4 trail 1.5R from entry": (0.0, 1.5)}
SPLIT = pd.Timestamp("2023-01-01", tz="UTC"); rows = []; book = {v: {"a": 0.0, "b": 0.0} for v in VAR}
for c in NAMES:
    if c not in TR or not TR[c]: continue
    w = BASE[c] / 100 * PORT["21"][c]
    for v, p in VAR.items():
        res = [(x[0], x[5]) for x in TR[c]] if p is None else trail(c, *p)
        t = pd.DatetimeIndex([x[0] for x in res]); R = np.array([x[1] for x in res]); A = t < SPLIT
        ya = max((t[A].max() - t[A].min()).days / 365.25, 0.5) if A.any() else np.nan; yb = max((t[~A].max() - t[~A].min()).days / 365.25, 0.5) if (~A).any() else np.nan
        ra, rb = (R[A].sum() / ya if A.any() else np.nan), (R[~A].sum() / yb if (~A).any() else np.nan)
        rows.append(dict(ea=c, variant=v, trades=len(R), win=round(100 * (R > 0).mean()), R_yr_pre2023=round(ra, 1), R_yr_2023on=round(rb, 1)))
        book[v]["a"] += w * (ra if np.isfinite(ra) else 0); book[v]["b"] += w * (rb if np.isfinite(rb) else 0)
D = pd.DataFrame(rows); pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
P = D.pivot_table(index="ea", columns="variant", values=["R_yr_pre2023", "R_yr_2023on"]); print(P.round(1).to_string())
print("\nBOOK at 1x (%/yr, weights of the pack):"); print(pd.DataFrame({v: {"pre-2023": round(100 * b["a"], 1), "2023-26": round(100 * b["b"], 1)} for v, b in book.items()}).to_string())
D.to_csv("trail_results.csv", index=False)
