import sys, numpy as np, pandas as pd
SP = sys.argv[1]
exec(open(SP + "/losers.py").read().split("FEATS = [")[0])
lab = {"btc": "BTC_Dip_v3", "gdip": "Gold_Dip", "gasia": "Gold_Asia_Breakout", "gmom": "Gold_Intraday_Momentum", "nqmom": "NQ_Intraday_Momentum",
       "orb15": "NQ_Opening_Range", "nqdip": "NQ_Dip_Grid", "spxdip": "SPX_Dip_Grid"}
rows = []
for k in USED:
    i = names.index(k); w = W[i]; r = R[i] * w; T = trade_table(k)
    eq = np.cumsum(r); y = pd.Series(r, idx).resample("YS").sum() * 100
    rows.append(dict(EA=lab[k], risk=w, trades_per_month=len(T) / ((idx[-1] - idx[0]).days / 30.44), win_rate=100 * (T.R > 0).mean(), avg_R=T.R.mean(),
                     per_year=100 * r.sum() / ((idx[-1] - idx[0]).days / 365.25), max_dd=100 * np.max(np.maximum.accumulate(eq) - eq), **{str(a.year): b for a, b in y.items()}))
pd.set_option("display.width", 250); print(pd.DataFrame(rows).round(2).to_string(index=False))
