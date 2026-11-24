# MSNR (fresh A/V close levels, first-touch reaction), CRT (HTF candle sweep + close back inside -> opposite end), linear-regression channel
# (fade the band in the slope direction). 19 symbols (loaders from smc.py), real costs, pre-registered rules. Results pooled and by class.
import numpy as np, pandas as pd
from multiprocessing import Pool
exec(open("smc.py").read().split("def run_symbol(")[0])
def atr(h, l, c, n=14):
    pc = np.r_[c[0], c[:-1]]; tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc))); return pd.Series(tr).rolling(n).mean().shift(1).to_numpy()
def first_hit(O, H, L, C, i0, i1, d, e, stop, tp):
    """Walk bars i0..i1-1 after entry; stop checked first (conservative). Returns exit R in price units and bar."""
    for q in range(i0, i1):
        if (d > 0 and L[q] <= stop) or (d < 0 and H[q] >= stop): return (min(O[q], stop) if d > 0 else max(O[q], stop)), q
        if (d > 0 and H[q] >= tp) or (d < 0 and L[q] <= tp): return tp, q
    return C[i1 - 1], i1 - 1
def run(name):
    loader, cost, cls = SRC[name]
    try: raw = loader()
    except Exception as ex: return []
    b5 = rs(raw, "5min") if (raw.index[1] - raw.index[0]) < pd.Timedelta("5min") else raw
    O5, H5, L5, C5, T5 = b5.o.to_numpy(), b5.h.to_numpy(), b5.l.to_numpy(), b5.c.to_numpy(), b5.index; out = []
    def rec(method, tf, t, d, e, stop, x):
        risk = abs(e - stop)
        if risk < 3 * cost * e: return
        out.append((name, cls, method, tf, t, d * (x - e) / risk - cost * e / risk))
    # ---- MSNR: fresh A/V levels on the close line, first touch, entries on 5m ----
    for tf in ("1h", "4h"):
        hb = rs(b5, tf); H, L, C = hb.h.to_numpy(), hb.l.to_numpy(), hb.c.to_numpy(); A = atr(H, L, C); ct = hb.index + pd.Timedelta(tf)
        for k in range(15, len(hb) - 2):
            for kind, d in (("A", -1), ("V", 1)):
                if kind == "A" and not (C[k] > C[k - 1] and C[k] > C[k + 1]): continue
                if kind == "V" and not (C[k] < C[k - 1] and C[k] < C[k + 1]): continue
                lvl = C[k]; a = A[k]
                if not np.isfinite(a): continue
                for m in range(k + 2, min(k + 31, len(hb))):          # first HTF candle that touches the level after confirmation
                    if L[m] <= lvl <= H[m]:
                        i0, i1 = T5.searchsorted(hb.index[m]), T5.searchsorted(ct[m])
                        j = next((q for q in range(i0, i1) if L5[q] <= lvl <= H5[q]), None)
                        if j is None: break
                        stop = lvl - d * 0.5 * a; tp = lvl + d * 2 * 0.5 * a; end = min(T5.searchsorted(ct[m] + 3 * pd.Timedelta(tf)), len(C5))
                        x, _ = first_hit(O5, H5, L5, C5, j, end, d, lvl, stop, tp); rec("MSNR", tf, T5[j], d, lvl, stop, x); break
    # ---- CRT: candle k sweeps candle k-1 high/low and closes back inside its range ----
    for tf in ("1h", "4h", "1D"):
        hb = rs(b5, tf); O, H, L, C = (hb[c].to_numpy() for c in "ohlc")
        for k in range(1, len(hb) - 4):
            h1, l1 = H[k - 1], L[k - 1]
            if H[k] > h1 and l1 < C[k] < h1: d, stop, tp = -1, H[k] * 1.0001, l1
            elif L[k] < l1 and l1 < C[k] < h1: d, stop, tp = 1, L[k] * 0.9999, h1
            else: continue
            e = O[k + 1]
            if (tp - e) * d <= 0 or (e - stop) * d <= 0: continue
            x, _ = first_hit(O, H, L, C, k + 1, k + 4, d, e, stop, tp); rec("CRT", tf, hb.index[k + 1], d, e, stop, x)
    # ---- Linear regression channel (100 bars, +/-2 sd), fade the band in the slope direction ----
    for tf in ("15min", "1h"):
        hb = rs(b5, tf); O, H, L, C = (hb[c].to_numpy() for c in "ohlc"); n = 100; x_ = np.arange(n); xm = x_.mean(); sxx = ((x_ - xm) ** 2).sum()
        busy = -1
        for k in range(n, len(C) - 51):
            if k <= busy: continue
            y = C[k - n + 1:k + 1]; slope = ((x_ - xm) * (y - y.mean())).sum() / sxx; mid = y.mean() + slope * (n - 1 - xm)
            sd = (y - (y.mean() + slope * (x_ - xm))).std()
            if sd <= 0: continue
            if slope > 0 and C[k] <= mid - 2 * sd: d = 1
            elif slope < 0 and C[k] >= mid + 2 * sd: d = -1
            else: continue
            e = O[k + 1]; stop = mid - d * 3 * sd; tp = mid
            if (tp - e) * d <= 0 or (e - stop) * d <= 0: continue
            x, q = first_hit(O, H, L, C, k + 1, k + 51, d, e, stop, tp); rec("LRC", tf, hb.index[k + 1], d, e, stop, x); busy = q
    return out
if __name__ == "__main__":
    with Pool(4) as p: res = p.map(run, list(SRC))
    D = pd.DataFrame([r for o in res for r in o], columns=["sym", "cls", "method", "tf", "t", "R"]); D.to_pickle("methods_trades.pkl")
    S = pd.Timestamp("2023-01-01", tz="UTC")
    def summ(g):
        a, b = g[g.t < S].R, g[g.t >= S].R; tt = lambda v: round(v.mean() / v.std(ddof=1) * np.sqrt(len(v)), 2) if len(v) > 2 else np.nan
        return pd.Series(dict(trades=len(g), win=round(100 * (g.R > 0).mean()), avgR=round(g.R.mean(), 3), t_pre2023=tt(a), t_2023on=tt(b)))
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 300)
    print("POOLED (all 19 symbols):"); print(D.groupby(["method", "tf"]).apply(summ).to_string())
    print("\nBY CLASS:"); print(D.groupby(["method", "tf", "cls"]).apply(summ).to_string())
    best = D.groupby(["method", "tf", "sym"]).apply(summ); best = best[(best.t_pre2023 > 2) & (best.t_2023on > 2)]
    print("\nsymbol/method combos positive with t>2 in BOTH periods:"); print(best.to_string() if len(best) else "none")
