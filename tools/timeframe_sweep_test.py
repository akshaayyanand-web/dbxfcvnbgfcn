# Timeframe sweep (M15/M30/H1/H2) of ORB, momentum breakout and dip families on broker exports: US30, XAGUSD (M5, Apr/Jun 2025-Nov 2026), GBPJPY H1 2020-2026. Run: python timeframe_sweep_test.py US30
# DAX (Germany 40) strategies on the Frankfurt session: opening range breakout, morning breakout, dips.
import sys, numpy as np, pandas as pd
sys.path.insert(0, "/home/user/dbxfcvnbgfcn/tools")
from portfolio_prop import load_csv, rsi, rma
import glob, io
SYM = sys.argv[1]
CFG = {"JPNIDXJPY": ("Asia/Tokyo", 540, 690, 895, 0.0002), "HKGIDXHKD": ("Asia/Hong_Kong", 570, 720, 955, 0.0003),
       "GBRIDXGBP": ("Europe/London", 480, 660, 985, 0.00012), "AUSIDXAUD": ("Australia/Sydney", 600, 750, 955, 0.0002),
       "DEUIDXEUR": ("Europe/Berlin", 540, 720, 1045, 0.0001),
       "USATECHIDXUSD": ("America/New_York", 570, 720, 955, 0.00012), "USA500IDXUSD": ("America/New_York", 570, 720, 955, 0.0001),
       "XAUUSD": ("Europe/London", 480, 660, 985, 0.0001), "XAUUSD_NY": ("America/New_York", 500, 690, 955, 0.0001),
       "EURUSD": ("Europe/London", 480, 660, 985, 0.00006), "EURUSD_ASIA": ("Europe/London", 0, 600, 985, 0.00006),
       "AUDCAD": ("Europe/London", 480, 660, 985, 0.00009),
       "BTCUSDT": ("America/New_York", 570, 720, 950, 0.0006), "ETHUSDT": ("America/New_York", 570, 720, 950, 0.0008), "US30": ("America/New_York", 570, 720, 955, 0.0001), "XAGUSD": ("Europe/London", 480, 660, 985, 0.0006), "XAGUSD_NY": ("America/New_York", 500, 690, 955, 0.0006), "GBPJPY": ("Europe/London", 480, 660, 985, 0.00015), "GBPJPY_H1": ("Europe/London", 480, 660, 985, 0.00015), "GBPJPY_ASIA": ("Asia/Tokyo", 540, 690, 895, 0.00015), "SOLUSDT": ("America/New_York", 570, 720, 950, 0.0015), "XRPUSDT": ("America/New_York", 570, 720, 950, 0.0015),
       "BTCUSDT_LDN": ("Europe/London", 480, 660, 985, 0.0006),
       "XAUUSD_ASIA": ("Europe/London", 0, 840, 1200, 0.0001), "USATECHIDXUSD_ASIA": ("Europe/London", 0, 840, 1200, 0.00012)}
TZ, OPEN, WEND, FLAT, COST = CFG[SYM]
FILES = {"US30": "31e2744b-.US30Cash_M5_202504030835_202611111855.csv", "GBPJPY": "b42efa34-GBPJPY_M5_202507030005_202611111900.csv",
         "XAGUSD": "0f502386-XAGUSD_M5_202506110100_202611111900.csv", "XAGUSD_NY": "0f502386-XAGUSD_M5_202506110100_202611111900.csv",
         "GBPJPY_ASIA": "b42efa34-GBPJPY_M5_202507030005_202611111900.csv", "GBPJPY_H1": "d6b8d649-GBPJPY_H1_202001021000_202611111900.csv"}
_br = pd.read_csv("/root/.claude/uploads/0ea82c59-9b45-5b6c-b663-efd40f90c87c/" + FILES[SYM], sep="\t"); _br.columns = [c.strip("<>").lower() for c in _br.columns]
_naive = pd.to_datetime(_br.date + " " + _br.time, format="%Y.%m.%d %H:%M:%S")
_ny = _naive.dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT")
_off = np.where(np.array([bool(x.dst()) if x is not pd.NaT else True for x in _ny]), 3, 2)
raw = pd.DataFrame({"o": _br.open.values, "h": _br.high.values, "l": _br.low.values, "c": _br.close.values},
                   index=(_naive - pd.to_timedelta(_off, unit="h")).dt.tz_localize("UTC")).sort_index(); raw = raw[~raw.index.duplicated()]
SPLIT = raw.index[0] + (raw.index[-1] - raw.index[0]) / 2
print(SYM, len(raw), "rows", raw.index.normalize().nunique(), "days", flush=True)
def bars(rule): return raw.resample(rule).agg(dict(o="first", h="max", l="min", c="last")).dropna()
def atr_of(b, n=14):
    c = b.c; return rma(pd.concat([b.h - b.l, (b.h - c.shift()).abs(), (b.l - c.shift()).abs()], axis=1).max(axis=1), n).to_numpy()
def stats(trades, name):
    r = np.array([(px - e) / abs(e - st) * np.sign(e - st) - COST * e / abs(e - st) for et, xt, e, st, px in trades])
    r2 = r - np.array([COST * e / abs(e - st) for et, xt, e, st, px in trades])
    t = pd.DatetimeIndex([x[0] for x in trades]); A = t < SPLIT
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

NATIVE = 60 if SYM.endswith("_H1") else 5
TFS = [t for t in (15, 30, 60, 120) if t >= NATIVE]
rows, TR = [], {}
def add(tr, nm, tf):
    if len(tr) >= 25:
        d = stats(tr, nm); d["tf"] = f"{tf}m"; d["fam"] = nm.split(" ")[0]; rows.append(d); TR[nm + f" @{tf}m"] = tr
for tf in TFS:
    b = bars(f"{tf}min"); T = b.index; fr = T.tz_convert(TZ); fm = (fr.hour * 60 + fr.minute).to_numpy(); fday = fr.normalize()
    O, H, L, C = (b[k].to_numpy() for k in "ohlc"); atr = atr_of(b)
    dc = b.c.resample("1D").last().dropna(); ema_d = {n: dc.ewm(span=n, adjust=False).mean().shift(1).reindex(T.floor("D"), method="ffill").to_numpy() for n in (20, 50)}
    if tf <= 60:   # opening range = first 60 minutes of the session
        N = 60; inr = (fm >= OPEN) & (fm < OPEN + N)
        g = pd.DataFrame({"h": np.where(inr, H, np.nan), "l": np.where(inr, L, np.nan), "d": fday}).groupby("d").agg(h=("h", "max"), l=("l", "min"))
        orh = g.h.reindex(fday).to_numpy(); orl = g.l.reindex(fday).to_numpy()
        for trend in (None, 20, 50):
            for tgt in (0, 1.5, 3.0):
                for stop in ("other", "mid"):
                    def sig(i, trend=trend):
                        if not np.isfinite(orh[i]): return 0
                        d = 1 if C[i] > orh[i] else (-1 if C[i] < orl[i] else 0)
                        if d and trend: d = d if (C[i] - ema_d[trend][i]) * d > 0 else 0
                        return d
                    stp = lambda i, d, e, stop=stop: (orl[i] if d == 1 else orh[i]) if stop == "other" else (orh[i] + orl[i]) / 2
                    add(intraday_sim(b, sig, stp, tgt, FLAT, OPEN + N, WEND), f"ORB60 trend{trend} target{tgt} stop-{stop}", tf)
    for nb in (20, 50):   # momentum breakout in the session window
        hi = b.h.rolling(nb).max().shift(1).to_numpy(); lo = b.l.rolling(nb).min().shift(1).to_numpy()
        for en in (200, 800):
            e_ = b.c.ewm(span=en, adjust=False).mean().to_numpy()
            for sm in (1.0, 2.0):
                sig = lambda i: 1 if (C[i] > hi[i] and C[i] > e_[i]) else (-1 if (C[i] < lo[i] and C[i] < e_[i]) else 0)
                stp = lambda i, d, e, sm=sm: e - d * sm * atr[i] if np.isfinite(atr[i]) else None
                add(intraday_sim(b, sig, stp, 0, FLAT, OPEN, WEND, one_per_day=False), f"breakout{nb} EMA{en} stop{sm}ATR", tf)
    crash = (dc / dc.shift(30) - 1).shift(1).reindex(T.floor("D"), method="ffill").to_numpy()
    for rl, buy in ((2, 15), (2, 25), (3, 20)):   # dip buys (long only), hold in hours
        r_ = rsi(b.c, rl).to_numpy()
        for en in (50, 200):
            e_ = b.c.ewm(span=en, adjust=False).mean().to_numpy()
            for hh in (48, 96, 144):
                hold = max(2, hh * 60 // tf); out, i = [], 0
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
                add(out, f"dip RSI{rl}<{buy} EMA{en} hold{hh}h", tf)
df = pd.DataFrame(rows); df["minhalf"] = df[["yrA", "yrB"]].min(axis=1)
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 300)
print(f"{SYM}: {len(raw)} bars, {raw.index[0].date()} to {raw.index[-1].date()}, split {SPLIT.date()}")
print("share of versions positive in both halves / median R per yr (worse half) by family and timeframe:")
print(df.groupby(["fam", "tf"]).agg(versions=("edge", "size"), pos_both=("minhalf", lambda x: f"{(x > 0).mean():.0%}"), median_minhalf=("minhalf", "median"), best_minhalf=("minhalf", "max")).round(1).to_string())
print("top 8:"); print(df.sort_values("minhalf", ascending=False).head(8)[["edge", "tf", "trades_mo", "win", "avgR", "yrA", "yrB", "yr_cost2"]].round(2).to_string(index=False))
pd.to_pickle((df, TR), f"tflab_{SYM}.pkl")
