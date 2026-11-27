# Meta-strategies on the 21-EA pack (daily P&L file, 3x preset risks): decide HOW MUCH each EA trades from its own past results.
# All weights use data strictly before the day (shifted by 1), rebalanced daily (filters) or monthly (rankings).
# Score: Sharpe before 2023 / from 2023 (holdout), yearly %, worst day, max drawdown, High Stakes pass sim (8% then 5%, 5% daily, 10% static) from weekly starts.
import numpy as np, pandas as pd
P = pd.read_csv("/home/user/dbxfcvnbgfcn/research/results/cook10/export/pack21_daily_pnl.csv", parse_dates=["server_date"], index_col="server_date")
WI = P.pop("BOOK_worst_intraday"); P.pop("BOOK_total"); E = list(P.columns); N = len(E)
def book(W):                                    # W: weights (same shape as P), applied to day t
    W = W.reindex(P.index).fillna(1.0); d = (P * W).sum(axis=1)
    gross0 = P.abs().sum(axis=1).replace(0, np.nan); gross = (P * W).abs().sum(axis=1)
    wi = (WI * (gross / gross0).fillna(1.0)).clip(upper=0); wi = np.minimum(wi, d.clip(upper=0)); return d, wi
def phase(d, wi, i, tgt, dl=5.0, ml=10.0):
    bal = 0.0
    for j in range(i, len(d)):
        if wi[j] + bal <= -ml + 1e-9 or wi[j] <= -dl: return "fail", j
        bal += d[j]
        if bal <= -ml: return "fail", j
        if bal >= tgt: return "pass", j
    return "open", len(d) - 1
def challenge(d, wi, i):
    t0 = i; tries = 0
    while tries < 10:
        tries += 1; a, j = phase(d, wi, t0, 8.0)
        if a == "open": return np.nan, tries
        if a == "fail": t0 = j + 1; continue
        b, k = phase(d, wi, j + 1, 5.0)
        if b == "pass": return (k - i) * 7 / 5, tries          # trading days -> calendar days (approx)
        if b == "open": return np.nan, tries
        t0 = k + 1
    return np.nan, tries
STARTS = [P.index.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D")]
S23 = P.index < "2023-01-01"
def score(name, W):
    d, wi = book(W); dv, wv = d.to_numpy(), wi.to_numpy(); sh = lambda x: round(x.mean() / x.std() * np.sqrt(252), 2)
    eq = d.cumsum(); dd = (eq - eq.cummax()).min(); res = [challenge(dv, wv, i) for i in STARTS]; days = np.array([r[0] for r in res]); tr = np.array([r[1] for r in res])
    return dict(variant=name, sharpe_train=sh(d[S23]), sharpe_hold=sh(d[~S23]), yr_pct=round(d.mean() * 252, 1), worst_day=round(wv.min(), 2), max_dd=round(dd, 1),
                first_try=round(100 * np.mean((tr == 1) & np.isfinite(days))), median_days=np.nanmedian(days), within_30d=round(100 * np.mean(days <= 30)), within_60d=round(100 * np.mean(days <= 60)))
ONES = pd.DataFrame(1.0, P.index, E); rows = [score("base (pack as is, 3x)", ONES)]
# matched-risk check: rescale a variant so its full-period daily stdev equals the base (only to compare like with like; flagged)
base_sd = P.sum(axis=1).std()
def matched(name, W):
    d, _ = book(W); k = base_sd / d.std(); rows.append(score(name + f"  [risk-matched x{k:.2f}]", W * k))
started = (P != 0).cumsum() > 0
# 1 equity-curve filters (per EA)
for n in (20, 60, 120):
    tr = P.rolling(n, min_periods=n // 2).sum().shift(1)
    for off, lab in ((0.0, "off"), (0.5, "half")):
        W = ONES.where(~(tr < 0), off); rows.append(score(f"EC filter: EA {lab} when its last {n}d < 0", W))
# 2 cross-sectional EA momentum (monthly): top third x1.5, bottom third x0.5, by trailing n-day P&L per unit of preset risk (risk = its own trade size)
risk = P.abs().where(P != 0).rolling(250, min_periods=20).median().shift(1)
me = P.index.to_series().groupby(P.index.to_period("M")).transform("first") == P.index.to_series()
for n in (63, 126, 252):
    sc = (P.rolling(n, min_periods=n // 2).sum().shift(1) / risk)
    W = pd.DataFrame(np.nan, P.index, E)
    for t in P.index[me]:
        s = sc.loc[t].where(started.loc[t]).dropna()
        if len(s) < 9: W.loc[t] = 1.0; continue
        r = s.rank(pct=True); w = pd.Series(1.0, E); w[r[r > 2 / 3].index] = 1.5; w[r[r <= 1 / 3].index] = 0.5; W.loc[t] = w
    W = W.ffill().fillna(1.0); rows.append(score(f"EA momentum {n}d: top third x1.5, bottom x0.5", W))
    Wr = W.copy(); Wr[W == 1.5] = 0.5; Wr[W == 0.5] = 1.5; rows.append(score(f"EA REVERSAL {n}d: bottom third x1.5, top x0.5", Wr))
# 3 inverse-volatility (risk parity) per EA, 120d, normalised to mean weight 1 among started EAs
vol = P.rolling(120, min_periods=40).std().shift(1).replace(0, np.nan); iv = 1 / vol; iv = iv.div(iv.mean(axis=1), axis=0).clip(0.33, 3).fillna(1.0)
rows.append(score("inverse-vol 120d (risk parity)", iv)); matched("inverse-vol 120d (risk parity)", iv)
# 4 book-level controls
bk = P.sum(axis=1)
for n in (10, 20, 60):
    m = bk.rolling(n).sum().shift(1); w = pd.Series(np.where(m > 0, 1.25, 0.75), P.index); rows.append(score(f"book momentum {n}d: x1.25 after an up {n}d, x0.75 after down", pd.DataFrame({e: w for e in E})))
eq = bk.cumsum()
for lvl in (2.0, 4.0):
    dd = (eq - eq.cummax()).shift(1).fillna(0); w = pd.Series(np.where(dd < -lvl, 0.5, 1.0), P.index); rows.append(score(f"book drawdown throttle: x0.5 while >{lvl:.0f}% below peak", pd.DataFrame({e: w for e in E})))
y = bk.shift(1); w = pd.Series(np.where(y < 0, 0.75, 1.25), P.index); rows.append(score("after a losing day x0.75, after a winning day x1.25", pd.DataFrame({e: w for e in E})))
w = pd.Series(np.where(y < 0, 1.25, 0.75), P.index); rows.append(score("after a losing day x1.25, after a winning day x0.75", pd.DataFrame({e: w for e in E})))
# 5 correlation clusters: cap same-day exposure of EAs on the same market family
R = pd.DataFrame(rows); pd.set_option("display.width", 260); pd.set_option("display.max_colwidth", 70); print(R.to_string(index=False)); R.to_csv("meta.csv", index=False)
print("\nautocorrelation of the book's daily P&L:", round(bk.autocorr(1), 3), "| of 5-day sums:", round(bk.rolling(5).sum()[::5].autocorr(1), 3))
