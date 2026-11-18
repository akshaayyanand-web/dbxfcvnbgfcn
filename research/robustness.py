"""Delay robustness for passing daily strategies: re-run the selected parameters with positions lagged one extra day.
A real edge should survive (slower execution); non-synchronous-data artifacts collapse. Writes results/robustness.json."""
import os, json, importlib, numpy as np, pandas as pd
from engine import universe, size, run, metrics, split_idx
H = os.path.dirname(__file__); _L = {}
for l in open(f"{H}/results/results.jsonl"):
    r = json.loads(l); _L[(r["id"], r.get("universe"))] = r          # latest record per strategy x market
R_ = list(_L.values())
specs = {}
for b in ("batch001", "batch002", "batch003", "batch004", "batch005", "batch008", "batch009", "batch011"):
    for s in importlib.import_module("strategies." + b).specs():
        if not s.get("blocked"): specs[s["id"]] = s
out = {}
for r in R_:
    if not r.get("passed") or r["id"] not in specs: continue
    s = specs[r["id"]]; Rr, cost, ann = universe(r["universe"])
    if s.get("start"): Rr = Rr.loc[s["start"]:]
    Rr = Rr.dropna(how="all"); sig = s["fn"](Rr, r["params"]); w = size(sig, Rr, ann) if s.get("sizing", True) else sig
    t1, t2 = split_idx(Rr.index); res = {}
    for lag in (0, 1):
        p, _, _ = run(w.shift(lag).fillna(0), Rr, cost, ann); res[lag] = (metrics(p, ann)["sharpe"], metrics(p.loc[t2:], ann)["sharpe"])
    fragile = res[1][1] <= 0 or res[1][0] < 0.5 * res[0][0]
    out[f'{r["id"]}@{r["universe"]}'] = dict(full_sharpe=res[0][0], full_sharpe_lag1=res[1][0], test_sharpe=res[0][1], test_sharpe_lag1=res[1][1], fragile=bool(fragile))
    print(r["id"], r["universe"], out[f'{r["id"]}@{r["universe"]}'], flush=True)
json.dump(out, open(f"{H}/results/robustness.json", "w"), indent=0)
