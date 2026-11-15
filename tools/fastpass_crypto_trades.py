exec(open("crypto_revert.py").read().split("CASES = [")[0])
import pandas as pd
sol = run("SOLUSDT", "ret", 5, 0.98, 12, "with", 0.0015, None)          # fade 25-min top-2% move, 60-min hold, 0.15% cost
btc = run("BTCUSDT", "ema", 0, 0.995, 12, "with", 0.0006, None)         # fade top-0.5% stretch from EMA200, 60-min hold
out = {"solrev": [(t, t + pd.Timedelta(minutes=65), r) for t, r in zip(sol.t, sol.R)], "btcrev": [(t, t + pd.Timedelta(minutes=65), r) for t, r in zip(btc.t, btc.R)]}
for k, v in out.items(): print(k, len(v), "trades, total R", round(sum(x[2] for x in v), 1))
pd.to_pickle(out, "crypto_trades.pkl")
