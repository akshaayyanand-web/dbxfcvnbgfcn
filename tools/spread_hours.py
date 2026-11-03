import sys, numpy as np, pandas as pd
SP = sys.argv[1]
exec(open(SP + "/losers.py").read().split("FEATS = [")[0])
lab = {"btc": "BTC_Dip_v3", "gdip": "Gold_Dip", "gasia": "Gold_Asia_Breakout", "gmom": "Gold_Intraday_Momentum", "nqmom": "NQ_Intraday_Momentum",
       "orb15": "NQ_Opening_Range", "nqdip": "NQ_Dip_Grid", "spxdip": "SPX_Dip_Grid"}
rows = []
for k in USED:
    T = trade_table(k); h = pd.DatetimeIndex(T.t).tz_convert("America/New_York"); mins = h.hour * 60 + h.minute
    roll = (mins >= 17 * 60) & (mins < 19 * 60)                      # rollover / reopen window 17:00-19:00 NY
    wkend = pd.DatetimeIndex(T.t).dayofweek >= 5                    # weekend (only BTC trades then)
    risky = roll | wkend
    w = W[names.index(k)]
    rows.append(dict(EA=lab[k], trades=len(T), in_rollover_17_19NY=int(roll.sum()), on_weekend=int(wkend.sum()),
                     share=100 * risky.mean(), avgR_those=T.R[risky].mean() if risky.any() else np.nan, avgR_rest=T.R[~risky].mean(),
                     pct_per_year_from_those=100 * w / 100 * T.R[risky].sum() / ((idx[-1] - idx[0]).days / 365.25) * 100))
pd.set_option("display.width", 250); print(pd.DataFrame(rows).round(2).to_string(index=False))
