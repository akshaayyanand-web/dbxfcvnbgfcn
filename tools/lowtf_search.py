# Low-timeframe (5m / 15m) strategy search on gold, Nasdaq, S&P. Score at 1% risk per trade, both halves, trades/month.
import sys, numpy as np, pandas as pd, itertools
SP = sys.argv[1]
from futures_lab import load_csv
from portfolio_prop import rsi, rma
from multiprocessing import Pool
MK = {"gold": ("fut1m/XAUUSD_1m.csv", 0.0001), "nq": ("fut1m/USATECHIDXUSD_1m.csv", 0.00012), "spx": ("fut1m/USA500IDXUSD_1m.csv", 0.0001)}
SPLIT = pd.Timestamp("2023-01-01", tz="UTC"); START = pd.Timestamp("2019-03-01", tz="UTC")
def bars(m, rule):
    d = load_csv(SP + "/" + MK[m][0]); return d.resample(rule).agg(dict(o="first", h="max", l="min", c="last")).dropna().loc[START:]
def sim(b, L, S, stopdist, hold, flat=None, tgtR=None):
    O, H, Lo, C, T = b.o.to_numpy(), b.h.to_numpy(), b.l.to_numpy(), b.c.to_numpy(), b.index; n = len(C); out = []; i = 0
    while i < n - 2:
        d = 1 if L[i] else (-1 if S is not None and S[i] else 0)
        if d == 0 or not np.isfinite(stopdist[i]) or stopdist[i] <= 0: i += 1; continue
        j = i + 1; e = O[j]; st = e - d * stopdist[i]; tg = e + d * tgtR * stopdist[i] if tgtR else None; k = j; px = None
        while k < n - 1:
            if (Lo[k] <= st) if d == 1 else (H[k] >= st): px = min(O[k], st) if d == 1 else max(O[k], st); break
            if tg is not None and ((H[k] >= tg) if d == 1 else (Lo[k] <= tg)): px = max(O[k], tg) if d == 1 else min(O[k], tg); break
            if k - j + 1 >= hold or (flat is not None and flat[k]) or T[k + 1] - T[k] > pd.Timedelta(hours=6): px = O[k + 1] if T[k + 1] - T[k] <= pd.Timedelta(hours=6) else C[k]; k += 1; break
            k += 1
        if px is None: break
        out.append((T[j], d * (px - e) / abs(e - st)))
        i = k
    return out
def score(tr, cost_frac, b, stopdist):
    if len(tr) < 60: return None
    t = np.array([x[0] for x in tr]); r = np.array([x[1] for x in tr])
    yrs_a = (SPLIT - START).days / 365.25; yrs_b = (b.index[-1] - SPLIT).days / 365.25
    return len(tr) / ((b.index[-1] - START).days / 30.44), r[t < SPLIT].sum() / yrs_a, r[t >= SPLIT].sum() / yrs_b
def job(arg):
    m, rule = arg; b = bars(m, rule); cost = MK[m][1]
    c = b.c; C = c.to_numpy(); tr_ = pd.concat([b.h - b.l, (b.h - c.shift()).abs(), (b.l - c.shift()).abs()], axis=1).max(axis=1); atr = rma(tr_, 14).to_numpy()
    loc_ny = b.index.tz_convert("America/New_York"); loc_ld = b.index.tz_convert("Europe/London")
    nymin = loc_ny.hour * 60 + loc_ny.minute; ldmin = loc_ld.hour * 60 + loc_ld.minute
    flat_ny = nymin >= 15 * 60 + 50; flat_ld = ldmin >= 16 * 60 + 50
    bpd = {"5min": 288, "15min": 96}[rule]; rows = []
    costR = lambda stopd: cost * C / stopd           # cost in R units per trade
    def add(fam, params, tr, sd):
        if not tr: return
        cr = np.interp(np.arange(len(tr)), [0], [0])  # placeholder
        # subtract cost in R using the stop distance at entry
        ts = pd.DatetimeIndex([x[0] for x in tr]); pos = b.index.get_indexer(ts) - 1
        rr = [(x[0], x[1] - cost * C[p] / sd[p]) for x, p in zip(tr, pos)]
        s = score(rr, cost, b, sd)
        if s: rows.append(dict(market=m, tf=rule, family=fam, params=params, trades_mo=s[0], yrA=s[1], yrB=s[2]))
    # 1) dip buying with a slow trend filter
    for rl, buy, en, hold_h in itertools.product((2, 3), (5, 10, 20), (200, 800), (2, 8, 24)):
        r = rsi(c, rl).to_numpy(); e = c.ewm(span=en, adjust=False).mean().to_numpy()
        L = (r < buy) & (C > e); sd = 2 * atr; hold = int(hold_h * bpd / 24)
        add("dip", f"RSI{rl}<{buy} EMA{en} hold {hold_h}h", sim(b, L, None, sd, hold), sd)
    # 2) session breakout of N-bar high/low with trend, flat at session end
    for N, sess, en, sa in itertools.product((20, 50), ("London 07-12", "NY 09:30-12"), (200, 800), (1.0, 2.0)):
        hi = b.h.rolling(N).max().shift(1).to_numpy(); lo_ = b.l.rolling(N).min().shift(1).to_numpy(); e = c.ewm(span=en, adjust=False).mean().to_numpy()
        win = ((ldmin >= 420) & (ldmin < 720)) if sess.startswith("London") else ((nymin >= 570) & (nymin < 720))
        L = win & (C > hi) & (C > e); S = win & (C < lo_) & (C < e); sd = sa * atr
        fl = flat_ld if sess.startswith("London") else flat_ny
        add("breakout", f"{N}-bar {sess} EMA{en} stop {sa}ATR", sim(b, L, S, sd, 10 ** 6, flat=fl), sd)
    # 3) big-candle momentum / reversal
    body = (b.c - b.o).to_numpy()
    for k, mode, hold_h, sess in itertools.product((1.5, 2.5), ("follow", "fade"), (1, 4), ("any", "NY")):
        big = np.abs(body) > k * atr
        if sess == "NY": big &= (nymin >= 570) & (nymin < 900)
        up = big & (body > 0); dn = big & (body < 0)
        L, S = (up, dn) if mode == "follow" else (dn, up); sd = 1.5 * atr
        add("big candle", f"{mode} >{k}ATR {sess} hold {hold_h}h", sim(b, L, S, sd, int(hold_h * bpd / 24)), sd)
    print(m, rule, "done", len(rows), flush=True)
    return rows
if __name__ == "__main__":
    with Pool(3) as p: res = p.map(job, [(m, r) for m in MK for r in ("15min", "5min")])
    df = pd.DataFrame([x for r in res for x in r]); df.to_pickle(SP + "/lowtf.pkl")
    df["minhalf"] = df[["yrA", "yrB"]].min(axis=1)
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 120)
    print(f"\n{len(df)} versions; >=10%/yr both halves: {(df.minhalf >= 10).sum()}; of those >= 8 trades/month: {((df.minhalf >= 10) & (df.trades_mo >= 8)).sum()}")
    print(df.sort_values("minhalf", ascending=False).head(30).round(1).to_string(index=False))
    print("\nby family (median %/yr):"); print(df.groupby(["family", "tf"])[["yrA", "yrB", "trades_mo"]].median().round(1).to_string())
