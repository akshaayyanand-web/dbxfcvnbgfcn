# Position trading on daily closes (21:00 UTC), long/short, decided at the close of day t and held from t to t+1.
# Cost: spread on every change of position (x |change|), swap on every day held (x 1.4 for weekends). Train < 2023, holdout 2023+.
import sys, numpy as np, pandas as pd
src = open("cat2000_daily.py").read(); exec(src.split("TESTS = []")[0])
def backtest(mk, pos):
    r = RET[mk].shift(-1); p = pos.reindex(r.index).fillna(0); ch = p.diff().abs().fillna(p.abs())
    net = (p * r - ch * COST[mk] - p.abs() * SWAP[mk] / 365 * 1.4).dropna(); net = net[net.index >= "2016-06-01"]
    return net
def stats(net, mk, rule, lo):
    bh = RET[mk].shift(-1).reindex(net.index).fillna(0)
    sh = lambda x: x.mean() / x.std() * np.sqrt(252) if x.std() > 0 else np.nan
    A, B = net[net.index < "2023-01-01"], net[net.index >= "2023-01-01"]
    ex = (net - bh) if lo else net; EA, EB = ex[ex.index < "2023-01-01"], ex[ex.index >= "2023-01-01"]
    yrs = net.groupby(net.index.year).sum(); eq = net.cumsum(); dd = (eq - eq.cummax()).min()
    return dict(market=mk, rule=rule, ann_pct=round(100 * net.mean() * 252, 1), sharpe_pre=round(sh(A), 2), sharpe_post=round(sh(B), 2),
                vs_buyhold_pre=round(100 * EA.mean() * 252, 1) if lo else np.nan, vs_buyhold_post=round(100 * EB.mean() * 252, 1) if lo else np.nan,
                pos_years=f"{(yrs > 0).sum()}/{len(yrs)}", maxdd_pct=round(100 * dd, 1), trades_yr=round((net != 0).sum() and (pos_changes[mk, rule] / max(len(net) / 252, 1)), 1))
rows = []; pos_changes = {}
for mk in PX.columns:
    c = PX[mk].dropna(); lc = np.log(c)
    R = {"TSMOM 12-1 (monthly)": np.sign(lc.shift(21) - lc.shift(252)), "TSMOM 3m (monthly)": np.sign(lc - lc.shift(63)),
         "200-day MA long/short": np.sign(c - c.rolling(200).mean()), "Golden cross 50/200": np.sign(c.rolling(50).mean() - c.rolling(200).mean())}
    for k in ("TSMOM 12-1 (monthly)", "TSMOM 3m (monthly)"):
        m = R[k]; R[k] = m.where(pd.Series(np.arange(len(m)) % 21 == 0, m.index)).ffill()
    hi55, lo55, hi20, lo20 = c.rolling(55).max().shift(1), c.rolling(55).min().shift(1), c.rolling(20).max().shift(1), c.rolling(20).min().shift(1); p = 0; tp = []
    for i in range(len(c)):
        x = c.iloc[i]
        if p == 0: p = 1 if x > hi55.iloc[i] else (-1 if x < lo55.iloc[i] else 0)
        elif p > 0 and x < lo20.iloc[i]: p = 0
        elif p < 0 and x > hi20.iloc[i]: p = 0
        tp.append(p)
    R["Turtle 55/20"] = pd.Series(tp, c.index)
    for k, pos in R.items():
        pos = pos.fillna(0); pos_changes[mk, k] = (pos.diff().abs() > 0).sum(); rows.append(stats(backtest(mk, pos), mk, k, False))
    if mk in ("SPX", "NQ", "DOW", "RUT", "DAX", "JPN", "XAU", "XAG", "BTC", "ETH"):
        pos = (c > c.rolling(200).mean()).astype(float); pos_changes[mk, "200-day MA long/flat"] = (pos.diff().abs() > 0).sum()
        rows.append(stats(backtest(mk, pos), mk, "200-day MA long/flat", True))
D = pd.DataFrame(rows); D.to_csv("position.csv", index=False); pd.set_option("display.width", 220); pd.set_option("display.max_rows", 200)
print(D.groupby("rule")[["ann_pct", "sharpe_pre", "sharpe_post"]].median().round(2).to_string())
print("\nboth periods Sharpe > 0.5:"); print(D[(D.sharpe_pre > 0.5) & (D.sharpe_post > 0.5)].sort_values("sharpe_post", ascending=False).to_string(index=False))
