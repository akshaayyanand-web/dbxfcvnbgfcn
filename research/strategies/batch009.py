"""STRAT-0801..0900: on-chain / crypto structure. Testable: stablecoin supply impulse (83), miner behaviour (85), liquidation-funding interaction (89),
crypto variance risk premium (90, synthetic swaps on Deribit DVOL). Blocked: token unlocks (81), exchange flows (82), holder cohorts (84), DEX pools (86), AMM vs CEX (87), cross-chain (88)."""
import numpy as np, pandas as pd
from strategies.lib import *
import crypto2
from engine import P as EP, _rets
from strategies.batch008 import fund, oi, met, xs, prem, btc_vol_pct, FU
from vol import varswap
C2 = crypto2.load()
FORMS = ["event-triggered", "cross-sectional", "time-series", "lead-lag", "regime-conditioned", "term-structure", "flow-based", "relative-value", "volatility-based", "execution-aware"]
ST = C2["stable"]; ST.index = ST.index.normalize()
def sg(R, n): return np.log(ST).diff(n).reindex(R.index, method="ffill").shift(1)          # stablecoin supply growth (known next day)
def bcast(s, R, cols=None): return pd.DataFrame({c: s if (cols is None or c in cols) else 0.0 for c in R.columns}, index=R.index).fillna(0)
MN = C2["miners"]; MN.index = MN.index.normalize()
def mser(R, col): return MN[col].reindex(R.index, method="ffill").shift(1)
def S(sid, fam, form, d, U, fn, gr, sizing=True): return dict(id=sid, family=fam, form=form, desc=d, universes=U, fn=fn, grid=gr, sizing=sizing)
def specs():
    o = []; F = "Stablecoin supply impulse"
    o += [S("STRAT-0821", F, "event-triggered", "large mint day (total USD stablecoin supply +k% in a day): long crypto for H days", ["crypto"], lambda R, p: bcast(hold(pd.DataFrame({"x": g_(sg(R, 1) > p["k"])}), p["H"])["x"], R), {"k": [0.003, 0.006], "H": [7]}),
          S("STRAT-0822", F, "cross-sectional", "when supply is growing, long high-beta alts vs BTC; when shrinking, the reverse", ["crypto"], lambda R, p: _beta_rot(R, p["n"]), {"n": [7, 30]}),
          S("STRAT-0823", F, "time-series", "long crypto when n-day stablecoin supply growth is positive, flat otherwise", ["crypto", "btc"], lambda R, p: bcast(g_(sg(R, p["n"]) > 0), R), {"n": [7, 30, 90]}),
          S("STRAT-0824", F, "lead-lag", "supply growth leads prices by L days: signal is the growth from L+n to L days ago", ["crypto"], lambda R, p: bcast(g_(sg(R, 30).shift(p["L"]) > 0), R), {"L": [7, 14]}),
          S("STRAT-0825", F, "regime-conditioned", "supply-growth rule only when BTC is above / below its 200-day average", ["crypto"],
            lambda R, p: bcast(g_(sg(R, 30) > 0) * g_((lambda b: (b > b.rolling(200).mean()) if p["side"] == "up" else (b <= b.rolling(200).mean()))(EP["crypto"]["BTC"].reindex(R.index))), R), {"side": ["up", "down"]}),
          S("STRAT-0826", F, "term-structure", "supply acceleration: 7-day growth above the 90-day average daily pace -> long", ["crypto"], lambda R, p: bcast(g_(sg(R, 7) / 7 > sg(R, 90) / 90), R), {"x": [1]}),
          S("STRAT-0827", F, "flow-based", "supply growth and taker buying both positive -> long", ["crypto"], lambda R, p: g_(sg(R, 30) > 0).values[:, None] * g_(EP["crypto_tb"].reindex(R.index)[R.columns].rolling(7).mean() > 0.5), {"x": [1]}),
          S("STRAT-0828", F, "relative-value", "ETH vs BTC: long ETH/short BTC when supply grows (new money goes further out the risk curve)", ["crypto"], lambda R, p: _ethbtc(R, p["n"]), {"n": [7, 30]}),
          S("STRAT-0829", F, "volatility-based", "supply-growth rule only when BTC vol is below / above its median", ["crypto"], lambda R, p: bcast(g_(sg(R, 30) > 0) * g_((btc_vol_pct(R) < 0.5) if p["side"] == "calm" else (btc_vol_pct(R) >= 0.5)), R), {"side": ["calm", "turbulent"]}),
          S("STRAT-0830", F, "execution-aware", "supply-growth rule decided weekly", ["crypto"], lambda R, p: w_exec(bcast(g_(sg(R, 30) > 0), R)), {"x": [1]})]
    F = "Miner inventory behavior"
    hr = lambda R: mser(R, "hash-rate"); rev = lambda R: mser(R, "miners-revenue")
    ribbon = lambda R: g_((hr(R).rolling(30).mean() > hr(R).rolling(60).mean()) & (hr(R).rolling(30).mean().shift(10) < hr(R).rolling(60).mean().shift(10)))
    o += [S("STRAT-0841", F, "event-triggered", "negative difficulty adjustment (miners capitulated): long BTC for H days", ["btc"], lambda R, p: hold(pd.DataFrame({"BTC": g_(mser(R, "difficulty") < mser(R, "difficulty").shift(1) * 0.97)}), p["H"]), {"H": [14, 30]}),
          S("STRAT-0842", F, "cross-sectional", "miner stress (hash-price at 1-year low quartile) -> long alts / short BTC (miners sell BTC)", ["crypto"], lambda R, p: _miner_rot(R), {"x": [1]}),
          S("STRAT-0843", F, "time-series", "hash ribbons: 30-day hash-rate average crosses back above the 60-day after capitulation -> long BTC for H days", ["btc"], lambda R, p: hold(pd.DataFrame({"BTC": ribbon(R)}), p["H"]), {"H": [30, 90]}),
          S("STRAT-0844", F, "lead-lag", "hash-rate growth over 90 days (miner investment) leads price: long BTC when positive", ["btc"], lambda R, p: pd.DataFrame({"BTC": g_(hr(R) / hr(R).shift(p["n"]) > 1)}), {"n": [30, 90]}),
          S("STRAT-0845", F, "regime-conditioned", "hash-ribbon buy only when BTC is below its 200-day average (bear-market capitulation)", ["btc"], lambda R, p: hold(pd.DataFrame({"BTC": ribbon(R) * g_(EP["crypto"]["BTC"].reindex(R.index) < EP["crypto"]["BTC"].reindex(R.index).rolling(200).mean())}), p["H"]), {"H": [30, 90]}),
          S("STRAT-0846", F, "term-structure", "difficulty ribbon: long BTC when the 9-day difficulty average is above the 90-day (expansion), flat when compressed", ["btc"], lambda R, p: pd.DataFrame({"BTC": g_(mser(R, "difficulty").rolling(9).mean() > mser(R, "difficulty").rolling(90).mean())}), {"x": [1]}),
          S("STRAT-0847", F, "flow-based", "miner revenue (USD) collapse: 30-day revenue below k x its 1-year average -> forced selling done -> long", ["btc"], lambda R, p: pd.DataFrame({"BTC": g_(rev(R).rolling(30).mean() < p["k"] * rev(R).rolling(365).mean())}), {"k": [0.6, 0.8]}),
          S("STRAT-0848", F, "relative-value", "hash-price (revenue per unit hash) z-score: low (miners squeezed) -> long, high -> flat", ["btc"], lambda R, p: pd.DataFrame({"BTC": g_(((rev(R) / hr(R)) - (rev(R) / hr(R)).rolling(365).mean()) / (rev(R) / hr(R)).rolling(365).std() < -p["z"])}), {"z": [0.5, 1.0]}),
          S("STRAT-0849", F, "volatility-based", "hash-rate growth signal only when BTC vol is below its median", ["btc"], lambda R, p: pd.DataFrame({"BTC": g_(hr(R) / hr(R).shift(90) > 1) * g_(R["BTC"].rolling(30).std() < R["BTC"].rolling(30).std().rolling(365, min_periods=120).median())}), {"x": [1]}),
          S("STRAT-0850", F, "execution-aware", "hash-rate growth signal decided monthly", ["btc"], lambda R, p: pd.DataFrame({"BTC": g_(hr(R) / hr(R).shift(90) > 1)}).loc[lambda x: x.index.is_month_end].reindex(R.index).ffill().fillna(0), {"x": [1]})]
    F = "Crypto liquidation funding interaction"
    dO = lambda R, n: oi(R) / oi(R).shift(n) - 1
    o += [S("STRAT-0881", F, "event-triggered", "funding above 30%/yr then OI drops >8% in a day (longs flushed): long H days", ["perp"], lambda R, p: hold(g_((fund(R, 3).shift(1) > 0.3) & (dO(R, 1) < -0.08)), p["H"]), {"H": [3, 7]}),
          S("STRAT-0882", F, "cross-sectional", "rank coins by funding x OI growth (crowded leveraged longs); short the most crowded, long the least", ["perp"], lambda R, p: xs(-(fund(R, 7) * dO(R, p["n"]))), {"n": [7, 14]}),
          S("STRAT-0883", F, "time-series", "negative funding with rising OI (shorts building) -> long (squeeze); high funding with rising OI -> short", ["perp"],
            lambda R, p: g_((fund(R, 7) < 0) & (dO(R, p["n"]) > 0.05)) - g_((fund(R, 7) > 0.3) & (dO(R, p["n"]) > 0.05)), {"n": [3, 7]}),
          S("STRAT-0884", F, "lead-lag", "BTC funding x OI state sets alt direction", ["perp"], lambda R, p: pd.DataFrame({c: (g_((fund(R, 7)["BTC"] < 0) & (dO(R, 7)["BTC"] > 0.05)) - g_((fund(R, 7)["BTC"] > 0.3) & (dO(R, 7)["BTC"] > 0.05))) * (c != "BTC") for c in R.columns}, index=R.index), {"x": [1]}),
          S("STRAT-0885", F, "regime-conditioned", "squeeze rule (0883) only in BTC calm / turbulent regime", ["perp"], lambda R, p: (g_((fund(R, 7) < 0) & (dO(R, 3) > 0.05)) - g_((fund(R, 7) > 0.3) & (dO(R, 3) > 0.05))).mul(g_((btc_vol_pct(R) < 0.5) if p["reg"] == "calm" else (btc_vol_pct(R) >= 0.5)), axis=0), {"reg": ["calm", "turbulent"]}),
          S("STRAT-0886", F, "term-structure", "negative perp premium AND negative funding with OI rising -> long (term structure inverted by shorts)", ["perp"], lambda R, p: g_((prem(R) < 0) & (fund(R, 3) < 0) & (dO(R, p["n"]) > 0)), {"n": [3, 7]}),
          S("STRAT-0887", F, "flow-based", "funding high and takers turning net sellers (taker L/S < 1) -> short", ["perp"], lambda R, p: -g_((fund(R, 7) > p["th"]) & (met(R, "taker_ls").rolling(3).mean() < 1)), {"th": [0.2, 0.4]}),
          S("STRAT-0888", F, "relative-value", "long the coin with lowest funding x OI-growth vs short the highest, within pairs", ["perp"], lambda R, p: _pair_crowd(R), {"x": [1]}),
          S("STRAT-0889", F, "volatility-based", "squeeze rule only when the coin's vol is low (pressure builds quietly)", ["perp"], lambda R, p: (g_((fund(R, 7) < 0) & (dO(R, 3) > 0.05)) - g_((fund(R, 7) > 0.3) & (dO(R, 3) > 0.05))).where(R.rolling(30).std() < R.rolling(30).std().rolling(365, min_periods=120).median(), 0), {"x": [1]}),
          S("STRAT-0890", F, "execution-aware", "squeeze rule entered one day late", ["perp"], lambda R, p: (g_((fund(R, 7) < 0) & (dO(R, 3) > 0.05)) - g_((fund(R, 7) > 0.3) & (dO(R, 3) > 0.05))).shift(1).fillna(0), {"x": [1]})]
    for off, (fam, why) in {800: ("Crypto token unlock pressure", "token vesting/unlock schedules"), 810: ("Crypto exchange-flow signal", "on-chain exchange inflow/outflow (CoinMetrics/Glassnode access refused)"),
                            830: ("On-chain holder cohort behavior", "on-chain UTXO/holder cohort data"), 850: ("DEX pool imbalance", "DEX pool reserves and swaps"),
                            860: ("AMM versus CEX arbitrage", "AMM pool prices/blocks"), 870: ("Cross-chain price discrepancy", "prices of the same asset on several chains/bridges")}.items():
        for j, form in enumerate(FORMS): o.append(dict(id=f"STRAT-{off + j + 1:04d}", family=fam, form=form, blocked=why + " - not available in this environment"))
    return sorted(o, key=lambda s: s["id"])
def g_(m): return m.astype(float)
def _beta_rot(R, n):
    s = np.sign(sg(R, n)).fillna(0); w = pd.DataFrame(0.0, index=R.index, columns=R.columns); alts = [c for c in R.columns if c != "BTC"]
    for c in alts: w[c] = s / len(alts)
    w["BTC"] = -s; return w
def _ethbtc(R, n):
    s = np.sign(sg(R, n)).fillna(0); w = pd.DataFrame(0.0, index=R.index, columns=R.columns); w["ETH"] = s; w["BTC"] = -s; return w
def _miner_rot(R):
    hp = mser(R, "miners-revenue") / mser(R, "hash-rate"); low = g_(hp.rolling(365).rank(pct=True) < 0.25)
    w = pd.DataFrame(0.0, index=R.index, columns=R.columns); alts = [c for c in R.columns if c != "BTC"]
    for c in alts: w[c] = low / len(alts)
    w["BTC"] = -low; return w
def _pair_crowd(R):
    c = fund(R, 7) * (oi(R) / oi(R).shift(7) - 1); w = pd.DataFrame(0.0, index=R.index, columns=R.columns)
    for a, b in [("ETH", "BTC"), ("SOL", "ETH"), ("XRP", "BTC"), ("DOGE", "BTC")]:
        s = np.sign(c[b] - c[a]).fillna(0); w[a] += s; w[b] -= s
    return w / 4
# ---------- crypto variance risk premium: synthetic 30-day swaps struck at DVOL ----------
DV = C2["dvol"]; DV.index = DV.index.normalize().tz_localize(None)
def jdv(c):
    r = EP["crypto"][c].pct_change(); r.index = r.index.tz_localize(None); return pd.DataFrame({"r": r, "iv": DV[c]}).dropna()
JB, JE = jdv("BTC"), jdv("ETH")
def cvs(j, fn): return varswap("BTC", fn, T=30, iv_override=j, ann=365, cost_vp=1.0)
ONE = lambda j, r: np.ones(len(r))
def rv(j, n=30): return (j.r ** 2).rolling(n).mean() * 365
F90 = [
    ("STRAT-0891", "event-triggered", "sell 30-day variance only on swaps started after a DVOL spike (+20% in 5 days)", lambda p: pd.DataFrame({"BTC": cvs(JB, lambda j, r: (j.iv / j.iv.shift(5) - 1 > p["u"]).values[r].astype(int)), "ETH": cvs(JE, lambda j, r: (j.iv / j.iv.shift(5) - 1 > p["u"]).values[r].astype(int))}), {"u": [0.2]}),
    ("STRAT-0892", "cross-sectional", "each roll sell variance on whichever of BTC/ETH has the higher implied/realised ratio", lambda p: _cxs(), {"x": [1]}),
    ("STRAT-0893", "time-series", "always short 30-day BTC and ETH variance struck at DVOL (crypto variance risk premium)", lambda p: pd.DataFrame({"BTC": cvs(JB, ONE), "ETH": cvs(JE, ONE)}), {"x": [1]}),
    ("STRAT-0894", "lead-lag", "sell crypto variance only when the equity VIX is below its 1-year median (equity vol leads crypto vol)", lambda p: pd.DataFrame({k: cvs(j, lambda jj, r: (_vix(jj) < 0.5).values[r].astype(int)) for k, j in (("BTC", JB), ("ETH", JE))}), {"x": [1]}),
    ("STRAT-0895", "regime-conditioned", "short crypto variance only when BTC is above / below its 200-day average", lambda p: pd.DataFrame({k: cvs(j, lambda jj, r: _btrend(jj, p["side"])[r]) for k, j in (("BTC", JB), ("ETH", JE))}), {"side": ["up", "down"]}),
    ("STRAT-0896", "term-structure", "short crypto variance only when DVOL is above trailing 30-day realised (positive premium)", lambda p: pd.DataFrame({k: cvs(j, lambda jj, r: ((jj.iv / 100) ** 2 > rv(jj)).values[r].astype(int)) for k, j in (("BTC", JB), ("ETH", JE))}), {"x": [1]}),
    ("STRAT-0898", "relative-value", "short BTC variance / long ETH variance (or reverse) by which implied/realised ratio is richer", lambda p: _crv(), {"x": [1]}),
    ("STRAT-0899", "volatility-based", "short crypto variance only when DVOL fell over the last 5 days (vol momentum down)", lambda p: pd.DataFrame({k: cvs(j, lambda jj, r: (jj.iv < jj.iv.shift(5)).values[r].astype(int)) for k, j in (("BTC", JB), ("ETH", JE))}), {"x": [1]}),
    ("STRAT-0900", "execution-aware", "always short crypto variance, entered one day after the scheduled roll", lambda p: pd.DataFrame({"BTC": cvs(JB, ONE).shift(1), "ETH": cvs(JE, ONE).shift(1)}).fillna(0), {"x": [1]}),
]
def _vix(j):
    from data import _fred
    v = _fred("VIXCLS").reindex(j.index, method="ffill"); return v.rolling(252, min_periods=126).rank(pct=True)
def _btrend(j, side):
    b = EP["crypto"]["BTC"].copy(); b.index = b.index.tz_localize(None); up = (b > b.rolling(200).mean()).reindex(j.index, method="ffill").values
    return (up if side == "up" else ~up).astype(int)
def _cxs():
    a = ((JB.iv / 100) ** 2 / rv(JB)); b = ((JE.iv / 100) ** 2 / rv(JE)).reindex(a.index); pick = (a >= b)
    return pd.DataFrame({"BTC": cvs(JB, lambda j, r: pick.reindex(j.index).fillna(False).values[r].astype(int)), "ETH": cvs(JE, lambda j, r: (~pick).reindex(j.index).fillna(False).values[r].astype(int))})
def _crv():
    a = ((JB.iv / 100) ** 2 / rv(JB)); b = ((JE.iv / 100) ** 2 / rv(JE)).reindex(a.index); d = np.sign(a - b).fillna(0)
    x = cvs(JB, lambda j, r: d.reindex(j.index).fillna(0).values[r]); y = cvs(JE, lambda j, r: -d.reindex(j.index).fillna(0).values[r])
    return pd.DataFrame({"PAIR": (x + y.reindex(x.index).fillna(0)) / 2})
FAMS = {"F90": ("Crypto volatility risk premium", F90)}
EXTRA_BLOCK = {"STRAT-0897": "crypto options flow / open interest by strike (Deribit trade history not downloaded)"}
