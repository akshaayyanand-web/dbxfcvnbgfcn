"""STRAT-0041..0050 opening-range expansion formulations on 1-minute data (NQ, SPX, GOLD at NY; DAX Frankfurt; EURUSD London; NQ-SPX spread)."""
import numpy as np, pandas as pd
from intraday import tables
from strategies.lib import nfp_mask
from engine import P
T = tables(); MAIN = ["NQ", "SPX", "GOLD", "DAX", "EURUSD"]
from intraday import _bars
DAYS = {}
for _a in MAIN + ["NQ-SPX"]:
    src = "NQ" if _a == "NQ-SPX" else _a
    DAYS[_a] = pd.DatetimeIndex(sorted(set(T[src].day)))          # days the instrument traded (any breakout table row = a session with data)
def full(df):
    out = {}
    for a in df.columns:
        d = DAYS[a]; out[a] = df[a].groupby(level=0).sum().reindex(d).fillna(0.0)
    return pd.DataFrame(out)
def stream(f, assets=MAIN, col_of=lambda p: p.get("stop", "far")):
    def fn(p):
        out = {}
        for a in assets:
            t = T[a]; t = t[t.M == p["M"]]; t = f(t, p) if f else t
            col = col_of(p); out[a] = t.set_index("day")[col].fillna(0.0)
        return full(pd.DataFrame(out))
    return fn
G = {"M": [15, 30], "stop": ["far", "mid"]}
def ev(t, p): return t[nfp_mask(pd.DatetimeIndex(t.day), 1).values]
def xs(t, p): return t   # cross-sectional handled below
def ll(t, p): return t[t.dir == t.overnight]
def rg(t, p): return t[(t.dir == t.trend50) if p["reg"] == "with" else (t.dir == -t.trend50)]
def ts_(t, p):
    sl = P["macro"]["T10Y3M"]; g = t.day.map(sl.reindex(pd.DatetimeIndex(t.day), method="ffill").shift(1).to_dict() if False else sl.shift(1).reindex(pd.DatetimeIndex(t.day), method="ffill").to_dict())
    return t[(g > 0) if p["side"] == "steep" else (g <= 0)]
def fl(t, p): return t[t.volratio >= p["vr"]]
def vb(t, p): r = t.width / t.atr14; return t[(r < r.rolling(250, min_periods=60).median().shift(1)) if p["w"] == "narrow" else (r >= r.rolling(250, min_periods=60).median().shift(1))]
def xs_fn(p):
    rows = []
    for a in MAIN:
        t = T[a]; t = t[t.M == p["M"]].copy(); t["rel"] = t.width / t.atr14; t["a"] = a; rows.append(t)
    d = pd.concat(rows).dropna(subset=["rel"]).reset_index(drop=True); pick = d.loc[d.groupby("day").rel.idxmin()]      # most compressed opening range of the day
    return full(pick.pivot(index="day", columns="a", values=p["stop"]).reindex(columns=MAIN))
SPECS = [
    ("STRAT-0041", "event-triggered", "only on US payrolls days (first Friday)", stream(ev), G),
    ("STRAT-0042", "cross-sectional", "each day trade only the instrument with the narrowest opening range relative to its 14-day range", xs_fn, G),
    ("STRAT-0043", "time-series", "every first close beyond the opening range, stop far side or mid, flat at session end", stream(None), G),
    ("STRAT-0044", "lead-lag", "only breakouts in the direction of the overnight move (previous close -> open)", stream(ll), G),
    ("STRAT-0045", "regime-conditioned", "only breakouts with / against the 50-day trend", stream(rg), dict(G, reg=["with", "against"])),
    ("STRAT-0046", "term-structure", "gated by the 10y-3m yield-curve sign", stream(ts_), dict(G, side=["steep", "inverted"])),
    ("STRAT-0047", "flow-based", "breakout bar volume at least vr x the opening-range average (tick volume)", stream(fl), dict(G, vr=[1.5, 2.5])),
    ("STRAT-0048", "relative-value", "opening-range breakout on the NQ/SPX ratio (long one, short the other)", stream(None, ["NQ-SPX"]), G),
    ("STRAT-0049", "volatility-based", "only when the opening range is narrow / wide vs its 1-year median (relative to 14-day range)", stream(vb), dict(G, w=["narrow", "wide"])),
    ("STRAT-0050", "execution-aware", "limit order back at the range edge within 60 min instead of a market order; far stop", stream(None, col_of=lambda p: "limit"), {"M": [15, 30]}),
]
