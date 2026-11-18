"""STRAT-1001..1031 - new mechanisms (no moving-average / momentum / Donchian variants): commodity supply-demand (EIA), scheduled macro events
(FOMC, claims), financial-conditions and news-uncertainty alternative data, Bayesian change-point, machine learning (gradient boosting, random forest,
logistic, k-NN analogues), reinforcement learning (tabular Q-learning, Thompson bandit), nonlinear (Hurst/DFA, ordinal patterns), market-neutral
factor sorts (BAB, IVOL, MAX, lead-lag network), cross-exchange crypto, on-chain/DeFi value, credit structural residual, rebalancing premium,
volatility-managed equity, Cochrane-Piazzesi forward-rate factor. Every signal uses only data published before the trade."""
import os, json, glob, numpy as np, pandas as pd, warnings
from strategies.lib import px, hold, sma
from engine import P, _rets
from data import _fred, RDATA, SCR
warnings.filterwarnings("ignore")
def g(m): return m.astype(float)
def eia(k):
    x = pd.read_csv(f"{RDATA}/eia/{k}.csv", parse_dates=["date"]).set_index("date")[k]; return x
def avail(s, days): s = s.copy(); s.index = s.index + pd.Timedelta(days=days); return s                     # publication lag
def to_daily(s, idx): return s.reindex(idx.union(s.index)).ffill().reindex(idx)
def seas_surprise(x):
    """weekly change minus the average change in the same week over the previous 5 years, scaled by a 3-year rolling sd."""
    d = x.diff(); exp = sum(d.shift(52 * k) for k in range(1, 6)) / 5; s = d - exp; return s / s.rolling(156, min_periods=60).std()
def seas_level(x): base = sum(x.shift(52 * k) for k in range(1, 6)) / 5; return x / base - 1
def one_col(R, col, s):
    w = pd.DataFrame(0.0, index=R.index, columns=R.columns); w[col] = s.reindex(R.index).fillna(0); return w
def spread(R, legs, s):
    w = pd.DataFrame(0.0, index=R.index, columns=R.columns)
    for c, k in legs.items(): w[c] += k * s.reindex(R.index).fillna(0)
    return w
def fomc_days(idx):
    d = pd.to_datetime(pd.read_csv(f"{RDATA}/fomc/fomc_dates_raw.csv").iloc[:, 0]); d = d[d.dt.dayofweek < 5]; return pd.Series(idx.normalize().isin(d), index=idx)
def S(sid, fam, d, U, fn, gr, sizing=True, start=None): return dict(id=sid, family=fam, form=fam, desc=d, universes=U, fn=fn, grid=gr, sizing=sizing, start=start)
# ---------------- machine learning helpers ----------------
def feats(R):
    p = px(R); f = {"r1": R, "r5": R.rolling(5).sum(), "r21": R.rolling(21).sum(), "v21": R.rolling(21).std(), "z63": (p - p.rolling(63).mean()) / p.rolling(63).std()}
    return f
def gbm_signal(R, p):
    from sklearn.ensemble import HistGradientBoostingClassifier
    F = feats(R); y = np.sign(R.shift(-1).rolling(5).sum().shift(-4)); out = pd.DataFrame(0.0, index=R.index, columns=R.columns)
    rvp = P["macro"]["NASDAQCOM"].pct_change().rolling(21).std().mul(np.sqrt(252) * 100).reindex(R.index).ffill()
    vix = P["macro"]["VIXCLS"].reindex(R.index).ffill().combine_first(rvp)          # pre-1990: realised-vol proxy
    sl = P["macro"]["T10Y3M"].reindex(R.index).ffill().combine_first((P["yields"]["DGS10"] - P["yields"]["DFF"]).reindex(R.index).ffill())
    years = sorted(set(R.index.year)); first = years[0] + 10
    def stack(ix):
        cols = []
        for k, v in F.items(): cols.append(v.loc[ix].stack(future_stack=True).rename(k))
        X = pd.concat(cols, axis=1); X["vix"] = X.index.get_level_values(0).map(vix.reindex(ix).to_dict()); X["slope"] = X.index.get_level_values(0).map(sl.reindex(ix).to_dict())
        return X
    for yr in range(first, years[-1] + 1):
        tr = R.index[(R.index.year < yr) & (R.index.year >= yr - p["win"])]; te = R.index[R.index.year == yr]
        if len(te) == 0: continue
        Xtr = stack(tr[:-6]); ytr = y.loc[tr[:-6]].stack(future_stack=True).reindex(Xtr.index); ok = ytr.notna() & (ytr != 0) & Xtr[["r1", "r5", "r21", "v21", "z63"]].notna().all(1)
        if ok.sum() < 2000: continue
        m = HistGradientBoostingClassifier(max_iter=150, max_depth=3, learning_rate=0.05, random_state=0).fit(Xtr[ok].values, (ytr[ok] > 0).values)
        Xte = stack(te); okte = Xte[["r1", "r5", "r21", "v21", "z63"]].notna().all(1)
        pr = pd.Series(np.nan, index=Xte.index); pr[okte] = m.predict_proba(Xte[okte].values)[:, 1]
        sig = (2 * pr - 1).unstack(); out.loc[sig.index, sig.columns] = np.clip(sig.values * p["k"], -1, 1)
    return out.fillna(0)
def rf_xs(R, p):
    from sklearn.ensemble import RandomForestRegressor
    me = R.index[R.index.to_series().dt.month != R.index.to_series().shift(-1).dt.month]; pm = px(R).loc[me]
    F = {"m1": pm.pct_change(1), "m3": pm.pct_change(3), "m12": pm.pct_change(12), "vol": R.rolling(63).std().loc[me], "ivol": (R.sub(R.mean(1), axis=0)).rolling(63).std().loc[me]}
    fwd = pm.pct_change().shift(-1); rk = fwd.rank(axis=1, pct=True); out = pd.DataFrame(0.0, index=me, columns=R.columns)
    for y0 in range(1975, me[-1].year + 1, 5):
        tr = me[(me.year < y0) & (me.year >= 1940)][:-1]; te = me[(me.year >= y0) & (me.year < y0 + 5)]
        X = pd.concat([v.loc[tr].stack(future_stack=True).rename(k) for k, v in F.items()], axis=1); yy = rk.loc[tr].stack(future_stack=True).reindex(X.index); ok = X.notna().all(1) & yy.notna()
        m = RandomForestRegressor(n_estimators=100, max_depth=5, min_samples_leaf=50, random_state=0, n_jobs=4).fit(X[ok].values, yy[ok].values)
        Xt = pd.concat([v.loc[te].stack(future_stack=True).rename(k) for k, v in F.items()], axis=1); okt = Xt.notna().all(1)
        pr = pd.Series(np.nan, index=Xt.index); pr[okt] = m.predict(Xt[okt].values); P_ = pr.unstack().rank(axis=1, pct=True)
        out.loc[P_.index, P_.columns] = (g(P_ >= 1 - p["q"]) - g(P_ <= p["q"])).values
    return out.reindex(R.index).ffill().fillna(0)
def logit_crypto(R, p):
    from sklearn.linear_model import LogisticRegression
    import crypto2; C2 = crypto2.load(); fu = C2["fund"].rename(columns=lambda c: c.replace("USDT", "")).reindex(R.index)
    coins = [c for c in C2["metrics"] if c in R.columns]; out = pd.DataFrame(0.0, index=R.index, columns=R.columns)
    def X_(c):
        m = C2["metrics"][c].reindex(R.index)
        return pd.DataFrame({"f7": fu[c].rolling(7).mean(), "prem": C2["prem"][c].reindex(R.index), "doi": m.oi / m.oi.shift(7) - 1, "taker": m.taker_ls.rolling(3).mean(), "r7": R[c].rolling(7).sum()})
    Xs = {c: X_(c).replace([np.inf, -np.inf], np.nan) for c in coins}; ys = {c: np.sign(R[c].shift(-1).rolling(3).sum().shift(-2)) for c in coins}
    for yr in range(2023, R.index[-1].year + 1):
        tr = R.index[R.index.year < yr][:-4]; te = R.index[R.index.year == yr]
        Xa = pd.concat([Xs[c].loc[tr] for c in coins]); ya = pd.concat([ys[c].loc[tr] for c in coins]); ok = Xa.notna().all(1) & ya.notna() & (ya != 0)
        if ok.sum() < 300: continue
        mu, sd = Xa[ok].mean(), Xa[ok].std(); m = LogisticRegression(C=0.5).fit(((Xa[ok] - mu) / sd).values, (ya[ok] > 0).values)
        for c in coins:
            xt = Xs[c].loc[te]; okt = xt.notna().all(1); pr = pd.Series(0.5, index=te); pr[okt] = m.predict_proba(((xt[okt] - mu) / sd).values)[:, 1]
            out.loc[te, c] = np.where(abs(pr - 0.5) > p["th"], np.sign(pr - 0.5), 0)
    return out
def knn_mkt(R, p):
    from sklearn.neighbors import NearestNeighbors
    r = R["MKT"]; v = r.rolling(63).std(); Z = pd.concat([(r.shift(k) / v) for k in range(10)], axis=1).dropna(); nxt = r.shift(-1).reindex(Z.index)
    out = pd.Series(0.0, index=R.index)
    for yr in range(1940, R.index[-1].year + 1):
        tr = Z.index[Z.index.year < yr][:-1]; te = Z.index[Z.index.year == yr]
        if len(tr) < 2000 or len(te) == 0: continue
        nn = NearestNeighbors(n_neighbors=p["k"]).fit(Z.loc[tr].values); _, ix = nn.kneighbors(Z.loc[te].values)
        pred = nxt.loc[tr].values[ix].mean(1); out.loc[te] = np.sign(pred)
    return pd.DataFrame({"MKT": out})
def qlearn(R, p):
    """weekly tabular Q-learning: state = (vol tercile, curve sign, NFCI sign); actions {cash, MKT, UST10Y}; trained on past weeks only, refit yearly."""
    wk = R.resample("W-FRI").sum(); idx = wk.index
    vol = R["MKT"].rolling(63).std().resample("W-FRI").last(); vt = vol.rolling(520, min_periods=104).rank(pct=True)
    sl = P["macro"]["T10Y3M"].resample("W-FRI").last().reindex(idx).ffill(); nf = avail(P["macro"]["NFCI"], 5).resample("W-FRI").last().reindex(idx).ffill()
    st = (np.minimum((vt.fillna(0.5) * 3).astype(int), 2) * 4 + (sl.fillna(1) > 0).astype(int) * 2 + (nf.fillna(0) > 0).astype(int)).values
    rew = np.c_[np.zeros(len(idx)), wk["MKT"].shift(-1).values, wk["UST10Y"].shift(-1).values]; act = np.zeros(len(idx), int)
    for yr in sorted(set(idx.year))[10:]:
        tr = np.where((idx.year < yr))[0][:-1]; Q = np.zeros((12, 3)); n = np.zeros((12, 3))
        for _ in range(3):
            for t in tr[:-1]:
                for a in range(3):
                    target = rew[t, a] + p["gamma"] * Q[st[t + 1]].max(); n[st[t], a] += 1; Q[st[t], a] += (target - Q[st[t], a]) / n[st[t], a]
        te = np.where(idx.year == yr)[0]; act[te] = Q[st[te]].argmax(1)
    w = pd.DataFrame({"MKT": (act == 1).astype(float), "UST10Y": (act == 2).astype(float)}, index=idx)
    return w.reindex(R.index, method="ffill").shift(1).fillna(0)
def dfa_hurst(x):
    y = np.cumsum(x - x.mean()); F = []; ns = [8, 16, 32]
    for n in ns:
        m = len(y) // n; segs = y[:m * n].reshape(m, n); t = np.arange(n)
        res = [np.sqrt(np.mean((s - np.polyval(np.polyfit(t, s, 1), t)) ** 2)) for s in segs]; F.append(np.mean(res))
    return np.polyfit(np.log(ns), np.log(F), 1)[0]
def hurst_switch(R, p):
    H = pd.DataFrame(np.nan, index=R.index, columns=R.columns); V = R.values
    for j in range(R.shape[1]):
        for i in range(128, len(R), 5):
            x = V[i - 128:i, j]
            if not np.isnan(x).any() and x.std() > 0: H.iloc[i, j] = dfa_hurst(x)
    H = H.ffill(limit=5)
    return g(H > p["hi"]) * np.sign(R.rolling(20).sum()) - g(H < 1 - p["hi"]) * np.sign(R.rolling(5).sum())
def ordinal(R, p):
    import itertools
    perms = {k: i for i, k in enumerate(itertools.permutations(range(4)))}
    def pat(a): return np.array([perms.get(tuple(np.argsort(a[i - 4:i])), -1) if not np.isnan(a[i - 4:i]).any() else -1 for i in range(len(a) + 1)])[1:]
    out = pd.DataFrame(0.0, index=R.index, columns=R.columns)
    for c in R.columns:
        a = R[c].values; pt = np.r_[[-1] * 3, pat(a)[3:]][:len(a)] if len(a) > 4 else np.full(len(a), -1)
        pt = np.array([perms.get(tuple(np.argsort(a[i - 3:i + 1])), -1) if i >= 3 and not np.isnan(a[i - 3:i + 1]).any() else -1 for i in range(len(a))])
        nxt = np.r_[a[1:], np.nan]; s = pd.Series(pt, index=R.index)
        cnt = pd.Series(1, index=R.index).groupby(pt).transform("size")
        # permutation entropy over 60 days
        def ent(w):
            v = w[w >= 0]
            if len(v) < 30: return np.nan
            q = np.bincount(v.astype(int), minlength=24) / len(v); q = q[q > 0]; return -(q * np.log(q)).sum() / np.log(24)
        E = s.rolling(60).apply(ent, raw=True)
        for yr in sorted(set(R.index.year))[5:]:
            tr = (R.index.year < yr); te = (R.index.year == yr)
            df = pd.DataFrame({"p": pt[tr][:-1], "n": nxt[tr][:-1]}).dropna(); df = df[df.p >= 0]
            st = df.groupby("p").n.agg(["mean", "std", "count"]); tt = st["mean"] / (st["std"] / np.sqrt(st["count"]))
            rule = np.sign(st["mean"]).where(tt.abs() > p["t"], 0)
            emed = E[tr].median()
            out.loc[te, c] = pd.Series(pt[te]).map(rule).fillna(0).values * (E[te] < emed).values
    return out
def mkt_beta(R, n=252):
    m = P["ff3"]["Mkt-RF"].reindex(R.index); return R.rolling(n).cov(m) .div(m.rolling(n).var(), axis=0)
def xs_sort(score, q=0.2, monthly=True):
    r = score.rank(axis=1, pct=True); s = g(r >= 1 - q) - g(r <= q); s = s.where(score.notna(), 0)
    if monthly: s = s.loc[s.index.to_series().dt.month != s.index.to_series().shift(-1).dt.month].reindex(s.index).ffill()
    return s.fillna(0)
def bab(R, p):
    b = mkt_beta(R).shift(1); s = xs_sort(-b, p["q"]); bl = (b * g(s > 0)).sum(1) / g(s > 0).sum(1).replace(0, np.nan); bh = (b * g(s < 0)).sum(1) / g(s < 0).sum(1).replace(0, np.nan)
    return s.where(s <= 0, s.mul(1 / bl, axis=0)).where(s >= 0, s.mul(1 / bh, axis=0)).clip(-3, 3).fillna(0)
def ivol(R, p):
    m = P["ff3"]["Mkt-RF"].reindex(R.index); b = mkt_beta(R, 63); res = R - b.mul(m, axis=0); return xs_sort(-res.rolling(63).std(), p["q"])
def maxeff(R, p): return xs_sort(-R.rolling(21).max(), p["q"])
def leadlag_net(R, p):
    W = R.resample("W-FRI").sum(); out = pd.DataFrame(0.0, index=W.index, columns=W.columns)
    for y0 in range(1960, W.index[-1].year + 1):
        tr = W[(W.index.year < y0) & (W.index.year >= y0 - 15)]; te = W.index[W.index.year == y0]
        if len(tr) < 300 or len(te) == 0: continue
        L = tr.shift(1); C = pd.DataFrame({j: L.corrwith(tr[j]) for j in tr.columns})       # C[i, j]: corr(i lagged, j)
        pred = pd.DataFrame({j: W.shift(1).loc[te, C[j].drop(j).nlargest(3).index].mean(1) for j in tr.columns})
        rk = pred.rank(axis=1, pct=True); out.loc[te] = (g(rk >= 1 - p["q"]) - g(rk <= p["q"])).values
    return out.reindex(R.index, method="ffill").shift(1).fillna(0)
def cb_premium(R):
    out = {}
    for c in ("BTC", "ETH"):
        rows = json.load(open(f"{SCR}/indep/cb/{c}.json")); cb = pd.Series({pd.Timestamp(int(t), unit="s", tz="UTC"): float(cl) for t, lo, hi, op, cl, v in rows}).sort_index()
        out[c] = (cb / P["crypto"][c].reindex(cb.index) - 1)
    pr = pd.DataFrame(out).reindex(R.index); return (pr - pr.rolling(30).mean()) / pr.rolling(30).std()
TVLMAP = {"Ethereum": "ETH", "Solana": "SOL", "BSC": "BNB", "Avalanche": "AVAX", "Tron": "TRX", "Cardano": "ADA"}
def tvl_panel(idx):
    d = {}
    for ch, c in TVLMAP.items():
        x = json.load(open(f"{RDATA}/tvl/{ch}.json")); s = pd.Series({pd.Timestamp(int(r["date"]), unit="s", tz="UTC"): r["tvl"] for r in x}).sort_index(); d[c] = s.replace(0, np.nan)
    return pd.DataFrame(d).reindex(idx).ffill().shift(1)
def tvl_value(R, p):
    T = tvl_panel(R.index); pxx = P["crypto"].reindex(R.index)[T.columns]
    sc = np.log(T / T.shift(p["n"])) - np.log(pxx / pxx.shift(p["n"])); r = sc.rank(axis=1, pct=True)
    s = (g(r >= 0.67) - g(r <= 0.34)).where(sc.notna(), 0); s = s.loc[s.index.dayofweek == 0].reindex(s.index).ffill().fillna(0)
    return s.reindex(columns=R.columns).fillna(0)
def nvt(R, p):
    import crypto2; mi = crypto2.load()["miners"]["n-transactions"]; mi.index = mi.index.normalize()
    tx = mi.reindex(R.index).ffill().rolling(90).mean().shift(1); v = np.log(P["crypto"]["BTC"].reindex(R.index)) - np.log(tx)
    z = (v - v.rolling(365).mean()) / v.rolling(365).std(); return pd.DataFrame({"BTC": g(z < -p["z"]) - g(z > p["z"]) * p["short"]}, index=R.index)
def merton_resid(R, p):
    s = (_fred("DBAA") - _fred("DGS20").combine_first((_fred("DGS10") + _fred("DGS30")) / 2)).reindex(R.index).ffill()
    vix = P["macro"]["VIXCLS"].reindex(R.index).ffill(); nq = P["macro"]["NASDAQCOM"].reindex(R.index).ffill(); dd = nq / nq.rolling(252).max() - 1
    N = p["N"]; res = pd.Series(np.nan, index=R.index)
    for i in range(N, len(R), 21):
        X = np.c_[np.ones(N), vix.iloc[i - N:i].values, dd.iloc[i - N:i].values]; y = s.iloc[i - N:i].values; ok = ~np.isnan(X).any(1) & ~np.isnan(y)
        if ok.sum() < N // 2: continue
        b = np.linalg.lstsq(X[ok], y[ok], rcond=None)[0]; seg = slice(i, min(i + 21, len(R)))
        res.iloc[seg] = s.iloc[seg].values - (np.c_[np.ones(len(R.index[seg])), vix.iloc[seg].values, dd.iloc[seg].values] @ b)
    z = (res - res.rolling(252, min_periods=120).mean()) / res.rolling(252, min_periods=120).std()
    w = pd.DataFrame(0.0, index=R.index, columns=R.columns); sig = (g(z > 1) - g(z < -1)).fillna(0); w["BAA"] = sig; w["T20"] = -sig; return w
def volmanaged(R, p):
    rv = R["MKT"].rolling(p["n"]).var().shift(0); c = (R["MKT"].var()); w = (rv.rolling(2520, min_periods=500).mean() / rv).clip(upper=p["cap"])
    return pd.DataFrame({"MKT": w.fillna(0)}, index=R.index)
def cochrane_piazzesi(R, p):
    Y = pd.DataFrame({n: _fred(f"DGS{n}") for n in (1, 2, 3, 5)}).reindex(R.index).ffill() / 100
    f = pd.DataFrame({1: Y[1], 2: 2 * Y[2] - Y[1], 3: 3 * Y[3] - 2 * Y[2], 5: (5 * Y[5] - 3 * Y[3]) / 2})          # approximate forward rates
    me = R.index[R.index.to_series().dt.month != R.index.to_series().shift(-1).dt.month]
    xr = R[["UST2Y", "UST5Y"]].mean(1); fut = xr[::-1].rolling(252).sum()[::-1].shift(-1)                       # next-12-month excess return
    pred = pd.Series(np.nan, index=me)
    for t in me:
        tr = me[(me <= t - pd.Timedelta(days=370)) & (me >= t - pd.Timedelta(days=365 * p["yrs"]))]
        if len(tr) < 60: continue
        X = np.c_[np.ones(len(tr)), f.loc[tr].values]; y = fut.loc[tr].values; ok = ~np.isnan(X).any(1) & ~np.isnan(y)
        if ok.sum() < 60: continue
        b = np.linalg.lstsq(X[ok], y[ok], rcond=None)[0]; x = np.r_[1, f.loc[t].values]
        if not np.isnan(x).any(): pred[t] = x @ b
    s = np.sign(pred).reindex(R.index).ffill().fillna(0); w = pd.DataFrame(0.0, index=R.index, columns=R.columns); w["UST5Y"] = s; return w
def specs():
    o = []
    cr = lambda R: to_daily(avail(seas_surprise(eia("WCESTUS1")), 5), R.index)
    o += [S("STRAT-1001", "Commodity supply-demand: crude inventory surprise", "EIA weekly crude stocks change minus the 5-year same-week average change (z): larger-than-seasonal draw -> long WTI until the next report, build -> short (used from the Wednesday release)", ["energy"],
            lambda R, p: one_col(R, "WTI", -np.sign(cr(R)) * g(cr(R).abs() > p["k"])), {"k": [0.5, 1.0]}),
          S("STRAT-1002", "Commodity supply-demand: gasoline inventory vs crack", "gasoline stocks surprise vs seasonal: unexpected draw -> long gasoline crack (NYH gasoline vs WTI)", ["energy"],
            lambda R, p: spread(R, {"GAS_NYH": 1, "WTI": -1}, -np.sign(to_daily(avail(seas_surprise(eia("WGTSTUS1")), 5), R.index)) * g(to_daily(avail(seas_surprise(eia("WGTSTUS1")), 5), R.index).abs() > p["k"])), {"k": [0.5, 1.0]}, sizing=False),
          S("STRAT-1003", "Commodity supply-demand: distillate inventory vs crack", "distillate stocks surprise vs seasonal: unexpected draw -> long heating-oil crack", ["energy"],
            lambda R, p: spread(R, {"HO_NYH": 1, "WTI": -1}, -np.sign(to_daily(avail(seas_surprise(eia("WDISTUS1")), 5), R.index)) * g(to_daily(avail(seas_surprise(eia("WDISTUS1")), 5), R.index).abs() > p["k"])), {"k": [0.5, 1.0]}, sizing=False),
          S("STRAT-1004", "Commodity supply-demand: refinery utilisation", "refinery utilisation above its 5-year seasonal norm (more product supply) -> short the 3-2-1 crack, below -> long", ["energy"],
            lambda R, p: spread(R, {"GAS_NYH": 2 / 3, "HO_NYH": 1 / 3, "WTI": -1}, -np.sign(to_daily(avail(seas_level(eia("WPULEUS3")), 5), R.index)) * g(to_daily(avail(seas_level(eia("WPULEUS3")), 5), R.index).abs() > p["x"])), {"x": [0.01, 0.03]}, sizing=False),
          S("STRAT-1005", "Commodity supply-demand: storage theory (inventory level)", "crude inventories below their 5-year same-week average (scarcity, backwardation) -> long WTI, above -> short (Gorton-Hayashi-Rouwenhorst)", ["energy"],
            lambda R, p: one_col(R, "WTI", -np.sign(to_daily(avail(seas_level(eia("WCESTUS1")), 5), R.index)) * g(to_daily(avail(seas_level(eia("WCESTUS1")), 5), R.index).abs() > p["x"])), {"x": [0.0, 0.03]})]
    o += [S("STRAT-1006", "Macro event: pre-FOMC drift", "hold US equities over FOMC statement days only (Lucca-Moench pre-announcement drift; FOMC dates from federalreserve.gov, 2006+)", ["mkt"],
            lambda R, p: pd.DataFrame({"MKT": g(fomc_days(R.index).shift(-1).fillna(False) | (fomc_days(R.index) & (p["w"] == 2)))}, index=R.index), {"w": [1, 2]}, start="2006-01-01"),
          S("STRAT-1007", "Macro event: post-FOMC Treasury drift", "after an FOMC statement day, hold Treasuries in the direction of that day's 10y yield move (continuation, sgn=+1) or against it (reversal) for H days", ["bonds"],
            lambda R, p: pd.DataFrame({c: hold(pd.DataFrame({"x": (-np.sign(P["yields"]["DGS10"].diff().reindex(R.index)) * p["sgn"] * fomc_days(R.index)).fillna(0)}), p["H"])["x"] for c in R.columns}, index=R.index), {"sgn": [1, -1], "H": [3, 5]}, start="2006-01-01"),
          S("STRAT-1008", "Macro event: jobless-claims shock", "initial claims 4-week rise > k sd (labour-market shock, used from Thursday release): long 10y Treasuries / short equities for a week", ["mkt_bonds"],
            lambda R, p: (lambda z: pd.DataFrame({"MKT": -hold(pd.DataFrame({"x": g(z > p["k"])}), 5)["x"], "UST10Y": hold(pd.DataFrame({"x": g(z > p["k"])}), 5)["x"]}, index=R.index))(
                to_daily(avail(((P["macro"]["ICSA"] / P["macro"]["ICSA"].rolling(4).mean().shift(1) - 1) / (P["macro"]["ICSA"] / P["macro"]["ICSA"].rolling(4).mean().shift(1) - 1).rolling(156).std()), 5), R.index)), {"k": [1.5, 2.5]}),
          S("STRAT-1009", "Macro regime: financial-conditions index", "Chicago Fed NFCI tightened over 4 weeks (published with a 5-day lag) -> out of equities, otherwise long", ["mkt"],
            lambda R, p: pd.DataFrame({"MKT": g(to_daily(avail(P["macro"]["NFCI"].diff(p["n"]), 5), R.index) <= 0)}, index=R.index), {"n": [2, 4]}, start="1972-01-01"),
          S("STRAT-1010", "Alternative data: news-based policy uncertainty", "daily Economic Policy Uncertainty index (newspaper text) 30-day average in its top 20% of 3 years -> long equities (risk premium, sgn=+1) or out (sgn=-1)", ["mkt"],
            lambda R, p: pd.DataFrame({"MKT": (lambda q: g(q > 0.8) if p["sgn"] == 1 else g(q <= 0.8))(_fred("USEPUINDXD").rolling(30).mean().rolling(756).rank(pct=True).shift(1).reindex(R.index).ffill())}, index=R.index), {"sgn": [1, -1]}, start="1988-01-01")]
    o += [S("STRAT-1012", "Machine learning: gradient-boosted multi-asset classifier", "HistGradientBoosting on lagged returns, vol, price z-score, VIX and curve slope predicts each asset's next-5-day sign; retrained yearly on the previous `win` years; position = k x (2p-1)", ["macro_long"], gbm_signal, {"win": [10], "k": [2.0]}),
          S("STRAT-1013", "Machine learning: random-forest cross-sectional ranker", "random forest predicts next-month return rank of 49 industries from 1/3/12-month returns, vol and idiosyncratic vol; refit every 5 years on past data; long top / short bottom q", ["ind49"], rf_xs, {"q": [0.2]}, start="1940-01-01"),
          S("STRAT-1014", "Machine learning: logistic model on crypto derivatives positioning", "logistic regression on funding, premium, OI change, taker ratio and 7-day return predicts the next-3-day sign of BTC/ETH/SOL/XRP/DOGE perps; refit yearly", ["perp"], logit_crypto, {"th": [0.03, 0.08]}),
          S("STRAT-1015", "Machine learning: k-nearest-neighbour analogues", "embed the last 10 vol-scaled daily market returns; the k nearest historical analogues' next-day mean return gives the position sign; refit yearly", ["mkt"], knn_mkt, {"k": [50, 200]}, start="1930-01-01"),
          S("STRAT-1016", "Reinforcement learning: tabular Q-learning allocator", "weekly Q-learning over states (vol tercile x curve sign x NFCI sign) and actions {cash, equities, 10y}; trained on past weeks only, refit yearly, greedy policy", ["mkt_bonds"], qlearn, {"gamma": [0.0, 0.5]}, sizing=True)]
    o += [S("STRAT-1018", "Nonlinear: Hurst-exponent regime switching", "DFA Hurst exponent on the last 128 days: H > hi -> follow the 20-day direction (persistent), H < 1-hi -> fade the 5-day move (anti-persistent), else flat", ["macro_long"], hurst_switch, {"hi": [0.55, 0.6]}),
          S("STRAT-1019", "Nonlinear: ordinal-pattern (permutation-entropy) forecasting", "the next-day mean return after each of the 24 ordinal patterns of the last 4 returns, learned on past years (|t| > t), traded only when 60-day permutation entropy is below its median", ["macro_long"], ordinal, {"t": [2.0, 3.0]})]
    o += [S("STRAT-1020", "Market-neutral factor: betting against beta", "long low-beta / short high-beta industries, each leg scaled to beta 1 (Frazzini-Pedersen), monthly", ["ind49"], bab, {"q": [0.2, 0.3]}, sizing=False, start="1930-01-01"),
          S("STRAT-1021", "Market-neutral factor: idiosyncratic volatility", "long low / short high idiosyncratic-vol industries (market-model residual vol, 63 days), monthly", ["ind49"], ivol, {"q": [0.2, 0.3]}, start="1930-01-01"),
          S("STRAT-1022", "Market-neutral factor: MAX (lottery) effect", "short the industries with the largest single-day return in the past month, long the smallest (Bali-Cakici-Whitelaw), monthly", ["ind49"], maxeff, {"q": [0.2, 0.3]}, start="1930-01-01"),
          S("STRAT-1023", "Statistical arbitrage: industry lead-lag network", "for each industry, the 3 industries whose lagged weekly returns best predicted it over the past 15 years form its leaders; rank by leaders' last-week return, long top / short bottom", ["ind49"], leadlag_net, {"q": [0.2]}, start="1940-01-01")]
    o += [S("STRAT-1024", "Cross-exchange: Coinbase premium (US demand) signal", "Coinbase USD vs Binance USDT price premium z-score (30 days): US buyers paying up (z > k) -> long BTC/ETH, discount -> short", ["crypto"],
            lambda R, p: (lambda z: pd.DataFrame({c: (g(z[c] > p["k"]) - g(z[c] < -p["k"])) if c in ("BTC", "ETH") else 0.0 for c in R.columns}, index=R.index))(cb_premium(R)), {"k": [1.0, 2.0]}),
          S("STRAT-1025", "Cross-exchange: price-dislocation convergence", "fade the Coinbase-Binance daily-close dislocation: long the cheap venue / short the rich venue when |z| > k (two-venue spread, both legs costed)", ["xex"],
            lambda R, p: (lambda z: pd.DataFrame({c: (-np.sign(z[c]) * g(z[c].abs() > p["k"])).fillna(0) for c in R.columns}, index=R.index))(cb_premium(R)), {"k": [1.5, 2.5]}),
          S("STRAT-1026", "Alternative data: DeFi TVL vs price (chain value)", "weekly: long the chain tokens whose total value locked grew faster than their price over n days, short the slowest (ETH, SOL, BNB, AVAX, TRX, ADA; DefiLlama)", ["crypto"], tvl_value, {"n": [30, 90]}),
          S("STRAT-1027", "On-chain value: BTC network-value-to-transactions", "log(BTC price / 90-day average transactions) z-score over a year: cheap (z < -z0) -> long, expensive (z > z0) -> short if short=1", ["btc"], nvt, {"z": [0.5, 1.0], "short": [0, 1]}),
          S("STRAT-1028", "Credit relative value: structural (Merton-style) residual", "Baa-Treasury spread vs the spread implied by equity vol (VIX) and equity drawdown (rolling 3-year regression): credit cheap vs equity -> long hedged credit, rich -> short", ["credit"], merton_resid, {"N": [756, 1260]}, sizing=False),
          S("STRAT-1030", "Volatility-managed equity (Moreira-Muir)", "equity exposure = long-run average variance / last-n-day variance, capped (vol timing of the market, not trend)", ["mkt"], volmanaged, {"n": [21, 63], "cap": [2.0]}, sizing=False, start="1930-01-01"),
          S("STRAT-1031", "Term structure: Cochrane-Piazzesi forward-rate factor", "regress next-12-month 2-5y bond excess returns on 1-5y forward rates (rolling, using only completed windows); long 5y duration when predicted excess return > 0, short when < 0", ["bonds"], cochrane_piazzesi, {"yrs": [20, 30]}, start="1970-01-01")]
    return sorted(o, key=lambda s: s["id"])
def nfci_realtime(n):
    """4-week (n-week) NFCI change as it was published each Wednesday (ALFRED vintage), usable from the next day."""
    rows = {}
    for f in sorted(glob.glob(f"{RDATA}/alfred_nfci/*.csv")):
        v = pd.Timestamp(os.path.basename(f)[:-4])
        try: d = pd.read_csv(f); x = pd.to_numeric(d.iloc[:, 1], errors="coerce").dropna()
        except Exception: continue
        if len(x) > n: rows[v + pd.Timedelta(days=1)] = x.iloc[-1] - x.iloc[-1 - n]
    return pd.Series(rows).sort_index()
_specs_old = specs
def specs():
    o = _specs_old()
    o.append(S("STRAT-1032", "Macro regime: financial-conditions index, REAL-TIME vintages", "same rule as STRAT-1009 but using only the NFCI values published at each Wednesday release (ALFRED vintages, 2011-06+): tightened over n weeks -> out of equities, else long", ["mkt"],
               lambda R, p: pd.DataFrame({"MKT": g(to_daily(nfci_realtime(p["n"]), R.index) <= 0)}, index=R.index), {"n": [2, 4]}, start="2011-06-02"))
    o.append(S("STRAT-1033", "Macro regime: financial-conditions index, revised data, same period", "STRAT-1009 rule on today's revised NFCI restricted to 2011-06+ (control for STRAT-1032)", ["mkt"],
               lambda R, p: pd.DataFrame({"MKT": g(to_daily(avail(P["macro"]["NFCI"].diff(p["n"]), 5), R.index) <= 0)}, index=R.index), {"n": [2, 4]}, start="2011-06-02"))
    return sorted(o, key=lambda s: s["id"])
