# Pass-mode sizing grid on the 12 EAs under FTMO's exact daily rule (midnight balance - 5%), tick guard on, brake on day-start equity.
# Varies the risk multiplier per phase, the room cap and the daily guard; an attempt starts every weekday.
import os, numpy as np, pandas as pd
src = open('ftmo_balance_rule_test.py').read().split("def ev(args)")[0]
exec(src.replace('print(f"check', 'pass  # print(f"check'))
def ev(cfg):
    global CFG
    m1, m2, Z, G = cfg; CFG = (Z, 0.905, (0.04, 0.02)); out = dict(p1_risk=m1, p2_risk=m2, room=Z, guard=G)
    for lab, a, z in (("A", "2020-04-01", "2022-12-31"), ("B", "2023-01-01", "2025-09-01"), ("C", "2026-01-01", "2026-08-15")):
        res = []
        for s in pd.date_range(a, z, freq="1D", tz="UTC"):
            if s.weekday() >= 5: continue
            h0 = idx.searchsorted(s); p1, i1 = attempt(h0, 0.10, m1, "balance", True, G, brake="equity")
            if p1 != "pass": res.append((p1, None)); continue
            p2, i2 = attempt(i1 + 1, 0.05, m2, "balance", True, G, brake="equity"); res.append((p2, (i2 - h0) / 24 if p2 == "pass" else None))
        n = len([x for x in res if x[0] != "open"]); t = [x[1] for x in res if x[1] is not None]
        out[f"{lab}pass"] = 100 * sum(x[0] == "pass" for x in res) / n; out[f"{lab}breach"] = 100 * sum(x[0] == "breach" for x in res) / n
        out[f"{lab}days"] = np.median(t); out[f"{lab}p80"] = np.percentile(t, 80)
    return out
cfgs = [(1.0, 1.0, 0.07, 0.04)]
for m1 in (1.25, 1.5, 2.0, 2.5, 3.0):
    for m2 in (1.0, m1):
        for Z in (0.05, 0.07, 0.09):
            for G in (0.03, 0.04):
                cfgs.append((m1, m2, Z, G))
with Pool(os.cpu_count()) as p: rows = p.map(ev, cfgs)
df = pd.DataFrame(rows); df.to_pickle("passmode2.pkl")
pd.set_option("display.width", 300); pd.set_option("display.max_rows", 200)
df["minpass"] = df[["Apass", "Bpass", "Cpass"]].min(axis=1)
print(df.round(1).to_string(index=False))
