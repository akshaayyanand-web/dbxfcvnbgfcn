# News filters for the 8 EAs. Events: FOMC statements (federalreserve.gov), NFP and CPI (8:30 ET, dates from the
# first-Friday rule / mid-month window, confirmed by the 8:30 volume spike in Nasdaq 1-minute data).
import sys, numpy as np, pandas as pd
SP = sys.argv[1]
exec(open(SP + "/losers.py").read().split("FEATS = [")[0])
_src = open(SP + "/losers.py").read(); exec("def run3" + _src.split("def run3", 1)[1].split("wst =")[0])
NY = "America/New_York"
fomc = [d for d in open(SP + "/news/fomc_dates.txt").read().split() if d not in ("20191011", "20200331", "20200827", "20250822")]
ev = [pd.Timestamp(f"{d[:4]}-{d[4:6]}-{d[6:]} 14:00", tz=NY) for d in fomc]
# 8:30 volume spike per day from Nasdaq 1m
m1 = pd.read_csv(SP + "/fut1m/USATECHIDXUSD_1m.csv", usecols=[0, 5], index_col=0); m1.index = pd.to_datetime(m1.index, utc=True).tz_convert(NY)
mm = m1.index.hour * 60 + m1.index.minute; dte = m1.index.normalize()
v830 = m1.v[(mm >= 510) & (mm < 515)].groupby(dte[(mm >= 510) & (mm < 515)]).sum()
v820 = m1.v[(mm >= 500) & (mm < 505)].groupby(dte[(mm >= 500) & (mm < 505)]).sum()
ratio = (v830 / v820.reindex(v830.index)).replace([np.inf], np.nan).dropna()
nfp, cpi = [], []
for (y, mo), g in ratio.groupby([ratio.index.year, ratio.index.month]):
    early = g[(g.index.day <= 10)]
    fri = early[early.index.weekday == 4]
    if len(fri) and fri.iloc[0] >= 3: nfp.append(fri.index[0])
    elif len(early): nfp.append(early.idxmax())
    mid = g[(g.index.day >= 9) & (g.index.day <= 16)]
    if len(mid): cpi.append(mid.idxmax())
ev += [d + pd.Timedelta(hours=8, minutes=30) for d in nfp + cpi]
EV = pd.DatetimeIndex(sorted(ev)).tz_convert("UTC")
print(f"events: {len(fomc)} FOMC, {len(nfp)} NFP, {len(cpi)} CPI | median 8:30 volume spike on NFP days x{ratio.reindex(nfp).median():.1f}, CPI days x{ratio.reindex(cpi).median():.1f}, other days x{ratio.drop(nfp + cpi, errors='ignore').median():.1f}")
evday = set(EV.tz_convert(NY).normalize())

def tlist(k):
    if k in ("nqdip", "spxdip"):
        df = nq if k == "nqdip" else spx; _, _, res = grid_run(df); return [(t, None, None, None, None, x) for t, x in res]
    trades, cost, h1 = TR[k]; return [(et, xt, e, st, px, (px - e) / (e - st) - cost * e / abs(e - st)) for et, xt, e, st, px in trades]
def near(ts, before, after):
    i = EV.searchsorted(ts - after); return i < len(EV) and EV[i] <= ts + before
FILTERS = {"no entries 1h before to 1h after news": lambda t: near(t, pd.Timedelta(hours=1), pd.Timedelta(hours=1)),
           "no entries on news days": lambda t: t.tz_convert(NY).normalize() in evday,
           "no entries in the 24h before news": lambda t: near(t, pd.Timedelta(hours=24), pd.Timedelta(0))}
# 1) compliance: entries / time exits within 2 minutes of an event (FTMO-style funded rule)
print("\ntrades opened or closed within 2 minutes of news (2020-2026):")
for k in USED:
    tl = tlist(k); two = pd.Timedelta(minutes=2)
    n_in = sum(near(t[0], two, two) for t in tl); n_out = sum(t[1] is not None and near(t[1], two, two) for t in tl)
    print(f"  {k:<7} {len(tl):5d} trades | opened in window {n_in:3d} | closed in window (time exits / stops) {n_out:3d}")
# 2) per strategy: R of trades entered near news vs the rest, by halves
rows = []
for k in USED:
    T = pd.DataFrame([(t[0], t[5]) for t in tlist(k)], columns=["t", "R"])
    for fl, fn in FILTERS.items():
        m = T.t.apply(fn)
        for p, sel in (("2020-22", T.t < split), ("2023-26", T.t >= split)):
            rows.append(dict(strategy=k, filter=fl, part=p, blocked=int((m & sel).sum()), avgR_blocked=T.R[m & sel].mean(), avgR_rest=T.R[~m & sel].mean(), R_saved=-T.R[m & sel].sum()))
rp = pd.DataFrame(rows); pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
print("\nWhat the blocked trades earned (R_saved > 0 means blocking helps):")
print(rp.pivot_table(index=["strategy", "filter"], columns="part", values=["blocked", "avgR_blocked", "R_saved"]).round(2).to_string())
# 3) prop test with each filter on all strategies
def filt_series(k, fn):
    if k in ("nqdip", "spxdip"):
        df = nq if k == "nqdip" else spx; allow = np.array([not fn(t) for t in df.index]); r, lo, _ = grid_run(df, allow); return r, lo
    trades, cost, h1 = TR[k]; return P.trade_series([t for t in trades if not fn(t[0])], cost, h1, idx)
wst = pd.date_range("2020-04-01", "2025-10-01", freq="MS", tz="UTC")
for fl, fn in [("8 EAs as now", None)] + list(FILTERS.items()):
    Rm, LOm = R.copy(), LO.copy()
    if fn:
        for k in USED: i = names.index(k); Rm[i], LOm[i] = filt_series(k, fn)
    res = []
    for s_ in est:
        h0 = idx.searchsorted(s_); a, i1, _ = run3(W, Rm, LOm, h0, len(idx), 0.10)
        if a != "pass": res.append((s_, a, None)); continue
        b, i2, _ = run3(W, Rm, LOm, h0 + i1 + 1, len(idx), 0.05); res.append((s_, b, (i1 + i2) / 24 if b == "pass" else None))
    yy = [(s_, *run3(W, Rm, LOm, idx.searchsorted(s_), idx.searchsorted(s_ + pd.DateOffset(years=1)), None)) for s_ in wst]
    for p, sel in (("2020-22", lambda s: s < split), ("2023-25", lambda s: s >= split)):
        rr = [x for x in res if sel(x[0])]; t = [x[2] for x in rr if x[2] is not None]; y = [v for v in yy if sel(v[0])]
        print(f"{fl:<40} {p} pass {100*np.mean([x[1]=='pass' for x in rr]):3.0f}% breach {100*np.mean([x[1]=='fail' for x in rr]):3.0f}% median {np.median(t):4.0f}d | funded median {100*np.median([v[3] for v in y]):+5.1f}% breaches {sum(v[1]=='fail' for v in y)}", flush=True)
