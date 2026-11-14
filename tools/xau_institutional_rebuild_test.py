# Python rebuild of the third-party 'XAU Institutional EA v7' from its PDF (VWAP + RSI7 35/65 + candle delta, 2xATR pullback,
# SL 2xATR / TP 3xATR, trail from 0.8xATR, martingale 1-2-8). Matched to the real 2026 MT5 report per trade, then run 2020-2026.
import sys, numpy as np, pandas as pd
sys.path.insert(0, "/home/user/dbxfcvnbgfcn/tools")
from portfolio_prop import load_csv, rsi, rma
m = load_csv("fut1m/XAUUSD_1m.csv").loc["2020-01-01":]
O, H, L, C, V = m.o.to_numpy(), m.h.to_numpy(), m.l.to_numpy(), m.c.to_numpy(), m.v.to_numpy(); T = m.index
srv = (T + pd.Timedelta(hours=2)).normalize()                     # broker server day (GMT+2) for the daily VWAP
tp_ = (H + L + C) / 3
g = pd.DataFrame({"pv": tp_ * V, "v": V, "d": srv})
vwap = (g.groupby("d").pv.cumsum() / g.groupby("d").v.cumsum()).to_numpy()
R7 = rsi(m.c, 7).to_numpy()
atr = rma(pd.concat([m.h - m.l, (m.h - m.c.shift()).abs(), (m.l - m.c.shift()).abs()], axis=1).max(axis=1), 14).to_numpy()
def run(spread=0.25, mart=(1, 2, 8), pend_bars=30, trail=True):
    n = len(C); pos = 0; lvl = 0; pend = 0; pend_t = 0; pend_until = 0; out = []
    i = 20
    while i < n - 1:
        if pos == 0:
            # 1) signal on the closed bar i
            if pend == 0 or i > pend_until:
                pend = 0
                if np.isfinite(vwap[i]) and np.isfinite(atr[i]):
                    buy = C[i] > vwap[i] and (R7[i] < 35 or (R7[i-1] < 35 and R7[i] > R7[i-1])) and C[i] > O[i]
                    sell = C[i] < vwap[i] and (R7[i] > 65 or (R7[i-1] > 65 and R7[i] < R7[i-1])) and C[i] < O[i]
                    if buy or sell:
                        pend = 1 if buy else -1; pend_t = C[i] - pend * 2 * atr[i] * 0.9; pend_until = i + pend_bars
                i += 1; continue
            # 2) waiting for the pullback + a bar closing back in the trade's direction
            d = pend
            reached = (L[i] <= pend_t) if d == 1 else (H[i] >= pend_t)
            momentum = (C[i] > O[i]) if d == 1 else (C[i] < O[i])
            if reached and momentum:
                e = O[i + 1] + d * spread / 2; a = atr[i]; sl = e - d * 2 * a; tp = e + d * 3 * a
                lots = 0.01 * mart[min(lvl, len(mart) - 1)]; j = i + 1; px = None
                while j < n:
                    if (L[j] <= sl) if d == 1 else (H[j] >= sl): px = sl; break
                    if (H[j] >= tp) if d == 1 else (L[j] <= tp): px = tp; break
                    if trail:
                        best = H[j] if d == 1 else L[j]
                        if (best - e) * d >= 0.8 * a:
                            nsl = best - d * 0.5 * a
                            if (nsl - sl) * d > 0: sl = nsl
                    j += 1
                if px is None: break
                pnl = ((px - e) * d - spread / 2) * lots * 100
                out.append((T[i + 1], lots, pnl))
                lvl = 0 if pnl > 0 else (lvl + 1 if lvl + 1 < len(mart) else 0)
                pend = 0; i = j + 1; continue
            i += 1
    return pd.DataFrame(out, columns=["t", "lots", "pnl"])
def report(r, lab):
    r = r.copy(); r["yr"] = r.t.dt.year
    eq = r.pnl.cumsum(); dd = (eq - eq.cummax()).min()
    wins, losses = r.pnl[r.pnl > 0], r.pnl[r.pnl <= 0]
    print(f"\n== {lab}: trades {len(r)}, win {100*(r.pnl>0).mean():.1f}%, avg win ${wins.mean():.2f} / avg loss ${losses.mean():.2f}, PF {wins.sum()/-losses.sum():.2f}, net ${r.pnl.sum():,.0f}, max DD ${dd:,.0f}")
    y = r.groupby("yr").agg(trades=("pnl", "size"), win=("pnl", lambda x: round(100 * (x > 0).mean(), 1)), net=("pnl", "sum"))
    y["max_dd"] = [round((r[r.yr == k].pnl.cumsum() - r[r.yr == k].pnl.cumsum().cummax()).min()) for k in y.index]
    print(y.round(0).to_string())
report(run(), "rebuild, martingale on (like your test)")
report(run(mart=(1,)), "rebuild, martingale OFF")
report(run(spread=0.5), "rebuild, martingale on, double spread")

# --- yearly run with the matched settings ---
def yearly(r, lab):
    r = r.copy(); r["yr"] = r.t.dt.year
    rows = []
    for y, g in r.groupby("yr"):
        w, l = g.pnl[g.pnl > 0], g.pnl[g.pnl <= 0]
        rows.append(dict(year=y, trades=len(g), win=round(100 * (g.pnl > 0).mean(), 1), PF=round(w.sum() / -l.sum(), 2), net=round(g.pnl.sum()), gold_atr=round(float(np.nanmedian(atr[(T.year == y)])), 2), gold_price=round(float(np.nanmedian(C[(T.year == y)])))))
    print(f"\n== {lab}: total net ${r.pnl.sum():,.0f}"); print(pd.DataFrame(rows).to_string(index=False))
yearly(run(spread=0.15, pend_bars=10), "rebuild matched to your 2026 report (martingale on, spread 0.15)")
yearly(run(spread=0.15, pend_bars=10, mart=(1,)), "same, martingale OFF")
