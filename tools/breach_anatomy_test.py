# Run from the scratchpad (needs regime_tilt.py chain).
import sys, numpy as np, pandas as pd
exec(open('regime_tilt.py').read().split("TILTS = {")[0])
gapr, gapl = 0.25 * V[(0.02, "48h")][0], 0.25 * V[(0.02, "48h")][1]
comp_r = {k: ser[k].to_numpy() for k in ser} | {"btcgap": gapr}; comp_l = {k: lo[k] for k in lo} | {"btcgap": gapl}
R = sum(comp_r.values()); Lw = sum(comp_l.values())
print("rebuilt == r12:", np.allclose(R, r12), flush=True)
exec("def attempt2" + open('phase2_boost.py').read().split("def attempt2")[1].split("def evp")[0])
r12, l12 = 1.1 * R, 1.1 * Lw
ev = []
for s in pd.date_range("2020-04-01", "2026-08-15", freq="1D", tz="UTC"):
    if s.weekday() >= 5: continue
    h0 = idx.searchsorted(s); a, i = attempt2(h0, 0.10, 1.0)
    if a == "pass": a, i = attempt2(i + 1, 0.05, 1.0)
    if a == "breach": ev.append(i)
hrs = pd.Series(ev).value_counts()
print(f"breaching attempts at 1.1x: {len(ev)}, on {hrs.size} distinct hours")
for h, n in hrs.items():
    t = idx[h]; d0 = idx.searchsorted(t.floor("D")); 
    dayloss = {k: 100 * (comp_r[k][d0:h].sum() + comp_l[k][h]) for k in comp_r}
    top = sorted(dayloss.items(), key=lambda x: x[1])[:4]
    print(f"{t} UTC ({t.tz_convert('America/New_York').strftime('%a %H:%M')} NY): {n} attempts | biggest day losses at 1x: " + ", ".join(f"{k} {v:+.2f}%" for k, v in top))
