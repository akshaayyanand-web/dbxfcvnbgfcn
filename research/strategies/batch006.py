"""STRAT-0501..0600. Testable: options implied-realised (56), variance risk premium (57), vol term structure (58), skew (59, as a signal only)
via synthetic variance swaps on VIX-family indices. Blocked: ETF creation/redemption (51), fund flows (52), 13F (53), short interest (54, 55), dispersion (60)."""
import numpy as np, pandas as pd
from vol import UND, varswap, trail_rv, cboe
from data import _fred
from engine import P
from strategies.lib import nfp_mask
ALL = list(UND)
def iv2(j): return (j.iv / 100) ** 2
def frame(d): return pd.DataFrame(d).sort_index()
VIX3M = pd.concat([_fred("VXVCLS"), cboe("VIX3M")]).groupby(level=0).last(); VVIX = cboe("VVIX"); SKEW = cboe("SKEW"); VIX9D = cboe("VIX9D")
def at(series, j, rolls): return series.reindex(j.index, method="ffill").values[rolls]
def mkt_ex():
    f = P["ff3"]; return f["Mkt-RF"]
def timing(sig):
    """equity timing stream: signal at close t earns market excess return t+1."""
    m = mkt_ex(); s = sig.reindex(m.index, method="ffill").shift(1).fillna(0); return frame({"MKT": (s * m).loc["1990":]})
def S(name, fn, T=21, **kw): return varswap(name, fn, T=T, **kw)

def ratio_sign(N, mode):
    def f(j, r):
        x = (iv2(j) / trail_rv(j, N)).values[r]
        return np.where(x > 1, 1, np.where(mode == "ls", -1, 0)) * ~np.isnan(x)
    return f
F56 = [
    ("STRAT-0551", "event-triggered", "sell variance only on swaps started the day after a VIX spike (+20% in 5 days): post-shock implied overshoot",
     lambda p: frame({"SPX": _spike_swaps(p["up"])}), {"up": [0.2, 0.4]}),
    ("STRAT-0552", "cross-sectional", "each roll, sell variance only on the underlying with the highest implied/realised ratio",
     lambda p: _xs_ratio(p["N"]), {"N": [21, 63]}),
    ("STRAT-0553", "time-series", "sell variance when implied variance > trailing realised (N days); buy it (ls) or stand aside when implied is cheaper",
     lambda p: frame({k: S(k, ratio_sign(p["N"], p["mode"])) for k in ALL}), {"N": [21, 63], "mode": ["short", "ls"]}),
    ("STRAT-0554", "lead-lag", "the S&P implied/realised signal decides the variance position on the other underlyings (SPX vol leads)",
     lambda p: frame({k: S(k, _lead(k, p["N"])) for k in ALL if k != "SPX"}), {"N": [21, 63]}),
    ("STRAT-0555", "regime-conditioned", "implied>realised short-variance rule only when VIX is below / above its 1-year median",
     lambda p: frame({k: S(k, _gate(ratio_sign(21, "short"), lambda j: _vixpct(j) < 0.5 if p["reg"] == "calm" else _vixpct(j) >= 0.5)) for k in ALL}), {"reg": ["calm", "turbulent"]}),
    ("STRAT-0556", "term-structure", "implied>realised short-variance rule only when VIX < VIX3M (contango)",
     lambda p: frame({k: S(k, _gate(ratio_sign(p["N"], "short"), lambda j: (j.iv * 0 + _ts(j)) < 1)) for k in ALL}), {"N": [21, 63]}),
    ("STRAT-0558", "relative-value", "short S&P variance / long Nasdaq variance when the S&P implied/realised ratio is the higher one, else the reverse",
     lambda p: _rv_pair(p["N"]), {"N": [21, 63]}),
    ("STRAT-0559", "volatility-based", "implied>realised short-variance rule only when VVIX is below its 1-year median (calm vol-of-vol)",
     lambda p: frame({k: S(k, _gate(ratio_sign(p["N"], "short"), lambda j: VVIX.reindex(j.index, method="ffill") < VVIX.rolling(252).median().reindex(j.index, method="ffill"))) for k in ALL}), {"N": [21, 63]}),
    ("STRAT-0560", "execution-aware", "same rule with weekly swaps (T=5) instead of monthly", lambda p: frame({k: S(k, ratio_sign(p["N"], "short"), T=5) for k in ALL}), {"N": [21, 63]}),
]
def _gate(base, cond):
    def f(j, r):
        c = cond(j); c = c.values[r] if hasattr(c, "values") else c[r]; return base(j, r) * np.nan_to_num(c.astype(float))
    return f
def _vixpct(j):
    v = _fred("VIXCLS").reindex(j.index, method="ffill"); return v.rolling(252, min_periods=126).rank(pct=True)
def _ts(j): return (_fred("VIXCLS") / VIX3M).reindex(j.index, method="ffill")
def _lead(k, N):
    def f(j, r):
        s = UND["SPX"]; x = (iv2(s) / trail_rv(s, N)).reindex(j.index, method="ffill").values[r]; return np.where(x > 1, 1, 0) * ~np.isnan(x)
    return f
def _spike_swaps(up):
    j = UND["SPX"]; v = j.iv; spike = (v / v.shift(5) - 1 > up).values
    def f(jj, r): return spike[r].astype(int)
    return S("SPX", f, T=21)
def _xs_ratio(N):
    out = {}
    R = pd.DataFrame({k: (iv2(j) / trail_rv(j, N)) for k, j in UND.items()})
    best = R.replace([np.inf, -np.inf], np.nan).fillna(-1).idxmax(axis=1)
    for k in ALL:
        out[k] = S(k, lambda j, r, k=k: (best.reindex(j.index, method="ffill").values[r] == k).astype(int))
    return frame(out)
def _rv_pair(N):
    a = (iv2(UND["SPX"]) / trail_rv(UND["SPX"], N)); b = (iv2(UND["NDX"]) / trail_rv(UND["NDX"], N)); d = (a - b)
    sa = S("SPX", lambda j, r: np.sign(d.reindex(j.index, method="ffill").fillna(0).values[r]))
    sb = S("NDX", lambda j, r: -np.sign(d.reindex(j.index, method="ffill").fillna(0).values[r]))
    return frame({"SPX_NDX": (sa + sb.reindex(sa.index).fillna(0)) / 2})
ON = lambda j, r: np.ones(len(r))
F57 = [
    ("STRAT-0561", "event-triggered", "start one-month short-variance swaps the day after each US payrolls release (post-event implied-vol crush)",
     lambda p: frame({k: _event_swaps(k) for k in ("SPX", "NDX")}), {"x": [1]}),
    ("STRAT-0562", "cross-sectional", "sell variance on the underlying whose implied vol is highest relative to its own 1-year history",
     lambda p: _xs_ivpct(), {"x": [1]}),
    ("STRAT-0563", "time-series", "always short one-month variance (unconditional variance risk premium), each underlying", lambda p: frame({k: S(k, ON) for k in p["set"]}), {"set": [("SPX",), tuple(ALL)]}),
    ("STRAT-0564", "lead-lag", "short variance only when implied vol has fallen over the last 5 days (vol momentum down)",
     lambda p: frame({k: S(k, lambda j, r: (j.iv.values[r] < j.iv.shift(5).values[r]).astype(int)) for k in ALL}), {"x": [1]}),
    ("STRAT-0565", "regime-conditioned", "short variance only when the stock market is above / below its 200-day average",
     lambda p: frame({k: S(k, lambda j, r: _mkt_trend(j, r, p["side"])) for k in ALL}), {"side": ["up", "down"]}),
    ("STRAT-0566", "term-structure", "short variance in VIX contango, long variance in backwardation (VIX/VIX3M)",
     lambda p: frame({k: S(k, lambda j, r: np.where(_ts(j).values[r] < 1, 1, np.where(p["ls"], -1, 0))) for k in ALL}), {"ls": [0, 1]}),
    ("STRAT-0568", "relative-value", "short equity (S&P) variance hedged with long gold variance (cross-asset vol spread)",
     lambda p: (lambda a, b: frame({"SPXvGOLD": (a - b.reindex(a.index).fillna(0) * p["h"]).loc["2016":]}))(S("SPX", ON), S("GOLD", ON)), {"h": [0.5, 1.0]}),
    ("STRAT-0569", "volatility-based", "short variance only when VVIX/VIX (vol-of-vol per unit vol) is below its median",
     lambda p: frame({k: S(k, lambda j, r: ((VVIX / _fred("VIXCLS")).reindex(j.index, method="ffill") < (VVIX / _fred("VIXCLS")).rolling(252).median().reindex(j.index, method="ffill")).values[r].astype(int)) for k in ALL}), {"x": [1]}),
    ("STRAT-0570", "execution-aware", "unconditional short variance but rolled with a one-day lag after the scheduled roll (stale-strike robustness)",
     lambda p: frame({k: S(k, ON).shift(1).fillna(0) for k in ALL}), {"x": [1]}),
]
def _event_swaps(k):
    j = UND[k]; ev = nfp_mask(j.index, 1).values
    return S(k, lambda jj, r: ev[r].astype(int), T=1) * 0 + _nfp_monthly(k)
def _nfp_monthly(k):
    j = UND[k]; idx = j.index; ev = np.where(nfp_mask(idx, 1).values)[0]; pnl = pd.Series(0.0, index=idx)
    r = j.r.values; iv = (j.iv.values / 100) ** 2; T = 21
    for s in ev:
        s1 = s + 1; e = min(s1 + T, len(idx) - 1)
        if s1 >= e: continue
        K = iv[s1]; N = 1 / K; cap = 6.25 * K; prev = 0.0; acc = 0.0
        for t in range(s1 + 1, e + 1):
            acc += r[t] ** 2; k_ = t - s1
            V = N * (min(acc * 252 / T + (T - k_) / T * iv[t], cap) - K) if t < e else N * (min(acc * 252 / T, cap) - K)
            pnl.iloc[t] += -(V - prev); prev = V
        pnl.iloc[s1 + 1] -= N * 2 * np.sqrt(K) * 0.005
    return pnl
def _xs_ivpct():
    P_ = pd.DataFrame({k: j.iv.rolling(252, min_periods=126).rank(pct=True) for k, j in UND.items()}); best = P_.fillna(-1).idxmax(axis=1)
    return frame({k: S(k, lambda j, r, k=k: (best.reindex(j.index, method="ffill").values[r] == k).astype(int)) for k in ALL})
def _mkt_trend(j, r, side):
    m = (1 + P["ff3"]["Mkt-RF"] + P["ff3"]["RF"]).cumprod(); up = (m > m.rolling(200).mean()).reindex(j.index, method="ffill").values[r]
    return (up if side == "up" else ~up).astype(int)
# term structure family: synthetic 3-month swaps on VIX3M
def var3m():
    j = UND["SPX"]; k3 = VIX3M.reindex(j.index, method="ffill"); jj = pd.DataFrame({"r": j.r, "iv": k3}).dropna(); return jj
J3 = var3m()
def S3(fn): return varswap("SPX", fn, T=63, iv_override=J3)
def calendar(sign_fn):
    a = S("SPX", sign_fn); b = S3(lambda j, r: -sign_fn(j, r) if True else 0)
    return frame({"CAL": (a + b.reindex(a.index).fillna(0) * 1.0).loc["2008":]})
def ts_sign(j, r): return np.where(_ts(j).values[r] < 1, 1, -1)
F58 = [
    ("STRAT-0571", "event-triggered", "equity timing: after VIX term structure flips back from backwardation to contango, long stocks for 20 days",
     lambda p: timing(_flip_back(p["H"])), {"H": [10, 20]}),
    ("STRAT-0573", "time-series", "calendar: in contango short 1-month / long 3-month variance (front premium decays), reverse in backwardation", lambda p: calendar(ts_sign), {"x": [1]}),
    ("STRAT-0574", "lead-lag", "VIX term-structure slope leads stocks: long the market when VIX/VIX3M < q, flat otherwise",
     lambda p: timing((_fred("VIXCLS") / VIX3M < p["q"]).astype(float)), {"q": [0.9, 1.0]}),
    ("STRAT-0575", "regime-conditioned", "calendar rule only when VIX below / above its 1-year median",
     lambda p: calendar(lambda j, r: ts_sign(j, r) * ((_vixpct(j) < 0.5) if p["reg"] == "calm" else (_vixpct(j) >= 0.5)).values[r]), {"reg": ["calm", "turbulent"]}),
    ("STRAT-0576", "term-structure", "very short end: short one-month variance only when VIX9D < VIX (no imminent event priced)",
     lambda p: frame({"SPX": S("SPX", lambda j, r: ((VIX9D / _fred("VIXCLS")).reindex(j.index, method="ffill") < p["q"]).values[r].astype(int)).loc["2011":]}), {"q": [0.95, 1.0]}),
    ("STRAT-0578", "relative-value", "which tenor carries the premium: short 3-month variance alone (vs short 1-month in 0563)", lambda p: frame({"V3M": S3(ON).loc["2008":]}), {"x": [1]}),
    ("STRAT-0579", "volatility-based", "calendar rule only when VVIX is below its median", lambda p: calendar(lambda j, r: ts_sign(j, r) * (VVIX.reindex(j.index, method="ffill") < VVIX.rolling(252).median().reindex(j.index, method="ffill")).values[r]), {"x": [1]}),
    ("STRAT-0580", "execution-aware", "calendar rule with weekly front swaps (T=5)", lambda p: frame({"CAL": (varswap("SPX", ts_sign, T=5) + S3(lambda j, r: -ts_sign(j, r)).reindex(UND["SPX"].index).fillna(0)).loc["2008":]}), {"x": [1]}),
]
def _flip_back(H):
    ts = (_fred("VIXCLS") / VIX3M).dropna(); flip = (ts < 1) & (ts.shift(1) >= 1); s = flip.astype(float).replace(0, np.nan).ffill(limit=H - 1).fillna(0); return s
F59 = [
    ("STRAT-0581", "event-triggered", "after a SKEW spike (+10 points in 5 days) buy one-month S&P variance (tail hedge pays?)",
     lambda p: frame({"SPX": S("SPX", lambda j, r: -((SKEW - SKEW.shift(5)).reindex(j.index, method="ffill").values[r] > p["d"]).astype(int))}), {"d": [10, 15]}),
    ("STRAT-0583", "time-series", "equity timing: out of the market when CBOE SKEW is in its top quintile (1-year), long otherwise",
     lambda p: timing((SKEW.rolling(252).rank(pct=True) < p["q"]).astype(float)), {"q": [0.8, 0.9]}),
    ("STRAT-0584", "lead-lag", "SKEW changes lead realised vol: short variance only when SKEW fell over the last 21 days",
     lambda p: frame({"SPX": S("SPX", lambda j, r: ((SKEW - SKEW.shift(21)).reindex(j.index, method="ffill").values[r] < 0).astype(int))}), {"x": [1]}),
    ("STRAT-0585", "regime-conditioned", "SKEW equity-timing rule only in calm / turbulent VIX regime",
     lambda p: timing(((SKEW.rolling(252).rank(pct=True) < 0.8) | ((_fred("VIXCLS").rolling(252).rank(pct=True) < 0.5) if p["reg"] == "turbulent" else (_fred("VIXCLS").rolling(252).rank(pct=True) >= 0.5))).astype(float)), {"reg": ["calm", "turbulent"]}),
    ("STRAT-0586", "term-structure", "short variance when SKEW is high AND VIX is in contango (tail fear priced but no near-term stress)",
     lambda p: frame({"SPX": S("SPX", lambda j, r: ((SKEW.rolling(252).rank(pct=True).reindex(j.index, method="ffill") > 0.5) & (_ts(j) < 1)).values[r].astype(int))}), {"x": [1]}),
    ("STRAT-0588", "relative-value", "SKEW relative to VIX: short variance when SKEW/VIX is in its top half (tails rich vs ATM)",
     lambda p: frame({"SPX": S("SPX", lambda j, r: ((SKEW / _fred("VIXCLS")).rolling(252).rank(pct=True).reindex(j.index, method="ffill").values[r] > p["q"]).astype(int))}), {"q": [0.5, 0.7]}),
    ("STRAT-0589", "volatility-based", "short variance sized by the implied-minus-realised gap (zero when negative)",
     lambda p: frame({"SPX": _sized()}), {"x": [1]}),
    ("STRAT-0590", "execution-aware", "SKEW timing rule acted on one week late", lambda p: timing((SKEW.rolling(252).rank(pct=True) < 0.8).astype(float).shift(5)), {"x": [1]}),
]
def _sized():
    j = UND["SPX"]; g = (iv2(j) - trail_rv(j, 21)).clip(lower=0) / iv2(j)
    return S("SPX", lambda jj, r: np.nan_to_num(g.values[r]))
BLOCKED = {500: ("ETF creation-redemption pressure", "ETF shares-outstanding / creation-redemption data"), 510: ("Mutual fund flow pressure", "fund flow data"),
           520: ("Institutional ownership change", "13F holdings"), 530: ("Short interest crowding", "short interest by stock"), 540: ("Short-sale constraint premium", "borrow fees / short interest by stock"),
           590: ("Options dispersion", "single-stock implied vols / implied correlation")}
EXTRA_BLOCK = {"STRAT-0557": "options volume / open interest / put-call flow data", "STRAT-0567": "options volume / dealer positioning data",
               "STRAT-0572": "term structures of several underlyings (only S&P VIX/VIX3M available)", "STRAT-0577": "VIX futures volume / positioning (COT)",
               "STRAT-0582": "skew for several underlyings (only S&P SKEW available)", "STRAT-0587": "options flow by strike"}
FAMS = {"F56": ("Options implied-realized volatility", F56), "F57": ("Variance risk premium", F57), "F58": ("Volatility term structure", F58), "F59": ("Volatility skew relative value", F59)}
