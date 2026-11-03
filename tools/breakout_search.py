# Breakout family search (1h range breakouts + 5m opening ranges): >=15%/yr at 1% risk in BOTH halves, stable neighbours.
import sys, numpy as np, pandas as pd, itertools
SP = sys.argv[1]
from backtest_ema_macd import load
from futures_lab import load_csv
import intraday_lab as I, orb_lab as O
from multiprocessing import Pool
SPLIT = pd.Timestamp("2023-01-01", tz="UTC"); START = pd.Timestamp("2020-04-01", tz="UTC"); END = pd.Timestamp("2026-10-30", tz="UTC")
yA = (SPLIT - START).days / 365.25; yB = (END - SPLIT).days / 365.25
def score(x, cost):
    tr = [(a[0], (a[4] - a[2]) / (a[2] - a[3]) - cost * a[2] / abs(a[2] - a[3])) for a in x if abs(a[2] - a[3]) > 0]
    tr = [(t, r) for t, r in tr if START <= t < END]
    if len(tr) < 40: return None
    return len(tr), sum(r for t, r in tr if t < SPLIT) / yA, sum(r for t, r in tr if t >= SPLIT) / yB
H1 = {"gold LDN": ("fut/XAUUSD.csv", 0.0001, "Europe/London", [(0, 7), (0, 8), (2, 7)], [16, 20]),
      "gold NY": ("fut/XAUUSD.csv", 0.0001, "America/New_York", [(0, 8), (3, 8), (18, 2)], [15, 16]),
      "nq NY": ("fut/USATECHIDXUSD.csv", 0.00012, "America/New_York", [(0, 9), (4, 9), (18, 3)], [15, 16]),
      "spx NY": ("fut/USA500IDXUSD.csv", 0.0001, "America/New_York", [(0, 9), (4, 9), (18, 3)], [15, 16]),
      "silver LDN": ("fut/XAGUSD.csv", 0.00025, "Europe/London", [(0, 7), (0, 8)], [16, 20]),
      "oil NY": ("fut/LIGHTCMDUSD.csv", 0.0003, "America/New_York", [(0, 9), (4, 9)], [14, 16]),
      "btc UTC": ("kh/BTCUSDT.csv", 0.0012, "UTC", [(0, 8), (0, 12)], [20, 23])}
def job_h1(m):
    f, cost, tz, ranges, flats = H1[m]; df = load(SP + "/" + f) if f.startswith("kh") else load_csv(SP + "/" + f); df = df.loc["2019-06-01":]
    rows = []
    for (r0, r1), fl, ew, sm, tg, both in itertools.product(ranges, flats, (3, 6), ("mid", "other"), (None, 1.5, 2.0, 3.0), (True, False)):
        w0 = r1 if r1 > r0 else r1; w1 = min(w0 + ew, fl - 1)
        if w1 <= w0: continue
        try: x = I.range_breakout(df, tz, r0, r1, w0, w1, fl, sm, tg, both, cost)
        except Exception: continue
        s = score([a[:5] for a in x], cost)
        if s: rows.append(dict(family="1h range", market=m, rng=f"{r0}-{r1}", flat=fl, entry_hours=ew, stop=sm, target=tg, both=both, trades=s[0], yrA=s[1], yrB=s[2]))
    print(m, "done", flush=True); return rows
M5 = {"nq": ("fut1m/USATECHIDXUSD_1m.csv", 0.00012, [("NY 9:30", "America/New_York", (9, 30), (15, 55))]),
      "spx": ("fut1m/USA500IDXUSD_1m.csv", 0.0001, [("NY 9:30", "America/New_York", (9, 30), (15, 55))]),
      "gold": ("fut1m/XAUUSD_1m.csv", 0.0001, [("COMEX 8:20", "America/New_York", (8, 20), (15, 55)), ("LDN 8:00", "Europe/London", (8, 0), (16, 0)),
                                               ("NY 9:30", "America/New_York", (9, 30), (15, 55))])}
def job_m5(m):
    f, cost, sess = M5[m]; d5 = O.five_min(load_csv(SP + "/" + f)); rows = []
    for (lab, tz, st, fl), mins, le_h, sm, tg, both in itertools.product(sess, (5, 15, 30, 60), (1.5, 3.5), ("other", "mid"), (1.0, 2.0, 3.0, None), (True, False)):
        le = (st[0] + int(le_h) + (1 if (st[1] + int((le_h % 1) * 60)) >= 60 else 0), (st[1] + int((le_h % 1) * 60)) % 60)
        try: x = O.orb(d5, tz, st, le, fl, mins, sm, tg, both, cost)
        except Exception: continue
        s = score([a[:5] for a in x], cost)
        if s: rows.append(dict(family="5m opening range", market=f"{m} {lab}", rng=f"{mins}m", flat=f"{fl[0]}:{fl[1]:02d}", entry_hours=le_h, stop=sm, target=tg, both=both, trades=s[0], yrA=s[1], yrB=s[2]))
    print(m, "5m done", flush=True); return rows
def job(k): return job_h1(k[1]) if k[0] == "h1" else job_m5(k[1])
if __name__ == "__main__":
    with Pool(4) as p: res = p.map(job, [("m5", m) for m in M5] + [("h1", m) for m in H1])
    df = pd.DataFrame([x for r in res for x in r]); df.to_pickle(SP + "/breaksearch.pkl")
    print(f"\n{len(df)} versions; >=10 both halves: {((df.yrA>=10)&(df.yrB>=10)).sum()}; >=15 both: {((df.yrA>=15)&(df.yrB>=15)).sum()}")
    w = df[(df.yrA >= 10) & (df.yrB >= 10)].copy()
    if len(w):
        def nb(r):   # neighbours: same market/family/range/both, any stop/target/entry window except itself
            n = df[(df.market == r.market) & (df.family == r.family) & (df.rng == r.rng) & (df.both == r.both) & (df.stop == r.stop)]
            return pd.Series({"nbA": n.yrA.median(), "nbB": n.yrB.median(), "n_nb": len(n)})
        w = pd.concat([w, w.apply(nb, axis=1)], axis=1); w["minh"] = w[["yrA", "yrB"]].min(axis=1)
        pd.set_option("display.width", 260); pd.set_option("display.max_rows", 200)
        print(w.sort_values("minh", ascending=False).head(30).round(1).to_string(index=False))
