# Original Kavach (fade |Z|>=2 both ways on M15, Kavach regime gate, grid basket) with loss caps and win-focused exits.
import sys, os, numpy as np, pandas as pd, itertools
from multiprocessing import Pool
SP = sys.argv[1]
K = {}; exec(open(SP + "/kavach_grid_replica.py").read().split("def basket_series")[0], K)

def basket(o, h, l, c, z, atr, gate_arr, cost, N, mult, Sp, stopk, exit_, cut, hold, zth=2.0, risk=0.02):
    n = len(o); r, lo = np.zeros(n), np.zeros(n); pos = None; wait = 0; res = []
    for i in range(500, n):
        if pos is None:
            if wait > 0: wait -= 1; continue
            zz = z[i - 1]
            if np.isnan(zz) or np.isnan(atr[i - 1]) or abs(zz) < zth or gate_arr[i - 1]: continue
            dr = -1 if zz > 0 else 1; e0, a0 = o[i], atr[i - 1]
            lv = [e0 - dr * k * Sp * a0 for k in range(N)]; sz = [mult ** k for k in range(N)]; sp = e0 - dr * ((N - 1) * Sp + stopk * Sp) * a0
            unit = risk / sum(s * abs(p - sp) / p for s, p in zip(sz, lv))
            pos = dict(d=dr, lv=lv, sz=[s * unit for s in sz], k=1, sp=sp, a0=a0, u=0.0, t=i, trail=False, half=False, real=0.0); r[i] -= unit * cost
        P = pos; dr = P["d"]; adv = l[i] if dr == 1 else h[i]; fav = h[i] if dr == 1 else l[i]; filled = 0
        while P["k"] < N and not P["trail"] and (adv - P["lv"][P["k"]]) * dr <= 0:
            r[i] -= P["sz"][P["k"]] * cost; P["k"] += 1; filled += 1
        held = list(zip(P["sz"][:P["k"]], P["lv"][:P["k"]]))
        mtm = lambda px: sum(s * dr * (px - p) / p for s, p in held)
        hit = (adv - P["sp"]) * dr <= 0; u0 = P["u"]
        fillpx = (min if dr == 1 else max)(P["sp"], o[i])
        lo[i] = r[i] + mtm(fillpx if hit else adv) - u0
        if hit:
            v = mtm(fillpx); r[i] += v - u0; res.append(P["real"] + v); pos = None; wait = 4; continue
        avg = sum(s * p for s, p in held) / sum(s for s, _ in held)
        if exit_ == "tp":                         # Kavach's own: TP = average + 1 ATR / levels filled
            tp = avg + dr * P["a0"] / P["k"]
            if not filled and (fav - tp) * dr >= 0:
                v = mtm(tp); r[i] += v - u0; res.append(P["real"] + v); pos = None; wait = 4; continue
        v = mtm(c[i]); r[i] += v - u0; P["u"] = v
        back = z[i] * dr >= 0                     # price back at its 20-bar mean
        done = i - P["t"] >= hold or (cut and i - P["t"] >= cut and v < 0 and not P["trail"])
        if exit_ == "z0": done = done or back
        elif exit_ == "be":
            done = done or back
            if (fav - avg) * dr >= P["a0"]: P["sp"] = avg if (avg - P["sp"]) * dr > 0 else P["sp"]
        elif exit_ in ("trail", "half"):
            if back and not P["trail"]:
                P["trail"] = True
                if exit_ == "half":
                    P["real"] += v / 2; P["sz"] = [s / 2 for s in P["sz"]]; P["u"] = v / 2
            if P["trail"]:
                cand = max((c[i] - dr * 1.5 * P["a0"]) * dr, avg * dr) * dr
                if (cand - P["sp"]) * dr > 0: P["sp"] = cand
        if done:
            res.append(P["real"] + P["u"]); pos = None; wait = 4
    return r, lo, np.array(res)

GRID = list(itertools.product([1, 3, 5], [1.0, 1.5], [1.0, 2.0], [1.0, 0.5, 0.25], ["tp", "z0", "be", "trail", "half"], [0, 8, 16]))

def job(m):
    d, cost = K["m15"](m); z, atr, adx, vr, don = K["indicators"](d, 20); gate_arr = (vr > 1.1) | (adx > 25) | don | np.isnan(vr)
    o, h, l, c = (d[k].to_numpy() for k in "ohlc"); idx = d.index; yrs = (idx[-1] - idx[0]).days / 365.25
    cut_i = idx.searchsorted(pd.Timestamp("2023-01-01", tz="UTC")); fr = cut_i / len(idx); out = []
    for N, mult, Sp, stopk, ex, cut in GRID:
        if N == 1 and mult != 1.0: continue
        r, lo, res = basket(o, h, l, c, z, atr, gate_arr, cost, N, mult, Sp, stopk, ex, cut, 480 if ex in ("trail", "half") else 192)
        eq = np.cumsum(r); w = res[res > 0]; ls = res[res <= 0]; dd = np.max(np.maximum.accumulate(eq) - eq)
        out.append(dict(market=m, levels=N, mult=mult, spacing=Sp, stop=stopk, exit=ex, cut=cut, trades_mo=len(res) / yrs / 12,
                        win=100 * len(w) / max(len(res), 1), avg_win=100 * w.mean() if len(w) else 0, avg_loss=100 * ls.mean() if len(ls) else 0,
                        yr=100 * r.sum() / yrs, yr_A=100 * r[:cut_i].sum() / (fr * yrs), yr_B=100 * r[cut_i:].sum() / ((1 - fr) * yrs), maxdd=100 * dd))
    print(m, "done", flush=True)
    return out

if __name__ == "__main__":
    mk = [m for m in ("Gold", "Nasdaq", "BTC", "EURUSD", "AUDCAD") if os.path.exists(SP + "/" + K["SRC"][m][0])]
    with Pool(min(4, len(mk))) as p: res = p.map(job, mk)
    df = pd.DataFrame([x for o in res for x in o]); df.to_pickle(SP + "/kavach_exits.pkl")
    pd.set_option("display.width", 260); pd.set_option("display.max_columns", 30)
    print(f"\nprofitable settings per market (of {len(df)//len(mk)}):", df[df.yr > 0].market.value_counts().to_dict())
    print("profitable in BOTH 2019-22 and 2023-26:", df[(df.yr_A > 0) & (df.yr_B > 0)].market.value_counts().to_dict())
    for col in ("exit", "stop", "cut", "levels"):
        print(f"\naverage %/yr by {col}:"); print(df.pivot_table(index=col, columns="market", values="yr").round(1).to_string())
    print("\nwin rate / average win / average loss by exit:"); print(df.groupby("exit")[["win", "avg_win", "avg_loss"]].mean().round(2).to_string())
    for m, g in df.groupby("market"):
        print(f"\n{m}: best 5 overall"); print(g.sort_values("yr", ascending=False).head(5).round(2).to_string(index=False))
