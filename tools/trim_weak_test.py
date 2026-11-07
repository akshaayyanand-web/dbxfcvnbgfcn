# Run from the scratchpad (needs safer_dd.py chain).
import sys, numpy as np, pandas as pd
exec(open('safer_dd.py').read().split("def ev(cfg)")[0])
W = SETS["8|btc0.75|x1.25"]; io, isx = KEYS.index("orb15"), KEYS.index("spx1h")
BASE = (r_.copy(), lo_.copy())
VAR = {"current 10 EAs": (1, 1), "NQ ORB at half": (0.5, 1), "no NQ ORB": (0, 1), "SPX Dip at half": (1, 0.5), "no SPX Dip": (1, 0),
       "both at half": (0.5, 0.5), "no NQ ORB, no SPX Dip": (0, 0)}
CFG = (0.07, 0.905, (0.04, 0.02))
def runv(item):
    nm, (fo, fs) = item
    global r_, lo_
    r_ = BASE[0] + (fo - 1) * W[io] * RM[io] + (fs - 1) * W[isx] * RM[isx]
    lo_ = BASE[1] + (fo - 1) * W[io] * LM[io] + (fs - 1) * W[isx] * LM[isx]
    out = ev(CFG); out = {k: v for k, v in out.items() if not k.startswith(("size", "hard", "half"))}; out = {"setup": nm} | out
    rr = pd.Series(r_, index=idx); out["2026 %"] = 100 * ((1 + rr[rr.index.year == 2026]).prod() - 1)
    ys = [(1 + rr[idx.searchsorted(s):idx.searchsorted(s + pd.DateOffset(years=1))]).prod() - 1 for s in pd.date_range("2020-04-01", "2025-10-01", freq="MS", tz="UTC")]
    out["funded yr median % (no guards)"] = 100 * np.median(ys); return out
exec("def ev(cfg)" + open('safer_dd.py').read().split("def ev(cfg)")[1].split("CFG = [")[0])
with Pool(4) as p: rows = p.map(runv, list(VAR.items()))
pd.set_option("display.width", 400); pd.set_option("display.max_columns", 40)
df = pd.DataFrame(rows); print(df.round(1).to_string(index=False))
