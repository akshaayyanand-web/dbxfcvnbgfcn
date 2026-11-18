"""Stream-type new mechanisms: STRAT-1011 Bayesian online change-point gated variance selling, STRAT-1017 Thompson-sampling bandit over strategy
streams (portfolio-level RL), STRAT-1029 rebalancing premium (volatility harvesting)."""
import os, pickle, numpy as np, pandas as pd
from scipy.special import gammaln
from vol import UND, varswap
from engine import P, _rets
from data import SCR
def bocpd_cp_prob(r, hazard=1 / 250, Rmax=300, a0=1.0, b0=1e-4):
    """Adams-MacKay BOCPD for a zero-mean Gaussian with unknown variance (inverse-gamma prior). Returns P(run length < 10) per day."""
    n = len(r); out = np.zeros(n); logR = np.array([0.0]); A = np.array([a0]); B = np.array([b0])
    for t in range(n):
        x = r[t]
        if np.isnan(x): out[t] = out[t - 1] if t else 0; continue
        nu = 2 * A; sc2 = B / A
        lp = gammaln((nu + 1) / 2) - gammaln(nu / 2) - 0.5 * np.log(np.pi * nu * sc2) - (nu + 1) / 2 * np.log1p(x * x / (nu * sc2))
        g = logR + lp + np.log(1 - hazard); cp = np.logaddexp.reduce(logR + lp + np.log(hazard))
        logR = np.r_[cp, g]; logR -= np.logaddexp.reduce(logR)
        A = np.r_[a0, A + 0.5]; B = np.r_[b0, B + 0.5 * x * x]
        if len(logR) > Rmax: logR, A, B = logR[:Rmax], A[:Rmax], B[:Rmax]; logR -= np.logaddexp.reduce(logR)
        out[t] = np.exp(logR[:10]).sum()
    return out
J = UND["SPX"]; CP = pd.Series(bocpd_cp_prob(J.r.values), index=J.index)
def gated(p):
    flag = (CP > p["th"]).astype(float).rolling(p["quiet"], min_periods=1).max()
    return pd.DataFrame({"SPX": varswap("SPX", lambda j, r: (flag.reindex(j.index).fillna(1).values[r] == 0).astype(int))})
def bandit(p):
    D = f"{SCR}/rdata/pnl"
    arms = ["STRAT-0561@F57", "STRAT-0618@F62", "STRAT-0036@macro_long", "STRAT-0203@energy", "STRAT-0002@ind49", "STRAT-0233@energy", "STRAT-0239@energy", "STRAT-0608@F61", "STRAT-0359@credit", "STRAT-0256@fx_tr", "STRAT-0195@commod"]
    S = {}
    for a in arms:
        s = pickle.load(open(f"{D}/{a}.pkl", "rb")); s.index = pd.to_datetime(s.index); s.index = s.index.tz_localize(None) if s.index.tz is not None else s.index
        s = s.groupby(s.index.normalize()).sum(); S[a] = s / (s.std() * np.sqrt(252)) * 0.10
    X = pd.DataFrame(S).loc["1995":].fillna(0); Wk = X.resample("W-FRI").sum(); rng = np.random.default_rng(0); wts = pd.DataFrame(0.0, index=Wk.index, columns=Wk.columns)
    for i in range(52, len(Wk)):
        past = Wk.iloc[:i]; live = past.columns[(past != 0).sum() > 26]
        if len(live) < 3: continue
        mu = past[live].mean(); se = past[live].std() / np.sqrt((past[live] != 0).sum()); draw = rng.normal(mu, se)
        top = live[np.argsort(-draw)[:p["k"]]]; wts.loc[wts.index[i], top] = 1 / p["k"]
    Wd = wts.reindex(X.index, method="ffill").shift(1).fillna(0); return pd.DataFrame({"BANDIT": (Wd * X).sum(1)})
def rebal(p):
    m = P["ff3"]["Mkt-RF"] + P["ff3"]["RF"]; b = P["bonds_ret"]["UST10Y"]; o = _rets(P["macro"]["DCOILWTICO"].where(P["macro"]["DCOILWTICO"] > 0)).clip(-0.3, 0.3)
    R = pd.concat([m, b, o], axis=1, keys=["MKT", "UST10Y", "WTI"]).dropna().loc["1987":]
    vol = R.rolling(252).std().shift(1); w0 = (1 / vol).div((1 / vol).sum(1), axis=0)
    reb = (w0.shift(1) * R).sum(1)
    yrs = R.index.year; bh = pd.Series(0.0, index=R.index); turn = pd.Series(0.0, index=R.index)
    for y in sorted(set(yrs)):
        ix = R.index[yrs == y]
        if len(ix) < 2 or w0.loc[ix[0]].isna().any(): continue
        g = (1 + R.loc[ix]).cumprod(); val = g.mul(w0.loc[ix[0]], axis=1); tot = val.sum(1); bh.loc[ix] = tot.pct_change().fillna(tot.iloc[0] - 1)
        drift = val.div(tot, axis=0); turn.loc[ix] = (drift.shift(1) - w0.loc[ix].shift(1)).abs().sum(1).fillna(0)
    return pd.DataFrame({"REBAL": (reb - bh - turn * p["c"] / 1e4).loc["1988":]})
F1011 = [("STRAT-1011", "Bayesian change-point gated variance selling", "short one-month S&P variance only when the Bayesian online change-point model has not flagged a variance regime break (P(run<10) > th) in the last `quiet` days", gated, {"th": [0.3, 0.5], "quiet": [21, 63]})]
F1017 = [("STRAT-1017", "Reinforcement learning: Thompson-sampling strategy allocator", "each week sample every strategy stream's posterior mean (past weeks only) and hold the k best samples (multi-armed bandit over the independent edges)", bandit, {"k": [3, 5]})]
F1029 = [("STRAT-1029", "Portfolio-level arbitrage: rebalancing premium", "daily-rebalanced inverse-vol stocks/10y/oil portfolio minus the same weights held buy-and-hold for the year (volatility-harvesting return), net of rebalancing cost", rebal, {"c": [2, 5]})]
FAMS = {"F1011": ("Bayesian change-point gated variance selling", F1011), "F1017": ("Thompson-sampling strategy allocator", F1017), "F1029": ("Rebalancing premium", F1029)}
