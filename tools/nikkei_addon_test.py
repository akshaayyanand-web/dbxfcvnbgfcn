# Nikkei breakout added to the 12 EAs (Pass Mode and default) under FTMO's exact rule, on the dates with Nikkei data.
import os, numpy as np, pandas as pd
src = open('/home/user/dbxfcvnbgfcn/tools/ftmo_balance_rule_test.py').read().split("def ev(args)")[0]
exec(src.replace('print(f"check', 'pass  # print(f"check'))
NM = "breakout20 EMA800 stop2.0ATR"; COSTJ = 0.0002
JT = list(pd.read_pickle("world_JPNIDXJPY.pkl")[1]["JPN 5min " + NM]) + list(pd.read_pickle("jp_broker_trades.pkl")[NM])
JR = np.zeros(len(idx)); JL = np.zeros(len(idx))
for et, xt, e, st, px in JT:
    h = idx.searchsorted(xt)
    if h >= len(idx): continue
    r = (px - e) / abs(e - st) * np.sign(e - st) - COSTJ * e / abs(e - st); JR[h] += r; JL[h] += min(r, 0.0)
print("Nikkei trades booked:", len(JT))
BASE_R, BASE_L = np.array(EQ_R, float).copy(), np.array(EQ_L, float).copy()
def ev(cfg):
    global CFG, EQ_R, EQ_L
    wj, m, Z = cfg; CFG = (Z, 0.905, (0.04, 0.02))
    EQ_R = BASE_R + wj / 100 * JR; EQ_L = np.minimum(BASE_L + wj / 100 * JL, BASE_L + wj / 100 * JL)
    out = dict(nikkei_risk=wj, mult=m, room=Z)
    for lab, a, z in (("2021-23", "2021-01-15", "2022-11-30"), ("2025-26", "2025-06-15", "2026-06-30")):
        res = []
        for s in pd.date_range(a, z, freq="1D", tz="UTC"):
            if s.weekday() >= 5: continue
            h0 = idx.searchsorted(s); p1, i1 = attempt(h0, 0.10, m, "balance", True, 0.04, brake="equity")
            if p1 != "pass": res.append((p1, None)); continue
            p2, i2 = attempt(i1 + 1, 0.05, m, "balance", True, 0.04, brake="equity"); res.append((p2, (i2 - h0) / 24 if p2 == "pass" else None))
        n = len([x for x in res if x[0] != "open"]); t = [x[1] for x in res if x[1] is not None]
        out[f"{lab} pass%"] = 100 * sum(x[0] == "pass" for x in res) / n; out[f"{lab} breach%"] = 100 * sum(x[0] == "breach" for x in res) / n
        out[f"{lab} open%"] = 100 * sum(x[0] == "open" for x in res) / len(res); out[f"{lab} days"] = np.median(t)
    return out
cfgs = [(wj, m, Z) for (m, Z) in ((1.0, 0.07), (1.5, 0.09)) for wj in (0.0, 0.1, 0.2, 0.3, 0.4)]
with Pool(os.cpu_count()) as p: rows = p.map(ev, cfgs)
pd.set_option("display.width", 300); print(pd.DataFrame(rows).round(1).to_string(index=False))
