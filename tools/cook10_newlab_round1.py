# New-mechanism lab (round "cook10"): time-of-day / flow / lead-lag effects, none of them dip, breakout or opening-range.
# Pre-registered hypotheses and variants are listed in HYP below; everything else is fixed before looking at results.
import os, glob, numpy as np, pandas as pd
SP = os.path.dirname(os.path.abspath(__file__))
NY, LDN = "America/New_York", "Europe/London"

def load_duka(sym):
    d = pd.read_csv(f"{SP}/fut/{sym}.csv", index_col=0, parse_dates=True)
    d.index = pd.to_datetime(d.index, utc=True); return d[["o", "h", "l", "c"]]

def load_1m_hourly(path):
    d = pd.read_csv(path, index_col=0, parse_dates=True); d.index = pd.to_datetime(d.index, utc=True)
    d.columns = ["o", "h", "l", "c", "v"][: len(d.columns)]
    return d.resample("1h").agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()

def load_crypto(sym):
    d = pd.read_csv(f"{SP}/kh/{sym}USDT.csv", header=None).iloc[:, :5]
    d.columns = ["t", "o", "h", "l", "c"]; t = d.t.astype("int64")
    d.index = pd.to_datetime(np.where(t > 1e14, t // 1000, t), unit="ms", utc=True)
    return d[["o", "h", "l", "c"]].astype(float).sort_index().loc[lambda x: ~x.index.duplicated()]

class Mkt:
    def __init__(self, name, bars, cost):
        self.name, self.b, self.cost = name, bars, cost
        self.o, self.h, self.l, self.c = (bars[k].to_numpy(float) for k in "ohlc")
        self.t = bars.index
        lr = np.log(self.c).diff() if False else np.diff(np.log(self.c), prepend=np.log(self.c[0]))
        self.sig = pd.Series(lr).rolling(480, min_periods=200).std().shift(1).to_numpy()   # hourly vol, past 20 days
        self.ny = self.t.tz_convert(NY); self.ldn = self.t.tz_convert(LDN)

def trade(m, i, j, d, k=2.5):
    """Enter at open of bar i, exit at open of bar j (hold bars i..j-1), direction d, stop at k*sigma*sqrt(hold).
    Returns (entry_time, exit_time, r, path) where path = list of (bar_index, r_increment, r_low) for the book."""
    if j <= i or j >= len(m.o) or not np.isfinite(m.sig[i]): return None
    e = m.o[i]; sd = k * m.sig[i] * np.sqrt(j - i) * e
    if not sd > 0: return None
    stop = e - d * sd; prev = e; path = []; cst = m.cost * e / sd
    for b in range(i, j):
        worst = m.l[b] if d > 0 else m.h[b]
        hit = (worst <= stop) if d > 0 else (worst >= stop)
        if hit:
            px = stop if ((m.o[b] > stop) if d > 0 else (m.o[b] < stop)) else m.o[b]
            path.append((b, d * (px - prev) / sd, min(0.0, d * (px - prev) / sd))); prev = px; xt = m.t[b] + pd.Timedelta("1h"); break
        path.append((b, d * (m.c[b] - prev) / sd, min(0.0, d * (worst - prev) / sd))); prev = m.c[b]
        xt = m.t[b] + pd.Timedelta("1h")
    r = d * (prev - e) / sd - cst
    path[0] = (path[0][0], path[0][1] - cst, path[0][2] - cst)
    return (m.t[i], xt, r, path)

def next_bar(m, i, cond, maxbars=30):
    for j in range(i + 1, min(i + maxbars, len(m.o))):
        if cond(j): return j
    return None

# ---------------- hypotheses ----------------
def h_gold_asia(m, exit_hr, cond):
    out = []; H = m.t.hour; WD = m.t.weekday
    for i in np.where((H == 23) & np.isin(WD, [6, 0, 1, 2, 3]))[0]:
        if cond == "after_down_us":
            k0 = next((k for k in range(i - 1, max(i - 12, 0), -1) if H[k] == 13), None)
            if k0 is None or m.c[i - 1] >= m.o[k0]: continue
        j = next_bar(m, i, lambda j: H[j] == exit_hr, 12)
        if j: out.append(trade(m, i, j, +1))
    return out

def h_session_hold(m, tzname, h_in, h_out, d, days=(0, 1, 2, 3, 4)):
    out = []; L = m.t.tz_convert(tzname); H = L.hour; WD = L.weekday
    for i in np.where((H == h_in) & np.isin(WD, days))[0]:
        j = next_bar(m, i, lambda j: H[j] == h_out, 24)
        if j: out.append(trade(m, i, j, d))
    return out

def h_index_overnight(m, h_in, cond):
    """Long from h_in ET (evening, after 17:00 ET rollover, or 01:00) to 04:00 ET (European open drift)."""
    out = []; H = m.ny.hour; WD = m.ny.weekday; D = m.ny.normalize()
    ok_days = (6, 0, 1, 2, 3) if h_in >= 17 else (0, 1, 2, 3, 4)
    for i in np.where((H == h_in) & np.isin(WD, ok_days))[0]:
        if cond == "after_down_day":
            # previous cash session: bar opening 09:00 ET to bar opening 16:00 ET, most recent before i
            k16 = next((k for k in range(i - 1, max(i - 40, 0), -1) if H[k] == 16), None)
            k09 = next((k for k in range(k16 - 1, max(k16 - 12, 0), -1) if H[k] == 9), None) if k16 else None
            if k09 is None or m.o[k16] >= m.o[k09]: continue
        j = next_bar(m, i, lambda j: H[j] == 4, 14)
        if j: out.append(trade(m, i, j, +1))
    return out

def h_intraday_mom(m, filt):
    out = []; H = m.ny.hour; WD = m.ny.weekday; sigs = []
    for i in np.where((H == 15) & (WD < 5))[0]:
        k10 = next((k for k in range(i - 1, max(i - 8, 0), -1) if H[k] == 10), None)
        k16 = next((k for k in range(i - 1, max(i - 40, 0), -1) if H[k] == 16), None)
        if k10 is None or k16 is None or k16 > k10: continue
        s = m.o[k10] / m.o[k16] - 1; sigs.append(abs(s))
        if filt == "big" and (len(sigs) < 60 or abs(s) <= np.median(sigs[-61:-1])): continue
        if s == 0: continue
        j = i + 1 if i + 1 < len(m.o) and H[i + 1] == 16 else None
        if j: out.append(trade(m, i, j, int(np.sign(s))))
    return out

def h_fomc(m):
    dates = [pd.Timestamp(x.strip()).date() for x in open(f"{SP}/news/fomc_dates.txt") if x.strip()]
    out = []; H = m.ny.hour; D = np.array(m.ny.date)
    for fd in dates:
        js = np.where((D == fd) & (H == 14))[0]
        if not len(js): continue
        j = js[0]; i = next((k for k in range(j - 1, max(j - 40, 0), -1) if H[k] == 14 and D[k] != fd), None)
        if i is not None: out.append(trade(m, i, j, +1))
    return out

def h_crypto_leadlag(btc, alts, hold, z=2.0):
    out = []
    rb = np.log(btc.b.c).diff(); sb = rb.rolling(720, min_periods=300).std().shift(1)
    for a in alts:
        ra = np.log(a.b.c).diff(); df = pd.concat([rb, sb, ra], axis=1, keys=["rb", "sb", "ra"]).dropna()
        beta = (df.rb * df.ra).rolling(720).sum() / (df.rb ** 2).rolling(720).sum(); beta = beta.shift(1)
        zz = df.rb / df.sb; pos = {t: k for k, t in enumerate(a.t)}
        for t in df.index[(zz.abs() > z) & ((df.ra / (beta * df.rb)) < 0.5) & (beta > 0.3)]:
            i = pos.get(t)
            if i is None or i + 1 + hold >= len(a.o): continue
            tr = trade(a, i + 1, i + 1 + hold, int(np.sign(df.rb[t])))
            if tr: out.append(tr)
    out.sort(key=lambda x: x[0]); return out

def stats(trs, split):
    trs = [x for x in trs if x]
    if len(trs) < 20: return dict(n=len(trs))
    r = np.array([x[2] for x in trs]); t = pd.DatetimeIndex([x[0] for x in trs])
    a, b = r[t < split], r[t >= split]
    f = lambda v: (len(v), v.mean(), v.mean() / v.std(ddof=1) * np.sqrt(len(v)) if len(v) > 2 and v.std() > 0 else np.nan)
    na, ma, ta = f(a); nb, mb, tb = f(b); nt, mt, tt = f(r)
    yrs = (t[-1] - t[0]).days / 365.25
    return dict(n=nt, per_yr=round(nt / yrs), meanR=round(mt, 3), t_all=round(tt, 2), n_tr=na, meanR_tr=round(ma, 3), t_tr=round(ta, 2),
                n_te=nb, meanR_te=round(mb, 3), t_te=round(tb, 2), win=round((r > 0).mean() * 100), R_yr=round(r.sum() / yrs, 1))

if __name__ == "__main__":
    import pickle
    C_IDX, C_GOLD, C_SILV, C_OIL, C_FX, C_FXX, C_CR = 0.00015, 0.00012, 0.0003, 0.0003, 0.00008, 0.00018, 0.0015
    M = {}
    for s, c in (("XAUUSD", C_GOLD), ("XAGUSD", C_SILV), ("USA500IDXUSD", C_IDX), ("USATECHIDXUSD", C_IDX), ("USA30IDXUSD", C_IDX), ("USSC2000IDXUSD", 0.0002)):
        M[s] = Mkt(s, load_duka(s), c)
    M["EURUSD"] = Mkt("EURUSD", load_1m_hourly(f"{SP}/fx1m/EURUSD_1m.csv"), C_FX)
    M["AUDCAD"] = Mkt("AUDCAD", load_1m_hourly(f"{SP}/fx1m/AUDCAD_1m.csv"), C_FXX)
    CR = {s: Mkt(s, load_crypto(s), C_CR) for s in ("BTC", "ETH", "SOL", "XRP", "ADA", "DOGE", "LTC", "LINK", "AVAX", "DOT", "BNB")}
    print("loaded", {k: (str(v.t[0].date()), len(v.t)) for k, v in M.items()}, flush=True)
    S16, S19, S20 = pd.Timestamp("2022-01-01", tz="UTC"), pd.Timestamp("2023-01-01", tz="UTC"), pd.Timestamp("2023-01-01", tz="UTC")
    HYP = []
    for x in (3, 6):
        for cnd in ("all", "after_down_us"): HYP.append(("H1 gold Asia-session drift", "XAUUSD", f"long 23->{x:02d} UTC {cnd}", lambda x=x, cnd=cnd: h_gold_asia(M["XAUUSD"], x, cnd), S16))
    HYP.append(("H1b silver Asia-session drift", "XAGUSD", "long 23->06 UTC all", lambda: h_gold_asia(M["XAGUSD"], 6, "all"), S16))
    HYP.append(("H1c gold US-session weakness", "XAUUSD", "short 13->20 UTC", lambda: h_session_hold(M["XAUUSD"], "UTC", 13, 20, -1), S16))
    for s in ("USA500IDXUSD", "USATECHIDXUSD", "USA30IDXUSD", "USSC2000IDXUSD"):
        for hin in (19, 1):
            for cnd in ("all", "after_down_day"):
                HYP.append(("H2 index overnight/Europe-open drift", s, f"long {hin:02d}->04 ET {cnd}", lambda s=s, hin=hin, cnd=cnd: h_index_overnight(M[s], hin, cnd), S16))
        for flt in ("all", "big"):
            HYP.append(("H3 intraday momentum (first move -> last hour)", s, f"last hour in direction of close->10:00 ET, {flt}", lambda s=s, flt=flt: h_intraday_mom(M[s], flt), S16))
    HYP.append(("H4 FX own-hours depreciation", "EURUSD", "short 07->12 London", lambda: h_session_hold(M["EURUSD"], LDN, 7, 12, -1), S19))
    HYP.append(("H4 FX own-hours depreciation", "EURUSD", "long 12->16 NY", lambda: h_session_hold(M["EURUSD"], NY, 12, 16, +1), S19))
    HYP.append(("H4 FX own-hours depreciation", "AUDCAD", "short 00->06 UTC (Sydney/Tokyo)", lambda: h_session_hold(M["AUDCAD"], "UTC", 0, 6, -1), S19))
    HYP.append(("H4 FX own-hours depreciation", "AUDCAD", "long 09->16 NY", lambda: h_session_hold(M["AUDCAD"], NY, 9, 16, +1), S19))
    for s in ("USA500IDXUSD", "USATECHIDXUSD"):
        HYP.append(("H5 pre-FOMC drift", s, "long 14:00 ET day before -> 14:00 ET FOMC day", lambda s=s: h_fomc(M[s]), S16))
    for hold in (1, 3):
        HYP.append(("H6 BTC->alt lead-lag", "10 alts", f"laggard follows BTC 2-sigma hour, hold {hold}h", lambda hold=hold: h_crypto_leadlag(CR["BTC"], [v for k, v in CR.items() if k != "BTC"], hold), S20))
    rows, TR = [], {}
    for hyp, mk, var, fn, split in HYP:
        trs = [x for x in fn() if x]; TR[(hyp, mk, var)] = trs
        st = stats(trs, split); rows.append(dict(hyp=hyp, market=mk, variant=var, **st)); print(rows[-1], flush=True)
    R = pd.DataFrame(rows); R.to_csv(f"{SP}/newlab_results.csv", index=False)
    pickle.dump(TR, open(f"{SP}/newlab_trades.pkl", "wb"))
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    print(R.drop(columns=["hyp"]).to_string())
