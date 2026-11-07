# Run from the scratchpad (needs fund_check.py chain).
# Per-EA trade ledger at the preset risk on a $200K account: 2026 gross profit / gross loss / net, and long-run profit factor.
import sys, numpy as np, pandas as pd
exec(open('fund_check.py').read().split("C = [")[0])
import orb_lab as O, intraday_lab as I
L = {}; exec(open('crypto_time_lab.py').read().split("rows = []")[0], L)
TRL = {}
t, c = P.dip_trades(btc, "2h", 3, 20, 0.15, P.FEE_CRYPTO); TRL["BTC_Dip_v3"] = (t, c, 0.75)
t, c = P.dip_trades(gold, "1h", 2, 10, 0.08, P.COST["XAUUSD"]); TRL["Gold_Dip"] = (t, c, 0.625)
ga = I.range_breakout(gold, "Europe/London", 0, 7, 7, 14, 20, "mid", None, True, I.COST["XAUUSD"]); TRL["Gold_Asia_Breakout"] = ([x[:5] for x in ga], I.COST["XAUUSD"], 0.3125)
gm = I.intraday_momentum(gold, "Europe/London", 17, 9, 16, 0.006, True, True, I.COST["XAUUSD"], 1.0); TRL["Gold_Intraday_Momentum"] = ([x[:5] for x in gm], I.COST["XAUUSD"], 0.3125)
nq5 = O.five_min(load_csv("fut1m/USATECHIDXUSD_1m.csv"))
TRL["NQ_Opening_Range"] = ([a[:5] for a in O.orb(nq5, "America/New_York", (9, 30), (11, 30), (15, 55), 15, "other", 2.0, True, O.COST["USATECHIDXUSD"])], O.COST["USATECHIDXUSD"], 0.625)
TRL["NQ_Dip_2h"] = (dipT(nq, "2h", 2, 25, 50, 96, 0.08), 0.00012, 0.3125)
TRL["SPX_Dip_1h"] = (dipT(spx, "1h", 2, 15, 200, 48, 0.08), 0.0001, 0.3125)
TRL["Oil_Dip_1h"] = (dipT(oil, "1h", 2, 25, 50, 144, 0.15), 0.0003, 0.1875)
d = L["load"]("BTC"); a = L["atr"](d).shift(1); ct = d.index.tz_convert("America/Chicago")
fri = d.index[(ct.weekday == 4) & (ct.hour == 16)]; sun = d.index[(ct.weekday == 6) & (ct.hour == 17)]; gt = []
for f in fri:
    s = sun[(sun > f) & (sun < f + pd.Timedelta("3D"))][:1]
    if not len(s): continue
    s = s[0]; pf = d.c.asof(f - pd.Timedelta("1min")); ps = d.o.get(s, np.nan)
    if not (np.isfinite(ps) and np.isfinite(pf)) or abs(ps / pf - 1) < 0.02: continue
    dr = 1 if ps > pf else -1; x = L["trade"](d, s, s + pd.Timedelta("48h"), dr, ps - dr * 1.5 * a.asof(s))
    if x: gt.append(x)
TRL["BTC_Weekend_Gap"] = (gt, P.FEE_CRYPTO, 0.25)
dfd, TRD = pd.read_pickle("dax_lab.pkl"); TRL["DAX_Opening_Range"] = (TRD["DAX 15min ORB30 trend50 target0 stop-mid"], 0.0001, 0.2)
rows = []; ACC = 200000
for nm, (tr, cost, risk) in TRL.items():
    R = pd.Series([(px - e) / abs(e - st) * np.sign(e - st) - cost * e / abs(e - st) for et, xt, e, st, px in tr], index=pd.DatetimeIndex([x[0] for x in tr]))
    usd = R * ACC * risk / 100; y = usd[usd.index.year == 2026]; allp = usd[usd.index >= "2020-01-01"]
    pf_all = allp[allp > 0].sum() / -allp[allp < 0].sum()
    yearly = allp.groupby(allp.index.year).sum()
    rows.append({"EA": nm, "risk %": risk, "2026 trades": len(y), "2026 gross profit $": y[y > 0].sum(), "2026 gross loss $": y[y < 0].sum(), "2026 net $": y.sum(),
                 "2026 PF": y[y > 0].sum() / -y[y < 0].sum(), "2020-26 PF": pf_all, "losing years 2020-26": int((yearly < 0).sum()), "net 2020-26 $/yr": allp.sum() / ((allp.index[-1] - allp.index[0]).days / 365.25)})
df = pd.DataFrame(rows); pd.set_option("display.width", 300)
print(df.round(2).to_string(index=False))
print("\nall 10 together, 2026 net $:", round(df["2026 net $"].sum()), " gross profit $:", round(df["2026 gross profit $"].sum()), " gross loss $:", round(df["2026 gross loss $"].sum()))
pd.to_pickle(TRL, "ea_trades.pkl")
