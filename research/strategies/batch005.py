"""STRAT-0401..0500. Families 41-49 need single-stock prices + corporate-event data (blocked). Family 50 (index rebalance flow) tested
with calendar flow rules on index/industry/Treasury data."""
import numpy as np, pandas as pd
from strategies.lib import *
from engine import P
FORMS = ["event-triggered", "cross-sectional", "time-series", "lead-lag", "regime-conditioned", "term-structure", "flow-based", "relative-value", "volatility-based", "execution-aware"]
def tdom(idx):
    """trading day of month (1..) and trading days remaining (0 = last day)."""
    s = pd.Series(1, index=idx); g = [idx.year, idx.month]
    return s.groupby(g).cumsum().values, (s.groupby(g).transform("sum") - s.groupby(g).cumsum()).values
def tom_mask(idx, before=1, after=3):
    first, left = tdom(idx); return pd.Series((left < before) | (first <= after), index=idx)
def third_friday_week(idx):
    d = pd.Series(idx, index=idx); third_fri = (idx.dayofweek == 4) & (idx.day >= 15) & (idx.day <= 21) & idx.month.isin([3, 6, 9, 12])
    wk = pd.Series(third_fri, index=idx); return wk[::-1].rolling(5, min_periods=1).max()[::-1].astype(bool)   # the 5 trading days ending on quad-witching Friday
def russell_window(idx, before=10):
    last_fri_june = pd.Series([(d.month == 6) and (d.dayofweek == 4) and (d.day + 7 > 30) for d in idx], index=idx)
    return last_fri_june[::-1].rolling(before, min_periods=1).max()[::-1].astype(bool)
def eq_only(R, cols): w = pd.DataFrame(0.0, index=R.index, columns=R.columns); return w, [c for c in cols if c in R.columns]
def tom_w(R, cols, before=1, after=3):
    w, cc = eq_only(R, cols); m = tom_mask(R.index, before, after).astype(float)
    for c in cc: w[c] = m
    return w
EQ_MACRO = ["NASDAQ"]
def fam50(off=490, fam="Index rebalance flow"):
    out = []
    def add(form, d, U, fn, g, sizing=True): out.append(dict(id=f"STRAT-{off + FORMS.index(form) + 1:04d}", family=fam, form=form, desc=d, universes=U, fn=fn, grid=g, sizing=sizing))
    add("event-triggered", "quad-witching / S&P quarterly-rebalance week: long US equity index the 5 trading days into the third Friday of Mar/Jun/Sep/Dec",
        ["cfd"], lambda R, p: pd.DataFrame({c: third_friday_week(R.index).astype(float) * p["sgn"] if c in ("SPX", "NQ", "DJI", "RUT") else 0.0 for c in R.columns}, index=R.index), {"sgn": [1, -1]})
    def wd(R, p):
        idx = R.index; first, left = tdom(idx); qend = pd.Series(idx.month.isin([3, 6, 9, 12]), index=idx)
        nxt = pd.Series(idx.month.isin([1, 4, 7, 10]), index=idx)
        ytd = px(R) / px(R).groupby(idx.year).transform("first") - 1; rk = ytd.rank(axis=1, pct=True)
        sig = (rk > 0.8).astype(float) - (rk < 0.2).astype(float)
        into = (qend & (left < p["n"])).values; outof = (nxt & (first <= p["n"])).values
        return sig.mul(into, axis=0) - sig.mul(outof, axis=0)
    add("cross-sectional", "quarter-end window dressing: long year-to-date winner industries / short losers in the last n days of a quarter, reverse in the first n days of the next",
        ["ind49"], wd, {"n": [3, 5]})
    add("time-series", "turn-of-the-month: long equities from the last trading day of the month through trading day 3 (pay-cycle and rebalancing flows)",
        ["ind10", "macro_long", "cfd"], lambda R, p: tom_w(R, list(R.columns) if R.shape[1] == 10 else ["NASDAQ"] if "NASDAQ" in R.columns else ["SPX", "NQ", "DJI", "RUT"], p["b"], p["a"]), {"b": [1, 2], "a": [3]})
    add("lead-lag", "month-to-date equity drift predicts the opposite month-end flow: if stocks beat bonds MTD, short stocks / long 10y in the last 3 days (pension rebalancing, Harvey et al.)",
        ["macro_long"], lambda R, p: _pension(R, p), {"n": [2, 3]}, sizing=True)
    add("regime-conditioned", "turn-of-month long only in calm / turbulent equity regime", ["ind10", "macro_long"],
        lambda R, p: tom_w(R, list(R.columns) if R.shape[1] == 10 else ["NASDAQ"], 1, 3).mul(regime(R, p["reg"]).astype(float), axis=0), {"reg": ["calm", "turbulent"]})
    add("term-structure", "turn-of-month long gated by yield-curve sign", ["ind10", "macro_long"],
        lambda R, p: tom_w(R, list(R.columns) if R.shape[1] == 10 else ["NASDAQ"], 1, 3).mul(w_term(pd.DataFrame(1.0, index=R.index, columns=["x"]), p["side"])["x"], axis=0), {"side": ["steep", "inverted"]})
    add("flow-based", "month-end pension rebalancing, US large/small: if large caps beat small caps MTD, short SPX/long RUT the last n days, reverse otherwise",
        ["cfd"], lambda R, p: _sizerot(R, p), {"n": [2, 3]})
    add("relative-value", "Russell reconstitution: long RUT / short SPX over the 10 trading days into the last Friday of June (index-addition demand)",
        ["cfd"], lambda R, p: pd.DataFrame({c: (russell_window(R.index, p["b"]).astype(float) * p["sgn"] * (1 if c == "RUT" else -1)) if c in ("RUT", "SPX") else 0.0 for c in R.columns}, index=R.index), {"b": [5, 10], "sgn": [1, -1]})
    add("volatility-based", "turn-of-month long only when the previous month's realised vol is above / below its 3-year median", ["ind10", "macro_long"],
        lambda R, p: tom_w(R, list(R.columns) if R.shape[1] == 10 else ["NASDAQ"], 1, 3).mul(_vgate(R, p["vs"]), axis=0), {"vs": ["high", "low"]})
    def tom_overnight(R, p):
        return tom_w(R, ["SPX", "NQ", "DJI", "RUT"], 1, p["a"])
    add("execution-aware", "turn-of-month on index CFDs with a shorter window (last day + first a days) to cut exposure",
        ["cfd"], tom_overnight, {"a": [1, 2]})
    return out
def _pension(R, p):
    idx = R.index; first, left = tdom(idx); eq, bd = px(R)["NASDAQ"], px(R)["UST10Y"]
    mtd = (eq / eq.groupby([idx.year, idx.month]).transform("first")) - (bd / bd.groupby([idx.year, idx.month]).transform("first"))
    s = -np.sign(mtd) * (left < p["n"]); w = pd.DataFrame(0.0, index=idx, columns=R.columns); w["NASDAQ"] = s; w["UST10Y"] = -s * 4; return w
def _sizerot(R, p):
    idx = R.index; first, left = tdom(idx); a, b = px(R)["SPX"], px(R)["RUT"]
    mtd = a / a.groupby([idx.year, idx.month]).transform("first") - b / b.groupby([idx.year, idx.month]).transform("first")
    s = -np.sign(mtd) * (left < p["n"]); w = pd.DataFrame(0.0, index=idx, columns=R.columns); w["SPX"] = s; w["RUT"] = -s; return w
def _vgate(R, side):
    v = R.mean(1).rolling(21).std(); m = v.rolling(756, min_periods=250).median(); return ((v > m) if side == "high" else (v <= m)).astype(float)

BLOCKED = {400: ("Spin-off event drift", "spin-off announcements + parent/child stock prices"), 410: ("Earnings announcement drift", "earnings dates, consensus and single-stock prices"),
           420: ("Earnings surprise reversal", "earnings surprises and single-stock prices"), 430: ("Analyst revision momentum", "analyst estimate histories (I/B/E/S-type)"),
           440: ("Guidance revision drift", "company guidance histories"), 450: ("Insider transaction signal", "insider filings (Form 4) + single-stock prices"),
           460: ("Share buyback event", "buyback announcements + single-stock prices"), 470: ("Dividend change signal", "dividend declarations + single-stock prices"),
           480: ("Index inclusion event", "index addition/deletion histories + single-stock prices")}
def specs():
    out = fam50()
    for off, (fam, why) in BLOCKED.items():
        for j, form in enumerate(FORMS): out.append(dict(id=f"STRAT-{off + j + 1:04d}", family=fam, form=form, blocked=why + " - not available in this environment (single-stock price source unreachable)"))
    return sorted(out, key=lambda s: s["id"])
