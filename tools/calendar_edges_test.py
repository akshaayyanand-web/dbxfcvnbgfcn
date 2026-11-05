# Run from the scratchpad.
# Calendar / session edges: overnight drift, turn of month, pre-FOMC drift, gold session split, last-hour momentum.
import sys, numpy as np, pandas as pd
SP = sys.argv[1] if len(sys.argv) > 1 else "."
sys.path.insert(0, "/home/user/dbxfcvnbgfcn/tools")
import portfolio_prop as P
from portfolio_prop import load_csv
def bars(path, rule="5min"):
    d = load_csv(SP + "/" + path); return d.resample(rule).agg(dict(o="first", h="max", l="min", c="last")).dropna().loc["2019-03-01":]
MK = {"nq": ("fut1m/USATECHIDXUSD_1m.csv", 0.00012), "spx": ("fut1m/USA500IDXUSD_1m.csv", 0.0001), "gold": ("fut1m/XAUUSD_1m.csv", 0.0001)}
SWAP = 0.0002          # per night (17:00 NY rollover), x3 on Fridays (conservative CFD long swap)
B = {k: bars(v[0]) for k, v in MK.items()}
H1 = {k: b.resample("1h").agg(dict(o="first", h="max", l="min", c="last")).dropna() for k, b in B.items()}
def daily_atr(b):
    d = b.c.resample("1D").last().dropna(); hi = b.h.resample("1D").max().dropna(); lo = b.l.resample("1D").min().dropna()
    tr = pd.concat([hi - lo, (hi - d.shift()).abs(), (lo - d.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / 14, adjust=False).mean().shift(1), d      # known at the start of each day
def window_trades(mk, entries, stop_atr, swap=SWAP):
    """entries: list of (entry_ts, exit_ts, dir). Entry at the open of the first bar >= entry_ts, exit at the open of the
    first bar >= exit_ts or at the stop. Returns P.trade_series-style tuples with the swap folded into the exit price."""
    b = B[mk]; T = b.index; O, Hh, L = b.o.to_numpy(), b.h.to_numpy(), b.l.to_numpy(); atr, _ = daily_atr(b)
    atrv = atr.reindex(T.floor("D"), method="ffill").to_numpy(); out = []
    for et, xt, d in entries:
        j = T.searchsorted(et); z = T.searchsorted(xt)
        if j >= len(T) - 1 or z >= len(T) or z <= j or not np.isfinite(atrv[j]): continue
        if T[j] - et > pd.Timedelta("30min"): continue                      # market closed at the planned entry
        e = O[j]; st = e - d * stop_atr * atrv[j]; px, xx = None, None
        for k in range(j, z):
            if (L[k] <= st) if d == 1 else (Hh[k] >= st): px, xx = (min(O[k], st) if d == 1 else max(O[k], st)), T[k] + pd.Timedelta("5min"); break
        if px is None: px, xx = O[z], T[z]
        ny = pd.date_range(T[j].tz_convert("America/New_York"), xx.tz_convert("America/New_York"), freq="1h")
        nights = sum(3 if t.weekday() == 4 else 1 for t in ny if t.hour == 17)
        if d == 1: px -= e * swap * nights          # longs pay swap; shorts assumed ~0
        out.append((T[j], xx, e, st, px))
    return out
def stats(trades, cost, name):
    r = np.array([(px - e) / abs(e - st) * np.sign(e - st) - cost * e / abs(e - st) for et, xt, e, st, px in trades])
    r2 = r - np.array([cost * e / abs(e - st) for et, xt, e, st, px in trades])
    t = pd.DatetimeIndex([x[0] for x in trades]); yrs = lambda m: max((t[m][-1] - t[m][0]).days / 365.25, 0.5) if m.sum() else 1
    A = t < pd.Timestamp("2023-01-01", tz="UTC"); Bm = ~A
    return dict(edge=name, trades_mo=len(r) / ((t[-1] - t[0]).days / 30.4), win=100 * (r > 0).mean(), avgR=r.mean(),
                yrA=r[A].sum() / yrs(A), yrB=r[Bm].sum() / yrs(Bm), yr_cost2=r2.sum() / ((t[-1] - t[0]).days / 365.25))
ET = lambda ts: ts.tz_convert("America/New_York")
def ny_days(mk):
    d = B[mk].index.tz_convert("America/New_York"); return pd.DatetimeIndex(sorted(set(d.normalize()))).tz_localize(None)
def at(day, hh, mm): return pd.Timestamp(day).replace(hour=hh, minute=mm).tz_localize("America/New_York").tz_convert("UTC")
if __name__ == "__main__":
    rows = []; TR = {}
    for mk in ("nq", "spx"):
        days = [d for d in ny_days(mk) if d.weekday() < 5]
        c5 = B[mk].c; p = pd.Series([c5.asof(at(d, 15, 50)) for d in days], index=days)     # price at 15:50 NY each day
        sma = p.rolling(200).mean(); sma50 = p.rolling(50).mean(); dret = p / p.shift(1) - 1
        for filt in ("all", "trend200", "trend50", "after_down", "after_down_trend"):
            ent = []
            for i in range(len(days) - 1):
                d0, d1 = days[i], days[i + 1]
                up = p[d0] > sma[d0]; up50 = p[d0] > sma50[d0]; dn = dret[d0] < 0
                ok = dict(all=True, trend200=up, trend50=up50, after_down=dn, after_down_trend=dn and up)[filt]
                if ok: ent.append((at(d0, 15, 55), at(d1, 9, 35), 1))
            for sa in (1.0, 2.0):
                tr = window_trades(mk, ent, sa); rows.append(stats(tr, MK[mk][1], f"{mk} overnight {filt} stop{sa}ATR")); TR[rows[-1]["edge"]] = (mk, tr)
        # turn of the month: close of the last trading day -> close of the 3rd trading day
        dd = pd.Series(days); ent = []
        for (y, m), g in dd.groupby([dd.dt.year, dd.dt.month]):
            nxt = dd[(dd > g.iloc[-1])].head(3)
            if len(nxt) == 3: ent.append((at(g.iloc[-1], 15, 55), at(nxt.iloc[-1], 15, 55), 1))
        for sa in (1.5, 3.0):
            tr = window_trades(mk, ent, sa); rows.append(stats(tr, MK[mk][1], f"{mk} turn-of-month stop{sa}ATR")); TR[rows[-1]["edge"]] = (mk, tr)
        # pre-FOMC drift: 14:00 the day before -> 13:55 on the decision day
        fomc = [pd.Timestamp(str(x).strip()) for x in open("/home/user/dbxfcvnbgfcn/tools/fomc_dates.txt") if x.strip()]
        ent = []
        for f in fomc:
            prev = [d for d in days if d < f]
            if prev: ent.append((at(prev[-1], 14, 0), at(f, 13, 55), 1))
        for sa in (1.0, 2.0):
            tr = window_trades(mk, ent, sa); rows.append(stats(tr, MK[mk][1], f"{mk} pre-FOMC stop{sa}ATR")); TR[rows[-1]["edge"]] = (mk, tr)
        # last-hour momentum: sign of (prev close -> 15:00) decides 15:00 -> 15:55
        b = B[mk]; c = b.c; nyb = b.index.tz_convert("America/New_York")
        for thr in (0.0, 0.005):
            ent = []
            for i in range(1, len(days)):
                d0, dp = days[i], days[i - 1]
                try:
                    pc = c.asof(at(dp, 15, 55)); p15 = c.asof(at(d0, 14, 59))
                except Exception: continue
                if not (np.isfinite(pc) and np.isfinite(p15)): continue
                rr = p15 / pc - 1
                if abs(rr) > thr and rr != 0: ent.append((at(d0, 15, 0), at(d0, 15, 55), 1 if rr > 0 else -1))
            for sa in (0.3, 0.6):
                tr = window_trades(mk, ent, sa, swap=0); rows.append(stats(tr, MK[mk][1], f"{mk} last-hour momentum thr{thr} stop{sa}ATR")); TR[rows[-1]["edge"]] = (mk, tr)
    # gold session split
    days = [d for d in ny_days("gold") if d.weekday() < 5]
    for (h0, m0, h1, m1, d, lab) in ((18, 5, 3, 0, 1, "Asia long 18:05-03:00"), (18, 5, 8, 0, 1, "Asia+London long 18:05-08:00"),
                                     (8, 20, 16, 0, -1, "NY short 08:20-16:00"), (10, 0, 16, 0, -1, "NY short 10:00-16:00")):
        ent = []
        for i in range(len(days) - 1):
            d0, d1 = days[i], days[i + 1]
            if h0 > h1: ent.append((at(d0, h0, m0), at(d1, h1, m1), d))
            else: ent.append((at(d1, h0, m0), at(d1, h1, m1), d))
        for sa in (0.5, 1.0):
            tr = window_trades("gold", ent, sa); rows.append(stats(tr, MK["gold"][1], f"gold {lab} stop{sa}ATR")); TR[rows[-1]["edge"]] = ("gold", tr)
    df = pd.DataFrame(rows); pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
    df["yrA%"] = df.yrA; df["yrB%"] = df.yrB          # R per year == %/yr at 1% risk
    print(df[["edge", "trades_mo", "win", "avgR", "yrA%", "yrB%", "yr_cost2"]].round(2).to_string(index=False))
    pd.to_pickle(TR, SP + "/calendar_trades.pkl")
