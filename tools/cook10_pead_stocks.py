# Post-earnings drift on 40 US large caps (Polygon daily, Nov 2024 - Nov 2026). Events detected from price/volume (no earnings calendar on this plan).
import json, glob, os, sys, numpy as np, pandas as pd
RAW = sys.argv[1]; rows = []; TR = []
for f in sorted(glob.glob(f"{RAW}/*.json")):
    t = os.path.basename(f)[:-5]
    if t == "t": continue
    r = json.load(open(f)).get("results") or []
    if len(r) < 200: continue
    d = pd.DataFrame(r); d.index = pd.to_datetime(d.t, unit="ms"); d = d.rename(columns={"o": "o", "h": "h", "l": "l", "c": "c", "v": "v"})
    O, H, L, C, V = (d[k].to_numpy(float) for k in "ohlcv"); n = len(d)
    tr = np.maximum(H[1:] - L[1:], np.maximum(abs(H[1:] - C[:-1]), abs(L[1:] - C[:-1]))); atr = np.r_[np.nan, pd.Series(tr).rolling(20).mean().to_numpy()]
    avgv = pd.Series(V).rolling(50).mean().shift(1).to_numpy(); busy = -1
    for i in range(51, n - 22):
        gap = O[i] / C[i - 1] - 1
        if abs(gap) < 0.03 or not V[i] > 3 * avgv[i] or i <= busy: continue
        ear = C[i] / C[i - 1] - 1; dr = int(np.sign(ear))
        if dr == 0 or not np.isfinite(atr[i]): continue
        e = O[i + 1]; st = e - dr * 2.5 * atr[i]; x = None; j = i + 1
        for j in range(i + 1, i + 21):
            if (dr > 0 and L[j] <= st) or (dr < 0 and H[j] >= st): x = st if (O[j] - st) * dr > 0 else O[j]; break
        if x is None: x = C[i + 20]; j = i + 20
        days = (d.index[j] - d.index[i + 1]).days; fin = (0.06 if dr > 0 else 0.03) * days / 365
        ret = dr * (x / e - 1) - 0.001 - fin; R = ret / (2.5 * atr[i] / e)
        TR.append(dict(ticker=t, date=d.index[i], ear=ear, dir=dr, ret=ret, R=R)); busy = i + 20
E = pd.DataFrame(TR); split = pd.Timestamp("2025-11-20")
def st(x):
    if len(x) < 10: return dict(n=len(x))
    a, b = x[x.date < split], x[x.date >= split]
    t_ = lambda v: round(v.mean() / v.std(ddof=1) * np.sqrt(len(v)), 2) if len(v) > 2 else np.nan
    return dict(n=len(x), win=round(100 * (x.ret > 0).mean()), avg_ret_pct=round(100 * x.ret.mean(), 2), avg_R=round(x.R.mean(), 3), t_all=t_(x.ret), n_yr1=len(a), t_yr1=t_(a.ret), n_yr2=len(b), t_yr2=t_(b.ret),
                longs=int((x.dir > 0).sum()), avg_long_pct=round(100 * x[x.dir > 0].ret.mean(), 2), avg_short_pct=round(100 * x[x.dir < 0].ret.mean(), 2))
pd.set_option("display.width", 250)
out = pd.DataFrame([dict(variant="P1 follow every earnings move", **st(E)), dict(variant="P2 follow only moves > 5%", **st(E[E.ear.abs() > 0.05]))])
print(out.to_string()); print("\nevents per ticker (median):", E.groupby("ticker").size().median())
E.to_csv("pead_trades.csv", index=False); out.to_csv("pead_results.csv", index=False)
