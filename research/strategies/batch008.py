"""STRAT-0701..0800: crypto derivatives. Testable: funding carry (72), spot-perp basis (73), dated-futures basis (74), liquidation cascade proxy (78),
OI divergence (79), basis regime switch (80). Merged: variance term-structure roll (71) -> 0573/0578. Blocked: 75, 76, 77."""
import numpy as np, pandas as pd, warnings
from strategies.lib import *
import crypto2
from engine import P as EP
warnings.filterwarnings("ignore")
C2 = crypto2.load()
FORMS = ["event-triggered", "cross-sectional", "time-series", "lead-lag", "regime-conditioned", "term-structure", "flow-based", "relative-value", "volatility-based", "execution-aware"]
FU = C2["fund"].rename(columns=lambda c: c.replace("USDT", ""))
def fund(R, n=7): return FU.reindex(R.index).reindex(columns=R.columns).rolling(n, min_periods=1).mean() * 365      # annualised funding
def prem(R): return C2["prem"].reindex(R.index).reindex(columns=R.columns)
def qb(R):   # annualised quarterly basis vs spot (BTC, ETH)
    out = {}
    for s, q in C2["cm"].items():
        sp = EP["crypto"][s].reindex(q.index); out[s] = (q.c / sp - 1) * 365 / q.dte
    return pd.DataFrame(out).reindex(R.index)
def btc_vol_pct(R): v = R["BTC"].rolling(21).std() if "BTC" in R else R.mean(1).rolling(21).std(); return v.rolling(365, min_periods=120).rank(pct=True)
def met(R, col):
    return pd.DataFrame({s: C2["metrics"][s][col] for s in C2["metrics"] if s in R.columns}).reindex(R.index).reindex(columns=R.columns)
def oi(R): return met(R, "oi")
def g(m): return m.astype(float)
def xs(score, q=0.3):
    r = score.rank(axis=1, pct=True); s = (r >= 1 - q).astype(float) - (r <= q).astype(float); s = s.where(score.notna(), 0)
    return s.loc[s.index.dayofweek == 0].reindex(s.index).ffill().fillna(0)
def hyst(x, on, off):
    """1 while x stays above `off` after crossing above `on` (hysteresis)."""
    out = np.zeros(x.shape); a = x.values; st = np.zeros(a.shape[1])
    for t in range(len(a)):
        st = np.where(np.nan_to_num(a[t], nan=-9) > on, 1, np.where(np.nan_to_num(a[t], nan=-9) < off, 0, st)); out[t] = st
    return pd.DataFrame(out, index=x.index, columns=x.columns)
def S(sid, fam, form, d, U, fn, gr, sizing=True): return dict(id=sid, family=fam, form=form, desc=d, universes=U, fn=fn, grid=gr, sizing=sizing)
def specs():
    o = []; F = "Crypto funding carry"
    o += [S("STRAT-0711", F, "event-triggered", "after a funding spike (daily funding > k x its 30-day mean and > 30%/yr) short that perp for H days", ["perp"],
            lambda R, p: hold(-(g((FU.reindex(R.index)[R.columns] * 365 > 0.3) & (FU.reindex(R.index)[R.columns] > p["k"] * FU.reindex(R.index)[R.columns].rolling(30).mean().abs()))), p["H"]), {"k": [3], "H": [3, 7]}),
          S("STRAT-0712", F, "cross-sectional", "weekly: long the lowest-funding perps, short the highest (cross-sectional carry)", ["perp"], lambda R, p: xs(-fund(R, p["n"])), {"n": [3, 7, 30]}),
          S("STRAT-0713", F, "time-series", "each perp: short when annualised funding > th (collect it), long when < -th/2", ["perp"],
            lambda R, p: -g(fund(R, p["n"]) > p["th"]) + g(fund(R, p["n"]) < -p["th"] / 2), {"n": [3, 7], "th": [0.1, 0.3]}),
          S("STRAT-0714", F, "lead-lag", "BTC funding drives alts: short alts when BTC funding is high, long when negative", ["perp"],
            lambda R, p: pd.DataFrame({c: (-np.sign(fund(R, p["n"])["BTC"] - p["th"]) * (c != "BTC")) for c in R.columns}, index=R.index), {"n": [3, 7], "th": [0.1, 0.2]}),
          S("STRAT-0715", F, "regime-conditioned", "cross-sectional carry only when BTC vol is in its bottom / top half", ["perp"], lambda R, p: xs(-fund(R, 7)).mul(g((btc_vol_pct(R) < 0.5) if p["reg"] == "calm" else (btc_vol_pct(R) >= 0.5)), axis=0), {"reg": ["calm", "turbulent"]}),
          S("STRAT-0716", F, "term-structure", "BTC/ETH: short the perp when its funding exceeds the quarterly futures basis (perp richer than term), long when below", ["perp"],
            lambda R, p: pd.DataFrame({c: (-np.sign(fund(R, p["n"])[c] - qb(R)[c]) if c in ("BTC", "ETH") else 0.0) for c in R.columns}, index=R.index).fillna(0), {"n": [3, 7]}),
          S("STRAT-0717", F, "flow-based", "cross-sectional carry only where taker flow agrees (short high-funding coins only when takers are net sellers, taker L/S < 1)", ["perp"],
            lambda R, p: (lambda s, t: s.where(((s < 0) & (t < p["tl"])) | ((s > 0) & (t > 1)), 0))(xs(-fund(R, 7)), met(R, "taker_ls").rolling(3).mean()), {"tl": [1.0, 0.95]}),
          S("STRAT-0718", F, "relative-value", "pairs: long the lower-funding / short the higher-funding coin within ETH-BTC, SOL-ETH, BNB-BTC, XRP-BTC", ["perp"], lambda R, p: _pair_carry(R, p["n"]), {"n": [3, 7]}),
          S("STRAT-0719", F, "volatility-based", "carry per unit risk: rank funding divided by 30-day vol", ["perp"], lambda R, p: xs(-fund(R, 7) / (R.rolling(30).std() * np.sqrt(365))), {"x": [1]}),
          S("STRAT-0720", F, "execution-aware", "carry only when the funding gap between the chosen long and short legs exceeds 20%/yr (trade-cost buffer)", ["perp"],
            lambda R, p: (lambda f: xs(-f).mul(((f.max(1) - f.min(1)) > p["gap"]).astype(float), axis=0))(fund(R, 7)), {"gap": [0.2, 0.4]}, )]
    F = "Crypto spot-perpetual basis"
    o += [S("STRAT-0721", F, "event-triggered", "enter cash-and-carry for H days after the premium index jumps above 0.1%", ["cashcarry"], lambda R, p: hold(g(prem(R) > 0.001), p["H"]), {"H": [3, 7]}),
          S("STRAT-0722", F, "cross-sectional", "hold cash-and-carry on the k coins with the highest 7-day funding (weekly)", ["cashcarry"], lambda R, p: (lambda r: g(r >= 1 - p["q"]))(fund(R, 7).rank(axis=1, pct=True)).loc[lambda x: x.index.dayofweek == 0].reindex(R.index).ffill().fillna(0), {"q": [0.2, 0.4]}),
          S("STRAT-0723", F, "time-series", "hold long spot / short perp while annualised trailing funding > th", ["cashcarry"], lambda R, p: g(fund(R, p["n"]) > p["th"]), {"n": [3, 7], "th": [0.05, 0.15]}),
          S("STRAT-0724", F, "lead-lag", "alt cash-and-carry only when BTC funding is above th (BTC leveraged demand leads alt basis)", ["cashcarry"],
            lambda R, p: pd.DataFrame({c: g(fund(R, 7)["BTC"] > p["th"]) * (c != "BTC") for c in R.columns}, index=R.index), {"th": [0.05, 0.15]}),
          S("STRAT-0725", F, "regime-conditioned", "carry only when BTC is above / below its 200-day average", ["cashcarry"],
            lambda R, p: g(fund(R, 7) > 0.05).mul(g((lambda b: (b > b.rolling(200).mean()) if p["side"] == "up" else (b <= b.rolling(200).mean()))(EP["crypto"]["BTC"].reindex(R.index))), axis=0), {"side": ["up", "down"]}),
          S("STRAT-0726", F, "term-structure", "BTC/ETH: perp carry only when funding exceeds the quarterly basis (best venue for the carry)", ["cashcarry"],
            lambda R, p: pd.DataFrame({c: g(fund(R, 7)[c] > qb(R)[c]) if c in ("BTC", "ETH") else 0.0 for c in R.columns}, index=R.index), {"x": [1]}),
          S("STRAT-0727", F, "flow-based", "carry only while open interest is rising (fresh leveraged longs keep funding positive)", ["cashcarry"],
            lambda R, p: g((fund(R, 7) > 0.05) & (oi(R) > oi(R).shift(p["n"]))), {"n": [3, 7]}),
          S("STRAT-0728", F, "relative-value", "always hold carry on whichever of BTC/ETH has the higher funding", ["cashcarry"],
            lambda R, p: pd.DataFrame({c: (g(fund(R, 7)["BTC"] >= fund(R, 7)["ETH"]) if c == "BTC" else g(fund(R, 7)["ETH"] > fund(R, 7)["BTC"]) if c == "ETH" else 0.0) for c in R.columns}, index=R.index), {"x": [1]}),
          S("STRAT-0729", F, "volatility-based", "carry only when the coin's 30-day vol is below its 1-year median (basis blowouts happen in turmoil)", ["cashcarry"],
            lambda R, p: g(fund(R, 7) > 0.05).where(R.rolling(30).std() < R.rolling(30).std().rolling(365, min_periods=120).median(), 0), {"x": [1]}),
          S("STRAT-0730", F, "execution-aware", "carry with hysteresis: enter when funding > on, exit only below off (fewer round trips)", ["cashcarry"], lambda R, p: hyst(fund(R, 7), p["on"], 0.0), {"on": [0.1, 0.2]})]
    F = "Crypto dated-futures basis"
    o += [S("STRAT-0731", F, "event-triggered", "always roll into the new quarterly right after expiry and hold the cash-and-carry for H days", ["qbasis"],
            lambda R, p: pd.DataFrame({c: hold(pd.DataFrame({"x": g(C2["cm"][c].exp.reindex(R.index).ffill() != C2["cm"][c].exp.reindex(R.index).ffill().shift(1))}), p["H"])["x"] for c in R.columns}, index=R.index), {"H": [30, 60]}),
          S("STRAT-0732", F, "cross-sectional", "hold the quarterly carry on whichever of BTC/ETH has the higher annualised basis", ["qbasis"],
            lambda R, p: (lambda b: pd.DataFrame({"BTC": g(b.BTC >= b.ETH), "ETH": g(b.ETH > b.BTC)}, index=R.index))(qb(R)), {"x": [1]}),
          S("STRAT-0733", F, "time-series", "long spot / short nearest quarterly while annualised basis > th", ["qbasis"], lambda R, p: g(qb(R) > p["th"]), {"th": [0.05, 0.1, 0.15]}),
          S("STRAT-0734", F, "lead-lag", "rising perp funding leads the quarterly basis: enter carry when 7-day funding rose over the last week", ["qbasis"], lambda R, p: g(fund(R, 7) > fund(R, 7).shift(7)), {"x": [1]}),
          S("STRAT-0735", F, "regime-conditioned", "quarterly carry only in BTC calm / turbulent vol regime", ["qbasis"], lambda R, p: g(qb(R) > 0.05).mul(g((btc_vol_pct(EP["crypto"].reindex(R.index)) < 0.5) if p["reg"] == "calm" else (btc_vol_pct(EP["crypto"].reindex(R.index)) >= 0.5)), axis=0), {"reg": ["calm", "turbulent"]}),
          S("STRAT-0736", F, "term-structure", "quarterly carry only when its basis beats perp funding (term premium over spot carry)", ["qbasis"], lambda R, p: g(qb(R) > fund(R, 7).reindex(columns=R.columns)), {"x": [1]}),
          S("STRAT-0737", F, "flow-based", "quarterly carry only while perp open interest is rising", ["qbasis"], lambda R, p: g((qb(R) > 0.05) & (oi(R) > oi(R).shift(7))), {"x": [1]}),
          S("STRAT-0738", F, "relative-value", "speculate on the basis itself: when its 90-day z-score > k short the basis (long future/short spot), < -k long it", ["qbasis"],
            lambda R, p: (lambda b: -np.sign((b - b.rolling(90).mean()) / b.rolling(90).std()) * g(((b - b.rolling(90).mean()) / b.rolling(90).std()).abs() > p["k"]))(qb(R)).fillna(0), {"k": [1.0, 2.0]}),
          S("STRAT-0739", F, "volatility-based", "quarterly carry only when the coin's 30-day vol is below its median", ["qbasis"], lambda R, p: g(qb(R) > 0.05).where(EP["crypto"].reindex(R.index)[R.columns].pct_change().rolling(30).std() < EP["crypto"].reindex(R.index)[R.columns].pct_change().rolling(30).std().rolling(365, min_periods=120).median(), 0), {"x": [1]}),
          S("STRAT-0740", F, "execution-aware", "quarterly carry with hysteresis (enter > on, exit < 2%)", ["qbasis"], lambda R, p: hyst(qb(R), p["on"], 0.02), {"on": [0.08, 0.15]})]
    F = "Crypto liquidation cascade"
    def casc(R, oid=0.08, pd_=0.05):
        o_ = oi(R); dO = o_ / o_.shift(1) - 1; dP = R
        return g((dO < -oid) & (dP < -pd_)) - g((dO < -oid) & (dP > pd_))       # +1 after long liquidations (fade), -1 after short squeezes
    o += [S("STRAT-0771", F, "event-triggered", "liquidation cascade (OI -x% and price -5% in a day): buy for H days; short squeeze: sell", ["perp"], lambda R, p: hold(casc(R, p["x"]), p["H"]), {"x": [0.05, 0.08], "H": [3, 7]}),
          S("STRAT-0772", F, "cross-sectional", "rank coins by OI drop x price drop over 3 days; long the most liquidated, short the most squeezed", ["perp"],
            lambda R, p: xs(-(oi(R) / oi(R).shift(3) - 1).clip(upper=0).abs() * np.sign(R.rolling(3).sum()) ), {"x": [1]}),
          S("STRAT-0773", F, "time-series", "continuation instead of reversal: after a cascade trade WITH the move for H days", ["perp"], lambda R, p: -hold(casc(R, p["x"]), p["H"]), {"x": [0.05, 0.08], "H": [3]}),
          S("STRAT-0774", F, "lead-lag", "a BTC liquidation cascade leads alts: buy alts for H days after a BTC long-liquidation day", ["perp"],
            lambda R, p: pd.DataFrame({c: hold(casc(R, 0.05)[["BTC"]], p["H"])["BTC"] * (c != "BTC") for c in R.columns}, index=R.index), {"H": [3, 7]}),
          S("STRAT-0775", F, "regime-conditioned", "cascade fade only when BTC is above / below its 200-day average", ["perp"],
            lambda R, p: hold(casc(R, 0.05), 3).mul(g((lambda b: (b > b.rolling(200).mean()) if p["side"] == "up" else (b <= b.rolling(200).mean()))(EP["crypto"]["BTC"].reindex(R.index))), axis=0), {"side": ["up", "down"]}),
          S("STRAT-0776", F, "term-structure", "cascade fade only when the perp premium has flipped negative (forced sellers pushed perps below spot)", ["perp"], lambda R, p: hold(casc(R, 0.05).where(prem(R) < 0, 0), p["H"]), {"H": [3, 7]}),
          S("STRAT-0777", F, "flow-based", "cascade fade only when takers were heavy sellers that day (taker L/S < 0.9)", ["perp"], lambda R, p: hold(casc(R, 0.05).where(met(R, "taker_ls") < p["t"], 0), 3), {"t": [0.9, 0.95]}),
          S("STRAT-0778", F, "relative-value", "after a coin-specific cascade, long that coin vs short BTC for H days", ["perp"],
            lambda R, p: (lambda c: c.sub(pd.DataFrame({k: c.sum(1) if k == "BTC" else 0 for k in R.columns}, index=R.index), fill_value=0))(hold(casc(R, 0.05).drop(columns=["BTC"], errors="ignore").reindex(columns=R.columns).fillna(0), p["H"])), {"H": [3, 7]}),
          S("STRAT-0779", F, "volatility-based", "cascade fade only when the coin's vol is above its median (genuine panic)", ["perp"], lambda R, p: hold(casc(R, 0.05).where(R.rolling(30).std() > R.rolling(30).std().rolling(365, min_periods=120).median(), 0), 3), {"x": [1]}),
          S("STRAT-0780", F, "execution-aware", "cascade fade entered one day later (avoid catching the falling knife)", ["perp"], lambda R, p: hold(casc(R, 0.05), p["H"]).shift(1).fillna(0), {"H": [3, 7]})]
    F = "Crypto open-interest divergence"
    def div(R, n): return np.sign(R.rolling(n).sum()) * np.sign(oi(R) / oi(R).shift(n) - 1)     # +1 price & OI agree, -1 diverge
    o += [S("STRAT-0781", F, "event-triggered", "after a big OI build-up (+20% in 3 days) bet against the crowded side for H days", ["perp"], lambda R, p: hold(-np.sign(R.rolling(3).sum()) * g(oi(R) / oi(R).shift(3) - 1 > 0.2), p["H"]), {"H": [3, 7]}),
          S("STRAT-0782", F, "cross-sectional", "rank coins by OI growth; long the coins where OI is shrinking, short where it is ballooning", ["perp"], lambda R, p: xs(-(oi(R) / oi(R).shift(p["n"]) - 1)), {"n": [7, 14]}),
          S("STRAT-0783", F, "time-series", "price and OI rising together: follow; price up with OI down (short covering) or price down with OI down (liquidation): fade", ["perp"],
            lambda R, p: np.sign(R.rolling(p["n"]).sum()) * div(R, p["n"]), {"n": [3, 7]}),
          S("STRAT-0784", F, "lead-lag", "BTC's price/OI agreement decides alt direction", ["perp"], lambda R, p: pd.DataFrame({c: (np.sign(R["BTC"].rolling(p["n"]).sum()) * div(R, p["n"])["BTC"]) * (c != "BTC") for c in R.columns}, index=R.index), {"n": [3, 7]}),
          S("STRAT-0785", F, "regime-conditioned", "OI-divergence rule only in BTC calm / turbulent regime", ["perp"], lambda R, p: (np.sign(R.rolling(3).sum()) * div(R, 3)).mul(g((btc_vol_pct(R) < 0.5) if p["reg"] == "calm" else (btc_vol_pct(R) >= 0.5)), axis=0), {"reg": ["calm", "turbulent"]}),
          S("STRAT-0786", F, "term-structure", "OI rising while the premium is negative (shorts piling in) -> long (squeeze setup)", ["perp"], lambda R, p: g((oi(R) / oi(R).shift(p["n"]) - 1 > 0.05) & (prem(R) < 0)), {"n": [3, 7]}),
          S("STRAT-0787", F, "flow-based", "OI rising and takers net buyers -> long; OI rising and takers net sellers -> short", ["perp"],
            lambda R, p: g(oi(R) > oi(R).shift(p["n"])) * np.sign(met(R, "taker_ls").rolling(p["n"]).mean() - 1), {"n": [3, 7]}),
          S("STRAT-0788", F, "relative-value", "top-trader positioning vs the crowd: follow top traders' long/short ratio relative to the account count ratio", ["perp"],
            lambda R, p: np.sign(met(R, "toptrader_ls").rolling(p["n"]).mean() - met(R, "count_ls").rolling(p["n"]).mean()), {"n": [3, 7]}),
          S("STRAT-0789", F, "volatility-based", "OI-divergence rule only when OI is large relative to recent volume... proxied by OI z-score > 1", ["perp"],
            lambda R, p: (np.sign(R.rolling(3).sum()) * div(R, 3)).where(((oi(R) - oi(R).rolling(90).mean()) / oi(R).rolling(90).std()) > p["z"], 0), {"z": [0.5, 1.0]}),
          S("STRAT-0790", F, "execution-aware", "OI-divergence rule decided weekly", ["perp"], lambda R, p: w_exec(np.sign(R.rolling(7).sum()) * div(R, 7)), {"x": [1]})]
    F = "Crypto basis regime switch"
    o += [S("STRAT-0791", F, "event-triggered", "when funding flips from positive to negative (regime break) go long for H days", ["perp"],
            lambda R, p: hold(g((fund(R, 3) < 0) & (fund(R, 3).shift(1) >= 0)), p["H"]), {"H": [7, 14]}),
          S("STRAT-0792", F, "cross-sectional", "rank coins by funding z-score vs their own 90 days; long the most depressed, short the most euphoric", ["perp"],
            lambda R, p: xs(-((fund(R, 7) - fund(R, 7).rolling(90).mean()) / fund(R, 7).rolling(90).std())), {"x": [1]}),
          S("STRAT-0793", F, "time-series", "two-state hidden Markov model on daily funding (fit on trailing 365 days, refit monthly): short in the high-funding state, long in the low state", ["perp"],
            lambda R, p: _hmm(R, p["side"]), {"side": ["ls", "long_low"]}, ),
          S("STRAT-0794", F, "lead-lag", "BTC funding regime (above/below its 90-day median) sets direction for alts", ["perp"],
            lambda R, p: pd.DataFrame({c: -np.sign(fund(R, 7)["BTC"] - fund(R, 7)["BTC"].rolling(90).median()) * (c != "BTC") for c in R.columns}, index=R.index), {"x": [1]}),
          S("STRAT-0795", F, "regime-conditioned", "funding z-score fade only in BTC calm / turbulent regime", ["perp"],
            lambda R, p: (-np.sign((fund(R, 7) - fund(R, 7).rolling(90).mean()) / fund(R, 7).rolling(90).std()) * g(((fund(R, 7) - fund(R, 7).rolling(90).mean()) / fund(R, 7).rolling(90).std()).abs() > 1)).mul(g((btc_vol_pct(R) < 0.5) if p["reg"] == "calm" else (btc_vol_pct(R) >= 0.5)), axis=0), {"reg": ["calm", "turbulent"]}),
          S("STRAT-0796", F, "term-structure", "BTC/ETH: long when the quarterly basis is below its 90-day mean (term structure cheap), short when above", ["perp"],
            lambda R, p: pd.DataFrame({c: (-np.sign(qb(R)[c] - qb(R)[c].rolling(90).mean())) if c in ("BTC", "ETH") else 0.0 for c in R.columns}, index=R.index).fillna(0), {"x": [1]}),
          S("STRAT-0797", F, "flow-based", "funding regime fade confirmed by OI: euphoric funding with OI at a 90-day high -> short", ["perp"],
            lambda R, p: -g((fund(R, 7) > fund(R, 7).rolling(90).quantile(0.8)) & (oi(R) >= oi(R).rolling(90).max() * 0.98)), {"x": [1]}),
          S("STRAT-0798", F, "relative-value", "premium-index regime: long when the perp trades below spot index for n days, short when above by > 0.05%", ["perp"],
            lambda R, p: g(prem(R).rolling(p["n"]).mean() < 0) - g(prem(R).rolling(p["n"]).mean() > 0.0005), {"n": [3, 7]}),
          S("STRAT-0799", F, "volatility-based", "funding z-score fade scaled down when the coin's vol is high", ["perp"],
            lambda R, p: (-((fund(R, 7) - fund(R, 7).rolling(90).mean()) / fund(R, 7).rolling(90).std()).clip(-2, 2) / 2), {"x": [1]}),
          S("STRAT-0800", F, "execution-aware", "funding z-score fade decided weekly", ["perp"], lambda R, p: w_exec(-np.sign((fund(R, 7) - fund(R, 7).rolling(90).mean()) / fund(R, 7).rolling(90).std())), {"x": [1]})]
    for sid in [f"STRAT-{i:04d}" for i in range(701, 711)]: o.append(dict(id=sid, family="Variance term-structure roll", form=FORMS[int(sid[-1]) - 1 if sid[-1] != "0" else 9], blocked="MERGED into STRAT-0573/0578: same synthetic VIX/VIX3M variance instruments and data; not counted separately"))
    for off, (fam, why) in {740: ("Cross-exchange crypto price dislocation", "synchronous prices from several exchanges (only Binance history reachable)"),
                            750: ("Cross-exchange funding differential", "funding history from several exchanges (Bybit blocked, OKX API only recent months)"),
                            760: ("CEX-DEX price discovery lead-lag", "DEX swap-level prices (on-chain)")}.items():
        for j, form in enumerate(FORMS): o.append(dict(id=f"STRAT-{off + j + 1:04d}", family=fam, form=form, blocked=why + " - not available in this environment"))
    o += [S("STRAT-0716", "x", "x", "", [], None, {})][:0]
    return sorted(o, key=lambda s: s["id"])
def _pair_carry(R, n):
    f = fund(R, n); w = pd.DataFrame(0.0, index=R.index, columns=R.columns)
    for a, b in [("ETH", "BTC"), ("SOL", "ETH"), ("BNB", "BTC"), ("XRP", "BTC")]:
        s = np.sign(f[b] - f[a]).fillna(0); w[a] += s; w[b] -= s
    return w / 4
def _hmm(R, side):
    from hmmlearn.hmm import GaussianHMM
    F = FU.reindex(R.index).reindex(columns=R.columns) * 365; out = pd.DataFrame(0.0, index=R.index, columns=R.columns)
    for c in R.columns:
        x = F[c]; idx = x.index
        for s in range(365, len(idx), 30):
            tr = x.iloc[s - 365:s].dropna()
            if len(tr) < 200: continue
            try:
                m = GaussianHMM(2, covariance_type="diag", n_iter=50, random_state=0).fit(tr.values.reshape(-1, 1))
                hi = int(np.argmax(m.means_.ravel())); seg = x.iloc[s - 365:s + 30].fillna(0).values.reshape(-1, 1)
                st = m.predict(seg)[365:]
                val = np.where(st == hi, -1.0 if side == "ls" else 0.0, 1.0)
                out.iloc[s:s + len(val), out.columns.get_loc(c)] = val
            except Exception: pass
    return out
