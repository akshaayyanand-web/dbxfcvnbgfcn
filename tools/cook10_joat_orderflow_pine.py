# "Orderflow Synthesis Pro [JOAT]" (TradingView indicator) turned into trade rules with its default inputs. Long logic; shorts = negated series.
import sys, numpy as np, pandas as pd
from multiprocessing import Pool
sys.argv = sys.argv[:1]
import cat1000 as K
from cat1000 import X, shift, rmax, rmin, sma, nb_exit, nb_nonoverlap, MK
def S_joat(X):
    A = X.atr(); O, H, L, C, V = X.O, X.H, X.L, X.C, X.V; N = X.N; bull = C > O; avgv = sma(V, 20); out = {}
    rh, rl = rmax(H, 50), rmin(L, 50); eq = (rh + rl) / 2; disc = C < eq - (eq - rl) * 0.5
    obsig = (shift(C) < shift(O)) & bull & ((H - L) > 1.5 * A) & (V > 1.3 * avgv) if X.hasvol else np.zeros(N, bool)
    mit = np.zeros(N, bool); mstop = np.full(N, np.nan); brk = np.zeros(N, bool); bstop = np.full(N, np.nan)
    zones = []                                    # [top, bottom, born, used]
    for k in range(2, N):
        keep = []
        for z in zones:
            top, bot, born, used = z
            if C[k] < bot:                        # mitigated (indicator deletes it) -> bearish breaker on the first close below
                if C[k - 1] >= bot and not np.isnan(A[k]): brk[k] = True; bstop[k] = top
                continue
            if k - born > 100: continue
            if not used and k > born and L[k] <= top and L[k] >= bot and bull[k] and np.isfinite(A[k]): mit[k] = True; mstop[k] = bot - 0.1 * A[k]; z[3] = True
            keep.append(z)
        zones = keep[-8:]
        if obsig[k]: zones.append([H[k - 1], L[k - 1], k, False])
    out["1 OB retest (MIT)"] = (mit, mstop); out["2 OB retest, discount only"] = (mit & disc, mstop)
    out["3 Breaker (short side of a broken bull OB)"] = (brk, bstop)      # NOTE: this array is the SHORT entry in long-logic terms -> handled below
    for nm, mn in (("4 FVG retest (gap >= 0.3%)", 0.003), ("4b FVG retest (gap >= 0.1%)", 0.001)):
        sig = np.zeros(N, bool); st = np.full(N, np.nan); gaps = []
        for k in range(2, N):
            g2 = []
            for gp in gaps:
                top, bot, born = gp
                if L[k] <= bot or k - born > 30: continue
                if k > born and L[k] <= top: sig[k] = True; st[k] = bot - 0.1 * A[k] if np.isfinite(A[k]) else bot; continue
                g2.append(gp)
            gaps = g2[-15:]
            if L[k] > H[k - 2] and (L[k] - H[k - 2]) / abs(H[k - 2]) >= mn: gaps.append((L[k], H[k - 2], k))
        out[nm] = (sig, st)
    sh, _, shi, sl, _, sli = X.sw(5)
    pl = np.full(N, np.nan)
    piv = [(i, L[i]) for i in range(5, N - 5) if L[i] == L[i - 5:i + 6].min()]
    eqlow = np.full(N, np.nan); last = []
    pi = 0
    for k in range(N):
        while pi < len(piv) and piv[pi][0] + 5 <= k:
            i, v = piv[pi]; pi += 1
            if any(abs(v - w) / abs(v) * 100 <= 0.15 for _, w in last[-3:]): eqlow_level = v
            else: eqlow_level = np.nan
            last.append((i, v))
            if np.isfinite(eqlow_level): eqlow[k:] = eqlow_level
    sw = (L < eqlow) & (C > eqlow) & ~(shift(L) < shift(eqlow))
    out["5 Equal-low sweep"] = (sw, L - 0.1 * A); out["5b Equal-low sweep + volume"] = (sw & (V > avgv) if X.hasvol else np.zeros(N, bool), L - 0.1 * A)
    return out
EX = [("2R target", 0, 2.0), ("time exit 10 bars", 5, 0.0)]
def run(job):
    sym, tf = job; b = K.bars(sym, tf)
    if b is None or len(b) < 5000: return []
    Xp = X(b, sym, tf, False, {}); Xn = X(b, sym, tf, True, {})
    Sp, Sn = S_joat(Xp), S_joat(Xn)
    O, H, L, C = (b[c].to_numpy() for c in "ohlc"); A = Xp.atr(); shl, _, _, sll, _, _ = Xp.sw()
    cost = MK[sym][2]; swb = MK[sym][3] / 365 * (0.25 if tf == "M15" else 1.0) / 24; T = b.index; rows = []
    for nm in Sp:
        sp, stp = Sp[nm]; sn, stn = Sn[nm]
        if nm.startswith("3"): sp, stp, sn, stn = sn, stn, sp, stp       # breaker of a bull OB is a SHORT: the long-logic array of the negated series is the long breaker
        sp = np.nan_to_num(np.asarray(sp, float)).astype(bool); sn = np.nan_to_num(np.asarray(sn, float)).astype(bool); sp[-3:] = sn[-3:] = False
        kp, kn = np.where(sp)[0], np.where(sn)[0]; ks = np.r_[kp, kn]; ds = np.r_[np.ones(len(kp)), -np.ones(len(kn))]
        stops = np.r_[np.asarray(stp, float)[kp], -np.asarray(stn, float)[kn]]
        if nm.startswith("3"): stops = np.r_[-np.asarray(stp, float)[kp], np.asarray(stn, float)[kn]]
        o = np.argsort(ks, kind="stable"); ks, ds, stops = ks[o].astype(np.int64), ds[o], stops[o]
        for en, md, pr in EX:
            if not len(ks): rows.append(dict(rule=nm, sym=sym, tf=tf, exit=en, n=0)); continue
            R, XK = nb_exit(O, H, L, C, A, sll, shl, ks, ds, stops, cost, swb, md, pr, 50); kp_ = nb_nonoverlap(ks, XK, np.isfinite(R)); rr = R[kp_]; tt_ = T[ks][kp_]; tr = tt_ < K.SPLIT
            tt = lambda v: float(v.mean() / v.std(ddof=1) * np.sqrt(len(v))) if len(v) > 2 and v.std() > 0 else np.nan
            rows.append(dict(rule=nm, sym=sym, tf=tf, exit=en, n=len(rr), win=round(100 * (rr > 0).mean()) if len(rr) else np.nan, avgR_train=rr[tr].mean() if tr.sum() else np.nan,
                             t_train=tt(rr[tr]), avgR_hold=rr[~tr].mean() if (~tr).sum() else np.nan, t_hold=tt(rr[~tr]), n_train=int(tr.sum()), n_hold=int((~tr).sum())))
    print(sym, tf, "done", flush=True); return rows
if __name__ == "__main__":
    jobs = [(s, tf) for s in ("NQ", "SPX", "DAX", "XAU", "BTC", "ETH", "EURUSD") for tf in ("M15", "H1")]
    with Pool(4) as p: res = p.map(run, jobs, chunksize=1)
    D = pd.DataFrame([r for o in res for r in o]); D.to_csv("joat.csv", index=False); D = D[D.n > 0]
    pd.set_option("display.width", 230); pd.set_option("display.max_rows", 200)
    g = D.groupby(["rule", "exit"]).agg(cells=("n", "size"), trades=("n", "sum"), win=("win", "median"), med_train=("avgR_train", "median"), med_hold=("avgR_hold", "median"),
                                         pos_both=("avgR_hold", lambda s: int(((s > 0) & (D.loc[s.index, "avgR_train"] > 0)).sum())))
    print("\nBY RULE (median over 7 markets x 2 timeframes):"); print(g.round(3).to_string())
    D["ok"] = (D.t_train >= 2) & (D.t_hold >= 1.5) & (D.n_train >= 50) & (D.n_hold >= 30)
    print(f"\ncells passing train t>=2 and holdout t>=1.5: {int(D.ok.sum())} of {len(D)}"); print(D[D.ok].round(3).to_string(index=False) if D.ok.any() else "none")
    print("\nbest 8 cells by holdout t:"); print(D.sort_values("t_hold", ascending=False).head(8).round(3).to_string(index=False))
