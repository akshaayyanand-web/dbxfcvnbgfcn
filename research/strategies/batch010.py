"""STRAT-0901..1000 microstructure on the BTCUSDT perpetual sample (100 days, one every 14 days, 2023-01..2026-10).
Minute signals pay taker 4.5 bp per side; market-making uses the conservative fill simulator (fill only when a trade prints through the quote, maker fee 2 bp).
Streams = one P&L value per sample day. Queue-position market making (94) is blocked (needs L3 queue data)."""
import numpy as np, pandas as pd
from micro import table, trades, days, mm_sim
T = table().copy(); T["r1"] = T.groupby("day").close.shift(-1) / T.close - 1; T["r1"] = T.r1.fillna(0)
T["vol15"] = T.groupby("day").close.transform(lambda c: c.pct_change().rolling(15).std())
def daily(pos, cost=4.5):
    pos = pos.fillna(0).clip(-1, 1); ch = pos.groupby(T.day).diff().fillna(pos).abs()
    pnl = pos * T.r1 - ch * cost / 1e4
    return pd.DataFrame({"BTC": pnl.groupby(T.day).sum()})
def holdm(ev, H):
    e = ev.replace(0, np.nan); return e.groupby(T.day).ffill(limit=H - 1).fillna(0) if H > 1 else ev
def sgn(x): return np.sign(x).fillna(0)
med = lambda x: x.groupby(T.day).transform("median")
def fam(prefix, name, rules):
    return (name, [(f"STRAT-{prefix + i + 1:04d}", form, d, fn, g) for i, (form, d, fn, g) in enumerate(rules) if fn is not None])
F91 = fam(900, "Order-book imbalance", [
    ("event-triggered", "imbalance shock: +/-1% book imbalance changes by more than x in a minute -> trade in its direction for H minutes", lambda p: daily(holdm(sgn(T.imb1.diff()) * (T.imb1.diff().abs() > p["x"]), p["H"])), {"x": [0.2, 0.4], "H": [3, 10]}),
    ("cross-sectional", "near vs deep book disagree: follow the deep (+/-5%) imbalance when it opposes the near (+/-1%) one", lambda p: daily(sgn(T.imb5) * (sgn(T.imb5) != sgn(T.imb1)) * (T.imb5.abs() > p["th"])), {"th": [0.1, 0.2]}),
    ("time-series", "trade the sign of the +/-1% book imbalance when |imbalance| > th", lambda p: daily(sgn(T.imb1) * (T.imb1.abs() > p["th"])), {"th": [0.2, 0.4, 0.6]}),
    ("lead-lag", "deep-book imbalance changes lead price: trade the sign of the 5-minute change in +/-5% imbalance", lambda p: daily(sgn(T.imb5 - T.imb5.shift(5)) * ((T.imb5 - T.imb5.shift(5)).abs() > p["x"])), {"x": [0.05, 0.1]}),
    ("regime-conditioned", "imbalance rule only in minutes with 15-minute vol above / below the day's median", lambda p: daily(sgn(T.imb1) * (T.imb1.abs() > 0.4) * ((T.vol15 > med(T.vol15)) if p["side"] == "high" else (T.vol15 <= med(T.vol15)))), {"side": ["high", "low"]}),
    ("term-structure", "trade only when near and deep imbalance agree in sign and both exceed th", lambda p: daily(sgn(T.imb1) * (sgn(T.imb1) == sgn(T.imb5)) * (T.imb1.abs() > p["th"]) * (T.imb5.abs() > p["th"] / 2)), {"th": [0.2, 0.4]}),
    ("flow-based", "imbalance confirmed by same-sign taker flow in the minute", lambda p: daily(sgn(T.imb1) * (sgn(T.imb1) == sgn(T.svol)) * (T.imb1.abs() > p["th"])), {"th": [0.2, 0.4]}),
    ("relative-value", "imbalance relative to its own day average (z-score > k)", lambda p: daily(sgn(T.imb1 - T.groupby("day").imb1.transform("mean")) * ((T.imb1 - T.groupby("day").imb1.transform("mean")).abs() > p["k"] * T.groupby("day").imb1.transform("std"))), {"k": [1.0, 2.0]}),
    ("volatility-based", "imbalance rule only when the +/-1% book is thinner than the day's median (thin books move more)", lambda p: daily(sgn(T.imb1) * (T.imb1.abs() > p["th"]) * (T.depth1 < med(T.depth1))), {"th": [0.2, 0.4]}),
    ("execution-aware", "same imbalance rule but entering with maker orders at 2 bp per side (assumes passive fills; optimistic)", lambda p: daily(sgn(T.imb1) * (T.imb1.abs() > p["th"]), cost=2.0), {"th": [0.4, 0.6]})])
F92 = fam(910, "Order-flow toxicity", [
    ("event-triggered", "VPIN spike (above its day's 90th pct): follow the last 5 minutes' signed flow for H minutes", lambda p: daily(holdm(sgn(T.svol.rolling(5).sum()) * (T.vpin > T.groupby("day").vpin.transform(lambda v: v.quantile(0.9))), p["H"])), {"H": [5, 15]}),
    ("cross-sectional", None, None, None),
    ("time-series", "high VPIN = informed flow: follow 5-minute signed volume only when VPIN > q-quantile of the day", lambda p: daily(sgn(T.svol.rolling(5).sum()) * (T.vpin > T.groupby("day").vpin.transform(lambda v: v.quantile(p["q"])))), {"q": [0.5, 0.8]}),
    ("lead-lag", "rising VPIN leads volatility: trade breakouts of the 15-minute range only when VPIN rose over 30 minutes", lambda p: daily(_brk(15) * (T.vpin > T.vpin.shift(30))), {"x": [1]}),
    ("regime-conditioned", "low VPIN = uninformed flow: fade 5-minute signed volume when VPIN is below the day's median", lambda p: daily(-sgn(T.svol.rolling(5).sum()) * (T.vpin < med(T.vpin))), {"x": [1]}),
    ("term-structure", "VPIN short (10-bucket) vs long (day) average: follow flow when short > long", lambda p: daily(sgn(T.svol.rolling(5).sum()) * (T.vpin > T.groupby("day").vpin.transform("mean") * p["k"])), {"k": [1.0, 1.2]}),
    ("flow-based", "toxicity from signed volume itself: follow when |5-minute signed volume| is in the day's top decile", lambda p: daily(sgn(T.svol.rolling(5).sum()) * (T.svol.rolling(5).sum().abs() > T.groupby("day").svol.transform(lambda v: v.rolling(5).sum().abs().quantile(0.9)))), {"x": [1]}),
    ("relative-value", "VPIN relative to book depth: follow flow when VPIN high and book thin", lambda p: daily(sgn(T.svol.rolling(5).sum()) * (T.vpin > med(T.vpin)) * (T.depth1 < med(T.depth1))), {"x": [1]}),
    ("volatility-based", "follow flow when VPIN high, sized by inverse 15-minute vol", lambda p: daily((sgn(T.svol.rolling(5).sum()) * (T.vpin > med(T.vpin)) * (med(T.vol15) / T.vol15).clip(upper=1)).fillna(0)), {"x": [1]}),
    ("execution-aware", "VPIN flow-following entered one minute late", lambda p: daily((sgn(T.svol.rolling(5).sum()) * (T.vpin > med(T.vpin))).groupby(T.day).shift(1)), {"x": [1]})])
def _brk(n): h = T.close.groupby(T.day).transform(lambda c: c.shift(1).rolling(n).max()); l = T.close.groupby(T.day).transform(lambda c: c.shift(1).rolling(n).min()); return (T.close > h).astype(float) - (T.close < l).astype(float)
F93 = fam(920, "Trade-sign autocorrelation", [
    ("event-triggered", "burst of one-sided trades (|signed volume| > 4x the day's median |signed volume|): follow it H minutes", lambda p: daily(holdm(sgn(T.svol) * (T.svol.abs() > 4 * med(T.svol.abs())), p["H"])), {"H": [3, 10]}),
    ("cross-sectional", None, None, None),
    ("time-series", "order-splitting persistence: follow the sign of the last minute's signed volume", lambda p: daily(sgn(T.svol.rolling(p["n"]).sum())), {"n": [1, 3, 5]}),
    ("lead-lag", "signed volume leads price: follow signed volume only when price has not yet moved in that direction this minute", lambda p: daily(sgn(T.svol) * (sgn(T.svol) != sgn(T.close - T.open))), {"x": [1]}),
    ("regime-conditioned", "follow signed volume only when the minute's trade-sign autocorrelation is above / below its median", lambda p: daily(sgn(T.svol) * ((T.sgn_ac > med(T.sgn_ac)) if p["side"] == "high" else (T.sgn_ac <= med(T.sgn_ac)))), {"side": ["high", "low"]}),
    ("term-structure", "1-minute and 15-minute signed volume agree -> follow", lambda p: daily(sgn(T.svol) * (sgn(T.svol) == sgn(T.svol.rolling(15).sum()))), {"x": [1]}),
    ("flow-based", "follow signed volume only when trade count is high (genuine flow, not one print)", lambda p: daily(sgn(T.svol) * (T.n > p["k"] * med(T.n))), {"k": [1.5, 3]}),
    ("relative-value", "contrarian: fade signed volume (liquidity-provider view of the same autocorrelation)", lambda p: daily(-sgn(T.svol.rolling(p["n"]).sum())), {"n": [1, 5]}),
    ("volatility-based", "follow signed volume only when 15-minute vol is low (persistence without noise)", lambda p: daily(sgn(T.svol) * (T.vol15 < med(T.vol15))), {"x": [1]}),
    ("execution-aware", "signed-volume following with maker entry at 2 bp per side (optimistic)", lambda p: daily(sgn(T.svol.rolling(p["n"]).sum()), cost=2.0), {"n": [3, 5]})])
# ---------- market making (simulated on trade data) ----------
_DAYS = days()
_TR = {}
def _tr(d):
    if d not in _TR:
        x = trades(d); mt = (x.t // 60000).values; f = T[T.day == pd.Timestamp(d)]
        _TR[d] = (x.t.values.astype(np.int64), x.p.values, x.s.values.astype(np.int64), mt, f)
    return _TR[d]
def mm(half, gamma, max_inv=5.0, tox_col=None, tox_q=1.01, refresh=1000, half_fn=None):
    out = {}
    for d in _DAYS:
        t, p, s, mt, f = _tr(d)
        if tox_col is None: tox = np.zeros(len(t))
        else:
            v = f[tox_col] if isinstance(tox_col, str) else tox_col(f)
            th = v.quantile(tox_q) if tox_q <= 1 else np.inf
            tox = pd.Series(v.values, index=f.index).reindex(mt, method="ffill").fillna(0).values - th
        h = half if half_fn is None else max(half_fn(f), 0.5)
        pnl, fills = mm_sim(t, p, s, h, gamma, max_inv, 2.0, tox, 0.0, refresh)
        out[pd.Timestamp(d)] = pnl / max_inv          # per unit of max inventory notional
    return pd.DataFrame({"MM": pd.Series(out)})
F95 = fam(940, "Inventory-aware market making", [
    ("event-triggered", "quote only in the 10 minutes after a large trade (> $5m) when spreads are wide", lambda p: mm(p["h"], 0.5, tox_col=lambda f: -(f.maxnot.rolling(10, min_periods=1).max() > 5e6).astype(float), tox_q=0.5), {"h": [2, 4]}),
    ("cross-sectional", None, None, None),
    ("time-series", "Avellaneda-Stoikov style: quotes +/- h bp around the last trade, skewed by gamma bp per unit inventory, refresh every second", lambda p: mm(p["h"], p["g"]), {"h": [1, 2, 4], "g": [0.5, 2.0]}),
    ("lead-lag", "skew quotes toward the book imbalance (quote only the side the book leans to)", lambda p: mm(p["h"], 1.0, tox_col=lambda f: f.imb1.abs(), tox_q=0.5), {"h": [2, 4]}),
    ("regime-conditioned", "quote only when 15-minute vol is below the day's median (calm)", lambda p: mm(p["h"], 1.0, tox_col=lambda f: f.close.pct_change().rolling(15).std().fillna(0), tox_q=0.5), {"h": [1, 2]}),
    ("term-structure", "quote only when near and deep imbalance are both small (balanced book across depths)", lambda p: mm(p["h"], 1.0, tox_col=lambda f: f.imb1.abs() + f.imb5.abs(), tox_q=0.5), {"h": [1, 2]}),
    ("flow-based", "pause quoting when the minute's |signed volume| is in the top third", lambda p: mm(p["h"], 1.0, tox_col=lambda f: f.svol.abs(), tox_q=0.66), {"h": [1, 2]}),
    ("relative-value", None, None, None),
    ("volatility-based", "half-spread = k x recent 15-minute vol (in bp), floor 0.5 bp", lambda p: mm(1, 1.0, half_fn=lambda f: p["k"] * float(np.nanmedian(f.close.pct_change().rolling(15).std())) * 1e4), {"k": [0.5, 1.0]}),
    ("execution-aware", "same quotes refreshed every 100 ms instead of 1 s", lambda p: mm(p["h"], 1.0, refresh=100), {"h": [1, 2]})])
F96 = fam(950, "Spread capture with toxicity filter", [
    ("event-triggered", "stop quoting for 5 minutes after any VPIN spike above the day's 90th percentile", lambda p: mm(p["h"], 1.0, tox_col=lambda f: f.vpin.rolling(5, min_periods=1).max(), tox_q=0.9), {"h": [1, 2]}),
    ("cross-sectional", None, None, None),
    ("time-series", "quote only while VPIN is below its day's q-quantile", lambda p: mm(p["h"], 1.0, tox_col="vpin", tox_q=p["q"]), {"h": [1, 2], "q": [0.5, 0.8]}),
    ("lead-lag", "quote only while VPIN is falling (toxicity receding)", lambda p: mm(p["h"], 1.0, tox_col=lambda f: f.vpin.diff(5).fillna(0), tox_q=0.5), {"h": [1, 2]}),
    ("regime-conditioned", "toxicity filter plus calm-vol filter", lambda p: mm(p["h"], 1.0, tox_col=lambda f: f.vpin.rank(pct=True) + f.close.pct_change().rolling(15).std().rank(pct=True), tox_q=0.5), {"h": [1, 2]}),
    ("term-structure", "quote only when 10-bucket VPIN is below the day's average VPIN", lambda p: mm(p["h"], 1.0, tox_col=lambda f: f.vpin - f.vpin.mean(), tox_q=0.5), {"h": [1, 2]}),
    ("flow-based", "toxicity = trade-sign autocorrelation: quote only when it is below the median", lambda p: mm(p["h"], 1.0, tox_col="sgn_ac", tox_q=0.5), {"h": [1, 2]}),
    ("relative-value", "toxicity = VPIN relative to book depth (high VPIN on a thin book): quote when below median", lambda p: mm(p["h"], 1.0, tox_col=lambda f: f.vpin / f.depth1, tox_q=0.5), {"h": [1, 2]}),
    ("volatility-based", "VPIN filter with half-spread widened to k x vol", lambda p: mm(1, 1.0, tox_col="vpin", tox_q=0.8, half_fn=lambda f: p["k"] * float(np.nanmedian(f.close.pct_change().rolling(15).std())) * 1e4), {"k": [0.5, 1.0]}),
    ("execution-aware", "VPIN filter with 100 ms quote refresh", lambda p: mm(p["h"], 1.0, tox_col="vpin", tox_q=0.8, refresh=100), {"h": [1, 2]})])
F98 = fam(970, "Order-book resiliency", [
    ("event-triggered", "depth shock (+/-1% depth falls > x% in a minute): fade that minute's price move for H minutes", lambda p: daily(holdm(-sgn(T.close - T.open) * (T.depth1 / T.depth1.shift(1) - 1 < -p["x"]), p["H"])), {"x": [0.1, 0.2], "H": [5, 15]}),
    ("cross-sectional", None, None, None),
    ("time-series", "fast refill: depth back above its pre-shock level within 3 minutes -> fade the shock move", lambda p: daily(holdm(-sgn(T.close - T.close.shift(3)) * ((T.depth1.shift(3) / T.depth1.shift(4) - 1 < -p["x"]) & (T.depth1 > T.depth1.shift(4))), 10)), {"x": [0.1, 0.2]}),
    ("lead-lag", "slow refill (depth still depressed after 3 minutes) -> follow the shock move", lambda p: daily(holdm(sgn(T.close - T.close.shift(3)) * ((T.depth1.shift(3) / T.depth1.shift(4) - 1 < -p["x"]) & (T.depth1 < 0.9 * T.depth1.shift(4))), 10)), {"x": [0.1, 0.2]}),
    ("regime-conditioned", "depth-shock fade only in high / low vol minutes", lambda p: daily(holdm(-sgn(T.close - T.open) * (T.depth1 / T.depth1.shift(1) - 1 < -0.15) * ((T.vol15 > med(T.vol15)) if p["side"] == "high" else (T.vol15 <= med(T.vol15))), 10)), {"side": ["high", "low"]}),
    ("term-structure", "near-book depth falls while deep book holds (+/-5% imbalance small): fade", lambda p: daily(holdm(-sgn(T.close - T.open) * (T.depth1 / T.depth1.shift(1) - 1 < -0.15) * (T.imb5.abs() < p["th"]), 10)), {"th": [0.1, 0.2]}),
    ("flow-based", "depth shock accompanied by heavy one-sided taker flow: follow it", lambda p: daily(holdm(sgn(T.svol) * (T.depth1 / T.depth1.shift(1) - 1 < -0.15) * (T.svol.abs() > 3 * med(T.svol.abs())), p["H"])), {"H": [5, 15]}),
    ("relative-value", None, None, None),
    ("volatility-based", "depth-shock fade sized by inverse vol", lambda p: daily((holdm(-sgn(T.close - T.open) * (T.depth1 / T.depth1.shift(1) - 1 < -0.15), 10) * (med(T.vol15) / T.vol15).clip(upper=1)).fillna(0)), {"x": [1]}),
    ("execution-aware", "depth-shock fade entered one minute late", lambda p: daily(holdm(-sgn(T.close - T.open) * (T.depth1 / T.depth1.shift(1) - 1 < -0.15), 10).groupby(T.day).shift(1)), {"x": [1]})])
F99 = fam(980, "Large-trade impact decay", [
    ("event-triggered", "a single aggregate trade above $X: fade the minute's move for H minutes (temporary impact decays)", lambda p: daily(holdm(-sgn(T.close - T.open) * (T.maxnot > p["X"]), p["H"])), {"X": [2e6, 5e6], "H": [5, 15]}),
    ("cross-sectional", None, None, None),
    ("time-series", "continuation instead: follow the minute's move after a large trade (information, permanent impact)", lambda p: daily(holdm(sgn(T.close - T.open) * (T.maxnot > p["X"]), p["H"])), {"X": [2e6, 5e6], "H": [5, 15]}),
    ("lead-lag", "large trade without a price move (absorbed): trade in the large trade's direction (hidden demand)", lambda p: daily(holdm(sgn(T.svol) * (T.maxnot > 2e6) * ((T.close / T.open - 1).abs() < p["bp"] / 1e4), 10)), {"bp": [2, 5]}),
    ("regime-conditioned", "large-trade fade only in calm / volatile minutes", lambda p: daily(holdm(-sgn(T.close - T.open) * (T.maxnot > 2e6) * ((T.vol15 > med(T.vol15)) if p["side"] == "high" else (T.vol15 <= med(T.vol15))), 10)), {"side": ["high", "low"]}),
    ("term-structure", "large trade against the 15-minute trend: fade; with the trend: follow", lambda p: daily(holdm(sgn(T.close - T.open) * (T.maxnot > 2e6) * np.where(sgn(T.close - T.open) == sgn(T.close - T.close.shift(15)), 1, -1), p["H"])), {"H": [5, 15]}),
    ("flow-based", "large trade plus heavy same-side flow in the minute: follow", lambda p: daily(holdm(sgn(T.svol) * (T.maxnot > 2e6) * (T.svol.abs() > 3 * med(T.svol.abs())), p["H"])), {"H": [5, 15]}),
    ("relative-value", "large trade relative to book depth (> k% of +/-1% depth): fade", lambda p: daily(holdm(-sgn(T.close - T.open) * (T.maxnot > p["k"] * T.depth1), 10)), {"k": [0.01, 0.02]}),
    ("volatility-based", "large-trade fade only when the move exceeds 2x 15-minute vol", lambda p: daily(holdm(-sgn(T.close - T.open) * (T.maxnot > 2e6) * ((T.close / T.open - 1).abs() > 2 * T.vol15), 10)), {"x": [1]}),
    ("execution-aware", "large-trade fade entered one minute late", lambda p: daily(holdm(-sgn(T.close - T.open) * (T.maxnot > 2e6), 10).groupby(T.day).shift(1)), {"x": [1]})])
def exec_cost(kind, k=1.0):
    """execution research: buy 1 unit through the UTC day. Saving in bp vs TWAP (positive = cheaper). VWAP uses the previous sample day's minute volume profile."""
    out = {}; prev = None
    for d, f in T.groupby("day"):
        twap = f.close.mean()
        if kind == "vwap":
            prof = (prev if prev is not None else f.vol.values * 0 + 1); prof = np.resize(prof, len(f)); px_ = (f.close.values * prof).sum() / prof.sum()
        elif kind == "limit":
            fill = (f.low.values <= f.close.shift(1).fillna(f.open).values * (1 - k / 1e4)); px_ = np.where(fill, f.close.shift(1).fillna(f.open).values * (1 - k / 1e4), f.close.values * (1 + 4.5 / 1e4)).mean()
        elif kind == "front": px_ = f.close.iloc[:60].mean()
        elif kind == "flow": w = np.where(f.svol.values < 0, 2.0, 0.5); px_ = (f.close.values * w).sum() / w.sum()
        out[d] = (twap - px_) / twap
        prev = f.vol.values
    return pd.DataFrame({"EXEC": pd.Series(out)})
F97 = fam(960, "Limit-order placement optimization", [
    ("event-triggered", None, None, None), ("cross-sectional", None, None, None),
    ("time-series", "work a daily buy with limit orders k bp below the last price each minute; unfilled minutes pay taker", lambda p: exec_cost("limit", p["k"]), {"k": [1, 3, 5]}),
    ("lead-lag", None, None, None), ("regime-conditioned", None, None, None), ("term-structure", None, None, None),
    ("flow-based", "weight a daily buy toward minutes with net taker selling (provide liquidity to sellers)", lambda p: exec_cost("flow"), {"x": [1]}),
    ("relative-value", None, None, None), ("volatility-based", None, None, None), ("execution-aware", None, None, None)])
F100 = fam(990, "VWAP execution alpha", [
    ("event-triggered", None, None, None), ("cross-sectional", None, None, None),
    ("time-series", "VWAP schedule (previous sample day's volume profile) vs TWAP for a daily buy", lambda p: exec_cost("vwap"), {"x": [1]}),
    ("lead-lag", None, None, None), ("regime-conditioned", None, None, None),
    ("term-structure", "front-load: execute the whole daily buy in the first hour vs TWAP", lambda p: exec_cost("front"), {"x": [1]}),
    ("flow-based", None, None, None), ("relative-value", None, None, None), ("volatility-based", None, None, None), ("execution-aware", None, None, None)])
FAMS = {k: v for k, v in {"F91": F91, "F92": F92, "F93": F93, "F95": F95, "F96": F96, "F97": F97, "F98": F98, "F99": F99, "F100": F100}.items()}
BLOCKED = {930: ("Queue-position market making", "exchange queue positions / L3 order-book data")}
EXTRA_BLOCK = {**{f"STRAT-{910 + 2:04d}": "cross-sectional toxicity needs several instruments' trade data (only BTCUSDT sampled)",
                  f"STRAT-{920 + 2:04d}": "cross-sectional sign autocorrelation needs several instruments (only BTCUSDT sampled)",
                  f"STRAT-{940 + 2:04d}": "multi-instrument market making needs several instruments", f"STRAT-{940 + 8:04d}": "relative-value quoting needs a hedge instrument's trades",
                  f"STRAT-{950 + 2:04d}": "multi-instrument data", f"STRAT-{970 + 2:04d}": "multi-instrument depth data", f"STRAT-{970 + 8:04d}": "multi-instrument depth data",
                  f"STRAT-{980 + 2:04d}": "multi-instrument trade data"},
               **{f"STRAT-{960 + i:04d}": "execution-layer variant: not a separate trading hypothesis (only the tested placement rules count)" for i in (1, 2, 4, 5, 6, 8, 9, 10)},
               **{f"STRAT-{990 + i:04d}": "execution-layer variant: not a separate trading hypothesis" for i in (1, 2, 4, 5, 7, 8, 9, 10)}}
