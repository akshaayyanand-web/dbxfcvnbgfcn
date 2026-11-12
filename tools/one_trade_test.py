# One trade per phase at 4.5% risk on BTC / SOL dip entries: odds of +2.2R / +1.1R before the stop.
import numpy as np, pandas as pd, glob
def h1(sym):
    p = []
    for f in sorted(glob.glob(f"k5full/{sym}-5m-*.csv")):
        d = pd.read_csv(f, header=None, usecols=[0, 2, 3, 4], names=["t", "h", "l", "c"]); d["t"] = np.where(d.t > 1e14, d.t // 1000, d.t); p.append(d)
    s = pd.concat(p); s.index = pd.to_datetime(s.t, unit="ms", utc=True); s = s[~s.index.duplicated()].sort_index()
    return s.resample("1h").agg(dict(h="max", l="min", c="last")).dropna()
SETS = {"SOL Dip 1h (best add-on)": ("SOLUSDT", "world_SOLUSDT.pkl", "SOL 1h dip RSI2<15 EMA200 hold144", 0.0015),
        "BTC Dip 1h": ("BTCUSDT", "world_BTCUSDT.pkl", None, 0.0006)}
rows = []
for lab, (sym, pk, nm, cost) in SETS.items():
    df, TR = pd.read_pickle(pk)
    if nm is None: nm = df[df.edge.str.contains("dip")].sort_values("minhalf", ascending=False).edge.iloc[0]
    bars = h1(sym); H, L, T = bars.h.to_numpy(), bars.l.to_numpy(), bars.index
    for tp_R in (1.1, 2.2):     # phase 2 needs +5% with a 4.5% stop = 1.1R; phase 1 needs +10% = 2.2R
        res = []
        for et, xt, e, st, px in TR[nm]:
            R = e - st; tp = e + tp_R * R + cost * e; k = T.searchsorted(et); out = "open"
            for j in range(k, min(k + 24 * 30, len(T))):
                if L[j] <= st: out = "loss"; break
                if H[j] >= tp: out = "win"; break
            res.append(out)
        r = pd.Series(res)
        rows.append(dict(strategy=f"{lab} [{nm}]", target=f"+{tp_R}R ({'+5% phase 2' if tp_R == 1.1 else '+10% phase 1'})", entries=len(r),
                         win=round(100 * (r == "win").mean(), 1), loss=round(100 * (r == "loss").mean(), 1), undecided_30d=round(100 * (r == "open").mean(), 1)))
pd.set_option("display.width", 250); print(pd.DataFrame(rows).to_string(index=False))
