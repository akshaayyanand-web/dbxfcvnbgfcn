# "One Shot One Kill" (TFlab, SMC/ICT) as written. Long (short = mirror via negated prices):
#  1 liquidity hunt : price trades below the PREVIOUS DAY LOW (trading day: 17:00 New York rollover; crypto UTC day; DAX Frankfurt day)
#  2 CISD           : CISD level = open of the run of consecutive bearish candles leading into the lowest low (look back <= 10 bars);
#                     a close above it within 30 bars of that low = market-structure shift (a lower low first resets low + CISD)
#  3 entry          : Fibonacci from the sweep low to the highest high since; limit buy at the 0.618 retracement (updated each bar from the
#                     previous bar's high), valid 50 bars; stop 0.1 ATR below the sweep low (fib 1.0); target = previous day high. Flat at day end.
# Variants: target 2R instead of PDH | enter at the CISD-break close (no 0.618) | NO previous-day sweep (any new 2-hour low) | 0.5 and 0.705 entries.
# One trade per side per day. Costs per market. Train < 2023.
import numpy as np, pandas as pd, sys
from multiprocessing import Pool
exec(open("transfer.py").read().split("JOBS = ")[0])
COST.update(NQ=.00015, SPX=.00015, DAX=.00015, XAU=.00012, BTC=.0009, ETH=.00227, EURUSD=.00008)
def daykey(idx, sym):
    if sym in ("BTC", "ETH"): return K.dayno(idx.tz_convert("UTC"))
    if sym == "DAX": return K.dayno(idx.tz_convert("Europe/Berlin"))
    return K.dayno((idx.tz_convert("America/New_York") + pd.Timedelta(hours=7)))
def side(O, H, L, C, A, day, pdl, pdh, cost, fib=0.618, target="pdh", entry="fib", sweep="pdl"):
    out = []; N = len(C)
    starts = np.r_[0, np.where(np.diff(day) != 0)[0] + 1, N]
    for di in range(len(starts) - 1):
        a, b = starts[di], starts[di + 1]
        if not np.isfinite(pdl[a]): continue
        state = 0; low = np.inf; lowk = -1; cisd = np.nan; brk = -1; sh = -np.inf; q0 = -1
        for k in range(a, b):
            if state == 2:                                       # pending 0.618 limit order: checked BEFORE anything else on this bar
                if k - brk > 50: break
                E = sh - fib * (sh - low)
                if L[k] <= E: e = min(O[k], E); q0 = k; break
                sh = max(sh, H[k]); continue
            if state == 0:
                lvl = pdl[a] if sweep == "pdl" else (np.min(L[k - 24:k]) if k - a >= 24 else np.inf)
                if L[k] < lvl: state = 1
                else: continue
            if L[k] < low:                                       # new low -> reset CISD
                low = L[k]; lowk = k; j = k if C[k] < O[k] else k - 1; st = None
                while j >= max(a, k - 10) and C[j] < O[j]: st = j; j -= 1
                cisd = O[st] if st is not None else np.nan
                continue
            if np.isfinite(cisd) and k - lowk <= 30 and C[k] > cisd:
                if entry == "close":
                    if k + 1 < b: e = O[k + 1]; q0 = k + 1
                    break
                state = 2; brk = k; sh = H[lowk:k + 1].max()
        if q0 < 0: continue
        stop = low - 0.1 * A[lowk]; risk = e - stop; ce = cost * abs(e)
        if not np.isfinite(risk) or risk <= 3 * ce: continue
        tp = pdh[a] if target == "pdh" else e + 2 * risk
        if tp <= e: continue
        x = None
        for q in range(q0, b):
            if L[q] <= stop: x = stop if q == q0 else min(O[q], stop); break
            if q > q0 and H[q] >= tp: x = max(tp, O[q]) if O[q] < tp else O[q]; x = tp if O[q] < tp else O[q]; break
        if x is None: x = C[b - 1]
        out.append((q0, (x - e - ce) / risk, (x - e - 2 * ce) / risk))
    return out
def run(job):
    sym, tf = job; b = m5(sym)
    if tf != "M5": b = K.rs(b, tf.replace("M", "") + "min").dropna()
    b = b[(b.h >= b.l) & (b.c > 0)]; T = b.index; day = daykey(T, sym)
    O, H, L, C = (b[c].to_numpy() for c in "ohlc"); A = atr(b)
    g = pd.DataFrame({"d": day, "h": H, "l": L}).groupby("d").agg(h=("h", "max"), l=("l", "min")); prev = g.shift(1)
    pdh = prev.h.reindex(day).to_numpy(); pdl = prev.l.reindex(day).to_numpy(); rows = []
    VAR = {"OSOK as written (0.618, target PDH)": {}, "target 2R": dict(target="2r"), "fib 0.5": dict(fib=0.5), "fib 0.705": dict(fib=0.705),
           "enter at CISD break (no 0.618)": dict(entry="close"), "NO prev-day sweep (any 2h low)": dict(sweep="any")}
    S = pd.Timestamp("2023-01-01", tz="UTC"); tt = lambda v: round(v.mean() / v.std(ddof=1) * np.sqrt(len(v)), 2) if len(v) > 2 else np.nan
    for nm, kw in VAR.items():
        lo = side(O, H, L, C, A, day, pdl, pdh, COST[sym], **kw); sh = side(-O, -L, -H, -C, A, day, -pdh, -pdl, COST[sym], **kw)
        D = pd.DataFrame([(T[q], r, r2) for q, r, r2 in lo + sh], columns=["t", "R", "R2"])
        if len(D) < 20: rows.append(dict(market=sym, tf=tf, variant=nm, trades=len(D))); continue
        a_, h_ = D[D.t < S].R, D[D.t >= S].R; y = D.groupby(D.t.dt.year).R.sum()
        rows.append(dict(market=sym, tf=tf, variant=nm, trades=len(D), per_yr=round(len(D) / max((D.t.max() - D.t.min()).days / 365, 1)), win=round(100 * (D.R > 0).mean()),
                         avgR=round(D.R.mean(), 3), t_train=tt(a_), avgR_hold=round(h_.mean(), 3), t_hold=tt(h_), dbl_cost=round(D.R2.mean(), 3), pos_years=f"{(y > 0).sum()}/{len(y)}"))
        if nm.startswith("OSOK"): D.to_pickle(f"osok_{sym}_{tf}.pkl")
    print(sym, tf, "done", flush=True); return rows
if __name__ == "__main__":
    jobs = [(s, tf) for s in ("NQ", "SPX", "DAX", "XAU", "EURUSD", "BTC", "ETH") for tf in ("M5", "M15")]
    with Pool(3) as p: res = p.map(run, jobs, chunksize=1)
    R = pd.DataFrame([r for o in res for r in o]); R.to_csv("osok.csv", index=False); pd.set_option("display.width", 240); pd.set_option("display.max_rows", 200)
    print(R[R.variant.str.startswith("OSOK")].to_string(index=False))
    print("\nMEDIAN BY VARIANT (14 market/timeframe cells):"); print(R.groupby("variant")[["trades", "win", "avgR", "avgR_hold", "dbl_cost"]].median().round(3).to_string())
    R["ok"] = (R.t_train >= 2) & (R.t_hold >= 1.5); print("\nPASS train t>=2 & holdout t>=1.5:"); print(R[R.ok].to_string(index=False) if R.ok.any() else "none")
