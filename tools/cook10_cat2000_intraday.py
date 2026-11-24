# Second user list ("1000 strategies", names only). Intraday part: mechanical long-side rules (shorts = same rule on the negated series),
# same markets / data / cost model / train-holdout split as cat1000.py. Three pre-registered exits per setup: fixed 1.5R, 2ATR stop with
# 3ATR trail, and a 10-bar time exit (stop at the setup's invalidation). Keys are the user's list numbers.
import os, sys, numpy as np, pandas as pd, warnings
from numba import njit
from multiprocessing import Pool
sys.argv = sys.argv[:1] + [a for a in sys.argv[1:] if ":" in a]
import cat1000 as K
from cat1000 import X, shift, rmax, rmin, sma, ema, rstd, pct_rank, xup, nb_exit, nb_nonoverlap, MK, dayno, rs
warnings.filterwarnings("ignore")
SPLIT = K.SPLIT
# ---------------------------------------------------------------- data with taker-buy volume for crypto
def crypto_tb(sym):
    import glob
    p = []
    for f in sorted(glob.glob(f"k5full/{sym}USDT-5m-*.csv")):
        x = pd.read_csv(f, header=None, usecols=[0, 1, 2, 3, 4, 5, 9], names=["t", "o", "h", "l", "c", "v", "tb"]); x["t"] = np.where(x.t > 1e14, x.t // 1000, x.t); p.append(x)
    x = pd.concat(p); x.index = pd.to_datetime(x.t, unit="ms", utc=True); return x[["o", "h", "l", "c", "v", "tb"]].astype(float).sort_index().loc[lambda z: ~z.index.duplicated()]
_c = {}
def bars2(sym, tf):
    if (sym, tf) in _c: return _c[(sym, tf)]
    if sym in ("BTC", "ETH"):
        raw = crypto_tb(sym); b = raw.resample("15min" if tf == "M15" else "1h").agg({"o": "first", "h": "max", "l": "min", "c": "last", "v": "sum", "tb": "sum"}).dropna(subset=["c"])
    else:
        b = K.bars(sym, tf)
        if b is None: return None
        b = b.copy(); b["tb"] = np.nan
    b = b[(b.h >= b.l) & (b.c > 0)]; _c[(sym, tf)] = b; return b
# ---------------------------------------------------------------- volume profile (prior day, prior 5 days) and developing POC
@njit(cache=True)
def nb_profile(day, tp, w, H, L, nb, ndays_win):
    """per bar: POC / VAH / VAL of the previous `ndays_win` completed days, plus LVN bins (bit mask) and bin geometry."""
    N = len(tp); poc = np.full(N, np.nan); vah = np.full(N, np.nan); val = np.full(N, np.nan); lo_o = np.full(N, np.nan); bw_o = np.full(N, np.nan)
    lvn = np.zeros((N, nb), np.bool_)
    starts = [0]
    for k in range(1, N):
        if day[k] != day[k - 1]: starts.append(k)
    starts.append(N)
    nd = len(starts) - 1
    for d in range(ndays_win, nd):
        a = starts[d - ndays_win]; b = starts[d]
        lo = 1e300; hi = -1e300
        for k in range(a, b):
            lo = min(lo, L[k]); hi = max(hi, H[k])
        if not (hi > lo): continue
        bwid = (hi - lo) / nb; hist = np.zeros(nb)
        for k in range(a, b):
            i = int((tp[k] - lo) / bwid)
            if i >= nb: i = nb - 1
            if i < 0: i = 0
            hist[i] += w[k]
        tot = hist.sum()
        if tot <= 0: continue
        ip = int(np.argmax(hist)); lo_i = ip; hi_i = ip; acc = hist[ip]
        while acc < 0.7 * tot:
            up = hist[hi_i + 1] if hi_i + 1 < nb else -1.0; dn = hist[lo_i - 1] if lo_i - 1 >= 0 else -1.0
            if up < 0 and dn < 0: break
            if up >= dn: hi_i += 1; acc += up
            else: lo_i -= 1; acc += dn
        p = lo + (ip + 0.5) * bwid; vh = lo + (hi_i + 1) * bwid; vl = lo + lo_i * bwid
        for k in range(starts[d], starts[d + 1]):
            poc[k] = p; vah[k] = vh; val[k] = vl; lo_o[k] = lo; bw_o[k] = bwid
            for i in range(nb): lvn[k, i] = hist[i] < 0.2 * hist[ip]
    return poc, vah, val, lo_o, bw_o, lvn
@njit(cache=True)
def nb_devpoc(day, tp, w, O, A, nb):
    N = len(tp); out = np.full(N, np.nan); hist = np.zeros(nb); lo = 0.0; bwid = 1.0
    for k in range(N):
        if k == 0 or day[k] != day[k - 1]:
            hist[:] = 0.0; a = A[k] if np.isfinite(A[k]) and A[k] > 0 else abs(O[k]) * 0.002
            lo = O[k] - 10 * a; bwid = 20 * a / nb
        i = int((tp[k] - lo) / bwid)
        if 0 <= i < nb: hist[i] += w[k]
        if hist.sum() > 0: out[k] = lo + (np.argmax(hist) + 0.5) * bwid
    return out
@njit(cache=True)
def nb_lvn_cross(C, lvn, lo, bw):
    N = len(C); nb = lvn.shape[1]; sig = np.zeros(N, np.bool_)
    for k in range(1, N):
        if not (np.isfinite(lo[k]) and bw[k] > 0) or C[k] <= C[k - 1]: continue
        for i in range(nb):
            if lvn[k, i]:
                ctr = lo[k] + (i + 0.5) * bw[k]
                if C[k - 1] < ctr <= C[k]: sig[k] = True; break
    return sig
@njit(cache=True)
def nb_cusum(r, h):
    N = len(r); up = np.zeros(N, np.bool_); dn = np.zeros(N, np.bool_); sp = 0.0; sn = 0.0
    for k in range(N):
        if not (np.isfinite(r[k]) and np.isfinite(h[k])): continue
        sp = max(0.0, sp + r[k]); sn = min(0.0, sn + r[k])
        if sp > h[k]: up[k] = True; sp = 0.0; sn = 0.0
        elif sn < -h[k]: dn[k] = True; sp = 0.0; sn = 0.0
    return up, dn
@njit(cache=True)
def nb_perm_entropy(C, n):
    N = len(C); out = np.full(N, np.nan)
    for k in range(n + 2, N):
        cnt = np.zeros(6)
        for j in range(k - n, k - 1):
            a, b, c = C[j - 1], C[j], C[j + 1]
            if a < b < c: cnt[0] += 1
            elif a < c <= b: cnt[1] += 1
            elif c <= a < b: cnt[2] += 1
            elif b <= a < c: cnt[3] += 1
            elif b < c <= a: cnt[4] += 1
            else: cnt[5] += 1
        p = cnt / cnt.sum(); e = 0.0
        for q in p:
            if q > 0: e -= q * np.log(q)
        out[k] = e / np.log(6.0)
    return out
@njit(cache=True)
def nb_sevcik(C, n):
    N = len(C); out = np.full(N, np.nan)
    for k in range(n, N):
        mx = C[k - n + 1]; mn = mx
        for j in range(k - n + 1, k + 1): mx = max(mx, C[j]); mn = min(mn, C[j])
        if mx <= mn: continue
        Lsum = 0.0
        for j in range(k - n + 2, k + 1):
            dy = (C[j] - C[j - 1]) / (mx - mn); dx = 1.0 / (n - 1); Lsum += np.sqrt(dy * dy + dx * dx)
        out[k] = 1 + np.log(Lsum) / np.log(2.0 * (n - 1))
    return out
def first(cond, grp): return cond & ~(pd.Series(cond).groupby(grp).cumsum().to_numpy() > 1)
def edge(cond): c = np.nan_to_num(np.asarray(cond, float)).astype(bool); return c & ~shift(c.astype(float), 1).astype(bool)
def consec(cond, n): return pd.Series(np.asarray(cond, float)).rolling(n).sum().to_numpy() >= n
def within(cond, n): return pd.Series(np.asarray(cond, float)).rolling(n).max().to_numpy() > 0
SESS_LEN = {("America/New_York", 9, 30): 390, ("Europe/Berlin", 9, 0): 510, ("Europe/London", 8, 0): 510, ("America/New_York", 9, 0): 270}
def S2(X, b):
    A = X.atr(); O, H, L, C, V = X.O, X.H, X.L, X.C, X.V; N = X.N; rng = H - L; body = np.abs(C - O); bull = C > O; bear = C < O
    upw = H - np.fmax(O, C); loww = np.fmin(O, C) - L; cl = np.where(rng > 0, (C - L) / rng, 0.5); atrstop = C - 1.5 * A
    shl, shp, shi, sll, slp, sli = X.sw(); pdh, pdl, pdc, dop, datr, dn = X.day(); e20, e50, e200 = X.ema(20), X.ema(50), X.ema(200)
    tz, hh, mm = X.home(); sid, mins = X.sess(tz, hh, mm); slen = SESS_LEN.get((tz, hh, mm), 390); vw = X.vwap(tz, hh, mm)
    tp = (H + L + C) / 3; w = V if X.hasvol else np.ones(N); dday = dayno(X.T)
    poc, vah, val, plo, pbw, lvn = X.get("prof1", lambda: nb_profile(dday, tp, w, H, L, 24, 1))
    cpoc, cvah, cval, _, _, _ = X.get("prof5", lambda: nb_profile(dday, tp, w, H, L, 30, 5))
    p2 = X.get("prof2", lambda: nb_profile(dday, tp, w, H, L, 24, 2)); p2vah, p2val = p2[1], p2[2]
    dpoc = X.get("dpoc", lambda: nb_devpoc(dday, tp, w, O, A, 60))
    dlow = pd.Series(L).groupby(dday).cummin().to_numpy(); dhigh = pd.Series(H).groupby(dday).cummax().to_numpy()
    sop = pd.Series(O).groupby(sid).transform("first").to_numpy(); scl = pd.Series(C).groupby(sid).last(); prevc = scl.shift(1).reindex(sid).to_numpy()
    tfm = 15 if X.tf == "M15" else 60; r14 = X.rsi(14); m_, ub, lbb = X.bb(); km, ku, kl = X.kc(); bw_ = (ub - lbb) / np.abs(m_); bwp = pct_rank(bw_, 200)
    ap = pct_rank(A, 200); hx = X.htf(); r1 = np.diff(C, prepend=np.nan); sd1 = rstd(r1, 200); vavg = sma(V, 20); vsd = rstd(V, 100)
    engulf = bull & (shift(C) < shift(O)) & (O <= shift(C)) & (C >= shift(O)); pin = (loww >= 0.6 * rng) & (rng > 0)
    o = {}
    # ---- market structure / auction 1-100
    o[1] = (first((C > vah) & (shift(C) <= shift(vah)) & (vw > poc), dday), poc)
    o[2] = (first(xup(dpoc, poc) & (C > dpoc), dday), atrstop)
    o[3] = (first((dop > val) & (dop < vah) & (L < val) & (C > val), dday), L - 0.1 * A)
    o[4] = (first((dop < val) & (C > val) & (shift(C) > shift(val)), dday), dlow)
    o[5] = ((shift(C) > shift(poc)) & (L <= poc + 0.1 * A) & (C > poc) & bull, poc - 0.5 * A)
    o[6] = (X.get("lvnx", lambda: nb_lvn_cross(C, lvn, plo, pbw)), C - A)
    ibn = 60; inib = mins < ibn; dS = pd.DataFrame({"s": sid, "h": H, "l": L})
    ibh = dS.h.where(inib).groupby(dS.s).transform("max").to_numpy(); ibl = dS.l.where(inib).groupby(dS.s).transform("min").to_numpy()
    o[9] = (first((mins >= ibn) & (mins < slen) & (C > ibh), sid), (ibh + ibl) / 2)
    o[10] = (first((mins >= ibn) & (mins < slen) & (L < ibl) & (C > ibl), sid), L - 0.1 * A)
    o[11] = ((C > dpoc) & (dpoc > shift(dpoc, 4)) & (L <= dpoc + 0.1 * A) & bull, dpoc - 0.5 * A)
    ovl = (np.fmin(vah, p2vah) > np.fmax(val, p2val))
    o[13] = (first(ovl & (dop > val) & (dop < vah) & (L <= val) & (C > val), dday), L - 0.2 * A)
    o[14] = (first((dop > vah) & (mins >= ibn) & (C > vah), sid), vah)
    pdf = pd.DataFrame({"d": dday, "h": H, "l": L, "rg": rng, "ww": loww})
    def flat_extreme(top):
        g = pdf.groupby("d"); res = []
        for d_, x in g:
            ext = x.h.max() if top else x.l.min(); near = ((x.h if top else x.l) - ext).abs() <= 0.05 * max(x.rg.mean(), 1e-12) * 4
            res.append((d_, near.sum() >= 2))
        s = pd.Series(dict(res)).shift(1); return s.reindex(dday).fillna(False).to_numpy().astype(bool)
    poor_hi = X.get("poorhi", lambda: flat_extreme(True))
    o[15] = (first(poor_hi & xup(C, poc), dday), atrstop)
    def excess_low():
        g = pdf.groupby("d"); res = []
        for d_, x in g:
            i = x.l.idxmin(); res.append((d_, x.ww.loc[i] >= 0.6 * max(x.rg.loc[i], 1e-12)))
        return pd.Series(dict(res)).shift(1).reindex(dday).fillna(False).to_numpy().astype(bool)
    exl = X.get("exl", excess_low)
    o[18] = (first(exl & (L <= pdl + 0.2 * A) & (C > pdl) & bull, dday), pdl - 0.3 * A)
    o[20] = (first(xup(C, cvah), dday), cpoc)
    pwh, pwl = X.week(); wk = (dday + 3) // 7
    o[26] = (first((L < pwl) & (C > pwl), wk), L - 0.1 * A)
    mo = X.T.year.to_numpy() * 12 + X.T.month.to_numpy(); gm = pd.DataFrame({"m": mo, "h": H, "l": L}).groupby("m").agg(h=("h", "max"), l=("l", "min")).shift(1)
    pmh, pml = gm.h.reindex(mo).to_numpy(), gm.l.reindex(mo).to_numpy()
    o[28] = (first((L < pml) & (C > pml), mo), L - 0.1 * A)
    o[29] = (first(C > pmh, mo), atrstop)
    o[39] = ((shl < shp) & (sll < slp) & xup(C, shl), sll)
    s1h, s1p, _, s1l, s1lp, _ = X.sw(1); s3h, s3p, _, s3l, s3lp, _ = X.sw(3)
    o[43] = ((s3h > s3p) & (s3l > s3lp) & xup(C, s1h), s1l)
    o[44] = (xup(C, s3h), s3l)
    bdn = (C < sll) & (shift(C) >= shift(sll)); blv = pd.Series(np.where(bdn, sll, np.nan)).ffill(limit=10).to_numpy()
    o[46] = (~bdn & np.isfinite(blv) & (H >= blv) & (C > blv) & (shift(C) < shift(blv)), rmin(L, 5))
    shi_prev = X.get("shiprev", lambda: K.prev_swing_val(shi, np.arange(N, dtype=float)))
    slope = (shl - shp) / np.maximum(shi - shi_prev, 1); line = shl + slope * (np.arange(N) - shi)
    o[47] = ((shl < shp) & (C > line) & (shift(C) > shift(line)) & ~(shift(C, 2) > shift(line, 2)), sll)
    sli_prev = X.get("sliprev", lambda: K.prev_swing_val(sli, np.arange(N, dtype=float)))
    sline = sll + (sll - slp) / np.maximum(sli - sli_prev, 1) * (np.arange(N) - sli)
    o[48] = ((sll > slp) & (shift(C) < shift(sline)) & (C > sline), rmin(L, 3))
    o[51] = ((shl > shp) & (sll < slp) & xup(C, shl), sll)
    o[54] = ((np.abs(shl - shp) <= 0.3 * A) & (sll > slp) & xup(C, np.fmax(shl, shp)), sll)
    o[56] = ((shl > shp) & (sll < slp) & (L <= sll + 0.2 * A) & bull, L - 0.2 * A)
    sq = within(bwp <= 0.2, 5); o[60] = (sq & within(C < lbb, 3) & (C > m_) & ~(shift(C) > shift(m_)), rmin(L, 3))
    inr = mins < 30; orh = dS.h.where(inr).groupby(dS.s).transform("max").to_numpy(); orl = dS.l.where(inr).groupby(dS.s).transform("min").to_numpy()
    o[72] = (first((mins >= 30) & (mins < 240) & within(C < orl, 2) & (C > orl), sid), dlow)
    onm = (mins >= 750); g_on = pd.DataFrame({"s": sid, "h": np.where(onm, H, np.nan), "l": np.where(onm, L, np.nan)}).groupby("s").agg(h=("h", "max"), l=("l", "min")).shift(1)
    onh, onl = g_on.h.reindex(sid).to_numpy(), g_on.l.reindex(sid).to_numpy(); early = mins < 180
    o[73] = (first(early & (C > onh), sid), (onh + onl) / 2)
    o[74] = (first(early & (L < onl) & (C > onl), sid), L - 0.1 * A)
    smid = (pd.Series(H).groupby(sid).cummax().to_numpy() + pd.Series(L).groupby(sid).cummin().to_numpy()) / 2
    o[80] = ((mins >= 0.66 * slen) & (mins < slen) & (C < smid - A) & bull, C - A)
    imp_dn = bear & (rng > 2 * A); last_imp_o = pd.Series(np.where(imp_dn, O, np.nan)).ffill(limit=3).to_numpy()
    o[82] = (~imp_dn & np.isfinite(last_imp_o) & (C > last_imp_o) & ~(shift(C) > shift(last_imp_o)), rmin(L, 4))
    o[84] = ((e50 > e200) & (shl < shp) & xup(C, shl), sll)
    o[86] = (((C - rmax(H, 20)) < -3 * A) & (r14 < 25) & bull, L)
    acc = consec(C > pdh, 4); o[91] = (first(acc, dday), pdh - 0.5 * A)
    # ---- candlesticks 101-200
    o[102] = ((e20 > e50) & (rmin(L, 3) <= e20) & engulf, L)
    o[103] = (pin & (L < sll) & (C > sll), L - 0.1 * A)
    dn3 = (shift(C) < shift(C, 2)) & (shift(C, 2) < shift(C, 3)) & (shift(C, 3) < shift(C, 4))
    o[104] = (pin & dn3, L)
    o[105] = (((C - shift(C, 5)) < -1.5 * A) & (loww >= 2 * body) & (loww > 0), L)
    o[106] = (bull & (upw < 0.1 * rng) & (rng > 1.2 * A), L)
    ib2 = (shift(H, 2) < shift(H, 3)) & (shift(L, 2) > shift(L, 3)); o[108] = (ib2 & (shift(L) < shift(L, 2)) & (C > shift(L, 2)), rmin(L, 2))
    outside = (H > shift(H)) & (L < shift(L))
    o[109] = (outside & (cl >= 0.75) & (shift(C) < shift(C, 4)), L)
    o[110] = (outside & (cl >= 0.75) & (e20 > e50), L)
    o[111] = ((shift(L) < shift(L, 2)) & (shift(L) < L) & (C > shift(H)), shift(L))
    rr = rng; o[112] = (bull & shift(bull.astype(float)).astype(bool) & shift(bull.astype(float), 2).astype(bool) & (rr > shift(rr)) & (shift(rr) > shift(rr, 2)) & (C > shift(C)) & (shift(C) > shift(C, 2)), rmin(L, 3))
    dec = (shift(rr) < shift(rr, 2)) & (shift(rr, 2) < shift(rr, 3)); o[113] = (dec & (C > rmax(shift(H), 3)), rmin(shift(L), 3))
    b2 = shift(body, 2); o[114] = (shift(bear.astype(float), 2).astype(bool) & (b2 > 0.6 * A) & (shift(body) <= 0.3 * b2) & (np.fmax(shift(O), shift(C)) < (shift(O, 2) + shift(C, 2)) / 2) & bull & (C > (shift(O, 2) + shift(C, 2)) / 2), rmin(L, 3))
    o[116] = (shift(bear.astype(float)).astype(bool) & (shift(body) > 0.5 * A) & (O <= shift(C)) & (C > (shift(O) + shift(C)) / 2) & (C < shift(O)), L)
    o[119] = ((np.abs(L - shift(L)) <= 0.05 * A) & shift(bear.astype(float)).astype(bool) & bull & (L <= rmin(L, 10) + 0.1 * A), np.fmin(L, shift(L)) - 0.1 * A)
    har = (np.fmax(shift(O), shift(C)) < np.fmax(shift(O, 2), shift(C, 2))) & (np.fmin(shift(O), shift(C)) > np.fmin(shift(O, 2), shift(C, 2))) & shift(bear.astype(float), 2).astype(bool)
    o[120] = (har & (C > shift(H, 2)), shift(L))
    maru = (body >= 0.9 * rng) & (rng > 1.2 * A); o[121] = (maru & bull, L)
    dn5 = consec(C < shift(C), 5); o[122] = (maru & bear & dn5, L - 0.5 * A)
    doji = (body <= 0.1 * rng) & (rng > 0); dj1 = shift(doji.astype(float)).astype(bool)
    o[123] = (dj1 & (shift(L) <= shift(rmin(L, 20)) + 0.1 * A) & (C > shift(H)), shift(L))
    o[124] = (dj1 & (C > shift(H)), shift(L))
    o[125] = (doji & (loww >= 0.7 * rng), L)
    o[127] = (shift((doji & (rng > 1.5 * A)).astype(float)).astype(bool) & (C > shift(H)), shift(L))
    spin = (body <= 0.3 * rng) & (upw > body) & (loww > body); o[128] = (shift(spin.astype(float)).astype(bool) & (e50 > shift(e50)) & (C > shift(H)), shift(L))
    col = np.sign(C - O); alt = (shift(col) * shift(col, 2) < 0) & (shift(col, 2) * shift(col, 3) < 0) & (shift(col, 3) * shift(col, 4) < 0)
    o[131] = (alt & (C > rmax(shift(H), 4)), rmin(shift(L), 4))
    o[135] = ((e20 > e50) & (loww > 2 * body) & (loww > upw), L)
    o[138] = (dn3 & (cl >= 0.8), L)
    o[139] = (consec(cl >= 0.7, 3), rmin(L, 3))
    first_bar = (mins < tfm) | (mins > 1440 - tfm); gapdn = (sop < prevc - 0.25 * datr)
    fb_bear = pd.Series(np.where(first_bar, bear, np.nan)).groupby(sid).transform("max").to_numpy() > 0
    o[146] = (first(gapdn & fb_bear & (mins >= tfm) & (mins < 120) & (C > sop), sid), dlow)
    o[147] = (first_bar & (loww >= 0.6 * rng) & (rng > 0), L)
    lastbar = (mins >= slen - tfm) & (mins < slen)
    o[148] = (lastbar & bull & (cl >= 0.8), L)
    o[149] = (lastbar & ((C - sop) < -0.5 * datr) & bull & (cl >= 0.8), L)
    o[153] = (consec(C > shift(C), 5) & ~consec(shift(C) > shift(C, 2), 5), rmin(L, 5))
    up = (C > O).astype(float); pu = sma(up, 20); ent = -(pu * np.log2(np.clip(pu, 1e-9, 1)) + (1 - pu) * np.log2(np.clip(1 - pu, 1e-9, 1)))
    o[154] = (edge((ent < 0.7) & (pu > 0.5)), atrstop)
    bodsum = pd.Series(np.where(bull, body, -body)).rolling(10).sum().to_numpy(); o[155] = (edge(bodsum > 2 * A), atrstop)
    wsum = pd.Series(loww).rolling(10).sum().to_numpy() / np.maximum(pd.Series(upw).rolling(10).sum().to_numpy(), 1e-12); o[157] = (edge(wsum > 2), atrstop)
    ovr = (np.fmin(H, shift(H)) - np.fmax(L, shift(L))) / np.maximum(rng, 1e-12); o5 = consec(shift(ovr) > 0.7, 5)
    o[160] = (o5 & (C > rmax(shift(H), 5)), rmin(shift(L), 5))
    o[161] = (consec((L > (shift(H) + shift(L)) / 2) & bull, 3) & ~consec(shift(((L > (shift(H) + shift(L)) / 2) & bull).astype(float)).astype(bool), 3), rmin(L, 3))
    dmv = (shift(C, 3) - shift(C, 8)) < -2 * A; small3 = consec(body < 0.3 * rng, 3); o[169] = (dmv & small3 & edge(small3), rmin(L, 3))
    beng = bear & (shift(C) > shift(O)) & (O >= shift(C)) & (C <= shift(O)); hi_be = pd.Series(np.where(beng, H, np.nan)).ffill(limit=3).to_numpy()
    o[171] = (~beng & np.isfinite(hi_be) & (C > hi_be) & ~(shift(C) > shift(hi_be)), rmin(L, 4))
    bpin = (upw >= 0.6 * rng) & (rng > 0); hi_bp = pd.Series(np.where(bpin, H, np.nan)).ffill(limit=3).to_numpy()
    o[172] = (~bpin & np.isfinite(hi_bp) & (C > hi_bp) & ~(shift(C) > shift(hi_bp)), rmin(L, 4))
    ins = (H < shift(H)) & (L > shift(L)); o[173] = (shift(ins.astype(float)).astype(bool) & outside & (cl >= 0.75), L)
    o[174] = (shift((outside & (cl >= 0.5) & bull).astype(float), 2).astype(bool) & shift(ins.astype(float)).astype(bool) & (C > shift(H)), shift(L))
    o[175] = ((shift(L) < shift(L, 2)) & (C > shift(H, 2)), shift(L))
    o[176] = ((shift(L) <= shift(rmin(L, 4))) & (C > rmax(shift(H), 3)), shift(L))
    o[177] = ((shift(L) <= shift(rmin(L, 5))) & (C > rmax(shift(H), 4)), shift(L))
    o[178] = (bull & (shift(L) <= shift(rmin(L, 20))) & (shift(body) < 0.5 * sma(body, 20)), shift(L))
    o[179] = (shift((bear & (rng > 3 * A)).astype(float)).astype(bool) & ins & bull, shift(L))
    o[189] = (consec(C < O, 4), L - 0.5 * A)
    o[194] = (bull & (cl >= 0.7) & (hx["c"] > hx["e"]) & (hx["r"] > 50), L)
    pat = engulf | pin
    o[196] = (pat & (np.abs(L - poc) <= 0.2 * A), L - 0.1 * A)
    o[197] = (pat & (L <= vw) & (C >= vw), L - 0.1 * A)
    o[198] = (pat & ((np.abs(L - pdl) <= 0.2 * A) | (np.abs(L - pdh) <= 0.2 * A)), L - 0.1 * A)
    o[199] = (pat & (L <= dlow), L - 0.1 * A)
    # ---- volume / crypto taker-flow 201-300 (delta = taker buy - taker sell, Binance)
    tb = X.extra.get("tb"); havedelta = tb is not None and np.isfinite(tb).mean() > 0.5
    z = np.zeros(N, bool)
    if havedelta:
        dl = (2 * tb - np.abs(V)) * (1.0 if not X.neg else -1.0); dsd = rstd(dl, 200); d10 = pd.Series(dl).rolling(10).sum().to_numpy(); d20 = pd.Series(dl).rolling(20).sum().to_numpy()
        o[201] = (edge(((C - shift(C, 10)) < 0) & (d10 > 0)), rmin(L, 10))
        o[202] = (edge((C > K.hb_(X, 20)) & (d20 > 0)), atrstop)
        o[205] = ((dl < -2 * dsd) & (cl >= 0.5), L)
        o[206] = (shift((dl < -2 * dsd).astype(float)).astype(bool) & (C > shift(H)), rmin(L, 2))
        d3 = pd.Series(dl).rolling(3).sum().to_numpy(); o[221] = (edge((d3 > shift(d3)) & (shift(d3) > shift(d3, 2)) & (d3 > 0)), atrstop)
        dz = (d20 - pd.Series(d20).rolling(500).mean().to_numpy()) / rstd(d20, 500); o[223] = (edge(dz < -2) & (C > shift(C)), atrstop)
        o[225] = (edge(((C - shift(C, 5)) < 0) & (pd.Series(dl).rolling(5).sum().to_numpy() > 0)), rmin(L, 5))
        ratio = pd.Series(tb).rolling(10).sum().to_numpy() / np.maximum(pd.Series(np.abs(V)).rolling(10).sum().to_numpy(), 1e-12)
        ratio = ratio if not X.neg else 1 - ratio; o[233] = (edge(ratio > 0.55), atrstop)
        o[235] = (xup(d20, 0.0) & (C > e50), atrstop)
        e5, e20d = ema(np.nan_to_num(dl), 5), ema(np.nan_to_num(dl), 20); o[244] = (xup(e5, 0.0) & (e20d < 0), atrstop)
        sdl = pd.Series(dl).groupby(sid).sum().shift(1).reindex(sid).to_numpy(); o[290] = (first_bar & (sdl > 0), atrstop)
    else:
        for k_ in (201, 202, 205, 206, 221, 223, 225, 233, 235, 244, 290): o[k_] = (z, atrstop)
    if X.hasvol:
        o[208] = ((V > 2 * vavg) & (rng < 0.7 * A) & (L <= rmin(L, 20) + 0.2 * A), L - 0.3 * A)
        absb = (V > 1.5 * vavg) & (rng < 0.7 * A); o[210] = (consec(shift(absb.astype(float)).astype(bool), 3) & (C > rmax(shift(H), 3)), rmin(shift(L), 3))
        o[211] = (shift(((V > 3 * vavg) & (rng > 2 * A) & bear).astype(float)).astype(bool) & bull & (C > (shift(H) + shift(L)) / 2), shift(L))
        pb = (C < shift(C, 3)) & (pd.Series(V).rolling(3).mean().to_numpy() < 0.6 * vavg); o[212] = ((e20 > e50) & shift(pb.astype(float)).astype(bool) & bull & (V > vavg), rmin(L, 4))
        o[213] = (consec(shift((V < 0.5 * vavg).astype(float)).astype(bool), 5) & (C > rmax(shift(H), 5)) & (V > vavg), rmin(shift(L), 5))
        o[214] = ((V > sma(V, 100) + 3 * vsd) & bull, L)
        o[226] = (edge(((C - shift(C, 5)) < 0) & (pd.Series(V).rolling(5).sum().to_numpy() < 0.7 * pd.Series(V).shift(5).rolling(5).sum().to_numpy())), rmin(L, 5))
        v20, v100 = sma(V, 20), sma(V, 100); o[252] = ((v20 < 0.6 * v100) & (C > K.hb_(X, 20)) & ~(shift(C) > shift(K.hb_(X, 20))), atrstop)
        o[253] = ((sma(V, 5) > 2 * sma(V, 50)) & (C > K.hb_(X, 20)) & ~(shift(C) > shift(K.hb_(X, 20))), atrstop)
        o[254] = ((V > 4 * vavg) & bull, L)
        o[255] = ((V > 4 * vavg) & bear, L - 0.5 * A)
        o[256] = ((L <= shift(rmin(L, 20))) & (V < 0.7 * vavg) & bull, L - 0.2 * A)
        o[257] = (consec(V > shift(V), 3) & consec(C > shift(C), 3), rmin(L, 3))
        dmv5 = (shift(C, 3) - shift(C, 8)) < -2 * A; o[258] = (dmv5 & consec(V < shift(V), 3) & bull, rmin(L, 4))
        upv = pd.Series(np.where(C > shift(C), V, 0)).rolling(20).sum().to_numpy(); dnv = pd.Series(np.where(C < shift(C), V, 0)).rolling(20).sum().to_numpy()
        o[270] = (edge((upv > 1.5 * dnv) & (C > e50)), atrstop)
        ses_up = pd.Series(np.where(C > O, V, 0)).groupby(sid).sum() / pd.Series(V).groupby(sid).sum().replace(0, np.nan); o[289] = (first_bar & (ses_up.shift(1).reindex(sid).to_numpy() > 0.6), atrstop)
        sv = pd.Series(V).groupby(sid).sum(); svc = (sv > 2 * sv.rolling(20).mean()).shift(1).reindex(sid).fillna(False).to_numpy().astype(bool)
        sret = (scl - pd.Series(O).groupby(sid).first()).shift(1).reindex(sid).to_numpy(); o[291] = (first_bar & svc & (sret < 0), atrstop)
    else:
        for k_ in (208, 210, 211, 212, 213, 214, 226, 252, 253, 254, 255, 256, 257, 258, 270, 289, 291): o[k_] = (z, atrstop)
    # ---- volatility 401-500
    sqz = (ub < ku) & (lbb > kl); o[405] = (shift(consec(sqz, 5).astype(float)).astype(bool) & ~sqz & (C > m_), m_)
    kw = (ku - kl); o[406] = ((C > ku) & (kw > shift(kw, 5)) & ~(shift(C) > shift(ku)), km)
    hv20, hv100 = rstd(r1, 20), rstd(r1, 100); o[409] = (xup(hv20 / hv100, 1.0) & (C > K.hb_(X, 20)), atrstop)
    o[410] = ((hv20 / hv100 > 2) & (X.z(50) < -2) & bull, atrstop)
    rv10, rv50 = rstd(r1, 10), rstd(r1, 50); o[411] = (edge((rv10 / rv50 > 1.5) & (C > e20) & (e20 > shift(e20))), atrstop)
    park = np.sqrt(pd.Series(np.log(np.abs(H / np.where(L == 0, np.nan, L))) ** 2).rolling(20).mean().to_numpy()); pp_ = pct_rank(park, 200)
    o[413] = (((pp_ > 0.8) & (C > K.hb_(X, 20)) & ~(shift(C) > shift(K.hb_(X, 20)))) | ((pp_ < 0.2) & (shift(C) < shift(lbb)) & (C > lbb)), atrstop)
    up_sv = pd.Series(np.where(r1 > 0, r1 ** 2, 0)).rolling(50).sum().to_numpy(); dn_sv = pd.Series(np.where(r1 < 0, r1 ** 2, 0)).rolling(50).sum().to_numpy()
    o[417] = (edge(up_sv > 1.5 * dn_sv), atrstop)
    o[418] = (r1 > 3 * rstd(r1, 100), L)
    o[421] = (within(ap > 0.9, 10) & (ap < 0.6) & (C < e20) & bull, atrstop)
    vov = rstd(A, 50) / sma(A, 50); vz = (vov - sma(vov, 200)) / rstd(vov, 200); o[422] = ((vz > 2) & (C > K.hb_(X, 20)) & ~(shift(C) > shift(K.hb_(X, 20))), atrstop)
    vix_ts, vrp = X.extra.get("vixts"), X.extra.get("vrp")
    if vix_ts is not None and not X.neg:
        o[427] = (first_bar & (vix_ts < 0.9), atrstop); o[428] = (first_bar & (vrp > 4), atrstop)
    else: o[427] = (z, atrstop); o[428] = (z, atrstop)
    pr = pd.DataFrame({"d": dday, "h": H, "l": L, "c": C, "o": O}).groupby("d").agg(h=("h", "max"), l=("l", "min"), c=("c", "last"), o=("o", "first"))
    prg = (pr.h - pr.l); shock_dn = ((prg > 2 * prg.rolling(14).mean()) & (pr.c < pr.o)).shift(1).reindex(dday).fillna(False).to_numpy().astype(bool)
    shock_up = ((prg > 2 * prg.rolling(14).mean()) & (pr.c > pr.o)).shift(1).reindex(dday).fillna(False).to_numpy().astype(bool)
    o[437] = (first_bar & shock_dn, atrstop); o[438] = (first_bar & shock_up, atrstop)
    o[448] = (r1 > 4 * sd1, L); o[449] = ((r1 < -4 * sd1), L - 0.5 * A)
    vsm = (C - shift(C, 20)) / (rstd(r1, 20) * np.sqrt(20)); o[451] = (xup(vsm, 1.5), atrstop); o[452] = ((vsm < -2) & bull, atrstop)
    o[467] = ((dhigh - dlow >= datr) & (C <= dlow + 0.2 * (dhigh - dlow)) & bull, dlow - 0.2 * A)
    whigh = pd.Series(H).groupby(wk).cummax().to_numpy(); wlow = pd.Series(L).groupby(wk).cummin().to_numpy()
    o[468] = ((whigh - wlow >= 2.2 * datr) & (C <= wlow + 0.15 * (whigh - wlow)) & bull, wlow - 0.2 * A)
    mhigh = pd.Series(H).groupby(mo).cummax().to_numpy(); mlow = pd.Series(L).groupby(mo).cummin().to_numpy()
    o[469] = ((mhigh - mlow >= 4.5 * datr) & (C <= mlow + 0.1 * (mhigh - mlow)) & bull, mlow - 0.2 * A)
    fd = X.get("fd", lambda: nb_sevcik(C, 50)); z50 = X.z(50)
    o[478] = (((fd < 1.4) & (C > K.hb_(X, 20)) & ~(shift(C) > shift(K.hb_(X, 20)))) | ((fd > 1.6) & (shift(z50) < -2) & (C > shift(C))), atrstop)
    # ---- statistics 501-600
    med = pd.Series(C).rolling(50).median().to_numpy(); mad = pd.Series(np.abs(C - med)).rolling(50).median().to_numpy(); rz = (C - med) / (1.4826 * mad)
    o[502] = ((shift(rz) < -3) & (C > shift(C)), atrstop)
    q05 = pd.Series(C).rolling(200).quantile(0.05).to_numpy(); o[504] = ((shift(C) < shift(q05)) & bull, L)
    def quad():
        n = 100; xx = np.arange(n) - (n - 1) / 2; Xm = np.vstack([np.ones(n), xx, xx ** 2]).T; P = np.linalg.pinv(Xm); out_ = np.full(N, np.nan)
        win = np.lib.stride_tricks.sliding_window_view(C, n); coef = win @ P.T; fit_last = coef @ Xm[-1]; resid = win - coef @ Xm.T; sd_ = resid.std(1)
        out_[n - 1:] = (C[n - 1:] - fit_last) / np.where(sd_ > 0, sd_, np.nan); return out_
    qz = X.get("quad", quad); o[507] = ((shift(qz) < -2) & bull, atrstop)
    kf = X.get("kal", lambda: K.nb_kalman(C, 1e-4 * np.nanvar(np.diff(C)), np.nanvar(np.diff(C)))); kr = (C - kf) / rstd(C - kf, 100)
    o[510] = ((shift(kr) < -2) & bull, atrstop)
    cu_up, cu_dn = X.get("cusum", lambda: nb_cusum(r1, 3 * sd1)); o[521] = (cu_up, atrstop); o[522] = (cu_dn & False | shift(cu_dn.astype(float)).astype(bool) & bull, atrstop)
    r4 = C - shift(C, 4); vr = pd.Series(r4).rolling(200).var().to_numpy() / (4 * pd.Series(r1).rolling(200).var().to_numpy())
    o[525] = (edge((vr > 1.15) & (r4 > 0)), atrstop); o[526] = (edge((vr < 0.85) & (r4 < -rstd(r4, 200))), atrstop)
    pe = X.get("pe", lambda: nb_perm_entropy(C, 50)); o[534] = (edge((pe < 0.85) & ((C - shift(C, 10)) > 0)), atrstop)
    dev = C - e50; phi = pd.Series(dev).rolling(200).corr(pd.Series(dev).shift(1)).to_numpy(); hl = -np.log(2) / np.log(np.clip(phi, 1e-6, 0.999999))
    devz = dev / rstd(dev, 200); o[541] = ((hl < 30) & (shift(devz) < -2) & bull, atrstop)
    ph1 = pd.Series(r1).rolling(200).corr(pd.Series(r1).shift(1)).to_numpy(); fc = ph1 * r1
    o[543] = (edge(fc > 2 * MK[X.sym][2] * np.abs(C)), atrstop)
    q005 = pd.Series(r1).rolling(1000, min_periods=500).quantile(0.005).to_numpy(); o[553] = (r1 < q005, L - 0.5 * A)
    # ---- time / session 801-900 (intraday ones)
    lt_ny = X.loc("America/New_York"); nyh = lt_ny.hour.to_numpy(); nyd = lt_ny.dayofweek.to_numpy()
    wopen = pd.Series(O).groupby(wk).transform("first").to_numpy()
    o[805] = ((nyd == 4) & (nyh == 14) & (lt_ny.minute.to_numpy() < tfm) & ((C - wopen) < -datr), atrstop)
    wbar = pd.Series(np.ones(N)).groupby(wk).cumsum().to_numpy(); wor = wbar <= (16 if X.tf == "M15" else 4)
    wrh = pd.DataFrame({"w": wk, "h": np.where(wor, H, np.nan)}).groupby("w").h.transform("max").to_numpy(); wrl = pd.DataFrame({"w": wk, "l": np.where(wor, L, np.nan)}).groupby("w").l.transform("min").to_numpy()
    o[807] = (first(~wor & (C > wrh), wk), (wrh + wrl) / 2)
    pwret = (pd.Series(C).groupby(wk).last() - pd.Series(O).groupby(wk).first()).shift(1).reindex(wk).to_numpy()
    o[806] = ((nyd == 0) & first_bar & (pwret < -datr), atrstop)
    pmret = (pd.Series(C).groupby(mo).last() - pd.Series(O).groupby(mo).first()).shift(1).reindex(mo).to_numpy(); mbar = pd.Series(np.ones(N)).groupby(mo).cumsum().to_numpy() == (4 if X.tf == "M15" else 1)
    o[811] = (mbar & (pmret > 0), atrstop); o[812] = (mbar & (pmret < 0), atrstop)
    us = MK[X.sym][4][0] == "America/New_York" and MK[X.sym][5] in ("index",)
    if us:
        nymin = (lt_ny.hour * 60 + lt_ny.minute).to_numpy(); ndk = dayno(lt_ny)
        lun = (nymin >= 720) & (nymin < 810); dl_ = pd.DataFrame({"d": ndk, "h": np.where(lun, H, np.nan), "l": np.where(lun, L, np.nan)})
        lh = dl_.groupby("d").h.transform("max").to_numpy(); ll_ = dl_.groupby("d").l.transform("min").to_numpy()
        mor = (nymin >= 570) & (nymin < 720); dm_ = pd.DataFrame({"d": ndk, "h": np.where(mor, H, np.nan), "l": np.where(mor, L, np.nan)})
        mrg = dm_.groupby("d").h.transform("max").to_numpy() - dm_.groupby("d").l.transform("min").to_numpy()
        aft = (nymin >= 810) & (nymin < 945)
        o[858] = (first(aft & (C > lh), ndk), (lh + ll_) / 2); o[857] = (first(aft & (C > lh) & ((lh - ll_) < 0.5 * mrg), ndk), (lh + ll_) / 2)
        c16 = pd.Series(np.where((nymin >= 960 - tfm) & (nymin < 960), C, np.nan)).groupby(ndk).transform("max").to_numpy()
        at20 = (nymin >= 1200 - tfm) & (nymin < 1200); o[855] = (at20 & ((C - c16) > 0.003 * np.abs(c16)), atrstop)
    else:
        for k_ in (855, 857, 858): o[k_] = (z, atrstop)
    qm = X.T.month.to_numpy(); qend = np.isin(qm, [3, 6, 9, 12]); qn = X.T.year.to_numpy() * 4 + (qm - 1) // 3
    dlast = pd.Series(dday).groupby(qn).transform("max").to_numpy(); qtd = C - pd.Series(O).groupby(qn).transform("first").to_numpy()
    o[816] = (first(qend & ((dlast - dday) <= 3) & (qtd < 0), qn), atrstop)
    return o
MIRROR = {115: 114, 117: 116, 118: 119, 126: 125, 130: 129, 137: 136, 156: 157, 163: 162, 182: 181, 207: 206, 222: 221, 224: 223, 234: 233, 16: 15, 17: 18, 25: 26, 55: 54, 419: 418,
          58: 57, 33: 32, 35: 34, 42: 41, 24: 23, 22: 21}
EX = [("fixed 1.5R", 0, 1.5), ("2ATR stop, 3ATR trail", 2, 0.0), ("time exit 10 bars", 5, 0.0)]
def run(job):
    sym, tf = job; b = bars2(sym, tf)
    if b is None or len(b) < 5000: return []
    extra = {}
    if sym in ("BTC", "ETH"): extra["tb"] = b.tb.to_numpy()
    if sym in ("SPX", "NQ"):
        def cboe(n): v = pd.read_csv(f"rdata/cboe/{n}.csv"); v.index = pd.DatetimeIndex(pd.to_datetime(v.DATE, format="%m/%d/%Y")).tz_localize("UTC") + pd.Timedelta(hours=21); return v.CLOSE
        vix = cboe("VIX"); ts = (vix / cboe("VIX3M")); dcl = b.c.resample("1D").last().dropna(); rv = np.log(dcl).diff().rolling(20).std() * np.sqrt(252) * 100
        rv.index = rv.index + pd.Timedelta(hours=21); vrp = (vix - rv.reindex(vix.index, method="ffill"))
        extra["vixts"] = ts.reindex(b.index, method="ffill").to_numpy(); extra["vrp"] = vrp.reindex(b.index, method="ffill").to_numpy()
    Xp = X(b, sym, tf, False, extra); Xp.MKc = MK[sym][5]
    exn = {k: (v if k in ("tb",) else v) for k, v in extra.items()}; Xn = X(b, sym, tf, True, exn); Xn.MKc = MK[sym][5]
    try: Sp, Sn = S2(Xp, b), S2(Xn, b)
    except Exception:
        import traceback; traceback.print_exc(); return []
    O, H, L, C = (b[c].to_numpy() for c in "ohlc"); A = Xp.atr(); shl, shp, shi, sll, slp, sli = Xp.sw()
    cost = MK[sym][2]; swap_bar = MK[sym][3] / 365 * (0.25 if tf == "M15" else 1.0) / 24; T = b.index; yr = T.year.to_numpy(); rows = []; keep = {}
    for sid_ in sorted(Sp):
        sp, stp = Sp[sid_]; sn, stn = Sn.get(sid_, (np.zeros(len(C), bool), np.full(len(C), np.nan)))
        sp = np.nan_to_num(np.asarray(sp, float)).astype(bool); sn = np.nan_to_num(np.asarray(sn, float)).astype(bool)
        if sid_ in (427, 428): sn[:] = False                                   # long-only by construction
        sp[-3:] = False; sn[-3:] = False; kp, kn = np.where(sp)[0], np.where(sn)[0]
        ks = np.r_[kp, kn]; ds = np.r_[np.ones(len(kp)), -np.ones(len(kn))]; stops = np.r_[np.asarray(stp, float)[kp], -np.asarray(stn, float)[kn]]
        oo = np.argsort(ks, kind="stable"); ks, ds, stops = ks[oo].astype(np.int64), ds[oo], stops[oo]
        for nm, md, pr in EX:
            if len(ks) == 0: rows.append(dict(sid=sid_, sym=sym, tf=tf, exit=nm, n=0)); continue
            R, XK = nb_exit(O, H, L, C, A, sll, shl, ks, ds, stops, cost, swap_bar, md, pr, 50)
            kp_ = nb_nonoverlap(ks, XK, np.isfinite(R)); rr = R[kp_]; tt = T[ks][kp_]; tr = tt < SPLIT
            tst = lambda v: float(v.mean() / v.std(ddof=1) * np.sqrt(len(v))) if len(v) > 2 and v.std() > 0 else np.nan
            yrs = pd.Series(rr).groupby(yr[ks][kp_]).sum() if len(rr) else pd.Series(dtype=float)
            rows.append(dict(sid=sid_, sym=sym, tf=tf, exit=nm, n=int(len(rr)), n_train=int(tr.sum()), n_hold=int((~tr).sum()), avgR=float(rr.mean()) if len(rr) else np.nan,
                             avgR_train=float(rr[tr].mean()) if tr.sum() else np.nan, avgR_hold=float(rr[~tr].mean()) if (~tr).sum() else np.nan, t_train=tst(rr[tr]), t_hold=tst(rr[~tr]),
                             win=float((rr > 0).mean()) if len(rr) else np.nan, pos_years=int((yrs > 0).sum()), years=int(len(yrs)), pf=float(rr[rr > 0].sum() / -rr[rr < 0].sum()) if (rr < 0).any() else np.nan))
            if len(rr) >= 30 and np.isfinite(rows[-1]["t_train"]) and rows[-1]["t_train"] > 2: keep[(sid_, sym, tf, nm)] = (tt.values, rr.astype(np.float32), T[XK[kp_]].values)
    print(f"{sym} {tf}: {len(rows)} results", flush=True); pd.to_pickle(keep, f"cat2000/trades_{sym}_{tf}.pkl"); return rows
if __name__ == "__main__":
    jobs = [(s, tf) for s in MK for tf in ("M15", "H1") if not (tf == "M15" and MK[s][0] is None)]
    if len(sys.argv) > 1: jobs = [tuple(j.split(":")) for j in sys.argv[1:]]
    with Pool(4) as p: res = p.map(run, jobs, chunksize=1)
    D = pd.DataFrame([r for o in res for r in o]); D.to_pickle("cat2000/results_intraday.pkl" if len(sys.argv) == 1 else "cat2000/results_partial.pkl"); print("rows", len(D))
