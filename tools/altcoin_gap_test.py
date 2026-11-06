# Run from the scratchpad.
import numpy as np, pandas as pd
L = {}; exec(open('crypto_time_lab.py').read().split("rows = []")[0], L)
rows = []; yearly = {}
for sym in ("BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "LINK", "LTC"):
    try: d = L["load"](sym)
    except Exception as e: print(sym, "no data", e); continue
    a = L["atr"](d).shift(1); ct = d.index.tz_convert("America/Chicago")
    fri = d.index[(ct.weekday == 4) & (ct.hour == 16)]; sun = d.index[(ct.weekday == 6) & (ct.hour == 17)]
    pairs = [(f, s) for f in fri for s in sun[(sun > f) & (sun < f + pd.Timedelta("3D"))][:1]]
    for thr in (0.02, 0.03, 0.05):
        tr = []
        for f, s in pairs:
            pf = d.c.asof(f - pd.Timedelta("1min")); ps = d.o.get(s, np.nan)
            if not (np.isfinite(ps) and np.isfinite(pf)) or abs(ps / pf - 1) < thr: continue
            dr = 1 if ps > pf else -1; x = L["trade"](d, s, s + pd.Timedelta("48h"), dr, ps - dr * 1.5 * a.asof(s))
            if x: tr.append(x)
        if len(tr) < 20: continue
        st = L["stats"](tr, f"{sym} weekend-gap follow >{thr:.0%}"); rows.append(st)
        r = pd.Series([(px - e) / abs(e - s_) * np.sign(e - s_) - L["COST"] * e / abs(e - s_) for et, xt, e, s_, px in tr], index=[t[0] for t in tr])
        yearly[st["edge"]] = r.groupby(r.index.year).sum().round(1)
df = pd.DataFrame(rows); df["minhalf"] = df[["yrA", "yrB"]].min(axis=1); pd.set_option("display.width", 250)
print(df.sort_values("minhalf", ascending=False).round(2).to_string(index=False))
print("\nR per year (sum of R at 1% risk = %/yr):"); print(pd.DataFrame(yearly).T.fillna(0).to_string())
