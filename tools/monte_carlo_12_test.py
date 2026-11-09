# Run from the scratchpad (needs phase2_boost.py chain).
# Block-bootstrap Monte Carlo of the 2-step evaluation with the 12 EAs and the drawdown brake.
import sys, numpy as np, pandas as pd
exec(open('phase2_boost.py').read().split("def attempt2")[0])
days_ = pd.Series(DAYN); bounds = np.r_[0, np.flatnonzero(np.diff(DAYN)) + 1, len(DAYN)]
CH = [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]          # one chunk per calendar day (hourly rows)
def synth(rng, ndays=500, block=20):
    out_r, out_l, out_d = [], [], []; dn = 0
    while dn < ndays:
        s = rng.integers(0, len(CH) - block)
        for a, b in CH[s:s + block]:
            out_r.append(r12[a:b]); out_l.append(l12[a:b]); out_d.append(np.full(b - a, dn)); dn += 1
    return np.concatenate(out_r), np.concatenate(out_l), np.concatenate(out_d)
def attempt(r, l, dn, h0, target):
    Z, sl, half = CFG; eq = 1.0; day = -1; hd = -1; halfmode = False
    for i in range(h0, len(r)):
        if dn[i] != day:
            day = dn[i]; dopen = eq
            if eq <= 1 - half[0]: halfmode = True
            elif eq >= 1 - half[1]: halfmode = False
            mm = max(0.0, min(1.0, (eq - 0.90) / Z)) * (0.5 if halfmode else 1.0)
        if hd == day or (r[i] == 0 and l[i] == 0): continue
        x = eq * (1 + mm * l[i])
        if x <= 0.90 or x <= dopen * 0.95: return "breach", i
        eq *= 1 + mm * r[i]
        if eq >= 1 + target: return "pass", i
        if 1 - eq / dopen >= 0.04: hd = day
        if eq <= sl: return "stopped", i
    return "open", len(r) - 1
def path(seed):
    rng = np.random.default_rng(seed); r, l, dn = synth(rng)
    a, i1 = attempt(r, l, dn, 0, 0.10)
    if a != "pass": return a, None
    b, i2 = attempt(r, l, dn, i1 + 1, 0.05)
    return b, (dn[i2] if b == "pass" else None)
with Pool(4) as p: res = p.map(path, range(2000))
out = pd.Series([x[0] for x in res]).value_counts(normalize=True) * 100
t = np.array([x[1] for x in res if x[1] is not None])          # day chunks are calendar days already
print("2,000 reshuffled histories (20-day blocks), 12 EAs + drawdown brake:")
print((out.round(1)).to_string())
print(f"median ~{np.median(t):.0f} calendar days to funded; funded within 60 days {100*np.mean(t<=60)*len(t)/len(res):.0f}%, within 120 days {100*np.mean(t<=120)*len(t)/len(res):.0f}% of all attempts")
