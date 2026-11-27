# "Move the moment" / "go extreme" (The Claude Trading Lab, ch. 2) on proven pack edges. Rules fixed before running.
#  GMOM-x : gold, reference = previous day's 17:00 London close; at session open x, |move| > 0.6% -> trade that way; stop 1 ATR(24, H1); exit 7h later.
#           x = 09:00 London (pack EA, sanity check), 09:30 New York, 09:00 Tokyo.
#  ORB-x  : NQ 15-min opening range at the London 08:00 and Asia 18:00 (NY) opens; first M5 close outside within 2h; stop other side; 2R; exit open+6h25.
#  FADE-x : NQ first-15-min move at the London / Asia opens > 1.5x its 60-session median -> fade; stop = the move; exit 30 min.
#  ORB-NY narrow / wide: the pack's NQ 09:30 ORB only when the range is below the 20th / above the 80th percentile of the last 60 sessions.
# Every result vs 40 random-entry runs (same times, same exits, random direction) and at double costs.
import sys, numpy as np, pandas as pd
from multiprocessing import Pool
exec(open("transfer.py").read().split("JOBS = ")[0])
COST.update(NQ=.00015, XAU=.00012)
HOME.update({"TKY": ("Asia/Tokyo", 9, 0), "NYG": ("America/New_York", 9, 30), "ASIA": ("America/New_York", 18, 0)})
def gmom(home, costm=1.0, rand=None):
    b = K.rs(m5("XAU"), "1h"); lt = b.index.tz_convert("Europe/London"); O, H, L, C = (b[c].to_numpy() for c in "ohlc"); T = b.index; A = pd.Series(np.maximum(H - L, np.maximum(abs(H - np.r_[C[0], C[:-1]]), abs(L - np.r_[C[0], C[:-1]])))).ewm(alpha=1 / 24, adjust=False).mean().to_numpy()
    ref = pd.Series(np.where(lt.hour == 16, C, np.nan), T).ffill().shift(1).to_numpy()            # close of the 16:00-17:00 London bar
    tz, hh, mm = HOME[home]; loc = b.index.tz_convert(tz); sig = (loc.hour == hh) & (loc.minute == 0 if mm == 0 else loc.hour == hh)
    out = []; busy = -1
    for k in np.where(sig)[0]:
        if k <= busy or k + 8 >= len(C) or not np.isfinite(ref[k]) or not np.isfinite(A[k]): continue
        mv = O[k] / ref[k] - 1
        if rand is None:
            if abs(mv) < 0.006: continue
            d = 1 if mv > 0 else -1
        else:
            if rand.random() > P_GMOM.get(home, 0.2): continue
            d = 1 if rand.random() < 0.5 else -1
        e = O[k]; stop = e - d * A[k - 1]; x, q = walk(O, H, L, C, k, k + 7, d, e, stop, None)
        out.append((T[k], (d * (x - e) - costm * COST["XAU"] * e) / A[k - 1])); busy = q
    return out
P_GMOM = {}
def orb_at(home, n=15, costm=1.0, rand=None, width=None):
    b = m5("NQ"); mins, day = session(b, home); O, H, L, C = (b[c].to_numpy() for c in "ohlc"); T = b.index; out = []; widths = []
    for d_ in np.unique(day):
        ix = np.where(day == d_)[0]; m = mins[ix]; rng = ix[(m >= 0) & (m < n)]
        if len(rng) < 2: continue
        hi, lo = H[rng].max(), L[rng].min(); w_ = hi - lo; hist = widths[-60:]; widths.append(w_)
        if width is not None:
            if len(hist) < 40: continue
            q20, q80 = np.quantile(hist, .2), np.quantile(hist, .8)
            if (width == "narrow" and w_ > q20) or (width == "wide" and w_ < q80): continue
        win = ix[(m >= n) & (m < n + 120)]; ek = ix[m < 385]
        if not len(ek) or not len(win): continue
        endk = ek[-1]; cand = None
        if rand is None:
            for k in win:
                dr = 1 if C[k] > hi else (-1 if C[k] < lo else 0)
                if dr: cand = (k, dr); break
        elif rand.random() < 0.9: cand = (rand.choice(win), 1 if rand.random() < .5 else -1)
        if cand is None: continue
        k, dr = cand
        if k + 1 > endk: continue
        e = O[k + 1]; stop = lo if dr > 0 else hi; risk = dr * (e - stop)
        if risk <= 3 * COST["NQ"] * e: continue
        x, _ = walk(O, H, L, C, k + 1, endk + 1, dr, e, stop, e + dr * 2 * risk); out.append((T[k], (dr * (x - e) - costm * COST["NQ"] * e) / risk))
    return out
def fade_at(home, costm=1.0, rand=None):
    old = COST["NQ"]; COST["NQ"] = old * costm
    try:
        if rand is None: return FADE("NQ", home)
        tr = FADE("NQ", home); r2 = [(t, R * (1 if rand.random() < 0.5 else -1) - (0 if R is None else 0)) for t, R in tr]
        return r2
    finally: COST["NQ"] = old
JOBS = [("Gold momentum 09:00 London (pack EA)", lambda **k: gmom("LDN", **k)), ("Gold momentum 09:30 New York", lambda **k: gmom("NYG", **k)),
        ("Gold momentum 09:00 Tokyo", lambda **k: gmom("TKY", **k)), ("NQ ORB London 08:00", lambda **k: orb_at("LDN", **k)), ("NQ ORB Asia 18:00 NY", lambda **k: orb_at("ASIA", **k)),
        ("NQ ORB 09:30 NY, narrow days", lambda **k: orb_at("NY", width="narrow", **k)), ("NQ ORB 09:30 NY, wide days", lambda **k: orb_at("NY", width="wide", **k)),
        ("NQ ORB 09:30 NY, all days (pack)", lambda **k: orb_at("NY", **k)), ("NQ fade London open", lambda **k: fade_at("LDN", **k)), ("NQ fade Asia open", lambda **k: fade_at("ASIA", **k))]
def run(i):
    name, f = JOBS[i]; tr = f(); D = pd.DataFrame(tr, columns=["t", "R"])
    if len(D) < 30: return dict(test=name, trades=len(D))
    S = pd.Timestamp("2023-01-01", tz="UTC"); A_, B_ = D[D.t < S].R, D[D.t >= S].R; tt = lambda v: round(v.mean() / v.std(ddof=1) * np.sqrt(len(v)), 2) if len(v) > 2 else np.nan
    if name.startswith("Gold"):
        home = {"Gold momentum 09:00 London (pack EA)": "LDN", "Gold momentum 09:30 New York": "NYG", "Gold momentum 09:00 Tokyo": "TKY"}[name]; P_GMOM[home] = len(D) / max(len(gmom(home, rand=np.random.default_rng(0))) / 0.2, 1) * 0.2
    rnd = [np.mean([x[1] for x in f(rand=np.random.default_rng(s))] or [np.nan]) for s in range(40)]
    dbl = np.mean([x[1] for x in f(costm=2.0)])
    yrs = D.groupby(D.t.dt.year).R.sum()
    r = dict(test=name, trades=len(D), per_yr=round(len(D) / max((D.t.max() - D.t.min()).days / 365, 1)), avgR=round(D.R.mean(), 3), t_train=tt(A_), avgR_hold=round(B_.mean(), 3), t_hold=tt(B_),
             random_mean=round(np.nanmean(rnd), 3), beats_random=f"{100*np.mean(np.array(rnd) < D.R.mean()):.0f}%", double_costs=round(dbl, 3), pos_years=f"{(yrs > 0).sum()}/{len(yrs)}")
    print(r, flush=True); return r
if __name__ == "__main__":
    with Pool(4) as p: res = p.map(run, range(len(JOBS)), chunksize=1)
    R = pd.DataFrame(res); pd.set_option("display.width", 250); print(R.to_string(index=False)); R.to_csv("moments.csv", index=False)
