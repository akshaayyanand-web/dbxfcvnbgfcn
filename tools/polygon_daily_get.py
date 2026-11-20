"""Download 2 years of daily bars from Polygon for a list of tickers (key from env POLY_KEY, never written to disk). Usage: poly_get.py OUT_DIR"""
import json, os, sys, time, urllib.request
out = sys.argv[1]; key = os.environ["POLY_KEY"]
T = "AAPL MSFT NVDA AMZN GOOGL META TSLA NFLX AMD INTC AVGO ORCL ADBE CRM QCOM CSCO IBM PYPL UBER BA JPM BAC GS V MA WMT KO PEP MCD NKE DIS PFE JNJ MRK XOM CVX COST HD T BABA".split()
for t in T:
    fn = f"{out}/{t}.json"
    if os.path.exists(fn) and os.path.getsize(fn) > 1000: continue
    req = urllib.request.Request(f"https://api.polygon.io/v2/aggs/ticker/{t}/range/1/day/2016-01-01/2026-11-19?adjusted=true&limit=50000", headers={"Authorization": f"Bearer {key}"})
    for k in range(3):
        try: raw = urllib.request.urlopen(req, timeout=60).read(); break
        except Exception as e: print(t, "retry", e, flush=True); time.sleep(30)
    open(fn, "wb").write(raw); print(t, len(json.loads(raw).get("results") or []), "bars", flush=True); time.sleep(13)
print("ALLDONE")
