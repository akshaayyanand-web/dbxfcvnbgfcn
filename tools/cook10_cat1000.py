# The user's "CFD Prop Firm 1000 Strategy Catalogue": 100 base setups x 10 filters, each row with its listed exit experiment.
# Mechanical definitions fixed before running (see SETUP docstrings). Long logic is written once; shorts = the same logic on the
# negated price series (O,H,L,C -> -O,-L,-H,-C), so every rule is exactly symmetric.
# Markets: NQ, SPX, DAX, XAU, EURUSD, GBPUSD, USDJPY, BTC, ETH (M15 + H1) and WTI (H1). Train < 2023-01-01, holdout >= 2023.
# Entry at the next bar's open; stop checked before target inside a bar; gaps fill at the open; cost = spread round trip + swap per day held.
import os, sys, glob, io, zipfile, numpy as np, pandas as pd, warnings
from numba import njit
from multiprocessing import Pool
warnings.filterwarnings("ignore")
SP = os.path.dirname(os.path.abspath(__file__)); os.chdir(SP)
SPLIT = pd.Timestamp("2023-01-01", tz="UTC")
# ---------------------------------------------------------------- data
def m1_csv(path):
    d = pd.read_csv(path, index_col=0); d.index = pd.to_datetime(d.index, utc=True); d = d[~d.index.duplicated()].sort_index().iloc[:, :5]
    d.columns = list("ohlcv")[: len(d.columns)]; return d
def hd(pair):
    parts = []
    for f in sorted(glob.glob(f"hd/raw/{pair}_*.zip")):
        try: z = zipfile.ZipFile(f)
        except zipfile.BadZipFile: continue
        nm = [n for n in z.namelist() if n.lower().endswith(".csv")]
        if nm: parts.append(pd.read_csv(io.BytesIO(z.read(nm[0])), sep=";", header=None, names=["t", "o", "h", "l", "c", "v"]))
    d = pd.concat(parts); d.index = pd.DatetimeIndex(pd.to_datetime(d.t, format="%Y%m%d %H%M%S")).tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT").tz_convert("UTC"); d = d[d.index.notna()]
    return d[["o", "h", "l", "c", "v"]].astype(float).loc[lambda x: ~x.index.duplicated()].sort_index()
def crypto(sym):
    p = []
    for f in sorted(glob.glob(f"k5full/{sym}USDT-5m-*.csv")):
        x = pd.read_csv(f, header=None, usecols=[0, 1, 2, 3, 4, 5], names=["t", "o", "h", "l", "c", "v"]); x["t"] = np.where(x.t > 1e14, x.t // 1000, x.t); p.append(x)
    x = pd.concat(p); x.index = pd.to_datetime(x.t, unit="ms", utc=True); return x[["o", "h", "l", "c", "v"]].astype(float).sort_index().loc[lambda z: ~z.index.duplicated()]
def duka_h(sym): d = pd.read_csv(f"fut/{sym}.csv", index_col=0); d.index = pd.to_datetime(d.index, utc=True); return d[["o", "h", "l", "c", "v"]]
def dayno(ix):
    ix = ix.normalize()
    if ix.tz is not None: ix = ix.tz_localize(None)
    return ix.values.astype("datetime64[D]").astype(np.int64)
def rs(d, rule): return d.resample(rule).agg({"o": "first", "h": "max", "l": "min", "c": "last", "v": "sum"}).dropna(subset=["c"])
MK = {  # name: (M15 loader (1m/5m), H1 loader, cost round trip, swap per year, session open (tz, hh, mm), class)
 "NQ": (lambda: m1_csv("fut1m/USATECHIDXUSD_1m.csv"), lambda: duka_h("USATECHIDXUSD"), 0.00015, 0.05, ("America/New_York", 9, 30), "index"),
 "SPX": (lambda: m1_csv("fut1m/USA500IDXUSD_1m.csv"), lambda: duka_h("USA500IDXUSD"), 0.00015, 0.05, ("America/New_York", 9, 30), "index"),
 "DAX": (lambda: m1_csv("eu1m/DEUIDXEUR_1m.csv"), None, 0.00015, 0.05, ("Europe/Berlin", 9, 0), "index"),
 "XAU": (lambda: m1_csv("fut1m/XAUUSD_1m.csv"), lambda: duka_h("XAUUSD"), 0.00012, 0.04, ("Europe/London", 8, 0), "gold"),
 "EURUSD": (lambda: m1_csv("fx1m/EURUSD_1m.csv"), None, 0.00008, 0.02, ("Europe/London", 8, 0), "fx"),
 "GBPUSD": (lambda: hd("GBPUSD"), None, 0.00009, 0.02, ("Europe/London", 8, 0), "fx"),
 "USDJPY": (lambda: hd("USDJPY"), None, 0.00007, 0.02, ("Europe/London", 8, 0), "fx"),
 "BTC": (lambda: crypto("BTC"), None, 0.0006, 0.15, ("America/New_York", 9, 30), "crypto"),
 "ETH": (lambda: crypto("ETH"), None, 0.001, 0.15, ("America/New_York", 9, 30), "crypto"),
 "WTI": (None, lambda: duka_h("LIGHTCMDUSD"), 0.0003, 0.05, ("America/New_York", 9, 0), "oil")}
PAIR = {"NQ": "SPX", "SPX": "NQ", "DAX": "SPX", "EURUSD": "GBPUSD", "GBPUSD": "EURUSD", "USDJPY": "EURUSD", "BTC": "ETH", "ETH": "BTC", "XAU": None, "WTI": None}
LEAD = {"NQ": "SPX", "SPX": "NQ", "DAX": "NQ", "XAU": "NQ", "EURUSD": "GBPUSD", "GBPUSD": "EURUSD", "USDJPY": "EURUSD", "BTC": "NQ", "ETH": "BTC", "WTI": "SPX"}
_cache = {}
def bars(sym, tf):
    key = (sym, tf)
    if key in _cache: return _cache[key]
    m15, h1 = MK[sym][0], MK[sym][1]
    if tf == "M15":
        if m15 is None: return None
        b = rs(m15(), "15min")
    else:
        b = h1() if h1 is not None else rs(m15(), "1h")
        b = b.dropna(subset=["c"])
    b = b[(b.h >= b.l) & (b.c > 0)]; _cache[key] = b; return b
# ---------------------------------------------------------------- indicators (numba loops)
@njit(cache=True)
def nb_swings(H, L, n):
    N = len(H); shl = np.full(N, np.nan); shp = np.full(N, np.nan); sll = np.full(N, np.nan); slp = np.full(N, np.nan)
    shi = np.full(N, -1); sli = np.full(N, -1)
    a, b, ai, c, d, ci = np.nan, np.nan, -1, np.nan, np.nan, -1
    for k in range(N):
        i = k - n
        if i - n >= 0:
            ok = True
            for j in range(i - n, i + n + 1):
                if j != i and H[j] >= H[i]: ok = False; break
            if ok: b = a; a = H[i]; ai = i
            ok = True
            for j in range(i - n, i + n + 1):
                if j != i and L[j] <= L[i]: ok = False; break
            if ok: d = c; c = L[i]; ci = i
        shl[k] = a; shp[k] = b; shi[k] = ai; sll[k] = c; slp[k] = d; sli[k] = ci
    return shl, shp, shi, sll, slp, sli
@njit(cache=True)
def nb_supertrend(H, L, C, A, m):
    N = len(C); fu = np.full(N, np.nan); fl = np.full(N, np.nan); dr = np.ones(N); st = np.full(N, np.nan)
    for k in range(1, N):
        if not np.isfinite(A[k]): continue
        hl = (H[k] + L[k]) / 2; ub = hl + m * A[k]; lb = hl - m * A[k]
        fu[k] = ub if (not np.isfinite(fu[k - 1]) or ub < fu[k - 1] or C[k - 1] > fu[k - 1]) else fu[k - 1]
        fl[k] = lb if (not np.isfinite(fl[k - 1]) or lb > fl[k - 1] or C[k - 1] < fl[k - 1]) else fl[k - 1]
        if np.isfinite(fu[k - 1]) and C[k] > fu[k - 1]: dr[k] = 1
        elif np.isfinite(fl[k - 1]) and C[k] < fl[k - 1]: dr[k] = -1
        else: dr[k] = dr[k - 1]
        st[k] = fl[k] if dr[k] > 0 else fu[k]
    return dr, st
@njit(cache=True)
def nb_psar(H, L, step, mx):
    N = len(H); sar = np.full(N, np.nan); up = np.ones(N)
    if N < 3: return sar, up
    u = True; af = step; ep = H[0]; s = L[0]
    for k in range(1, N):
        s = s + af * (ep - s)
        if u:
            s = min(s, L[k - 1], L[k - 2] if k >= 2 else L[k - 1])
            if L[k] < s: u = False; s = ep; ep = L[k]; af = step
            elif H[k] > ep: ep = H[k]; af = min(af + step, mx)
        else:
            s = max(s, H[k - 1], H[k - 2] if k >= 2 else H[k - 1])
            if H[k] > s: u = True; s = ep; ep = H[k]; af = step
            elif L[k] < ep: ep = L[k]; af = min(af + step, mx)
        sar[k] = s; up[k] = 1.0 if u else -1.0
    return sar, up
@njit(cache=True)
def nb_kalman(C, q, r):
    N = len(C); x = np.full(N, np.nan); xe = C[0]; p = 1.0
    for k in range(N):
        p = p + q; g = p / (p + r); xe = xe + g * (C[k] - xe); p = (1 - g) * p; x[k] = xe
    return x
@njit(cache=True)
def nb_chandelier(C, A, m):
    N = len(C); out = np.full(N, np.nan); dr = np.ones(N); hc = C[0]; lc = C[0]; d = 1.0
    for k in range(1, N):
        if not np.isfinite(A[k]): continue
        if d > 0:
            hc = max(hc, C[k]); lvl = hc - m * A[k]
            if C[k] < lvl: d = -1.0; lc = C[k]; lvl = lc + m * A[k]
        else:
            lc = min(lc, C[k]); lvl = lc + m * A[k]
            if C[k] > lvl: d = 1.0; hc = C[k]; lvl = hc - m * A[k]
        out[k] = lvl; dr[k] = d
    return dr, out
def ema(x, n): return pd.Series(x).ewm(span=n, adjust=False, min_periods=n).mean().to_numpy()
def sma(x, n): return pd.Series(x).rolling(n).mean().to_numpy()
def rmax(x, n): return pd.Series(x).rolling(n).max().to_numpy()
def rmin(x, n): return pd.Series(x).rolling(n).min().to_numpy()
def rstd(x, n): return pd.Series(x).rolling(n).std().to_numpy()
def shift(x, k=1):
    y = np.empty_like(x, dtype=float); y[:k] = np.nan; y[k:] = x[:-k]; return y
def wilder(x, n): return pd.Series(x).ewm(alpha=1 / n, adjust=False, min_periods=n).mean().to_numpy()
def rsi(c, n):
    d = np.diff(c, prepend=np.nan); up = wilder(np.where(d > 0, d, 0.0), n); dn = wilder(np.where(d < 0, -d, 0.0), n)
    return 100 - 100 / (1 + up / np.where(dn == 0, np.nan, dn))
def pct_rank(x, n): return pd.Series(x).rolling(n, min_periods=n // 2).rank(pct=True).to_numpy()
def xup(a, b): return (a > b) & (shift(a) <= shift(b) if np.ndim(b) else shift(a) <= b)
class X:
    """Context: price arrays (possibly negated for shorts) plus cached indicators. neg=True -> shorts."""
    def __init__(s, b, sym, tf, neg, extra):
        s.sym, s.tf, s.neg, s.c_ = sym, tf, neg, {}; g = -1.0 if neg else 1.0
        s.O = g * b.o.to_numpy(); s.C = g * b.c.to_numpy()
        s.H = (-b.l if neg else b.h).to_numpy() * (1.0 if not neg else 1.0); s.L = (-b.h if neg else b.l).to_numpy()
        s.V = b.v.fillna(0).to_numpy(); s.T = b.index; s.N = len(s.C); s.extra = extra; s.hasvol = (s.V > 0).mean() > 0.5
        s.barh = 0.25 if tf == "M15" else 1.0
    def get(s, k, f):
        if k not in s.c_: s.c_[k] = f()
        return s.c_[k]
    def ema(s, n): return s.get(("ema", n), lambda: ema(s.C, n))
    def atr(s, n=14):
        def f():
            pc = shift(s.C); tr = np.nanmax(np.vstack([s.H - s.L, np.abs(s.H - pc), np.abs(s.L - pc)]), axis=0); return wilder(tr, n)
        return s.get(("atr", n), f)
    def rsi(s, n): return s.get(("rsi", n), lambda: rsi(s.C, n))
    def sw(s, n=2): return s.get(("sw", n), lambda: nb_swings(s.H, s.L, n))
    def adx(s, n=14):
        def f():
            up = s.H - shift(s.H); dn = shift(s.L) - s.L; pdm = np.where((up > dn) & (up > 0), up, 0.0); mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
            a = s.atr(n); pdi = 100 * wilder(pdm, n) / a; mdi = 100 * wilder(mdm, n) / a; dx = 100 * np.abs(pdi - mdi) / (pdi + mdi); return wilder(dx, n), pdi, mdi
        return s.get(("adx", n), f)
    def bb(s, n=20, k=2.0):
        def f():
            m = sma(s.C, n); sd = rstd(s.C, n); return m, m + k * sd, m - k * sd
        return s.get(("bb", n, k), f)
    def kc(s, n=20, k=1.5):
        def f():
            m = ema(s.C, n); a = s.atr(n); return m, m + k * a, m - k * a
        return s.get(("kc", n, k), f)
    def macd(s):
        def f():
            m = ema(s.C, 12) - ema(s.C, 26); return m, ema(np.nan_to_num(m), 9)
        return s.get("macd", f)
    def stoch(s, n=14):
        def f():
            hh, ll = rmax(s.H, n), rmin(s.L, n); k_ = 100 * (s.C - ll) / (hh - ll); return sma(k_, 3)
        return s.get(("st", n), f)
    def cci(s, n=20):
        def f():
            tp = (s.H + s.L + s.C) / 3; m = sma(tp, n); md = pd.Series(tp).rolling(n).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True).to_numpy()
            return (tp - m) / (0.015 * md)
        return s.get(("cci", n), f)
    def willr(s, n=14): return s.get(("wr", n), lambda: -100 * (rmax(s.H, n) - s.C) / (rmax(s.H, n) - rmin(s.L, n)))
    def ichi(s):
        def f():
            hh = lambda n: rmax(s.H, n); ll = lambda n: rmin(s.L, n); tk = (hh(9) + ll(9)) / 2; kj = (hh(26) + ll(26)) / 2
            sa = shift((tk + kj) / 2, 26); sb = shift((hh(52) + ll(52)) / 2, 26); return tk, kj, np.fmax(sa, sb), np.fmin(sa, sb)
        return s.get("ichi", f)
    def er(s, n):
        def f():
            ch = np.abs(s.C - shift(s.C, n)); vol = pd.Series(np.abs(np.diff(s.C, prepend=np.nan))).rolling(n).sum().to_numpy(); return ch / vol
        return s.get(("er", n), f)
    def z(s, n): return s.get(("z", n), lambda: (s.C - sma(s.C, n)) / rstd(s.C, n))
    def loc(s, tz):
        return s.get(("loc", tz), lambda: s.T.tz_convert(tz))
    def sess(s, tz, hh, mm):
        """session id (day number of the local session starting at hh:mm) and minutes since session open."""
        def f():
            lt = s.loc(tz); mins = lt.hour * 60 + lt.minute - (hh * 60 + mm); dayn = dayno(lt)
            sid = np.where(mins >= 0, dayn, dayn - 1); return sid, np.where(mins >= 0, mins, mins + 1440)
        return s.get(("sess", tz, hh, mm), f)
    def vwap(s, tz, hh, mm):
        def f():
            sid, _ = s.sess(tz, hh, mm); tp = (s.H + s.L + s.C) / 3; w = s.V if s.hasvol else np.ones(s.N)
            df = pd.DataFrame({"s": sid, "pv": tp * w, "w": w}); g = df.groupby("s"); return (g.pv.cumsum() / g.w.cumsum()).to_numpy()
        return s.get(("vwap", tz, hh, mm), f)
    def home(s): return MK[s.sym][4]
    def day(s):
        """UTC-day prior high/low/close, today's open, daily ATR (aligned to bars, known at the bar)."""
        def f():
            dn = dayno(s.T); df = pd.DataFrame({"d": dn, "h": s.H, "l": s.L, "c": s.C, "o": s.O})
            g = df.groupby("d").agg(h=("h", "max"), l=("l", "min"), c=("c", "last"), o=("o", "first"))
            pc = g.c.shift(1); tr = np.maximum(g.h - g.l, np.maximum(abs(g.h - pc), abs(g.l - pc))); g["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
            p = g.shift(1); m = lambda col: p[col].reindex(dn).to_numpy()
            today_open = g.o.reindex(dn).to_numpy()
            return m("h"), m("l"), m("c"), today_open, m("atr"), dn
        return s.get("day", f)
    def week(s):
        def f():
            wk = (dayno(s.T) + 3) // 7; df = pd.DataFrame({"w": wk, "h": s.H, "l": s.L})
            g = df.groupby("w").agg(h=("h", "max"), l=("l", "min")).shift(1); return g.h.reindex(wk).to_numpy(), g.l.reindex(wk).to_numpy()
        return s.get("week", f)
    def htf(s):
        """last COMPLETED higher-timeframe bar (4x): close, EMA50, EMA50 one bar earlier, RSI14, cloud top/bottom, ATR."""
        def f():
            rule = "1h" if s.tf == "M15" else "4h"; df = pd.DataFrame({"o": s.O, "h": s.H, "l": s.L, "c": s.C}, index=s.T)
            hb = df.resample(rule).agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()
            c = hb.c.to_numpy(); e = ema(c, 50); r = rsi(c, 14); hh = lambda n: rmax(hb.h.to_numpy(), n); ll = lambda n: rmin(hb.l.to_numpy(), n)
            tk = (hh(9) + ll(9)) / 2; kj = (hh(26) + ll(26)) / 2; sa = shift((tk + kj) / 2, 26); sb = shift((hh(52) + ll(52)) / 2, 26)
            out = pd.DataFrame({"c": c, "e": e, "e1": shift(e), "e10": shift(e, 10), "r": r, "top": np.fmax(sa, sb), "bot": np.fmin(sa, sb)}, index=hb.index + pd.Timedelta(rule))
            al = out.reindex(s.T, method="ffill"); return {k: al[k].to_numpy() for k in out.columns}
        return s.get("htf", f)
F = lambda a: np.nan_to_num(a, nan=0.0).astype(bool) if a.dtype != bool else a
def lowest(X, n): return rmin(X.L, n)
def hb_(X, n): return shift(rmax(X.H, n))     # highest high of the previous n bars
def lb_(X, n): return shift(rmin(X.L, n))
# ---------------------------------------------------------------- the 100 base setups (long side; stop = invalidation level)
def S(X):
    A = X.atr(); O, H, L, C = X.O, X.H, X.L, X.C; bull = C > O; atrstop = C - 1.5 * A
    shl, shp, shi, sll, slp, sli = X.sw(); out = {}
    e20, e50, e200 = X.ema(20), X.ema(50), X.ema(200)
    # ---- trend following 1-10
    out[1] = ((e20 > e50) & (e50 > shift(e50)) & (L <= e20) & (C > e20) & bull, rmin(L, 3))
    out[2] = ((e50 > e200) & (C > shift(rmax(C, 10))) & ~(shift(C) > shift(rmax(C, 10), 1)), atrstop)
    hx = X.htf(); htf_up = hx["c"] > hx["e"]
    out[3] = ((C > hb_(X, 20)) & htf_up, (hb_(X, 20) + lb_(X, 20)) / 2)
    adx, pdi, mdi = X.adx(); e10 = X.ema(10)
    out[4] = ((adx > 25) & (pdi > mdi) & (shift(C) < shift(e10)) & (C > e10), rmin(L, 5))
    dr, st = X.get("st103", lambda: nb_supertrend(H, L, C, X.atr(10), 3.0))
    flip = pd.Series((dr > 0) & (shift(dr) < 0)).rolling(10).max().to_numpy() > 0
    out[5] = (flip & (dr > 0) & (L <= st + 0.2 * A) & bull & (C > st), st - 0.5 * A)
    hl_new = (sli == np.arange(X.N) - 2) & (sll > slp) & (shl > shp)
    out[6] = (hl_new, sll)
    tk, kj, ctop, cbot = X.ichi()
    out[7] = ((C > ctop) & (tk > kj) & (L <= kj) & (C > kj), np.fmin(kj, ctop) - 0.5 * A)
    sar, up = X.get("sar", lambda: nb_psar(H, L, 0.02, 0.2))
    out[8] = ((up > 0) & (C > shl) & (shift(C) <= shift(shl)), sar)
    tz, hh, mm = X.home(); vw = X.vwap(tz, hh, mm); above = pd.Series((C > vw).astype(float)).rolling(12).sum().to_numpy() >= 10
    out[9] = (above & (vw > shift(vw, 6)) & (L <= vw) & (C > vw), L - 0.3 * A)
    rib = np.vstack([X.ema(n) for n in (8, 13, 21, 34, 55)]); spread = (rib.max(0) - rib.min(0)) / A; ordered = np.all(np.diff(rib[::-1], axis=0) > 0, axis=0)
    out[10] = ((pd.Series(spread).rolling(10).min().to_numpy() < 0.5) & (spread > 1.0) & (shift(spread) <= 1.0) & (C > X.ema(8)) & ordered, atrstop)
    # ---- mean reversion 11-20
    m, ub, lbb = X.bb(); out[11] = ((shift(C) < shift(lbb)) & (C > lbb), np.fmin(L, shift(L)))
    r14 = X.rsi(14); out[12] = ((pd.Series(r14 < 25).rolling(3).max().to_numpy() > 0) & bull & (C > shift(H)), rmin(L, 3))
    km, ku, kl = X.kc(); out[13] = ((shift(C) < shift(kl)) & (C > kl), np.fmin(L, shift(L)))
    out[14] = (((C - vw) / A < -3) & bull, L - 0.2 * A)
    z50 = X.z(50); out[15] = ((shift(z50) < -2.5) & (C > shift(C)), np.fmin(L, shift(L)))
    er50 = X.er(50); rh, rl = shift(rmax(H, 50)), shift(rmin(L, 50))
    out[16] = ((er50 < 0.2) & (C < rl + 0.1 * (rh - rl)) & bull, rl - 0.3 * A)
    cci = X.cci(); out[17] = (xup(cci, -100.0), rmin(L, 5))
    wr = X.willr(); out[18] = (xup(wr, -80.0), rmin(L, 5))
    rsi_at_sl = pd.Series(np.where(sli >= 0, r14[np.clip(sli, 0, None)], np.nan)).to_numpy()
    out[19] = ((L <= shift(rmin(L, 50)) + 0.2 * A) & (L < sll) & (r14 > rsi_at_sl) & bull, L - 0.2 * A)
    out[20] = (((C - e20) < -2.5 * A) & (L > shift(L)) & bull, shift(L))
    # ---- breakout 21-30
    sid, mins = X.sess(tz, hh, mm); df = pd.DataFrame({"s": sid, "h": H, "l": L, "m": mins})
    inr = mins < 30; orh = df.h.where(inr).groupby(df.s).transform("max").to_numpy(); orl = df.l.where(inr).groupby(df.s).transform("min").to_numpy()
    first_break = lambda cond, sidv: cond & ~(pd.Series(cond).groupby(sidv).cumsum().to_numpy() > 1)
    out[21] = (first_break((mins >= 30) & (mins < 210) & (C > orh), sid), orl)
    lt = X.loc("UTC"); hr = lt.hour.to_numpy(); dn = dayno(X.T)
    da = pd.DataFrame({"d": dn, "h": H, "l": L}); asia = hr < 7
    ah = da.h.where(asia).groupby(da.d).transform("max").to_numpy(); al = da.l.where(asia).groupby(da.d).transform("min").to_numpy()
    out[22] = (first_break((hr >= 7) & (hr < 12) & (C > ah), dn), (ah + al) / 2)
    pdh, pdl, pdc, dop, datr, _ = X.day()
    out[23] = (first_break(C > pdh, dn), atrstop)
    out[24] = ((C > hb_(X, 55)) & ~(shift(C) > shift(hb_(X, 55))), lb_(X, 20))
    bw = (ub - lbb) / m; bwp = pct_rank(bw, 200); sq = pd.Series(bwp <= 0.2).rolling(5).max().to_numpy() > 0
    out[25] = (sq & (C > ub) & ~(shift(C) > shift(ub)), m)
    inside1 = (shift(H) < shift(H, 2)) & (shift(L) > shift(L, 2))
    out[26] = (inside1 & (C > shift(H)), shift(L))
    g3 = pd.DataFrame({"d": dn, "h": H, "l": L}).groupby("d").agg(h=("h", "max"), l=("l", "min"))
    box_h = g3.h.rolling(3).max().shift(1).reindex(dn).to_numpy(); box_l = g3.l.rolling(3).min().shift(1).reindex(dn).to_numpy()
    tight = (box_h - box_l) < 1.5 * datr
    out[27] = (first_break(tight & (C > box_h), dn), (box_h + box_l) / 2)
    tri = (shl < shp) & (sll > slp)
    brk = tri & (C > shl) & (shift(C) <= shift(shl)); lvl = np.where(brk, shl, np.nan); lvl = pd.Series(lvl).ffill(limit=10).to_numpy()
    out[28] = ((~brk) & np.isfinite(lvl) & (L <= lvl) & (C > lvl) & ~(pd.Series((L <= lvl) & (C > lvl)).shift(1).fillna(False).to_numpy()), sll)
    pwh, pwl = X.week(); wk = (dayno(X.T) + 3) // 7
    out[29] = (first_break(C > pwh, wk), atrstop)
    rng = H - L; out[30] = ((rng > 2 * shift(sma(rng, 20))) & (C > shl) & bull, L)
    # ---- price action 31-40
    lw = np.fmin(O, C) - L; near_sup = (L <= shift(rmin(L, 50)) + 0.3 * A) | (np.abs(L - pdl) <= 0.3 * A)
    out[31] = ((lw >= 0.66 * rng) & (rng > 0) & near_sup, L - 0.1 * A)
    engulf = bull & (shift(C) < shift(O)) & (O <= shift(C)) & (C >= shift(O))
    out[32] = (engulf & (np.abs(L - sll) <= 0.5 * A), L)
    bos = (C > shl) & (shift(C) <= shift(shl)); blv = pd.Series(np.where(bos, shl, np.nan)).ffill(limit=10).to_numpy()
    out[33] = (~bos & np.isfinite(blv) & (L <= blv) & (C > blv) & bull, sll)
    out[34] = X.get("sd", lambda: zone_setup(O, H, L, C, A, "demand"))
    lvl20 = hb_(X, 20); out[35] = ((shift(C) > shift(lvl20)) & (C < shift(lvl20)) & False, H)  # short-side logic -> see mirror note below
    out[35] = ((shift(C) < shift(lb_(X, 20))) & (C > shift(lb_(X, 20))), np.fmin(L, shift(L)))   # failed breakdown -> long (mirror gives failed breakout -> short)
    out[36] = X.get("3bar", lambda: three_bar(O, H, L, C, A))
    out[37] = X.get("ibc", lambda: inside_comp(H, L, C))
    r50 = hb_(X, 50); brk50 = (C > r50) & (shift(C) <= shift(r50)); lv50 = pd.Series(np.where(brk50, r50, np.nan)).ffill(limit=20).to_numpy()
    out[38] = (~brk50 & np.isfinite(lv50) & (L <= lv50) & (C > lv50) & bull, lv50 - 0.5 * A)
    imp = (shl - sll); up_imp = (shi > sli) & (imp > 3 * A); f50 = shl - 0.5 * imp; f618 = shl - 0.618 * imp; f786 = shl - 0.786 * imp
    out[39] = (up_imp & (L <= f50) & (L >= f618 - 0.1 * A) & bull & (C > f618), f786)
    out[40] = X.get("wick", lambda: wick_cluster(O, H, L, C, A))
    # ---- liquidity 41-50 (41 equal-high sweep short is the mirror of 42 equal-low sweep long; 41 kept as its own row with an extra-equal tolerance)
    out[42] = X.get("eql", lambda: equal_sweep(H, L, C, A, 0.1))
    out[41] = X.get("eql2", lambda: equal_sweep(H, L, C, A, 0.25))
    out[43] = ((L < pdl) & (C > pdl), L - 0.1 * A)
    sw_ok = (hr >= 7) & (hr < 21); out[44] = (sw_ok & (L < al) & (C > al) & ~(shift(L) < shift(al)), L - 0.1 * A)
    out[45] = ((L < sll) & (C > sll) & (C > rmax(shift(H), 2)), L)
    out[46] = X.get("swd", lambda: sweep_disp(O, H, L, C, A, sll))
    out[47] = X.get("fvg", lambda: fvg(O, H, L, C, A))
    out[48] = X.get("ob", lambda: order_block(O, H, L, C, A, shl))
    pdz = (shi > sli) & (C < (shl + sll) / 2) & (C > sll); out[49] = (pdz & engulf, sll)
    swept = pd.Series(L < pdl).groupby(dn).cummax().to_numpy(); dlow = pd.Series(L).groupby(dn).cummin().to_numpy()
    out[50] = (swept & xup(C, vw), dlow)
    # ---- momentum 51-60
    mc, ms = X.macd(); out[51] = (xup(mc, 0.0) & (C > e50), atrstop)
    out[52] = (xup(mc, ms) & htf_up & (hx["e"] > hx["e1"]), atrstop)
    out[53] = (xup(r14, 50.0) & (C > hb_(X, 5)), rmin(L, 5))
    roc = (C / shift(C, 10) - 1) if not X.neg else (shift(C, 10) / C - 1) * -1
    roc = (C - shift(C, 10)) / np.abs(shift(C, 10)); rs_ = rstd(roc, 200)
    out[54] = (xup(roc, rs_) & (roc > shift(roc, 3)), atrstop)
    stc = X.stoch(); out[55] = ((e50 > e200) & xup(stc, 20.0), rmin(L, 5))
    dc = np.diff(C, prepend=np.nan); tsi = 100 * ema(np.nan_to_num(ema(np.nan_to_num(dc), 25)), 13) / ema(np.nan_to_num(ema(np.nan_to_num(np.abs(dc)), 25)), 13)
    out[56] = (xup(tsi, ema(np.nan_to_num(tsi), 7)) & (C > e50), atrstop)
    rsh = np.where(shi >= 0, r14[np.clip(shi, 0, None)], np.nan); rshp = X.get("rshp", lambda: prev_swing_val(shi, r14))
    bear_div = (shl > shp) & (rsh < rshp); out[57] = (bear_div & (C > shl) & (shift(C) <= shift(shl)), sll)
    out[58] = ((C > hb_(X, 20)) & (X.V > 1.5 * sma(X.V, 20)), atrstop) if X.hasvol else (np.zeros(X.N, bool), atrstop)
    out[59] = (xup(pdi - mdi, 10.0) & (adx > shift(adx)) & (adx > 20), atrstop)
    mt = (r14 > 55) & (hx["r"] > 55); out[60] = (mt & ~shift(mt.astype(float)).astype(bool), atrstop)
    # ---- volatility 61-70
    ap = pct_rank(A, 200); out[61] = ((pd.Series(ap < 0.2).rolling(10).max().to_numpy() > 0) & (A > 1.2 * shift(A, 3)) & (C > hb_(X, 10)), atrstop)
    low5 = pd.Series(ap <= 0.1).rolling(5).sum().to_numpy() >= 5; r10h, r10l = hb_(X, 10), lb_(X, 10)
    out[62] = (shift(low5.astype(float)).astype(bool) & (C > r10h), (r10h + r10l) / 2)
    out[63] = ((shift(bwp) <= 0.1) & (bw > shift(bw)) & (C > ub), m)
    nr7 = (rng <= pd.Series(rng).rolling(7).min().to_numpy()); out[64] = (shift(nr7.astype(float)).astype(bool) & (C > shift(H)) & ~(shift(C) > shift(H, 2)), shift(L))
    rv = rstd(np.diff(C, prepend=np.nan), 50); hiv = rv > pd.Series(rv).rolling(200).median().to_numpy()
    out[65] = ((hiv & (C > hb_(X, 20))) | (~hiv & (shift(C) < shift(lbb)) & (C > lbb)), np.where(hiv, atrstop, np.fmin(L, shift(L))))
    w20 = hb_(X, 20) - lb_(X, 20); out[66] = ((w20 < 3 * A) & (C > hb_(X, 20)) & ~(shift(C) > shift(hb_(X, 20))), (hb_(X, 20) + lb_(X, 20)) / 2)
    out[67] = ((ap > 0.7) & (e20 > e50) & (L <= e20) & bull & (C > e20), rmin(L, 3) - 0.2 * A)
    out[68] = ((ap < 0.3) & (C < lbb) & bull, L)        # long mirror of "fade extension above the upper band"
    cd, cl = X.get("chand", lambda: nb_chandelier(C, X.atr(22), 3.0)); flip_c = (cd > 0) & (shift(cd) < 0)
    out[69] = (shift(flip_c.astype(float)).astype(bool) & (C > shift(C)) & (cd > 0), cl)
    sidH, minH = X.sess(tz, hh, mm); sop = pd.Series(O).groupby(sidH).transform("first").to_numpy()
    sclose = pd.Series(C).groupby(sidH).last(); prevc = sclose.shift(1).reindex(sidH).to_numpy()
    fh = (minH >= 45) & (minH < 60) if X.tf == "M15" else (minH >= 0) & (minH < 60)
    out[70] = (((sop - prevc) > 0.25 * datr) & (A > shift(A, 4)) & fh & (C > sop), sop)
    # ---- session 71-80
    sidL, minL = X.sess("Europe/London", 7, 0); dL = pd.DataFrame({"s": sidL, "h": H, "l": L})
    inL = minL < 60; lh = dL.h.where(inL).groupby(dL.s).transform("max").to_numpy(); ll_ = dL.l.where(inL).groupby(dL.s).transform("min").to_numpy()
    out[71] = (first_break((minL >= 60) & (minL < 240) & (C > lh), sidL), ll_)
    sidN, minN = X.sess("America/New_York", 9, 30); dN = pd.DataFrame({"s": sidN, "h": H, "l": L})
    inN = minN < 30; nh = dN.h.where(inN).groupby(dN.s).transform("max").to_numpy(); nl = dN.l.where(inN).groupby(dN.s).transform("min").to_numpy()
    out[72] = (first_break((minN >= 30) & (minN < 150) & (C > nh), sidN), nl)
    vwL = X.vwap("Europe/London", 7, 0); aboveL = pd.Series((C > vwL).astype(float)).rolling(8 if X.tf == "M15" else 3).mean().to_numpy() >= 0.75
    out[73] = ((minL >= 60) & (minL < 240) & aboveL & (L <= vwL) & (C > vwL), L - 0.3 * A)
    vwN = X.vwap("America/New_York", 9, 30); nopen = pd.Series(O).groupby(sidN).transform("first").to_numpy()
    upday = pd.Series(np.where(minN == 30, C > nopen, np.nan)).groupby(sidN).transform("max").to_numpy() > 0
    out[74] = ((minN >= 30) & (minN < 330) & upday & xup(C, vwN), vwN - 0.5 * A)
    fake = (hr >= 7) & (hr < 10) & (shift(L) < shift(al)) & (C > al); out[75] = (fake, rmin(L, 3))
    lmove = pd.Series(np.where(minL == 300, C, np.nan)).groupby(sidL).transform("max").to_numpy() - pd.Series(np.where(minL == 0, O, np.nan)).groupby(sidL).transform("max").to_numpy()
    lmove_by_ny = pd.Series(lmove).groupby(sidN).transform("first").to_numpy() if False else lmove
    first30 = (minN == 30) | ((X.tf == "H1") & (minN == 30))
    out[76] = (((minN >= 30) & (minN < 45 if X.tf == "M15" else minN < 90)) & (lmove > 0.5 * datr) & (C > nopen) & ~(pd.Series((C > nopen) & (minN >= 30)).groupby(sidN).cumsum().to_numpy() > 1), C - A)
    rah = pd.Series(np.where(asia, H, np.nan)).groupby(dn).cummax().to_numpy(); ral = pd.Series(np.where(asia, L, np.nan)).groupby(dn).cummin().to_numpy()
    quiet = shift(rah - ral) < 0.5 * datr
    out[77] = ((hr >= 3) & (hr < 7) & quiet & (L < shift(rmin(L, 4))) & (C > shift(rmin(L, 4))), L)
    ovl = (minL >= 300) & (minL < 540); roc5 = C - shift(C, 5)
    out[78] = (ovl & (C > shl) & (shift(C) <= shift(shl)) & (roc5 > 0) & (rng > sma(rng, 20)), sll)
    endN = (minN >= 270) & (minN < 390); out[79] = (endN & ((vwN - C) > 1.5 * A) & bull, C - A)
    gapN = (nopen - pd.Series(np.where(minN == 389, C, np.nan)).groupby(sidN).transform("max").shift(0).to_numpy())
    prevclose = pd.Series(np.where((minN >= 375) & (minN < 390), C, np.nan)).groupby(sidN).transform("last").to_numpy()
    pc_prev = pd.Series(prevclose).groupby(sidN).first().shift(1).reindex(sidN).to_numpy()
    gapdn = (nopen < pc_prev * (1 - 0.003 * np.sign(pc_prev))) if not X.neg else (nopen < pc_prev - 0.003 * np.abs(pc_prev))
    out[80] = ((minN == (0 if X.tf == "M15" else 30)) & gapdn & (X.MKc in ("index", "oil")), nopen - np.abs(pc_prev - nopen))
    # ---- quantitative 81-90
    z100 = X.z(100); out[81] = ((shift(z100) < -2.5) & (C > shift(C)), atrstop)
    n_ = 100; xs = np.arange(n_); xm = xs.mean(); sxx = ((xs - xm) ** 2).sum()
    def lrc():
        Cs = pd.Series(C); mean_ = Cs.rolling(n_).mean().to_numpy(); cov = Cs.rolling(n_).apply(lambda y: ((xs - xm) * (y - y.mean())).sum(), raw=True).to_numpy() / sxx
        mid = mean_ + cov * (n_ - 1 - xm); ss = rstd(C, n_) ** 2 * (n_ - 1); resid_sd = np.sqrt(np.clip(ss - cov ** 2 * sxx, 0, None) / n_); return mid, resid_sd
    mid, rsd = X.get("lrc", lrc); out[82] = ((C > mid + 2 * rsd) & ~(shift(C) > shift(mid + 2 * rsd)), mid)
    kf = X.get("kal", lambda: nb_kalman(C, 1e-4 * np.nanvar(np.diff(C)), np.nanvar(np.diff(C)))); out[83] = ((kf > shift(kf, 5)) & xup(C, kf), atrstop)
    pz = X.extra.get("pairz"); out[84] = ((pz < -2) & (shift(pz) >= -2), atrstop) if pz is not None else (np.zeros(X.N, bool), atrstop)
    ld = X.extra.get("lead"); r1 = np.diff(C, prepend=np.nan) / rstd(np.diff(C, prepend=np.nan), 200)
    out[85] = ((ld > 2) & (r1 < 0.5), atrstop) if ld is not None else (np.zeros(X.N, bool), atrstop)
    def hurst():
        lags = (2, 4, 8, 16); lg = np.log(lags); sds = np.vstack([np.log(rstd(C - shift(C, k), 200)) for k in lags]); lgm = lg.mean()
        return ((lg[:, None] - lgm) * (sds - sds.mean(0))).sum(0) / ((lg - lgm) ** 2).sum()
    hu = X.get("hurst", hurst); out[86] = (((hu > 0.55) & (C > hb_(X, 20))) | ((hu < 0.45) & (shift(z50) < -2) & (C > shift(C))), atrstop)
    ew = pd.Series(np.diff(C, prepend=np.nan) ** 2).ewm(span=50).mean().to_numpy(); calm = ew < pd.Series(ew).rolling(200).median().to_numpy()
    out[87] = (calm & (C > hb_(X, 20)) & ~(shift(C) > shift(hb_(X, 20))), atrstop)
    rr = np.diff(C, prepend=np.nan); ac = pd.Series(rr).rolling(200).corr(pd.Series(rr).shift(1)).to_numpy(); big = rr > rstd(rr, 200)
    out[88] = (((ac > 0.05) & big) | ((ac < -0.05) & (rr < -rstd(rr, 200))), atrstop)
    out[89] = ((X.er(20) > 0.4) & xup(C, e20), atrstop)
    score = (np.sign(C - e50) + np.sign(np.nan_to_num(mc)) + np.sign(r14 - 50) + np.sign(roc) + np.sign(C - vw)); allin = score >= 5
    out[90] = (allin & ~shift(allin.astype(float)).astype(bool), atrstop)
    # ---- hybrid 91-100
    out[91] = (htf_up & (hx["e"] > hx["e1"]) & (rmin(L, 3) <= e20) & xup(r14, 40.0), rmin(L, 3))
    out[92] = ((C > hb_(X, 20)) & ~(shift(C) > shift(hb_(X, 20))) & (A > shift(A, 5)) & ((X.V > sma(X.V, 20)) if X.hasvol else False), atrstop)
    sw1h, _, _, sw1l, _, _ = X.sw(1); swept_low = pd.Series(L < sll).rolling(5).max().to_numpy() > 0; sweep_lo = rmin(L, 5)
    out[93] = (swept_low & (C > sw1h) & (shift(C) <= shift(sw1h)), sweep_lo)
    flat = np.abs(hx["e"] - hx["e10"]) < 0.5 * A * (2 if X.tf == "M15" else 2)
    out[94] = (flat & (shift(z50) < -2) & (C > shift(C)), atrstop)
    out[95] = (first_break((hr >= 7) & (hr < 12) & (C > ah), dn) & (ap > 0.5), (ah + al) / 2)
    vx = xup(C, vw); vxr = pd.Series(vx).rolling(3).max().to_numpy() > 0
    out[96] = (vxr & (C > shl) & (shift(C) <= shift(shl)), sll)
    out[97] = ((hx["c"] > hx["top"]) & xup(mc, ms), atrstop)
    out[98] = ((er50 < 0.25) & (adx < 20) & xup(r14, 30.0), rmin(L, 5))
    out[99] = ((e50 > e200) & xup(C, e20), lb_(X, 20))
    cons = (C > X.ema(100)) & (mc > ms) & (C > hb_(X, 20)); out[100] = (cons & ~shift(cons.astype(float)).astype(bool), atrstop)
    return out
# ---- loop-based setups (long side)
def zone_setup(O, H, L, C, A, kind):
    N = len(C); sig = np.zeros(N, bool); stop = np.full(N, np.nan); zt = zb = np.nan; born = -10**9; used = True
    for k in range(2, N):
        if np.isfinite(A[k]) and (H[k] - L[k]) > 2 * A[k] and C[k] > O[k] and C[k] > H[k - 1]:
            zt, zb, born, used = max(O[k - 1], C[k - 1]), L[k - 1], k, False
        elif not used and k - born <= 100 and k > born + 1 and L[k] <= zt and C[k] > zb and C[k] > O[k]:
            sig[k] = True; stop[k] = zb - 0.2 * A[k]; used = True
    return sig, stop
def three_bar(O, H, L, C, A):
    N = len(C); sig = np.zeros(N, bool); stop = np.full(N, np.nan)
    for k in range(5, N):
        i = k - 4
        if not np.isfinite(A[i]) or (H[i] - L[i]) < 1.5 * A[i] or C[i] <= O[i]: continue
        p = range(i + 1, i + 4)
        if all((H[j] - L[j]) < 1.0 * A[i] and H[j] <= H[i] and L[j] >= (L[i] + H[i]) / 2 for j in p) and C[k] > H[i]:
            sig[k] = True; stop[k] = min(L[j] for j in p)
    return sig, stop
def inside_comp(H, L, C):
    N = len(C); sig = np.zeros(N, bool); stop = np.full(N, np.nan); mh = ml = np.nan; cnt = 0
    for k in range(1, N):
        if cnt == 0:
            if H[k] < H[k - 1] and L[k] > L[k - 1]: mh, ml, cnt = H[k - 1], L[k - 1], 1
            continue
        if H[k] <= mh and L[k] >= ml: cnt += 1; continue
        if cnt >= 2 and C[k] > mh: sig[k] = True; stop[k] = ml
        cnt = 0
        if H[k] < H[k - 1] and L[k] > L[k - 1]: mh, ml, cnt = H[k - 1], L[k - 1], 1
    return sig, stop
def wick_cluster(O, H, L, C, A):
    N = len(C); sig = np.zeros(N, bool); stop = np.full(N, np.nan)
    lw = np.minimum(O, C) - L; rg = H - L
    for k in range(6, N):
        idx = [j for j in range(k - 5, k) if rg[j] > 0 and lw[j] > 0.5 * rg[j]]
        if len(idx) >= 2 and np.isfinite(A[k]) and (max(L[j] for j in idx) - min(L[j] for j in idx)) <= 0.3 * A[k] and C[k] > max(C[k - 5:k]):
            sig[k] = True; stop[k] = min(L[j] for j in idx) - 0.2 * A[k]
    return sig, stop
def equal_sweep(H, L, C, A, tol):
    """two swing lows within tol*ATR in the last 50 bars; a bar trades below both and closes back above -> long."""
    N = len(C); sig = np.zeros(N, bool); stop = np.full(N, np.nan); lows = []
    for k in range(4, N):
        i = k - 2
        if L[i] < L[i - 1] and L[i] < L[i - 2] and L[i] < L[i + 1] and L[i] < L[i + 2]: lows.append((i, L[i]))
        lows = [(i_, v) for i_, v in lows if k - i_ <= 50]
        if len(lows) >= 2 and np.isfinite(A[k]):
            (i1, v1), (i2, v2) = lows[-2], lows[-1]
            if abs(v1 - v2) <= tol * A[k] and L[k] < min(v1, v2) and C[k] > min(v1, v2):
                sig[k] = True; stop[k] = L[k] - 0.1 * A[k]; lows = []
    return sig, stop
def sweep_disp(O, H, L, C, A, sll):
    N = len(C); sig = np.zeros(N, bool); stop = np.full(N, np.nan); last = -100; lo = np.nan
    for k in range(1, N):
        if np.isfinite(sll[k]) and L[k] < sll[k] and C[k] > sll[k] - 0.5 * A[k] if np.isfinite(A[k]) else False: last = k; lo = L[k]
        if 0 < k - last <= 3 and np.isfinite(A[k]) and (H[k] - L[k]) > 1.5 * A[k] and C[k] > O[k] and (H[k] - C[k]) < 0.25 * (H[k] - L[k]):
            sig[k] = True; stop[k] = lo; last = -100
    return sig, stop
def fvg(O, H, L, C, A):
    N = len(C); sig = np.zeros(N, bool); stop = np.full(N, np.nan); top = bot = np.nan; born = -100
    for k in range(2, N):
        if np.isfinite(A[k - 1]) and L[k] > H[k - 2] and (H[k - 1] - L[k - 1]) > 1.5 * A[k - 1] and C[k - 1] > O[k - 1]:
            top, bot, born = L[k], H[k - 2], k; continue
        if born > 0 and k - born <= 30 and L[k] <= top and C[k] > bot and C[k] > O[k]:
            sig[k] = True; stop[k] = bot - 0.2 * A[k]; born = -100
    return sig, stop
def order_block(O, H, L, C, A, shl):
    N = len(C); sig = np.zeros(N, bool); stop = np.full(N, np.nan); zt = zb = np.nan; born = -100
    for k in range(3, N):
        if np.isfinite(shl[k]) and C[k] > shl[k] and C[k - 1] <= shl[k - 1] and np.isfinite(A[k]) and (H[k] - L[k]) > 1.2 * A[k]:
            j = k - 1
            while j > k - 10 and C[j] >= O[j]: j -= 1
            if C[j] < O[j]: zt, zb, born = H[j], L[j], k
            continue
        if born > 0 and 1 < k - born <= 50 and L[k] <= zt and C[k] > zb and C[k] > O[k]:
            sig[k] = True; stop[k] = zb - 0.1 * A[k]; born = -100
    return sig, stop
def prev_swing_val(shi, v):
    out = np.full(len(shi), np.nan); prev_i = -1; cur = -1
    for k in range(len(shi)):
        if shi[k] != cur: prev_i, cur = cur, shi[k]
        out[k] = v[prev_i] if prev_i >= 0 else np.nan
    return out
# ---------------------------------------------------------------- exits (numba)
@njit(cache=True)
def nb_exit(O, H, L, C, A, SLL, SHL, ks, ds, stops, cost, swap_bar, mode, par, cap):
    n = len(ks); R = np.full(n, np.nan); XK = np.full(n, -1)
    N = len(C)
    for t in range(n):
        k = ks[t]; d = ds[t]
        if k + 2 >= N: continue
        e = O[k + 1]; a = A[k]
        if not np.isfinite(a) or a <= 0: continue
        st = stops[t]
        if mode == 1 or mode == 2: st = e - d * 2 * a
        risk = d * (e - st)
        if not np.isfinite(risk) or risk <= 3 * cost * abs(e) or risk > 6 * a: continue
        tp = e + d * (par if mode == 0 else 2.0) * risk if (mode == 0 or mode == 1) else np.nan
        best = e; x = np.nan; xk = -1; half = False; stop = st; last = min(k + cap, N - 1)
        if mode == 5: last = min(k + 10, N - 1)
        if mode == 3: last = min(k + 20, N - 1)
        for j in range(k + 1, last + 1):
            hitS = (d > 0 and L[j] <= stop) or (d < 0 and H[j] >= stop)
            if hitS:
                px = stop
                if (d > 0 and O[j] < stop) or (d < 0 and O[j] > stop): px = O[j]
                x = (0.5 * (d * (px - e)) + 0.5 * risk) if half else d * (px - e); xk = j; break
            if mode == 0 or mode == 1:
                if (d > 0 and H[j] >= tp) or (d < 0 and L[j] <= tp): x = d * (tp - e); xk = j; break
            if mode == 4 and not half and ((d > 0 and H[j] >= e + risk) or (d < 0 and L[j] <= e - risk)): half = True
            if mode == 2 or mode == 4:
                if d > 0: best = max(best, C[j]); nst = best - (3.0 if mode == 2 else 2.0) * A[j]; stop = max(stop, nst) if (mode == 2 or half) else stop
                else: best = min(best, C[j]); nst = best + (3.0 if mode == 2 else 2.0) * A[j]; stop = min(stop, nst) if (mode == 2 or half) else stop
            if mode == 3:
                if (d > 0 and np.isfinite(SLL[j]) and C[j] < SLL[j] and SLL[j] < e + 10 * a) or (d < 0 and np.isfinite(SHL[j]) and C[j] > SHL[j] and SHL[j] > e - 10 * a):
                    x = d * (C[j] - e); xk = j; break
        if xk < 0:
            xk = last; x = (0.5 * d * (C[last] - e) + 0.5 * risk) if half else d * (C[last] - e)
        R[t] = (x - cost * abs(e) - swap_bar * abs(e) * (xk - k)) / risk; XK[t] = xk
    return R, XK
@njit(cache=True)
def nb_nonoverlap(ks, xks, mask):
    keep = np.zeros(len(ks), np.bool_); last = -1
    for t in range(len(ks)):
        if mask[t] and xks[t] >= 0 and ks[t] >= last: keep[t] = True; last = xks[t]
    return keep
EXITS = {"Initial stop beyond the setup invalidation point; test fixed 1R, 1.5R and 2R targets.": [("fixed 1R", 0, 1.0), ("fixed 1.5R", 0, 1.5), ("fixed 2R", 0, 2.0)],
         "ATR-based initial stop; compare fixed-R target with an ATR trailing exit.": [("2ATR stop, 2R target", 1, 2.0), ("2ATR stop, 3ATR trail", 2, 0.0)],
         "Structure-based stop; exit on opposite structure break or pre-defined time stop.": [("structure exit / 20-bar time stop", 3, 0.0)],
         "Scale-out at 1R and trail the remainder; include spread and commission in results.": [("half at 1R, trail rest 2ATR", 4, 0.0)],
         "Time-based exit after a fixed number of bars; compare with a structure invalidation exit.": [("time exit 10 bars", 5, 0.0), ("invalidation stop only, 50-bar cap", 6, 0.0)]}
FILTERS = ["Only take signals aligned with the next higher timeframe.", "Skip entries when spread exceeds a pre-defined instrument-specific ceiling.",
           "Trade only inside a pre-defined ATR percentile band.", "Skip the firm's restricted high-impact news window; verify the exact rulebook.",
           "Allow entries only inside a fixed liquid session window.", "Test each weekday separately, then retain only effects that persist out of sample.",
           "Require tick volume above its rolling median or percentile.", "Skip when ADX/efficiency ratio indicates a non-directional market.",
           "Block entries that would exceed the total risk limit for correlated instruments.", "Require candle close confirmation; do not trigger on an unconfirmed intrabar touch."]
def filt_masks(b, Xp, ks, ds):
    """per-signal boolean masks for filters 0..9 (5 = weekday, resolved later)."""
    T = b.index; hr = T.hour.to_numpy()[ks]; hx = Xp.htf(); C = b.c.to_numpy()[ks]
    m = {}
    m[0] = np.where(ds > 0, (hx["c"][ks] > hx["e"][ks]), (hx["c"][ks] < hx["e"][ks]))
    lt = T.tz_convert("UTC"); wk = lt.dayofweek.to_numpy()[ks]; mon_open = (wk == 0) & (hr < 1) if MK[Xp.sym][5] != "crypto" else np.zeros(len(ks), bool)
    m[1] = ~((hr >= 21) & (hr <= 23)) & ~mon_open
    ap = pct_rank(Xp.atr(), 500)[ks]; m[2] = (ap >= 0.2) & (ap <= 0.8)
    ny = T.tz_convert("America/New_York"); mn = (ny.hour * 60 + ny.minute).to_numpy()[ks]; wd = ny.dayofweek.to_numpy()[ks]
    m[3] = ~(((mn >= 500) & (mn < 530)) | ((mn >= 595) & (mn < 610)) | ((wd == 2) & (mn >= 830) & (mn < 885)))
    m[4] = (hr >= 7) & (hr < 20)
    m[5] = np.ones(len(ks), bool)
    V = b.v.fillna(0).to_numpy(); med = pd.Series(V).rolling(100).median().to_numpy()
    m[6] = (V[ks] > med[ks]) if Xp.hasvol else np.zeros(len(ks), bool)
    m[7] = Xp.er(20)[ks] >= 0.3
    m[8] = np.ones(len(ks), bool); m[9] = np.ones(len(ks), bool)
    return {k: np.nan_to_num(v.astype(float)).astype(bool) for k, v in m.items()}
CAT = pd.read_excel("cat1000/cat.xlsx", sheet_name=0)
CAT["base_n"] = (np.arange(len(CAT)) // 10) + 1; assert CAT.groupby("base_n")["Core entry logic"].nunique().max() == 1; CAT["fidx"] = CAT["Additional filter"].map({f: i for i, f in enumerate(FILTERS)})
def run(job):
    sym, tf = job; b = bars(sym, tf)
    if b is None or len(b) < 5000: return []
    extra = {}
    try:
        if PAIR.get(sym):
            o = bars(PAIR[sym], tf)
            if o is not None:
                la = np.log(b.c); lb = np.log(o.c.reindex(b.index, method="ffill", limit=2)); W = 500
                mp = W // 2; beta = la.rolling(W, min_periods=mp).cov(lb) / lb.rolling(W, min_periods=mp).var(); res = la - beta * lb; extra["pairz"] = ((res - res.rolling(W, min_periods=mp).mean()) / res.rolling(W, min_periods=mp).std()).to_numpy()
        if LEAD.get(sym):
            o = bars(LEAD[sym], tf)
            if o is not None:
                lr = np.log(o.c).diff(); lz = (lr / lr.rolling(200).std()).reindex(b.index); lz[~b.index.isin(o.index)] = np.nan; extra["lead"] = lz.to_numpy()
    except Exception as ex: print(sym, tf, "extra fail", ex, flush=True)
    Xp = X(b, sym, tf, False, extra); Xp.MKc = MK[sym][5]
    ex_n = {k: (-v if v is not None else None) for k, v in extra.items()}; Xn = X(b, sym, tf, True, ex_n); Xn.MKc = MK[sym][5]
    try: Sp = S(Xp); Sn = S(Xn)
    except Exception as ex:
        import traceback; traceback.print_exc(); return []
    O, H, L, C = (b[c].to_numpy() for c in "ohlc"); A = Xp.atr(); shl, shp, shi, sll, slp, sli = Xp.sw()
    cost = MK[sym][2]; swap_bar = MK[sym][3] / 365 * (0.25 if tf == "M15" else 1.0) / 24; T = b.index; yr = T.year.to_numpy()
    rows = []; keep_tr = {}
    for bn in range(1, 101):
        try:
            sp, stp = Sp[bn]; sn, stn = Sn[bn]
        except Exception as ex: print("setup", bn, "missing", ex, flush=True); continue
        sp = np.nan_to_num(np.asarray(sp, dtype=float)).astype(bool); sn = np.nan_to_num(np.asarray(sn, dtype=float)).astype(bool)
        sp[-3:] = False; sn[-3:] = False
        kp = np.where(sp)[0]; kn = np.where(sn)[0]
        ks = np.r_[kp, kn]; ds = np.r_[np.ones(len(kp)), -np.ones(len(kn))]; stops = np.r_[np.asarray(stp, float)[kp], -np.asarray(stn, float)[kn]]
        o_ = np.argsort(ks, kind="stable"); ks, ds, stops = ks[o_].astype(np.int64), ds[o_], stops[o_]
        if len(ks) == 0:
            for _, r in CAT[CAT.base_n == bn].iterrows():
                for nm, md, pr in EXITS[r["Exit / risk experiment"]]: rows.append(dict(ID=r.ID, base=bn, sym=sym, tf=tf, exit=nm, n=0))
            continue
        FM = filt_masks(b, Xp, ks, ds); res = {}
        for r_i, r in CAT[CAT.base_n == bn].iterrows():
            for nm, md, pr in EXITS[r["Exit / risk experiment"]]:
                if (md, pr) not in res: res[(md, pr)] = nb_exit(O, H, L, C, A, sll, shl, ks, ds, stops, cost, swap_bar, md, pr, 50)
                R, XK = res[(md, pr)]; mask = FM[int(r.fidx)] & np.isfinite(R)
                if int(r.fidx) == 5:                                         # weekday: learn on the train period only
                    tr = mask & (T[ks] < SPLIT); wdv = T[ks].dayofweek.to_numpy()
                    good = [w for w in range(7) if (tr & (wdv == w)).sum() >= 10 and np.nanmean(R[tr & (wdv == w)]) > 0]
                    mask = mask & np.isin(wdv, good)
                kp_ = nb_nonoverlap(ks, XK, mask); rr = R[kp_]; tt = T[ks][kp_]; tr = tt < SPLIT
                def tst(v): return float(v.mean() / v.std(ddof=1) * np.sqrt(len(v))) if len(v) > 2 and v.std() > 0 else np.nan
                yrs = pd.Series(rr).groupby(yr[ks][kp_]).sum() if len(rr) else pd.Series(dtype=float)
                rows.append(dict(ID=r.ID, base=bn, sym=sym, tf=tf, exit=nm, n=int(len(rr)), n_train=int(tr.sum()), n_hold=int((~tr).sum()),
                                 avgR=float(rr.mean()) if len(rr) else np.nan, avgR_train=float(rr[tr].mean()) if tr.sum() else np.nan,
                                 avgR_hold=float(rr[~tr].mean()) if (~tr).sum() else np.nan, t_train=tst(rr[tr]), t_hold=tst(rr[~tr]),
                                 win=float((rr > 0).mean()) if len(rr) else np.nan, pos_years=int((yrs > 0).sum()), years=int(len(yrs)),
                                 pf=float(rr[rr > 0].sum() / -rr[rr < 0].sum()) if (rr < 0).any() else np.nan))
                if len(rr) >= 30 and np.isfinite(rows[-1]["t_train"]) and rows[-1]["t_train"] > 2:
                    keep_tr[(r.ID, sym, tf, nm)] = (tt.values, rr.astype(np.float32))
    print(f"{sym} {tf}: {len(rows)} results", flush=True)
    pd.to_pickle(keep_tr, f"cat1000/trades_{sym}_{tf}.pkl"); return rows
if __name__ == "__main__":
    jobs = [(s, tf) for s in MK for tf in ("M15", "H1") if not (tf == "M15" and MK[s][0] is None)]
    if len(sys.argv) > 1: jobs = [tuple(j.split(":")) for j in sys.argv[1:]]
    with Pool(4) as p: res = p.map(run, jobs, chunksize=1)
    D = pd.DataFrame([r for o in res for r in o]); D.to_pickle("cat1000/results.pkl" if len(sys.argv) == 1 else "cat1000/results_partial.pkl"); print("rows", len(D))
