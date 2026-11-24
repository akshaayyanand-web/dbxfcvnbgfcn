# Two crypto candidates with the 21-EA book, hourly mark-to-market:
#   A = CFD-0262: ETH M15 multi-day consolidation breakout (catalogue 1 base 27, spread-ceiling filter), 2ATR stop + 3ATR trail.
#   B = #448: BTC M15 jump direction persistence (|bar| > 4 sigma, follow), 2ATR stop + 3ATR trail.
# Trades rebuilt with entry price, direction, stop distance and exit bar; P&L marked to the hourly close (worst price inside the hour
# for the drawdown side), spread + swap charged at the exit. Cost x1 and x2. The5ers High Stakes (3x) and Bootcamp.
import sys, os, numpy as np, pandas as pd
sys.argv = sys.argv[:1]
import cat1000 as K, cat2000 as K2
def trades(which, cost_mult):
    if which == "A": sym, tf = "ETH", "M15"; b = K.bars(sym, tf)
    else: sym, tf = "BTC", "M15"; b = K2.bars2(sym, tf)
    Xp = K.X(b, sym, tf, False, {}); Xn = K.X(b, sym, tf, True, {}); Xp.MKc = Xn.MKc = K.MK[sym][5]
    if which == "A": Sp, Sn = K.S(Xp)[27], K.S(Xn)[27]
    else:
        Xp.extra["tb"] = b.tb.to_numpy(); Xn.extra["tb"] = b.tb.to_numpy(); Sp, Sn = K2.S2(Xp, b)[448], K2.S2(Xn, b)[448]
    sp = np.nan_to_num(np.asarray(Sp[0], float)).astype(bool); sn = np.nan_to_num(np.asarray(Sn[0], float)).astype(bool); sp[-3:] = sn[-3:] = False
    kp, kn = np.where(sp)[0], np.where(sn)[0]; ks = np.r_[kp, kn]; ds = np.r_[np.ones(len(kp)), -np.ones(len(kn))]
    st = np.r_[np.asarray(Sp[1], float)[kp], -np.asarray(Sn[1], float)[kn]]; o = np.argsort(ks, kind="stable"); ks, ds, st = ks[o].astype(np.int64), ds[o], st[o]
    if which == "A": m = K.filt_masks(b, Xp, ks, ds)[1]
    else: m = np.ones(len(ks), bool)
    O, H, L, C = (b[c].to_numpy() for c in "ohlc"); A = Xp.atr(); shl, _, _, sll, _, _ = Xp.sw()
    c0 = K.MK[sym][2]; sw = K.MK[sym][3] / 365 * 0.25 / 24
    R, XK = K.nb_exit(O, H, L, C, A, sll, shl, ks, ds, st, c0, sw, 2, 0.0, 50)     # base cost decides which trades exist (same as the scan)
    keep = K.nb_nonoverlap(ks, XK, m & np.isfinite(R))
    ks, ds, XK, R = ks[keep], ds[keep], XK[keep], R[keep]; e = O[ks + 1]; risk = 2 * A[ks]
    gross = R * risk + c0 * e + sw * e * (XK - ks); xpx = e + ds * gross                # exact exit price from the engine
    Rn = (gross - cost_mult * c0 * e - sw * e * (XK - ks)) / risk
    T = b.index
    return pd.DataFrame({"t_in": T[ks + 1], "t_out": T[XK] + pd.Timedelta("15min"), "d": ds, "e": e, "risk": risk, "x": xpx, "R": Rn, "notional_x_risk": e / risk, "sym": sym})
if __name__ == "__main__":
    TR = {}
    for w in ("A", "B"):
        for cm in (1.0, 2.0):
            TR[(w, cm)] = trades(w, cm); t = TR[(w, cm)]; S = pd.Timestamp("2023-01-01", tz="UTC")
            tt = lambda v: round(v.mean() / v.std() * np.sqrt(len(v)), 2)
            print(f"{w} cost x{cm:.0f}: {len(t)} trades, avg R {t.R.mean():+.3f} | train {t.R[t.t_in < S].mean():+.3f} (t {tt(t.R[t.t_in < S])}) | holdout {t.R[t.t_in >= S].mean():+.3f} (t {tt(t.R[t.t_in >= S])}) | median hold {((t.t_out - t.t_in).dt.total_seconds() / 3600).median():.1f}h", flush=True)
    pd.to_pickle(TR, "csleeve_trades.pkl")
