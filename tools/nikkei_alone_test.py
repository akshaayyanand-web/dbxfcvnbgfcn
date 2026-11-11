# Nikkei breakout alone: stats and a stand-alone FTMO 2-step test at several risk sizes.
import numpy as np, pandas as pd
NM = "breakout20 EMA800 stop2.0ATR"; COST = 0.0002
JT = [("duk", x) for x in pd.read_pickle("world_JPNIDXJPY.pkl")[1]["JPN 5min " + NM]] + [("broker", x) for x in pd.read_pickle("jp_broker_trades.pkl")[NM]]
rows = []
for src, (et, xt, e, st, px) in JT:
    r = (px - e) / abs(e - st) * np.sign(e - st) - COST * e / abs(e - st)
    rows.append(dict(src=src, t=pd.Timestamp(et), day=pd.Timestamp(et).tz_convert("Asia/Tokyo").normalize(), R=r, R2=r - COST * e / abs(e - st)))
T = pd.DataFrame(rows)
# trading sessions covered (days with data), so the 2023-25 gap is not counted as time
sess = {"duk": pd.bdate_range("2021-01-06", "2023-05-15"), "broker": pd.bdate_range("2025-06-11", "2026-11-11")}
nsess = sum(len(v) for v in sess.values()); yrs = nsess / 252
print(f"trades {len(T)}, sessions {nsess} (~{yrs:.1f} yrs), trades/day {len(T)/nsess:.2f}, win {100*(T.R>0).mean():.0f}%, avgR {T.R.mean():.2f}")
for s, g in T.groupby("src"): print(f"  {s}: {len(g)} trades, R/yr {g.R.sum()/(len(sess[s])/252):.1f}, R/yr 2x cost {g.R2.sum()/(len(sess[s])/252):.1f}")
cum = T.R.cumsum(); dd = (cum - cum.cummax()).min(); ls = max(len(list(g)) for k, g in __import__("itertools").groupby(T.R < 0) if k)
dayR = T.groupby("day").R.sum()
print(f"max drawdown {dd:.1f}R, longest losing streak {ls} trades, worst day {dayR.min():.1f}R, best day {dayR.max():.1f}R")
mo = T.groupby(T.t.dt.tz_convert(None).dt.to_period("M")).R.sum()
print(f"months: {(mo>0).sum()}/{len(mo)} positive, worst month {mo.min():.1f}R, best {mo.max():.1f}R")
# FTMO 2-step on this EA alone: start on every session day, trades in order; daily guard stops the day at -4%, stop at -9.5%
days = sorted(dayR.index); dlist = [T[T.day == d].R.to_numpy() for d in days]
def run(start, risk, target):
    eq = 1.0
    for k in range(start, len(days)):
        ref = eq
        for r in dlist[k]:
            eq += risk / 100 * r * (1.0)
            if eq >= 1 + target: return "pass", k
            if eq <= 0.905: return "stopped", k
            if ref - eq >= 0.04: break
            if ref - eq >= 0.05 or eq <= 0.90: return "breach", k
    return "open", len(days)
out = []
for risk in (0.25, 0.5, 0.75, 1.0, 1.5, 2.0):
    res = []
    for s0 in range(len(days)):
        p1, k1 = run(s0, risk, 0.10)
        if p1 != "pass": res.append((p1, None)); continue
        p2, k2 = run(k1 + 1, risk, 0.05); res.append((p2, k2 - s0 + 1 if p2 == "pass" else None))
    done = [x for x in res if x[0] != "open"]; t = [x[1] for x in done if x[1]]
    # trading days with trades -> calendar days: sessions per traded day
    f = nsess / len(days) * 7 / 5
    out.append(dict(risk_per_trade=f"{risk}%", attempts=len(done), pass_pct=100 * sum(x[0] == "pass" for x in done) / len(done),
                    breach_pct=100 * sum(x[0] == "breach" for x in done) / len(done), stopped_pct=100 * sum(x[0] == "stopped" for x in done) / len(done),
                    median_days=np.median(t) * f if t else None, p80_days=np.percentile(t, 80) * f if t else None))
print(pd.DataFrame(out).round(1).to_string(index=False))
