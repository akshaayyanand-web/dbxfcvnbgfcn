import sys, os, json, datetime as dt, math, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import independent.vcb as V
cash = V.load_cash(); S0 = (dt.date(2021, 1, 1) - dt.date(1970, 1, 1)).days
src = {"Binance spot (13)": V.load_binance_spot(), "Coinbase USD (11)": V.load_coinbase(), "Bitstamp USD (11)": V.load_bitstamp(), "Binance USD-M perps, price only (13)": V.load_binance_perp()}
CB11 = ["BTC", "ETH", "ADA", "AVAX", "BCH", "DOGE", "DOT", "LINK", "LTC", "SOL", "XRP"]
out = {}
def run(px, **k):
    d, p, W, t, c = V.backtest(px, cash, start_day=S0, end_day=(dt.date(2026, 10, 29) - dt.date(1970, 1, 1)).days, **k); return pd.Series(p, index=pd.to_datetime([dt.date(1970, 1, 1) + dt.timedelta(days=int(x)) for x in d])), t
print("== data source / instrument (same rule, 6 bp)"); out["sources"] = {}
base = {}
for name, px in src.items():
    p, t = run(px); base[name] = p; out["sources"][name] = V.stats(p.values); print(f"  {name:38s}", out["sources"][name], "turnover/yr", round(t.sum() / (len(t) / 365), 1))
p11, _ = run(src["Binance spot (13)"], coins=CB11); out["sources"]["Binance spot, same 11 coins as Coinbase"] = V.stats(p11.values); print("  Binance spot (same 11 coins)          ", out["sources"]["Binance spot, same 11 coins as Coinbase"])
c = pd.concat([base["Binance spot (13)"], base["Coinbase USD (11)"], p11], axis=1).dropna().corr().round(3); print("  P&L corr Binance13 / Coinbase11 / Binance11:\n", c.values)
print("== costs per side (Binance spot)"); out["costs"] = {}
for cb in (0, 6, 15, 30, 50):
    p, _ = run(src["Binance spot (13)"], cost_bp=cb); out["costs"][cb] = V.stats(p.values); print("  ", cb, "bp", out["costs"][cb])
p, _ = run(src["Binance spot (13)"], extra_slip_bp=20); out["costs"]["6bp + 20bp extra slippage"] = V.stats(p.values); print("   6 bp + 20 bp slippage", out["costs"]["6bp + 20bp extra slippage"])
print("== parameter neighbourhood (Binance spot)"); grid = []
for N in (10, 15, 20, 30):
    for H in (3, 5, 10, 20):
        for pc in (0.1, 0.2, 0.3):
            p, _ = run(src["Binance spot (13)"], N=N, H=H, pct=pc); s = V.stats(p.values); grid.append(dict(N=N, H=H, pct=pc, **s))
G = pd.DataFrame(grid); out["grid"] = G.to_dict("records")
print("  combos:", len(G), "| share with Sharpe > 0:", round((G.sharpe > 0).mean(), 2), "| median Sharpe", round(G.sharpe.median(), 2), "| best", G.sharpe.max(), "| worst", G.sharpe.min())
print(G.pivot_table(index=["N"], columns="H", values="sharpe", aggfunc="median").round(2))
print("== direction / liquidity"); out["variants"] = {}
for name, kw in {"long only": dict(long_only=True), "majors BTC ETH SOL XRP BNB": dict(coins=["BTC", "ETH", "SOL", "XRP", "BNB"]), "alts ex-majors": dict(coins=["ADA", "AVAX", "BCH", "DOGE", "DOT", "LINK", "LTC", "TRX"])}.items():
    p, _ = run(src["Binance spot (13)"], **kw); out["variants"][name] = V.stats(p.values); print("  ", name, out["variants"][name])
print("== regimes (Binance spot base)"); pb = base["Binance spot (13)"]
btc = pd.Series(src["Binance spot (13)"]["BTC"]); btc.index = pd.to_datetime([dt.date(1970, 1, 1) + dt.timedelta(days=int(x)) for x in btc.index]); btc = btc.sort_index()
v = btc.pct_change().rolling(30).std().shift(1).reindex(pb.index); tr = (btc > btc.rolling(200).mean()).shift(1).reindex(pb.index)
out["regimes"] = {"BTC vol high": V.stats(pb[v > v.median()].values), "BTC vol low": V.stats(pb[v <= v.median()].values), "BTC uptrend": V.stats(pb[tr == True].values), "BTC downtrend": V.stats(pb[tr == False].values)}
for k, s in out["regimes"].items(): print("  ", k, s)
out["years"] = {str(y): V.stats(pb[pb.index.year == y].values) for y in sorted(set(pb.index.year))}
print("== by year", {y: s["sharpe"] for y, s in out["years"].items()})
rng = np.random.default_rng(1); x = pb.values; n = len(x); bs = []
for _ in range(3000):
    i = rng.integers(n); path = []
    while len(path) < n:
        path.append(x[i]); i = (i + 1) % n if rng.random() > 1 / 20 else rng.integers(n)
    q = np.array(path); bs.append(q.mean() / q.std() * math.sqrt(365))
out["bootstrap_sharpe_ci"] = [round(float(np.percentile(bs, 2.5)), 2), round(float(np.percentile(bs, 97.5)), 2)]; print("== block-bootstrap 95% CI of Sharpe:", out["bootstrap_sharpe_ci"], "| P(Sharpe<=0):", round(float(np.mean(np.array(bs) <= 0)), 3))
json.dump(out, open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results", "strat0053_deep_dive.json"), "w"), indent=1, default=str)
