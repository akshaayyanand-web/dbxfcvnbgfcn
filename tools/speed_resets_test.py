# 12 EAs + SOL 0.3% at x1.5-x4 sizing, buying a new account after each failure: calendar days and fees to funded (FTMO exact rule, 4-day minimum per phase).
import os, numpy as np, pandas as pd
exec(open("sol_addon_test.py").read().split("def ev(cfg)")[0])
R_, L_, rl, n = SER["SOL 1h dip RSI2<15 EMA200 hold144"]
def setup(w):
    global EQ_R, EQ_L, FLT
    EQ_R = BASE_R + w / 100 * R_; EQ_L = BASE_L + w / 100 * L_; FLT = BASE_FLT + w / 100 * (np.cumsum(R_) - np.cumsum(rl))
def run(h0, m, Z, G):
    global CFG
    CFG = (Z, 0.905, (0.04, 0.02)); start = h0; acc = 1
    while True:
        p1, i1 = attempt(h0, 0.10, m, "balance", True, G, brake="equity")
        if p1 == "open": return None
        if p1 == "pass":
            i1 = max(i1, h0 + 134)                               # 4 trading days minimum
            p2, i2 = attempt(i1 + 24, 0.05, m, "balance", True, G, brake="equity")
            if p2 == "open": return None
            if p2 == "pass": return (max(i2, i1 + 24 + 134) - start) / 24, acc
            h0 = i2 + 1
        else: h0 = i1 + 1
        acc += 1
def ev(cfg):
    m, Z, G = cfg; setup(0.3); out = []
    for s in pd.date_range("2020-09-01", "2026-03-01", freq="3D", tz="UTC"):
        r = run(idx.searchsorted(s), m, Z, G)
        if r: out.append(r)
    d = np.array([x[0] for x in out]); a = np.array([x[1] for x in out])
    return dict(sizing=f"x{m}", room=Z, guard=G, first_try=round(100 * (a == 1).mean(), 1), median_days=round(np.median(d)), p25=round(np.percentile(d, 25)),
                within_30d=round(100 * (d <= 30).mean()), within_60d=round(100 * (d <= 60).mean()), p90_days=round(np.percentile(d, 90)),
                mean_accounts=round(a.mean(), 2), p90_accounts=int(np.percentile(a, 90)), mean_fees=round(250 * a.mean()))
cfgs = [(1.5, 0.09, 0.04), (2.0, 0.09, 0.04), (2.5, 0.05, 0.04), (3.0, 0.05, 0.04), (4.0, 0.05, 0.04)]
with Pool(os.cpu_count()) as p: rows = p.map(ev, cfgs)
pd.set_option("display.width", 250); print(pd.DataFrame(rows).to_string(index=False))
