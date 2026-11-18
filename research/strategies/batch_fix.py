"""STRAT-0271..0280 FX fixing-window flow (WM/Reuters 4pm London fix) on 1-minute EURUSD and AUDCAD (2019+)."""
import os, pickle, numpy as np, pandas as pd
from data import SCR, RDATA
from engine import P
from strategies.lib import nfp_mask
COST = {"EURUSD": 1.0, "AUDCAD": 2.0}       # bp round trip
def day_table(name):
    p = f"{RDATA}/fix_{name}.pkl"
    if os.path.exists(p): return pickle.load(open(p, "rb"))
    d = pd.read_csv(f"{SCR}/fx1m/{name}_1m.csv", parse_dates=["t"]).set_index("t"); d.index = d.index.tz_convert("Europe/London")
    d = d[d.index.dayofweek < 5]; m = d.index.hour * 60 + d.index.minute
    def at(mins):
        s = d.c[m == mins]; s.index = s.index.normalize().tz_localize(None); return s.groupby(level=0).last()
    def vol_between(a, b):
        s = d.v[(m >= a) & (m < b)]; s.index = s.index.normalize().tz_localize(None); return s.groupby(level=0).sum()
    t = pd.DataFrame({"p1500": at(900), "p1530": at(930), "p1550": at(950), "p1559": at(959), "p1600": at(960), "p1700": at(1020), "v": vol_between(900, 950)}).dropna()
    t["dayvol"] = np.log(t.p1600).diff().abs().rolling(21).mean().shift(1)
    pickle.dump(t, open(p, "wb")); return t
T = {n: day_table(n) for n in COST}
spx = P["cfd"]["SPX"].copy(); spx.index = spx.index.tz_localize(None).normalize()
def month_end(idx): s = pd.Series(idx, index=idx); return (s.groupby([idx.year, idx.month]).transform("max") == s).values
def mtd_sign(idx):
    m = spx.groupby([spx.index.year, spx.index.month]).transform("first"); mtd = (spx / m - 1).shift(1)     # through the previous day
    return np.sign(mtd.reindex(idx, method="ffill")).values
def r(t, a, b, sign, name): return sign * (t[b] / t[a] - 1) - (sign != 0) * COST[name] / 1e4
def stream(rule, names=("EURUSD",)):
    def fn(p):
        out = {}
        for n in names:
            t = T[n]; out[n] = pd.Series(rule(t, p, n), index=t.index).fillna(0.0)
        return pd.DataFrame(out)
    return fn
def ts_sign(t, p): return np.sign(t.p1550 - t.p1500) * (abs(t.p1550 / t.p1500 - 1) > p["th"] / 1e4)
def r_ts(t, p, n): return r(t, "p1550", "p1600", ts_sign(t, p), n)
def regime_mask(t, side): pr = t.dayvol.rolling(250, min_periods=60).rank(pct=True); return (pr < 0.5) if side == "calm" else (pr >= 0.5)
def term_mask(t, side):
    sl = P["macro"]["T10Y3M"]; g = sl.reindex(t.index, method="ffill").shift(1); return (g > 0) if side == "steep" else (g <= 0)
G = {"th": [0, 3]}
SPECS = [
    ("STRAT-0271", "event-triggered", "month-end only: long EUR vs USD 15:00->16:00 if US stocks are up month-to-date (foreign hedge rebalancing sells USD), short if down",
     stream(lambda t, p, n: r(t, "p1500", "p1600", pd.Series(month_end(t.index) * mtd_sign(t.index), index=t.index), n), ("EURUSD",)), {"x": [1]}),
    ("STRAT-0272", "cross-sectional", "of EURUSD and AUDCAD, trade only the pair with the larger 15:00-15:50 move, in its direction into the fix",
     lambda p: (lambda a, b: pd.DataFrame({"EURUSD": a["EURUSD"].where((T["EURUSD"].p1550 / T["EURUSD"].p1500 - 1).abs() >= (T["AUDCAD"].p1550 / T["AUDCAD"].p1500 - 1).abs().reindex(T["EURUSD"].index), 0),
                                         "AUDCAD": b["AUDCAD"].where((T["AUDCAD"].p1550 / T["AUDCAD"].p1500 - 1).abs() > (T["EURUSD"].p1550 / T["EURUSD"].p1500 - 1).abs().reindex(T["AUDCAD"].index), 0)}).fillna(0))(stream(r_ts)(p), stream(r_ts, ("AUDCAD",))(p)), G),
    ("STRAT-0273", "time-series", "momentum into the fix: at 15:50 trade in the direction of the 15:00-15:50 move (if > th bp), exit at 16:00", stream(r_ts), G),
    ("STRAT-0274", "lead-lag", "post-fix reversal: 16:00->17:00 against the 15:00->16:00 move", stream(lambda t, p, n: r(t, "p1600", "p1700", -np.sign(t.p1600 - t.p1500) * (abs(t.p1600 / t.p1500 - 1) > p["th"] / 1e4), n)), G),
    ("STRAT-0275", "regime-conditioned", "fix momentum only in calm / turbulent EURUSD vol regime", stream(lambda t, p, n: r_ts(t, p, n).where(regime_mask(t, p["reg"]), 0)), dict(G, reg=["calm", "turbulent"])),
    ("STRAT-0276", "term-structure", "fix momentum gated by the US curve sign", stream(lambda t, p, n: r_ts(t, p, n).where(term_mask(t, p["side"]), 0)), dict(G, side=["steep", "inverted"])),
    ("STRAT-0277", "flow-based", "fix momentum only when 15:00-15:50 tick volume is above 1.3x its 20-day average", stream(lambda t, p, n: r_ts(t, p, n).where(t.v > 1.3 * t.v.rolling(20).mean().shift(1), 0)), G),
    ("STRAT-0278", "relative-value", "placebo/relative: same fix-momentum rule on AUDCAD (no USD leg, so no fix-flow effect expected)", stream(r_ts, ("AUDCAD",)), G),
    ("STRAT-0279", "volatility-based", "fix momentum only when the 15:00-15:50 move is large relative to the 21-day average absolute daily move",
     stream(lambda t, p, n: r_ts(t, p, n).where(abs(t.p1550 / t.p1500 - 1) > p["k"] * t.dayvol, 0)), {"th": [0], "k": [0.2, 0.4]}),
    ("STRAT-0280", "execution-aware", "month-end rebalancing rule entered 15:30 and closed 15:59, avoiding the fix-minute spread",
     stream(lambda t, p, n: r(t, "p1530", "p1559", pd.Series(month_end(t.index) * mtd_sign(t.index), index=t.index), n)), {"x": [1]}),
]
