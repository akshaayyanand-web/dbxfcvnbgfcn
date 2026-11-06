# Generic index ORB/breakout/dip lab. Run from the scratchpad: python world_lab.py SYMBOL
# DAX (Germany 40) strategies on the Frankfurt session: opening range breakout, morning breakout, dips.
import sys, numpy as np, pandas as pd
sys.path.insert(0, "/home/user/dbxfcvnbgfcn/tools")
from portfolio_prop import load_csv, rsi, rma
import glob, io
SYM = sys.argv[1]
CFG = {"JPNIDXJPY": ("Asia/Tokyo", 540, 690, 895, 0.0002), "HKGIDXHKD": ("Asia/Hong_Kong", 570, 720, 955, 0.0003),
       "GBRIDXGBP": ("Europe/London", 480, 660, 985, 0.00012), "AUSIDXAUD": ("Australia/Sydney", 600, 750, 955, 0.0002),
       "DEUIDXEUR": ("Europe/Berlin", 540, 720, 1045, 0.0001)}
TZ, OPEN, WEND, FLAT, COST = CFG[SYM]
parts = []
for f in sorted(glob.glob(f"world1m/{SYM}/*.csv") if SYM != "DEUIDXEUR" else glob.glob("eu1m/days/*.csv")):
    t = open(f).read().strip()
    if t: parts.append(pd.read_csv(io.StringIO(t), header=None, names=["t", "o", "h", "l", "c", "v"]))
raw = pd.concat(parts); raw["t"] = pd.to_datetime(raw.t, unit="s", utc=True); raw = raw.drop_duplicates("t").set_index("t").sort_index()
print(SYM, len(raw), "rows", raw.index.normalize().nunique(), "days", flush=True)
def bars(rule): return raw.resample(rule).agg(dict(o="first", h="max", l="min", c="last")).dropna().loc["2019-03-01":]
def atr_of(b, n=14):
    c = b.c; return rma(pd.concat([b.h - b.l, (b.h - c.shift()).abs(), (b.l - c.shift()).abs()], axis=1).max(axis=1), n).to_numpy()
def stats(trades, name):
    r = np.array([(px - e) / abs(e - st) * np.sign(e - st) - COST * e / abs(e - st) for et, xt, e, st, px in trades])
    r2 = r - np.array([COST * e / abs(e - st) for et, xt, e, st, px in trades])
    t = pd.DatetimeIndex([x[0] for x in trades]); A = t < pd.Timestamp("2023-01-01", tz="UTC")
    ya = (t[A][-1] - t[A][0]).days / 365.25; yb = (t[~A][-1] - t[~A][0]).days / 365.25
    return dict(edge=name, trades_mo=len(r) / ((t[-1] - t[0]).days / 30.4), win=100 * (r > 0).mean(), avgR=r.mean(),
                yrA=r[A].sum() / ya, yrB=r[~A].sum() / yb, yr_cost2=r2.sum() / ((t[-1] - t[0]).days / 365.25))
def intraday_sim(b, sig_fn, stop_fn, target_R, flat_min, start_min, end_min, one_per_day=True):
    """Generic Frankfurt-session day trade on bars b. sig_fn(i) -> +1/-1/0 at bar i close; entry next bar open."""
    T = b.index; fr = T.tz_convert(TZ); fm = (fr.hour * 60 + fr.minute).to_numpy(); fday = fr.normalize()
    O, H, L, C = (b[k].to_numpy() for k in "ohlc"); n = len(C); out = []; i = 0; traded = None
    while i < n - 2:
        if not (start_min <= fm[i] < end_min) or (one_per_day and traded == fday[i]): i += 1; continue
        d = sig_fn(i)
        if d == 0: i += 1; continue
        j = i + 1
        if fday[j] != fday[i]: i += 1; continue
        e = O[j]; st = stop_fn(i, d, e)
        if st is None or (st - e) * d >= 0: i += 1; continue
        R1 = abs(e - st); tg = e + d * target_R * R1 if target_R else None; px = None; k = j
        while k < n:
            if fday[k] != fday[j] or fm[k] >= flat_min: px, xt = O[k], T[k]; break
            if (L[k] <= st) if d == 1 else (H[k] >= st): px, xt = (min(O[k], st) if d == 1 else max(O[k], st)), T[k]; break
            if tg is not None and ((H[k] >= tg) if d == 1 else (L[k] <= tg)): px, xt = (max(O[k], tg) if d == 1 else min(O[k], tg)), T[k]; break
            k += 1
        if px is None: break
        out.append((T[j], xt, e, st, px)); traded = fday[i]; i = k + 1
    return out
rows, TR = [], {}
for tf in ("5min", "15min"):
    b = bars(tf); T = b.index; fr = T.tz_convert(TZ); fm = (fr.hour * 60 + fr.minute).to_numpy(); fday = fr.normalize()
    C = b.c.to_numpy(); H = b.h.to_numpy(); L = b.l.to_numpy(); atr = atr_of(b)
    dc = b.c.resample("1D").last().dropna(); ema_d = {n: dc.ewm(span=n, adjust=False).mean().shift(1).reindex(T.floor("D"), method="ffill").to_numpy() for n in (20, 50)}
    # opening range: first N minutes after 09:00 Frankfurt
    for N in (15, 30, 60):
        if tf == "15min" and N == 15: continue
        inr = (fm >= OPEN) & (fm < OPEN + N)
        g = pd.DataFrame({"h": np.where(inr, H, np.nan), "l": np.where(inr, L, np.nan), "d": fday}).groupby("d").agg(h=("h", "max"), l=("l", "min"))
        orh = g.h.reindex(fday).to_numpy(); orl = g.l.reindex(fday).to_numpy()
        for trend in (None, 20, 50):
            for tgt in (0, 1.5, 2.0, 3.0):
                for stop in ("other", "mid"):
                    def sig(i, trend=trend):
                        if not np.isfinite(orh[i]): return 0
                        d = 1 if C[i] > orh[i] else (-1 if C[i] < orl[i] else 0)
                        if d and trend: d = d if (C[i] - ema_d[trend][i]) * d > 0 else 0
                        return d
                    def stp(i, d, e, stop=stop):
                        return (orl[i] if d == 1 else orh[i]) if stop == "other" else (orh[i] + orl[i]) / 2
                    tr = intraday_sim(b, sig, stp, tgt, FLAT, OPEN + N, WEND)
                    nm = f"{SYM[:3]} {tf} ORB{N} trend{trend} target{tgt} stop-{stop}"
                    if len(tr) > 50: rows.append(stats(tr, nm)); TR[nm] = tr
    # morning breakout (like NQ_Breakout_15m): close beyond 20/50-bar high/low with EMA filter, stop 1 ATR, flat 17:25
    for nb in (20, 50):
        hi = b.h.rolling(nb).max().shift(1).to_numpy(); lo = b.l.rolling(nb).min().shift(1).to_numpy()
        for en in (200, 800):
            e_ = b.c.ewm(span=en, adjust=False).mean().to_numpy()
            for sm in (1.0, 2.0):
                def sig(i): return 1 if (C[i] > hi[i] and C[i] > e_[i]) else (-1 if (C[i] < lo[i] and C[i] < e_[i]) else 0)
                def stp(i, d, e, sm=sm): return e - d * sm * atr[i] if np.isfinite(atr[i]) else None
                tr = intraday_sim(b, sig, stp, 0, FLAT, OPEN, WEND, one_per_day=False)
                nm = f"{SYM[:3]} {tf} breakout{nb} EMA{en} stop{sm}ATR"
                if len(tr) > 50: rows.append(stats(tr, nm)); TR[nm] = tr
# dips on 1h / 2h (same rule family as the other dip EAs), 48-144 bar holds
for tf in ("1h", "2h"):
    b = bars(tf); c = b.c; O, H, L, C, T = (b[k].to_numpy() for k in "ohlc"), None, None, None, b.index
    O = b.o.to_numpy(); L = b.l.to_numpy(); C = c.to_numpy(); atr = atr_of(b); dc = c.resample("1D").last().dropna()
    crash = (dc / dc.shift(30) - 1).shift(1).reindex(T.floor("D"), method="ffill").to_numpy()
    for rl, buy in ((2, 10), (2, 15), (2, 25), (3, 20)):
        r_ = rsi(c, rl).to_numpy()
        for en in (50, 200):
            e_ = c.ewm(span=en, adjust=False).mean().to_numpy()
            for hold in (48, 96, 144):
                out, i = [], 0
                while i < len(C) - 2:
                    if not (r_[i] < buy and C[i] > e_[i] and np.isfinite(atr[i]) and (crash[i] > -0.08 if np.isfinite(crash[i]) else True)): i += 1; continue
                    j = i + 1; e = O[j]; st = C[i] - 2 * atr[i]
                    if e <= st: i += 1; continue
                    k, px = j, None
                    while k < len(C) - 1:
                        if L[k] <= st: px, xt = min(O[k], st), T[k]; break
                        if k - j + 1 >= hold: px, xt = O[k + 1], T[k + 1]; k += 1; break
                        k += 1
                    if px is None: break
                    out.append((T[j], xt, e, st, px)); i = k
                nm = f"{SYM[:3]} {tf} dip RSI{rl}<{buy} EMA{en} hold{hold}"
                if len(out) > 30: rows.append(stats(out, nm)); TR[nm] = out
df = pd.DataFrame(rows); df["minhalf"] = df[["yrA", "yrB"]].min(axis=1)
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 300)
print(f"{len(df)} versions; >=10%/yr both halves: {(df.minhalf >= 10).sum()}; positive both: {(df.minhalf > 0).sum()}")
print(df.sort_values("minhalf", ascending=False).head(30).round(2).to_string(index=False))
df["fam"] = df.edge.str.split(" ").str[:3].str.join(" ")
print(df.groupby("fam")[["yrA", "yrB", "trades_mo"]].median().round(1).to_string())
pd.to_pickle((df, TR), f"world_{SYM}.pkl")
