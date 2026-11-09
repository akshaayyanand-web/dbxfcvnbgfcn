# Run from the scratchpad.
# "Crash catcher": short Nasdaq / S&P intraday once the day is already down hard from the open; hold to the close.
import sys, numpy as np, pandas as pd
rows, TRC = [], {}
for sym in ("USATECHIDXUSD", "USA500IDXUSD"):
    sys.argv = ["x", sym]; ns = {}; exec(open("world_lab.py").read().split("rows, TR = [], {}")[0], ns)
    b = ns["bars"]("5min"); T = b.index; z = T.tz_convert("America/New_York"); fm = (z.hour * 60 + z.minute).to_numpy(); fday = z.normalize()
    O, H, L, C = (b[k].to_numpy() for k in "ohlc"); atr = ns["atr_of"](b)
    op = pd.Series(np.where(fm == 570, O, np.nan)).groupby(fday.values).transform("max").to_numpy()        # 09:30 open
    dr = (b.h.resample("1D").max() - b.l.resample("1D").min()).dropna().ewm(alpha=1 / 14, adjust=False).mean().shift(1)
    datr = dr.reindex(T.floor("D"), method="ffill").to_numpy()
    for drop in (0.015, 0.02, 0.025):
        for stopk in (0.5, 1.0):
            for until in (840, 930):
                sig = lambda i, drop=drop, until=until: -1 if (585 <= fm[i] < until and np.isfinite(op[i]) and C[i] < op[i] * (1 - drop)) else 0
                stp = lambda i, d, e, stopk=stopk: e + stopk * datr[i] if np.isfinite(datr[i]) else None
                tr = ns["intraday_sim"](b, sig, stp, 0, 955, 585, until)
                if len(tr) < 20: continue
                nm = f"{sym[:6]} crash short: down {drop:.1%} from open before {until // 60}:{until % 60:02d}, stop {stopk} day-ATR"
                rows.append(ns["stats"](tr, nm) | dict(n=len(tr))); TRC[nm] = (sym, tr)
df = pd.DataFrame(rows); df["minhalf"] = df[["yrA", "yrB"]].min(axis=1); pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 90)
print(df.sort_values("minhalf", ascending=False).round(2).to_string(index=False)); pd.to_pickle((df, TRC), "crash_short.pkl")

"""hedge test (crash_hedge.py):
import sys, numpy as np, pandas as pd
exec(open('phase2_boost.py').read().split("def evp(m2)")[0])
_, TRC = pd.read_pickle("crash_short.pkl")
sym, tr = TRC["USATEC crash short: down 1.5% from open before 15:30, stop 0.5 day-ATR"]
hed = P.trade_series(tr, 0.00012, nq, idx)
dd = pd.DataFrame({"hedge": hed[0], "port": r12}, index=idx).resample("1D").sum(); dd = dd[dd.abs().sum(axis=1) > 0]
worst = dd.port.nsmallest(30).index
print(f"corr with the 12 EAs: {dd.corr().iloc[0, 1]:.2f}; on the portfolio's 30 worst days the hedge made {100 * dd.hedge.loc[worst].mean():+.3f}% per 1% risk on average", flush=True)
BASE = (r12.copy(), l12.copy())
def run(cfg):
    global r12, l12
    m, w = cfg; r12 = m * BASE[0] + w * hed[0]; l12 = m * BASE[1] + w * hed[1]
    o = evp(1.0); o["phase 2 risk x"] = f"12 EAs x{m} + crash short @{w}%"; return o
exec("def evp(m2)" + open('phase2_boost.py').read().split("def evp(m2)")[1].split("with Pool")[0])
with Pool(4) as p: rows = p.map(run, [(1.0, 0), (1.0, 0.25), (1.0, 0.5), (1.1, 0), (1.1, 0.5), (1.25, 0), (1.25, 0.5), (1.25, 1.0)])
pd.set_option("display.width", 300); print(pd.DataFrame(rows).rename(columns={"phase 2 risk x": "setup"}).round(1).to_string(index=False))
"""
