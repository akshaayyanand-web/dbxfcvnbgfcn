import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from engine import evaluate_streams, RES
from strategies.batch_orb import SPECS
done = {json.loads(l)["id"] for l in open(RES)} if os.path.exists(RES) else set()
for sid, form, desc, fn, g in SPECS:
    if sid in done: continue
    u = "orb_pairs" if sid == "STRAT-0048" else "orb_main"
    r = evaluate_streams(sid, f"Opening-range expansion — {form}", u, fn, g, desc)
    print(f'{sid} {u} WF CAGR {r["walkforward"]["cagr"]:+.3f} Sh {r["walkforward"]["sharpe"]:+.2f} | test Sh {r["test"]["sharpe"]:+.2f} DD {r["test"]["maxdd"]:+.2f} | trades {r["test_trades"]["trades"]} win {r["test_trades"]["win"]} | corr {r["max_corr"]} {r["max_corr_with"]} | t {r["alpha_t"]} | pass {r["passed"]} {r["params"]}', flush=True)
