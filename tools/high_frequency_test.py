# Run from the scratchpad (needs world_lab.py and 1m data).
# One EA, 5+ trades a day: N-bar trend breakouts traded all session on 1m / 3m / 5m, several markets.
import sys, numpy as np, pandas as pd
from multiprocessing import Pool
MK = {"USATECHIDXUSD": (570, 950, 955), "USA500IDXUSD": (570, 950, 955), "DEUIDXEUR": (540, 1020, 1045), "XAUUSD_NY": (500, 950, 955)}
def job(args):
    sym, tf = args
    sys.argv = ["x", sym]; ns = {}; exec(open("world_lab.py").read().split("rows, TR = [], {}")[0], ns)
    a0, a1, fl = MK[sym]; b = ns["bars"](tf); T = b.index; z = T.tz_convert(ns["TZ"]); fm = (z.hour * 60 + z.minute).to_numpy()
    C = b.c.to_numpy(); atr = ns["atr_of"](b); out = []
    for N in (20, 50):
        hi = b.h.rolling(N).max().shift(1).to_numpy(); lo = b.l.rolling(N).min().shift(1).to_numpy()
        for en in (200, 800):
            e = b.c.ewm(span=en, adjust=False).mean().to_numpy()
            for sm in (1.0, 2.0):
                for tg in (0, 2.0):
                    sig = lambda i: 1 if (C[i] > hi[i] and C[i] > e[i]) else (-1 if (C[i] < lo[i] and C[i] < e[i]) else 0)
                    stp = lambda i, d, ee, sm=sm: ee - d * sm * atr[i] if np.isfinite(atr[i]) else None
                    tr = ns["intraday_sim"](b, sig, stp, tg, fl, a0, a1, one_per_day=False)
                    if len(tr) < 200: continue
                    R = np.array([(px - ee) / abs(ee - st) * np.sign(ee - st) for et, xt, ee, st, px in tr])
                    cst = np.array([ns["COST"] * ee / abs(ee - st) for et, xt, ee, st, px in tr])
                    t = pd.DatetimeIndex([x[0] for x in tr]); A = t < pd.Timestamp("2023-01-01", tz="UTC")
                    ya = (t[A][-1] - t[A][0]).days / 365.25; yb = (t[~A][-1] - t[~A][0]).days / 365.25
                    wd = pd.bdate_range(t[0].date(), t[-1].date()).size
                    out.append(dict(market=sym, tf=tf, N=N, ema=en, stop=sm, target=tg, trades_per_day=len(R) / wd, avgR=(R - cst).mean(),
                                    yrA=(R - cst)[A].sum() / ya, yrB=(R - cst)[~A].sum() / yb, yrB_cost2=(R - 2 * cst)[~A].sum() / yb))
    return out
if __name__ == "__main__":
    jobs = [(s, tf) for s in MK for tf in ("1min", "3min", "5min")]
    with Pool(4) as p: res = p.map(job, jobs)
    df = pd.DataFrame([r for x in res for r in x]); df["minhalf"] = df[["yrA", "yrB"]].min(axis=1); df.to_pickle("hf_search.pkl")
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 100)
    hf = df[df.trades_per_day >= 5]
    print(f"{len(df)} versions, {len(hf)} with 5+ trades/day; of those positive in both halves: {(hf.minhalf > 0).sum()}, and also positive at double costs: {((hf.minhalf > 0) & (hf.yrB_cost2 > 0)).sum()}")
    print(hf.sort_values("minhalf", ascending=False).head(20).round(2).to_string(index=False))
    print("\nbusiest versions that are positive in both halves and at double costs:")
    ok = df[(df.minhalf > 0) & (df.yrB_cost2 > 0)].sort_values("trades_per_day", ascending=False)
    print(ok.head(10).round(2).to_string(index=False))
