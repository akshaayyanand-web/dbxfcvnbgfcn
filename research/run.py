"""Run catalogue entries in ID order, skipping ones already recorded. Usage: python3 run.py [first_id] [last_id]"""
import sys, json, os, time
sys.path.insert(0, os.path.dirname(__file__))
from engine import evaluate, RES
from strategies import batch001
done = set()
if os.path.exists(RES):
    for l in open(RES): r = json.loads(l); done.add((r["id"], r["universe"]))
lo, hi = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ("STRAT-0001", "STRAT-9999")
for s in batch001.specs():
    if not (lo <= s["id"] <= hi): continue
    for u in s["universes"]:
        if (s["id"], u) in done: continue
        t = time.time()
        try:
            r = evaluate(s["id"], f'{s["family"]} — {s["form"]}', u, s["fn"], s["grid"], s["desc"])
            print(f'{s["id"]} {u:13s} WF CAGR {r["walkforward"]["cagr"]:+.3f} Sh {r["walkforward"]["sharpe"]:+.2f} | test Sh {r["test"]["sharpe"]:+.2f} DD {r["test"]["maxdd"]:+.2f} | trades {r["test_trades"]["trades"]} | corr {r["max_corr"]} {r["max_corr_with"]} | a_t {r["alpha_t"]} beta {r["beta"]} | pass {r["passed"]} ({time.time()-t:.0f}s)', flush=True)
        except Exception as e:
            print(f'{s["id"]} {u} ERROR {type(e).__name__}: {e}', flush=True)
