"""Two-stage duplicate review: (1) conceptual - every tested entry gets a mechanism class + whether it is a core rule or a filter/timing/execution
layer on a core; (2) statistical - weekly walk-forward P&L correlation, compared only where step 1 says the mechanism could be the same.
DUPLICATE = same class AND |corr| >= 0.7 ; VARIANT = same class, statistically different (not a new mechanism under the protocol: filters, parameters
or indicator swaps of the same idea) ; CORRELATED-DISTINCT = different class but |corr| >= 0.7 (overlapping exposure, still a different mechanism) ; DISTINCT."""
import os, json, pickle, numpy as np, pandas as pd
from data import SCR
H = os.path.dirname(__file__); D = f"{SCR}/rdata/pnl"
FAMCLASS = {"Time-series momentum": "trend-following (own asset)", "Breakout continuation": "trend-following (own asset)", "Moving-average regime allocation": "trend-following (own asset)",
  "Donchian channel trend": "trend-following (own asset)", "Volatility compression breakout": "trend-following (own asset)", "Cross-sectional momentum": "cross-sectional momentum",
  "Dual momentum": "cross-sectional momentum", "Trend pullback entry": "pullback within trend", "Trend exhaustion reversal": "short-term reversal", "Opening-range expansion": "intraday opening-range breakout",
  "Pairs distance trading": "pairs relative value", "Cointegration spread trading": "pairs relative value", "Basket statistical arbitrage": "factor-residual statistical arbitrage",
  "Commodity inter-commodity spread": "inter-commodity spread", "Commodity crack spread": "refining-margin (crack) spread", "Location basis convergence": "location basis", "Currency carry": "FX carry",
  "FX value reversion": "FX value", "FX fixing-window flow": "FX fix flow", "Interest-rate term premium": "duration timing", "Yield-curve slope trades": "curve slope", "Butterfly curve trades": "curve butterfly",
  "Swap spread relative value": "swap spread", "Credit spread mean reversion": "credit spread", "Index rebalance flow": "calendar flow", "Options implied-realized volatility": "short variance premium",
  "Variance risk premium": "short variance premium", "Volatility event premium": "short variance premium", "Gamma scalping": "long gamma / conditional variance", "Volatility term structure": "vol term structure",
  "Volatility skew relative value": "skew signal", "Correlation trading": "realised-correlation signal", "Crypto funding carry": "crypto funding carry", "Crypto spot-perpetual basis": "crypto cash-and-carry",
  "Crypto dated-futures basis": "crypto cash-and-carry", "Crypto liquidation cascade": "crypto liquidation/positioning", "Crypto open-interest divergence": "crypto liquidation/positioning",
  "Crypto liquidation funding interaction": "crypto liquidation/positioning", "Crypto basis regime switch": "crypto basis regime", "Stablecoin supply impulse": "stablecoin liquidity", "Miner inventory behavior": "miner behaviour",
  "Crypto volatility risk premium": "crypto short variance", "Order-book imbalance": "order-book imbalance", "Order-flow toxicity": "order-flow toxicity", "Trade-sign autocorrelation": "trade-sign persistence",
  "Inventory-aware market making": "market making", "Spread capture with toxicity filter": "market making", "Limit-order placement optimization": "execution policy", "Order-book resiliency": "book resiliency",
  "Large-trade impact decay": "large-trade impact", "VWAP execution alpha": "execution policy"}
# formulations that are genuinely different hypotheses inside a family (own class), from the rules actually implemented
OWN = {"STRAT-0002": "cross-sectional momentum", "STRAT-0012": "cross-sectional momentum", "STRAT-0032": "52-week-high (anchoring) ranking", "STRAT-0092": "52-week-high (anchoring) ranking",
  "STRAT-0072": "short-term reversal", "STRAT-0062": "pullback within trend", "STRAT-0082": "cross-sectional momentum", "STRAT-0052": "cross-sectional low-vol trend ranking",
  "STRAT-0004": "lead-lag (leader trend)", "STRAT-0014": "lead-lag (leader trend)", "STRAT-0034": "lead-lag (leader trend)", "STRAT-0094": "lead-lag (leader trend)", "STRAT-0084": "lead-lag (leader trend)",
  "STRAT-0104": "pair 1-day divergence reversal", "STRAT-0114": "error-correction single-leg", "STRAT-0118": "Kalman dynamic-hedge pairs", "STRAT-0122": "factor-residual statistical arbitrage", "STRAT-0124": "beta catch-up (lead-lag)",
  "STRAT-0128": "short-term reversal", "STRAT-0201": "commodity seasonality", "STRAT-0231": "commodity seasonality", "STRAT-0204": "product-crude lead-lag", "STRAT-0234": "product-crude lead-lag",
  "STRAT-0208": "spread momentum", "STRAT-0238": "spread momentum", "STRAT-0198": "spread momentum", "STRAT-0194": "spread lead-lag",
  "STRAT-0254": "policy-rate momentum", "STRAT-0264": "inflation-differential momentum", "STRAT-0292": "carry per duration (curve RV)", "STRAT-0294": "flight-to-quality (equity drawdown -> bonds)",
  "STRAT-0296": "curve-slope momentum", "STRAT-0298": "curve slope", "STRAT-0299": "volatility-managed duration", "STRAT-0304": "policy-rate momentum", "STRAT-0306": "curve carry", "STRAT-0308": "slope vs level regression residual",
  "STRAT-0317": "PCA curve-model residual", "STRAT-0318": "PCA curve-model residual", "STRAT-0352": "quality spread (Baa-Aaa)", "STRAT-0354": "equity-to-credit lead-lag", "STRAT-0356": "credit carry by cycle phase",
  "STRAT-0358": "credit spread momentum", "STRAT-0359": "credit carry (VIX-gated)",
  "STRAT-0491": "quad-witching / quarterly rebalance week", "STRAT-0492": "quarter-end window dressing", "STRAT-0493": "turn-of-the-month", "STRAT-0494": "month-end pension rebalancing", "STRAT-0497": "month-end pension rebalancing (size)",
  "STRAT-0498": "Russell reconstitution", "STRAT-0500": "turn-of-the-month", "STRAT-0495": "turn-of-the-month", "STRAT-0496": "turn-of-the-month", "STRAT-0499": "turn-of-the-month",
  "STRAT-0558": "relative variance premium (S&P vs Nasdaq)", "STRAT-0568": "cross-asset vol spread (equity vs gold)", "STRAT-0571": "vol-term-structure equity timing", "STRAT-0574": "vol-term-structure equity timing",
  "STRAT-0573": "vol calendar spread", "STRAT-0575": "vol calendar spread", "STRAT-0579": "vol calendar spread", "STRAT-0578": "short variance premium (3-month)", "STRAT-0576": "short variance premium",
  "STRAT-0581": "skew-spike long variance", "STRAT-0583": "skew signal", "STRAT-0585": "skew signal", "STRAT-0590": "skew signal", "STRAT-0584": "short variance premium", "STRAT-0586": "short variance premium",
  "STRAT-0588": "short variance premium", "STRAT-0589": "short variance premium", "STRAT-0601": "post-panic rebound", "STRAT-0602": "short-term reversal", "STRAT-0604": "short variance premium",
  "STRAT-0608": "stock-bond correlation risk parity", "STRAT-0609": "realised-correlation signal", "STRAT-0613": "long gamma / conditional variance", "STRAT-0692": "event vs non-event variance",
  "STRAT-0698": "short variance term spread", "STRAT-0712": "crypto funding carry", "STRAT-0713": "crypto funding time-series fade", "STRAT-0714": "crypto funding time-series fade", "STRAT-0716": "perp vs quarterly term carry",
  "STRAT-0718": "crypto funding carry", "STRAT-0738": "crypto basis speculation", "STRAT-0782": "crypto OI cross-sectional", "STRAT-0788": "top-trader vs crowd positioning",
  "STRAT-0793": "HMM funding regime", "STRAT-0796": "crypto basis regime", "STRAT-0822": "stablecoin liquidity rotation", "STRAT-0828": "stablecoin liquidity rotation", "STRAT-0842": "miner stress rotation",
  "STRAT-1011": "short variance premium", "STRAT-1032": "Macro regime: financial-conditions index", "STRAT-1033": "Macro regime: financial-conditions index",
  "STRAT-1030": "volatility-managed exposure", "STRAT-0299": "volatility-managed exposure",
  "STRAT-0928": "trade-sign contrarian", "STRAT-0983": "large-trade continuation", "STRAT-0984": "absorbed large trade"}
recs = {}
for l in open(f"{H}/results/results.jsonl"):
    r = json.loads(l)
    if r.get("universe") != "BLOCKED": recs[(r["id"], r["universe"])] = r
W = {}
for (sid, u) in recs:
    f = f"{D}/{sid}@{u}.pkl"
    if os.path.exists(f):
        s = pickle.load(open(f, "rb")); s.index = pd.to_datetime(s.index); s.index = s.index.tz_localize(None) if s.index.tz is not None else s.index; W[(sid, u)] = s.resample("W").sum()
def cls(sid, name):
    fam = name.split(" — ")[0]; return OWN.get(sid, FAMCLASS.get(fam, fam))
def layer(sid, name):
    form = name.split(" — ")[-1]
    return "core rule" if sid in OWN or form in ("time-series",) else "filter/timing/execution layer" if form in ("event-triggered", "regime-conditioned", "term-structure", "volatility-based", "execution-aware", "flow-based") else "core rule (different construction)"
rows = []; byid = {}
for (sid, u), r in sorted(recs.items()): byid.setdefault(sid, []).append((u, r))
for sid, lst in byid.items():
    name = lst[0][1]["name"]; c = cls(sid, name); ly = layer(sid, name)
    best_same, best_other = (0, None), (0, None)
    for u, r in lst:
        a = W.get((sid, u))
        if a is None: continue
        for (sid2, u2), b in W.items():
            if u2 != u or sid2 >= sid: continue
            j = pd.concat([a, b], axis=1, join="inner").dropna(); j = j[(j != 0).any(axis=1)]
            if len(j) < 52: continue
            cc = float(j.corr().iloc[0, 1]); c2 = cls(sid2, recs[(sid2, u2)]["name"])
            if c2 == c and abs(cc) > abs(best_same[0]): best_same = (round(cc, 2), sid2)
            if c2 != c and abs(cc) > abs(best_other[0]): best_other = (round(cc, 2), sid2)
    earlier_same = [s for s in byid if s < sid and cls(s, byid[s][0][1]["name"]) == c]
    twin = max([best_same, best_other], key=lambda x: abs(x[0]))
    if abs(twin[0]) >= 0.9: cat = f"DUPLICATE of {twin[1]} (near-identical returns, weekly corr {twin[0]}, whatever the label)"
    elif abs(best_same[0]) >= 0.7: cat = f"DUPLICATE of {best_same[1]} (same mechanism class, weekly corr {best_same[0]})"
    elif earlier_same: cat = f"VARIANT of the '{c}' mechanism (first tested as {earlier_same[0]}; statistically different, max same-class corr {best_same[0]} with {best_same[1]}) - not counted as a new mechanism"
    elif abs(best_other[0]) >= 0.7: cat = f"CORRELATED-DISTINCT: new mechanism, but returns overlap with {best_other[1]} (corr {best_other[0]}, different class)"
    else: cat = "DISTINCT mechanism (first of its class)"
    rows.append(dict(id=sid, name=name, mechanism_class=c, layer=ly, review=cat, max_same_class_corr=best_same[0], with_same=best_same[1], max_other_class_corr=best_other[0], with_other=best_other[1]))
R = pd.DataFrame(rows); R.to_csv(f"{H}/results/duplicate_review.csv", index=False)
old = json.load(open(f"{H}/results/uniqueness.json"))
old_dup = {k.split("@")[0] for k, v in old.items() if abs(v[0]) >= 0.7}
print("tested entries:", len(R), "| distinct mechanism classes tested:", R.mechanism_class.nunique())
print(R.review.str.split(" ").str[0].value_counts().to_dict())
print("old correlation-only 'variation' flags:", len(old_dup), "| of those now: ", R[R.id.isin(old_dup)].review.str.split(" ").str[0].value_counts().to_dict())
print("CORRELATED-DISTINCT examples:"); print(R[R.review.str.startswith("CORRELATED")][["id", "name", "review"]].head(12).to_string(index=False))
