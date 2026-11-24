# Seasonality round, pre-registered. Daily closes: US symbols at the 16:00 New York close, DAX at 17:00 Berlin, metals/oil at 17:00 NY, crypto 00:00 UTC.
# Effects (each tested as "returns on flagged days vs all other days", Welch t, split pre-2023 / 2023+, plus a long/short sleeve after costs):
#  TOM  : trading days -1, +1, +2, +3 around the month boundary (long).
#  DOWx : each weekday vs the rest (sign chosen by the full-sample mean is NOT allowed: we report both periods so a flip shows).
#  PREH : the trading day before a NYSE holiday (long), US symbols + gold.
#  HALLO: Nov-Apr vs May-Oct.
#  MEF  : last 2 trading days of the month, fade the month-to-date move as of day -3.
#  ON   : SPX/NQ overnight (16:00 -> 09:30) vs intraday (09:30 -> 16:00), from 1m data.
# Sleeve cost per trade: round-trip spread + swap per night held (indices/metals/oil 5%/yr, crypto 15%/yr).
import numpy as np, pandas as pd
from dateutil.easter import easter
from pandas.tseries.holiday import USFederalHolidayCalendar
exec(open("smc.py").read().split("def run_symbol(")[0])
def duka(sym): d = pd.read_csv(f"fut/{sym}.csv", index_col=0); d.index = pd.to_datetime(d.index, utc=True); return d.c
SYM = {"SPX": (lambda: duka("USA500IDXUSD"), "America/New_York", 15, 0.00015, 0.05), "NQ": (lambda: duka("USATECHIDXUSD"), "America/New_York", 15, 0.00015, 0.05),
       "DOW": (lambda: duka("USA30IDXUSD"), "America/New_York", 15, 0.00015, 0.05), "RUT": (lambda: duka("USSC2000IDXUSD"), "America/New_York", 15, 0.0003, 0.05),
       "DAX": (lambda: m1_csv("eu1m/DEUIDXEUR_1m.csv").c.resample("1h").last().dropna(), "Europe/Berlin", 16, 0.00015, 0.05),
       "XAU": (lambda: duka("XAUUSD"), "America/New_York", 16, 0.00012, 0.04), "XAG": (lambda: duka("XAGUSD"), "America/New_York", 16, 0.0008, 0.04),
       "WTI": (lambda: duka("LIGHTCMDUSD"), "America/New_York", 16, 0.0003, 0.05),
       "BTC": (lambda: crypto("BTC").c.resample("1h").last().dropna(), "UTC", 23, 0.0006, 0.15), "ETH": (lambda: crypto("ETH").c.resample("1h").last().dropna(), "UTC", 23, 0.001, 0.15)}
US = {"SPX", "NQ", "DOW", "RUT", "XAU"}
hol = set(USFederalHolidayCalendar().holidays("2015-01-01", "2027-12-31").date)
hol -= {d.date() for d in pd.to_datetime(list(hol)) if d.month in (10, 11) and d.day < 15 and d.dayofweek == 0}   # drop Columbus Day
hol -= {d.date() for d in pd.to_datetime(list(hol)) if d.month == 11 and d.day == 11}                                # drop Veterans Day
hol -= {d.date() for d in pd.to_datetime(list(hol)) if d.month == 6 and d.year < 2022}                                # Juneteenth from 2022
hol |= {easter(y) - pd.Timedelta(days=2) for y in range(2015, 2028)}
hol = {pd.Timestamp(d).date() for d in hol}
SPLIT = pd.Timestamp("2023-01-01")
def daily(sym):
    f, tz, hr, *_ = SYM[sym]; h = f(); h.index = h.index.tz_convert(tz); h = h[h.index.hour <= hr]
    d = h.groupby(h.index.date).last(); d.index = pd.to_datetime(d.index)
    if sym not in ("BTC", "ETH"): d = d[d.index.dayofweek < 5]
    if sym in US: d = d[[x.date() not in hol for x in d.index]]
    return d
def tstat(a, b):
    if len(a) < 5: return np.nan
    return (a.mean() - b.mean()) / np.sqrt(a.var() / len(a) + b.var() / len(b))
rows = []; sleeves = {}
def add(sym, eff, flag, sign, r, cost_rt, swap, nights):
    """flag: bool Series over r's index. sign +1 long, -1 short (or a Series of signs)."""
    for per, m in (("pre2023", r.index < SPLIT), ("2023on", r.index >= SPLIT)):
        a, b = r[m & flag], r[m & ~flag]; sg = sign if np.isscalar(sign) else sign[m & flag]
        rows.append(dict(sym=sym, eff=eff, per=per, n=len(a), flagged_bp=round(1e4 * (sg * a).mean(), 1) if len(a) else np.nan, other_bp=round(1e4 * b.mean(), 1), t_vs_other=round(tstat(sg * a, (b if np.isscalar(sign) else b * 0)), 2)))
    sl = (sign * r).where(flag, 0.0) - flag * (cost_rt / nights + swap / 365 * (1.4 if sym not in ("BTC", "ETH") else 1.0))   # cost spread across the days held
    sleeves[(sym, eff)] = sl
for sym in SYM:
    try: c = daily(sym)
    except Exception as ex: print(sym, "load fail", ex); continue
    r = np.log(c).diff().dropna(); idx = r.index; cost, swap = SYM[sym][3], SYM[sym][4]
    ym = idx.to_period("M"); pos = pd.Series(np.arange(len(idx)), idx).groupby(ym).rank(method="first").astype(int)
    neg = pd.Series(np.arange(len(idx)), idx).groupby(ym).rank(method="first", ascending=False).astype(int)
    tom = pd.Series((neg == 1) | (pos <= 3), idx)
    add(sym, "TOM", tom, 1, r, cost, swap, 4)
    for k, nm in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
        f = pd.Series(idx.dayofweek == k, idx)
        if f.sum() > 50: add(sym, f"DOW_{nm}", f, 1, r, cost, swap, 1)
    if sym in US:
        nxt = pd.Series(idx, idx).shift(-1)
        pre = pd.Series([(n is not pd.NaT) and any((d + pd.Timedelta(days=i)).date() in hol for i in range(1, (n - d).days)) for d, n in zip(idx, nxt)], idx)
        add(sym, "PREH", pre, 1, r, cost, swap, 1)
    add(sym, "HALLO_NovApr", pd.Series(idx.month.isin([11, 12, 1, 2, 3, 4]), idx), 1, r, cost, swap, 120)
    mtd = r.groupby(ym).cumsum(); sgn = -np.sign(mtd.where(neg == 3)).groupby(ym).transform("max").fillna(0)
    sgn = pd.Series(-np.sign(mtd.where(neg == 3).groupby(ym).transform("first")), idx).fillna(0)
    add(sym, "MEF", pd.Series(neg <= 2, idx) & (sgn != 0), sgn, r, cost, swap, 2)
# overnight vs intraday from 1m
for sym, path in (("SPX", "fut1m/USA500IDXUSD_1m.csv"), ("NQ", "fut1m/USATECHIDXUSD_1m.csv")):
    m = m1_csv(path).c; m.index = m.index.tz_convert("America/New_York"); m = m[m.index.dayofweek < 5]
    o = m[(m.index.hour == 9) & (m.index.minute == 30)]; cl = m[(m.index.hour == 15) & (m.index.minute == 59)]
    o.index, cl.index = pd.to_datetime(o.index.date), pd.to_datetime(cl.index.date); j = o.index.intersection(cl.index)
    o, cl = o.loc[j], cl.loc[j]; intra = np.log(cl / o); on = np.log(o / cl.shift(1)).dropna()
    for per, msk in (("pre2023", on.index < SPLIT), ("2023on", on.index >= SPLIT)):
        a, b = on[msk], intra.reindex(on.index)[msk]
        nights = pd.Series((on.index[1:] - on.index[:-1]).days, on.index[1:]).reindex(a.index).fillna(1)
        net = a - SYM[sym][3] - SYM[sym][4] / 365 * nights
        rows.append(dict(sym=sym, eff="ON_overnight_long", per=per, n=len(a), flagged_bp=round(1e4 * a.mean(), 2), other_bp=round(1e4 * b.mean(), 2), t_vs_other=round(tstat(a, b), 2),
                         net_bp=round(1e4 * net.mean(), 2), t_net=round(net.mean() / net.std() * np.sqrt(len(net)), 2)))
R = pd.DataFrame(rows); pd.set_option("display.width", 220); pd.set_option("display.max_rows", 500)
W = R.pivot_table(index=["eff", "sym"], columns="per", values=["flagged_bp", "other_bp", "t_vs_other", "n"], aggfunc="first")
W.columns = [f"{a}_{b}" for a, b in W.columns]; print(W[["n_pre2023", "flagged_bp_pre2023", "other_bp_pre2023", "t_vs_other_pre2023", "n_2023on", "flagged_bp_2023on", "other_bp_2023on", "t_vs_other_2023on"]].to_string())
print("\nOvernight rows:"); print(R[R.eff == "ON_overnight_long"].to_string())
print("\nEFFECTS with t>2 vs other days in BOTH periods (same sign):")
q = W[(W.t_vs_other_pre2023 > 2) & (W.t_vs_other_2023on > 2)]; print(q.to_string() if len(q) else "none")
q2 = W[(W.t_vs_other_pre2023 < -2) & (W.t_vs_other_2023on < -2)]; print("negative both periods:"); print(q2.to_string() if len(q2) else "none")
print("\nSLEEVES after costs (long on flagged days only): Sharpe pre2023 / 2023on, ann % at 1x notional")
out = []
for (s, e), sl in sleeves.items():
    if e.startswith("DOW"): continue
    sh = lambda x: round(x.mean() / x.std() * np.sqrt(252), 2) if x.std() > 0 else np.nan
    out.append(dict(sym=s, eff=e, sh_pre=sh(sl[sl.index < SPLIT]), sh_post=sh(sl[sl.index >= SPLIT]), ann_pct=round(100 * sl.mean() * 252, 1)))
print(pd.DataFrame(out).to_string()); pd.to_pickle(sleeves, "season_sleeves.pkl")
