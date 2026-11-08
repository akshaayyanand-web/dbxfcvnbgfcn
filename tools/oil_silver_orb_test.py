# Run from the scratchpad (hourly oil / silver data in fut/).
# Opening-range (first hour) breakouts on hourly data: oil (NYMEX open) and silver (London / NY opens).
import sys, numpy as np, pandas as pd
sys.path.insert(0, "/home/user/dbxfcvnbgfcn/tools")
from portfolio_prop import load_csv, rma
MK = {"oil NY 09:00": ("fut/LIGHTCMDUSD.csv", "America/New_York", 9, 13, 14, 0.0003),
      "silver London 08:00": ("fut/XAGUSD.csv", "Europe/London", 8, 12, 16, 0.00025),
      "silver NY 08:00": ("fut/XAGUSD.csv", "America/New_York", 8, 12, 15, 0.00025),
      "oil London 08:00": ("fut/LIGHTCMDUSD.csv", "Europe/London", 8, 12, 16, 0.0003)}
rows = []
for nm, (f, tz, oh, last, flat, cost) in MK.items():
    b = load_csv(f).loc["2016-01-01":]; T = b.index; z = T.tz_convert(tz); hr = z.hour.to_numpy(); day = z.normalize()
    O, H, L, C = (b[k].to_numpy() for k in "ohlc")
    dc = b.c.resample("1D").last().dropna(); ema = {n: dc.ewm(span=n, adjust=False).mean().shift(1).reindex(T.floor("D"), method="ffill").to_numpy() for n in (20, 50)}
    rh = pd.Series(np.where(hr == oh, H, np.nan)).groupby(day.values).transform("max").to_numpy()
    rl = pd.Series(np.where(hr == oh, L, np.nan)).groupby(day.values).transform("min").to_numpy()
    for trend in (None, 20, 50):
        for stop in ("mid", "other"):
            for tg in (0, 2.0):
                out, i, traded = [], 0, None
                while i < len(C) - 2:
                    if not (oh + 1 <= hr[i] < last) or traded == day[i] or not np.isfinite(rh[i]): i += 1; continue
                    d = 1 if C[i] > rh[i] else (-1 if C[i] < rl[i] else 0)
                    if d and trend and (C[i] - ema[trend][i]) * d <= 0: d = 0
                    if d == 0: i += 1; continue
                    j = i + 1
                    if day[j] != day[i]: i += 1; continue
                    e = O[j]; st = (rh[i] + rl[i]) / 2 if stop == "mid" else (rl[i] if d == 1 else rh[i])
                    if (st - e) * d >= 0: i += 1; continue
                    tgp = e + d * tg * abs(e - st) if tg else None; k = j; px = None
                    while k < len(C):
                        if day[k] != day[j] or hr[k] >= flat: px, xt = O[k], T[k]; break
                        if (L[k] <= st) if d == 1 else (H[k] >= st): px, xt = (min(O[k], st) if d == 1 else max(O[k], st)), T[k]; break
                        if tgp is not None and ((H[k] >= tgp) if d == 1 else (L[k] <= tgp)): px, xt = (max(O[k], tgp) if d == 1 else min(O[k], tgp)), T[k]; break
                        k += 1
                    if px is None: break
                    out.append((T[j], xt, e, st, px)); traded = day[i]; i = k + 1
                if len(out) < 100: continue
                R = np.array([(px - e) / abs(e - st) * np.sign(e - st) for et, xt, e, st, px in out]); cst = np.array([cost * e / abs(e - st) for et, xt, e, st, px in out])
                t = pd.DatetimeIndex([x[0] for x in out]); A = t < pd.Timestamp("2021-07-01", tz="UTC")
                ya = (t[A][-1] - t[A][0]).days / 365.25; yb = (t[~A][-1] - t[~A][0]).days / 365.25
                rows.append(dict(setup=f"{nm} ORB60 trend{trend} stop-{stop} target{tg}", trades_mo=len(R) / ((t[-1] - t[0]).days / 30.4), win=100 * ((R - cst) > 0).mean(),
                                 avgR=(R - cst).mean(), yr_2016_21=(R - cst)[A].sum() / ya, yr_2021_26=(R - cst)[~A].sum() / yb, yr_2021_26_cost2=(R - 2 * cst)[~A].sum() / yb))
df = pd.DataFrame(rows); df["minhalf"] = df[["yr_2016_21", "yr_2021_26"]].min(axis=1); pd.set_option("display.width", 250)
print(f"{len(df)} versions; >=10%/yr both halves: {(df.minhalf >= 10).sum()}; positive both: {(df.minhalf > 0).sum()}")
print(df.sort_values("minhalf", ascending=False).head(15).round(2).to_string(index=False))
df.to_pickle("hourly_orb.pkl")
