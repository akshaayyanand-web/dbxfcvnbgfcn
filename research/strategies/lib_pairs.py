"""Pairs / cointegration / basket stat-arb machinery. Pairs are formed on a trailing window only and traded in the following window."""
import numpy as np, pandas as pd, warnings
from statsmodels.tsa.stattools import coint
from strategies.lib import px
warnings.filterwarnings("ignore")

def _windows(n, L, T):
    s = L
    while s < n: yield s - L, s, min(s + T, n); s += T

_CACHE = {}
def eg_stat(y, x):
    """Engle-Granger statistic: Dickey-Fuller t on the OLS residual (more negative = stronger cointegration)."""
    b, c = np.polyfit(x, y, 1); e = y - b * x - c; de = np.diff(e); el = e[:-1] - e[:-1].mean()
    g = (el @ de) / (el @ el); res = de - g * el; se = np.sqrt((res @ res) / (len(de) - 2) / (el @ el)); return g / se
def pair_select(Pw, npairs, sel):
    key = (tuple(Pw.columns), Pw.index[0], Pw.index[-1], npairs, sel)
    if key not in _CACHE: _CACHE[key] = _pair_select(Pw, npairs, sel)
    return _CACHE[key]
def _pair_select(Pw, npairs, sel):
    X = (Pw / Pw.iloc[0]).values; N = X.shape[1]
    sq = (X ** 2).sum(0); ssd = sq[:, None] + sq[None, :] - 2 * X.T @ X
    iu = np.triu_indices(N, 1); order = np.argsort(ssd[iu])
    cand = [(iu[0][k], iu[1][k]) for k in order[: (3 * npairs if sel == "coint" else npairs)]]
    if sel == "coint":
        lp = np.log(Pw.values); sc = []
        for i, j in cand:
            try: sc.append((eg_stat(lp[:, i], lp[:, j]), i, j))
            except Exception: pass
        cand = [(i, j) for _, i, j in sorted(sc)[:npairs]]
    return cand

def pair_book(R, L=252, T=126, npairs=10, k=2.0, sel="ssd", hedge="1:1", delay=0, mode="revert", gate=None, adjust_only=False, kalman=False):
    """weights DataFrame. mode: revert (enter |z|>k, exit at z sign change) | catchup (1-day divergence reversal inside formed pairs)."""
    P = px(R); idx = R.index; W = np.zeros(R.shape); cols = list(R.columns); Rv = R.fillna(0).values
    for a, s, e in _windows(len(idx), L, T):
        Pf = P.iloc[a:s]; ok = Pf.notna().all() & P.iloc[s:e].notna().all()
        Pf = Pf.loc[:, ok]
        if Pf.shape[1] < 3: continue
        names = list(Pf.columns); ci = [cols.index(c) for c in names]
        for i, j in pair_select(Pf, npairs, sel):
            I, J = ci[i], ci[j]
            if mode == "catchup":
                d = Rv[s - 1:e - 1, J] - Rv[s - 1:e - 1, I]        # yesterday's divergence (known at t)
                W[s:e, I] += np.sign(d) / (2 * npairs); W[s:e, J] -= np.sign(d) / (2 * npairs); continue
            if hedge == "ols":
                lf = np.log(Pf.iloc[:, [i, j]].values); b, c0 = np.polyfit(lf[:, 1], lf[:, 0], 1)
                res = lf[:, 0] - b * lf[:, 1] - c0; mu, sd = res.mean(), res.std()
                lt = np.log(P.iloc[s:e, [I, J]].values)
                if kalman:   # time-varying hedge ratio, random-walk beta (delta=1e-4), observation noise from formation residuals
                    beta, Pk, q, r_ = b, 1.0, 1e-4, sd ** 2; zz = []
                    for t in range(len(lt)):
                        Pk += q; yhat = beta * lt[t, 1] + c0; err = lt[t, 0] - yhat
                        zz.append(err / sd); K = Pk * lt[t, 1] / (lt[t, 1] ** 2 * Pk + r_); beta += K * err; Pk *= (1 - K * lt[t, 1])
                    z = np.array(zz)
                else: z = (lt[:, 0] - b * lt[:, 1] - c0 - mu) / sd
                wi, wj = 1 / (1 + abs(b)), -b / (1 + abs(b))
                if adjust_only:      # error-correction: trade only the leg that historically does the adjusting
                    e_ = res[:-1]; di, dj = np.diff(lf[:, 0]), np.diff(lf[:, 1])
                    ai = np.polyfit(e_, di, 1)[0]; aj = np.polyfit(e_, dj, 1)[0]
                    if abs(ai) >= abs(aj): wj = 0.0; wi = 1.0
                    else: wi = 0.0; wj = -1.0 if b > 0 else 1.0
            else:
                n0 = P.iloc[a, [I, J]].values; nf = Pf.iloc[:, [i, j]].values / n0; sp = nf[:, 0] - nf[:, 1]
                mu, sd = sp.mean(), sp.std(); nt = P.iloc[s:e, [I, J]].values / n0; z = (nt[:, 0] - nt[:, 1] - mu) / sd; wi, wj = 0.5, -0.5
            pos = 0; out = np.zeros(len(z)); pend = None
            for t in range(len(z)):
                if pend is not None and t >= pend[0]: pos = pend[1]; pend = None
                if pos == 0 and pend is None and abs(z[t]) > k: 
                    if delay: pend = (t + delay, -np.sign(z[t]))
                    else: pos = -np.sign(z[t])
                elif pos != 0 and np.sign(z[t]) == pos: pos = 0          # spread crossed back through the mean
                out[t] = pos
            out[-1] = 0
            W[s:e, I] += out * wi / npairs; W[s:e, J] += out * wj / npairs
    w = pd.DataFrame(W, index=idx, columns=cols)
    if gate is not None: w = w.mul(gate.reindex(idx).fillna(False).astype(float), axis=0)
    return w

def pca_sscore(R, L=252, k=3, est=21, ou=60, s_in=1.25, s_out=0.5, mode="sscore", vol_filter=None):
    """Avellaneda-Lee style: residuals vs top-k PCs (re-estimated every `est` days on trailing L days); OU s-score of 60-day cumulative residual."""
    idx = R.index; N = R.shape[1]; Rv = R.values; resid = np.full(R.shape, np.nan); beta1 = np.full(R.shape, np.nan); f1 = np.full(len(idx), np.nan)
    for s in range(L, len(idx), est):
        X = Rv[s - L:s]; ok = ~np.isnan(X).any(0)
        if ok.sum() < k + 3: continue
        Xo = X[:, ok]; mu = Xo.mean(0); sdv = Xo.std(0) + 1e-12; Z = (Xo - mu) / sdv
        U, S, Vt = np.linalg.svd(Z, full_matrices=False); Wf = (Vt[:k] / sdv)       # factor portfolios (eigenportfolios)
        F = Xo @ Wf.T; B = np.linalg.lstsq(np.c_[np.ones(L), F], Xo, rcond=None)[0]
        Y = Rv[s:s + est][:, ok]; Ft = np.nan_to_num(Y) @ Wf.T
        resid[s:s + est, np.where(ok)[0]] = Y - (np.c_[np.ones(len(Y)), Ft] @ B) + B[0]
        beta1[s:s + est, np.where(ok)[0]] = B[1]; f1[s:s + est] = Ft[:, 0]
    E = pd.DataFrame(resid, index=idx, columns=R.columns)
    if mode == "xs":                       # residual reversal: rank 5-day residual return
        sc = -E.rolling(5).sum(); r = sc.rank(axis=1, pct=True); w = (r >= 0.7).astype(float) - (r <= 0.3).astype(float)
        return w.where(sc.notna(), 0).sub(w.where(sc.notna(), 0).mean(1), axis=0)
    if mode == "leadlag":                  # assets that under-reacted to yesterday's market factor move catch up
        sc = pd.DataFrame(beta1 * f1[:, None], index=idx, columns=R.columns) - R
        return np.sign(sc).fillna(0).sub(np.sign(sc).fillna(0).mean(1), axis=0)
    Xc = E.fillna(0).rolling(ou).sum(); Xl = Xc.shift(1)
    mx, ml = Xc.rolling(ou).mean(), Xl.rolling(ou).mean()
    b = ((Xc - mx) * (Xl - ml)).rolling(ou).mean() / ((Xl - ml) ** 2).rolling(ou).mean()
    a = mx - b * ml; m = a / (1 - b); sig_eq = ((Xc - a - b * Xl).rolling(ou).std()) / np.sqrt((1 - b ** 2).clip(lower=1e-4))
    sscore = ((Xc - m) / sig_eq).where((b > 0) & (b < 0.97))
    if vol_filter is not None: sscore = sscore.where(vol_filter)
    S = sscore.values; pos = np.zeros_like(S); cur = np.zeros(S.shape[1])
    for t in range(len(S)):
        st = S[t]; nn = ~np.isnan(st)
        cur[nn & (cur == 0) & (st > s_in)] = -1; cur[nn & (cur == 0) & (st < -s_in)] = 1
        cur[nn & (cur == -1) & (st < s_out)] = 0; cur[nn & (cur == 1) & (st > -s_out)] = 0; cur[~nn] = 0
        pos[t] = cur
    w = pd.DataFrame(pos, index=idx, columns=R.columns)
    return w.sub(w.mean(1), axis=0) / max(1, N)
