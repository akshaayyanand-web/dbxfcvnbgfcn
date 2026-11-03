# Big dip-family search: >=10%/yr at 1% risk in BOTH halves, with stable neighbours; then replacement test.
import sys, numpy as np, pandas as pd, itertools
SP = sys.argv[1]
from backtest_ema_macd import load
from futures_lab import load_csv
from portfolio_prop import resample, rsi, rma
from multiprocessing import Pool
MK = {"btc": ("kh/BTCUSDT.csv", 0.0012, 0.15), "eth": ("kh/ETHUSDT.csv", 0.0012, 0.15), "sol": ("kh/SOLUSDT.csv", 0.0012, 0.2),
      "gold": ("fut/XAUUSD.csv", 0.0001, 0.08), "silver": ("fut/XAGUSD.csv", 0.00025, 0.12), "nq": ("fut/USATECHIDXUSD.csv", 0.00012, 0.08),
      "spx": ("fut/USA500IDXUSD.csv", 0.0001, 0.08), "dow": ("fut/USA30IDXUSD.csv", 0.00012, 0.08), "oil": ("fut/LIGHTCMDUSD.csv", 0.0003, 0.15)}
SPLIT = pd.Timestamp("2023-01-01", tz="UTC"); START = pd.Timestamp("2020-04-01", tz="UTC"); END = pd.Timestamp("2026-10-30", tz="UTC")
def get(m):
    f, c, cr = MK[m]; d = load(SP + "/" + f) if f.startswith("kh") else load_csv(SP + "/" + f)
    return d.loc["2019-06-01":], c, cr
def dip3(raw, tf, rl, buy, ema_n, hold_h, crash, cost):
    b = resample(raw, tf) if tf != "1h" else raw; c = b.c
    d = raw.c.resample("1D").last().dropna()
    blk = (d / d.shift(30) - 1 < -crash).shift(1).reindex(b.index.floor("D")).fillna(False).to_numpy().astype(bool)
    sig = ((rsi(c, rl) < buy) & (c > c.ewm(span=ema_n, adjust=False).mean())).to_numpy() & ~blk
    tr = pd.concat([b.h - b.l, (b.h - c.shift()).abs(), (b.l - c.shift()).abs()], axis=1).max(axis=1); atr = rma(tr, 14).to_numpy()
    O_, L, C, T = b.o.to_numpy(), b.l.to_numpy(), c.to_numpy(), b.index; bar = T[1] - T[0]; mb = max(1, int(pd.Timedelta(f"{hold_h}h") / bar))
    out = []; i = 0
    while i < len(C) - 2:
        if not sig[i] or np.isnan(atr[i]): i += 1; continue
        j = i + 1; e, st = O_[j], C[i] - 2 * atr[i]
        if e <= st: i += 1; continue
        k, px = j, None
        while k < len(C) - 1:
            if L[k] <= st: px = min(O_[k], st); break
            if k - j + 1 >= mb: px = O_[k + 1]; k += 1; break
            k += 1
        if px is None: break
        if T[min(k, len(T) - 1)] - T[j] <= pd.Timedelta(days=12 + hold_h / 24): out.append((T[j], (px - e) / (e - st) - cost * e / (e - st)))
        i = k
    return out
GRID = list(itertools.product(["1h", "2h", "4h"], [2, 3], [5, 10, 15, 20, 25], [50, 100, 200], [48, 96, 144]))
def job(m):
    raw, cost, cr = get(m); rows = []
    yA = (SPLIT - START).days / 365.25; yB = (END - SPLIT).days / 365.25
    for tf, rl, buy, en, hold in GRID:
        tr = [(t, r) for t, r in dip3(raw, tf, rl, buy, en, hold, cr, cost) if START <= t < END]
        if len(tr) < 30: continue
        A = sum(r for t, r in tr if t < SPLIT); B = sum(r for t, r in tr if t >= SPLIT)
        rows.append(dict(market=m, tf=tf, rsi=rl, buy=buy, ema=en, hold=hold, trades=len(tr), yrA=A / yA, yrB=B / yB))   # R per year = %/yr at 1% risk
    print(m, "done", flush=True); return rows
if __name__ == "__main__":
    with Pool(4) as p: res = p.map(job, list(MK))
    df = pd.DataFrame([x for r in res for x in r]); df.to_pickle(SP + "/dipsearch.pkl")
    # neighbour stability: same market/tf/rsi/ema, buy +-5 and hold +-48
    def neigh(r):
        n = df[(df.market == r.market) & (df.tf == r.tf) & (df.rsi == r.rsi) & (df.ema == r.ema) & ((df.buy - r.buy).abs() <= 5) & ((df.hold - r.hold).abs() <= 48)]
        return pd.Series({"nbA": n.yrA.median(), "nbB": n.yrB.median()})
    win = df[(df.yrA >= 10) & (df.yrB >= 10)].copy()
    print(f"\n{len(df)} versions tested; >=10%/yr in both halves: {len(win)}")
    if len(win):
        win = pd.concat([win, win.apply(neigh, axis=1)], axis=1); win["stable"] = (win.nbA >= 8) & (win.nbB >= 8)
        pd.set_option("display.width", 250); pd.set_option("display.max_rows", 300)
        print(win.sort_values(["stable", "yrB"], ascending=False).round(1).to_string(index=False))
    print("\nby market: best min(half) per market"); df["minhalf"] = df[["yrA", "yrB"]].min(axis=1)
    print(df.sort_values("minhalf", ascending=False).groupby("market").head(1).round(1).to_string(index=False))
