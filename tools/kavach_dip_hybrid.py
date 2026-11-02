# Kavach x what worked before: fade only DOWN moves (Z <= -zth) while the trend is up (close > EMA200),
# optional Kavach regime gate, optional grid levels, exit when Z gets back to 0 (price back at its mean) or ATR TP,
# 48-hour time exit, hard stop one spacing past the last level sized to `risk` worst case.
import sys, numpy as np, pandas as pd, itertools
from multiprocessing import Pool
exec(open(sys.argv[1] + "/kavach_grid_replica.py").read().split("def basket_series")[0])

def basket2(o, h, l, c, z, atr, ema, gate_arr, cost, zth, trend, gate, N, mult, Sp, exit_, hold, risk=0.02, longonly=True):
    n = len(o); r, lo = np.zeros(n), np.zeros(n); pos = None; wait = 0; nb = 0; wins = 0
    for i in range(900, n):
        if pos is None:
            if wait > 0: wait -= 1; continue
            zz = z[i - 1]
            if np.isnan(zz) or np.isnan(atr[i - 1]) or abs(zz) < zth: continue
            dr = 1 if zz < 0 else -1
            if longonly and dr == -1: continue
            if trend and (c[i - 1] - ema[i - 1]) * dr <= 0: continue
            if gate and gate_arr[i - 1]: continue
            e0, a0 = o[i], atr[i - 1]
            lv = [e0 - dr * k * Sp * a0 for k in range(N)]; sz = [mult ** k for k in range(N)]; sp = e0 - dr * N * Sp * a0
            unit = risk / sum(s * abs(sp - p) / p for s, p in zip(sz, lv))
            pos = dict(d=dr, lv=lv, sz=[s * unit for s in sz], k=1, sp=sp, a0=a0, u=0.0, t=i); r[i] -= pos["sz"][0] * cost; nb += 1
        P = pos; dr = P["d"]; adv = l[i] if dr == 1 else h[i]; fav = h[i] if dr == 1 else l[i]; filled = 0
        while P["k"] < N and (adv - P["lv"][P["k"]]) * dr <= 0:
            r[i] -= P["sz"][P["k"]] * cost; P["k"] += 1; filled += 1
        held = list(zip(P["sz"][:P["k"]], P["lv"][:P["k"]]))
        mtm = lambda px: sum(s * dr * (px - p) / p for s, p in held)
        hit = (adv - P["sp"]) * dr <= 0; u0 = P["u"]
        lo[i] = r[i] + mtm(P["sp"] if hit else adv) - u0
        if hit:
            r[i] += mtm(P["sp"]) - u0; pos = None; wait = 4; continue
        if exit_ == "tp":
            avg = sum(s * p for s, p in held) / sum(s for s, _ in held); tp = avg + dr * P["a0"] / P["k"]
            if not filled and (fav - tp) * dr >= 0:
                r[i] += mtm(tp) - u0; pos = None; wait = 4; wins += 1; continue
        done = (exit_ == "z0" and z[i] * dr >= 0) or (i - P["t"] >= hold)
        v = mtm(c[i])
        if done:
            r[i] += v - u0; pos = None; wait = 4; wins += v > 0; continue
        P["u"] = v; r[i] += v - u0
    return r, lo, nb, wins

GRID = list(itertools.product(["M15", "H1"], [2.0, 2.5], [True, False], [False, True], [(1, 1.0), (3, 1.0), (3, 1.5), (3, 2.0)], [1.0, 2.0], ["z0", "tp"]))

def market(m):
    d15, cost = m15(m); out = []
    for tf in ("M15", "H1"):
        d = d15 if tf == "M15" else d15.resample("1h").agg(dict(o="first", h="max", l="min", c="last")).dropna()
        z, atr, adx, vr, don = indicators(d, 20); gate_arr = (vr > 1.1) | (adx > 25) | don | np.isnan(vr)
        ema = d.c.ewm(span=200).mean().to_numpy(); o, h, l, c = (d[k].to_numpy() for k in "ohlc")
        idx = d.index; yrs = (idx[-1] - idx[0]).days / 365.25; cut = idx.searchsorted(pd.Timestamp("2023-01-01", tz="UTC")); f = cut / len(idx)
        hold = 192 if tf == "M15" else 48
        for _, zth, trend, gate, (N, mult), Sp, ex in [g for g in GRID if g[0] == tf]:
            r, lo, nb, w = basket2(o, h, l, c, z, atr, ema, gate_arr, cost, zth, trend, gate, N, mult, Sp, ex, hold)
            r0, *_ = basket2(o, h, l, c, z, atr, ema, gate_arr, 0.0, zth, trend, gate, N, mult, Sp, ex, hold)
            eq = np.cumsum(r)
            out.append(dict(market=m, tf=tf, zth=zth, uptrend_only=trend, kavach_gate=gate, levels=N, mult=mult, spacing=Sp, exit=ex,
                            trades_mo=round(nb / yrs / 12, 1), win=round(100 * w / max(nb, 1), 1), yr=100 * r.sum() / yrs, yr_nocost=100 * r0.sum() / yrs,
                            yr_19_22=100 * r[:cut].sum() / (f * yrs), yr_23_26=100 * r[cut:].sum() / ((1 - f) * yrs),
                            maxdd=100 * np.max(np.maximum.accumulate(eq) - eq)))
    return out

if __name__ == "__main__":
    mk = sys.argv[2:]
    with Pool(len(mk)) as p: res = p.map(market, mk)
    df = pd.DataFrame([x for o in res for x in o]); df.to_pickle(sys.argv[1] + "/kavach_v2.pkl")
    pd.set_option("display.width", 260)
    for m, g in df.groupby("market"):
        print(f"\n===== {m} ({len(g)} settings, long-only dip buying, 2% worst case per trade/basket) =====")
        print(f"profitable: {(g.yr>0).sum()} | profitable in BOTH 2019-22 and 2023-26: {((g.yr_19_22>0)&(g.yr_23_26>0)).sum()}")
        for col in ("uptrend_only", "kavach_gate", "levels", "exit", "tf"):
            print(f"  avg %/yr by {col}:", g.groupby(col).yr.mean().round(1).to_dict())
        print(g.groupby(["levels", "mult"]).yr.mean().round(1).to_string())
        print("top 8 picked on 2019-22 -> result 2023-26:")
        print(g.sort_values("yr_19_22", ascending=False).head(8).round(1).to_string(index=False))
