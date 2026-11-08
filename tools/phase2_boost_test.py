# Run from the scratchpad (needs spx_add11.py chain).
import sys, numpy as np, pandas as pd
exec(open('spx_add11.py').read().split("def runc(job):")[0])
r12 = r0 + 0.1 * CAND["SPX 5m breakout"][0]; l12 = l0 + 0.1 * CAND["SPX 5m breakout"][1]      # current 12 EAs
CFG = (0.07, 0.905, (0.04, 0.02))
def attempt2(h0, target, m):
    Z, sl, half = CFG; eq = 1.0; day = -1; hd = -1; halfmode = False
    for i in range(h0, len(r12)):
        dd_ = DAYN[i]
        if dd_ != day:
            day = dd_; dopen = eq
            if eq <= 1 - half[0]: halfmode = True
            elif eq >= 1 - half[1]: halfmode = False
            mm = m * max(0.0, min(1.0, (eq - 0.90) / Z)) * (0.5 if halfmode else 1.0)
        if hd == dd_ or (r12[i] == 0 and l12[i] == 0): continue
        x = eq * (1 + mm * l12[i])
        if x <= 0.90 or x <= dopen * 0.95: return "breach", i
        eq *= 1 + mm * r12[i]
        if eq >= 1 + target: return "pass", i
        if 1 - eq / dopen >= 0.04: hd = dd_
        if eq <= sl: return "stopped", i
    return "open", len(r12) - 1
def evp(m2):
    out = {"phase 2 risk x": m2}
    for lab, a, z in (("2020-22", "2020-04-01", "2022-12-31"), ("2023-25", "2023-01-01", "2025-09-01"), ("2026", "2026-01-01", "2026-08-15")):
        res = []
        for s in pd.date_range(a, z, freq="1D", tz="UTC"):
            if s.weekday() >= 5: continue
            h0 = idx.searchsorted(s); p1, i1 = attempt2(h0, 0.10, 1.0)
            if p1 != "pass": res.append((p1, None)); continue
            p2, i2 = attempt2(i1 + 1, 0.05, m2); res.append((p2, (i2 - h0) / 24 if p2 == "pass" else None))
        n = len([x for x in res if x[0] != "open"]); t = [x[1] for x in res if x[1] is not None]
        out[f"{lab} pass%"] = 100 * sum(x[0] == "pass" for x in res) / n; out[f"{lab} breach%"] = 100 * sum(x[0] == "breach" for x in res) / n; out[f"{lab} days"] = np.median(t)
    return out
with Pool(4) as p: rows = p.map(evp, [1.0, 1.25, 1.5, 2.0])
pd.set_option("display.width", 250); print(pd.DataFrame(rows).round(1).to_string(index=False))
