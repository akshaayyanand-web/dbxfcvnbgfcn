# Run from the scratchpad (needs fund_check.py, crypto_time_lab.py; see tools/fast_preset_test.py). ATR shifted by 1 bar (no lookahead).
import sys, numpy as np, pandas as pd
exec(open('fund_check.py').read().split("C = [")[0])
exec("dst =" + open('fund_check.py').read().split("dst =")[1].split("with Pool")[0])
L = {}; exec(open('crypto_time_lab.py').read().split("rows = []")[0], L)
d = L["load"]("BTC"); a = L["atr"](d).shift(1); ct = d.index.tz_convert("America/Chicago")
fri = d.index[(ct.weekday == 4) & (ct.hour == 16)]; sun = d.index[(ct.weekday == 6) & (ct.hour == 17)]
pairs = [(f, s) for f in fri for s in sun[(sun > f) & (sun < f + pd.Timedelta("3D"))][:1]]
V = {}
for thr in (0.01, 0.02, 0.03):
    for hold in ("48h", "96h"):
        tr = []
        for f, s in pairs:
            pf = d.c.asof(f - pd.Timedelta("1min")); ps = d.o.get(s, np.nan)
            if not (np.isfinite(ps) and np.isfinite(pf)) or abs(ps / pf - 1) < thr: continue
            dr = 1 if ps > pf else -1; x = L["trade"](d, s, s + pd.Timedelta(hold), dr, ps - dr * 1.5 * a.asof(s))
            if x: tr.append(x)
        V[(thr, hold)] = P.trade_series(tr, P.FEE_CRYPTO, btc, idx)
        dd = pd.DataFrame({"gap": V[(thr, hold)][0], "btcdip": RM[0], "port": RB["8|btc0.75|x1.25"][0]}, index=idx).resample("1D").sum()
        cc = dd[dd.abs().sum(axis=1) > 0].corr()
        print(f"gap>{thr:.0%} hold {hold}: {len(tr)} trades, corr with BTC dip {cc.loc['gap','btcdip']:.2f}, with portfolio {cc.loc['gap','port']:.2f}", flush=True)
RULE = ("room", 1.0, 1.0, 0.03, 0.905, -1); C = [("8|btc0.75|x1.25", RULE, "fast preset")]
for k in V:
    for w in ((0.5,) if k in ((0.02, "48h"), (0.03, "48h")) else ()):
        nm = f"+BTC weekend-gap follow >{k[0]:.0%} {k[1]} @{w}"; RB[nm] = (RB["8|btc0.75|x1.25"][0] + w * V[k][0], RB["8|btc0.75|x1.25"][1] + w * V[k][1]); C.append((nm, RULE, nm))
if __name__ == "__main__":
    with Pool(4) as p: rows = p.map(job, C)
    pd.set_option("display.width", 300); print(pd.DataFrame(rows).round(1).to_string(index=False), flush=True)

"""cost stress (cmegap_stress.py):
import sys, numpy as np, pandas as pd
CM = float(sys.argv[1])
import portfolio_prop as P0
_o = P0.trade_series; P0.trade_series = lambda trades, cost, h1, idx: _o(trades, cost * CM, h1, idx)
src = open('cmegap.py').read().split("RULE = (")[0]; exec(src)
RULE = ("room", 1.0, 1.0, 0.03, 0.905, -1)
C = [("8|btc0.75|x1.25", RULE, f"fast preset costs x{CM}")]
for k, w in (((0.02, "48h"), 0.5), ((0.03, "48h"), 0.5), ((0.02, "48h"), 0.25)):
    nm = f"+gap >{k[0]:.0%} {k[1]} @{w} costs x{CM}"; RB[nm] = (RB["8|btc0.75|x1.25"][0] + w * V[k][0], RB["8|btc0.75|x1.25"][1] + w * V[k][1]); C.append((nm, RULE, nm))
with Pool(4) as p: rows = p.map(job, C)
pd.set_option("display.width", 300); print(pd.DataFrame(rows).round(1).to_string(index=False), flush=True)
"""
