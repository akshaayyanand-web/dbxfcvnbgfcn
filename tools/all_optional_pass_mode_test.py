# 12 EAs + optional EAs (SOL dip 0.3, gold VWAP pullback 0.2, S&P open fade 0.25, Nikkei 0.1) in Pass Mode under FTMO's exact rule.
import os, numpy as np, pandas as pd
exec(open("sol_addon_test.py").read().split("def ev(cfg)")[0])
R_sol, L_sol, rl_sol, _ = SER["SOL 1h dip RSI2<15 EMA200 hold144"]
AT = pd.read_pickle("addon_trades.pkl")
NM = "breakout20 EMA800 stop2.0ATR"
nk = [(et, xt, (px - e) / abs(e - st) * np.sign(e - st) - 0.0002 * e / abs(e - st)) for et, xt, e, st, px in
      list(pd.read_pickle("world_JPNIDXJPY.pkl")[1]["JPN 5min " + NM]) + list(pd.read_pickle("jp_broker_trades.pkl")[NM])]
def intraday(tr):
    R = np.zeros(len(idx)); L = np.zeros(len(idx))
    for et, xt, r in tr:
        h = idx.searchsorted(pd.Timestamp(xt))
        if h < len(idx) and pd.Timestamp(xt) >= idx[0]: R[h] += r; L[h] += min(r, 0.0)
    return R, L
ADD = {"gold": intraday(AT["gold"]), "spx_fade": intraday(AT["spx_fade"]), "nikkei": intraday(nk)}
W = {"sol": 0.3, "gold": 0.2, "spx_fade": 0.25, "nikkei": 0.1}
def ev(names):
    global CFG, EQ_R, EQ_L, FLT
    CFG = (0.09, 0.905, (0.04, 0.02))
    EQ_R, EQ_L, FLT = BASE_R.copy(), BASE_L.copy(), BASE_FLT.copy()
    for nmx in names:
        w = W[nmx] / 100
        if nmx == "sol": EQ_R = EQ_R + w * R_sol; EQ_L = EQ_L + w * L_sol; FLT = FLT + w * (np.cumsum(R_sol) - np.cumsum(rl_sol))
        else: r, l = ADD[nmx]; EQ_R = EQ_R + w * r; EQ_L = EQ_L + w * l
    yrs = (idx[-1] - idx[0]).days / 365.25
    out = dict(setup="12 EAs" + "".join(" + " + x for x in names), profit_x1_pct_yr=round(100 * EQ_R.sum() / yrs, 1))
    eq = np.cumsum(EQ_R); out["max_dd_x1_pct"] = round(100 * (eq - np.maximum.accumulate(eq)).min(), 1)
    for lab, a, z in (("2020-22", "2020-09-01", "2022-12-31"), ("2023-25", "2023-01-01", "2025-09-01"), ("2026", "2026-01-01", "2026-08-15")):
        res = []
        for s in pd.date_range(a, z, freq="1D", tz="UTC"):
            if s.weekday() >= 5: continue
            h0 = idx.searchsorted(s); p1, i1 = attempt(h0, 0.10, 1.5, "balance", True, 0.04, brake="equity")
            if p1 != "pass": res.append((p1, None)); continue
            p2, i2 = attempt(i1 + 1, 0.05, 1.5, "balance", True, 0.04, brake="equity"); res.append((p2, (i2 - h0) / 24 if p2 == "pass" else None))
        n = len([x for x in res if x[0] != "open"]); t = [x[1] for x in res if x[1] is not None]
        out[f"pass {lab}"] = round(100 * sum(x[0] == "pass" for x in res) / n, 1); out[f"breach {lab}"] = round(100 * sum(x[0] == "breach" for x in res) / n, 1); out[f"days {lab}"] = round(np.median(t))
    return out
combos = [(), ("sol",), ("gold",), ("spx_fade",), ("nikkei",), ("sol", "gold"), ("sol", "gold", "spx_fade"), ("sol", "gold", "spx_fade", "nikkei")]
with Pool(os.cpu_count()) as p: rows = p.map(ev, combos)
pd.set_option("display.width", 320); print(pd.DataFrame(rows).to_string(index=False))
