import numpy as np, pandas as pd, itertools, sys
from multiprocessing import Pool
df = pd.read_csv("fut1m/USATECHIDXUSD_1m.csv", parse_dates=["t"]).set_index("t")
df.index = df.index.tz_convert("America/New_York")
df = df[(df.index.time >= pd.Timestamp("09:30").time()) & (df.index.time < pd.Timestamp("16:00").time()) & (df.index.dayofweek < 5)]
DAYS = []
for d, g in df.groupby(df.index.date):
    if len(g) < 300: continue
    DAYS.append((d, g.index.hour.values * 60 + g.index.minute.values, g.o.values, g.h.values, g.l.values, g.c.values, g.v.values))
COST = 1.5   # points, spread + slippage round trip
def run(p):
    rng, stopm, tgt, last, vol, wd = p
    out = []
    for d, mins, o, h, l, c, v in DAYS:
        if wd and pd.Timestamp(d).dayofweek in wd: continue
        r0 = mins < 570 + rng
        if r0.sum() < rng * 0.8: continue
        hi, lo = h[r0].max(), l[r0].min(); width = hi - lo
        if width <= 0: continue
        # 5-minute closes after the range
        start = np.argmax(~r0); trade = None
        k = start
        while k + 5 <= len(c) and mins[k] < last:
            cl = c[k + 4]; vv = v[k:k + 5].sum(); vavg = np.mean([v[j:j + 5].sum() for j in range(max(0, k - 100), k, 5)]) if k >= 10 else vv
            dirn = 1 if cl > hi else (-1 if cl < lo else 0)
            if dirn and (vol == 0 or vv >= vol * vavg):
                entry = cl; stop = (lo if dirn == 1 else hi) if stopm == "range" else (hi + lo) / 2
                risk = abs(entry - stop)
                if risk > 0: trade = (k + 5, dirn, entry, stop, risk)
                break
            k += 5
        if not trade: continue
        j0, dr, en, st, rk = trade; tp = en + dr * tgt * rk if tgt else None; res = None
        for j in range(j0, len(c)):
            if dr == 1:
                if l[j] <= st: res = (st - en); break
                if tp and h[j] >= tp: res = tp - en; break
            else:
                if h[j] >= st: res = en - st; break
                if tp and l[j] <= tp: res = en - tp; break
            if mins[j] >= 955: res = (c[j] - en) * dr; break
        if res is None: res = (c[-1] - en) * dr
        out.append((d, (res - COST) / rk, rk))
    t = pd.DataFrame(out, columns=["d", "R", "risk"])
    if len(t) < 50: return None
    eq = t.R.cumsum(); dd = (eq - eq.cummax()).min()
    los = (t.R < 0).astype(int); streak = (los.groupby((los != los.shift()).cumsum()).cumsum()).max()
    yrs = pd.Series(t.R.values, index=pd.to_datetime(t.d)).groupby(lambda x: x.year).sum().round(1).to_dict()
    return dict(rng=rng, stop=stopm, tgt=tgt, last=last, vol=vol, skipdays=str(wd), n=len(t), win=round(100 * (t.R > 0).mean()), avgR=round(t.R.mean(), 3),
                PF=round(t.R[t.R > 0].sum() / -t.R[t.R < 0].sum(), 2), maxDD_R=round(dd, 1), losestreak=int(streak), worst_year=min(yrs.values()), years=yrs)
if __name__ == "__main__":
    grid = list(itertools.product([15], ["range", "mid"], [0, 1, 1.5, 2, 3], [600, 660, 720], [0, 1.5], [(), (0,), (4,)]))
    with Pool() as p: R = [r for r in p.map(run, grid) if r]
    R = pd.DataFrame(R).sort_values("avgR", ascending=False); pd.set_option("display.width", 300); pd.set_option("display.max_colwidth", 120)
    R.to_pickle("nqorb.pkl"); print(R.head(15).to_string(index=False)); print(len(R), "variants; share with avgR>0:", round((R.avgR > 0).mean(), 2))
