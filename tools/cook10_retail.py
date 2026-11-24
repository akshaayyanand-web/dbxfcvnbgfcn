# Popular retail systems with textbook settings, 19 symbols, real costs: Supertrend(10,3), Ichimoku TK cross with cloud filter, EMA 9/21 cross,
# daily inside-bar and NR7 breakouts (5m triggers), floor-pivot R1/S1 fade. Pre-registered; pooled and by class.
import numpy as np, pandas as pd
from multiprocessing import Pool
exec(open("methods.py").read().split("def run(")[0])
def trend_system(O, H, L, C, T, sig_fn):
    """sig_fn(k) -> (+1/-1/0 new signal at bar k close, stop level). Enter next open; exit at stop or on an opposite signal (next open)."""
    out = []; pos = 0; e = stop = None; i_e = None
    for k in range(60, len(C) - 1):
        if pos:
            if (pos > 0 and L[k] <= stop) or (pos < 0 and H[k] >= stop):
                x = min(O[k], stop) if pos > 0 else max(O[k], stop); out.append((T[i_e], pos, e, risk0, x)); pos = 0
        s, st = sig_fn(k)
        if s and s != pos:
            if pos: out.append((T[i_e], pos, e, risk0, O[k + 1])); pos = 0
            e = O[k + 1]; stop = st; risk0 = abs(e - st)
            if risk0 > 0 and (e - st) * s > 0: pos = s; i_e = k + 1
        elif pos and st is not None and np.isfinite(st):
            stop = max(stop, st) if pos > 0 else min(stop, st)          # trailing systems tighten the stop
    return out
def run(name):
    loader, cost, cls = SRC[name]
    try: raw = loader()
    except Exception: return []
    b5 = rs(raw, "5min") if (raw.index[1] - raw.index[0]) < pd.Timedelta("5min") else raw
    out = []
    def addR(method, tf, lst):
        for t, d, e, risk, x in lst:
            if risk < 3 * cost * e: continue
            out.append((name, cls, method, tf, t, d * (x - e) / risk - cost * e / risk))
    for tf in ("1h", "4h"):
        hb = rs(b5, tf); O, H, L, C = (hb[c].to_numpy() for c in "ohlc"); T = hb.index; A10 = atr(H, L, C, 10); A14 = atr(H, L, C, 14)
        # Supertrend(10,3)
        hl2 = (H + L) / 2; ub = hl2 + 3 * A10; lb = hl2 - 3 * A10; fub = ub.copy(); flb = lb.copy(); dirn = np.ones(len(C)); st = np.full(len(C), np.nan)
        for k in range(1, len(C)):
            if not np.isfinite(A10[k]): continue
            fub[k] = ub[k] if (not np.isfinite(fub[k - 1]) or ub[k] < fub[k - 1] or C[k - 1] > fub[k - 1]) else fub[k - 1]
            flb[k] = lb[k] if (not np.isfinite(flb[k - 1]) or lb[k] > flb[k - 1] or C[k - 1] < flb[k - 1]) else flb[k - 1]
            dirn[k] = 1 if C[k] > fub[k - 1] else (-1 if C[k] < flb[k - 1] else dirn[k - 1]); st[k] = flb[k] if dirn[k] > 0 else fub[k]
        addR("Supertrend", tf, trend_system(O, H, L, C, T, lambda k: ((int(dirn[k]) if dirn[k] != dirn[k - 1] else 0), st[k])))
        # Ichimoku
        hh = lambda n: pd.Series(H).rolling(n).max().to_numpy(); ll = lambda n: pd.Series(L).rolling(n).min().to_numpy()
        tk = (hh(9) + ll(9)) / 2; kj = (hh(26) + ll(26)) / 2; sa = np.r_[np.full(26, np.nan), ((tk + kj) / 2)[:-26]]; sb = np.r_[np.full(26, np.nan), ((hh(52) + ll(52)) / 2)[:-26]]
        def ich(k):
            if not (np.isfinite(sa[k]) and np.isfinite(sb[k])): return 0, kj[k]
            up = tk[k] > kj[k] and tk[k - 1] <= kj[k - 1] and C[k] > max(sa[k], sb[k]); dn = tk[k] < kj[k] and tk[k - 1] >= kj[k - 1] and C[k] < min(sa[k], sb[k])
            return (1 if up else (-1 if dn else 0)), kj[k]
        addR("Ichimoku", tf, trend_system(O, H, L, C, T, ich))
        # EMA 9/21 cross, stop 2 ATR (fixed)
        e9 = pd.Series(C).ewm(span=9, adjust=False).mean().to_numpy(); e21 = pd.Series(C).ewm(span=21, adjust=False).mean().to_numpy()
        def ema(k):
            s = 1 if (e9[k] > e21[k] and e9[k - 1] <= e21[k - 1]) else (-1 if (e9[k] < e21[k] and e9[k - 1] >= e21[k - 1]) else 0)
            return s, (C[k] - s * 2 * A14[k]) if s else np.nan
        addR("EMA9/21", tf, trend_system(O, H, L, C, T, ema))
    # daily patterns triggered on 5m
    db = rs(b5, "1D"); DO, DH, DL, DC = (db[c].to_numpy() for c in "ohlc"); DT = db.index; DA = atr(DH, DL, DC, 14)
    O5, H5, L5, C5, T5 = (b5[c].to_numpy() for c in "ohlc"), None, None, None, b5.index
    O5, H5, L5, C5 = (b5[c].to_numpy() for c in "ohlc")
    rng7 = pd.Series(DH - DL).rolling(7).min().to_numpy()
    for k in range(8, len(db) - 1):
        i0, i1 = T5.searchsorted(DT[k + 1]), T5.searchsorted(DT[k + 1] + pd.Timedelta("1D"))
        if i1 - i0 < 20: continue
        for method, cond in (("InsideBar", DH[k] < DH[k - 1] and DL[k] > DL[k - 1]), ("NR7", (DH[k] - DL[k]) <= rng7[k])):
            if not cond: continue
            hi, lo = DH[k], DL[k]; trig = None
            for q in range(i0, i1):
                if H5[q] > hi: trig = (q, 1, hi, lo); break
                if L5[q] < lo: trig = (q, -1, lo, hi); break
            if trig:
                q, d, e, stp = trig; risk = abs(e - stp); tp = e + d * 2 * risk
                x, _ = first_hit(O5, H5, L5, C5, q, i1, d, e, stp, tp)
                if risk >= 3 * cost * e: out.append((name, cls, method, "1D", T5[q], d * (x - e) / risk - cost * e / risk))
        # floor pivots from day k for day k+1
        P = (DH[k] + DL[k] + DC[k]) / 3; R1 = 2 * P - DL[k]; S1 = 2 * P - DH[k]; a = DA[k]
        if np.isfinite(a):
            for lvl, d in ((R1, -1), (S1, 1)):
                j = next((q for q in range(i0, i1) if L5[q] <= lvl <= H5[q]), None)
                if j is None: continue
                stp = lvl - d * 0.5 * a; x, _ = first_hit(O5, H5, L5, C5, j, i1, d, lvl, stp, P)
                risk = abs(lvl - stp)
                if (P - lvl) * d > 0 and risk >= 3 * cost * lvl: out.append((name, cls, "Pivot R1/S1 fade", "1D", T5[j], d * (x - lvl) / risk - cost * lvl / risk))
    return out
if __name__ == "__main__":
    with Pool(4) as p: res = p.map(run, list(SRC))
    D = pd.DataFrame([r for o in res for r in o], columns=["sym", "cls", "method", "tf", "t", "R"]); D.to_pickle("retail_trades.pkl")
    S = pd.Timestamp("2023-01-01", tz="UTC")
    def summ(g):
        a, b = g[g.t < S].R, g[g.t >= S].R; tt = lambda v: round(v.mean() / v.std(ddof=1) * np.sqrt(len(v)), 2) if len(v) > 2 else np.nan
        return pd.Series(dict(trades=len(g), win=round(100 * (g.R > 0).mean()), avgR=round(g.R.mean(), 3), t_pre2023=tt(a), t_2023on=tt(b)))
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 300)
    print("POOLED (19 symbols):"); print(D.groupby(["method", "tf"]).apply(summ).to_string())
    print("\nBY CLASS:"); print(D.groupby(["method", "tf", "cls"]).apply(summ).to_string())
    b = D.groupby(["method", "tf", "sym"]).apply(summ); b = b[(b.t_pre2023 > 2) & (b.t_2023on > 2)]
    print("\nsymbol/method combos with t>2 in BOTH periods:"); print(b.to_string() if len(b) else "none")
