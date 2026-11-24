# G2: intraday machine learning, strict walk-forward. Hourly NQ, SPX, DAX, XAU, BTC, ETH.
# Features at bar close t only; target = sign of the next-4h log return. HistGradientBoosting retrained monthly on the previous 24 months
# (with a 1-day gap). Trade: p>T long / p<1-T short, T in {0.55, 0.60}; hold 4h, no overlap. Costs per symbol round trip.
import numpy as np, pandas as pd, warnings
from multiprocessing import Pool
from sklearn.ensemble import HistGradientBoostingClassifier
warnings.filterwarnings("ignore")
exec(open("smc.py").read().split("def run_symbol(")[0])
def duka(sym): d = pd.read_csv(f"fut/{sym}.csv", index_col=0); d.index = pd.to_datetime(d.index, utc=True); return d[["o", "h", "l", "c"]]
LOAD = {"NQ": (lambda: duka("USATECHIDXUSD"), 0.00015), "SPX": (lambda: duka("USA500IDXUSD"), 0.00015), "XAU": (lambda: duka("XAUUSD"), 0.00012),
        "DAX": (lambda: rs(m1_csv("eu1m/DEUIDXEUR_1m.csv"), "1h"), 0.00015), "BTC": (lambda: rs(crypto("BTC"), "1h"), 0.0006), "ETH": (lambda: rs(crypto("ETH"), "1h"), 0.001)}
H = 4
def cboe(n): v = pd.read_csv(f"rdata/cboe/{n}.csv"); v.index = pd.DatetimeIndex(pd.to_datetime(v.DATE, format="%m/%d/%Y")).tz_localize("UTC") + pd.Timedelta(hours=21); return v.CLOSE
def feats(b, cross):
    c = np.log(b.c); r1 = c.diff(); f = pd.DataFrame(index=b.index)
    for k in (1, 2, 4, 8, 24, 72): f[f"r{k}"] = c - c.shift(k)
    v24 = r1.rolling(24).std(); f["vol24"] = v24; f["volratio"] = v24 / r1.rolling(240).std()
    for k in (24, 120): f[f"z{k}"] = (c - c.rolling(k).mean()) / (v24 * np.sqrt(k))
    f["dhi"] = (np.log(b.h.rolling(24).max()) - c) / v24; f["dlo"] = (c - np.log(b.l.rolling(24).min())) / v24
    f["hour"] = b.index.hour; f["dow"] = b.index.dayofweek
    for nm, s in cross.items():
        s = s.reindex(b.index, method="ffill"); f[f"{nm}_r1"] = s - s.shift(1); f[f"{nm}_r4"] = s - s.shift(4)
    vix = cboe("VIX"); ts = vix / cboe("VIX3M")
    f["vix"] = vix.reindex(b.index, method="ffill"); f["vixts"] = ts.reindex(b.index, method="ffill")
    y = c.shift(-H) - c
    return f.replace([np.inf, -np.inf], np.nan), y
def run(sym):
    b = LOAD[sym][0]().dropna(); cost = LOAD[sym][1]
    cross = {nm: np.log(LOAD[nm][0]().c.resample("1h").last().dropna()) for nm in ("NQ", "XAU", "BTC") if nm != sym}
    X, y = feats(b, cross); months = pd.date_range(X.index[0].normalize() + pd.DateOffset(months=25), X.index[-1], freq="MS", tz="UTC")
    P = pd.Series(np.nan, X.index)
    for m in months:
        tr = (X.index >= m - pd.DateOffset(months=24)) & (X.index < m - pd.Timedelta(days=1)); te = (X.index >= m) & (X.index < m + pd.DateOffset(months=1))
        ok = tr & X.notna().all(axis=1).to_numpy() & y.notna().to_numpy()
        if ok.sum() < 3000 or te.sum() == 0: continue
        mdl = HistGradientBoostingClassifier(max_iter=200, max_depth=3, learning_rate=0.05, min_samples_leaf=200, random_state=0).fit(X[ok].values, (y[ok] > 0).values)
        tx = te & X.notna().all(axis=1).to_numpy(); P[tx] = mdl.predict_proba(X[tx].values)[:, 1]
    out = []; yy = y.to_numpy(); pp = P.to_numpy(); T_ = X.index
    for T in (0.55, 0.60):
        k = 0
        while k < len(pp) - H:
            p = pp[k]
            if np.isfinite(p) and np.isfinite(yy[k]) and (p > T or p < 1 - T):
                d = 1 if p > T else -1; out.append((sym, T, T_[k], d * yy[k] - cost)); k += H
            else: k += 1
    print(sym, "done", len(out), "first prediction", P.first_valid_index(), flush=True); return out
if __name__ == "__main__":
    with Pool(4) as p: res = p.map(run, list(LOAD))
    D = pd.DataFrame([r for o in res for r in o], columns=["sym", "T", "t", "ret"]); D.to_pickle("mlwf_trades.pkl")
    S = pd.Timestamp("2023-01-01", tz="UTC")
    def summ(g):
        a, b_ = g[g.t < S].ret, g[g.t >= S].ret; tt = lambda v: round(v.mean() / v.std() * np.sqrt(len(v)), 2) if len(v) > 2 else np.nan
        yrs = g.groupby(g.t.dt.year).ret.sum()
        return pd.Series(dict(trades=len(g), win=round(100 * (g.ret > 0).mean()), avg_net_bp=round(1e4 * g.ret.mean(), 2), t_pre2023=tt(a), t_2023on=tt(b_), pos_years=f"{(yrs > 0).sum()}/{len(yrs)}"))
    pd.set_option("display.width", 200); print(D.groupby(["T", "sym"]).apply(summ).to_string()); print(D.groupby("T").apply(summ).to_string())
