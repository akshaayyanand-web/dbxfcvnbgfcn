"""Backtest + validation engine used for every catalogue entry.
Positions are decided on day t's close and earn day t+1's return (no look-ahead). Costs = |change in weight| x cost_bps per side.
Protocol per strategy: pre-registered small grid -> select on TRAIN (first 60%) by Sharpe -> report VALIDATION (next 20%)
-> report untouched TEST (last 20%) once -> expanding walk-forward (re-select yearly) -> uniqueness check vs earlier strategies."""
import os, json, pickle, itertools, numpy as np, pandas as pd
from data import load, COST, SCR
P = load()
PNL_DIR = f"{SCR}/rdata/pnl"; os.makedirs(PNL_DIR, exist_ok=True)
RES = os.path.join(os.path.dirname(__file__), "results", "results.jsonl")
import subprocess, datetime as _dt
RUN_ID = os.environ.get("RUN_ID") or _dt.datetime.utcnow().strftime("run_%Y%m%d_%H%M%S")
try: COMMIT = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=os.path.dirname(__file__)).stdout.strip()
except Exception: COMMIT = "unknown"
def save_record(rec):
    """append-only: current table + per-run log (never edited in place)."""
    rec = dict(rec, run_id=RUN_ID, code_commit=COMMIT, recorded_utc=_dt.datetime.utcnow().isoformat(timespec="seconds"))
    os.makedirs(os.path.join(os.path.dirname(RES), "runs"), exist_ok=True)
    for path in (RES, os.path.join(os.path.dirname(RES), "runs", RUN_ID + ".jsonl")):
        with open(path, "a") as f: f.write(json.dumps(rec) + "\n")
ANN = {"crypto": 365, "default": 252}

def _rets(px): return px.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)

_RF = None
def rf_daily():
    """daily cash rate: Fama-French RF (1926+), extended with fed funds/360 after it ends."""
    global _RF
    if _RF is None:
        ff = P["ff3"]["RF"].copy(); dff = P["yields"]["DFF"] / 100 / 360
        _RF = pd.concat([ff, dff[dff.index > ff.index[-1]]]).sort_index()
    return _RF
def excess(R):
    i2 = R.index.tz_localize(None) if getattr(R.index, "tz", None) is not None else R.index
    rf = rf_daily().reindex(i2, method="ffill").fillna(0).values
    if (pd.DatetimeIndex(i2).dayofweek >= 5).mean() > 0.1: rf = rf * 252 / 365     # calendar-day series (crypto): per-calendar-day cash rate
    return R.sub(rf, axis=0)
def universe(name):
    """returns (daily EXCESS returns over cash for funded assets, per-asset cost bps, periods/year). FX/spreads are already self-financing."""
    R, c, a = _universe(name)
    if name in ("mkt_bonds_x",) or name in ("crypto", "btc", "cfd", "bonds", "ind10", "ind49", "macro_long", "multi_recent", "cashcarry", "qbasis"):
        if name in ("macro_long", "multi_recent"):
            funded = [k for k in R.columns if len(k) != 2]           # FX columns (2 letters) are spot, unfunded
            R = R.copy(); R[funded] = excess(R[funded])
        else: R = excess(R)
    return R, c, a
def _universe(name):
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
        R1, c1, _ = _universe("cfd"); R2, c2, _ = _universe("fx"); R3, c3, _ = _universe("bonds"); R4, c4, _ = _universe("crypto")
        R4 = R4[["BTC", "ETH"]]; R4.index = R4.index.tz_localize(None); R1 = R1.copy(); R1.index = R1.index.tz_localize(None)
        R4 = (1 + R4.fillna(0)).resample("1D").prod() - 1
        R = pd.concat([R1, R2, R3, R4], axis=1).loc["2016-01-04":]; R = R[R.index.dayofweek < 5]
        return R, pd.concat([c1, c2, c3, c4[["BTC", "ETH"]]]), 252
    if name == "fx_tr":    # FX spot + daily carry accrual (foreign minus US 3m interbank, monthly OECD, lagged ~1 month)
        R, c, a = _universe("fx"); rd = fx_rate_diff().reindex(R.index, method="ffill")
        return (R + rd / 100 / 252).where(R.notna()), c, a
    if name == "energy":   # FRED spot crude and refined products (spot proxies for NYMEX CL/RB/HO, see notes)
        from data import _fred
        px_ = pd.concat([_fred("DCOILWTICO").where(lambda x: x > 0).rename("WTI"), _fred("DCOILBRENTEU").rename("BRENT"), _fred("DGASNYH").rename("GAS_NYH"),
                         _fred("DHOILNYH").rename("HO_NYH"), _fred("DJFUELUSGULF").rename("JET_GULF"), _fred("DGASUSGULF").rename("GAS_GULF")], axis=1)
        R = _rets(px_); R = R[R.index.dayofweek < 5].clip(-0.3, 0.3).loc["1990-04-03":]
        return R, pd.Series(5.0, R.columns), 252
    if name in ("curve", "swaps", "credit"):
        from data import _fred, _par_bond_ret
        if name == "curve":
            ys = {n: _fred(f"DGS{n}") for n in (1, 2, 3, 5, 7, 10, 20, 30)}
            ys[20] = ys[20].combine_first((_fred("DGS10") + _fred("DGS30")) / 2)            # 1987-93 gap: midpoint of 10y and 30y
            R = pd.DataFrame({f"T{n}": _par_bond_ret(y, n) for n, y in ys.items()}).loc["1962-01-03":]
            R = excess(R); return R, pd.Series(1.0, R.columns), 252
        if name == "swaps":
            R = pd.DataFrame({**{f"SW{n}": _par_bond_ret(_fred(f"DSWP{n}"), n) for n in (2, 5, 10, 30)}, **{f"T{n}": _par_bond_ret(_fred(f"DGS{n}"), n) for n in (2, 5, 10, 30)}}).loc["2000-07-05":"2016-10-28"]
            R = excess(R); return R, pd.Series(1.5, R.columns), 252
        t20 = _fred("DGS20").combine_first((_fred("DGS10") + _fred("DGS30")) / 2)
        R = pd.DataFrame({"BAA": _par_bond_ret(_fred("DBAA"), 20), "AAA": _par_bond_ret(_fred("DAAA"), 20), "T20": _par_bond_ret(t20, 20)}).loc["1986-01-03":]
        R = excess(R); return R, pd.Series({"BAA": 10.0, "AAA": 8.0, "T20": 1.0}), 252
    if name == "mkt":            # US equity market excess return (Fama-French Mkt-RF, CRSP value-weighted)
        R = P["ff3"][["Mkt-RF"]].rename(columns={"Mkt-RF": "MKT"}); return R, pd.Series(1.0, R.columns), 252
    if name == "mkt_bonds":      # market excess + 10y Treasury excess
        R = pd.concat([P["ff3"]["Mkt-RF"].rename("MKT"), (P["bonds_ret"]["UST10Y"] - P["ff3"]["RF"].reindex(P["bonds_ret"].index).fillna(0)).rename("UST10Y")], axis=1).dropna()
        return R, pd.Series({"MKT": 1.0, "UST10Y": 1.0}), 252
    if name == "xex":            # Coinbase USD minus Binance USDT daily return, BTC and ETH (both legs costed)
        import json as _j
        out = {}
        for c in ("BTC", "ETH"):
            rows = _j.load(open(f"{SCR}/indep/cb/{c}.json")); cb = pd.Series({pd.Timestamp(int(t), unit="s", tz="UTC"): float(cl) for t, lo, hi, op, cl, v in rows}).sort_index()
            bn = P["crypto"][c]; out[c] = (cb.pct_change() - bn.pct_change().reindex(cb.index))
        R = pd.DataFrame(out).loc["2020-01-02":"2026-10-30"]; return R, pd.Series(12.0, R.columns), 365
    if name == "btc":
        R = _rets(P["crypto"][["BTC"]]); return R, pd.Series(6.0, R.columns), 365
    if name in ("perp", "cashcarry", "qbasis"):
        import crypto2; C2 = crypto2.load()
        pr = C2["perp"]; fu = C2["fund"].rename(columns=lambda c: c.replace("USDT", "")).reindex(pr.index).fillna(0)[pr.columns.intersection(C2["fund"].rename(columns=lambda c: c.replace("USDT", "")).columns)]
        fu = fu.reindex(columns=pr.columns).fillna(0)
        if name == "perp":
            R = (_rets(pr) - fu).loc["2021-01-02":]; return R, pd.Series(5.0, R.columns), 365
        if name == "cashcarry":   # long spot, short perp: earns funding, pays the basis change; both legs costed
            sp = P["crypto"].reindex(pr.index)[pr.columns.intersection(P["crypto"].columns)]
            R = (_rets(sp) - _rets(pr[sp.columns]) + fu[sp.columns]).loc["2021-01-02":]; return R, pd.Series(10.0, R.columns), 365
        sp = P["crypto"]; out = {}
        for s in C2["cm"]:
            q = C2["cm"][s]; out[s] = _rets(sp[s]).reindex(q.index) - q["ret"]
        R = pd.DataFrame(out).loc["2020-06-01":]; return R, pd.Series(10.0, R.columns), 365
    if name == "commod":   # FRED spot WTI, Brent, Henry Hub gas + CFD gold/silver (spot proxies, see notes)
        m = P["macro"]; cf = P["cfd"].copy(); cf.index = cf.index.tz_localize(None)
        px_ = pd.concat([m["DCOILWTICO"].where(m["DCOILWTICO"] > 0).rename("WTI"), m["DCOILBRENTEU"].rename("BRENT"), m["DHHNGSP"].rename("HHGAS"),
                         cf["GOLD"].rename("GOLD"), cf["SILVER"].rename("SILVER")], axis=1)
        R = _rets(px_); R = R[R.index.dayofweek < 5].clip(-0.25, 0.25).loc["1997-01-08":]
        return R, pd.Series({"WTI": 4.0, "BRENT": 4.0, "HHGAS": 8.0, "GOLD": 2.0, "SILVER": 3.0}), 252
    if name.startswith("pairs_"):   # dollar-neutral spreads: long A / short B, cost = both legs
        base = {"pairs_cfd": ("cfd", [("NQ", "SPX"), ("SPX", "RUT"), ("DJI", "SPX"), ("GOLD", "SILVER"), ("NQ", "RUT"), ("GOLD", "WTI")]),
                "pairs_crypto": ("crypto", [("ETH", "BTC"), ("SOL", "ETH"), ("BNB", "BTC"), ("LTC", "BTC"), ("XRP", "BTC"), ("ADA", "ETH"), ("DOGE", "BTC"), ("LINK", "ETH")]),
                "pairs_macro": ("macro_long", [("UST10Y", "UST2Y"), ("UST30Y", "UST5Y"), ("AL", "NZ"), ("EU", "SZ"), ("CA", "AL"), ("NO", "SD"), ("UK", "EU"), ("JP", "SZ")])}[name]
        R0, c0, a = _universe(base[0])
        R = pd.DataFrame({f"{x}-{y}": R0[x] - R0[y] for x, y in base[1] if x in R0 and y in R0}).dropna(how="all")
        c = pd.Series({f"{x}-{y}": c0[x] + c0[y] for x, y in base[1] if x in R0 and y in R0})
        return R, c, a
    raise ValueError(name)

FX_RATE = {"EU": "EZ", "UK": "GB", "AL": "AU", "NZ": "NZ", "JP": "JP", "CA": "CA", "SZ": "CH", "SD": "SE", "NO": "NO", "MX": "MX", "KO": "KR", "SF": "ZA"}
def fx_rate_diff():
    """foreign minus US 3-month interbank rate (% p.a.), daily, published with a one-month lag."""
    from data import _fred
    us = _fred("IR3TIB01USM156N"); out = {}
    for c, k in FX_RATE.items():
        try: f = _fred(f"IR3TIB01{k}M156N")
        except Exception: continue
        d = (f - us).dropna(); d.index = d.index + pd.offsets.MonthEnd(1) + pd.Timedelta(days=1)   # month m value usable from start of m+2
        out[c] = d
    D = pd.DataFrame(out); return D.resample("1D").ffill()
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
    enough = tstats["trades"] >= 30 or (alpha["alpha_t"] >= 3 and len(pnl.loc[t2:]) >= 500)   # continuous-exposure books: judged on alpha, not trade count
    passed = m_va["sharpe"] > 0 and m_te["sharpe"] > 0.3 and m_wf["sharpe"] > 0.3 and enough and alpha["alpha_t"] >= 1.5 and beats
    rec = dict(id=sid, name=name, universe=universe_name, mechanism=mechanism, notes=notes, params=prm, trials=len(combos),
               period=f"{R.index[0].date()}..{R.index[-1].date()}", split=f"train..{t1.date()} | val..{t2.date()} | test..{R.index[-1].date()}",
               train=m_tr, val=m_va, test=m_te, walkforward=m_wf, test_trades=tstats, grid_positive_share=robust,
               avg_daily_cost_bps=round(float(tc.mean() * 1e4), 2), lev_for_300=k300, maxdd_at_300=None if dd300 is None else round(dd300, 3),
               max_corr=round(corr_max, 2), max_corr_with=corr_id, **alpha, passed=bool(passed))
    save_record(rec)
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
    beta_b, bench_te = 0.0, None
    if set(S.columns) & {"MKT", "SB"}:     # market-timing stream: must add alpha over always-long market (same vol target)
        m = P["ff3"]["Mkt-RF"]; bS = pd.DataFrame({"MKT": m.reindex(S.index).fillna(0)})
        bw = size(bS.notna().astype(float), bS, ann, cap=3.0); bp, _, _ = run(bw, bS, pd.Series(0.0, bS.columns), ann)
        bench_te = metrics(bp.loc[t2:].iloc[1:], ann)["sharpe"]; bb = bp.reindex(wfp.index).fillna(0)
        X = np.vstack([np.ones(len(wfp)), bb.values]).T; coef, *_ = np.linalg.lstsq(X, wfp.fillna(0).values, rcond=None); res_ = wfp.fillna(0).values - X @ coef
        a_t = float(coef[0] / (res_.std() / np.sqrt(len(res_)))) if res_.std() > 0 else 0; beta_b = float(coef[1])
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
    if bench_te is not None: passed = passed and a_t >= 2 and m_te["sharpe"] > bench_te
    rec = dict(id=sid, name=name, universe=uname, mechanism=mechanism, notes=notes, params=prm, trials=len(combos), period=f"{idx[0].date()}..{idx[-1].date()}",
               split=f"train..{t1.date()} | val..{t2.date()} | test..{idx[-1].date()}", train=m_tr, val=m_va, test=m_te, walkforward=m_wf, test_trades=tst,
               grid_positive_share=round(float(np.mean([s > 0 for s in tr])), 2), avg_daily_cost_bps=None, lev_for_300=k300, maxdd_at_300=None if dd300 is None else round(dd300, 3),
               max_corr=round(corr_max, 2), max_corr_with=corr_id, alpha_ann=round(float(wfp.mean() * ann), 4), alpha_t=round(a_t, 2), beta=round(beta_b, 2), bench_test_sharpe=bench_te, passed=bool(passed))
    save_record(rec)
    return rec
