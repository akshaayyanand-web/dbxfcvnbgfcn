# The user's strategy list: every mechanically testable idea on gold, Nasdaq, S&P, BTC, silver.
# Standalone at 1% risk by halves, then the best few go through the 8-EA prop test (add and swap).
import sys, numpy as np, pandas as pd
SP = sys.argv[1]
exec(open(SP + "/speed8.py").read().split("V2 = [")[0])
_l = open(SP + "/losers.py").read(); exec("def run3" + _l.split("def run3", 1)[1].split("wst =")[0])
import orb_lab as O
from portfolio_prop import resample, rsi, rma
from multiprocessing import Pool
spx = load_csv(SP + "/fut/USA500IDXUSD.csv"); slv = load_csv(SP + "/fut/XAGUSD.csv")
g5 = O.five_min(load_csv(SP + "/fut1m/XAUUSD_1m.csv"))
MK = {"gold": (gold, 0.0001, "America/New_York"), "nq": (nq, 0.00012, "America/New_York"), "spx": (spx, 0.0001, "America/New_York"),
      "btc": (btc, 0.0012, "UTC"), "silver": (slv, 0.00025, "America/New_York")}

def atr_of(b, n=14):
    pc = b.c.shift(); return rma(pd.concat([b.h - b.l, (b.h - pc).abs(), (b.l - pc).abs()], axis=1).max(axis=1), n).to_numpy()
def sim(b, L, S, stL, stS, tgR=None, tgL=None, tgS=None, xL=None, xS=None, maxb=48, flat=None):
    O_, H, Lo, C, T = b.o.to_numpy(), b.h.to_numpy(), b.l.to_numpy(), b.c.to_numpy(), b.index
    bar = T[1] - T[0]; n = len(C); out = []; i = 0
    while i < n - 2:
        d = 1 if L[i] else (-1 if S is not None and S[i] else 0)
        if d == 0: i += 1; continue
        j = i + 1; e = O_[j]; st = stL[i] if d == 1 else stS[i]
        if not np.isfinite(st) or d * (e - st) <= 0: i += 1; continue
        tg = (tgL[i] if d == 1 else tgS[i]) if tgL is not None else (e + d * tgR * abs(e - st) if tgR else None)
        if tg is not None and (not np.isfinite(tg) or d * (tg - e) <= 0): i += 1; continue
        k, px = j, None
        while k < n - 1:
            if (Lo[k] <= st) if d == 1 else (H[k] >= st): px, xt = (min(O_[k], st) if d == 1 else max(O_[k], st)), T[k] + bar; break
            if tg is not None and ((H[k] >= tg) if d == 1 else (Lo[k] <= tg)): px, xt = (max(O_[k], tg) if d == 1 else min(O_[k], tg)), T[k] + bar; break
            if k - j + 1 >= maxb or (flat is not None and flat[k]) or (d == 1 and xL is not None and xL[k]) or (d == -1 and xS is not None and xS[k]):
                px, xt = O_[k + 1], T[k + 1]; k += 1; break
            k += 1
        if px is None: break
        if xt - T[j] <= pd.Timedelta(days=12): out.append((T[j], xt, e, st, px))
        i = k
    return out
CAND = {}
def add(name, mkt, trades):
    df, cost, tz = MK[mkt] if mkt in MK else mkt
    CAND[name] = P.trade_series(trades, cost, df, idx)

def cross_up(a, b): return (a > b) & (np.roll(a, 1) <= np.roll(b, 1))
for m, (df, cost, tz) in MK.items():
    # ---------- trend families on 4h ----------
    b = resample(df, "4h"); c = b.c.to_numpy(); a4 = atr_of(b)
    for f, s_, mult in ((50, 200, 3.0), (20, 50, 2.5)):
        ef, es = b.c.ewm(span=f, adjust=False).mean().to_numpy(), b.c.ewm(span=s_, adjust=False).mean().to_numpy()
        add(f"{m} MA cross {f}/{s_} (4h)", m, sim(b, cross_up(ef, es), cross_up(es, ef), c - mult * a4, c + mult * a4, xL=ef < es, xS=ef > es, maxb=10 ** 6))
    # supertrend 10 x 3
    hl2 = ((b.h + b.l) / 2).to_numpy(); atr10 = atr_of(b, 10); up, dn = hl2 - 3 * atr10, hl2 + 3 * atr10
    fu, fd, dr = up.copy(), dn.copy(), np.ones(len(c))
    for i in range(1, len(c)):
        if not np.isfinite(atr10[i - 1]): continue
        fu[i] = max(up[i], fu[i - 1]) if c[i - 1] > fu[i - 1] else up[i]
        fd[i] = min(dn[i], fd[i - 1]) if c[i - 1] < fd[i - 1] else dn[i]
        dr[i] = 1 if c[i] > fd[i - 1] else (-1 if c[i] < fu[i - 1] else dr[i - 1])
    flipU = (dr == 1) & (np.roll(dr, 1) == -1); flipD = (dr == -1) & (np.roll(dr, 1) == 1)
    add(f"{m} Supertrend 10x3 (4h)", m, sim(b, flipU, flipD, np.minimum(fu, c - 0.5 * a4), np.maximum(fd, c + 0.5 * a4), xL=dr == -1, xS=dr == 1, maxb=10 ** 6))
    # heikin ashi + supertrend
    hc = ((b.o + b.h + b.l + b.c) / 4).to_numpy(); ho = np.empty(len(c)); ho[0] = b.o.iat[0]
    for i in range(1, len(c)): ho[i] = (ho[i - 1] + hc[i - 1]) / 2
    green = hc > ho
    add(f"{m} Heikin Ashi + Supertrend (4h)", m, sim(b, green & ~np.roll(green, 1) & (dr == 1), ~green & np.roll(green, 1) & (dr == -1),
                                                   c - 2 * a4, c + 2 * a4, xL=~green, xS=green, maxb=10 ** 6))
    # weekly high/low sweep and weekly-open reversion (4h)
    wk = b.index.to_period("W-SUN"); g = pd.DataFrame({"h": b.h.to_numpy(), "l": b.l.to_numpy(), "o": b.o.to_numpy()}, index=wk).groupby(level=0)
    pwh = g.h.max().shift(1).reindex(wk).to_numpy(); pwl = g.l.min().shift(1).reindex(wk).to_numpy(); wo = g.o.first().reindex(wk).to_numpy()
    H4, L4 = b.h.to_numpy(), b.l.to_numpy()
    wkh = pd.Series(H4, index=b.index).groupby(wk).cummax().to_numpy(); wkl = pd.Series(L4, index=b.index).groupby(wk).cummin().to_numpy()
    add(f"{m} weekly high/low sweep (4h)", m, sim(b, (L4 < pwl) & (c > pwl), (H4 > pwh) & (c < pwh), wkl - 0.2 * a4, wkh + 0.2 * a4, tgR=2.0, maxb=30))
    dow = b.index.dayofweek; mid = (dow >= 1) & (dow <= 3); dev = (c - wo) / a4; fri = (dow == 4) & (b.index.hour >= 16)
    add(f"{m} weekly-open reversion (4h)", m, sim(b, mid & (dev < -3), mid & (dev > 3), c - 1.5 * a4, c + 1.5 * a4, tgL=wo, tgS=wo, maxb=20, flat=fri))
    # ---------- 1h families ----------
    h = df; C, Hh, Ll, Oo = h.c.to_numpy(), h.h.to_numpy(), h.l.to_numpy(), h.o.to_numpy(); a1 = atr_of(h)
    e200 = h.c.ewm(span=200, adjust=False).mean().to_numpy(); upT = C > e200; dnT = C < e200
    e10, e20, e50 = (h.c.ewm(span=s, adjust=False).mean().to_numpy() for s in (10, 20, 50))
    al_u = (e10 > e20) & (e20 > e50); al_d = (e10 < e20) & (e20 < e50)
    add(f"{m} triple EMA 10/20/50 (1h)", m, sim(h, al_u & ~np.roll(al_u, 1), al_d & ~np.roll(al_d, 1), C - 2 * a1, C + 2 * a1, xL=~al_u, xS=~al_d, maxb=10 ** 6))
    r14 = rsi(h.c, 14).to_numpy()
    mid20 = h.c.rolling(20).mean().to_numpy(); sd20 = h.c.rolling(20).std().to_numpy(); bu, bl = mid20 + 2 * sd20, mid20 - 2 * sd20
    ll14, hh14 = h.l.rolling(14).min(), h.h.rolling(14).max(); k_ = (100 * (h.c - ll14) / (hh14 - ll14)).rolling(3).mean(); d_ = k_.rolling(3).mean()
    K, D = k_.to_numpy(), d_.to_numpy()
    tp = ((h.h + h.l + h.c) / 3); cci = ((tp - tp.rolling(20).mean()) / (0.015 * (tp - tp.rolling(20).mean()).abs().rolling(20).mean())).to_numpy()
    kl, ku = e20 - 2 * a1, e20 + 2 * a1
    macd = (h.c.ewm(span=12, adjust=False).mean() - h.c.ewm(span=26, adjust=False).mean()).to_numpy()
    low40 = h.l.rolling(40).min().shift(1).to_numpy(); high40 = h.h.rolling(40).max().shift(1).to_numpy()
    mlow40 = pd.Series(macd).rolling(40).min().shift(1).to_numpy(); mhigh40 = pd.Series(macd).rolling(40).max().shift(1).to_numpy()
    MR = {"RSI 30/70": (cross_up(r14, np.full(len(C), 30.0)), cross_up(np.full(len(C), 70.0), r14), r14 > 50, r14 < 50),
          "Bollinger bounce": ((np.roll(C, 1) < np.roll(bl, 1)) & (C > bl), (np.roll(C, 1) > np.roll(bu, 1)) & (C < bu), C >= mid20, C <= mid20),
          "Stochastic 14,3": (cross_up(K, D) & (K < 20), cross_up(D, K) & (K > 80), K > 50, K < 50),
          "CCI 20 +-100": (cross_up(cci, np.full(len(C), -100.0)), cross_up(np.full(len(C), 100.0), cci), cci > 0, cci < 0),
          "Keltner reversion": ((np.roll(C, 1) < np.roll(kl, 1)) & (C > kl), (np.roll(C, 1) > np.roll(ku, 1)) & (C < ku), C >= e20, C <= e20),
          "MACD divergence": ((Ll < low40) & (macd > mlow40), (Hh > high40) & (macd < mhigh40), None, None)}
    for nm, (lg, sh, xl, xs) in MR.items():
        tgR = 2.0 if xl is None else None
        add(f"{m} {nm} both ways (1h)", m, sim(h, lg, sh, C - 2 * a1, C + 2 * a1, tgR=tgR, xL=xl, xS=xs, maxb=48))
        add(f"{m} {nm} with trend (1h)", m, sim(h, lg & upT, sh & dnT, C - 2 * a1, C + 2 * a1, tgR=tgR, xL=xl, xS=xs, maxb=48))
    # Bollinger squeeze breakout
    bw = (bu - bl) / mid20; sq = pd.Series(bw).rolling(120).min().to_numpy()
    sqz = np.roll(bw <= sq * 1.1, 1)
    add(f"{m} Bollinger squeeze breakout (1h)", m, sim(h, sqz & (C > bu), sqz & (C < bl), mid20, mid20, tgR=2.0, maxb=24))
    # engulfing with 4h trend; pin bar at 20-bar extreme
    e50_4 = pd.Series(b.c.ewm(span=50, adjust=False).mean().to_numpy(), index=b.index).shift(1).reindex(h.index, method="ffill").to_numpy()
    bull = (C > Oo) & (np.roll(C, 1) < np.roll(Oo, 1)) & (C >= np.roll(Oo, 1)) & (Oo <= np.roll(C, 1))
    bear = (C < Oo) & (np.roll(C, 1) > np.roll(Oo, 1)) & (C <= np.roll(Oo, 1)) & (Oo >= np.roll(C, 1))
    add(f"{m} engulfing + 4h trend (1h)", m, sim(h, bull & (C > e50_4), bear & (C < e50_4), Ll - 0.1 * a1, Hh + 0.1 * a1, tgR=2.5, maxb=24))
    rng = Hh - Ll; lw = np.minimum(Oo, C) - Ll; uw = Hh - np.maximum(Oo, C)
    l20 = h.l.rolling(20).min().to_numpy(); h20 = h.h.rolling(20).max().to_numpy()
    add(f"{m} pin bar at 20-bar extreme (1h)", m, sim(h, (lw >= 0.66 * rng) & (Ll <= l20) & (rng > 0), (uw >= 0.66 * rng) & (Hh >= h20) & (rng > 0),
                                                   Ll - 0.1 * a1, Hh + 0.1 * a1, tgR=2.0, maxb=24))
    # yesterday's high / low rejection
    loc = h.index.tz_convert(tz); day = pd.Index((loc - pd.Timedelta(hours=17)).date) if tz != "UTC" else pd.Index(loc.date)
    gd = pd.DataFrame({"h": Hh, "l": Ll}, index=day).groupby(level=0); yh = gd.h.max().shift(1).reindex(day).to_numpy(); yl = gd.l.min().shift(1).reindex(day).to_numpy()
    dh = pd.Series(Hh).groupby(day.to_numpy()).cummax().to_numpy(); dl = pd.Series(Ll).groupby(day.to_numpy()).cummin().to_numpy()
    first_l = (Ll < yl) & (C > yl); first_s = (Hh > yh) & (C < yh)
    seen = pd.Series(first_l | first_s).groupby(day.to_numpy()).cumsum().to_numpy()
    endday = np.r_[day[1:] != day[:-1], True]
    add(f"{m} yesterday high/low rejection (1h)", m, sim(h, first_l & (seen == 1), first_s & (seen == 1), dl - 0.1 * a1, dh + 0.1 * a1, tgR=2.0, maxb=24, flat=endday))
    print(m, "built", len(CAND), flush=True)

# ---------- ICT on specific sessions ----------
for m in ("gold", "nq"):
    df, cost, _ = MK[m]; h = df; loc = h.index.tz_convert("Europe/London"); hr = loc.hour; dd = pd.Index(loc.date)
    C, Hh, Ll = h.c.to_numpy(), h.h.to_numpy(), h.l.to_numpy(); a1 = atr_of(h)
    asia = hr < 7; ah = pd.Series(np.where(asia, Hh, np.nan)).groupby(dd.to_numpy()).transform("max").to_numpy()
    al = pd.Series(np.where(asia, Ll, np.nan)).groupby(dd.to_numpy()).transform("min").to_numpy()
    win = (hr >= 7) & (hr < 10)
    sh = win & (Hh > ah) & (C < ah); lg = win & (Ll < al) & (C > al)
    cnt = pd.Series(sh | lg).groupby(dd.to_numpy()).cumsum().to_numpy()
    lonh = pd.Series(np.where(hr >= 7, Hh, np.nan)).groupby(dd.to_numpy()).cummax().to_numpy(); lonl = pd.Series(np.where(hr >= 7, Ll, np.nan)).groupby(dd.to_numpy()).cummin().to_numpy()
    add(f"{m} Asian sweep / Judas swing (1h)", m, sim(h, lg & (cnt == 1), sh & (cnt == 1), lonl - 0.1 * a1, lonh + 0.1 * a1, tgR=2.0, maxb=12, flat=hr >= 16))
# SMT divergence NQ vs S&P
nqa = nq.reindex(idx).ffill(); spa = spx.reindex(idx).ffill()
for tgt_nm, A, B in (("nq", nqa, spa), ("spx", spa, nqa)):
    a1 = atr_of(A); AL, AH, BL, BH, AC = (A.l.to_numpy(), A.h.to_numpy(), B.l.to_numpy(), B.h.to_numpy(), A.c.to_numpy())
    newAL = AL < pd.Series(AL).rolling(20).min().shift(1).to_numpy(); noBL = BL >= pd.Series(BL).rolling(20).min().shift(1).to_numpy()
    newAH = AH > pd.Series(AH).rolling(20).max().shift(1).to_numpy(); noBH = BH <= pd.Series(BH).rolling(20).max().shift(1).to_numpy()
    tr = sim(A, newAL & noBL, newAH & noBH, AL - 0.25 * a1, AH + 0.25 * a1, tgR=2.0, maxb=24)
    CAND[f"{tgt_nm} SMT divergence NQ vs S&P (1h)"] = P.trade_series(tr, MK[tgt_nm][1], MK[tgt_nm][0], idx)
# Silver Bullet FVG (NQ and gold 5m, 10:00-11:00 NY)
for m, f5 in (("nq", nq5), ("gold", g5)):
    loc = f5.index.tz_convert("America/New_York"); mins = loc.hour * 60 + loc.minute; dd = pd.Index(loc.date).to_numpy()
    O5, H5, L5, C5 = (f5[k].to_numpy() for k in "ohlc"); n = len(C5); Lg = np.zeros(n, bool); Sh = np.zeros(n, bool); stL = np.full(n, np.nan); stS = np.full(n, np.nan)
    inwin = (mins >= 600) & (mins < 660); done = None; fvg = None
    for i in range(2, n):
        if dd[i] != done and inwin[i]:
            if fvg is None or fvg[0] != dd[i]:
                if L5[i] > H5[i - 2] and dd[i - 2] == dd[i]: fvg = (dd[i], 1, L5[i], L5[i - 2], i)
                elif H5[i] < L5[i - 2] and dd[i - 2] == dd[i]: fvg = (dd[i], -1, H5[i], H5[i - 2], i)
            elif i > fvg[4]:
                if fvg[1] == 1 and L5[i] <= fvg[2]: Lg[i] = True; stL[i] = fvg[3]; done = dd[i]
                if fvg[1] == -1 and H5[i] >= fvg[2]: Sh[i] = True; stS[i] = fvg[3]; done = dd[i]
    tr = sim(f5, Lg, Sh, stL, stS, tgR=2.0, maxb=10 ** 6, flat=mins >= 720)
    CAND[f"{m} Silver Bullet FVG (5m)"] = P.trade_series(tr, MK[m][1], MK[m][0], idx)
# post-news 15-min continuation / fade (NQ and gold 5m)
fomc = [d for d in open(SP + "/news/fomc_dates.txt").read().split() if d not in ("20191011", "20200331", "20200827", "20250822")]
EVT = [pd.Timestamp(f"{d[:4]}-{d[4:6]}-{d[6:]} 14:00", tz="America/New_York") for d in fomc]
m1 = pd.read_csv(SP + "/fut1m/USATECHIDXUSD_1m.csv", usecols=[0, 5], index_col=0); m1.index = pd.to_datetime(m1.index, utc=True).tz_convert("America/New_York")
mm = m1.index.hour * 60 + m1.index.minute; dte = m1.index.normalize()
v830 = m1.v[(mm >= 510) & (mm < 515)].groupby(dte[(mm >= 510) & (mm < 515)]).sum(); v820 = m1.v[(mm >= 500) & (mm < 505)].groupby(dte[(mm >= 500) & (mm < 505)]).sum()
ratio = (v830 / v820.reindex(v830.index)).replace([np.inf], np.nan).dropna()
for (yy, mo), gg in ratio.groupby([ratio.index.year, ratio.index.month]):
    early = gg[gg.index.day <= 10]; fri = early[early.index.weekday == 4]
    if len(fri) and fri.iloc[0] >= 3: EVT.append(fri.index[0] + pd.Timedelta(hours=8, minutes=30))
    elif len(early): EVT.append(early.idxmax() + pd.Timedelta(hours=8, minutes=30))
    mid_ = gg[(gg.index.day >= 9) & (gg.index.day <= 16)]
    if len(mid_): EVT.append(mid_.idxmax() + pd.Timedelta(hours=8, minutes=30))
del m1
for m, f5 in (("nq", nq5), ("gold", g5)):
    O5, H5, L5, C5 = (f5[k].to_numpy() for k in "ohlc"); n = len(C5)
    for mode in ("continuation", "fade"):
        Lg = np.zeros(n, bool); Sh = np.zeros(n, bool); stL = np.full(n, np.nan); stS = np.full(n, np.nan); flat = np.zeros(n, bool)
        for ev in EVT:
            a = f5.index.searchsorted(ev.tz_convert("UTC"))
            if a + 3 >= n or f5.index[a] - ev.tz_convert("UTC") > pd.Timedelta(minutes=10): continue
            mv = C5[a + 2] - O5[a]; d = np.sign(mv) * (1 if mode == "continuation" else -1)
            if d == 0: continue
            hi, lo = H5[a:a + 3].max(), L5[a:a + 3].min()
            if d == 1: Lg[a + 2] = True; stL[a + 2] = lo
            else: Sh[a + 2] = True; stS[a + 2] = hi
            e2 = f5.index.searchsorted(ev.tz_convert("UTC") + pd.Timedelta(hours=2)); flat[min(e2, n - 1)] = True
        CAND[f"{m} post-news 15-min {mode} (5m)"] = P.trade_series(sim(f5, Lg, Sh, stL, stS, tgR=2.0, maxb=10 ** 6, flat=flat), MK[m][1], MK[m][0], idx)
# VWAP 2-sigma reversion (NQ 5m, equal-weight session average; the 5m data has no real volume)
loc = nq5.index.tz_convert("America/New_York"); mins = loc.hour * 60 + loc.minute; dd = pd.Index(loc.date).to_numpy()
C5 = nq5.c.to_numpy(); tp = ((nq5.h + nq5.l + nq5.c) / 3).to_numpy(); sess = (mins >= 570) & (mins < 955)
key = np.where(sess, dd, None); s = pd.Series(np.where(sess, tp, np.nan))
vw = s.groupby(key).transform(lambda x: x.expanding().mean()).to_numpy()
dev = pd.Series(np.where(sess, C5 - vw, np.nan)); sig = dev.pow(2).groupby(key).transform(lambda x: x.expanding().mean()).pow(0.5).to_numpy()
ok = sess & (mins >= 600) & (mins < 900)
lg = ok & (C5 < vw - 2 * sig); sh = ok & (C5 > vw + 2 * sig)
CAND["nq VWAP 2-sigma reversion (5m)"] = P.trade_series(sim(nq5, lg, sh, C5 - (vw - C5), C5 + (C5 - vw), tgL=vw, tgS=vw, maxb=10 ** 6, flat=mins >= 955), MK["nq"][1], nq, idx)
print("all built:", len(CAND), flush=True)

# ---------- standalone ----------
yrs = (idx[-1] - idx[0]).days / 365.25; cut = idx.searchsorted(split); f = cut / len(idx)
rows = []
for k, (r, lo) in CAND.items():
    eq = np.cumsum(r); rows.append(dict(strategy=k, yr=100 * r.sum() / yrs, yr_2020_22=100 * r[:cut].sum() / (f * yrs), yr_2023_26=100 * r[cut:].sum() / ((1 - f) * yrs),
                                        maxdd=100 * np.max(np.maximum.accumulate(eq) - eq)))
st = pd.DataFrame(rows).sort_values("yr", ascending=False); st.to_pickle(SP + "/cook9_standalone.pkl")
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 300)
print(f"\nSTANDALONE at 1% risk ({len(st)} strategies). Profitable in both halves: {((st.yr_2020_22 > 0) & (st.yr_2023_26 > 0)).sum()}, "
      f"both halves above +2%/yr: {((st.yr_2020_22 > 2) & (st.yr_2023_26 > 2)).sum()}")
print(st.round(2).to_string(index=False), flush=True)
good = st[(st.yr_2020_22 > 2) & (st.yr_2023_26 > 2) & (st.maxdd < 40)].copy()
good["minhalf"] = good[["yr_2020_22", "yr_2023_26"]].min(axis=1); good = good.sort_values("minhalf", ascending=False).head(8)
wst = pd.date_range("2020-04-01", "2025-10-01", freq="MS", tz="UTC")
def evaluate(v):
    lab, out_k, cand, wt = v
    Rm, LOm, w = R.copy(), LO.copy(), W.copy()
    if out_k: w[names.index(out_k)] = 0.0
    if cand: Rm = np.vstack([Rm, CAND[cand][0]]); LOm = np.vstack([LOm, CAND[cand][1]]); w = np.append(w, wt)
    res = []
    for s_ in est:
        h0 = idx.searchsorted(s_); a, i1, _ = run3(w, Rm, LOm, h0, len(idx), 0.10)
        if a != "pass": res.append((s_, a, None)); continue
        b2, i2, _ = run3(w, Rm, LOm, h0 + i1 + 1, len(idx), 0.05); res.append((s_, b2, (i1 + i2) / 24 if b2 == "pass" else None))
    yy = [(s_, *run3(w, Rm, LOm, idx.searchsorted(s_), idx.searchsorted(s_ + pd.DateOffset(years=1)), None)) for s_ in wst]
    o = dict(variant=lab)
    for p, sel in (("A", lambda s: s < split), ("B", lambda s: s >= split)):
        rr = [x for x in res if sel(x[0])]; t = [x[2] for x in rr if x[2] is not None]; y = [q for q in yy if sel(q[0])]
        o |= {f"{p}_pass": 100 * np.mean([x[1] == "pass" for x in rr]), f"{p}_breach": 100 * np.mean([x[1] == "fail" for x in rr]), f"{p}_days": np.median(t),
              f"{p}_fund": 100 * np.median([q[3] for q in y]), f"{p}_fbr": sum(q[1] == "fail" for q in y)}
    return o
jobs = [("8 EAs as now", None, None, 0)]
for c in good.strategy:
    jobs += [(f"+ {c} 0.25", None, c, 0.25), (f"nqdip -> {c} 0.5", "nqdip", c, 0.5)]
print(f"\nportfolio tests for {len(good)} candidates", flush=True)
with Pool(3) as p: out = p.map(evaluate, jobs)
print(pd.DataFrame(out).round(1).to_string(index=False))
