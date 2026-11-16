import numpy as np, pandas as pd, itertools
from multiprocessing import Pool
src = open("strat3.py").read(); exec(src[:src.index("# 1) ORB")])
AGG = {"o": "first", "h": "max", "l": "min", "c": "last"}
def bars(s, tf): return load(s).resample(tf).agg(AGG).dropna()
# 1) D1 50-EMA trend + H4 engulfing pullback
def pullback(args):
    s, tgt = args; h4 = bars(s, "4h"); d1 = bars(s, "1D")
    ema = d1.c.ewm(span=50).mean().shift(1); trend = np.sign(d1.c.shift(1) - ema)
    tr = pd.Series(h4.index.normalize()).map(trend.reindex(trend.index.normalize()).to_dict()).values
    e20 = h4.c.ewm(span=20).mean().values; o, h, l, c = h4.o.values, h4.h.values, h4.l.values, h4.c.values; rows = []; i = 3
    while i < len(c) - 1:
        t = tr[i]
        if t == 1 and l[i - 1] <= e20[i - 1] and c[i - 1] < o[i - 1] and c[i] > o[i] and c[i] > o[i - 1] and o[i] <= c[i - 1]:
            st = min(l[i], l[i - 1]); dr = 1
        elif t == -1 and h[i - 1] >= e20[i - 1] and c[i - 1] > o[i - 1] and c[i] < o[i] and c[i] < o[i - 1] and o[i] >= c[i - 1]:
            st = max(h[i], h[i - 1]); dr = -1
        else: i += 1; continue
        en = o[i + 1]; rk = abs(en - st)
        if rk > 0 and (st - en) * dr < 0:
            res = resolve(o, h, l, c, i + 1, dr, en, st, en + dr * tgt * rk, i + 1 + 60); rows.append((h4.index[i].date(), (res - COST[s]) / rk)); i += 6; continue
        i += 1
    return stats(f"{s} D1-trend H4 engulfing pullback tgt={tgt}R", rows)
# 2) FVG retest with H4 trend (H1 bars)
def fvg(args):
    s, tgt = args; h1 = bars(s, "1h"); o, h, l, c = h1.o.values, h1.h.values, h1.l.values, h1.c.values
    e = h1.c.ewm(span=200).mean().values; rows = []; gaps = []
    for i in range(2, len(c) - 1):
        if l[i] > h[i - 2] and c[i] > e[i]: gaps.append((i, 1, h[i - 2], l[i], l[i - 1]))      # bullish gap zone [h[i-2], l[i]]
        if h[i] < l[i - 2] and c[i] < e[i]: gaps.append((i, -1, l[i - 2], h[i], h[i - 1]))
        gaps = [g for g in gaps if i - g[0] <= 24]
        for g in list(gaps):
            k, dr, edge, far, base = g
            if k == i: continue
            if (dr == 1 and l[i] <= far) or (dr == -1 and h[i] >= far):
                en = far; st = base if (base - en) * dr < 0 else edge - dr * 0.5 * abs(far - edge)
                rk = abs(en - st); gaps.remove(g)
                if rk <= 0: continue
                if (dr == 1 and l[i] <= st) or (dr == -1 and h[i] >= st): rows.append((h1.index[i].date(), (-rk - COST[s]) / rk)); continue
                res = resolve(o, h, l, c, i + 1, dr, en, st, en + dr * tgt * rk, i + 1 + 48); rows.append((h1.index[i].date(), (res - COST[s]) / rk))
    return stats(f"{s} H1 FVG retest with EMA200 trend tgt={tgt}R", rows)
# 3) Asian range sweep -> reversal at London / NY open (M15)
def sweep(args):
    s, sess, tgt = args; m = load(s).resample("15min").agg(AGG).dropna(); m.index = m.index.tz_convert("UTC")
    win = {"london": (8, 11), "ny": (13, 16)}[sess]; rows = []
    for day, g in m.groupby(m.index.date):
        if pd.Timestamp(day).dayofweek > 4: continue
        a = g[(g.index.hour < 7)]; w = g[(g.index.hour >= win[0]) & (g.index.hour < win[1])]
        if len(a) < 16 or len(w) < 8: continue
        ah, al = a.h.max(), a.l.min(); o, h, l, c = g.o.values, g.h.values, g.l.values, g.c.values; pos = {t: n for n, t in enumerate(g.index)}
        for t in w.index:
            n = pos[t]
            if n + 1 >= len(c): break
            if h[n] > ah and c[n] < ah and c[n] < o[n]: dr, st = -1, h[n]
            elif l[n] < al and c[n] > al and c[n] > o[n]: dr, st = 1, l[n]
            else: continue
            en = o[n + 1]; rk = abs(en - st) + COST[s]
            if rk <= COST[s] or (st - en) * dr >= 0: break
            res = resolve(o, h, l, c, n + 1, dr, en, st + dr * 0, en + dr * tgt * rk, len(c)); rows.append((day, (res - COST[s]) / rk)); break
    return stats(f"{s} Asian-range sweep reversal {sess} tgt={tgt}R", rows)
# 4) pairs: NQ vs SPX log-spread z-score (H1), market neutral
def pairs(args):
    look, zin = args; a = bars("NQ", "1h").c; b = bars("SPX", "1h").c; df = pd.concat([a, b], axis=1, keys=["a", "b"]).dropna()
    la, lb = np.log(df.a), np.log(df.b); beta = (la.diff().rolling(look).cov(lb.diff()) / lb.diff().rolling(look).var()).shift(1)
    sp = la - beta * lb; z = ((sp - sp.rolling(look).mean()) / sp.rolling(look).std()).shift(0)
    rows = []; pos = 0; zz = z.values; ra = la.diff().values; rb = lb.diff().values; bt = beta.values; acc = 0; vol = (la.diff() - beta * lb.diff()).rolling(look).std().values
    for i in range(look * 2, len(zz) - 1):
        if pos:
            acc += pos * (ra[i + 1] - b0 * rb[i + 1])
            if abs(zz[i]) < 0.2 or abs(zz[i]) > zin + 2 or i - i0 > 120:
                rows.append((df.index[i].date(), (acc - 0.0004) / r0)); pos = 0
            continue
        if abs(zz[i]) > zin and not np.isnan(bt[i]): pos = -np.sign(zz[i]); b0 = bt[i]; acc = 0; i0 = i; r0 = 2 * vol[i] * np.sqrt(24)
    return stats(f"NQ/SPX pairs z>{zin} look={look}h", rows)
def run(fa): return fa[0](fa[1])
if __name__ == "__main__":
    J = [(pullback, a) for a in itertools.product(["NQ", "SPX", "GOLD"], [2, 3])]
    J += [(fvg, a) for a in itertools.product(["NQ", "SPX", "GOLD"], [2, 3])]
    J += [(sweep, a) for a in itertools.product(["NQ", "SPX", "GOLD"], ["london", "ny"], [1.5, 2])]
    J += [(pairs, a) for a in itertools.product([120, 480], [2.0, 2.5])]
    with Pool(4) as p: R = [r for r in p.map(run, J) if r]
    R = pd.DataFrame(R).sort_values("R_per_yr", ascending=False); R.to_pickle("strat4.pkl"); pd.set_option("display.width", 250)
    print(R.to_string(index=False))
