# Run from the scratchpad.
# Morning-breakout rule moved to other sessions / markets.
import sys, numpy as np, pandas as pd
SP = "."
exec(open("lowtf_port.py").read().split("def bars1")[0].split("from multiprocessing")[0]) if False else None
sys.path.insert(0, "/home/user/dbxfcvnbgfcn/tools")
from portfolio_prop import load_csv, rma
src = open("lowtf_port.py").read(); exec("def bars1" + src.split("def bars1", 1)[1].split("def cands")[0])
from multiprocessing import Pool
FILES = {"nq": ("fut1m/USATECHIDXUSD_1m.csv", 0.00012), "spx": ("fut1m/USA500IDXUSD_1m.csv", 0.0001), "gold": ("fut1m/XAUUSD_1m.csv", 0.0001)}
WIN = {"london 03-06": (180, 360, 690), "ny-am 09:30-12": (570, 720, 950), "ny-pm 13-15:30": (780, 930, 950), "asia 20-02": (1200, 120, 180)}
def run(args):
    mk, tf = args; b = bars1(FILES[mk][0], tf); cost = FILES[mk][1]; c = b.c; Cc = c.to_numpy()
    atr = rma(pd.concat([b.h - b.l, (b.h - c.shift()).abs(), (b.l - c.shift()).abs()], axis=1).max(axis=1), 14).to_numpy()
    ny = b.index.tz_convert("America/New_York"); m = (ny.hour * 60 + ny.minute).to_numpy(); rows = []
    for wn, (a, z, fl) in WIN.items():
        win = ((m >= a) & (m < z)) if a < z else ((m >= a) | (m < z))
        flat = (m >= fl) & (m < fl + 60) if wn == "asia 20-02" else (m >= fl)
        for N in (20, 50):
            hi = b.h.rolling(N).max().shift(1).to_numpy(); lo = b.l.rolling(N).min().shift(1).to_numpy()
            for en in (200, 800):
                e = c.ewm(span=en, adjust=False).mean().to_numpy()
                for sm in (1.0, 2.0):
                    tr = simT(b, win & (Cc > hi) & (Cc > e), win & (Cc < lo) & (Cc < e), sm * atr, 10 ** 6, flat)
                    if len(tr) < 50: continue
                    R = np.array([(px - en_) / abs(en_ - st) * np.sign(en_ - st) - cost * en_ / abs(en_ - st) for et, xt, en_, st, px in tr])
                    R2 = R - np.array([cost * en_ / abs(en_ - st) for et, xt, en_, st, px in tr])
                    t = pd.DatetimeIndex([x[0] for x in tr]); A = t < pd.Timestamp("2023-01-01", tz="UTC")
                    ya = (t[A][-1] - t[A][0]).days / 365.25; yb = (t[~A][-1] - t[~A][0]).days / 365.25
                    rows.append(dict(mk=mk, tf=tf, window=wn, N=N, ema=en, stop=sm, trades_mo=len(R) / ((t[-1] - t[0]).days / 30.4),
                                     yrA=R[A].sum() / ya, yrB=R[~A].sum() / yb, yrB_cost2=R2[~A].sum() / yb))
    return rows
if __name__ == "__main__":
    with Pool(4) as p: res = p.map(run, [(mk, tf) for mk in FILES for tf in ("5min", "15min")])
    df = pd.DataFrame([r for x in res for r in x]); df["minhalf"] = df[["yrA", "yrB"]].min(axis=1); df.to_pickle("session_bo.pkl")
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 300)
    print(f"{len(df)} versions; >=15%/yr both halves: {(df.minhalf >= 15).sum()}; >=10: {(df.minhalf >= 10).sum()}")
    print(df.sort_values("minhalf", ascending=False).head(30).round(1).to_string(index=False))
    print(df.groupby(["mk", "window"])[["yrA", "yrB", "yrB_cost2"]].median().round(1).to_string())
