import sys, os, datetime as dt, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import independent.vcb as V
from engine import universe, size, run, metrics
from strategies.lib import c_squeeze
cash = V.load_cash(); bn = V.load_binance_spot()
def day(s): return (dt.date.fromisoformat(s) - dt.date(1970, 1, 1)).days
# engine (fixed) on the same 13-coin Binance universe, selected params
R, cost, ann = universe("crypto"); w = size(c_squeeze(R, N=20, H=5, pct=0.2), R, ann); pe, _, _ = run(w, R, cost, ann)
pe.index = pe.index.tz_localize(None)
days, pi, W, turn, coins = V.backtest(bn, cash, start_day=day("2021-01-01"))
pi = pd.Series(pi, index=pd.to_datetime([dt.date(1970, 1, 1) + dt.timedelta(days=int(d)) for d in days]))
j = pd.concat([pe.rename("engine"), pi.rename("independent")], axis=1).loc["2021-01-01":"2026-10-29"].dropna()
print("daily P&L correlation engine vs independent (Binance):", round(j.corr().iloc[0, 1], 3))
for k in j: print(k, V.stats(j[k].values))
for per in ("2021-01-01:2023-12-31", "2024-01-01:2026-10-29"):
    a, b = per.split(":"); print(per, {k: V.stats(j[k].loc[a:b].values) for k in j})
