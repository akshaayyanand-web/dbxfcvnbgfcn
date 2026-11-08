# Run from the scratchpad (hourly data in fut/ and kh/).
import sys, numpy as np, pandas as pd
sys.path.insert(0, "/home/user/dbxfcvnbgfcn/tools")
from portfolio_prop import load_csv
L = {}; exec(open('crypto_time_lab.py').read().split("rows = []")[0], L)
MK = {"gold": ("fut/XAUUSD.csv", 0.0001), "nasdaq": ("fut/USATECHIDXUSD.csv", 0.00012), "sp500": ("fut/USA500IDXUSD.csv", 0.0001),
      "dow": ("fut/USA30IDXUSD.csv", 0.0001), "russell": ("fut/USSC2000IDXUSD.csv", 0.00015), "oil": ("fut/LIGHTCMDUSD.csv", 0.0003),
      "silver": ("fut/XAGUSD.csv", 0.00025), "btc": (None, 0.0012)}
rows = []
for nm, (f, cost) in MK.items():
    b = (load_csv(f) if f else L["load"]("BTC")).loc["2016-01-01":]
    T = b.index; ny = T.tz_convert("America/New_York"); wk = (ny - pd.to_timedelta(ny.weekday, unit="D")).normalize()
    dow = ny.weekday.to_numpy(); O, H, Lo, C = (b[k].to_numpy() for k in "ohlc")
    rh = pd.Series(np.where(dow == 0, H, np.nan)).groupby(wk.values).transform("max").to_numpy()
    rl = pd.Series(np.where(dow == 0, Lo, np.nan)).groupby(wk.values).transform("min").to_numpy()
    dc = b.c.resample("1D").last().dropna(); ema = {n: dc.ewm(span=n, adjust=False).mean().shift(1).reindex(T.floor("D"), method="ffill").to_numpy() for n in (20, 50)}
    for trend in (None, 20, 50):
        for stop in ("mid", "other"):
            for tg in (0, 2.0):
                out, i, traded = [], 0, None
                while i < len(C) - 2:
                    if not (1 <= dow[i] <= 3) or traded == wk[i] or not np.isfinite(rh[i]): i += 1; continue
                    d = 1 if C[i] > rh[i] else (-1 if C[i] < rl[i] else 0)
                    if d and trend and (C[i] - ema[trend][i]) * d <= 0: d = 0
                    if d == 0: i += 1; continue
                    j = i + 1; e = O[j]; st = (rh[i] + rl[i]) / 2 if stop == "mid" else (rl[i] if d == 1 else rh[i])
                    if (st - e) * d >= 0: i += 1; continue
                    tgp = e + d * tg * abs(e - st) if tg else None; k = j; px = None
                    while k < len(C):
                        if wk[k] != wk[j] or (dow[k] == 4 and ny[k].hour >= 15) or dow[k] >= 5: px, xt = O[k], T[k]; break
                        if (Lo[k] <= st) if d == 1 else (H[k] >= st): px, xt = (min(O[k], st) if d == 1 else max(O[k], st)), T[k]; break
                        if tgp is not None and ((H[k] >= tgp) if d == 1 else (Lo[k] <= tgp)): px, xt = (max(O[k], tgp) if d == 1 else min(O[k], tgp)), T[k]; break
                        k += 1
                    if px is None: break
                    out.append((T[j], xt, e, st, px)); traded = wk[i]; i = k + 1
                if len(out) < 60: continue
                R = np.array([(px - e) / abs(e - st) * np.sign(e - st) for et, xt, e, st, px in out]); cst = np.array([cost * e / abs(e - st) for et, xt, e, st, px in out])
                t = pd.DatetimeIndex([x[0] for x in out]); A = t < pd.Timestamp("2021-07-01", tz="UTC")
                ya = (t[A][-1] - t[A][0]).days / 365.25; yb = (t[~A][-1] - t[~A][0]).days / 365.25
                rows.append(dict(setup=f"{nm} weekly ORB trend{trend} stop-{stop} target{tg}", trades_mo=len(R) / ((t[-1] - t[0]).days / 30.4), win=100 * ((R - cst) > 0).mean(),
                                 avgR=(R - cst).mean(), yr_early=(R - cst)[A].sum() / ya, yr_late=(R - cst)[~A].sum() / yb, yr_late_cost2=(R - 2 * cst)[~A].sum() / yb))
df = pd.DataFrame(rows); df["minhalf"] = df[["yr_early", "yr_late"]].min(axis=1); pd.set_option("display.width", 250)
print(f"{len(df)} versions; >=10%/yr both halves: {(df.minhalf >= 10).sum()}; positive both: {(df.minhalf > 0).sum()}")
print(df.sort_values("minhalf", ascending=False).head(15).round(2).to_string(index=False)); df.to_pickle("weekly_orb.pkl")
