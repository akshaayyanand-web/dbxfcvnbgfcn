import numpy as np, pandas as pd, itertools
from multiprocessing import Pool
FILES = {"NQ": "USATECHIDXUSD", "SPX": "USA500IDXUSD", "GOLD": "XAUUSD"}
COST = {"NQ": 1.5, "SPX": 0.5, "GOLD": 0.35}
def load(s):
    d = pd.read_csv(f"fut1m/{FILES[s]}_1m.csv", parse_dates=["t"]).set_index("t")[["o", "h", "l", "c"]]
    d.index = d.index.tz_convert("America/New_York"); return d
def stats(name, rows):
    t = pd.DataFrame(rows, columns=["d", "R"])
    if len(t) < 40: return None
    eq = t.R.cumsum(); yrs = t.groupby(pd.to_datetime(t.d).dt.year).R.sum().round(1)
    nyr = len(t) / max(1, (pd.to_datetime(t.d).max() - pd.to_datetime(t.d).min()).days / 365.25)
    return dict(strategy=name, n=len(t), per_yr=round(nyr), win=round(100 * (t.R > 0).mean()), avgR=round(t.R.mean(), 3),
                PF=round(t.R[t.R > 0].sum() / max(1e-9, -t.R[t.R < 0].sum()), 2), R_per_yr=round(t.R.mean() * nyr, 1), maxDD_R=round((eq - eq.cummax()).min(), 1),
                losing_years=int((yrs < 0).sum()), y2026=yrs.get(2026, 0.0))
def resolve(o, h, l, c, j0, dr, en, st, tp, jmax):
    for j in range(j0, min(jmax, len(c))):
        if dr == 1:
            if l[j] <= st: return st - en
            if tp is not None and h[j] >= tp: return tp - en
        else:
            if h[j] >= st: return en - st
            if tp is not None and l[j] <= tp: return en - tp
    j = min(jmax, len(c)) - 1; return (c[j] - en) * dr
# 1) ORB break-and-retest (indices, NY open)
def retest(args):
    s, stopm, tgt, wait = args; d = load(s); d = d[(d.index.dayofweek < 5)]
    d = d.between_time("09:30", "15:59"); rows = []
    for day, g in d.groupby(d.index.date):
        if len(g) < 300: continue
        m = g.index.hour.values * 60 + g.index.minute.values; o, h, l, c = g.o.values, g.h.values, g.l.values, g.c.values
        r = m < 585
        if r.sum() < 10 or r.all(): continue
        hi, lo = h[r].max(), l[r].min(); mid = (hi + lo) / 2
        k = np.argmax(~r); sig = None
        while k + 5 <= len(c) and m[k] < 660:
            cl = c[k + 4]
            if cl > hi: sig = (k + 5, 1); break
            if cl < lo: sig = (k + 5, -1); break
            k += 5
        if not sig: continue
        j0, dr = sig; lvl = hi if dr == 1 else lo; st = (lo if dr == 1 else hi) if stopm == "range" else mid
        fill = None
        for j in range(j0, len(c)):
            if m[j] >= 570 + 15 + wait or m[j] >= 900: break
            if (dr == 1 and l[j] <= lvl) or (dr == -1 and h[j] >= lvl):
                fill = j; break
            if (dr == 1 and l[j] <= st) or (dr == -1 and h[j] >= st): break
        if fill is None: continue
        rk = abs(lvl - st)
        if rk <= 0: continue
        tp = lvl + dr * tgt * rk if tgt else None
        eod = int(np.searchsorted(m, 955)); res = resolve(o, h, l, c, fill + 1, dr, lvl, st, tp, max(eod, fill + 2))
        rows.append((day, (res - COST[s]) / rk))
    return stats(f"{s} ORB retest stop={stopm} tgt={tgt} wait={wait}m", rows)
# 2) price action: pin bar rejecting the previous day's high/low, 1:R target
def pinbar(args):
    s, tf, tgt, wick = args; d = load(s).resample(tf).agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()
    day = d.index.date; dd = d.groupby(day).agg(h=("h", "max"), l=("l", "min")); pdh = pd.Series(day).map(dd.h.shift(1)).values; pdl = pd.Series(day).map(dd.l.shift(1)).values
    o, h, l, c = d.o.values, d.h.values, d.l.values, d.c.values; rows = []; i = 1; hold = 24 if tf == "1h" else 64
    while i < len(c) - 1:
        rg = h[i] - l[i]
        if rg > 0 and not np.isnan(pdh[i]):
            up = h[i] - max(o[i], c[i]); dn = min(o[i], c[i]) - l[i]; dr = 0
            if up >= wick * rg and h[i] > pdh[i] and c[i] < pdh[i]: dr = -1; st = h[i] + 0.05 * rg
            elif dn >= wick * rg and l[i] < pdl[i] and c[i] > pdl[i]: dr = 1; st = l[i] - 0.05 * rg
            if dr:
                en = o[i + 1]; rk = abs(en - st)
                if rk > 0 and (st - en) * dr < 0:
                    tp = en + dr * tgt * rk; res = resolve(o, h, l, c, i + 1, dr, en, st, tp, i + 1 + hold)
                    rows.append((d.index[i].date(), (res - COST[s]) / rk)); i += hold // 4; continue
        i += 1
    return stats(f"{s} pin bar at prior-day H/L {tf} tgt={tgt}R wick>={wick}", rows)
# 3) trend following: Donchian breakout, ATR chandelier trail
def donchian(args):
    s, tf, n, mult = args; d = load(s).resample(tf).agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()
    o, h, l, c = d.o.values, d.h.values, d.l.values, d.c.values
    tr = np.maximum(h[1:] - l[1:], np.maximum(abs(h[1:] - c[:-1]), abs(l[1:] - c[:-1]))); atr = pd.Series(np.r_[np.nan, tr]).ewm(alpha=1 / 14).mean().values
    hh = pd.Series(h).rolling(n).max().shift(1).values; ll = pd.Series(l).rolling(n).min().shift(1).values
    rows = []; pos = 0
    for i in range(n + 15, len(c) - 1):
        if pos == 0:
            if c[i] > hh[i]: pos, en, rk = 1, o[i + 1], mult * atr[i]; st = en - rk; ext = h[i]; ei = i
            elif c[i] < ll[i]: pos, en, rk = -1, o[i + 1], mult * atr[i]; st = en + rk; ext = l[i]; ei = i
            continue
        if pos == 1:
            if l[i] <= st and i > ei: rows.append((d.index[i].date(), (st - en - COST[s]) / rk)); pos = 0; continue
            ext = max(ext, h[i]); st = max(st, ext - mult * atr[i])
        else:
            if h[i] >= st and i > ei: rows.append((d.index[i].date(), (en - st - COST[s]) / rk)); pos = 0; continue
            ext = min(ext, l[i]); st = min(st, ext + mult * atr[i])
    return stats(f"{s} Donchian {n} {tf} trail {mult}xATR", rows)
def run(fa): return fa[0](fa[1])
if __name__ == "__main__":
    J = [(retest, a) for a in itertools.product(["NQ", "SPX"], ["range", "mid"], [1.5, 2, 3], [30, 90])]
    J += [(pinbar, a) for a in itertools.product(["NQ", "SPX", "GOLD"], ["15min", "1h"], [2, 3], [0.6])]
    J += [(donchian, a) for a in itertools.product(["NQ", "SPX", "GOLD"], ["4h", "1D"], [20, 55], [3, 4])]
    with Pool(4) as p: R = [r for r in p.map(run, J) if r]
    R = pd.DataFrame(R); R.to_pickle("strat3.pkl"); pd.set_option("display.width", 250)
    for fam in ("retest", "pin bar", "Donchian"):
        x = R[R.strategy.str.contains(fam)].sort_values("R_per_yr", ascending=False); print(x.head(6).to_string(index=False)); print(fam, "variants", len(x), "profitable", int((x.avgR > 0).sum()), "\n")
