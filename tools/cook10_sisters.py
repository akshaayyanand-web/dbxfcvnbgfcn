# Sister variants of the pack's proven EAs (rules fixed before running), judged standalone then inside the book.
#  ORB-n: range = first n minutes after the home open (n = 15/30/60), first M5 close outside it within 2h after the range, stop other side,
#         target 2R, flat at open+6h25. Markets NQ, SPX (09:30 NY), DAX (09:00 Frankfurt).
#  DIP-tf: RSI(2) < 15, close > EMA200, crash filter, stop 2 ATR, exit after 96 hours worth of bars. NQ 1h/4h, SPX 2h/4h, BTC 1h/4h, XAU 2h/4h.
import sys, numpy as np, pandas as pd
exec(open("transfer.py").read().split("JOBS = ")[0])
COST.update(NQ=.00015, SPX=.00015, BTC=.0009)
def ORBn(sym, home, n):
    b = m5(sym); mins, day = session(b, home); O, H, L, C = (b[c].to_numpy() for c in "ohlc"); T = b.index; out = []
    for d_ in np.unique(day):
        ix = np.where(day == d_)[0]; m = mins[ix]; rng = ix[(m >= 0) & (m < n)]
        if len(rng) < n // 5 * 0.6: continue
        hi, lo = H[rng].max(), L[rng].min(); win = ix[(m >= n) & (m < n + 120)]; ek = ix[m < 385]
        if not len(ek): continue
        endk = ek[-1]
        for k in win:
            if k + 1 > endk: break
            dr = 1 if C[k] > hi else (-1 if C[k] < lo else 0)
            if not dr: continue
            e = O[k + 1]; stop = lo if dr > 0 else hi; risk = dr * (e - stop)
            if risk <= 3 * COST[sym] * e: break
            x, q = walk(O, H, L, C, k + 1, endk + 1, dr, e, stop, e + dr * 2 * risk); out.append((T[k], T[q], (dr * (x - e) - COST[sym] * e) / risk)); break
    return out
def DIPtf(sym, rule):
    b = (K.rs(m5(sym), rule) if sym != "XAU" else K.rs(m5(sym), rule)).dropna(); O, H, L, C = (b[c].to_numpy() for c in "ohlc"); T = b.index; A = atr(b); E = ema(C, 200)
    hold = int(96 / {"1h": 1, "2h": 2, "4h": 4}[rule]); bh = {"1h": 1, "2h": 2, "4h": 4}[rule]
    dc = pd.Series(C, T).resample("1D").last().dropna(); crash = (dc >= 0.92 * dc.shift(30)).reindex(T, method="ffill").fillna(False).to_numpy()
    dl = np.diff(C, prepend=np.nan); up = pd.Series(np.where(dl > 0, dl, 0)).ewm(alpha=.5, adjust=False).mean(); dn = pd.Series(np.where(dl < 0, -dl, 0)).ewm(alpha=.5, adjust=False).mean()
    rsi2 = (100 - 100 / (1 + up / dn.replace(0, np.nan))).to_numpy(); out = []; busy = -1
    for k in range(250, len(C) - 2):
        if k <= busy or not (rsi2[k] < 15 and C[k] > E[k] and crash[k]): continue
        e = O[k + 1]; stop = C[k] - 2 * A[k]; risk = e - stop
        if risk <= 3 * COST[sym] * e: continue
        x, q = walk(O, H, L, C, k + 1, min(k + 1 + hold, len(C)), 1, e, stop, None)
        out.append((T[k], T[q], (x - e - COST[sym] * e - SWAP.get(sym, .05) / 365 * (q - k) * bh / 24 * e) / risk)); busy = q
    return out
JOBS2 = [("ORB", s, h, n) for s, h in (("NQ", "NY"), ("SPX", "NY"), ("DAX", "FRA")) for n in (15, 30, 60)] + \
        [("DIP", s, None, r) for s, rs_ in (("NQ", ("1h", "4h")), ("SPX", ("2h", "4h")), ("BTC", ("1h", "4h")), ("XAU", ("2h", "4h"))) for r in rs_]
def run2(j):
    fam, sym, home, p = j
    tr = ORBn(sym, home, p) if fam == "ORB" else DIPtf(sym, p)
    D = pd.DataFrame(tr, columns=["t", "tx", "R"]); S = pd.Timestamp("2023-01-01", tz="UTC"); A_, B_ = D[D.t < S].R, D[D.t >= S].R
    tt = lambda v: round(v.mean() / v.std(ddof=1) * np.sqrt(len(v)), 2) if len(v) > 2 else np.nan
    yrs = D.groupby(D.t.dt.year).R.sum(); span = max((D.t.max() - D.t.min()).days / 365, 1)
    r = dict(variant=f"{fam}-{p} {sym}", trades=len(D), per_yr=round(len(D) / span), win=round(100 * (D.R > 0).mean()), R_yr=round(D.R.sum() / span, 1),
             avgR_train=round(A_.mean(), 3), t_train=tt(A_), avgR_hold=round(B_.mean(), 3), t_hold=tt(B_), pos_years=f"{(yrs > 0).sum()}/{len(yrs)}")
    r["PASS"] = bool(r["t_train"] >= 2 and r["t_hold"] >= 1.5); D.to_pickle(f"sister_{fam}_{sym}_{p}.pkl"); print(r, flush=True); return r
if __name__ == "__main__":
    with Pool(4) as p: res = p.map(run2, JOBS2, chunksize=1)
    R = pd.DataFrame(res); R.to_csv("sisters.csv", index=False); pd.set_option("display.width", 220); print(R.to_string(index=False))
