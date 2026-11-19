# Round 3 (1-minute data): lead-lag (5), fix/auction reversal (8 + 2 month-end), MOC-window continuation (2). Pre-registered.
import pickle, numpy as np, pandas as pd
SP = "."
def load1m(path):
    d = pd.read_csv(path, index_col=0); d.index = pd.to_datetime(d.index, utc=True)
    d.columns = ["o", "h", "l", "c", "v"][: len(d.columns)]; return d[~d.index.duplicated()].sort_index()
class M1:
    def __init__(s, name, path, cost):
        s.name, s.cost = name, cost; d = load1m(path); s.t = d.index; s.o, s.h, s.l, s.c = (d[k].to_numpy(float) for k in "ohlc")
        lr = np.diff(np.log(s.c), prepend=np.log(s.c[0])); lr[np.abs(lr) > 0.05] = 0
        s.sig = pd.Series(lr).rolling(20 * 1000, min_periods=5000).std().shift(1).to_numpy()   # ~20 trading days of 1m returns
    def at(s, ts, tol="3min"):
        k = s.t.searchsorted(ts)
        return k if k < len(s.t) and s.t[k] - ts <= pd.Timedelta(tol) else None
def trade(m, ts_in, ts_out, d, k=2.5):
    i, j = m.at(ts_in), m.at(ts_out)
    if i is None or j is None or j <= i or not np.isfinite(m.sig[i]): return None
    e = m.o[i]; sd = k * m.sig[i] * np.sqrt(j - i) * e
    if not sd > 0: return None
    stop = e - d * sd; lo = m.l[i:j].min() if d > 0 else m.h[i:j].max()
    if (d > 0 and lo <= stop) or (d < 0 and lo >= stop):
        kk = i + (np.argmax(m.l[i:j] <= stop) if d > 0 else np.argmax(m.h[i:j] >= stop)); x = stop; ts_out = m.t[kk]
    else: x = m.o[j]
    return (m.t[i], ts_out, d * (x - e) / sd - m.cost * e / sd)
def days_of(m, tz): return sorted(set(m.t.tz_convert(tz).date))
def h_fix_reversal(m, tz, hh, mm, pre_min, post_min, big, month_end=False):
    out = []; mags = []
    for dte in days_of(m, tz):
        if pd.Timestamp(dte).weekday() >= 5: continue
        if month_end:
            nb = pd.bdate_range(dte, periods=3)
            if not (nb[1].month != dte.month or nb[2].month != dte.month): continue
        tfix = pd.Timestamp(f"{dte} {hh:02d}:{mm:02d}", tz=tz).tz_convert("UTC"); tpre = tfix - pd.Timedelta(minutes=pre_min)
        a, b = m.at(tpre), m.at(tfix)
        if a is None or b is None or not np.isfinite(m.sig[b]): continue
        pre = m.o[b] / m.o[a] - 1; z = pre / (m.sig[b] * np.sqrt(max(b - a, 1))); mags.append(abs(z))
        if pre == 0 or (big and abs(z) < 1.0): continue
        tr = trade(m, tfix, tfix + pd.Timedelta(minutes=post_min), -int(np.sign(pre)))
        if tr: out.append(tr)
    return out
def h_moc(m):
    out = []
    for dte in days_of(m, "America/New_York"):
        if pd.Timestamp(dte).weekday() >= 5: continue
        t15 = pd.Timestamp(f"{dte} 15:00", tz="America/New_York").tz_convert("UTC"); t1550 = t15 + pd.Timedelta(minutes=50); t16 = t15 + pd.Timedelta(minutes=60)
        a, b = m.at(t15), m.at(t1550)
        if a is None or b is None: continue
        s = np.sign(m.o[b] / m.o[a] - 1)
        if s:
            tr = trade(m, t1550, t16, int(s))
            if tr: out.append(tr)
    return out
def five(m):
    s = pd.Series(m.c, m.t).resample("5min").last().dropna(); return s
def h_leadlag(L, F, z=2.5, hold=15, slow=0.3):
    sl, sf = five(L), five(F); df = pd.concat([np.log(sl).diff(), np.log(sf).diff()], axis=1, keys=["l", "f"]).dropna()
    df = df[(df.l.abs() < 0.03) & (df.f.abs() < 0.03)]
    sdl = df.l.rolling(2000, min_periods=500).std().shift(1)
    beta = ((df.l * df.f).rolling(2000, min_periods=500).sum() / (df.l ** 2).rolling(2000, min_periods=500).sum()).shift(1)
    zz = df.l / sdl; exp = beta * df.l
    sel = df.index[(zz.abs() > z) & (beta.abs() > 0.2) & ((df.f / exp) < slow)]
    out, last = [], None
    for t in sel:
        if last is not None and t < last: continue
        tin = t + pd.Timedelta(minutes=5); d = int(np.sign(exp[t]))
        tr = trade(F, tin, tin + pd.Timedelta(minutes=hold), d)
        if tr: out.append(tr); last = tr[1]
    return out
def stats(trs, split):
    trs = [x for x in trs if x]
    if len(trs) < 20: return dict(n=len(trs))
    r = np.array([x[2] for x in trs]); t = pd.DatetimeIndex([x[0] for x in trs]); a, b = r[t < split], r[t >= split]
    f = lambda v: (len(v), v.mean(), v.mean() / v.std(ddof=1) * np.sqrt(len(v)) if len(v) > 2 else np.nan)
    na, ma, ta = f(a); nb, mb, tb = f(b); nt, mt, tt = f(r); yrs = max((t[-1] - t[0]).days / 365.25, 0.5)
    return dict(n=nt, per_yr=round(nt / yrs), meanR=round(mt, 3), t_all=round(tt, 2), n_tr=na, meanR_tr=round(ma, 3), t_tr=round(ta, 2),
                n_te=nb, meanR_te=round(mb, 3), t_te=round(tb, 2), win=round((r > 0).mean() * 100), R_yr=round(r.sum() / yrs, 1))
if __name__ == "__main__":
    M = {"XAU": M1("XAU", "fut1m/XAUUSD_1m.csv", 0.00012), "SPX": M1("SPX", "fut1m/USA500IDXUSD_1m.csv", 0.00015), "NQ": M1("NQ", "fut1m/USATECHIDXUSD_1m.csv", 0.00015),
         "EUR": M1("EUR", "fx1m/EURUSD_1m.csv", 0.00008), "DAX": M1("DAX", "eu1m/DEUIDXEUR_1m.csv", 0.00015)}
    print("loaded", flush=True)
    S = pd.Timestamp("2023-01-01", tz="UTC"); SD = pd.Timestamp("2024-01-01", tz="UTC"); HYP = []
    for a, b in (("EUR", "XAU"), ("XAU", "EUR"), ("NQ", "SPX"), ("SPX", "NQ"), ("NQ", "DAX")):
        HYP.append(("R3-1 lead-lag", f"{a}->{b}", "leader 5m z>2.5, follower lagging, hold 15m", lambda a=a, b=b: h_leadlag(M[a], M[b]), SD if "DAX" in b else S))
    for nm, mk, tz, hh, mm_, pre, post, sp in (("gold AM fix", "XAU", "Europe/London", 10, 30, 30, 45, S), ("gold PM fix", "XAU", "Europe/London", 15, 0, 30, 45, S),
                                               ("EURUSD WMR 4pm fix", "EUR", "Europe/London", 16, 0, 30, 30, S), ("DAX Xetra close", "DAX", "Europe/Berlin", 17, 30, 30, 60, SD)):
        for big in (False, True):
            HYP.append(("R3-2 fix/auction reversal", mk, f"{nm}: fade {pre}m pre-move for {post}m{' (|z|>1)' if big else ''}",
                        lambda mk=mk, tz=tz, hh=hh, mm_=mm_, pre=pre, post=post, big=big: h_fix_reversal(M[mk], tz, hh, mm_, pre, post, big), sp))
    for big in (False, True):
        HYP.append(("R3-2 fix reversal month-end", "EUR", f"WMR 4pm fix, last 2 business days{' (|z|>1)' if big else ''}", lambda big=big: h_fix_reversal(M["EUR"], "Europe/London", 16, 0, 30, 30, big, True), S))
    for mk in ("SPX", "NQ"): HYP.append(("R3-3 MOC-window continuation", mk, "15:00->15:50 ET sign, hold 15:50->16:00", lambda mk=mk: h_moc(M[mk]), S))
    rows, TR = [], {}
    for hyp, mk, var, fn, sp in HYP:
        trs = [x for x in fn() if x]; TR[(hyp, mk, var)] = trs; rows.append(dict(hyp=hyp, market=mk, variant=var, **stats(trs, sp))); print(rows[-1], flush=True)
    R = pd.DataFrame(rows); R.to_csv("newlab3_results.csv", index=False); pickle.dump(TR, open("newlab3_trades.pkl", "wb"))
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30); print(R.drop(columns=["hyp"]).to_string())
