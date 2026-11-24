# Currency strength / dollar momentum. 8 currencies valued in USD from hourly closes (EURUSD synthetic = EURJPY/USDJPY for full history).
# Pre-registered families:
#  XS  : rank the 8 currencies on their L-day return at 21:00 UTC, long the top k / short the bottom k (equal weights), rebalance every H days.
#        L in {5,20,60,120}, k in {1,3}, H in {1,5}.
#  TS  : dollar basket time-series momentum: sign of the USD basket's L-day return, long/short USD vs the other 7 equally. L in {20,60,120}, H=5.
#  MTR : intraday "strength meter": rank on 07-12 UTC return, long top k / short bottom k from 12:00 to 20:00 UTC, k in {1,3}.
# Costs: each currency traded pays half its USD pair's round-trip spread per side (USD free). Swap markup 2%/yr on gross notional held overnight.
# Interest-rate differential (carry) is NOT modelled: caveat.
import numpy as np, pandas as pd
exec(open("smc.py").read().split("def run_symbol(")[0])
H1 = {s: hd(s).c.resample("1h").last() for s in ("GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF", "USDJPY", "EURJPY")}
X = pd.DataFrame(H1).dropna()
V = pd.DataFrame({"EUR": X.EURJPY / X.USDJPY, "GBP": X.GBPUSD, "AUD": X.AUDUSD, "NZD": X.NZDUSD, "CAD": 1 / X.USDCAD, "CHF": 1 / X.USDCHF, "JPY": 1 / X.USDJPY})
V["USD"] = 1.0; P = np.log(V); CUR = list(P.columns)
COST = pd.Series({"EUR": 0.00008 + 0.00003, "GBP": 0.00009, "AUD": 0.0001, "NZD": 0.00014, "CAD": 0.0001, "CHF": 0.00012, "JPY": 0.00007, "USD": 0.0})
SWAP = 0.02 / 365
S = pd.Timestamp("2023-01-01", tz="UTC")
def stats(r, name):
    r = r.dropna(); r = r[r.index >= pd.Timestamp("2016-06-01", tz="UTC")]
    sh = lambda x: x.mean() / x.std() * np.sqrt(252) if x.std() > 0 else np.nan
    a, b = r[r.index < S], r[r.index >= S]; yrs = r.groupby(r.index.year).sum()
    return dict(cfg=name, sharpe=round(sh(r), 2), sh_pre2023=round(sh(a), 2), t_pre=round(sh(a) * np.sqrt(len(a) / 252), 2), sh_2023on=round(sh(b), 2),
                t_post=round(sh(b) * np.sqrt(len(b) / 252), 2), ann_ret_at_10vol=round(100 * r.mean() * 252 / (r.std() * np.sqrt(252)) * 0.10, 1), pos_years=f"{(yrs > 0).sum()}/{len(yrs)}")
# daily snapshot at 21:00 UTC weekdays
D = P[(P.index.hour == 21) & (P.index.dayofweek < 5)]; DR = D.diff().shift(-1)        # next-day return of each currency vs USD
def run_weights(W, H, name):
    W = W.iloc[::H].reindex(D.index).ffill()                                        # hold H days
    gross = (W * DR).sum(axis=1); turn = (W.diff().abs() * COST / 2).sum(axis=1).fillna(0); swap = W.abs().sum(axis=1) / 2 * SWAP * 1.4
    return stats(gross - turn - swap, name)
rows = []
for L in (5, 20, 60, 120):
    mom = D - D.shift(L); rk = mom.rank(axis=1, ascending=False)
    for k in (1, 3):
        W = (rk <= k).astype(float) / k - (rk > 8 - k).astype(float) / k; W[mom.isna().any(axis=1)] = 0
        for H in (1, 5): rows.append(run_weights(W, H, f"XS L{L} k{k} H{H}"))
usd = -D.drop(columns="USD").mean(axis=1)
for L in (20, 60, 120):
    sg = np.sign(usd - usd.shift(L)).fillna(0)
    W = pd.DataFrame({c: (-sg / 7 if c != "USD" else sg) for c in CUR})              # long USD = short each other currency 1/7
    rows.append(run_weights(W, 5, f"TS USD L{L} H5"))
# intraday strength meter
day = P.index.normalize(); P7, P12, P20 = (P[(P.index.hour == h) & (P.index.dayofweek < 5)] for h in (7, 12, 20))
P7.index, P12.index, P20.index = P7.index.normalize(), P12.index.normalize(), P20.index.normalize()
j = P7.index.intersection(P12.index).intersection(P20.index); sig = P12.loc[j] - P7.loc[j]; ret = P20.loc[j] - P12.loc[j]; rk = sig.rank(axis=1, ascending=False)
for k in (1, 3):
    W = (rk <= k).astype(float) / k - (rk > 8 - k).astype(float) / k
    rows.append(stats((W * ret).sum(axis=1) - (W.abs() * COST).sum(axis=1), f"MTR k{k} 12-20UTC"))
R = pd.DataFrame(rows).set_index("cfg"); pd.set_option("display.width", 200); print(R.to_string())
print("\nconfigs with t>2 in BOTH periods:"); q = R[(R.t_pre > 2) & (R.t_post > 2)]; print(q.to_string() if len(q) else "none")
print(f"\n{len(R)} configs; data {P.index[0].date()} -> {P.index[-1].date()}")
