# Second user list, daily macro / intermarket / calendar part. Daily closes at 21:00 UTC. Macro and CBOE signals dated d act from the close of d+1
# (one extra day so nothing is used before it is published); price signals act from the close of d. Hold H days, no overlap per strategy/market.
# Net = direction x log return - spread - swap. Long-only ideas are also judged against holding the market (drift-adjusted).
import sys, numpy as np, pandas as pd, warnings
sys.argv = sys.argv[:1]
import cat1000 as K
warnings.filterwarnings("ignore")
SPLIT = pd.Timestamp("2023-01-01")
def duka_c(sym): d = pd.read_csv(f"fut/{sym}.csv", index_col=0); d.index = pd.to_datetime(d.index, utc=True); return d.c
def jpn():
    import glob, io
    parts = [pd.read_csv(io.StringIO(open(f).read().strip()), header=None, names=["t", "o", "h", "l", "c", "v"]) for f in sorted(glob.glob("world1m/JPNIDXJPY/*.csv")) if open(f).read().strip()]
    x = pd.concat(parts); x.index = pd.to_datetime(x.t, unit="s", utc=True); return x[~x.index.duplicated()].sort_index().c
SRCS = {"SPX": (lambda: K.bars("SPX", "H1").c, .00015, .05), "NQ": (lambda: K.bars("NQ", "H1").c, .00015, .05), "DOW": (lambda: duka_c("USA30IDXUSD"), .00015, .05),
        "RUT": (lambda: duka_c("USSC2000IDXUSD"), .0003, .05), "DAX": (lambda: K.bars("DAX", "H1").c, .00015, .05), "JPN": (lambda: jpn(), .0002, .05),
        "XAU": (lambda: K.bars("XAU", "H1").c, .00012, .04), "XAG": (lambda: duka_c("XAGUSD"), .0008, .04), "WTI": (lambda: K.bars("WTI", "H1").c, .0003, .05),
        "EURUSD": (lambda: K.bars("EURUSD", "H1").c, .00008, .02), "GBPUSD": (lambda: K.bars("GBPUSD", "H1").c, .00009, .02), "USDJPY": (lambda: K.bars("USDJPY", "H1").c, .00007, .02),
        "BTC": (lambda: K.bars("BTC", "H1").c, .0006, .15), "ETH": (lambda: K.bars("ETH", "H1").c, .001, .15)}
for p_, c_ in (("AUDUSD", .0001), ("NZDUSD", .00014), ("USDCAD", .0001), ("USDCHF", .00012), ("EURJPY", .0001), ("GBPJPY", .00015)):
    SRCS[p_] = (lambda p_=p_: K.hd(p_).c, c_, .02)
def daily(series):
    s = series[series.index.hour <= 20]; d = s.groupby(s.index.date).last(); d.index = pd.to_datetime(d.index); return d[d.index.dayofweek < 5]
P = {}
for k, (f, c, sw) in SRCS.items():
    try: P[k] = daily(f().resample("1h").last().dropna())
    except Exception as ex: print("load fail", k, ex)
P["AUDJPY"] = (P["AUDUSD"] * P["USDJPY"]).dropna(); P["NZDJPY"] = (P["NZDUSD"] * P["USDJPY"]).dropna(); P["CHFJPY"] = (P["USDJPY"] / P["USDCHF"]).dropna()
COST = {k: v[1] for k, v in SRCS.items()}; COST.update(AUDJPY=.00025, NZDJPY=.0003, CHFJPY=.0003); SWAP = {k: v[2] for k, v in SRCS.items()}; SWAP.update(AUDJPY=.02, NZDJPY=.02, CHFJPY=.02)
PX = pd.DataFrame(P).sort_index(); RET = np.log(PX).diff()
def fred(n): v = pd.read_csv(f"rdata/fred/{n}.csv"); v.index = pd.to_datetime(v.iloc[:, 0]); return pd.to_numeric(v.iloc[:, 1], errors="coerce").dropna()
def cboe(n): v = pd.read_csv(f"rdata/cboe/{n}.csv"); v.index = pd.to_datetime(v.DATE, format="%m/%d/%Y"); return v.CLOSE
idx = PX.index; al = lambda s: s.reindex(idx, method="ffill")
DGS10, T10YIE, T10Y2Y, BAA, NFCI, DXY, VIX, VIX3M = (al(fred("DGS10")), al(fred("T10YIE")), al(fred("T10Y2Y")), al(fred("BAA10Y")), al(fred("NFCI")), al(fred("DTWEXBGS")), al(cboe("VIX")), al(cboe("VIX3M")))
BRENT, WTIs = al(fred("DCOILBRENTEU")), al(fred("DCOILWTICO")); RY = DGS10 - T10YIE
def z(x, n): r = x.rolling(n, min_periods=n // 2); return (x - r.mean()) / r.std()
def catchup(y, x, n=250, thr=1.5):
    """y, x: 5-day changes. Rolling OLS residual z; y lagging (resid z < -thr) -> +1 (catch up), > thr -> -1."""
    mp = n // 2; b = y.rolling(n, min_periods=mp).cov(x) / x.rolling(n, min_periods=mp).var(); a = y.rolling(n, min_periods=mp).mean() - b * x.rolling(n, min_periods=mp).mean(); res = y - (a + b * x); rz = z(res, n)
    return pd.Series(np.where(rz < -thr, 1, np.where(rz > thr, -1, 0)), y.index)
def sig_from(cond_up, cond_dn): return pd.Series(np.where(cond_up, 1, np.where(cond_dn, -1, 0)), idx)
L5 = lambda s: np.log(s) - np.log(s.shift(5)); D5 = lambda s: s - s.shift(5)
TESTS = []   # (id, name, market, signal, H, skip, long_only)
def add(i, nm, mk, sig, H=5, skip=0, lo=False): TESTS.append((i, nm, mk, sig.reindex(idx).fillna(0), H, skip, lo))
spx_rv = RET.SPX.rolling(20).std() * np.sqrt(252) * 100; nq_rv = RET.NQ.rolling(20).std() * np.sqrt(252) * 100
for mk, rv in (("SPX", spx_rv), ("NQ", nq_rv)):
    add(427, "VIX term structure (VIX/VIX3M<0.9) long", mk, sig_from(VIX / VIX3M < 0.9, False), 5, 1, True)
    add(428, "Volatility risk premium (VIX-RV20>4) long", mk, sig_from(VIX - rv > 4, False), 5, 1, True)
brk = sig_from(DGS10 > DGS10.shift(1).rolling(20).max(), DGS10 < DGS10.shift(1).rolling(20).min())
for mk, sgn in (("USDJPY", 1), ("XAU", -1), ("NQ", -1)): add(630, "Treasury yield breakout", mk, brk * sgn, 5, 1)
yz = z(D5(DGS10), 250); rev = sig_from(yz < -2, yz > 2)
for mk, sgn in (("USDJPY", 1), ("XAU", -1), ("NQ", -1)): add(631, "Treasury yield reversal", mk, rev * sgn, 5, 1)
st = sig_from(T10Y2Y - T10Y2Y.shift(20) > 0.15, T10Y2Y - T10Y2Y.shift(20) < -0.15)
add(632, "Yield curve steepening/flattening", "XAU", st, 5, 1); add(632, "Yield curve steepening/flattening", "USDJPY", -st, 5, 1)
ry = sig_from(RY - RY.shift(20) < -0.15, RY - RY.shift(20) > 0.15); add(635, "Real yield momentum (gold)", "XAU", ry, 5, 1)
ryz = z(D5(RY), 250); add(636, "Real yield reversion (gold)", "XAU", sig_from(ryz > 2, ryz < -2), 5, 1)
be = sig_from(T10YIE - T10YIE.shift(20) > 0.10, T10YIE - T10YIE.shift(20) < -0.10)
for mk in ("XAU", "WTI"): add(637, "Inflation breakeven repricing", mk, be, 5, 1)
cs = sig_from(BAA - BAA.shift(20) < -0.15, BAA - BAA.shift(20) > 0.15)
for mk in ("SPX", "NQ"): add(641, "Credit spread widening/tightening", mk, cs, 5, 1)
nf = NFCI.diff(5); add(645, "Financial conditions index shock", "SPX", sig_from(nf < -0.05, nf > 0.05), 5, 1)
vx5 = VIX / VIX.shift(5) - 1
add(660, "Safe haven rotation (VIX +25% -> gold)", "XAU", sig_from(vx5 > 0.25, False), 5, 1); add(660, "Safe haven rotation (VIX +25% -> JPY)", "USDJPY", sig_from(False, vx5 > 0.25), 5, 1)
add(661, "Risk-on (VIX -20%) -> AUDJPY", "AUDJPY", sig_from(vx5 < -0.20, False), 5, 1); add(661, "Risk-on (VIX -20%) -> NQ", "NQ", sig_from(vx5 < -0.20, False), 5, 1, True)
dx5 = L5(DXY)
add(701, "EURUSD-DXY divergence", "EURUSD", catchup(L5(PX.EURUSD), dx5)); add(702, "GBPUSD-DXY divergence", "GBPUSD", catchup(L5(PX.GBPUSD), dx5))
add(703, "USDJPY-Treasury yield relationship", "USDJPY", catchup(L5(PX.USDJPY), D5(DGS10)))
add(708, "USDCAD-oil relationship", "USDCAD", catchup(L5(PX.USDCAD), L5(PX.WTI))); add(709, "USDCHF-risk sentiment (VIX)", "USDCHF", catchup(L5(PX.USDCHF), vx5))
for i, mk in ((713, "AUDJPY"), (714, "NZDJPY")):
    rz = z(L5(PX[mk]), 250); add(i, f"{mk} carry unwind (follow 2-sigma weeks)", mk, sig_from(rz > 2, rz < -2))
add(721, "Gold-DXY divergence", "XAU", catchup(L5(PX.XAU), dx5)); add(722, "Gold-real yield divergence", "XAU", catchup(L5(PX.XAU), D5(RY)))
add(736, "Oil-DXY relationship", "WTI", catchup(L5(PX.WTI), dx5)); add(738, "Oil-equity divergence", "WTI", catchup(L5(PX.WTI), L5(PX.SPX)))
go = z(np.log(PX.XAU / PX.WTI), 250); add(726, "Gold-oil ratio reversion", "WTI", sig_from(go > 2, go < -2), 10)
for mk in ("XAU", "XAG"):
    pm = (np.log(PX.XAU).diff(20) + np.log(PX.XAG).diff(20)) / 2; add(728, "Precious metals basket momentum", mk, sig_from(pm > 0, pm < 0))
    pr = z((L5(PX.XAU) + L5(PX.XAG)) / 2, 250); add(729, "Precious metals basket reversion", mk, sig_from(pr < -2, pr > 2))
bw = z(np.log(BRENT / WTIs), 60); add(739, "Brent-WTI spread reversion", "WTI", sig_from(bw > 2, bw < -2), 10, 1)
bm = np.log(BRENT / WTIs).diff(20); add(740, "Brent-WTI spread momentum", "WTI", sig_from(bm < 0, bm > 0), 5, 1)
for mk in ("XAU", "XAG", "WTI"):
    m20 = np.log(PX[mk]).diff(20); add(745, "Commodity basket momentum (per leg)", mk, sig_from(m20 > 0, m20 < 0))
    r5 = z(L5(PX[mk]), 250); add(746, "Commodity basket reversion (per leg)", mk, sig_from(r5 < -2, r5 > 2))
def xs(mks, look, top, rev=False):
    m = np.log(PX[mks]).diff(look); rk = m.rank(axis=1, ascending=rev); n_ = m.notna().sum(axis=1)
    out = {}
    for mk in mks: out[mk] = pd.Series(np.where(rk[mk] <= top, 1, np.where(rk[mk] > n_ - top, -1, 0)), idx) * (m[mk].notna())
    return out
for mk, s_ in xs(["NQ", "SPX", "DOW", "RUT", "DAX", "JPN"], 20, 1).items(): add(749, "Equity index relative strength (20d, weekly)", mk, s_)
spz = z(RET.SPX, 250); add(755, "Nikkei follows the S&P day", "JPN", sig_from(spz > 1, spz < -1), 1)
cb = RET.SPX.rolling(60, min_periods=40).corr(-DGS10.diff()); add(761, "Equity-bond correlation regime (long SPX when bonds hedge)", "SPX", sig_from(cb < 0, False), 5, 1, True)
add(763, "Equity-dollar divergence", "SPX", catchup(L5(PX.SPX), dx5))
add(764, "Equity-credit spread divergence", "SPX", sig_from(False, (np.log(PX.SPX).diff(20) > 0) & (BAA - BAA.shift(20) > 0.10)), 5, 1)
add(765, "Equity-VIX relationship (both up -> short)", "SPX", sig_from(False, (L5(PX.SPX) > 0) & (vx5 > 0.10)), 5, 1)
add(768, "Volatility index momentum", "SPX", sig_from(vx5 < -0.20, vx5 > 0.20), 5, 1)
ALL = [c for c in PX.columns]
for mk, s_ in xs(ALL, 20, 3).items(): add(581, "Cross-sectional rank momentum (20d, top/bottom 3, weekly)", mk, s_)
for mk, s_ in xs(ALL, 5, 3, rev=True).items(): add(582, "Cross-sectional rank reversal (5d, weekly)", mk, s_)
dow = pd.Series(idx.dayofweek, idx); wkn = pd.Series(idx.isocalendar().week.values + 100 * idx.year.values, idx)
for mk in ("SPX", "NQ", "XAU", "EURUSD", "BTC"):
    mt = np.log(PX[mk]).groupby(wkn).transform(lambda s: s - s.iloc[0]); thu = (dow == 3)
    add(808, "Weekly closing momentum (Fri follows Mon-Thu)", mk, sig_from(thu & (mt > 0), thu & (mt < 0)), 1)
    add(809, "Weekly closing reversal (Fri fades Mon-Thu)", mk, sig_from(thu & (mt < 0), thu & (mt > 0)), 1)
    yr = idx.year; ytd = np.log(PX[mk]).groupby(yr).transform(lambda s: s - s.iloc[0]); lastwk = (idx.month == 12) & (idx.day >= 23)
    add(820, "Year-end position squaring (fade YTD in the last week)", mk, sig_from(lastwk & (ytd < 0), lastwk & (ytd > 0)), 1)
for mth in range(1, 13):
    for mk in ("SPX", "NQ", "XAU", "BTC"): add(820 + mth, f"Month {mth} seasonality (long every day)", mk, sig_from(pd.Series(idx.month == mth, idx), False), 1, 0, True)
def run_test(t):
    i, nm, mk, sig, H, skip, lo = t; r = RET[mk].fillna(0).to_numpy(); s = sig.to_numpy(); n = len(r); out = []; k = 0
    c = COST[mk]; swp = SWAP[mk] / 365 * 1.4
    drift = np.nanmean(RET[mk].to_numpy())
    while k < n - H - skip - 1:
        if s[k] != 0 and np.isfinite(PX[mk].iloc[k]):
            a = k + skip; g = s[k] * r[a + 1:a + 1 + H].sum(); net = g - c - swp * H; out.append((idx[a], net, net - s[k] * drift * H)); k = a + H
        else: k += 1
    D = pd.DataFrame(out, columns=["t", "net", "adj"])
    if len(D) < 10: return dict(id=i, name=nm, mkt=mk, n=len(D))
    tr = D.t < SPLIT; tt = lambda v: v.mean() / v.std(ddof=1) * np.sqrt(len(v)) if len(v) > 2 and v.std() > 0 else np.nan
    col = "adj" if lo else "net"; yrs = D.groupby(D.t.dt.year)[col].sum()
    return dict(id=i, name=nm, mkt=mk, H=H, long_only=lo, n=len(D), n_train=int(tr.sum()), n_hold=int((~tr).sum()), mean_bp=1e4 * D.net.mean(), mean_adj_bp=1e4 * D.adj.mean(),
                t_train=tt(D[col][tr]), t_hold=tt(D[col][~tr]), avg_train_bp=1e4 * D[col][tr].mean(), avg_hold_bp=1e4 * D[col][~tr].mean(), pos_years=int((yrs > 0).sum()), years=len(yrs))
if __name__ == "__main__":
    R = pd.DataFrame([run_test(t) for t in TESTS]); R.to_pickle("cat2000/results_daily.pkl")
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 300)
    print(R.round(2).to_string(index=False))
