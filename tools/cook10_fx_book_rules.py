# The book's own rule families, unchanged in form, on 9 FX majors/crosses (HistData 1m). Pre-registered 4 rules x 9 pairs,
# judged POOLED per rule (one test per rule), then per pair for information only.
import sys, pickle, numpy as np, pandas as pd
sys.path.insert(0, "/home/user/dbxfcvnbgfcn/tools")
from portfolio_prop import rsi
exec(open("fxlab.py").read().split('\nif __name__ == "__main__":')[0])
PAIRS = ["USDJPY", "GBPUSD", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURJPY", "GBPJPY", "EURGBP"]
def bars(m, rule):
    d = pd.DataFrame({"o": m.o, "h": m.h, "l": m.l, "c": m.c}, index=m.t)
    return d.resample(rule).agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()
def atr14(b):
    pc = b.c.shift(1); tr = pd.concat([b.h - b.l, (b.h - pc).abs(), (b.l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / 14, adjust=False).mean().to_numpy()
def R(e, st, x, d, cost): rk = abs(e - st); return d * (x - e) / rk - cost * e / rk
def d1_dip(b, cost, hold):
    O, H, L, C, T = b.o.to_numpy(), b.h.to_numpy(), b.l.to_numpy(), b.c.to_numpy(), b.index
    r2 = rsi(b.c, 2).to_numpy(); ema = b.c.ewm(span=200, adjust=False).mean().to_numpy(); atr = atr14(b); out = []; i = 200
    while i < len(C) - 2:
        d = 1 if (r2[i] < 15 and C[i] > ema[i]) else (-1 if (r2[i] > 85 and C[i] < ema[i]) else 0)
        if not d or not np.isfinite(atr[i]): i += 1; continue
        j = i + 1; e = O[j]; st = C[i] - d * 2 * atr[i]
        if (e - st) * d <= 0: i += 1; continue
        k, x = j, None
        while k < len(C) - 1:
            if (d > 0 and L[k] <= st) or (d < 0 and H[k] >= st): x = st if (O[k] - st) * d > 0 else O[k]; xt = T[k]; break
            if k - j + 1 >= hold: x = O[k + 1]; xt = T[k + 1]; break
            k += 1
        if x is None: break
        out.append((T[j], xt, R(e, st, x, d, cost), e, st, d)); i = k + 1
    return out
def session_bo(b5, cost, tz, r0, r1, w1, flat, stop_mode):
    loc = b5.index.tz_convert(tz); mins = loc.hour * 60 + loc.minute; day = loc.date
    O, H, L, C, T = b5.o.to_numpy(), b5.h.to_numpy(), b5.l.to_numpy(), b5.c.to_numpy(), b5.index
    df = pd.DataFrame({"day": day, "m": mins}); out = []
    for dte, g in df.groupby("day"):
        ix = g.index.to_numpy()
        if pd.Timestamp(dte).weekday() >= 5: continue
        rng = ix[(g.m.to_numpy() >= r0) & (g.m.to_numpy() < r1)]
        if len(rng) < (r1 - r0) // 5 * 0.8: continue
        hi, lo = H[rng].max(), L[rng].min()
        win = ix[(g.m.to_numpy() >= r1) & (g.m.to_numpy() < w1)]; fl = ix[g.m.to_numpy() >= flat]
        if not len(win) or not len(fl): continue
        for k in win:
            d = 1 if C[k] > hi else (-1 if C[k] < lo else 0)
            if not d or k + 1 >= len(C): continue
            j = k + 1; e = O[j]; st = (lo if d > 0 else hi) if stop_mode == "other" else (hi + lo) / 2
            if (e - st) * d <= 0 or abs(e - st) / e < 0.0005: break
            x = None
            for q in range(j, fl[0]):
                if (d > 0 and L[q] <= st) or (d < 0 and H[q] >= st): x = st if (O[q] - st) * d > 0 else O[q]; xt = T[q]; break
            if x is None: x = O[fl[0]]; xt = T[fl[0]]
            out.append((T[j], xt, R(e, st, x, d, cost), e, st, d)); break
    return out
if __name__ == "__main__":
    S = pd.Timestamp("2023-01-01", tz="UTC"); TR = {}; rows = []
    for p in PAIRS:
        m = FX(p); b1 = bars(m, "1h"); b5 = bars(m, "5min"); c = COST[p]
        TR[(p, "D1 dip 48h")] = d1_dip(b1, c, 48); TR[(p, "D1 dip 144h")] = d1_dip(b1, c, 144)
        TR[(p, "D2 London ORB")] = session_bo(b5, c, "Europe/London", 420, 480, 660, 960, "other")
        TR[(p, "D3 Asia-range breakout")] = session_bo(b5, c, "Europe/London", 0, 420, 720, 1020, "mid")
        for rule in ("D1 dip 48h", "D1 dip 144h", "D2 London ORB", "D3 Asia-range breakout"):
            rows.append(dict(pair=p, rule=rule, **stats([x[:3] for x in TR[(p, rule)]], S)))
        pickle.dump(TR, open("fxbook_trades.pkl", "wb")); print(p, "done", flush=True)
    D = pd.DataFrame(rows); pd.set_option("display.width", 250); pd.set_option("display.max_rows", 100)
    print(D.to_string()); D.to_csv("fxbook_by_pair.csv", index=False)
    P = []
    for rule in ("D1 dip 48h", "D1 dip 144h", "D2 London ORB", "D3 Asia-range breakout"):
        allt = sorted([x[:3] for p in PAIRS for x in TR[(p, rule)]], key=lambda x: x[0])
        P.append(dict(rule=rule, pairs_positive_test=int((D[D.rule == rule].meanR_te > 0).sum()), **stats(allt, S)))
    P = pd.DataFrame(P); print("\nPOOLED over 9 pairs (the actual test):\n" + P.to_string()); P.to_csv("fxbook_pooled.csv", index=False)
