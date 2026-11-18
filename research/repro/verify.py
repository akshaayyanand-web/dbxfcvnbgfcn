"""Re-run recorded strategies from the snapshot only (RSCRATCH points at a directory that holds nothing but the imported snapshot)."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import universe, size, run, metrics, split_idx
from strategies import batch001, batch008
specs = {s["id"]: s for s in batch001.specs() + batch008.specs() if not s.get("blocked")}
rec = {}
for l in open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results", "results.jsonl")):
    r = json.loads(l); rec[(r["id"], r["universe"])] = r
for sid, u in (("STRAT-0002", "ind49"), ("STRAT-0720", "perp")):
    s = specs[sid]; r = rec[(sid, u)]; R, c, a = universe(u); R = R.dropna(how="all")
    w = size(s["fn"](R, r["params"]), R, a) if s.get("sizing", True) else s["fn"](R, r["params"]); p, _, _ = run(w, R, c, a); t1, t2 = split_idx(R.index)
    print(sid, u, "| recorded test Sharpe", r["test"]["sharpe"], "| reproduced test Sharpe", metrics(p.loc[t2:].iloc[1:], a)["sharpe"], "| recorded train", r["train"]["sharpe"], "| reproduced train", metrics(p.loc[:t1], a)["sharpe"])
