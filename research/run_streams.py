"""Run stream-type batches (modules exposing FAMS / BLOCKED / EXTRA_BLOCK). Usage: python3 run_streams.py strategies.batch006"""
import sys, os, json, importlib
sys.path.insert(0, os.path.dirname(__file__))
from engine import evaluate_streams, RES
M = importlib.import_module(sys.argv[1])
done = {json.loads(l)["id"] for l in open(RES)} if os.path.exists(RES) else set()
FORMS = ["event-triggered", "cross-sectional", "time-series", "lead-lag", "regime-conditioned", "term-structure", "flow-based", "relative-value", "volatility-based", "execution-aware"]
def block(sid, name, why):
    if sid in done: return
    with open(RES, "a") as f: f.write(json.dumps(dict(id=sid, name=name, universe="BLOCKED", blocked=why)) + "\n")
    print(sid, "BLOCKED:", why)
for off, (fam, why) in getattr(M, "BLOCKED", {}).items():
    for j, form in enumerate(FORMS): block(f"STRAT-{off + j + 1:04d}", f"{fam} — {form}", why + " - not available in this environment")
FAMS = {k: (v if isinstance(v, tuple) else v) for k, v in M.FAMS.items()}
for key, (fam, specs) in FAMS.items():
    for sid, form, desc, fn, g in specs:
        if sid in done: continue
        try:
            r = evaluate_streams(sid, f"{fam} — {form}", key, fn, g, desc)
            print(f'{sid} {key} WF CAGR {r["walkforward"]["cagr"]:+.3f} Sh {r["walkforward"]["sharpe"]:+.2f} DD {r["walkforward"]["maxdd"]:+.2f} | test Sh {r["test"]["sharpe"]:+.2f} DD {r["test"]["maxdd"]:+.2f} | trades {r["test_trades"]["trades"]} | corr {r["max_corr"]} {r["max_corr_with"]} | t {r["alpha_t"]} | pass {r["passed"]} {r["params"]}', flush=True)
        except Exception as e: print(sid, "ERROR", type(e).__name__, e, flush=True)
for sid, ref in getattr(M, "MERGED", {}).items():
    if sid in done: continue
    with open(RES, "a") as f: f.write(json.dumps(dict(id=sid, name="Calendar options spread", universe="BLOCKED", blocked=f"MERGED into {ref}: same synthetic calendar instrument (1M vs 3M on VIX/VIX3M) and data; not counted separately")) + "\n")
for sid, why in getattr(M, "EXTRA_BLOCK", {}).items():
    fam = next((f for k, (f, sp) in M.FAMS.items() if sp and sid[:9] == sp[0][0][:9]), "Microstructure")
    block(sid, f"{fam} — {FORMS[int(sid[-1]) - 1 if sid[-1] != '0' else 9]}", why + " - not available in this environment")
