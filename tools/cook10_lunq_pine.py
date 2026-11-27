# "Order Flow - Volume Delta, CVD, Absorption & Divergence [LunqFX]" (TradingView) as trade rules, default inputs. Long logic; shorts = negated series.
# Delta = volume x close location in the bar's range (buy = v(c-l)/(h-l)); CVD resets each day (UTC date; the script uses the exchange session).
#  L1 bull divergence  : pivot low (8/8, confirmed 8 bars later) below the previous pivot low while CVD at the pivot is higher -> long at confirmation;
#                        stop 0.1 ATR under the pivot low
#  L2 absorption buy   : volume > 1.8 x 20-bar avg, body < 0.35 ATR, delta >= 0 -> long next bar; stop 0.1 ATR under the bar
#  L3 absorption retest: price later (within 50 bars) dips to an absorption-buy level (bar midpoint) and closes above -> long; stop 0.1 ATR under the bar
#  L4 divergence retest: price later dips to a bull-divergence level (the pivot low) and closes above -> long; stop 0.1 ATR under the bar
#  L5f CVD crosses above 0 -> long (follow)     L5r CVD crosses below 0 -> long (fade)
# Exits: 2R target or 10-bar time exit (shared harness). Train < 2023.
import sys
exec(open("joat.py").read().split("def S_joat")[0])
EX = [("2R target", 0, 2.0), ("time exit 10 bars", 5, 0.0)]
def retest(level_bars, level_px, L, C, N, span=50):
    sig = np.zeros(N, bool); act = []                                      # active levels [px, born]
    lv = dict(zip(level_bars, level_px))
    for k in range(N):
        keep = []
        for px, born in act:
            if k - born > span: continue
            if k > born and L[k] <= px and C[k] > px: sig[k] = True; continue
            if C[k] < px: continue                                         # closed through -> level broken
            keep.append((px, born))
        act = keep[-10:]
        if k in lv: act.append((lv[k], k))
    return sig
def S_lunq(X):
    O, H, L, C, V = X.O, X.H, X.L, X.C, X.V; N = X.N; A = X.atr(); out = {}; st_bar = L - 0.1 * A; st_atr = C - 1.5 * A
    names = ["L1 bull divergence", "L2 absorption buy", "L3 absorption retest", "L4 divergence retest", "L5f CVD crosses above 0", "L5r CVD crosses below 0 (fade)"]
    if not X.hasvol: return {n: (np.zeros(N, bool), st_bar) for n in names}
    rg = np.maximum(H - L, 1e-12); delta = V * (C - L) / rg - V * (H - C) / rg
    day = pd.DatetimeIndex(X.T).tz_convert("UTC").normalize().asi8; newday = np.r_[True, day[1:] != day[:-1]]
    grp = np.cumsum(newday); cvd = pd.Series(delta).groupby(grp).cumsum().to_numpy()
    absb = (V > 1.8 * sma(V, 20)) & (np.abs(C - O) < 0.35 * A) & (delta >= 0)
    p = 8; lmin = pd.Series(L).rolling(2 * p + 1, center=True).min().to_numpy(); is_pl = (L == lmin)
    div = np.zeros(N, bool); dstop = np.full(N, np.nan); lastL = np.nan; lastD = np.nan; dbars = []; dpx = []
    for j in np.where(is_pl)[0]:
        k = j + p
        if k >= N: break
        if np.isfinite(lastL) and L[j] < lastL and cvd[j] > lastD and np.isfinite(A[k]): div[k] = True; dstop[k] = L[j] - 0.1 * A[k]; dbars.append(k); dpx.append(L[j])
        lastL, lastD = L[j], cvd[j]
    out[names[0]] = (div, dstop); out[names[1]] = (absb, st_bar)
    ab_k = np.where(absb)[0]; out[names[2]] = (retest(ab_k, (H[ab_k] + L[ab_k]) / 2, L, C, N), st_bar)
    out[names[3]] = (retest(np.array(dbars, int), np.array(dpx), L, C, N), st_bar)
    pc = shift(cvd); same = ~newday
    out[names[4]] = ((cvd > 0) & (pc <= 0) & same, st_atr); out[names[5]] = ((cvd < 0) & (pc >= 0) & same, st_atr)
    return out
src = open("joat.py").read(); fn = src[src.index("def run(job):"):src.index('\nif __name__ == "__main__":')]
fn = fn.replace("S_joat", "S_lunq").replace('(0.25 if tf == "M15" else 1.0)', '({"M5": 5 / 60, "M15": 0.25}.get(tf, 1.0))').replace('if nm.startswith("3"):', 'if False:')
exec(fn)
if __name__ == "__main__":
    mk = ("NQ", "SPX", "DAX", "XAU", "BTC", "ETH", "EURUSD")
    for s in mk:
        try: K._cache[(s, "M5")] = K.rs(K.MK[s][0](), "5min").pipe(lambda b: b[(b.h >= b.l) & (b.c > 0)])
        except Exception as ex: print(s, "no M5", ex)
    jobs = [(s, tf) for s in mk for tf in ("M5", "M15", "H1")]
    with Pool(3) as p: res = p.map(run, jobs, chunksize=1)
    D = pd.DataFrame([r for o in res for r in o]); D.to_csv("lunq.csv", index=False); D = D[D.n > 0]
    pd.set_option("display.width", 230); pd.set_option("display.max_rows", 300)
    g = D.groupby(["rule", "exit"]).agg(cells=("n", "size"), trades=("n", "sum"), win=("win", "median"), med_train=("avgR_train", "median"), med_hold=("avgR_hold", "median"))
    print("\nBY RULE (median over 7 markets x 3 timeframes):"); print(g.round(3).to_string())
    D["ok"] = (D.t_train >= 2) & (D.t_hold >= 1.5) & (D.n_train >= 50) & (D.n_hold >= 30)
    print(f"\ncells passing train t>=2 and holdout t>=1.5: {int(D.ok.sum())} of {len(D)} (luck ~{len(D)*0.023*0.067:.1f})"); print(D[D.ok].round(3).to_string(index=False) if D.ok.any() else "none")
    print("\nbest 8 cells by holdout t:"); print(D.sort_values("t_hold", ascending=False).head(8).round(3).to_string(index=False))
