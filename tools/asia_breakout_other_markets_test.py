# Run from the scratchpad (hourly data in fut/ and kh/).
import sys, numpy as np, pandas as pd
sys.path.insert(0, "/home/user/dbxfcvnbgfcn/tools")
from portfolio_prop import load_csv
import intraday_lab as I
L = {}; exec(open('crypto_time_lab.py').read().split("rows = []")[0], L)
MK = {"gold (current EA)": ("fut/XAUUSD.csv", I.COST["XAUUSD"]), "silver": ("fut/XAGUSD.csv", 0.00025), "nasdaq": ("fut/USATECHIDXUSD.csv", 0.00012),
      "sp500": ("fut/USA500IDXUSD.csv", 0.0001), "dow": ("fut/USA30IDXUSD.csv", 0.0001), "russell": ("fut/USSC2000IDXUSD.csv", 0.00015),
      "oil": ("fut/LIGHTCMDUSD.csv", 0.0003), "btc": (None, 0.0012)}
rows = []
for nm, (f, cost) in MK.items():
    d = (load_csv(f) if f else L["load"]("BTC")).loc["2016-01-01":]
    tr = I.range_breakout(d, "Europe/London", 0, 7, 7, 14, 20, "mid", None, True, cost)
    R = np.array([x[5] if len(x) > 5 else np.nan for x in tr]) if False else None
    out = [x[:5] for x in tr]
    Rr = np.array([(px - e) / abs(e - st) * np.sign(e - st) for et, xt, e, st, px in out]); cst = np.array([cost * e / abs(e - st) for et, xt, e, st, px in out])
    t = pd.DatetimeIndex([x[0] for x in out]); A = t < pd.Timestamp("2021-07-01", tz="UTC")
    ya = (t[A][-1] - t[A][0]).days / 365.25; yb = (t[~A][-1] - t[~A][0]).days / 365.25
    yr = pd.Series(Rr - cst, index=t).groupby(t.year).sum()
    rows.append(dict(market=nm, trades_mo=len(Rr) / ((t[-1] - t[0]).days / 30.4), win=100 * ((Rr - cst) > 0).mean(), avgR=(Rr - cst).mean(),
                     yr_2016_21=(Rr - cst)[A].sum() / ya, yr_2021_26=(Rr - cst)[~A].sum() / yb, yr_2021_26_cost2=(Rr - 2 * cst)[~A].sum() / yb, losing_years=int((yr < 0).sum())))
pd.set_option("display.width", 250); print(pd.DataFrame(rows).round(2).to_string(index=False))
