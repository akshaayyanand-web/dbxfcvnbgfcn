# 3-hurdle grind for any market / timeframe: python scalp_grind_any_test.py NAME SOURCE TZ OPEN_MIN CLOSE_MIN SPREAD(abs, or <0.01 = fraction of price) RULE(1min/5min)
import sys, itertools, numpy as np, pandas as pd
sys.path.insert(0, "/home/user/dbxfcvnbgfcn/tools")
from portfolio_prop import load_csv
import glob
NAME, SRC, TZ, OPEN_, CLOSE_, SP, RULE = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]), float(sys.argv[6]), sys.argv[7]
if SRC.startswith("k5full"):
    p = []
    for f in sorted(glob.glob(SRC)):
        d = pd.read_csv(f, header=None, usecols=[0, 1, 2, 3, 4, 5], names=["t", "o", "h", "l", "c", "v"]); d["t"] = np.where(d.t > 1e14, d.t // 1000, d.t); p.append(d)
    m1 = pd.concat(p); m1.index = pd.to_datetime(m1.t, unit="ms", utc=True); m1 = m1[~m1.index.duplicated()].sort_index().drop(columns="t")
else:
    m1 = load_csv(SRC)
m1 = m1.loc["2020-01-01":]
if RULE != "1min": m1 = m1.resample(RULE).agg(dict(o="first", h="max", l="min", c="last", v="sum")).dropna()
O, H, L, C, V, T = (m1[k].to_numpy() for k in "ohlcv"), None, None, None, None, m1.index
O, H, L, C, V = m1.o.to_numpy(), m1.h.to_numpy(), m1.l.to_numpy(), m1.c.to_numpy(), m1.v.to_numpy()
ny = T.tz_convert(TZ); mins = (ny.hour * 60 + ny.minute).to_numpy(); wd = ny.weekday.to_numpy(); yr = ny.year.to_numpy()
cs = pd.Series(C)
F = {}
for k in (1, 2, 3, 5, 10, 15, 30): F[f"ret{k}m"] = (cs - cs.shift(k)).to_numpy()
F["dist_ema200"] = (cs - cs.ewm(span=200, adjust=False).mean()).to_numpy()
hh, ll = pd.Series(H).rolling(30).max(), pd.Series(L).rolling(30).min()
F["range_pos30"] = ((cs - ll) / (hh - ll)).to_numpy() - 0.5
BPD = max(1, (CLOSE_ - OPEN_) // (1 if RULE == "1min" else 5))
F["vol_z"] = ((pd.Series(V) - pd.Series(V).rolling(BPD).mean()) / pd.Series(V).rolling(BPD).std()).to_numpy() * np.sign(F["ret1m"])
trend = np.sign((cs.ewm(span=800, adjust=False).mean().diff(30)).to_numpy())
atr = pd.Series(H - L).rolling(30).mean(); vreg = (atr > atr.rolling(BPD * 20).median()).to_numpy()
FWD = {h: (np.roll(O, -(1 + h)) - np.roll(O, -1)) for h in (1, 2, 3, 5, 10, 15, 30, 60)}   # enter next open, exit h minutes later
L_ = CLOSE_ - OPEN_
WIN = {"first 30m": (OPEN_, OPEN_ + 30), "30m-2h": (OPEN_ + 30, OPEN_ + 120), "2h-4.5h": (OPEN_ + 120, OPEN_ + 270), "4.5h-end": (OPEN_ + 270, CLOSE_), "whole session": (OPEN_, CLOSE_)}
base = (wd < 5) & (mins >= OPEN_) & (mins < CLOSE_)
P = {"train": (yr <= 2022), "valid": (yr >= 2023) & (yr <= 2024), "test": (yr >= 2025)}
# thresholds from training data only
TH = {}
for fn, f in F.items():
    a = np.abs(f[P["train"] & base & np.isfinite(f)])
    TH[fn] = {q: np.quantile(a, q) for q in (0.8, 0.9, 0.95, 0.98, 0.995)}
def stats(mask, fwd, d):
    x = d[mask] * fwd[mask] - (SP * O[mask] if SP < 0.01 else SP)
    x = x[np.isfinite(x)]
    if len(x) < 200: return None
    return x.mean(), x.mean() / (x.std() / np.sqrt(len(x))), len(x)
rows = []; n_tested = 0
for fn, f in F.items():
    sgn = np.sign(f)
    for q, th in TH[fn].items():
        big = np.isfinite(f) & (np.abs(f) >= th) & base
        for wn, (a, z) in WIN.items():
            wm = big & (mins >= a) & (mins < z)
            for filt in ("none", "with trend", "against trend", "high vol", "low vol"):
                fm = wm
                if filt == "with trend": fm = wm & (trend == sgn)
                elif filt == "against trend": fm = wm & (trend == -sgn)
                elif filt == "high vol": fm = wm & vreg
                elif filt == "low vol": fm = wm & ~vreg
                for mode in ("follow", "fade"):
                    d = sgn if mode == "follow" else -sgn
                    for h, fwd in FWD.items():
                        n_tested += 1
                        s = stats(fm & P["train"], fwd, d)
                        if s is None or s[1] < 3.0: continue          # must clearly beat the spread in training (t > 3)
                        v = stats(fm & P["valid"], fwd, d); te = stats(fm & P["test"], fwd, d)
                        rows.append(dict(feature=fn, extreme=f"top {round((1-q)*100,1)}%", window=wn, filter=filt, mode=mode, hold_min=h,
                                         train_pts=round(s[0], 2), train_t=round(s[1], 1), train_n=s[2],
                                         valid_pts=round(v[0], 2) if v else None, valid_t=round(v[1], 1) if v else None,
                                         test_pts=round(te[0], 2) if te else None, test_t=round(te[1], 1) if te else None, test_n=te[2] if te else 0))
df = pd.DataFrame(rows)
print(f"variations tested: {n_tested:,}")
print(f"passed hurdle 1 (2020-22, beats spread, t>3): {len(df)}")
v = df[(df.valid_pts > 0) & (df.valid_t > 2)] if len(df) else df
print(f"also passed hurdle 2 (2023-24, beats spread, t>2): {len(v)}")
t = v[(v.test_pts > 0) & (v.test_t > 2)] if len(v) else v
print(f"also passed hurdle 3 (2025-26, beats spread, t>2): {len(t)}")
pd.set_option("display.width", 300); pd.set_option("display.max_rows", 60)
if len(df): print("\nbest of hurdle 1 by training t:"); print(df.sort_values("train_t", ascending=False).head(15).to_string(index=False))
if len(t): print("\nSURVIVORS:"); print(t.sort_values("test_t", ascending=False).to_string(index=False))
df.to_pickle(f"grind_{NAME}.pkl")
