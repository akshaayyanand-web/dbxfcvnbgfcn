# Two TradingView order-flow indicators turned into trade rules (default inputs). Long logic; shorts = negated series (both scripts are symmetric).
# A) "Order Flow Profiler (Zeiierman)": rolling 80-bar profile, 84 rows, candle-shape buy share + 'focus' row weighting (exact port, numba).
#    Z1f bias follow : Directional Bias % crosses above its rolling 90th pct (500 bars) -> long      Z1r bias fade: crosses below 10th pct -> long
#    Z2 control retest: control row is BUY-dominant; bar dips to the control price and closes above it (previous close above) -> long
#    Z3 pressure support: nearest buy-pressure row below price (ratio 300%, activity >= 4% of peak): bar dips to it and closes above -> long
#    Z4f acceptance break: close crosses above the upper acceptance level (70%) -> long        Z4r: close crosses below the lower level -> long (fade)
# B) "Order Flow Dashboard": DOM = 6-bar buy% from close location; Tape = 5-bar aggressive buy share.
#    D1f BUYERS LEAD (DOM buy% > 60 and tape buy share > 65, fresh) -> long      D1r SELLERS LEAD -> long (fade)
#    D2f big-volume bar (volume > 3x its 20-bar average), green -> long           D2r big red bar -> long (fade)
# Stops: 0.1 ATR beyond the signal bar's extreme for bar-pattern rules, 1.5 ATR for the others. Exits: 2R target or 10-bar time exit. Train < 2023.
import sys
exec(open("joat.py").read().split("def S_joat")[0])
from numba import njit
EX = [("2R target", 0, 2.0), ("time exit 10 bars", 5, 0.0)]
@njit
def zprof(O, H, L, C, V, lb, rows, focus, vapct, pratio, pmin):
    N = len(C); ctrl = np.full(N, np.nan); vah = np.full(N, np.nan); val = np.full(N, np.nan); bias = np.full(N, np.nan); cside = np.zeros(N); pbelow = np.full(N, np.nan)
    br = np.zeros(rows); sr = np.zeros(rows)
    for k in range(lb - 1, N):
        lo = 1e300; hi = -1e300
        for j in range(k - lb + 1, k + 1):
            if V[j] > 0:
                lo = min(lo, L[j]); hi = max(hi, H[j])
        if hi <= lo: continue
        rh = (hi - lo) / rows
        for r in range(rows): br[r] = 0.0; sr[r] = 0.0
        for j in range(k - lb + 1, k + 1):
            v = V[j]
            if v <= 0: continue
            o, h, l, c = O[j], H[j], L[j], C[j]; rng = h - l; share = 0.5
            if rng > 0:
                cp = min(1.0, max(0.0, (c - l) / rng)); body = min(1.0, max(-1.0, (c - o) / rng))
                uw = max(h - max(o, c), 0.0) / rng; lw = max(min(o, c) - l, 0.0) / rng
                drive = 0.48 * (2 * cp - 1) + 0.32 * body + 0.20 * (lw - uw); share = min(0.975, max(0.025, 0.5 + 0.43 * drive))
            bv = v * share; sv = v - bv
            if rng <= 0:
                r = int(min(rows - 1, max(0, np.floor((c - lo) / rh)))); br[r] += bv; sr[r] += sv; continue
            f = int(min(rows - 1, max(0, np.floor((l - lo) / rh)))); t = int(min(rows - 1, max(0, np.floor((h - lo) / rh))))
            ba = min(h, max(l, 0.5 * c + 0.32 * h + 0.18 * o)); sa = min(h, max(l, 0.5 * c + 0.32 * l + 0.18 * o)); bw = 0.0; sw = 0.0
            for r in range(f, t + 1):
                rl = lo + r * rh; rhh = rl + rh; tch = max(0.0, min(h, rhh) - max(l, rl))
                if tch > 0:
                    mid = 0.5 * (rl + rhh); tc = tch / rng
                    bw += tc * (1 + 2.6 * (1 - min(abs(mid - ba) / rng, 1.0)) ** focus); sw += tc * (1 + 2.6 * (1 - min(abs(mid - sa) / rng, 1.0)) ** focus)
            if bw > 0 and sw > 0:
                for r in range(f, t + 1):
                    rl = lo + r * rh; rhh = rl + rh; tch = max(0.0, min(h, rhh) - max(l, rl))
                    if tch > 0:
                        mid = 0.5 * (rl + rhh); tc = tch / rng
                        br[r] += bv * tc * (1 + 2.6 * (1 - min(abs(mid - ba) / rng, 1.0)) ** focus) / bw
                        sr[r] += sv * tc * (1 + 2.6 * (1 - min(abs(mid - sa) / rng, 1.0)) ** focus) / sw
        bt = 0.0; st = 0.0; peak = -1.0; cr = 0
        for r in range(rows):
            bt += br[r]; st += sr[r]
            if br[r] + sr[r] > peak: peak = br[r] + sr[r]; cr = r
        tot = bt + st
        if tot <= 0: continue
        bias[k] = 100 * (bt - st) / tot; ctrl[k] = lo + (cr + 0.5) * rh; cside[k] = 1.0 if br[cr] > sr[cr] else (-1.0 if sr[cr] > br[cr] else 0.0)
        goal = tot * vapct; a = cr; b = cr; vv = br[cr] + sr[cr]
        while vv < goal and (a > 0 or b < rows - 1):
            up = br[b + 1] + sr[b + 1] if b < rows - 1 else -1.0; dn = br[a - 1] + sr[a - 1] if a > 0 else -1.0
            if up >= dn: b += 1; vv += max(up, 0.0)
            else: a -= 1; vv += max(dn, 0.0)
        vah[k] = lo + (b + 1) * rh; val[k] = lo + a * rh
        minv = peak * pmin; px = C[k]
        for d in range(1, rows):                                  # nearest BUY-pressure row below the close
            r = int(np.floor((px - lo) / rh)) - d
            if r < 1: break
            if r >= rows: continue
            if br[r] + sr[r] >= minv and sr[r - 1] > 0 and br[r] > sr[r - 1] * pratio: pbelow[k] = lo + (r + 0.5) * rh; break
    return ctrl, vah, val, bias, cside, pbelow
def S_ofp(X):
    O, H, L, C, V = X.O, X.H, X.L, X.C, X.V; N = X.N; A = X.atr(); out = {}; st_bar = L - 0.1 * A; st_atr = C - 1.5 * A
    names = ["Z1f bias follow", "Z1r bias fade", "Z2 control retest", "Z3 pressure support", "Z4f acceptance break", "Z4r acceptance fade", "D1f BUYERS LEAD", "D1r SELLERS LEAD fade", "D2f big green bar", "D2r big red bar fade"]
    if not X.hasvol: return {n: (np.zeros(N, bool), st_bar) for n in names}
    ctrl, vah, val, bias, cside, pb = zprof(O, H, L, C, V.astype(np.float64), 80, 84, 2.15, 0.70, 3.0, 0.04)
    bs = pd.Series(bias); q90 = bs.rolling(500, min_periods=200).quantile(.9).shift(1).to_numpy(); q10 = bs.rolling(500, min_periods=200).quantile(.1).shift(1).to_numpy()
    out[names[0]] = ((bias > q90) & ~(shift(bias) > shift(q90)), st_atr); out[names[1]] = ((bias < q10) & ~(shift(bias) < shift(q10)), st_atr)
    pc = shift(ctrl); out[names[2]] = ((shift(cside) > 0) & (L <= pc) & (C > pc) & (shift(C) > pc), st_bar)
    pp = shift(pb); out[names[3]] = (np.isfinite(pp) & (L <= pp) & (C > pp), st_bar)
    pv = shift(vah); pl_ = shift(val); out[names[4]] = ((C > pv) & (shift(C) <= shift(pv)), st_atr); out[names[5]] = ((C < pl_) & (shift(C) >= shift(pl_)), st_atr)
    rg = H - L; cr = np.where(rg > 0, (C - L) / np.where(rg > 0, rg, 1), 0.5); buy = V * cr; sell = V * (1 - cr)
    db = pd.Series(buy).rolling(6).sum().to_numpy(); ds = pd.Series(sell).rolling(6).sum().to_numpy(); dom = 100 * db / np.where(db + ds > 0, db + ds, np.nan)
    ab = pd.Series(V * np.maximum(cr - .5, 0) * 2).rolling(5).sum().to_numpy(); asl = pd.Series(V * np.maximum(.5 - cr, 0) * 2).rolling(5).sum().to_numpy()
    tape = 100 * ab / np.where(ab + asl > 0, ab + asl, np.nan)
    bl = (dom > 60) & (tape > 65); sl = (dom < 40) & (tape < 35)
    out[names[6]] = (bl & ~shift(bl).astype(bool), st_atr); out[names[7]] = (sl & ~shift(sl).astype(bool), st_atr)
    big = V > 3 * sma(V, 20); out[names[8]] = (big & (C > O), st_bar); out[names[9]] = (big & (C < O), st_atr)
    return out
src = open("joat.py").read(); fn = src[src.index("def run(job):"):src.index('\nif __name__ == "__main__":')]
fn = fn.replace("S_joat", "S_ofp").replace('(0.25 if tf == "M15" else 1.0)', '({"M5": 5 / 60, "M15": 0.25}.get(tf, 1.0))').replace('if nm.startswith("3"):', 'if False:')
exec(fn)
if __name__ == "__main__":
    mk = ("NQ", "SPX", "DAX", "XAU", "BTC", "ETH", "EURUSD")
    for s in mk:
        try: K._cache[(s, "M5")] = K.rs(K.MK[s][0](), "5min").pipe(lambda b: b[(b.h >= b.l) & (b.c > 0)])
        except Exception as ex: print(s, "no M5", ex)
    jobs = [(s, tf) for s in mk for tf in ("M5", "M15", "H1")]
    with Pool(3) as p: res = p.map(run, jobs, chunksize=1)
    D = pd.DataFrame([r for o in res for r in o]); D.to_csv("ofp.csv", index=False); D = D[D.n > 0]
    pd.set_option("display.width", 230); pd.set_option("display.max_rows", 300)
    g = D.groupby(["rule", "exit"]).agg(cells=("n", "size"), trades=("n", "sum"), win=("win", "median"), med_train=("avgR_train", "median"), med_hold=("avgR_hold", "median"))
    print("\nBY RULE (median over 7 markets x 3 timeframes):"); print(g.round(3).to_string())
    D["ok"] = (D.t_train >= 2) & (D.t_hold >= 1.5) & (D.n_train >= 50) & (D.n_hold >= 30)
    print(f"\ncells passing train t>=2 and holdout t>=1.5: {int(D.ok.sum())} of {len(D)} (luck ~{len(D)*0.023*0.067:.1f})"); print(D[D.ok].round(3).to_string(index=False) if D.ok.any() else "none")
    print("\nbest 8 cells by holdout t:"); print(D.sort_values("t_hold", ascending=False).head(8).round(3).to_string(index=False))
