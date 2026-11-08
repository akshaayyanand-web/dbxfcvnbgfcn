# Run from the scratchpad (needs Binance funding files in funding/, ea_trades.pkl).
import glob, numpy as np, pandas as pd
fr = pd.concat([pd.read_csv(f) for f in sorted(glob.glob("funding/*.csv"))])
fr["t"] = pd.to_datetime(np.where(fr.calc_time > 1e14, fr.calc_time // 1000, fr.calc_time), unit="ms", utc=True)
fr = fr.drop_duplicates("t").set_index("t").sort_index().last_funding_rate
f3 = fr.rolling(3).mean()            # average of the last 3 funding prints (~24h), known at each print
TRL = pd.read_pickle("ea_trades.pkl"); tr, cost, risk = TRL["BTC_Dip_v3"]
rows = []
for et, xt, e, st, px in tr:
    R = (px - e) / abs(e - st) - cost * e / abs(e - st)
    rows.append(dict(t=et, R=R, fund=f3.asof(et - pd.Timedelta("1min"))))
df = pd.DataFrame(rows).dropna(); df["half"] = np.where(df.t < pd.Timestamp("2023-01-01", tz="UTC"), "2020-22", "2023-26")
q = df.fund.quantile([0.2, 0.4, 0.6, 0.8]).values
df["bucket"] = pd.cut(df.fund, [-1, *q, 1], labels=["lowest 20%", "20-40%", "40-60%", "60-80%", "highest 20%"])
print("BTC_Dip_v3 trades by 24h funding at entry (avg R):")
print(df.pivot_table(index="bucket", columns="half", values="R", aggfunc=["mean", "count"], observed=True).round(2).to_string())
# standalone: buy BTC after 24h funding < threshold, hold 48/96h, 2 ATR stop
L = {}; exec(open('crypto_time_lab.py').read().split("rows = []")[0], L)
d = L["load"]("BTC"); a = L["atr"](d).shift(1); out = []
for thr in (-0.0001, -0.00005, 0.0):
    for hold in ("48h", "96h"):
        trs = []; last = None
        for t, v in f3[f3 < thr].items():
            if last is not None and t < last: continue
            ent = d.index[d.index.searchsorted(t)] if d.index.searchsorted(t) < len(d) else None
            if ent is None or not np.isfinite(a.asof(ent)): continue
            x = L["trade"](d, ent, ent + pd.Timedelta(hold), 1, d.o[ent] - 2 * a.asof(ent))
            if x: trs.append(x); last = x[1]
        if len(trs) > 10:
            s = L["stats"](trs, f"buy BTC when 24h funding < {thr:.5f}, hold {hold}"); out.append(s)
pd.set_option("display.width", 220); print("\nstandalone:"); print(pd.DataFrame(out).round(2).to_string(index=False))
