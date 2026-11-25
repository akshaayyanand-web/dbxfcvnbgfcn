# "Win $350 per trade" / "one trade = $1K" / "80-85% win rate" on The5ers High Stakes $10K, using the 21 EAs' real entries.
# Each trade re-simulated on 5-minute bars: stop = k x the EA's own stop distance, target = r x stop, conservative (stop first inside a bar).
# Variant 'native': exit at the EA's own time exit if neither is hit. Variant 'hold': hold until TP or SL (10-day cap).
# Costs: the EA's own cost in R, scaled by 1/k (wider stop = smaller position = same cost in price).
import sys, numpy as np, pandas as pd
exec(open("stopsize.py").read().split("\nREAL = ")[0])
from multiprocessing import Pool
def resim(c, k, r, mode):
    B = BARS[INS[c]]; T = B.index; O, H, L, C = B.o.to_numpy(), B.h.to_numpy(), B.l.to_numpy(), B.c.to_numpy(); out = []
    for et, xt, e, sd, d, rr0, px in TR[c]:
        cost_r = d * (px - e) / sd - rr0; s = k * sd; sl, tp = e - d * s, e + d * r * s
        t_end = xt if mode == "native" else et + pd.Timedelta(days=10)
        i, j = T.searchsorted(et), min(T.searchsorted(t_end, "right"), len(T))   # include the exit bar
        if i >= len(T) or j <= i: continue
        res, x, tx = None, None, None
        for q in range(i, j):
            if (d > 0 and L[q] <= sl) or (d < 0 and H[q] >= sl): res, x, tx = "loss", sl, T[q]; break
            if (d > 0 and H[q] >= tp) or (d < 0 and L[q] <= tp): res, x, tx = "win", tp, T[q]; break
        if res is None: res, x, tx = "time", C[j - 1], T[j - 1]
        out.append((et, tx, res, d * (x - e) / s - max(cost_r, 0) / k))      # outcome in units of the stop ($ risk)
    return pd.DataFrame(out, columns=["et", "xt", "res", "R"])
def job(a):
    c, k, r, mode = a
    try: D = resim(c, k, r, mode)
    except Exception as ex: return None
    if len(D) < 30: return None
    S = pd.Timestamp("2023-01-01", tz="UTC")
    return dict(ea=c, k=k, r=r, mode=mode, trades=len(D), win=round(100 * (D.res == "win").mean(), 1), loss=round(100 * (D.res == "loss").mean(), 1),
                time=round(100 * (D.res == "time").mean(), 1), avgR=round(D.R.mean(), 3), avgR_2023on=round(D[D.et >= S].R.mean(), 3), trades_per_yr=round(len(D) / max((D.et.max() - D.et.min()).days / 365, 0.5), 1))
if __name__ == "__main__":
    jobs = [(c, k, r, m) for c in TR for k in (1, 2, 3) for r in (0.25, 0.5, 0.875, 2.5) for m in ("native", "hold")]
    with Pool(4) as p: res = [x for x in p.map(job, jobs) if x]
    W = pd.DataFrame(res); W.to_csv("fixedtp_winrates.csv", index=False); pd.set_option("display.width", 250); pd.set_option("display.max_rows", 400)
    print("WIN RATE by EA (best mode per EA/k/r shown sorted):")
    print(W.sort_values(["r", "win"], ascending=[True, False]).groupby("r").head(12).to_string(index=False))
    print("\nEAs reaching >= 80% win rate:"); print(W[W.win >= 80].sort_values("avgR", ascending=False).to_string(index=False))
