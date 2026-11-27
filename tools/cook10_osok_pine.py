# TFlab "One Shot One Kill ICT" - port of the PINE CODE (not the description). Bearish logic below; bullish = same code on negated prices.
#  Liquidity: pivot highs (50/50, known 50 bars later). A swing high is SWEPT by the first bar with high > swing > close, provided no earlier
#             close went above it (a close above kills it). Previous-day high/low are only drawn by the script -> used here only as the target.
#  CISD (on a sweep bar): first bearish candle i (1..5 bars back); level = min(open[i-1], open[i-2]) (open[0] if i = 1); valid 25 bars from that candle.
#             Fib high = max(high, high[1], high[2]) of the sweep bar, fib low = its low, both extended within the 25-bar window.
#  Shift: a close <= CISD level inside the window -> fib drawn (values of that bar) -> sell limit at low + 0.618 x (high - low), valid 50 bars,
#         cancelled if price reaches the target first. Stop 0.1 ATR above the fib high. Target = previous trading day's low. Max hold 100 bars.
#  One pending order and one open trade at a time per side. Variants: target 2R | entry 0.5 | entry 0.786 | market entry at the CISD break.
import numpy as np, pandas as pd, bisect, sys
from multiprocessing import Pool
exec(open("transfer.py").read().split("JOBS = ")[0])
COST.update(NQ=.00015, SPX=.00015, DAX=.00015, XAU=.00012, BTC=.0009, ETH=.00227, EURUSD=.00008)
def daykey(idx, sym):
    if sym in ("BTC", "ETH"): return K.dayno(idx.tz_convert("UTC"))
    if sym == "DAX": return K.dayno(idx.tz_convert("Europe/Berlin"))
    return K.dayno((idx.tz_convert("America/New_York") + pd.Timedelta(hours=7)))
def setups(O, H, L, C, p=50, bb=5, val=25):
    N = len(C); hmax = pd.Series(H).rolling(2 * p + 1, center=True).max().to_numpy(); piv = np.where(H == hmax)[0]
    conf = {j + p: H[j] for j in piv if j + p < N}; lv = []; out = []
    active = False; cisd = np.nan; x1 = -10 ** 9; fh = fl = np.nan
    for k in range(3, N):
        if k in conf: bisect.insort(lv, conf[k])
        while lv and lv[0] < C[k]: lv.pop(0)                         # closed above -> no longer liquidity
        sw = False
        while lv and lv[0] < H[k]:
            if lv[0] > C[k]: sw = True
            lv.pop(0)
        if sw:
            fh = max(H[k], H[k - 1], H[k - 2]); fl = L[k]
            for i in range(1, bb + 1):
                if C[k - i] < O[k - i]:
                    if i > 1:
                        a_, b_ = O[k - i + 1], O[k - i + 2]; cisd = min(a_, b_); x1 = (k - i + 2) if b_ <= a_ else (k - i + 1)
                    else: cisd = O[k]; x1 = k
                    active = True; break
        broke = False
        if active and k - x1 <= val and C[k] <= cisd: active = False; broke = True
        if k - x1 <= val: fh = max(fh, H[k]); fl = min(fl, L[k])
        if broke: out.append((k, fh, fl))
    return out
def trade(O, H, L, C, A, day, pdl, S, cost, fib=0.618, target="pdl", entry="limit"):
    res = []; busy = -1
    for k, fh, fl in S:
        if k <= busy or k + 2 >= len(C): continue
        stop = fh + 0.1 * A[k]; q0 = None
        tp0 = pdl[k] if target == "pdl" else None
        if entry == "market": e = O[k + 1]; q0 = k + 1
        else:
            E = fl + fib * (fh - fl)
            for q in range(k + 1, min(k + 51, len(C))):
                if tp0 is not None and L[q] <= tp0: break
                if H[q] >= E: e = max(O[q], E); q0 = q; break
        if q0 is None: continue
        risk = stop - e; ce = cost * abs(e)
        if not np.isfinite(risk) or risk <= 3 * ce: continue
        tp = tp0 if target == "pdl" else e - 2 * risk
        if not np.isfinite(tp) or tp >= e: continue
        x = None
        for q in range(q0, min(q0 + 100, len(C))):
            if H[q] >= stop: x = stop if q == q0 else max(O[q], stop); break
            if q > q0 and L[q] <= tp: x = tp if O[q] > tp else O[q]; break
        if x is None: q = min(q0 + 99, len(C) - 1); x = C[q]
        res.append((q0, (e - x - ce) / risk, (e - x - 2 * ce) / risk)); busy = q
    return res
def run(job):
    sym, tf = job; b = m5(sym)
    if tf != "M5": b = K.rs(b, {"M15": "15min", "H1": "1h"}[tf]).dropna()
    b = b[(b.h >= b.l) & (b.c > 0)]; T = b.index; day = daykey(T, sym); O, H, L, C = (b[c].to_numpy() for c in "ohlc"); A = atr(b)
    g = pd.DataFrame({"d": day, "h": H, "l": L}).groupby("d").agg(h=("h", "max"), l=("l", "min")).shift(1)
    pdh = g.h.reindex(day).to_numpy(); pdl = g.l.reindex(day).to_numpy()
    Sb = setups(O, H, L, C); Sl = setups(-O, -L, -H, -C)
    VAR = {"OSOK code (0.618 limit, target prev-day low/high)": {}, "target 2R": dict(target="2r"), "entry 0.5": dict(fib=0.5), "entry 0.786": dict(fib=0.786),
           "market entry at CISD break": dict(entry="market")}
    S = pd.Timestamp("2023-01-01", tz="UTC"); tt = lambda v: round(v.mean() / v.std(ddof=1) * np.sqrt(len(v)), 2) if len(v) > 2 else np.nan; rows = []
    for nm, kw in VAR.items():
        tr = trade(O, H, L, C, A, day, pdl, Sb, COST[sym], **kw) + trade(-O, -L, -H, -C, A, day, -pdh, Sl, COST[sym], **kw)
        D = pd.DataFrame([(T[q], r, r2) for q, r, r2 in tr], columns=["t", "R", "R2"])
        if len(D) < 20: rows.append(dict(market=sym, tf=tf, variant=nm, trades=len(D))); continue
        a_, h_ = D[D.t < S].R, D[D.t >= S].R; y = D.groupby(D.t.dt.year).R.sum()
        rows.append(dict(market=sym, tf=tf, variant=nm, setups=len(Sb) + len(Sl), trades=len(D), per_yr=round(len(D) / max((D.t.max() - D.t.min()).days / 365, 1)), win=round(100 * (D.R > 0).mean()),
                         avgR=round(D.R.mean(), 3), t_train=tt(a_), avgR_hold=round(h_.mean(), 3), t_hold=tt(h_), dbl_cost=round(D.R2.mean(), 3), pos_years=f"{(y > 0).sum()}/{len(y)}"))
    print(sym, tf, "done", flush=True); return rows
if __name__ == "__main__":
    jobs = [(s, tf) for s in ("NQ", "SPX", "DAX", "XAU", "EURUSD", "BTC", "ETH") for tf in ("M5", "M15", "H1")]
    with Pool(4) as p: res = p.map(run, jobs, chunksize=1)
    R = pd.DataFrame([r for o in res for r in o]); R.to_csv("osok_code.csv", index=False); pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
    print(R[R.variant.str.startswith("OSOK")].drop(columns="variant").to_string(index=False))
    print("\nMEDIAN BY VARIANT (21 market/timeframe cells):"); print(R.groupby("variant")[["trades", "win", "avgR", "avgR_hold", "dbl_cost"]].median().round(3).to_string())
    R["ok"] = (R.t_train >= 2) & (R.t_hold >= 1.5); print(f"\nPASS train t>=2 & holdout t>=1.5 ({len(R)} tests, luck ~{len(R)*0.023*0.067:.1f}):"); print(R[R.ok].to_string(index=False) if R.ok.any() else "none")
