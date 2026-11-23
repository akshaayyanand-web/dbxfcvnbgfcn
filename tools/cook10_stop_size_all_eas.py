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

REAL = {"btc", "btcgap", "daxorb", "daxpm", "gasia", "gdip", "gmom", "nq2h", "nqbo15", "oil1h", "orb15", "spx1h", "spxbo5"}
def restop(c, k):
    B = BARS[INS[c]]; T = B.index; O, H, L, C = B.o.to_numpy(), B.h.to_numpy(), B.l.to_numpy(), B.c.to_numpy()
    tr = TR[c]; maxhold = max((xt - et) for et, xt, *_ in tr); out = []
    for et, xt, e, sd, d, r, px in tr:
        cost_r = d * (px - e) / sd - r
        stopped = abs(px - (e - d * sd)) <= 0.05 * sd
        t_end = (et + maxhold) if (stopped and k > 1) else xt
        i, j = T.searchsorted(et), T.searchsorted(t_end)
        if i >= len(T) or j > len(T) or j <= i: out.append((et, r)); continue
        s_ = e - d * k * sd; x = None
        for q in range(i, j):
            if (d > 0 and L[q] <= s_) or (d < 0 and H[q] >= s_): x = (min(O[q], s_) if d > 0 else max(O[q], s_)); break
        if x is None: x = px if not (stopped and k > 1) else C[j - 1]
        out.append((et, d * (x - e) / (k * sd) - cost_r / k))
    return out
SPLIT = pd.Timestamp("2023-01-01", tz="UTC"); rows = []; KS = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0); book = {k: [0.0, 0.0] for k in KS}; bookR = {k: [0.0, 0.0] for k in KS}
for c in NAMES:
    if c not in TR or not TR[c]: continue
    w = BASE[c] / 100 * PORT["21"][c]
    for k in KS:
        res = [(x[0], x[5]) for x in TR[c]] if k == 1.0 else restop(c, k)
        t = pd.DatetimeIndex([x[0] for x in res]); R = np.array([x[1] for x in res]); A = t < SPLIT
        ya = max((t[A].max() - t[A].min()).days / 365.25, 0.5) if A.any() else np.nan; yb = max((t[~A].max() - t[~A].min()).days / 365.25, 0.5) if (~A).any() else np.nan
        ra, rb = (R[A].sum() / ya if A.any() else 0.0), (R[~A].sum() / yb if (~A).any() else 0.0)
        rows.append(dict(ea=c, exact="yes" if c in REAL else "approx", stop_x=k, R_yr_pre2023=round(ra, 1), R_yr_2023on=round(rb, 1)))
        book[k][0] += w * ra; book[k][1] += w * rb
        if c in REAL: bookR[k][0] += w * ra; bookR[k][1] += w * rb
D = pd.DataFrame(rows); pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
print(D.pivot_table(index=["exact", "ea"], columns="stop_x", values="R_yr_2023on").round(1).to_string())
print("\nBOOK at 1x, %/yr (all EAs | only the 13 EAs with exact stops):")
print(pd.DataFrame({f"stop x{k}": {"all pre-2023": round(100 * book[k][0], 1), "all 2023-26": round(100 * book[k][1], 1), "exact13 pre-2023": round(100 * bookR[k][0], 1), "exact13 2023-26": round(100 * bookR[k][1], 1)} for k in KS}).to_string())
D.to_csv("stopsize_results.csv", index=False)
