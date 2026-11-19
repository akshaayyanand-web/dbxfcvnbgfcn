# The book's SOL_Dip rule, unchanged, on other FTMO-listed coins (1h Binance data). Pre-registered: one rule, no tuning.
# Rule: RSI(2) < 15, close > EMA200, 30-day return > -8%  -> buy next bar open; stop = close - 2*ATR14; exit after 144 bars or stop.
import pickle, numpy as np, pandas as pd, sys
sys.path.insert(0, "/home/user/dbxfcvnbgfcn/tools")
from portfolio_prop import rsi
exec(open("newlab.py").read().split('if __name__ == "__main__":')[0])
COST = {"ETH": 0.001, "BNB": 0.002, "XRP": 0.002, "ADA": 0.0025, "DOGE": 0.0025, "LTC": 0.002, "LINK": 0.0025, "AVAX": 0.0025, "DOT": 0.0025, "BCH": 0.0025, "TRX": 0.003, "SOL": 0.0015, "BTC": 0.0006}
def atr14(b):
    pc = b.c.shift(1); tr = pd.concat([b.h - b.l, (b.h - pc).abs(), (b.l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / 14, adjust=False).mean().to_numpy()
def dip_trades(sym, buy=15, en=200, hold=144):
    b = load_crypto(sym); O, H, L, C = (b[k].to_numpy(float) for k in "ohlc"); T = b.index; cost = COST[sym]
    r_ = rsi(b.c, 2).to_numpy(); e_ = b.c.ewm(span=en, adjust=False).mean().to_numpy(); atr = atr14(b)
    dc = b.c.resample("1D").last().dropna(); crash = (dc / dc.shift(30) - 1).shift(1).reindex(T.floor("D"), method="ffill").to_numpy()
    out, i = [], 0
    while i < len(C) - 2:
        if not (r_[i] < buy and C[i] > e_[i] and np.isfinite(atr[i]) and (crash[i] > -0.08 if np.isfinite(crash[i]) else True)): i += 1; continue
        j = i + 1; e = O[j]; st = C[i] - 2 * atr[i]; risk = e - st
        if risk <= 0: i += 1; continue
        k, px, prev, path = j, None, e, []
        while k < len(C) - 1:
            if L[k] <= st:
                px = min(O[k], st); path.append((T[k], (px - prev) / risk, min(0.0, (px - prev) / risk))); xt = T[k] + pd.Timedelta("1h"); break
            path.append((T[k], (C[k] - prev) / risk, min(0.0, (L[k] - prev) / risk))); prev = C[k]
            if k - j + 1 >= hold: px = C[k]; xt = T[k] + pd.Timedelta("1h"); break
            k += 1
        if px is None: break
        c_r = cost * e / risk; path[0] = (path[0][0], path[0][1] - c_r, path[0][2] - c_r)
        out.append((T[j], xt, (px - e) / risk - c_r, path)); i = k + 1
    return out
if __name__ == "__main__":
    S = pd.Timestamp("2023-01-01", tz="UTC"); rows, TR = [], {}
    for sym in ("SOL", "ETH", "BNB", "XRP", "ADA", "DOGE", "LTC", "LINK", "AVAX", "DOT", "BCH", "TRX"):
        trs = dip_trades(sym); TR[sym] = trs; st = stats([(a, b, r) for a, b, r, _ in trs], S)
        # daily P&L correlation with SOL version
        rows.append(dict(coin=sym, cost_pct=100 * COST[sym], **st)); print(rows[-1], flush=True)
    D = {k: pd.Series({x[1].normalize(): 0 for x in v}) for k, v in TR.items()}
    dd = pd.DataFrame({k: pd.Series([x[2] for x in v], index=pd.DatetimeIndex([x[1] for x in v]).normalize()).groupby(level=0).sum() for k, v in TR.items()}).fillna(0)
    R = pd.DataFrame(rows); R["corr_with_SOL"] = [round(dd[c].corr(dd["SOL"]), 2) for c in R.coin]
    pd.set_option("display.width", 250); print(R.to_string()); R.to_csv("altdip_results.csv", index=False)
    pickle.dump(TR, open("altdip_trades.pkl", "wb"))
