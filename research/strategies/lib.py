"""Core signals (one per research family = the family's mechanism) and formulation wrappers (the catalogue's 10 hypothesis formulations).
All signals use data up to and including day t only; the engine applies them to day t+1 returns."""
import numpy as np, pandas as pd
from engine import P

def px(R): return (1 + R.fillna(0)).cumprod().where(R.notna().cumsum() > 0)
def sma(x, n): return x.rolling(n, min_periods=n).mean()
def hold(ev, H):
    """turn +1/-1 entry events into positions held for H bars (latest event wins)."""
    e = ev.replace(0, np.nan)
    last = e.ffill(limit=H - 1) if H > 1 else e
    return last.fillna(0)

# ---------------- family cores ----------------
def c_tsmom(R, L=126, **k):                 # F1 time-series momentum
    return np.sign(px(R) / px(R).shift(L) - 1)
def s_xsmom(R, L=252, skip=21, **k):        # F2 cross-sectional momentum score (12-1 style)
    p = px(R); return p.shift(skip) / p.shift(L) - 1
def c_breakout_hold(R, N=50, H=20, **k):    # F4 breakout continuation: N-day closing breakout, fixed holding period
    p = px(R); ev = (p > p.shift(1).rolling(N).max()).astype(int) - (p < p.shift(1).rolling(N).min()).astype(int)
    return hold(ev, H)
def c_squeeze(R, N=20, H=10, pct=0.2, **k): # F6 volatility-compression breakout
    p = px(R); v = R.rolling(N).std(); pr = v.rolling(252, min_periods=126).rank(pct=True)
    sq = (pr.shift(1) < pct)
    ev = ((p > p.shift(1).rolling(N).max()) & sq).astype(int) - ((p < p.shift(1).rolling(N).min()) & sq).astype(int)
    return hold(ev, H)
def c_pullback(R, T=200, x=1.5, H=5, **k):   # F7 trend pullback: buy dips in uptrends / sell rallies in downtrends
    p = px(R); up = p > sma(p, T); dn = p < sma(p, T)
    z = (p / p.shift(3) - 1) / (R.rolling(60).std() * np.sqrt(3))
    ev = ((z < -x) & up).astype(int) - ((z > x) & dn).astype(int)
    return hold(ev, H)
def c_exhaust(R, N=20, k=2.5, H=5, **kw):   # F8 trend exhaustion: fade stretched moves away from the N-day mean
    p = px(R); z = (p - sma(p, N)) / p.rolling(N).std()
    ev = (z < -k).astype(int) - (z > k).astype(int)
    return hold(ev, H)
def c_maregime(R, N=200, **k):              # F9 moving-average regime allocation (long/flat)
    p = px(R); return (p > sma(p, N)).astype(float).where(p.notna())
def c_donchian(R, N=55, M=20, **k):          # F10 Donchian channel trend (state machine, trailing exit)
    p = px(R); hi = p.shift(1).rolling(N).max(); lo = p.shift(1).rolling(N).min()
    xl = p.shift(1).rolling(M).min(); xs = p.shift(1).rolling(M).max()
    L = pd.DataFrame(np.where(p > hi, 1.0, np.where(p < xl, 0.0, np.nan)), index=p.index, columns=p.columns).ffill().fillna(0)
    S = pd.DataFrame(np.where(p < lo, -1.0, np.where(p > xs, 0.0, np.nan)), index=p.index, columns=p.columns).ffill().fillna(0)
    return (L + S).clip(-1, 1)

# ---------------- formulation wrappers ----------------
def nfp_mask(idx, H):
    d = pd.Series(((idx.dayofweek == 4) & (idx.day <= 7)).astype(int), index=idx)   # first Friday = US payrolls day (approx.)
    return (d.replace(0, np.nan).ffill(limit=H - 1) if H > 1 else d.replace(0, np.nan)).fillna(0).astype(bool)
def w_event(sig, H): return sig.mul(nfp_mask(sig.index, H), axis=0)
def w_xs(score, q=0.3, weekly=True):
    r = score.rank(axis=1, pct=True); n = score.notna().sum(1)
    s = (r >= 1 - q).astype(float) - (r <= q).astype(float); s = s.where(score.notna()).where(n >= 4, 0)
    if weekly: s = s.loc[s.index.dayofweek == 4].reindex(s.index).ffill()
    return s
def leader_of(R):
    for c in ("BTC", "SPX", "NASDAQ", "Other"):
        if c in R.columns: return c
    return R.columns[0]
def w_leadlag(sig, R):
    ld = leader_of(R); s = pd.DataFrame({c: sig[ld] for c in R.columns}, index=R.index).where(R.notna())
    s[ld] = 0; return s
def regime(R, kind):
    ew = R.mean(1); idx = px(ew.to_frame("m"))["m"]
    vol = ew.rolling(21).std(); pr = vol.rolling(252, min_periods=126).rank(pct=True)
    return {"calm": pr < 0.5, "turbulent": pr >= 0.5, "uptrend": idx > sma(idx, 200), "downtrend": idx < sma(idx, 200)}[kind]
def w_regime(sig, R, kind): return sig.mul(regime(R, kind).astype(float), axis=0)
def w_term(sig, side):
    sl = P["macro"]["T10Y3M"]; sl.index = pd.to_datetime(sl.index)
    idx = sig.index.tz_localize(None) if sig.index.tz is not None else sig.index
    g = sl.reindex(idx, method="ffill").shift(1)
    m = (g > 0) if side == "steep" else (g <= 0)
    return sig.mul(m.values.astype(float), axis=0)
def w_flow(sig, R, uname, L=10):
    if uname == "crypto":
        tb = P["crypto_tb"].reindex(R.index)[R.columns].rolling(L).mean()
        conf_l, conf_s = tb > 0.505, tb < 0.495
    else:
        v = P["crypto_v"] if uname == "crypto" else None
        raise ValueError("flow formulation needs crypto taker-flow data")
    return sig.where(((sig > 0) & conf_l) | ((sig < 0) & conf_s), 0)
def w_volgate(sig, R, side):
    v = R.rolling(20).std(); med = v.rolling(252, min_periods=126).median()
    return sig.where((v < med) if side == "calm" else (v >= med), 0)
def w_exec(sig, buf=0.0):
    s = sig.loc[sig.index.dayofweek == 4].reindex(sig.index).ffill()      # weekly decisions (Friday close) = fewer trades
    return s
