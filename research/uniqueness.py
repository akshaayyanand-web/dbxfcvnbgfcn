"""Post-hoc uniqueness: weekly-aggregated correlation of each strategy's walk-forward P&L with every EARLIER strategy on the same market
(catches time-shifted duplicates that daily correlation misses). Writes results/uniqueness.json."""
import os, json, pickle, pandas as pd, numpy as np
from data import SCR
D = f"{SCR}/rdata/pnl"; S = {}
for f in os.listdir(D):
    s = pickle.load(open(f"{D}/{f}", "rb")); s.index = pd.to_datetime(s.index); s.index = s.index.tz_localize(None) if s.index.tz is not None else s.index
    S[f[:-4]] = s.resample("W").sum()
out = {}
for k, s in S.items():
    sid, u = k.split("@"); best = (0.0, None)
    for k2, s2 in S.items():
        sid2, u2 = k2.split("@")
        if u2 != u or sid2 >= sid: continue
        j = pd.concat([s, s2], axis=1, join="inner").dropna(); j = j[(j != 0).any(axis=1)]
        if len(j) >= 52:
            c = float(j.corr().iloc[0, 1])
            if abs(c) > abs(best[0]): best = (round(c, 2), sid2)
    out[k] = best
json.dump(out, open(os.path.join(os.path.dirname(__file__), "results", "uniqueness.json"), "w"), indent=0)
print(len(out), "strategy-market series; |weekly corr|>=0.7:", sum(abs(v[0]) >= 0.7 for v in out.values()))
