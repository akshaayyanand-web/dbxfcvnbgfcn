# Run from the scratchpad (needs dax_more_port.py chain).
import sys, numpy as np, pandas as pd
exec(open('dax_more_port.py').read().split('RULE = ("room", 1.0, 1.0, 0.03, 0.905, -1); C = [("10 core"')[0])
RULE = ("room", 1.0, 1.0, 0.03, 0.905, -1)
gap = V[(0.02, "48h")]
RB["10 core"] = TEN; RB["10 core minus BTC gap"] = (TEN[0] - 0.5 * gap[0], TEN[1] - 0.5 * gap[1])
RB["10 core, BTC gap at 0.25"] = (TEN[0] - 0.25 * gap[0], TEN[1] - 0.25 * gap[1])
def rec(name):
    out = {"setup": name}
    for lab, a, z in (("2023-25", "2023-01-01", "2025-09-01"), ("2024H2-25", "2024-07-01", "2025-09-01")):
        res = []
        for s in pd.date_range(a, z, freq="1D", tz="UTC"):
            h0 = idx.searchsorted(s); r1, i1 = run4(name, RULE, 1, h0, 0.10)
            if r1 != "pass": res.append((r1, None)); continue
            r2, i2 = run4(name, RULE, 2, h0 + i1 + 1, 0.05); res.append((r2, (i1 + i2) / 24 if r2 == "pass" else None))
        t = [x[1] for x in res if x[1] is not None]
        out[f"{lab} pass"] = 100 * np.mean([x[0] == "pass" for x in res]); out[f"{lab} breach"] = 100 * np.mean([x[0] == "fail" for x in res]); out[f"{lab} days"] = np.median(t)
    yy = [run5(name, RULE, idx.searchsorted(s), idx.searchsorted(s + pd.DateOffset(years=1)), None) for s in pd.date_range("2024-01-01", "2025-10-01", freq="MS", tz="UTC")]
    out["funded yr (2024-25 starts)"] = 100 * np.median([y[1] for y in yy]); out["funded breaches"] = sum(y[0] == "fail" for y in yy)
    r = pd.Series(RB[name][0], index=idx); out["2025 %"] = 100 * ((1 + r[r.index.year == 2025]).prod() - 1); out["2026 %"] = 100 * ((1 + r[r.index.year == 2026]).prod() - 1)
    return out
with Pool(3) as p: rows = p.map(rec, ["10 core", "10 core, BTC gap at 0.25", "10 core minus BTC gap"])
pd.set_option("display.width", 300); print(pd.DataFrame(rows).round(1).to_string(index=False))
