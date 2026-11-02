# NQ dip-grid (long-only, uptrend dips, H1) with loss caps and win-focused exits, across markets.
import sys, numpy as np, pandas as pd, itertools
from multiprocessing import Pool
from futures_lab import load_csv
SP = sys.argv[1]
K = {}; exec(open(SP + "/kavach_grid_replica.py").read().split("def basket_series")[0], K)
MK = {"Nasdaq": ("fut/USATECHIDXUSD.csv", 0.00012), "S&P 500": ("fut/USA500IDXUSD.csv", 0.0001), "Dow": ("fut/USA30IDXUSD.csv", 0.00012),
      "Russell": ("fut/USSC2000IDXUSD.csv", 0.0002), "Gold": ("fut/XAUUSD.csv", 0.0001), "Silver": ("fut/XAGUSD.csv", 0.00025)}

def basket3(o, h, l, c, z, atr, ema, cost, zth, N, stopk, exit_, cut, hold, risk=0.02, Sp=1.0):
    n = len(o); r, lo = np.zeros(n), np.zeros(n); pos = None; wait = 0; nb = 0; res = []
    for i in range(300, n):
        if pos is None:
            if wait > 0: wait -= 1; continue
            if np.isnan(z[i - 1]) or np.isnan(atr[i - 1]) or z[i - 1] > -zth or c[i - 1] <= ema[i - 1]: continue
            e0, a0 = o[i], atr[i - 1]; lv = [e0 - k * Sp * a0 for k in range(N)]; sp = e0 - ((N - 1) * Sp + stopk * Sp) * a0
            unit = risk / sum((p - sp) / p for p in lv)
            pos = dict(lv=lv, sz=[unit] * N, k=1, sp=sp, a0=a0, u=0.0, t=i, trail=False, half=False, real=0.0); r[i] -= unit * cost; nb += 1
        P = pos; filled = 0
        while P["k"] < N and l[i] <= P["lv"][P["k"]] and not P["trail"]:
            r[i] -= P["sz"][P["k"]] * cost; P["k"] += 1; filled += 1
        held = list(zip(P["sz"][:P["k"]], P["lv"][:P["k"]]))
        mtm = lambda px: sum(s * (px - p) / p for s, p in held)
        hit = l[i] <= P["sp"]; u0 = P["u"]
        lo[i] = r[i] + mtm(min(P["sp"], o[i]) if hit else l[i]) - u0
        if hit:
            v = mtm(min(P["sp"], o[i])); r[i] += v - u0; res.append(P["real"] + v); pos = None; wait = 4; continue
        v = mtm(c[i]); r[i] += v - u0; P["u"] = v
        avg = sum(s * p for s, p in held) / sum(s for s, _ in held)
        done = i - P["t"] >= hold or (cut and i - P["t"] >= cut and v < 0 and not P["trail"])
        if exit_ == "z0":
            done = done or z[i] >= 0
        elif exit_ == "be":                     # z0 exit, plus stop to break-even once +1 ATR above the average
            done = done or z[i] >= 0
            if h[i] - avg >= P["a0"]: P["sp"] = max(P["sp"], avg)
        elif exit_ == "trail":                  # no z0 exit: once back at the mean, trail 1.5 ATR under the close
            if z[i] >= 0: P["trail"] = True
            if P["trail"]: P["sp"] = max(P["sp"], c[i] - 1.5 * P["a0"], avg)
        elif exit_ == "half":                   # half off at the mean, trail the rest
            if z[i] >= 0 and not P["half"]:
                P["half"] = True; P["trail"] = True; P["real"] += v / 2
                P["sz"] = [s / 2 for s in P["sz"]]; P["u"] = v / 2
            if P["trail"]: P["sp"] = max(P["sp"], c[i] - 1.5 * P["a0"], avg)
        if done:
            res.append(P["real"] + P["u"]); pos = None; wait = 4
    return r, lo, np.array(res)

GRID = list(itertools.product([2.0, 2.5], [1, 2, 3], [1.0, 0.5], ["z0", "be", "trail", "half"], [0, 6, 12]))

def job(m):
    f, cost = MK[m]; d = load_csv(SP + "/" + f).loc["2016-01-01":]
    z, atr, *_ = K["indicators"](d, 20); ema = d.c.ewm(span=200).mean().to_numpy(); o, h, l, c = (d[k].to_numpy() for k in "ohlc")
    idx = d.index; yrs = (idx[-1] - idx[0]).days / 365.25; cut_i = idx.searchsorted(pd.Timestamp("2021-07-01", tz="UTC")); fr = cut_i / len(idx)
    out = []
    for zth, N, stopk, ex, cut in GRID:
        hold = 120 if ex in ("trail", "half") else 48
        r, lo, res = basket3(o, h, l, c, z, atr, ema, cost, zth, N, stopk, ex, cut, hold)
        eq = np.cumsum(r); w = res[res > 0]; ls = res[res <= 0]; dd = np.max(np.maximum.accumulate(eq) - eq)
        out.append(dict(market=m, zth=zth, levels=N, stop=stopk, exit=ex, cut=cut, trades_mo=len(res) / yrs / 12, win=100 * len(w) / max(len(res), 1),
                        avg_win=100 * w.mean() if len(w) else 0, avg_loss=100 * ls.mean() if len(ls) else 0,
                        payoff=(w.mean() / -ls.mean()) if len(w) and len(ls) else np.nan,
                        yr=100 * r.sum() / yrs, yr_A=100 * r[:cut_i].sum() / (fr * yrs), yr_B=100 * r[cut_i:].sum() / ((1 - fr) * yrs),
                        maxdd=100 * dd, ret_dd=(100 * r.sum() / yrs) / (100 * dd) if dd > 0 else np.nan))
    return out

if __name__ == "__main__":
    with Pool(4) as p: res = p.map(job, list(MK))
    df = pd.DataFrame([x for o in res for x in o]); df.to_pickle(SP + "/dipgrid_exits.pkl")
    pd.set_option("display.width", 260); pd.set_option("display.max_columns", 30)
    print("Average %/yr by exit style (all markets):"); print(df.pivot_table(index="exit", columns="market", values="yr").round(1).to_string())
    print("\nAverage by early cut:"); print(df.pivot_table(index="cut", columns="market", values="yr").round(1).to_string())
    print("\nAverage by stop distance (1.0 = one spacing past the last level, 0.5 = half):"); print(df.pivot_table(index="stop", columns="market", values="yr").round(1).to_string())
    print("\nAverage by levels:"); print(df.pivot_table(index="levels", columns="market", values="yr").round(1).to_string())
    print("\nWin rate / payoff by exit:"); print(df.groupby("exit")[["win", "avg_win", "avg_loss", "payoff"]].mean().round(2).to_string())
    # settings that hold across markets: rank by the worst of the 4 index markets, both halves
    idxm = ["Nasdaq", "S&P 500", "Dow", "Russell"]
    keys = ["zth", "levels", "stop", "exit", "cut"]
    g = df[df.market.isin(idxm)].groupby(keys).agg(min_yr=("yr", "min"), mean_yr=("yr", "mean"), minA=("yr_A", "min"), minB=("yr_B", "min"),
                                                   mean_dd=("maxdd", "mean"), win=("win", "mean"), payoff=("payoff", "mean")).reset_index()
    print("\nBest settings across the 4 US indices (ranked by the WORST index):"); print(g.sort_values("min_yr", ascending=False).head(12).round(2).to_string(index=False))
    base = df[(df.zth == 2.0) & (df.levels == 3) & (df.stop == 1.0) & (df.exit == "z0") & (df.cut == 0)]
    print("\nBase NQ dip grid (3 levels, z0 exit) per market:"); print(base[["market", "trades_mo", "win", "avg_win", "avg_loss", "payoff", "yr", "yr_A", "yr_B", "maxdd"]].round(2).to_string(index=False))
