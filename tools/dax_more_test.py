# Run from the scratchpad (needs world_lab.py and DAX day files).
# More DAX strategies around the Frankfurt day: US-open ORB, afternoon momentum, pre-market range, gap, ORB second chance.
import sys, numpy as np, pandas as pd
sys.argv = ["x", "DEUIDXEUR"]
exec(open("world_lab.py").read().split("rows, TR = [], {}")[0])
rows, TR = [], {}
def add(tr, nm):
    if len(tr) > 50: rows.append(stats(tr, nm)); TR[nm] = tr
for tf in ("5min", "15min"):
    b = bars(tf); T = b.index; fr = T.tz_convert(TZ); fm = (fr.hour * 60 + fr.minute).to_numpy(); fday = fr.normalize()
    O, H, L, C = (b[k].to_numpy() for k in "ohlc"); atr = atr_of(b)
    dc = b.c.resample("1D").last().dropna()
    ema_d = {n: dc.ewm(span=n, adjust=False).mean().shift(1).reindex(T.floor("D"), method="ffill").to_numpy() for n in (20, 50)}
    datr = (b.h.resample("1D").max() - b.l.resample("1D").min()).dropna().ewm(alpha=1 / 14, adjust=False).mean().shift(1).reindex(T.floor("D"), method="ffill").to_numpy()
    def rng(a, z):
        m = (fm >= a) & (fm < z)
        g = pd.DataFrame({"h": np.where(m, H, np.nan), "l": np.where(m, L, np.nan), "d": fday}).groupby("d").agg(h=("h", "max"), l=("l", "min"))
        return g.h.reindex(fday).to_numpy(), g.l.reindex(fday).to_numpy()
    def at_price(mins):          # close of the bar that ends at `mins` Frankfurt, per day
        m = fm == mins - (5 if tf == "5min" else 15)
        s = pd.Series(np.where(m, C, np.nan)).groupby(fday.values).transform("max").to_numpy(); return s
    trendsig = lambda d, i, tr: d if tr is None or (C[i] - ema_d[tr][i]) * d > 0 else 0
    # 1) US-open ORB: range 15:30-15:45/16:00 Frankfurt, entries until 17:00, flat 17:25
    for N in ((15, 30) if tf == "5min" else (30,)):
        orh, orl = rng(930, 930 + N)
        for trend in (None, 20, 50):
            for stop in ("mid", "other"):
                sig = lambda i, trend=trend: 0 if not np.isfinite(orh[i]) else trendsig(1 if C[i] > orh[i] else (-1 if C[i] < orl[i] else 0), i, trend)
                stp = lambda i, d, e, stop=stop: (orh[i] + orl[i]) / 2 if stop == "mid" else (orl[i] if d == 1 else orh[i])
                add(intraday_sim(b, sig, stp, 0, 1045, 930 + N, 1020), f"DAX {tf} US-open ORB{N} trend{trend} stop-{stop}")
    # 2) afternoon momentum: 09:00 -> 15:30 move decides 15:30 -> 17:25
    p900 = at_price(545 if tf == "5min" else 555); p1530 = at_price(930)
    for thr in (0.0, 0.25, 0.5):
        for sk in (0.3, 0.6):
            def sig(i, thr=thr):
                if fm[i] != 930 - (5 if tf == "5min" else 15) or not (np.isfinite(p900[i]) and np.isfinite(datr[i])): return 0
                mv = C[i] - p900[i]; return 0 if abs(mv) < thr * datr[i] else (1 if mv > 0 else -1)
            stp = lambda i, d, e, sk=sk: e - d * sk * datr[i]
            add(intraday_sim(b, sig, stp, 0, 1045, 900, 935), f"DAX {tf} afternoon momentum thr{thr} stop{sk}dATR")
    # 3) pre-market range 08:00-09:00, entries 09:00-11:00, flat 17:25
    pmh, pml = rng(480, 540)
    for trend in (None, 50):
        for stop in ("mid", "other"):
            sig = lambda i, trend=trend: 0 if not np.isfinite(pmh[i]) else trendsig(1 if C[i] > pmh[i] else (-1 if C[i] < pml[i] else 0), i, trend)
            stp = lambda i, d, e, stop=stop: (pmh[i] + pml[i]) / 2 if stop == "mid" else (pml[i] if d == 1 else pmh[i])
            add(intraday_sim(b, sig, stp, 0, 1045, 540, 660), f"DAX {tf} pre-market range trend{trend} stop-{stop}")
    # 4) opening gap: previous 17:30 close vs 09:00 open -> follow / fade, entry on the first bar after 09:00, exit 12:00 or 17:25
    pc = pd.Series(np.where(fm == 1050 - (5 if tf == "5min" else 15), C, np.nan)).groupby(fday.values).transform("max")
    prevclose = pd.Series(pc.groupby(fday.values).first()).shift(1).reindex(fday.values).to_numpy()
    for thr in (0.2, 0.4):
        for mode in ("follow", "fade"):
            for fl in (720, 1045):
                def sig(i, thr=thr, mode=mode):
                    if fm[i] != 540 or not (np.isfinite(prevclose[i]) and np.isfinite(datr[i])): return 0
                    g = O[i] - prevclose[i]
                    if abs(g) < thr * datr[i]: return 0
                    return (1 if g > 0 else -1) * (1 if mode == "follow" else -1)
                stp = lambda i, d, e: e - d * 0.5 * datr[i]
                add(intraday_sim(b, sig, stp, 0, fl, 540, 545), f"DAX {tf} gap {mode} >{thr}dATR until{fl}")
    # 5) morning ORB with a second chance: up to 2 trades a day (the opposite break after a failed first one)
    for N in ((15, 30) if tf == "5min" else (30, 60)):
        orh, orl = rng(540, 540 + N)
        for trend in (None, 50):
            sig = lambda i, trend=trend: 0 if not np.isfinite(orh[i]) else trendsig(1 if C[i] > orh[i] else (-1 if C[i] < orl[i] else 0), i, trend)
            stp = lambda i, d, e: (orh[i] + orl[i]) / 2
            tr = intraday_sim(b, sig, stp, 0, 1045, 540 + N, 720, one_per_day=False)
            seen = {}; tr2 = []
            for t in tr:                                     # keep only the first two trades of each day (no look-ahead)
                dkey = t[0].tz_convert(TZ).normalize(); seen[dkey] = seen.get(dkey, 0) + 1
                if seen[dkey] <= 2: tr2.append(t)
            add(tr2, f"DAX {tf} ORB{N} second-chance trend{trend}")
df = pd.DataFrame(rows); df["minhalf"] = df[["yrA", "yrB"]].min(axis=1)
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 300)
print(f"{len(df)} versions; >=10%/yr both halves: {(df.minhalf >= 10).sum()}; positive both: {(df.minhalf > 0).sum()}")
print(df.sort_values("minhalf", ascending=False).round(2).to_string(index=False))
pd.to_pickle((df, TR), "dax_more.pkl")
