# Run from the scratchpad: needs fund_check.py / nobtc.py / weightopt.py there (see tools/fast_preset_test.py).
import sys, numpy as np, pandas as pd
exec(open('fund_check.py').read().split("C = [")[0])
exec("dst =" + open('fund_check.py').read().split("dst =")[1].split("with Pool")[0])
import inspect
_run4 = run4
HALT = {"v": 0.8}
def run4(set_, rule, phase, h0, target, halt=None, maxl=0.10, daily=0.05): return _run4(set_, rule, phase, h0, target, HALT["v"], maxl, daily)
for sc in (1.0, 1.1, 1.2):
    w = SETS["8|btc0.75|x1.25"] * sc; w[0] = 0.75; RB[f"s{sc}"] = mk(w)
grid = [(f"s{sc}", ("room", 1.0, m2, 0.03, 0.905, -1), h) for sc in (1.0, 1.1, 1.2) for m2 in (0.75, 1.0, 1.25) for h in (0.5, 0.6, 0.7, 0.8)]
def evh(g):
    s, r, h = g; HALT["v"] = h; out = ev((s, r, "A")); out["halt"] = h; return out
def jobh(g):
    s, r, h = g; HALT["v"] = h; o = job((s, r, f"{s} {r[2]} halt{h}")); return o
if __name__ == "__main__":
    with Pool(4) as p: A = p.map(evh, grid)
    dA = pd.DataFrame(A); pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 60)
    ok = dA[(dA.breach == 0) & (dA.pass_ >= 93)].sort_values("days"); print(f"{len(ok)} of {len(dA)} ok on 2020-22", flush=True)
    print(dA.sort_values("days").round(1).to_string(index=False), flush=True)
    pick = [("s1.0", ("room", 1.0, 1.0, 0.03, 0.905, -1), 0.8)] + [(r.set, eval(r.rule), r.halt) for r in ok.head(8).itertuples()]
    with Pool(4) as p: rows = p.map(jobh, pick)
    print(pd.DataFrame(rows).round(1).to_string(index=False), flush=True)
