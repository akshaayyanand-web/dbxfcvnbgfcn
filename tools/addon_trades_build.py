# Trade lists for the gold VWAP pullback and S&P open fade add-ons (writes addon_trades.pkl).
# Build trade lists (entry, exit, R) for the gold VWAP pullback and the S&P open fade.
import numpy as np, pandas as pd
exec(open("xau_better.py").read().split("def run(")[0].replace('for tf in ("1min", "5min", "15min")', 'for tf in ("5min",)'))
O, H, L, C, T, vwap, R7, atr, hr = DATA["5min"]
def gold_trades(spread=0.15, am=4):
    n = len(C); pend = 0; pend_t = 0; pend_until = 0; out = []; i = 20
    while i < n - 1:
        if pend == 0 or i > pend_until:
            pend = 0
            if np.isfinite(vwap[i]) and np.isfinite(atr[i]) and atr[i] >= am * spread and 8 <= hr[i] < 21:
                buy = C[i] > vwap[i] and (R7[i] < 35 or (R7[i-1] < 35 and R7[i] > R7[i-1])) and C[i] > O[i]
                sell = C[i] < vwap[i] and (R7[i] > 65 or (R7[i-1] > 65 and R7[i] < R7[i-1])) and C[i] < O[i]
                if buy or sell: pend = 1 if buy else -1; pend_t = C[i] - pend * 2 * atr[i] * 0.9; pend_until = i + 10
            i += 1; continue
        d = pend
        if ((L[i] <= pend_t) if d == 1 else (H[i] >= pend_t)) and ((C[i] > O[i]) if d == 1 else (C[i] < O[i])):
            e = O[i + 1] + d * spread / 2; a = atr[i]; sl = e - d * 2 * a; tp = e + d * 4 * a; R = 2 * a; j = i + 1; px = None
            while j < n:
                if (L[j] <= sl) if d == 1 else (H[j] >= sl): px = sl; break
                if (H[j] >= tp) if d == 1 else (L[j] <= tp): px = tp; break
                best = H[j] if d == 1 else L[j]
                if (best - e) * d >= 0.8 * a:
                    nsl = best - d * 0.5 * a
                    if (nsl - sl) * d > 0: sl = nsl
                j += 1
            if px is None: break
            out.append((T[i + 1], T[j], ((px - e) * d - spread / 2) / R)); pend = 0; i = j + 1; continue
        i += 1
    return out
g = gold_trades(); print("gold trades", len(g), "total R", round(sum(x[2] for x in g), 1))
exec(open("open_fade_risk.py").read().split("a = detail")[0])
a = detail("fut1m/USA500IDXUSD_1m.csv", 0.6, 15, 0.98, 30, True)
s = [(t, t + pd.Timedelta(minutes=31), r) for t, r in zip(a.t, a.R)]
print("S&P fade trades", len(s), "total R", round(a.R.sum(), 1))
pd.to_pickle({"gold": g, "spx_fade": s}, "addon_trades.pkl")
