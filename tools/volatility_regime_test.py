# Run from the scratchpad (needs phase2_boost.py chain).
import sys, numpy as np, pandas as pd
exec(open('phase2_boost.py').read().split("def attempt2")[0])
W12 = dict(zip(KEYS, SETS["8|btc0.75|x1.25"])); W12["nqbo15"] = 0.2
DIPS = ["btc", "gdip", "nq2h", "spx1h", "oil1h"]; BOS = ["gasia", "gmom", "orb15", "nqbo15"]
ser = {k: pd.Series(W12[k] * RM[KEYS.index(k)], index=idx) for k in DIPS + BOS}
ser["daxorb"] = pd.Series(0.2 * S[("DAX 15min ORB30 trend50 target0 stop-mid", 1)][0], index=idx); BOS.append("daxorb")
ser["spxbo5"] = pd.Series(0.1 * CAND["SPX 5m breakout"][0], index=idx); BOS.append("spxbo5")
day = lambda s: s.resample("1D").sum()
dip_d = day(sum(ser[k] for k in DIPS)); bo_d = day(sum(ser[k] for k in BOS))
nqd = nq.c.resample("1D").last().dropna(); rv = np.log(nqd).diff().rolling(20).std() * np.sqrt(252)
regime = (rv > rv.rolling(250, min_periods=120).median()).shift(1)          # yesterday's 20-day vol vs its own 1-year median
df = pd.DataFrame({"dips": dip_d, "breakouts": bo_d, "hivol": regime.reindex(dip_d.index, method="ffill")}).dropna()
df["half"] = np.where(df.index < pd.Timestamp("2023-01-01", tz="UTC"), "2020-22", "2023-26")
print("average daily result (% of account) by Nasdaq volatility regime:")
print((df.groupby(["half", "hivol"])[["dips", "breakouts"]].mean() * 100).round(3).to_string())

"""tilt test (regime_tilt.py):
import sys, numpy as np, pandas as pd
exec(open('regime.py').read().split("day = lambda")[0])
lo = {k: W12[k] * LM[KEYS.index(k)] for k in DIPS + ["gasia", "gmom", "orb15", "nqbo15"]}
lo["daxorb"] = 0.2 * S[("DAX 15min ORB30 trend50 target0 stop-mid", 1)][1]; lo["spxbo5"] = 0.1 * CAND["SPX 5m breakout"][1]
R_dip = sum(ser[k].to_numpy() for k in DIPS); L_dip = sum(lo[k] for k in DIPS)
R_bo = sum(ser[k].to_numpy() for k in BOS); L_bo = sum(lo[k] for k in BOS)
nqd = nq.c.resample("1D").last().dropna(); rv = np.log(nqd).diff().rolling(20).std() * np.sqrt(252)
hv = (rv > rv.rolling(250, min_periods=120).median()).shift(1).reindex(idx.floor("D"), method="ffill").fillna(False).to_numpy().astype(bool)
print("check base == r12:", np.allclose(R_dip + R_bo, r12), flush=True)
TILTS = {"current (no switching)": (1, 1, 1, 1), "shift 1.25 / 0.75": (1.25, 0.75, 0.75, 1.25), "shift 1.5 / 0.5": (1.5, 0.5, 0.5, 1.5),
         "cut the weak side only (x0.75)": (1, 0.75, 0.75, 1), "cut the weak side only (x0.5)": (1, 0.5, 0.5, 1)}
def run(item):
    global r12, l12
    nm, (dh, bh, dl, bl) = item          # dips in high vol, breakouts in high vol, dips in low vol, breakouts in low vol
    r12 = np.where(hv, dh * R_dip + bh * R_bo, dl * R_dip + bl * R_bo); l12 = np.where(hv, dh * L_dip + bh * L_bo, dl * L_dip + bl * L_bo)
    o = evp(1.0); o["phase 2 risk x"] = nm
    rr = pd.Series(r12, index=idx); ys = [(1 + rr[idx.searchsorted(s):idx.searchsorted(s + pd.DateOffset(years=1))]).prod() - 1 for s in pd.date_range("2020-04-01", "2025-10-01", freq="MS", tz="UTC")]
    o["funded yr median %"] = 100 * np.median(ys); o["2026 %"] = 100 * ((1 + rr[rr.index.year == 2026]).prod() - 1); return o
exec("def attempt2" + open('phase2_boost.py').read().split("def attempt2")[1].split("with Pool")[0])
with Pool(4) as p: rows = p.map(run, list(TILTS.items()))
df = pd.DataFrame(rows).rename(columns={"phase 2 risk x": "setup"}); pd.set_option("display.width", 300); print(df.round(1).to_string(index=False))
"""
