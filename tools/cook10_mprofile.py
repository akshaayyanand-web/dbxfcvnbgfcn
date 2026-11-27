# Market Profile family (never tested before in this research). TPO profile from 1-minute bars of the regular session; bins = 5 bp of price.
# Value area = 70% of time-at-price around the point of control (POC). Rules fixed before running:
#  MP1 80% rule    : open outside yesterday's VA, price re-enters and two consecutive 30-min brackets close inside -> trade to the other VA edge;
#                    stop = session extreme beyond the re-entered edge; exit target / session end.
#  MP2 acceptance  : open above VAH (below VAL) and the first 30-min bracket closes beyond it -> follow; stop = first-30-min opposite extreme; target 2R.
#  MP4 naked POC   : nearest untouched POC of the last 5 sessions within 1 daily ATR of the open -> trade toward it at open+5m; target = POC, stop 1R.
#  MP5 VA fade     : open inside yesterday's VA; first touch of VAH (VAL) after 30 min -> fade; target yesterday's POC; stop = half the VAH-POC distance beyond.
#  MP6 POC shift   : developing POC at mid-session above yesterday's VAH (below VAL) -> follow to the close; stop = yesterday's VAH (VAL).
# Each: random direction at the same times with the same stop/target distances (40 runs), double costs, one-minute-late entry. Train < 2023, holdout 2023+.
import numpy as np, pandas as pd, sys
from multiprocessing import Pool
sys.argv = sys.argv[:1]
import cat1000 as K
MK = {"NQ": ("fut1m/USATECHIDXUSD_1m.csv", "America/New_York", 570, 960, .00015), "SPX": ("fut1m/USA500IDXUSD_1m.csv", "America/New_York", 570, 960, .00015),
      "DAX": ("eu1m/DEUIDXEUR_1m.csv", "Europe/Berlin", 540, 1050, .00015), "XAU": ("fut1m/XAUUSD_1m.csv", "Europe/London", 480, 1020, .00012)}
def profile(h, l, c0):
    bs = c0 * 0.0005; lo = np.floor(l.min() / bs); hi = np.floor(h.max() / bs); n = int(hi - lo) + 1
    cnt = np.zeros(n)
    for a, b in zip(np.floor(l / bs) - lo, np.floor(h / bs) - lo): cnt[int(a):int(b) + 1] += 1
    p = int(cnt.argmax()); i = j = p; tot = cnt.sum(); s = cnt[p]
    while s < 0.7 * tot:
        up = cnt[j + 1] if j + 1 < n else -1; dn = cnt[i - 1] if i - 1 >= 0 else -1
        if up >= dn: j += 1; s += up
        else: i -= 1; s += dn
    return (lo + p + .5) * bs, (lo + j + 1) * bs, (lo + i) * bs          # POC, VAH, VAL
def sessions(sym):
    f, tz, a, b, cost = MK[sym]; m = K.m1_csv(f); lt = m.index.tz_convert(tz); mins = lt.hour * 60 + lt.minute; keep = (mins >= a) & (mins < b)
    m = m[keep]; day = K.dayno(lt[keep]); mi = (mins[keep] - a).to_numpy(); out = []
    for d in np.unique(day):
        ix = np.where(day == d)[0]
        if len(ix) < 0.8 * (b - a): continue
        s = m.iloc[ix]; out.append((d, s.o.to_numpy(), s.h.to_numpy(), s.l.to_numpy(), s.c.to_numpy(), mi[ix], s.index))
    return out, cost
def walk(O, H, L, C, k, d, e, stop, tp):
    for q in range(k, len(C)):
        if (d > 0 and L[q] <= stop) or (d < 0 and H[q] >= stop): return (min(O[q], stop) if d > 0 else max(O[q], stop))
        if tp is not None and ((d > 0 and H[q] >= tp) or (d < 0 and L[q] <= tp)): return tp
    return C[-1]
def run(args):
    sym, rule = args; S, cost = sessions(sym); prof = [profile(s[2], s[3], s[4][0]) for s in S]
    natr = pd.Series([s[2].max() - s[3].min() for s in S]).rolling(14).mean().shift(1).to_numpy()
    def trades(rand=None, cm=1.0, late=0):
        out = []
        for i in range(6, len(S)):
            d, O, H, L, C, mi, T = S[i]; poc, vah, val = prof[i - 1]; o = O[0]; sig = None   # sig = (bar k, dir, stop, target)
            if rule == "MP1":
                if o > vah or o < val:
                    side = -1 if o > vah else 1; edge = vah if side < 0 else val; br = mi // 30; inside = 0
                    for bb in range(0, br.max() + 1):
                        ks = np.where(br == bb)[0]
                        if not len(ks): continue
                        cl = C[ks[-1]]; inside = inside + 1 if val < cl < vah else 0
                        if inside == 2:
                            k = ks[-1] + 1
                            if k >= len(C) - 5: break
                            ext = H[:k].max() if side < 0 else L[:k].min(); sig = (k, side, ext, val if side < 0 else vah); break
            elif rule == "MP2":
                if o > vah or o < val:
                    dr = 1 if o > vah else -1; ks = np.where(mi < 30)[0]
                    if len(ks) < 10: continue
                    k = ks[-1] + 1
                    if (dr > 0 and C[ks[-1]] > vah) or (dr < 0 and C[ks[-1]] < val):
                        st = L[ks].min() if dr > 0 else H[ks].max(); sig = (k, dr, st, None)
            elif rule == "MP4":
                if np.isfinite(natr[i]):
                    nk = []
                    for j in range(i - 5, i):
                        pc = prof[j][0]
                        if all(not (S[q][3].min() <= pc <= S[q][2].max()) for q in range(j + 1, i)): nk.append(pc)
                    k = 5; e0 = O[k] if len(O) > k else None
                    if nk and e0 is not None:
                        pc = min(nk, key=lambda x: abs(x - e0))
                        if 0 < abs(pc - e0) < natr[i]:
                            dr = 1 if pc > e0 else -1; sig = (k, dr, e0 - dr * abs(pc - e0), pc)
            elif rule == "MP5":
                if val < o < vah:
                    for k in np.where(mi >= 30)[0]:
                        if k >= len(C) - 5: break
                        if H[k] >= vah: sig = (k + 1, -1, vah + 0.5 * (vah - poc), poc); break
                        if L[k] <= val: sig = (k + 1, 1, val - 0.5 * (poc - val), poc); break
            elif rule == "MP6":
                ks = np.where(mi < (mi.max() + 1) // 2)[0]
                if len(ks) < 30: continue
                k = ks[-1] + 1
                dp = profile(H[ks], L[ks], O[0])[0]
                if dp > vah: sig = (k, 1, vah, None)
                elif dp < val: sig = (k, -1, val, None)
            if sig is None: continue
            k, dr, st, tp = sig; k = k + late
            if k >= len(C) - 1: continue
            e = O[k]; risk = dr * (e - st)
            if risk <= 3 * cost * e: continue
            if rand is not None:
                nd = 1 if rand.random() < .5 else -1
                if nd != dr: st = e + dr * risk; tp = None if tp is None else e - (tp - e); dr = nd
            if rule == "MP2" and tp is None: tp = e + dr * 2 * risk
            x = walk(O, H, L, C, k, dr, e, st, tp); out.append((T[k], (dr * (x - e) - cm * cost * e) / risk))
        return out
    D = pd.DataFrame(trades(), columns=["t", "R"])
    if len(D) < 30: return dict(market=sym, rule=rule, trades=len(D))
    SP = pd.Timestamp("2023-01-01", tz="UTC"); A, B = D[D.t < SP].R, D[D.t >= SP].R; tt = lambda v: round(v.mean() / v.std(ddof=1) * np.sqrt(len(v)), 2) if len(v) > 2 else np.nan
    rnd = [np.mean([x[1] for x in trades(rand=np.random.default_rng(s))]) for s in range(40)]; y = D.groupby(D.t.dt.year).R.sum()
    r = dict(market=sym, rule=rule, trades=len(D), per_yr=round(len(D) / max((D.t.max() - D.t.min()).days / 365, 1)), win=round(100 * (D.R > 0).mean()), avgR=round(D.R.mean(), 3),
             t_train=tt(A), avgR_hold=round(B.mean(), 3), t_hold=tt(B), random=round(np.mean(rnd), 3), beats_random=round(100 * np.mean(np.array(rnd) < D.R.mean())),
             dbl_cost=round(np.mean([x[1] for x in trades(cm=2.0)]), 3), late_1m=round(np.mean([x[1] for x in trades(late=1)]), 3), pos_years=f"{(y > 0).sum()}/{len(y)}")
    D.to_pickle(f"mp_{sym}_{rule}.pkl"); print(r, flush=True); return r
if __name__ == "__main__":
    import re
    done = [eval(l, {"np": np}) for l in open("mprofile.log") if l.startswith("{")] if len(sys.argv) else []
    have = {(d["market"], d["rule"]) for d in done}
    jobs = [(s, r) for s in MK for r in ("MP1", "MP2", "MP4", "MP5", "MP6") if (s, r) not in have]
    with Pool(3) as p: res = done + p.map(run, jobs, chunksize=1)
    R = pd.DataFrame(res); pd.set_option("display.width", 250); print(R.to_string(index=False)); R.to_csv("mprofile.csv", index=False)
    R["ok"] = (R.t_train >= 2) & (R.t_hold >= 1.5) & (R.beats_random >= 95) & (R.dbl_cost > 0); print("\nSURVIVORS:\n", R[R.ok].to_string(index=False) if R.ok.any() else "none")
    print(f"20 tests -> luck expectation ~{20*0.006*0.023:.2f} passes")
