# Tick replay of 3-10 point Nasdaq scalps on RoboForex .USTECHCash ticks (Nov 6-12 2026): fills at ask/bid, 900 random NY-hours entries; compared with 1m-bar fair / best-case counts.
import numpy as np, pandas as pd
f = "ticks_in/.USTECHCash_202611061900_202611121702.csv"
t = pd.read_csv(f, sep="\t", usecols=[0, 1, 2, 3]); t.columns = ["d", "tm", "bid", "ask"]
t[["bid", "ask"]] = t[["bid", "ask"]].ffill(); t = t.dropna()
ts = pd.to_datetime(t.d + " " + t.tm, format="%Y.%m.%d %H:%M:%S.%f") - pd.Timedelta(hours=2)    # server GMT+2 in November -> UTC
ny = ts.dt.tz_localize("UTC").dt.tz_convert("America/New_York")
B, A = t.bid.to_numpy(), t.ask.to_numpy(); TS = ts.to_numpy(); m = (ny.dt.hour * 60 + ny.dt.minute).to_numpy()
rth = (m >= 570) & (m < 960)
sp = (A - B)[rth]
print(f"ticks {len(B):,}; New York 09:30-16:00 spread (points): median {np.median(sp):.1f}, 10% {np.percentile(sp,10):.1f}, 90% {np.percentile(sp,90):.1f}")
print("by hour (NY):", pd.Series(A - B)[rth].groupby(ny.dt.hour[rth].values).median().round(1).to_dict())
# random entries during 09:35-15:30 New York, one every ~2 minutes, random side
rng = np.random.default_rng(3)
cand = np.where((m >= 575) & (m < 930))[0]
picks = np.sort(rng.choice(cand, 900, replace=False)); sides = rng.choice([-1, 1], len(picks))
# 1-minute bars of the mid price, to compare the bar-based "fair" and "best-case" counts with the tick truth
mid = (A + B) / 2; minute = (TS.astype("datetime64[m]"))
bars = pd.DataFrame({"m": minute, "mid": mid}).groupby("m").mid.agg(["first", "max", "min", "last"])
bidx = bars.index.to_numpy(); BH, BL = bars["max"].to_numpy(), bars["min"].to_numpy()
rows = []
for tp in (3, 6, 10):
    for sl in (3, 6, 10, 20):
        tick_r, fair_r, best_r = [], [], []
        for i, d in zip(picks, sides):
            e = A[i] if d == 1 else B[i]                      # fill at the ask (buy) / bid (sell)
            j1 = min(i + 400000, len(B))
            px = B[i:j1] if d == 1 else A[i:j1]              # exit side
            hit_tp = np.where((px - e) * d >= tp)[0]; hit_sl = np.where((px - e) * d <= -sl)[0]
            a = hit_tp[0] if len(hit_tp) else 10**9; b = hit_sl[0] if len(hit_sl) else 10**9
            if a == b == 10**9: continue
            tick_r.append(tp if a < b else -sl)
            # bar version: entry at mid +- half the median spread, exits on mid with the other half
            k = np.searchsorted(bidx, minute[i]); em = mid[i]; hs = np.median(sp) / 2; res_f = res_b = None
            for q in range(k, min(k + 400, len(bidx))):
                up = (BH[q] - em) * d if d == 1 else (em - BL[q]); dn = (em - BL[q]) if d == 1 else (BH[q] - em)
                htp = up >= tp + 2 * hs; hsl = dn >= sl - 0
                if htp and hsl: res_f, res_b = -sl, tp; break
                if hsl: res_f = res_b = -sl; break
                if htp: res_f = res_b = tp; break
            if res_f is None: tick_r.pop(); continue
            fair_r.append(res_f); best_r.append(res_b)
        r = np.array(tick_r); n = len(r)
        rows.append(dict(tp=tp, sl=sl, entries=n, tick_win=round(100 * (r > 0).mean(), 1), tick_avg_pts=round(r.mean(), 2), usd_50lots=round(50 * r.mean()),
                         bars_fair_avg=round(np.mean(fair_r), 2), bars_best_avg=round(np.mean(best_r), 2), breakeven_win=round(100 * sl / (tp + sl), 1)))
pd.set_option("display.width", 250); print(pd.DataFrame(rows).to_string(index=False))
