# Aggressive presets (run from the scratchpad, see tools/fast_preset_test.py).
# Aggressive "turbo" presets: aim for funded in ~30 days at 70-80% pass.
import sys, numpy as np, pandas as pd
exec(open('fund_check.py').read().split("C = [")[0])
_run4 = run4; HALT = {"v": 0.8}
def run4(set_, rule, phase, h0, target, halt=None, maxl=0.10, daily=0.05): return _run4(set_, rule, phase, h0, target, HALT["v"], maxl, daily)
base = SETS["8|btc0.75|x1.25"]
for sc in (1.5, 2.0, 2.5, 3.0, 4.0):
    for btc in ("same", "half", "zero"):
        w = base * sc
        if btc == "half": w[0] *= 0.5
        if btc == "zero": w[0] = 0.0
        RB[f"x{sc}|btc-{btc}"] = mk(w)
dst = pd.date_range("2020-04-01", "2025-09-01", freq="3D", tz="UTC")
def evt(g):
    s, rule, h, part = g; HALT["v"] = h; res = []
    for st in dst:
        if (st < split) != (part == "A"): continue
        h0 = idx.searchsorted(st); a, i1 = run4(s, rule, 1, h0, 0.10)
        if a != "pass": res.append((a, None)); continue
        b, i2 = run4(s, rule, 2, h0 + i1 + 1, 0.05); res.append((b, (i1 + i2) / 24 if b == "pass" else None))
    t = [x[1] for x in res if x[1] is not None]
    return dict(set=s, rule=str(rule), halt=h, part=part, pass_=100 * np.mean([x[0] == "pass" for x in res]),
                breach=100 * np.mean([x[0] == "fail" for x in res]), days=np.median(t) if t else 999,
                in30=100 * np.mean([x[1] is not None and x[1] <= 30 for x in res]), in45=100 * np.mean([x[1] is not None and x[1] <= 45 for x in res]))
grid = [(s, ("room", 1.0, m2, Z, 0.905, -1), h) for s in RB if s.startswith("x") for m2 in (0.5, 1.0) for Z in (0.03, 0.06) for h in (0.5, 0.8)]
if __name__ == "__main__":
    with Pool(4) as p: A = p.map(evt, [g + ("A",) for g in grid], chunksize=4)
    dA = pd.DataFrame(A); dA.to_pickle("turbo_A.pkl")
    pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 60)
    ok = dA[dA.pass_ >= 70].sort_values("in30", ascending=False)
    print(f"{len(ok)} of {len(dA)} with >=70% pass on 2020-22", flush=True); print(ok.head(25).round(1).to_string(index=False), flush=True)
    pick = ok.head(12)
    with Pool(4) as p: B = p.map(evt, [(r.set, eval(r.rule), r.halt, "B") for r in pick.itertuples()])
    m = pick.merge(pd.DataFrame(B), on=["set", "rule", "halt"], suffixes=("_A", "_B")).drop(columns=["part_A", "part_B"])
    print(m.round(1).to_string(index=False), flush=True)

# ---- comparison on both periods (turbo_b.py) ----
"""
import sys
exec(open('turbo.py').read().split('if __name__')[0])
RB["fast"] = mk(base)
G = [("fast", ("room", 1.0, 1.0, 0.03, 0.905, -1), 0.8, "fast preset (current default)"),
     ("x1.5|btc-same", ("room", 1.0, 0.5, 0.06, 0.905, -1), 0.5, "1.5x phase 1, 0.5x phase 2, 2.5% daily stop"),
     ("x1.5|btc-same", ("room", 1.0, 1.0, 0.03, 0.905, -1), 0.5, "1.5x both phases, 2.5% daily stop"),
     ("x2.0|btc-same", ("room", 1.0, 1.0, 0.03, 0.905, -1), 0.5, "2x both phases, 2.5% daily stop"),
     ("x2.5|btc-same", ("room", 1.0, 1.0, 0.03, 0.905, -1), 0.5, "2.5x both phases, 2.5% daily stop")]
def f(g):
    out = {"setup": g[3]}
    for part in "AB":
        r = evt((g[0], g[1], g[2], part)); out |= {f"{part}_{k}": r[k] for k in ("pass_", "breach", "days", "in30", "in45")}
    return out
if __name__ == "__main__":
    with Pool(4) as p: rows = p.map(f, G)
    pd.set_option("display.width", 250); print(pd.DataFrame(rows).round(1).to_string(index=False))
"""
