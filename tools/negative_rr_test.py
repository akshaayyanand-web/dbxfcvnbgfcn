# Run from the scratchpad (needs world_lab.py and data).
# Negative risk:reward test: small take-profit vs wider stop, on existing entries and on a classic 5m dip scalp.
import sys, numpy as np, pandas as pd
def run_lab(sym):
    sys.argv = ["x", sym]; ns = {}
    exec(open("world_lab.py").read().split("rows, TR = [], {}")[0], ns); return ns
def summarize(tr, cost, name):
    R = np.array([(px - e) / abs(e - st) * np.sign(e - st) - cost * e / abs(e - st) for et, xt, e, st, px in tr])
    t = pd.DatetimeIndex([x[0] for x in tr]); A = t < pd.Timestamp("2023-01-01", tz="UTC")
    ya = max((t[A][-1] - t[A][0]).days / 365.25, 0.5); yb = max((t[~A][-1] - t[~A][0]).days / 365.25, 0.5)
    streak = mx = 0
    for r in R:
        streak = streak + 1 if r < 0 else 0; mx = max(mx, streak)
    eq = np.cumsum(R); dd = np.max(np.maximum.accumulate(eq) - eq)
    return dict(test=name, trades_mo=len(R) / ((t[-1] - t[0]).days / 30.4), win_pct=100 * (R > 0).mean(), avg_win=R[R > 0].mean(), avg_loss=R[R <= 0].mean(),
                avgR=R.mean(), yrA=R[A].sum() / ya, yrB=R[~A].sum() / yb, worst_streak=mx, maxDD_R=dd)
rows = []
# 1) DAX ORB (the core EA's entry) with small targets vs no target
ns = run_lab("DEUIDXEUR"); DAXNS = ns; b = ns["bars"]("15min"); T = b.index; fr = T.tz_convert(ns["TZ"]); fm = (fr.hour * 60 + fr.minute).to_numpy(); fday = fr.normalize()
H, L, C = b.h.to_numpy(), b.l.to_numpy(), b.c.to_numpy(); dc = b.c.resample("1D").last().dropna()
ema = dc.ewm(span=50, adjust=False).mean().shift(1).reindex(T.floor("D"), method="ffill").to_numpy()
inr = (fm >= 540) & (fm < 570)
g = pd.DataFrame({"h": np.where(inr, H, np.nan), "l": np.where(inr, L, np.nan), "d": fday}).groupby("d").agg(h=("h", "max"), l=("l", "min"))
orh = g.h.reindex(fday).to_numpy(); orl = g.l.reindex(fday).to_numpy()
def sig(i):
    if not np.isfinite(orh[i]): return 0
    d = 1 if C[i] > orh[i] else (-1 if C[i] < orl[i] else 0)
    return d if d and (C[i] - ema[i]) * d > 0 else 0
for tg in (0.25, 0.33, 0.5, 0.75, 1.0, 0):
    tr = ns["intraday_sim"](b, sig, lambda i, d, e: (orh[i] + orl[i]) / 2, tg, 1045, 570, 720)
    rows.append(summarize(tr, ns["COST"], f"DAX ORB, target {tg if tg else 'none (current EA)'}R"))
# 2) NQ ORB (core EA) with small targets vs 2R
sys.path.insert(0, "/home/user/dbxfcvnbgfcn/tools"); import orb_lab as O
from portfolio_prop import load_csv
nq5 = O.five_min(load_csv("fut1m/USATECHIDXUSD_1m.csv")); cst = O.COST["USATECHIDXUSD"]
for tg in (0.25, 0.33, 0.5, 0.75, 1.0, 2.0):
    x = O.orb(nq5, "America/New_York", (9, 30), (11, 30), (15, 55), 15, "other", tg, True, cst)
    rows.append(summarize([a[:5] for a in x], cst, f"NQ ORB, target {tg}R" + (" (current EA)" if tg == 2.0 else "")))
# 3) classic negative-RR scalp: 5m RSI(2) dip above EMA200, TP = k x ATR, SL = 3k x ATR (1:3), flat after 2h
for sym in ("USATECHIDXUSD", "XAUUSD_NY", "DEUIDXEUR"):
    ns = run_lab(sym) if sym != "DEUIDXEUR" else DAXNS
    b = ns["bars"]("5min"); c = b.c; O_, H, L, C = (b[k].to_numpy() for k in "ohlc"); T = b.index
    from portfolio_prop import rsi
    r2 = rsi(c, 2).to_numpy(); e200 = c.ewm(span=200, adjust=False).mean().to_numpy(); atr = ns["atr_of"](b)
    for tp_k, sl_k in ((0.5, 1.5), (0.5, 2.0), (1.0, 3.0), (1.0, 1.0)):
        out, i = [], 0
        while i < len(C) - 2:
            if not (r2[i] < 10 and C[i] > e200[i] and np.isfinite(atr[i])): i += 1; continue
            j = i + 1; e = O_[j]; st = e - sl_k * atr[i]; tg = e + tp_k * atr[i]; k = j; px = None
            while k < len(C) - 1:
                if L[k] <= st: px, xt = min(O_[k], st), T[k]; break
                if H[k] >= tg: px, xt = max(O_[k], tg), T[k]; break
                if k - j >= 24: px, xt = O_[k + 1], T[k + 1]; break
                k += 1
            if px is None: break
            out.append((T[j], xt, e, st, px)); i = k + 1
        rows.append(summarize(out, ns["COST"], f"{sym.split('_')[0][:6]} 5m dip scalp TP {tp_k} ATR / SL {sl_k} ATR (RR 1:{sl_k / tp_k:g})"))
df = pd.DataFrame(rows); pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 80)
print(df.round(2).to_string(index=False))
