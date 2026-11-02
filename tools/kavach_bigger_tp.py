import sys, numpy as np, pandas as pd, itertools
src = open(sys.argv[1] + "/kavach_grid_replica.py").read().split("if __name__")[0]
src = src.replace('tp = avg + dr * T * P["a0"] / P["k"]', 'tp = avg + dr * T * P["a0"] / (P["k"] if TIGHT else 1)')
src = src.replace('wins += 1; continue', 'wins += 1; WIN.append(mtm(tp) + 0); continue').replace('r[i] += mtm(P["sp"]) - u0; pos = None', 'r[i] += mtm(P["sp"]) - u0; LOSS.append(1); pos = None')
exec(src)
pd.set_option("display.width", 250)
for m in sys.argv[2:]:
    d, cost = m15(m); idx = d.index; yrs = (idx[-1] - idx[0]).days / 365.25; cut = idx.searchsorted(pd.Timestamp("2023-01-01", tz="UTC"))
    ind = indicators(d, 50); rows = []
    for (Sp, N, mult), T, TIGHT in itertools.product([(2.0, 5, 2.0), (2.0, 5, 1.5), (2.0, 3, 2.0), (1.0, 5, 1.5)], [1, 2, 3, 5, 8, 12], [True, False]):
        WIN, LOSS = [], []
        r, lo, nb, w = basket_series(d, cost, ind, 2.0, Sp, N, mult, T, 0.02, True, 4)
        r0, *_ = basket_series(d, 0.0, ind, 2.0, Sp, N, mult, T, 0.02, True, 4)
        eq = np.cumsum(r)
        rows.append(dict(spacing=Sp, levels=N, mult=mult, tp_atr=T, tighten=TIGHT, baskets_mo=round(nb / yrs / 12), win=100 * w / nb,
                         avg_win_pct=100 * np.mean(WIN[-w:]) if w else 0, stops_mo=len(LOSS[-(nb - w):]) / yrs / 12 if nb > w else 0,
                         yr_all=100 * r.sum() / yrs, yr_nocost=100 * r0.sum() / yrs,
                         yr_2019_22=100 * r[:cut].sum() / (cut / len(r) * yrs), yr_2023_26=100 * r[cut:].sum() / ((1 - cut / len(r)) * yrs),
                         maxdd=100 * np.max(np.maximum.accumulate(eq) - eq)))
    g = pd.DataFrame(rows)
    print(f"\n===== {m}: bigger take-profits (2% worst case per basket) =====")
    print(f"profitable: {(g.yr_all>0).sum()}/{len(g)} | profitable with ZERO costs: {(g.yr_nocost>0).sum()}/{len(g)} | both halves: {((g.yr_2019_22>0)&(g.yr_2023_26>0)).sum()}/{len(g)}")
    print("average by take-profit size:"); print(g.groupby("tp_atr")[["win", "avg_win_pct", "yr_all", "yr_nocost"]].mean().round(2).to_string())
    print("best 6:"); print(g.sort_values("yr_all", ascending=False).head(6).round(2).to_string(index=False))
