import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from engine import evaluate_streams, RES
from strategies.batch_fix import SPECS
done = {json.loads(l)["id"] for l in open(RES)} if os.path.exists(RES) else set()
for sid, form, desc, fn, g in SPECS:
    if sid in done: continue
    r = evaluate_streams(sid, f"FX fixing-window flow — {form}", "fx_fix", fn, g, desc)
    print(f'{sid} WF CAGR {r["walkforward"]["cagr"]:+.3f} Sh {r["walkforward"]["sharpe"]:+.2f} | test Sh {r["test"]["sharpe"]:+.2f} | trades {r["test_trades"]["trades"]} win {r["test_trades"]["win"]} | t {r["alpha_t"]} | pass {r["passed"]} {r["params"]}', flush=True)
