# Gap-filler sleeve: long-only trend on 8 CFDs. Pre-registered single spec (no grid):
# daily at 20:00 UTC: long if close > EMA100(daily) and 60-day return > 0, else flat; size = equal daily vol (1/sigma20);
# costs: entry/exit spread + overnight financing (indices 6%/yr, metals/oil 5%/yr, crypto 20%/yr).
import pickle, numpy as np, pandas as pd
exec(open("newlab.py").read().split('\nif __name__ == "__main__":')[0].split("class Mkt")[0])
SPEC = {"USA500IDXUSD": (0.00015, 0.06), "USATECHIDXUSD": (0.00015, 0.06), "USA30IDXUSD": (0.00015, 0.06), "XAUUSD": (0.00012, 0.05),
        "XAGUSD": (0.0003, 0.05), "LIGHTCMDUSD": (0.0003, 0.05), "BTC": (0.0006, 0.20), "ETH": (0.001, 0.20)}
def daily_close(sym):
    b = load_crypto(sym) if sym in ("BTC", "ETH") else load_duka(sym)
    c = b.c[b.index.hour == 20]; c.index = c.index.normalize(); return c[~c.index.duplicated()]
def sleeve(sym):
    cost, fin = SPEC[sym]; c = daily_close(sym); r = c.pct_change()
    ema = c.ewm(span=100, adjust=False).mean(); sig = ((c > ema) & (c / c.shift(60) > 1)).astype(float)
    vol = r.rolling(20).std(); w = (sig / vol).shift(1)                       # decided yesterday, held today
    w = w.where(np.isfinite(w), 0.0) * 0.01                                  # 1% daily vol per instrument when on
    days = c.index.to_series().diff().dt.days.fillna(1).clip(1, 4)
    pnl = w * r - (w - w.shift(1)).abs().fillna(0) * cost - w * fin / 365 * days
    return pnl.fillna(0), w
if __name__ == "__main__":
    P = {s: sleeve(s) for s in SPEC}
    out = {}
    for s, (pnl, w) in P.items():
        a, b = pnl[:"2021-12-31"], pnl["2022-01-01":]
        if s in ("BTC", "ETH"): a, b = pnl[:"2022-12-31"], pnl["2023-01-01":]
        sh = lambda x: round(x.mean() / x.std() * np.sqrt(252), 2) if x.std() > 0 else np.nan
        out[s] = dict(time_in_market=round((w > 0).mean() * 100), sharpe_train=sh(a), sharpe_test=sh(b), sharpe_all=sh(pnl))
    print(pd.DataFrame(out).T.to_string())
    tot = pd.concat({s: p for s, (p, w) in P.items()}, axis=1).fillna(0).sum(axis=1)
    sh = lambda x: round(x.mean() / x.std() * np.sqrt(252), 2)
    print("sleeve (8 markets) Sharpe 2016-21:", sh(tot[:"2021-12-31"]), " 2022-26:", sh(tot["2022-01-01":]), " all:", sh(tot))
    pickle.dump(P, open("tsmom_sleeve.pkl", "wb"))
