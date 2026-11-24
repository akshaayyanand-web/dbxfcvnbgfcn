# Nasdaq session momentum (user's idea): first 5m candle after 9:30 NY closes above/below a 5m moving average -> long/short at 9:35.
# Initial stop k_init x daily ATR, trailing stop k_trail x daily ATR from the best price (only tightens), multi-day holds, one position at a time,
# 1% risk per trade. Costs: 0.015% round trip + 6%/yr financing on the notional per night (x3 Friday). Pre-registered 8 variants.
import numpy as np, pandas as pd
d = pd.read_csv("fut1m/USATECHIDXUSD_1m.csv", index_col=0); d.index = pd.to_datetime(d.index, utc=True); d = d[~d.index.duplicated()].sort_index().iloc[:, :4]; d.columns = list("ohlc")
b = d.resample("5min").agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()
O, H, L, C, T = b.o.to_numpy(), b.h.to_numpy(), b.l.to_numpy(), b.c.to_numpy(), b.index
ny = T.tz_convert("America/New_York"); mins = ny.hour * 60 + ny.minute
dd = d.resample("1D").agg({"h": "max", "l": "min", "c": "last"}).dropna(); atr_d = (dd.h - dd.l).rolling(14).mean().shift(1)
EMA = {n: b.c.ewm(span=n, adjust=False).mean().to_numpy() for n in (20, 200)}
first = np.flatnonzero((mins == 570) & (ny.weekday < 5))                     # the 9:30-9:35 candle
COST, FIN = 0.00015, 0.06 / 365
def run(ma, k_init, k_trail):
    out = []; busy_until = -1
    for f in first:
        if f <= busy_until or f + 1 >= len(C): continue
        a = atr_d.asof(T[f].normalize())
        if not np.isfinite(a): continue
        dr = 1 if C[f] > EMA[ma][f] else -1; i = f + 1; e = O[i]; risk = k_init * a; stop = e - dr * risk; best = e; x = None
        for q in range(i, len(C)):
            if (dr > 0 and L[q] <= stop) or (dr < 0 and H[q] >= stop): x = (min(O[q], stop) if dr > 0 else max(O[q], stop)); break
            best = max(best, H[q]) if dr > 0 else min(best, L[q])
            stop = max(stop, best - k_trail * a) if dr > 0 else min(stop, best + k_trail * a)
        if x is None: q = len(C) - 1; x = C[q]
        nights = max(0, (T[q].tz_convert("America/New_York").normalize() - ny[i].normalize()).days)
        notional_frac = e / risk                                              # position notional per 1R of risk
        r = dr * (x - e) / risk - COST * notional_frac - FIN * nights * notional_frac
        out.append((T[i], T[q], dr, r, (T[q] - T[i]).total_seconds() / 86400)); busy_until = q
    return pd.DataFrame(out, columns=["et", "xt", "dir", "R", "days"])
rows = []; S = pd.Timestamp("2023-01-01", tz="UTC"); yrs = (T[-1] - T[first[0]]).days / 365.25
tt = lambda v: round(v.mean() / v.std(ddof=1) * np.sqrt(len(v)), 2) if len(v) > 2 else np.nan
for ma in (20, 200):
    for ki in (2.0, 3.0):
        for kt in (1.0, 2.0):
            D = run(ma, ki, kt); eq = D.R.cumsum(); mdd = (eq - eq.cummax()).min()
            rows.append(dict(average=f"EMA{ma}", init_stop=f"{ki:g}x ATR", trail=f"{kt:g}x ATR", trades=len(D), per_yr=round(len(D) / yrs), win=round(100 * (D.R > 0).mean()),
                             avgR=round(D.R.mean(), 3), R_per_yr=round(D.R.sum() / yrs, 1), pct_yr_at_1pct=round(D.R.sum() / yrs, 1), max_dd_R=round(mdd, 1),
                             avg_hold_days=round(D.days.mean(), 1), t_2019_22=tt(D[D.et < S].R), t_2023_26=tt(D[D.et >= S].R),
                             longs_R_yr=round(D[D.dir > 0].R.sum() / yrs, 1), shorts_R_yr=round(D[D.dir < 0].R.sum() / yrs, 1)))
            print(rows[-1], flush=True)
bh = (C[-1] / O[first[0] + 1] - 1)
print(f"\nBenchmark: holding Nasdaq the whole period = {100*bh:.0f}% total ({100*((1+bh)**(1/yrs)-1):.1f}%/yr)")
pd.set_option("display.width", 250); print(pd.DataFrame(rows).to_string(index=False)); pd.DataFrame(rows).to_csv("nqmom_results.csv", index=False)
