# Silver round (Dukascopy hourly XAGUSD 2016-2026, cost 0.08% round trip). Pre-registered: A1 book dip rule, A3 Asia-range breakout at London,
# A4 gold/silver ratio z>2 -> silver catch-up (10 days, silver only).
import sys, numpy as np, pandas as pd
sys.path.insert(0, "/home/user/dbxfcvnbgfcn/tools")
from portfolio_prop import rsi
exec(open("newlab.py").read().split('\nif __name__ == "__main__":')[0])
CS = 0.0008; X = load_duka("XAGUSD"); G = load_duka("XAUUSD"); M = Mkt("XAG", X, CS)
def atr14(b):
    pc = b.c.shift(1); tr = pd.concat([b.h - b.l, (b.h - pc).abs(), (b.l - pc).abs()], axis=1).max(axis=1); return tr.ewm(alpha=1 / 14, adjust=False).mean().to_numpy()
def a1(hold=96):
    b = X; O, H, L, C = (b[k].to_numpy(float) for k in "ohlc"); T = b.index
    r_ = rsi(b.c, 2).to_numpy(); e_ = b.c.ewm(span=200, adjust=False).mean().to_numpy(); atr = atr14(b)
    dc = b.c.resample("1D").last().dropna(); crash = (dc / dc.shift(30) - 1).shift(1).reindex(T.floor("D"), method="ffill").to_numpy()
    out, i = [], 200
    while i < len(C) - 2:
        if not (r_[i] < 15 and C[i] > e_[i] and np.isfinite(atr[i]) and (crash[i] > -0.08 if np.isfinite(crash[i]) else True)): i += 1; continue
        j = i + 1; e = O[j]; st = C[i] - 2 * atr[i]; risk = e - st
        if risk <= 0: i += 1; continue
        k, x = j, None
        while k < len(C) - 1:
            if L[k] <= st: x = min(O[k], st); break
            if k - j + 1 >= hold: x = O[k + 1]; break
            k += 1
        if x is None: break
        out.append((T[j], T[k], (x - e) / risk - CS * e / risk)); i = k + 1
    return out
def a3():
    out = []; L_ = M.ldn; H_ = L_.hour; D_ = np.array(L_.date)
    for dte in sorted(set(D_)):
        if pd.Timestamp(dte).weekday() >= 5: continue
        ix = np.flatnonzero(D_ == dte); hh = H_[ix]
        rng = ix[hh < 7]; win = ix[(hh >= 7) & (hh < 12)]; fl = ix[hh == 17]
        if len(rng) < 5 or not len(win) or not len(fl): continue
        hi, lo = M.h[rng].max(), M.l[rng].min(); mid = (hi + lo) / 2
        for k in win:
            d = 1 if M.c[k] > hi else (-1 if M.c[k] < lo else 0)
            if not d or k + 1 >= fl[0]: continue
            e = M.o[k + 1]; risk = abs(e - mid)
            if risk <= 0 or (e - mid) * d <= 0: break
            x = None
            for q in range(k + 1, fl[0]):
                if (d > 0 and M.l[q] <= mid) or (d < 0 and M.h[q] >= mid): x = mid; break
            x = M.o[fl[0]] if x is None else x
            out.append((M.t[k + 1], M.t[min(q, fl[0])], d * (x - e) / risk - CS * e / risk)); break
    return out
def a4():
    g = G.c[G.index.hour == 20]; s = X.c[X.index.hour == 20]; g.index = g.index.normalize(); s.index = s.index.normalize()
    j = pd.concat([g, s], axis=1, keys=["g", "s"]).dropna(); ratio = np.log(j.g / j.s); z = ((ratio - ratio.rolling(60).mean()) / ratio.rolling(60).std()).shift(1)
    out, busy = [], None
    for dte, v in z.dropna().items():
        if abs(v) <= 2 or (busy is not None and dte <= busy): continue
        i = M.t.searchsorted(dte + pd.Timedelta(hours=21)); jx = M.t.searchsorted(dte + pd.Timedelta(days=14, hours=21))
        if jx >= len(M.t): continue
        tr = trade(M, i, jx, int(np.sign(v)))          # ratio high = silver cheap -> long silver
        if tr: out.append(tr[:3]); busy = dte + pd.Timedelta(days=14)
    return out
if __name__ == "__main__":
    S = pd.Timestamp("2022-01-01", tz="UTC"); rows = []
    for nm, fn in (("A1 silver dip (book rule, hold 96h)", a1), ("A3 silver Asia-range breakout at London", a3), ("A4 gold/silver ratio |z|>2 -> silver catch-up 10d", a4)):
        trs = fn(); rows.append(dict(test=nm, **stats(trs, S)))
        r = pd.Series([x[2] for x in trs], index=pd.DatetimeIndex([x[0] for x in trs])).sort_index(); rows[-1]["R_by_year"] = r.groupby(r.index.year).sum().round(1).to_dict()
        print(rows[-1], flush=True)
    pd.set_option("display.width", 300); pd.set_option("display.max_colwidth", 200); R = pd.DataFrame(rows); print(R.drop(columns="R_by_year").to_string()); R.to_csv("silverlab_results.csv", index=False)
    for r in rows: print(r["test"], "R by year:", r["R_by_year"])
