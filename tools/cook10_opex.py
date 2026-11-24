# Options-expiry pinning, pre-registered. SPX and NQ CFD 1m data (Dukascopy), New York clock.
#  P1 PIN  : |16:00 close - nearest strike| on monthly OPEX (3rd Friday) vs other days; strike grid SPX 25 & 50, NQ 100.
#            Trade: at 14:00 if 0.05% < distance to the nearest strike < 0.35%, go toward it; target = strike, stop = same distance away; exit 15:55.
#  P2 FADE : at 15:00 fade the 14:00->15:00 move, exit 15:55, stop = size of that move. OPEX Fridays vs other Fridays vs all days.
#  P3 WEEK : weekly return (Fri close -> Fri close) for OPEX week, the week after, and other weeks.
#  P4 0DTE : P1/P2 trades on ALL days, split before / after 2022-05-11 (SPX Tue/Thu expiries added -> daily 0DTE).
# Costs: SPX/NQ round trip 0.015% of price.
import numpy as np, pandas as pd
exec(open("smc.py").read().split("def run_symbol(")[0])
COST = 0.00015; DAILY0 = pd.Timestamp("2022-05-11")
def opex_days(idx):
    d = pd.Series(idx, idx); fri = d[d.dt.dayofweek == 4]; return set(fri.groupby([fri.dt.year, fri.dt.month]).apply(lambda x: x.iloc[2] if len(x) >= 3 else None).dropna())
rows = []; trades = []
for sym, path, grids in (("SPX", "fut1m/USA500IDXUSD_1m.csv", (25, 50)), ("NQ", "fut1m/USATECHIDXUSD_1m.csv", (100,))):
    m = m1_csv(path); m.index = m.index.tz_convert("America/New_York"); m = m[m.index.dayofweek < 5]
    m = m[(m.index.hour >= 9) & (m.index.hour < 16)]
    g = {d: x for d, x in m.groupby(m.index.date)}
    days = pd.to_datetime(sorted(g)); OP = {pd.Timestamp(x).normalize() for x in opex_days(days)}
    for dte in days:
        x = g[dte.date()]; t = x.index.hour * 60 + x.index.minute
        def at(mins):
            k = np.searchsorted(t, mins); return (k if k < len(t) and abs(t[k] - mins) <= 2 else None)
        k14, k15, k1555, k1559 = at(14 * 60), at(15 * 60), at(15 * 60 + 55), at(15 * 60 + 59)
        if None in (k14, k15, k1555, k1559): continue
        c = x.c.to_numpy(); h = x.h.to_numpy(); l = x.l.to_numpy(); isop = dte in OP; isfri = dte.dayofweek == 4
        for G in grids:
            strike_close = round(c[k1559] / G) * G; rows.append(dict(sym=sym, grid=G, d=dte, opex=isop, fri=isfri, dist_close=abs(c[k1559] - strike_close) / G))
        # P1 trade toward nearest strike of the first grid
        G = grids[0]; p = c[k14]; s = round(p / G) * G; dist = abs(p - s) / p
        if 0.0005 < dist < 0.0035:
            dirn = np.sign(s - p); stop = p - dirn * abs(s - p); x_ = c[k1555]
            for q in range(k14 + 1, k1555 + 1):
                if (dirn > 0 and l[q] <= stop) or (dirn < 0 and h[q] >= stop): x_ = stop; break
                if (dirn > 0 and h[q] >= s) or (dirn < 0 and l[q] <= s): x_ = s; break
            trades.append(dict(sym=sym, kind="P1_pin", d=dte, opex=isop, fri=isfri, R=(dirn * (x_ - p) - COST * p) / abs(s - p)))
        # P2 fade
        mv = c[k15] - c[k14]
        if abs(mv) > 3 * COST * c[k15]:
            dirn = -np.sign(mv); e = c[k15]; stop = e - dirn * abs(mv); x_ = c[k1555]
            for q in range(k15 + 1, k1555 + 1):
                if (dirn > 0 and l[q] <= stop) or (dirn < 0 and h[q] >= stop): x_ = stop; break
            trades.append(dict(sym=sym, kind="P2_fade", d=dte, opex=isop, fri=isfri, R=(dirn * (x_ - e) - COST * e) / abs(mv)))
    # P3 weekly
    cl = pd.Series({d: g[d.date()].c.iloc[-1] for d in days}); fr = cl[cl.index.dayofweek == 4]; wr = np.log(fr).diff().dropna()
    opw = pd.Series([d in OP for d in wr.index], wr.index); after = opw.shift(1, fill_value=False)
    for nm, f in (("OPEX week", opw), ("week after OPEX", after), ("other weeks", ~opw & ~after)):
        for per, msk in (("pre2023", wr.index < pd.Timestamp("2023-01-01")), ("2023on", wr.index >= pd.Timestamp("2023-01-01"))):
            v = wr[f & msk]; trades.append(dict(sym=sym, kind=f"P3 {nm}", d=pd.NaT, opex=None, fri=None, R=np.nan, wk_mean_bp=round(1e4 * v.mean(), 1), wk_t=round(v.mean() / v.std() * np.sqrt(len(v)), 2), n=len(v), per=per))
D = pd.DataFrame(rows); T = pd.DataFrame(trades); pd.set_option("display.width", 220); pd.set_option("display.max_rows", 200)
print("P1 PIN - mean distance of the 16:00 close from the nearest strike, in strike widths (0.25 = random):")
D["era"] = np.where(D.d < DAILY0, "pre-0DTE", "0DTE era")
print(D.groupby(["sym", "grid", "era", "opex"]).dist_close.agg(["count", "mean"]).round(3).to_string())
def summ(g):
    r = g.R.dropna(); return pd.Series(dict(n=len(r), win=round(100 * (r > 0).mean()), avgR=round(r.mean(), 3), t=round(r.mean() / r.std() * np.sqrt(len(r)), 2) if len(r) > 2 else np.nan))
X = T[T.kind.isin(["P1_pin", "P2_fade"])].copy(); X["era"] = np.where(X.d < DAILY0, "pre-0DTE", "0DTE era")
X["daytype"] = np.where(X.opex, "monthly OPEX", np.where(X.fri, "other Friday", "Mon-Thu"))
print("\nP1/P2 TRADES by day type and era:"); print(X.groupby(["kind", "sym", "daytype", "era"]).apply(summ).to_string())
print("\nP1/P2 pooled (SPX+NQ) by day type:"); print(X.groupby(["kind", "daytype"]).apply(summ).to_string())
print("\nP4 0DTE: all days, by era:"); print(X.groupby(["kind", "sym", "era"]).apply(summ).to_string())
print("\nP3 WEEKS:"); print(T[T.kind.str.startswith("P3")][["sym", "kind", "per", "n", "wk_mean_bp", "wk_t"]].to_string(index=False))
