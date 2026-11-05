# Safer turbo grid (run from the scratchpad, needs turbo.py there; see tools/turbo_preset_test.py).
# Safer turbo: keep ~37-40 day median, raise pass rate / cut breaches.
import sys, numpy as np, pandas as pd
exec(open('turbo.py').read().split('grid = [')[0])
def mult(rule, phase, eq):
    if rule[0] == "room":
        _, m1, m2, Z, sl, cu = rule; b = 1.0 if phase == 1 else m2
        return max(0.0, min(b, (eq - 0.90) / Z))
    _, m2, Z, sl, L, lockm = rule                      # "tb"
    b = 1.0 if phase == 1 else m2
    if L and phase == 1 and eq - 1 >= L: b = lockm   # close to the phase-1 target: ease off
    return max(0.0, min(b, b * (eq - 0.90) / Z if Z > 0.03 else (eq - 0.90) / Z))
_r4 = _run4
def _run4(set_, rule, phase, h0, target, halt=0.8, maxl=0.10, daily=0.05):
    return _r4(set_, ("room", 1, 1, 0, rule[3], 0) if False else rule, phase, h0, target, halt, maxl, daily)
for nb in (1.25, 1.5, 1.75, 2.0):
    for bw in (0.5, 0.75, 1.125):
        w = base * nb; w[0] = bw; RB[f"nb{nb}|btc{bw}"] = mk(w)
grid = [(f"nb{nb}|btc{bw}", ("tb", m2, Z, 0.905, L, 0.6), h) for nb in (1.25, 1.5, 1.75, 2.0) for bw in (0.5, 0.75, 1.125)
        for m2 in (0.75, 1.0) for Z in (0.03, 0.05, 0.08) for h in (0.4, 0.5, 0.6) for L in (0, 0.07)]
if __name__ == "__main__":
    with Pool(4) as p: A = p.map(evt, [g + ("A",) for g in grid], chunksize=8)
    dA = pd.DataFrame(A); dA.to_pickle("turbo2_A.pkl")
    pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 60)
    ok = dA[dA.days <= 42].sort_values(["pass_", "breach"], ascending=[False, True])
    print(f"{len(ok)} of {len(dA)} with median <=42 days on 2020-22", flush=True); print(ok.head(25).round(1).to_string(index=False), flush=True)
    pick = ok.head(16)
    with Pool(4) as p: B = p.map(evt, [(r.set, eval(r.rule), r.halt, "B") for r in pick.itertuples()])
    m = pick.merge(pd.DataFrame(B), on=["set", "rule", "halt"], suffixes=("_A", "_B")).drop(columns=["part_A", "part_B"])
    m.to_pickle("turbo2_AB.pkl"); print(m.round(1).to_string(index=False), flush=True)
