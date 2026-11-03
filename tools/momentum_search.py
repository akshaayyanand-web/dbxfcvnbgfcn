# Time-of-day momentum family search: >=15%/yr at 1% risk in BOTH halves with stable neighbours.
import sys, numpy as np, pandas as pd, itertools
SP = sys.argv[1]
from backtest_ema_macd import load
from futures_lab import load_csv
import intraday_lab as I
from multiprocessing import Pool
MK = {"gold LDN": ("fut/XAUUSD.csv", 0.0001, "Europe/London", (16, 17)), "gold NY": ("fut/XAUUSD.csv", 0.0001, "America/New_York", (16, 17)),
      "nq NY": ("fut/USATECHIDXUSD.csv", 0.00012, "America/New_York", (16, 17)), "spx NY": ("fut/USA500IDXUSD.csv", 0.0001, "America/New_York", (16, 17)),
      "silver LDN": ("fut/XAGUSD.csv", 0.00025, "Europe/London", (16, 17)), "silver NY": ("fut/XAGUSD.csv", 0.00025, "America/New_York", (16, 17)),
      "oil NY": ("fut/LIGHTCMDUSD.csv", 0.0003, "America/New_York", (16, 17)), "btc NY": ("kh/BTCUSDT.csv", 0.0012, "America/New_York", (16, 17)),
      "eth NY": ("kh/ETHUSDT.csv", 0.0012, "America/New_York", (16, 17))}
SPLIT = pd.Timestamp("2023-01-01", tz="UTC"); START = pd.Timestamp("2020-04-01", tz="UTC"); END = pd.Timestamp("2026-10-30", tz="UTC")
def job(m):
    f, cost, tz, refs = MK[m]; df = load(SP + "/" + f) if f.startswith("kh") else load_csv(SP + "/" + f); df = df.loc["2019-06-01":]
    yA = (SPLIT - START).days / 365.25; yB = (END - SPLIT).days / 365.25; rows = []
    for ref, sig, hold, thr, both, sa in itertools.product(refs, (9, 10, 11, 12, 13), (3, 5), (0.004, 0.006, 0.008, 0.01), (True, False), (1.0, 1.5)):
        flat = min(sig + hold, 16)
        if flat <= sig: continue
        try: x = I.intraday_momentum(df, tz, ref, sig, flat, thr, True, both, cost, sa)
        except Exception as e: continue
        tr = [(a[0], (a[4] - a[2]) / (a[2] - a[3]) - cost * a[2] / abs(a[2] - a[3])) for a in x if abs(a[2] - a[3]) > 0]
        tr = [(t, r) for t, r in tr if START <= t < END]
        if len(tr) < 40: continue
        A = sum(r for t, r in tr if t < SPLIT); B = sum(r for t, r in tr if t >= SPLIT)
        rows.append(dict(market=m, ref=ref, sig=sig, flat=flat, thr=thr, both=both, stop_atr=sa, trades=len(tr), yrA=A / yA, yrB=B / yB))
    print(m, "done", flush=True); return rows
if __name__ == "__main__":
    with Pool(4) as p: res = p.map(job, list(MK))
    df = pd.DataFrame([x for r in res for x in r]); df.to_pickle(SP + "/momsearch.pkl")
    def nb(r):
        n = df[(df.market == r.market) & (df.ref == r.ref) & (df.both == r.both) & (df.stop_atr == r.stop_atr) & ((df.sig - r.sig).abs() <= 1) & ((df.thr - r.thr).abs() <= 0.0021)]
        return pd.Series({"nbA": n.yrA.median(), "nbB": n.yrB.median()})
    print(f"\n{len(df)} versions; >=10 both halves: {((df.yrA>=10)&(df.yrB>=10)).sum()}; >=15 both: {((df.yrA>=15)&(df.yrB>=15)).sum()}")
    w = df[(df.yrA >= 10) & (df.yrB >= 10)].copy()
    if len(w):
        w = pd.concat([w, w.apply(nb, axis=1)], axis=1); w["minh"] = w[["yrA", "yrB"]].min(axis=1)
        s = w[(w.nbA >= 8) & (w.nbB >= 8)]
        pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
        print(f"stable (neighbours >=8 both halves): {len(s)}"); print(s.sort_values("minh", ascending=False).groupby("market").head(4).round(1).to_string(index=False))
