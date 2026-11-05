# Run from the scratchpad (needs calendar_lab.py there).
# Failed-breakout reversals (turtle soup) and VWAP snap-backs on NQ / SPX / gold 5m, New York session.
import sys, numpy as np, pandas as pd
sys.argv = ["x", "."]
exec(open("calendar_lab.py").read().split('if __name__')[0])
from portfolio_prop import rma
def sim(b, sigs, stops, targets, flat_min, tzname="America/New_York"):
    """sigs[i] in {-1,0,1} at bar i close -> entry at next open; one position at a time; stops/targets are price arrays."""
    T = b.index; z = T.tz_convert(tzname); zm = (z.hour * 60 + z.minute).to_numpy(); zd = z.normalize()
    O, H, L = b.o.to_numpy(), b.h.to_numpy(), b.l.to_numpy(); n = len(O); out = []; i = 0
    while i < n - 2:
        d = sigs[i]
        if d == 0: i += 1; continue
        j = i + 1; e = O[j]; st = stops[i]; tg = targets[i]
        if zd[j] != zd[i] or not np.isfinite(st) or (st - e) * d >= 0 or (np.isfinite(tg) and (tg - e) * d <= 0): i += 1; continue
        k = j; px = None
        while k < n:
            if zd[k] != zd[j] or zm[k] >= flat_min: px, xt = O[k], T[k]; break
            if (L[k] <= st) if d == 1 else (H[k] >= st): px, xt = (min(O[k], st) if d == 1 else max(O[k], st)), T[k]; break
            if np.isfinite(tg) and ((H[k] >= tg) if d == 1 else (L[k] <= tg)): px, xt = (max(O[k], tg) if d == 1 else min(O[k], tg)), T[k]; break
            k += 1
        if px is None: break
        out.append((T[j], xt, e, st, px)); i = k + 1
    return out
rows, TRS = [], {}
for mk in ("nq", "spx", "gold"):
    b = B[mk]; T = b.index; z = T.tz_convert("America/New_York"); zm = (z.hour * 60 + z.minute).to_numpy(); zd = z.normalize()
    O, H, L, C = (b[k].to_numpy() for k in "ohlc")
    atr = rma(pd.concat([b.h - b.l, (b.h - b.c.shift()).abs(), (b.l - b.c.shift()).abs()], axis=1).max(axis=1), 14).to_numpy()
    rth = (zm >= 570) & (zm < 960)
    # previous RTH day high / low / close
    g = pd.DataFrame({"h": np.where(rth, H, np.nan), "l": np.where(rth, L, np.nan), "c": np.where(rth, C, np.nan), "d": zd})
    dd = g.groupby("d").agg(h=("h", "max"), l=("l", "min"), c=("c", "last")).dropna()
    prev = dd.shift(1).reindex(zd)
    ph, pl, pc = prev.h.to_numpy(), prev.l.to_numpy(), prev.c.to_numpy()
    # today's high/low so far (RTH)
    hs = pd.Series(np.where(rth, H, np.nan)).groupby(zd.values).cummax().to_numpy(); ls_ = pd.Series(np.where(rth, L, np.nan)).groupby(zd.values).cummin().to_numpy()
    # session VWAP from 09:30 (5m typical price x 1 as a proxy: Dukascopy CFD volume is tick volume)
    tp = (H + L + C) / 3; cum = pd.Series(np.where(rth, tp, np.nan)).groupby(zd.values).expanding().mean().reset_index(level=0, drop=True).sort_index().to_numpy()
    ema = pd.Series(C).ewm(span=800, adjust=False).mean().to_numpy()
    for win_end in (720, 900):
        win = rth & (zm >= 585) & (zm < win_end)
        # 1) turtle soup on the previous day's high / low: today's high went above PDH, now a close back below it -> short
        for buf in (0.0, 0.25):
            for tgt in ("pdmid", "2R", "close"):
                sigs = np.zeros(len(C), int)
                up_fail = win & (hs > ph + buf * atr) & (C < ph) & (np.roll(C, 1) >= ph)
                dn_fail = win & (ls_ < pl - buf * atr) & (C > pl) & (np.roll(C, 1) <= pl)
                sigs[up_fail] = -1; sigs[dn_fail] = 1
                stops = np.where(sigs == -1, hs + 0.1 * atr, ls_ - 0.1 * atr)
                if tgt == "pdmid": targets = (ph + pl) / 2
                elif tgt == "2R": targets = C + sigs * 2 * np.abs(C - stops)
                else: targets = np.full(len(C), np.nan)
                tr = sim(b, sigs, stops, targets, 955); nm = f"{mk} turtle-soup PDH/PDL buf{buf} target-{tgt} until{win_end}"
                if len(tr) > 40: rows.append(stats(tr, MK[mk][1], nm)); TRS[nm] = (mk, tr)
        # 2) VWAP snap-back: k ATR away from VWAP (against the 800-bar EMA trend side only) -> fade back to VWAP
        for kk in (1.5, 2.5, 3.5):
            for trendonly in (True, False):
                sigs = np.zeros(len(C), int)
                lo_ = win & (C < cum - kk * atr) & ((C > ema) if trendonly else True)
                hi_ = win & (C > cum + kk * atr) & ((C < ema) if trendonly else True)
                sigs[lo_] = 1; sigs[hi_] = -1
                stops = C - sigs * 1.5 * atr; targets = cum
                tr = sim(b, sigs, stops, targets, 955); nm = f"{mk} VWAP-snap {kk}ATR trendonly{trendonly} until{win_end}"
                if len(tr) > 40: rows.append(stats(tr, MK[mk][1], nm)); TRS[nm] = (mk, tr)
df = pd.DataFrame(rows); df["minhalf"] = df[["yrA", "yrB"]].min(axis=1)
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 300)
print(f"{len(df)} versions; >=10%/yr both halves: {(df.minhalf >= 10).sum()}; positive both: {(df.minhalf > 0).sum()}")
print(df.sort_values("minhalf", ascending=False).head(25).round(2).to_string(index=False))
df["fam"] = df.edge.str.split(" ").str[:2].str.join(" "); print(df.groupby("fam")[["yrA", "yrB", "yr_cost2", "trades_mo"]].median().round(1).to_string())
pd.to_pickle((df, TRS), "reversal_lab.pkl")
