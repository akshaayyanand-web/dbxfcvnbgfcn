# Reverse-engineer the losers: conditions at entry for every trade of the 8 EAs.
# Bad conditions are chosen on 2020-2022 trades ONLY, then judged on 2023-2026 trades (unseen), then in the prop test.
import sys, numpy as np, pandas as pd
SP = sys.argv[1]
import portfolio_prop as P
REC = []; _orig = P.trade_series
def _rec(trades, cost, h1, idx_):
    REC.append((list(trades), cost, h1)); return _orig(trades, cost, h1, idx_)
P.trade_series = _rec
exec(open(SP + "/speed8.py").read().split("V2 = [")[0])
P.trade_series = _orig
names0 = names[:len(names) - 2]; TR = {k: REC[i] for i, k in enumerate(names0)}
spx = load_csv(SP + "/fut/USA500IDXUSD.csv")
MKT = {"btc": btc, "gdip": gold, "gasia": gold, "gmom": gold, "nqmom": nq, "orb15": nq, "nqdip": nq, "spxdip": spx}
USED = [k for k in names if W[names.index(k)] > 0]

# dip grids with entry times + an "allowed" mask
src = open(SP + "/dipgrid_exits.py").read().split("GRID =")[0]
src = src.replace("def basket3(o, h, l, c, z, atr, ema, cost, zth, N, stopk, exit_, cut, hold, risk=0.02, Sp=1.0):",
                  "def basket3(o, h, l, c, z, atr, ema, cost, zth, N, stopk, exit_, cut, hold, risk=0.02, Sp=1.0, allow=None):")
src = src.replace("if np.isnan(z[i - 1]) or np.isnan(atr[i - 1]) or z[i - 1] > -zth or c[i - 1] <= ema[i - 1]: continue",
                  "if np.isnan(z[i - 1]) or np.isnan(atr[i - 1]) or z[i - 1] > -zth or c[i - 1] <= ema[i - 1] or (allow is not None and not allow[i]): continue")
src = src.replace('res.append(P["real"] + v)', 'res.append((P["t"], (P["real"] + v) / risk))').replace('res.append(P["real"] + P["u"])', 'res.append((P["t"], (P["real"] + P["u"]) / risk))')
KD = {}; exec(src, KD)
def grid_run(df, allow=None):
    z, atr, *_ = KD["K"]["indicators"](df, 20); ema = df.c.ewm(span=200).mean().to_numpy(); o, h, l, c = (df[k].to_numpy() for k in "ohlc")
    r, lo, res = KD["basket3"](o, h, l, c, z, atr, ema, 0.00012 if df is nq else 0.0001, 2.0, 3, 1.0, "trail", 0, 120, allow=allow)
    s = pd.DataFrame({"r": r / 2, "lo": lo / 2}, index=df.index).reindex(idx).fillna(0.0)
    return s.r.to_numpy(), s.lo.to_numpy(), [(df.index[int(t)], x) for t, x in res]

# features known at the signal bar (hourly, no look-ahead)
def feats(df):
    c = df.c; tr = pd.concat([df.h - df.l, (df.h - c.shift()).abs(), (df.l - c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 24).mean() / c
    f = pd.DataFrame(index=df.index)
    f["vol_regime"] = atr / atr.rolling(24 * 250, min_periods=500).median()
    f["trend_200d"] = c / c.rolling(24 * 200, min_periods=500).mean() - 1
    f["ret_24h"] = c / c.shift(24) - 1
    f["ret_5d"] = c / c.shift(120) - 1
    f["off_20d_high"] = c / c.rolling(480).max() - 1
    loc = df.index.tz_convert("America/New_York"); f["hour_ny"] = loc.hour; f["weekday"] = loc.weekday
    return f
F = {id(df): feats(df) for df in (btc, gold, nq, spx)}
CROSS = pd.DataFrame({"btc_vol_regime": F[id(btc)].vol_regime, "nq_vol_regime": F[id(nq)].vol_regime.reindex(btc.index, method="ffill"),
                      "nq_ret_5d": F[id(nq)].ret_5d.reindex(btc.index, method="ffill")})

def trade_table(k):
    if k in ("nqdip", "spxdip"):
        _, _, res = grid_run(nq if k == "nqdip" else spx); rows = [(t, x) for t, x in res]
    else:
        trades, cost, h1 = TR[k]; rows = [(et, (px - e) / (e - st) - cost * e / abs(e - st)) for et, xt, e, st, px in trades]
    df = MKT[k]; f = F[id(df)]; T = pd.DataFrame(rows, columns=["t", "R"])
    tt = pd.DatetimeIndex(T.t) - pd.Timedelta(hours=1); pos = np.clip(f.index.searchsorted(tt, side="right") - 1, 0, len(f) - 1)   # last bar fully closed before entry
    X = f.iloc[pos].reset_index(drop=True)
    cp = np.clip(CROSS.index.searchsorted(tt, side="right") - 1, 0, len(CROSS) - 1); X = pd.concat([X, CROSS.iloc[cp].reset_index(drop=True)], axis=1)
    return pd.concat([T, X], axis=1)

FEATS = ["vol_regime", "trend_200d", "ret_24h", "ret_5d", "off_20d_high", "btc_vol_regime", "nq_vol_regime", "nq_ret_5d"]
rules, report = {}, []
for k in USED:
    T = trade_table(k); A = T[T.t < split]; B = T[T.t >= split]
    print(f"\n=== {k}: {len(A)} trades 2020-22 (avg {A.R.mean():+.3f}R), {len(B)} trades 2023-26 (avg {B.R.mean():+.3f}R)")
    best = None
    for fe in FEATS + ["weekday", "hour_ny"]:
        if fe in ("weekday", "hour_ny"):
            groups = [(f"{fe}={v}", (lambda v: lambda X: X[fe] == v)(v)) for v in sorted(A[fe].dropna().unique())]
        else:
            q = A[fe].quantile([0.2, 0.8]).to_numpy()
            groups = [(f"{fe} < {q[0]:.4g} (lowest 20%)", (lambda q: lambda X: X[fe] < q)(q[0])), (f"{fe} > {q[1]:.4g} (highest 20%)", (lambda q: lambda X: X[fe] > q)(q[1]))]
        for lab, fn in groups:
            mA = fn(A); n = mA.sum()
            if n < 20: continue
            mu, sd = A.R[mA].mean(), A.R[mA].std(ddof=1); t = mu / (sd / np.sqrt(n)) if sd > 0 else 0
            if mu < -0.1 and t < -1.5:                      # bad bucket, judged on 2020-22 only
                mB = fn(B); gainA = -A.R[mA].sum(); gainB = -B.R[mB].sum()
                report.append(dict(strategy=k, block=lab, nA=int(n), avgR_A=mu, t_A=t, nB=int(mB.sum()), avgR_B=B.R[mB].mean() if mB.sum() else np.nan, R_saved_A=gainA, R_saved_B=gainB))
                if best is None or t < best[2]: best = (lab, fn, t, fe)
    if best: rules[k] = best
rep = pd.DataFrame(report); pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
print("\nBAD CONDITIONS found on 2020-22 (avg R < -0.1, t < -1.5), and what blocking them did on unseen 2023-26 trades:")
print(rep.round(3).to_string(index=False) if len(rep) else "none")
rep.to_pickle(SP + "/losers_report.pkl")

# portfolio test: block the strongest bad condition per strategy (only if it ALSO helped 2023-26 is NOT required: honest out-of-sample)
def filtered_series(k, fn):
    T = trade_table(k); bad = set(T.t[fn(T)])
    if k in ("nqdip", "spxdip"):
        df = nq if k == "nqdip" else spx; allow = ~df.index.isin(list(bad))   # entry bar index == basket start
        r, lo, _ = grid_run(df, allow); return r, lo
    trades, cost, h1 = TR[k]; keep = [t for t in trades if t[0] not in bad]
    return P.trade_series(keep, cost, h1, idx)
R_f, LO_f = R.copy(), LO.copy()
for k, (lab, fn, t, fe) in rules.items():
    i = names.index(k); R_f[i], LO_f[i] = filtered_series(k, fn); print(f"rule for {k}: block {lab}")
def run3(w, Rm, LOm, h0, h1, target, halt=0.8, maxl=0.10, daily=0.05):
    r = (Rm[:, h0:h1] * w[:, None]).sum(0); lo = (LOm[:, h0:h1] * w[:, None]).sum(0); eq = 1.0; day = None; hd = None
    for i in range(len(r)):
        dd_ = days[h0 + i]
        if dd_ != day: day = dd_; dopen = eq
        if hd == dd_: continue
        if eq * (1 + lo[i]) <= 1 - maxl or eq * (1 + lo[i]) <= dopen * (1 - daily): return "fail", i, eq - 1
        eq *= 1 + r[i]
        if target and eq >= 1 + target: return "pass", i, eq - 1
        if 1 - eq / dopen >= halt * daily: hd = dd_
        if eq <= 1 - 0.8 * maxl: return "stopped", i, eq - 1
    return "open", len(r), eq - 1
wst = pd.date_range("2020-04-01", "2025-10-01", freq="MS", tz="UTC")
for lab, Rm, LOm in (("8 EAs as now", R, LO), ("8 EAs with bad-condition blocks", R_f, LO_f)):
    res = []
    for s_ in est:
        h0 = idx.searchsorted(s_); a, i1, _ = run3(W, Rm, LOm, h0, len(idx), 0.10)
        if a != "pass": res.append((s_, a, None)); continue
        b, i2, _ = run3(W, Rm, LOm, h0 + i1 + 1, len(idx), 0.05); res.append((s_, b, (i1 + i2) / 24 if b == "pass" else None))
    yy = [(s_, *run3(W, Rm, LOm, idx.searchsorted(s_), idx.searchsorted(s_ + pd.DateOffset(years=1)), None)) for s_ in wst]
    eqc = np.cumprod(1 + (Rm * W[:, None]).sum(0)); mdd = 100 * np.max(1 - eqc / np.maximum.accumulate(eqc))
    for p, sel in (("2020-22 (rules picked here)", lambda s: s < split), ("2023-25 (unseen)", lambda s: s >= split)):
        rr = [x for x in res if sel(x[0])]; t = [x[2] for x in rr if x[2] is not None]; y = [v for v in yy if sel(v[0])]
        print(f"{lab:<34} {p:<28} pass {100*np.mean([x[1]=='pass' for x in rr]):3.0f}% breach {100*np.mean([x[1]=='fail' for x in rr]):3.0f}% "
              f"median {np.median(t):4.0f}d | funded median {100*np.median([v[3] for v in y]):+5.1f}% breaches {sum(v[1]=='fail' for v in y)} | maxDD {mdd:.1f}%")
