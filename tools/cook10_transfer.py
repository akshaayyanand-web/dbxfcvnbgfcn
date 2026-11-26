# Transfer the pack's proven rule families to markets they do not run on yet. Pre-registered rules (EA logic, fixed parameters):
#  ORB  : range = first 15 min after the home open; first M5 close outside it within 2h -> next bar open; stop other side; target 2R; flat open+6h25.
#  BO15 : M15, open .. open+2h30: close > highest high of the previous 20 bars and > EMA200 (mirror short); stop 1 ATR14; flat open+6h20; one at a time.
#  DIP  : H1, RSI(2) < 15, close > EMA200, daily close >= 92% of 30 days ago; long; stop 2 ATR14; exit after 48 bars.
#  REV  : M5, |close / EMA200 - 1| > 4 sigma (rolling 4000 bars) with the move in the EMA800-slope direction -> fade; stop = half the stretch; exit 60 min.
#  FADE : 15-min move from the home open, |move| > 1.5x its rolling 60-session median; fade at open+15m; stop = the move; exit after 30 min.
# Costs: spread round trip per market (+swap for H1 holds). Pass rule: train t >= 2, holdout t >= 1.5 and holdout avg >= +0.05R.
import sys, numpy as np, pandas as pd, warnings
from multiprocessing import Pool
sys.argv = sys.argv[:1]
import cat1000 as K
warnings.filterwarnings("ignore")
def m5(sym):
    if sym in ("BTC", "ETH", "SOL", "XRP"): raw = K.crypto(sym) if sym in ("BTC", "ETH") else __import__("cat1000").crypto(sym)
    elif sym == "XAU": raw = K.m1_csv("fut1m/XAUUSD_1m.csv")
    elif sym == "SPX": raw = K.m1_csv("fut1m/USA500IDXUSD_1m.csv")
    elif sym == "NQ": raw = K.m1_csv("fut1m/USATECHIDXUSD_1m.csv")
    elif sym == "DAX": raw = K.m1_csv("eu1m/DEUIDXEUR_1m.csv")
    elif sym == "EURUSD": raw = K.m1_csv("fx1m/EURUSD_1m.csv")
    else: raw = K.hd(sym)
    return K.rs(raw, "5min")
def h1(sym):
    if sym in ("DOW", "RUT", "XAG"): return K.duka_h({"DOW": "USA30IDXUSD", "RUT": "USSC2000IDXUSD", "XAG": "XAGUSD"}[sym])
    return K.rs(m5(sym), "1h")
COST = {"SPX": .00015, "NQ": .00015, "DAX": .00015, "DOW": .00015, "RUT": .0003, "XAU": .00012, "XAG": .0008, "EURUSD": .00008, "GBPUSD": .00009, "USDJPY": .00007,
        "BTC": .0009, "ETH": .00227, "XRP": .002}
SWAP = {"SPX": .05, "NQ": .05, "DAX": .05, "DOW": .05, "RUT": .05, "XAU": .04, "XAG": .04, "EURUSD": .02, "GBPUSD": .02, "USDJPY": .02, "BTC": .15, "ETH": .15, "XRP": .15}
HOME = {"NY": ("America/New_York", 9, 30), "LDN": ("Europe/London", 8, 0), "FRA": ("Europe/Berlin", 9, 0)}
def walk(O, H, L, C, i0, i1, d, e, stop, tp):
    for q in range(i0, i1):
        if (d > 0 and L[q] <= stop) or (d < 0 and H[q] >= stop): return (min(O[q], stop) if d > 0 else max(O[q], stop)), q
        if tp is not None and ((d > 0 and H[q] >= tp) or (d < 0 and L[q] <= tp)): return tp, q
    return C[i1 - 1], i1 - 1
def session(b, home):
    tz, hh, mm = HOME[home]; lt = b.index.tz_convert(tz); mins = (lt.hour * 60 + lt.minute).to_numpy() - (hh * 60 + mm); day = K.dayno(lt); return mins, day
def ema(x, n): return pd.Series(x).ewm(span=n, adjust=False).mean().to_numpy()
def atr(b, n=14):
    h, l, c = b.h.to_numpy(), b.l.to_numpy(), b.c.to_numpy(); pc = np.r_[c[0], c[:-1]]
    return pd.Series(np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))).ewm(alpha=1 / n, adjust=False).mean().to_numpy()
def ORB(sym, home):
    b = m5(sym); mins, day = session(b, home); O, H, L, C = (b[c].to_numpy() for c in "ohlc"); T = b.index; out = []
    for d_ in np.unique(day):
        ix = np.where(day == d_)[0]; m = mins[ix]; rng = ix[(m >= 0) & (m < 15)]
        if len(rng) < 3: continue
        hi, lo = H[rng].max(), L[rng].min(); win = ix[(m >= 15) & (m < 120)]; endk = ix[(m < 385)][-1] if (m < 385).any() else None
        for k in win:
            if k + 1 > endk: break
            dr = 1 if C[k] > hi else (-1 if C[k] < lo else 0)
            if not dr: continue
            e = O[k + 1]; stop = lo if dr > 0 else hi; risk = dr * (e - stop)
            if risk <= 3 * COST[sym] * e: break
            x, _ = walk(O, H, L, C, k + 1, endk + 1, dr, e, stop, e + dr * 2 * risk); out.append((T[k], (dr * (x - e) - COST[sym] * e) / risk)); break
    return out
def BO15(sym, home):
    b = K.rs(m5(sym), "15min"); mins, day = session(b, home); O, H, L, C = (b[c].to_numpy() for c in "ohlc"); T = b.index; A = atr(b); E = ema(C, 200)
    hh = pd.Series(H).rolling(20).max().shift(1).to_numpy(); ll = pd.Series(L).rolling(20).min().shift(1).to_numpy(); out = []; busy = -1
    for k in range(250, len(C) - 2):
        if k <= busy or not (0 <= mins[k] < 150): continue
        dr = 1 if (C[k] > hh[k] and C[k] > E[k]) else (-1 if (C[k] < ll[k] and C[k] < E[k]) else 0)
        if not dr: continue
        e = O[k + 1]; stop = e - dr * A[k]; risk = A[k]
        if risk <= 3 * COST[sym] * e: continue
        end = k + 1
        while end < len(C) - 1 and day[end] == day[k] and mins[end] < 380: end += 1
        x, q = walk(O, H, L, C, k + 1, end, dr, e, stop, None); out.append((T[k], (dr * (x - e) - COST[sym] * e) / risk)); busy = q
    return out
def DIP(sym):
    b = h1(sym).dropna(); O, H, L, C = (b[c].to_numpy() for c in "ohlc"); T = b.index; A = atr(b); E = ema(C, 200)
    d = pd.Series(C, T); dc = d.resample("1D").last().dropna(); crash = (dc >= 0.92 * dc.shift(30)).reindex(T, method="ffill").fillna(False).to_numpy()
    dl = np.diff(C, prepend=np.nan); up = pd.Series(np.where(dl > 0, dl, 0)).ewm(alpha=.5, adjust=False).mean(); dn = pd.Series(np.where(dl < 0, -dl, 0)).ewm(alpha=.5, adjust=False).mean()
    rsi2 = (100 - 100 / (1 + up / dn.replace(0, np.nan))).to_numpy(); out = []; busy = -1
    for k in range(250, len(C) - 2):
        if k <= busy or not (rsi2[k] < 15 and C[k] > E[k] and crash[k]): continue
        e = O[k + 1]; stop = C[k] - 2 * A[k]; risk = e - stop
        if risk <= 3 * COST[sym] * e: continue
        x, q = walk(O, H, L, C, k + 1, min(k + 49, len(C)), 1, e, stop, None)
        out.append((T[k], (x - e - COST[sym] * e - SWAP[sym] / 365 * (q - k) / 24 * e) / risk)); busy = q
    return out
def REV(sym):
    b = m5(sym); O, H, L, C = (b[c].to_numpy() for c in "ohlc"); T = b.index; E2, E8 = ema(C, 200), ema(C, 800)
    dist = C / E2 - 1; sd = pd.Series(dist).rolling(4000, min_periods=2000).std().to_numpy(); sl = np.sign(E8 - np.r_[np.full(30, np.nan), E8[:-30]]); out = []; busy = -1
    for k in range(4000, len(C) - 14):
        if k <= busy or not np.isfinite(sd[k]) or abs(dist[k]) < 4 * sd[k] or np.sign(dist[k]) != sl[k]: continue
        dr = -int(np.sign(dist[k])); e = O[k + 1]; risk = 0.5 * abs(C[k] - E2[k]); stop = e - dr * risk
        if risk <= 3 * COST[sym] * e: continue
        x, q = walk(O, H, L, C, k + 1, k + 13, dr, e, stop, None); out.append((T[k], (dr * (x - e) - COST[sym] * e) / risk)); busy = q
    return out
def FADE(sym, home):
    b = m5(sym); mins, day = session(b, home); O, H, L, C = (b[c].to_numpy() for c in "ohlc"); T = b.index; rows = []
    for d_ in np.unique(day):
        ix = np.where(day == d_)[0]; m = mins[ix]; a = ix[m == 0]; z = ix[m == 15]
        if len(a) and len(z): rows.append((d_, a[0], z[0], C[z[0] - 1] - O[a[0]]))
    mv = pd.Series([r[3] for r in rows]); med = mv.abs().rolling(60, min_periods=30).median().shift(1).to_numpy(); out = []
    for (d_, a, z, m_), md in zip(rows, med):
        if not np.isfinite(md) or abs(m_) < 1.5 * md: continue
        dr = -int(np.sign(m_)); e = O[z]; risk = abs(m_); stop = e - dr * risk
        if risk <= 3 * COST[sym] * e: continue
        x, _ = walk(O, H, L, C, z, min(z + 6, len(C)), dr, e, stop, None); out.append((T[z], (dr * (x - e) - COST[sym] * e) / risk))
    return out
JOBS = [("ORB", s, h) for s, h in (("SPX", "NY"), ("XAU", "NY"), ("XAU", "LDN"), ("EURUSD", "LDN"), ("GBPUSD", "LDN"), ("BTC", "NY"), ("ETH", "NY"))] + \
       [("BO15", s, h) for s, h in (("XAU", "NY"), ("DAX", "FRA"), ("EURUSD", "LDN"), ("GBPUSD", "LDN"), ("BTC", "NY"), ("ETH", "NY"))] + \
       [("DIP", s, None) for s in ("DOW", "RUT", "DAX", "XAG", "ETH", "XRP", "EURUSD", "GBPUSD", "USDJPY")] + [("REV", s, None) for s in ("ETH", "XAU", "NQ", "SPX")] + \
       [("FADE", s, h) for s, h in (("DAX", "FRA"), ("XAU", "NY"), ("BTC", "NY"), ("ETH", "NY"))]
def run(j):
    fam, sym, home = j
    try: tr = {"ORB": ORB, "BO15": BO15, "FADE": FADE}[fam](sym, home) if fam in ("ORB", "BO15", "FADE") else {"DIP": DIP, "REV": REV}[fam](sym)
    except Exception as ex: print(j, "fail", ex, flush=True); return None
    D = pd.DataFrame(tr, columns=["t", "R"])
    if len(D) < 30: return dict(family=fam, market=sym, session=home, trades=len(D))
    S = pd.Timestamp("2023-01-01", tz="UTC"); A, B = D[D.t < S].R, D[D.t >= S].R; tt = lambda v: round(v.mean() / v.std(ddof=1) * np.sqrt(len(v)), 2) if len(v) > 2 else np.nan
    yrs = D.groupby(D.t.dt.year).R.sum(); D.to_pickle(f"transfer_{fam}_{sym}_{home}.pkl")
    r = dict(family=fam, market=sym, session=home, trades=len(D), per_yr=round(len(D) / max((D.t.max() - D.t.min()).days / 365, 1), 1), win=round(100 * (D.R > 0).mean()),
             avgR_train=round(A.mean(), 3), t_train=tt(A), avgR_hold=round(B.mean(), 3), t_hold=tt(B), pos_years=f"{(yrs > 0).sum()}/{len(yrs)}")
    r["PASS"] = bool(r["t_train"] >= 2 and r["t_hold"] >= 1.5 and r["avgR_hold"] >= 0.05); print(r, flush=True); return r
if __name__ == "__main__":
    with Pool(4) as p: res = [r for r in p.map(run, JOBS, chunksize=1) if r]
    R = pd.DataFrame(res); R.to_csv("transfer.csv", index=False); pd.set_option("display.width", 220); print(R.to_string(index=False))
