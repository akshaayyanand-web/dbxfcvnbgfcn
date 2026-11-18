"""Backtest + validation engine used for every catalogue entry.
Positions are decided on day t's close and earn day t+1's return (no look-ahead). Costs = |change in weight| x cost_bps per side.
Protocol per strategy: pre-registered small grid -> select on TRAIN (first 60%) by Sharpe -> report VALIDATION (next 20%)
-> report untouched TEST (last 20%) once -> expanding walk-forward (re-select yearly) -> uniqueness check vs earlier strategies."""
import os, json, pickle, itertools, numpy as np, pandas as pd
from data import load, COST, SCR
P = load()
PNL_DIR = f"{SCR}/rdata/pnl"; os.makedirs(PNL_DIR, exist_ok=True)
RES = os.path.join(os.path.dirname(__file__), "results", "results.jsonl")
ANN = {"crypto": 365, "default": 252}

def _rets(px): return px.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)

def universe(name):
    """returns (daily returns DataFrame, per-asset cost bps Series, periods/year)"""
    if name == "crypto":
        R = _rets(P["crypto"]); return R, pd.Series(COST["crypto"], R.columns), 365
    if name == "cfd":
        R = _rets(P["cfd"]); R = R[R.index.dayofweek < 5]
        c = pd.Series({k: COST["metal"] if k in ("GOLD", "SILVER") else COST["energy"] if k == "WTI" else COST["index"] for k in R.columns}); return R, c, 252
    if name == "fx":
        R = _rets(P["fx"]); return R, pd.Series(COST["fx"], R.columns), 252
    if name == "bonds":
        R = P["bonds_ret"]; return R, pd.Series(COST["rates"], R.columns), 252
    if name in ("ind10", "ind49"):
        R = P[name]; return R, pd.Series(COST["industry"], R.columns), 252
    if name == "macro_long":   # long-history multi-asset: FX + Treasuries + Nasdaq Composite + WTI/Brent spot
        R = pd.concat([_rets(P["fx"]), P["bonds_ret"], _rets(P["macro"]["NASDAQCOM"]).rename("NASDAQ"),
                       _rets(P["macro"]["DCOILWTICO"].where(P["macro"]["DCOILWTICO"] > 0)).rename("WTI_SPOT")], axis=1)
        R = R[R.index.dayofweek < 5].clip(-0.25, 0.25)
        c = pd.Series({k: COST["fx"] if len(k) == 2 else COST["rates"] if k.startswith("UST") else COST["index"] if k == "NASDAQ" else COST["commod_spot"] for k in R.columns})
        return R, c, 252
    if name == "multi_recent":  # 2016+: CFDs + FX + Treasuries + BTC/ETH (weekday calendar)
        R1, c1, _ = universe("cfd"); R2, c2, _ = universe("fx"); R3, c3, _ = universe("bonds"); R4, c4, _ = universe("crypto")
        R4 = R4[["BTC", "ETH"]]; R4.index = R4.index.tz_localize(None); R1 = R1.copy(); R1.index = R1.index.tz_localize(None)
        R4 = (1 + R4.fillna(0)).resample("1D").prod() - 1
        R = pd.concat([R1, R2, R3, R4], axis=1).loc["2016-01-04":]; R = R[R.index.dayofweek < 5]
        return R, pd.concat([c1, c2, c3, c4[["BTC", "ETH"]]]), 252
    if name.startswith("pairs_"):   # dollar-neutral spreads: long A / short B, cost = both legs
        base = {"pairs_cfd": ("cfd", [("NQ", "SPX"), ("SPX", "RUT"), ("DJI", "SPX"), ("GOLD", "SILVER"), ("NQ", "RUT"), ("GOLD", "WTI")]),
                "pairs_crypto": ("crypto", [("ETH", "BTC"), ("SOL", "ETH"), ("BNB", "BTC"), ("LTC", "BTC"), ("XRP", "BTC"), ("ADA", "ETH"), ("DOGE", "BTC"), ("LINK", "ETH")]),
                "pairs_macro": ("macro_long", [("UST10Y", "UST2Y"), ("UST30Y", "UST5Y"), ("AL", "NZ"), ("EU", "SZ"), ("CA", "AL"), ("NO", "SD"), ("UK", "EU"), ("JP", "SZ")])}[name]
        R0, c0, a = universe(base[0])
        R = pd.DataFrame({f"{x}-{y}": R0[x] - R0[y] for x, y in base[1] if x in R0 and y in R0}).dropna(how="all")
        c = pd.Series({f"{x}-{y}": c0[x] + c0[y] for x, y in base[1] if x in R0 and y in R0})
        return R, c, a
    raise ValueError(name)

def ewvol(R, span=60, ann=252): return (R.ewm(span=span, min_periods=20).std() * np.sqrt(ann)).shift(0)

def size(signal, R, ann, tv=0.15, cap=3.0, span=60):
    """inverse-vol sizing: each active asset targets tv/sqrt(N_active) so the book ~tv if uncorrelated; per-asset cap."""
    v = ewvol(R, span, ann).replace(0, np.nan)
    n = signal.notna().sum(1).replace(0, np.nan)
    w = signal * (tv / v).clip(upper=cap)
    return w.div(np.sqrt(n), axis=0).fillna(0)

def run(w, R, cost, ann, tv=0.15, port_vt=True, lev_cap=5.0, gross_cap=None):
    """daily net pnl of weights w (decided at t close). Optional portfolio vol targeting with lagged realised vol."""
    w = w.reindex(R.index).fillna(0)
    gross = (w.shift(1) * R.fillna(0)).sum(1)
    if port_vt:
        rv = gross.ewm(span=120, min_periods=40).std().shift(1) * np.sqrt(ann)
        k = (tv / rv).clip(upper=lev_cap).fillna(0)
        w = w.mul(k.shift(-1).fillna(0), axis=0)   # scale decided with info up to t (k_{t+1} uses vol through t)
        gross = (w.shift(1) * R.fillna(0)).sum(1)
    gc = gross_cap or (2.0 if ann == 365 else 4.0)                 # realistic margin: max gross exposure
    g = w.abs().sum(1); w = w.mul((gc / g).clip(upper=1).fillna(0), axis=0)
    gross = (w.shift(1) * R.fillna(0)).sum(1)
    tc = (w.diff().abs() * cost.reindex(w.columns).fillna(10) / 1e4).sum(1)
    return gross - tc, w, tc

def metrics(p, ann):
    p = p.dropna()
    if len(p) < 20 or p.std() == 0: return dict(cagr=0, vol=0, sharpe=0, sortino=0, maxdd=0, calmar=0)
    eq = (1 + p).cumprod(); yrs = len(p) / ann
    cagr = eq.iloc[-1] ** (1 / yrs) - 1 if eq.iloc[-1] > 0 else -1
    dd = (eq / eq.cummax() - 1).min(); sd = p[p < 0].std()
    return dict(cagr=round(float(cagr), 4), vol=round(float(p.std() * np.sqrt(ann)), 4), sharpe=round(float(p.mean() / p.std() * np.sqrt(ann)), 3),
                sortino=round(float(p.mean() / sd * np.sqrt(ann)), 3) if sd > 0 else 0, maxdd=round(float(dd), 4), calmar=round(float(cagr / -dd), 3) if dd < 0 else 0)

def trades(w, R):
    """per-asset trade segmentation: a trade = a run of same-sign non-zero weight; pnl = sum of weight_{t-1} x ret_t over the run."""
    w = w.reindex(R.index).fillna(0); contrib = w.shift(1) * R.fillna(0); out = []
    for c in w.columns:
        s = np.sign(w[c].values); ct = contrib[c].values; cur = 0; acc = 0.0
        for i in range(len(s)):
            if cur != 0: acc += ct[i]
            if s[i] != cur:
                if cur != 0: out.append(acc)
                cur = s[i]; acc = 0.0
        if cur != 0: out.append(acc)
    t = np.array(out)
    if len(t) == 0: return dict(trades=0, win=0, pf=0, avg_win=0, avg_loss=0)
    return dict(trades=int(len(t)), win=round(float((t > 0).mean()), 3), pf=round(float(t[t > 0].sum() / -t[t < 0].sum()), 3) if (t < 0).any() else 99,
                avg_win=round(float(t[t > 0].mean()), 5) if (t > 0).any() else 0, avg_loss=round(float(t[t < 0].mean()), 5) if (t < 0).any() else 0)

def lev_for_target(p, ann, target=3.0):
    """scale k such that the compounded annualised return of k*p reaches +300%; returns (k, maxDD at k) or None if unreachable."""
    p = p.dropna(); best = None
    for k in np.arange(0.5, 40.01, 0.25):
        q = (k * p).clip(lower=-0.99); eq = (1 + q).cumprod()
        cagr = eq.iloc[-1] ** (ann / len(q)) - 1
        if cagr >= target: return float(k), float((eq / eq.cummax() - 1).min())
        best = cagr
    return None, None

def split_idx(idx):
    n = len(idx); return idx[int(n * 0.6)], idx[int(n * 0.8)]

def evaluate(sid, name, universe_name, signal_fn, grid, mechanism, notes="", start=None, sizing=True, cap=3.0):
    """signal_fn(R, params) -> raw signal DataFrame (positions before sizing, decided at close t)."""
    R, cost, ann = universe(universe_name)
    if start: R = R.loc[start:]
    R = R.dropna(how="all")
    keys = sorted(grid); combos = [dict(zip(keys, v)) for v in itertools.product(*[grid[k] for k in keys])]
    t1, t2 = split_idx(R.index); runs = []
    for prm in combos:
        sig = signal_fn(R, prm)
        w = size(sig, R, ann, cap=cap) if sizing else sig
        pnl, wf, tc = run(w, R, cost, ann)
        runs.append((prm, pnl, wf, tc))
    tr = [metrics(p.loc[:t1], ann)["sharpe"] for _, p, _, _ in runs]
    bi = int(np.argmax(tr)); prm, pnl, wf, tc = runs[bi]
    m_tr, m_va, m_te = metrics(pnl.loc[:t1], ann), metrics(pnl.loc[t1:t2].iloc[1:], ann), metrics(pnl.loc[t2:].iloc[1:], ann)
    # walk-forward: each calendar year after the first 3 years, pick params by Sharpe on all data before it
    years = sorted(set(R.index.year))[3:]; wf_parts = []
    for y in years:
        past = [metrics(p[p.index.year < y], ann)["sharpe"] for _, p, _, _ in runs]
        j = int(np.argmax(past)); wf_parts.append(runs[j][1][runs[j][1].index.year == y])
    wfp = pd.concat(wf_parts) if wf_parts else pnl.iloc[:0]
    m_wf = metrics(wfp, ann); tstats = trades(wf.loc[t2:], R.loc[t2:])
    # benchmark: equal-risk buy-and-hold of the same universe, same vol target / caps
    bp, _, _ = run(size(R.notna().astype(float).where(R.notna()), R, ann, cap=cap), R, cost, ann)
    b_te = metrics(bp.loc[t2:].iloc[1:], ann); bw = bp.reindex(wfp.index)
    X = np.vstack([np.ones(len(wfp)), bw.fillna(0).values]).T
    beta_hat, *_ = np.linalg.lstsq(X, wfp.fillna(0).values, rcond=None); resid = wfp.fillna(0).values - X @ beta_hat
    a_t = beta_hat[0] / (resid.std() / np.sqrt(len(resid))) if resid.std() > 0 else 0
    alpha = dict(alpha_ann=round(float(beta_hat[0] * ann), 4), alpha_t=round(float(a_t), 2), beta=round(float(beta_hat[1]), 2), bench_test_sharpe=b_te["sharpe"])
    robust = round(float(np.mean([s > 0 for s in tr])), 2)
    k300, dd300 = lev_for_target(wfp, ann)
    # uniqueness: correlation of walk-forward pnl with every earlier strategy's walk-forward pnl
    corr_max, corr_id = 0.0, None
    tag = f"{sid}@{universe_name}"
    for f in os.listdir(PNL_DIR):
        oid = f[:-4]
        if oid == tag or not oid.endswith("@" + universe_name) or oid.split("@")[0] >= sid: continue
        o = pickle.load(open(f"{PNL_DIR}/{f}", "rb"))
        a = wfp.copy(); b = o.copy()
        a.index = pd.to_datetime(a.index).tz_localize(None) if getattr(a.index, "tz", None) else a.index
        b.index = pd.to_datetime(b.index).tz_localize(None) if getattr(b.index, "tz", None) else b.index
        a = a.groupby(a.index.normalize()).sum(); b = b.groupby(b.index.normalize()).sum()
        j = pd.concat([a, b], axis=1, join="inner").dropna()
        if len(j) > 250:
            c = float(j.corr().iloc[0, 1])
            if abs(c) > abs(corr_max): corr_max, corr_id = c, oid.split("@")[0]
    pickle.dump(wfp, open(f"{PNL_DIR}/{tag}.pkl", "wb"))
    beats = (alpha["beta"] < 0.3) or (alpha["alpha_t"] >= 2 and m_te["sharpe"] > b_te["sharpe"])   # long-biased must add alpha over buy-and-hold
    passed = m_va["sharpe"] > 0 and m_te["sharpe"] > 0.3 and m_wf["sharpe"] > 0.3 and tstats["trades"] >= 30 and alpha["alpha_t"] >= 1.5 and beats
    rec = dict(id=sid, name=name, universe=universe_name, mechanism=mechanism, notes=notes, params=prm, trials=len(combos),
               period=f"{R.index[0].date()}..{R.index[-1].date()}", split=f"train..{t1.date()} | val..{t2.date()} | test..{R.index[-1].date()}",
               train=m_tr, val=m_va, test=m_te, walkforward=m_wf, test_trades=tstats, grid_positive_share=robust,
               avg_daily_cost_bps=round(float(tc.mean() * 1e4), 2), lev_for_300=k300, maxdd_at_300=None if dd300 is None else round(dd300, 3),
               max_corr=round(corr_max, 2), max_corr_with=corr_id, **alpha, passed=bool(passed))
    with open(RES, "a") as f: f.write(json.dumps(rec) + "\n")
    return rec

def evaluate_streams(sid, name, uname, stream_fn, grid, mechanism, notes=""):
    """same protocol for strategies whose per-asset daily net returns are produced directly (intraday trade streams)."""
    keys = sorted(grid); combos = [dict(zip(keys, v)) for v in itertools.product(*[grid[k] for k in keys])]
    ann = 252; runs = []
    for prm in combos:
        S = stream_fn(prm).sort_index(); S = S[S.index.dayofweek < 5]
        act = S.notna() & (S != 0)
        w = size((S.notna()).astype(float).where(S.notna()), S.fillna(0).where(S.notna()), ann, cap=3.0)
        pnl, wf, tc = run(w, S.fillna(0), pd.Series(0.0, S.columns), ann)
        runs.append((prm, pnl, wf, S, act))
    idx = runs[0][1].index; t1, t2 = split_idx(idx)
    tr = [metrics(p.loc[:t1], ann)["sharpe"] for _, p, _, _, _ in runs]; bi = int(np.argmax(tr)); prm, pnl, wf, S, act = runs[bi]
    m_tr, m_va, m_te = metrics(pnl.loc[:t1], ann), metrics(pnl.loc[t1:t2].iloc[1:], ann), metrics(pnl.loc[t2:].iloc[1:], ann)
    years = sorted(set(idx.year))[2:]; parts = []
    for y in years:
        past = [metrics(p[p.index.year < y], ann)["sharpe"] for _, p, _, _, _ in runs]; j = int(np.argmax(past)); parts.append(runs[j][1][runs[j][1].index.year == y])
    wfp = pd.concat(parts); m_wf = metrics(wfp, ann)
    tt = S.loc[t2:].where(act.loc[t2:]).stack().dropna(); ntr = int(len(tt))
    tst = dict(trades=ntr, win=round(float((tt > 0).mean()), 3) if ntr else 0, pf=round(float(tt[tt > 0].sum() / -tt[tt < 0].sum()), 3) if (tt < 0).any() else 0,
               avg_win=round(float(tt[tt > 0].mean()), 5) if (tt > 0).any() else 0, avg_loss=round(float(tt[tt < 0].mean()), 5) if (tt < 0).any() else 0)
    a_t = float(wfp.mean() / (wfp.std() / np.sqrt(len(wfp)))) if wfp.std() > 0 else 0
    tag = f"{sid}@{uname}"; corr_max, corr_id = 0.0, None
    for f in os.listdir(PNL_DIR):
        oid = f[:-4]
        if not oid.endswith("@" + uname) or oid.split("@")[0] >= sid: continue
        o = pickle.load(open(f"{PNL_DIR}/{f}", "rb")); j = pd.concat([wfp, o], axis=1, join="inner").dropna()
        if len(j) > 250:
            c = float(j.corr().iloc[0, 1])
            if abs(c) > abs(corr_max): corr_max, corr_id = c, oid.split("@")[0]
    pickle.dump(wfp, open(f"{PNL_DIR}/{tag}.pkl", "wb")); k300, dd300 = lev_for_target(wfp, ann)
    passed = m_va["sharpe"] > 0 and m_te["sharpe"] > 0.3 and m_wf["sharpe"] > 0.3 and ntr >= 30 and a_t >= 1.5
    rec = dict(id=sid, name=name, universe=uname, mechanism=mechanism, notes=notes, params=prm, trials=len(combos), period=f"{idx[0].date()}..{idx[-1].date()}",
               split=f"train..{t1.date()} | val..{t2.date()} | test..{idx[-1].date()}", train=m_tr, val=m_va, test=m_te, walkforward=m_wf, test_trades=tst,
               grid_positive_share=round(float(np.mean([s > 0 for s in tr])), 2), avg_daily_cost_bps=None, lev_for_300=k300, maxdd_at_300=None if dd300 is None else round(dd300, 3),
               max_corr=round(corr_max, 2), max_corr_with=corr_id, alpha_ann=round(float(wfp.mean() * ann), 4), alpha_t=round(a_t, 2), beta=0.0, bench_test_sharpe=None, passed=bool(passed))
    with open(RES, "a") as f: f.write(json.dumps(rec) + "\n")
    return rec
