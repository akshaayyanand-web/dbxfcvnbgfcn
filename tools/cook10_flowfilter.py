# Order-flow / options-flow filters on the 21 EAs' real trades (take the trade or skip it). Pre-registered:
#  H1 gamma regime (SqueezeMetrics GEX, previous day, percentile over the past 252 days): breakout EAs only when GEX pct <= 0.40;
#     fade/dip EAs only when GEX pct > 0.40.
#  H2 dark-pool flow (DIX 5-day mean vs its 252-day median, previous day): longs only when above, shorts only when below.
#  H3 crypto taker flow (Binance, the hour before entry): trade only when the taker-buy share is on the trade's side (H3b: the opposite).
# A filter "works" if kept trades beat skipped trades in BOTH 2016-22 and 2023-26 (pooled over the EAs it applies to).
import sys, glob, numpy as np, pandas as pd
exec(open("stopsize.py").read().split("\nREAL = ")[0])
dx = pd.read_csv("optflow/DIX.csv", parse_dates=["date"]).set_index("date")
gpct = dx.gex.rolling(252, min_periods=126).rank(pct=True).shift(1); dixs = (dx.dix.rolling(5).mean() > dx.dix.rolling(252, min_periods=126).median()).shift(1)
BREAK = {"orb15", "nqbo15", "spxbo5", "daxorb", "daxpm", "nikkei", "gasia", "gmom"}; FADE = {"nqfade", "spxfade", "nq2h", "spx1h", "gdip", "goldvwap", "oil1h"}
EQUITY = {"orb15", "nqbo15", "spxbo5", "daxorb", "daxpm", "nikkei", "nqfade", "spxfade", "nq2h", "spx1h"}
def taker(sym):
    p = []
    for f in sorted(glob.glob(f"k5full/{sym}USDT-5m-*.csv")):
        x = pd.read_csv(f, header=None, usecols=[0, 5, 9], names=["t", "v", "tb"]); x["t"] = np.where(x.t > 1e14, x.t // 1000, x.t); p.append(x)
    x = pd.concat(p); x.index = pd.to_datetime(x.t, unit="ms", utc=True); x = x[~x.index.duplicated()].sort_index()
    return (x.tb.rolling(12).sum() / x.v.rolling(12).sum().replace(0, np.nan))          # taker-buy share over the last hour
TK = {s: taker(s) for s in ("BTC", "SOL", "XRP")}
rows = []
for c, tl in TR.items():
    for et, xt, e, sd, d, r, px in tl:
        nyd = pd.Timestamp(et).tz_convert("America/New_York").normalize().tz_localize(None)
        g = gpct.asof(nyd) if len(gpct) else np.nan; ds = dixs.asof(nyd)
        tk = np.nan
        if INS[c] in TK: s_ = TK[INS[c]]; tk = s_.asof(pd.Timestamp(et) - pd.Timedelta("5min"))
        rows.append(dict(ea=c, et=pd.Timestamp(et), xt=pd.Timestamp(xt), d=d, R=r, gex_pct=g, dix_up=ds, taker=tk))
T = pd.DataFrame(rows); T["period"] = np.where(T.et < pd.Timestamp("2023-01-01", tz="UTC"), "2016-22", "2023-26")
def judge(name, sub, keep):
    out = []
    for per in ("2016-22", "2023-26"):
        s = sub[sub.period == per]; k = keep.loc[s.index]
        kk, sk = s.R[k], s.R[~k]
        tdiff = (kk.mean() - sk.mean()) / np.sqrt(kk.var() / max(len(kk), 1) + sk.var() / max(len(sk), 1)) if len(kk) > 5 and len(sk) > 5 else np.nan
        out.append(dict(filter=name, period=per, kept=len(kk), skipped=len(sk), kept_avgR=round(kk.mean(), 3), skipped_avgR=round(sk.mean(), 3), all_avgR=round(s.R.mean(), 3),
                        t_diff=round(tdiff, 2), R_yr_all=round(s.R.sum() / (7 if per == "2016-22" else 3.9), 1), R_yr_kept=round(kk.sum() / (7 if per == "2016-22" else 3.9), 1)))
    return out
res = []
a = T[T.ea.isin(BREAK & EQUITY) & T.gex_pct.notna()]; res += judge("H1 breakouts only in low gamma (GEX pct <= 0.4)", a, a.gex_pct <= 0.4)
b = T[T.ea.isin(FADE & EQUITY) & T.gex_pct.notna()]; res += judge("H1 fades/dips only in higher gamma (GEX pct > 0.4)", b, b.gex_pct > 0.4)
e = T[T.ea.isin(EQUITY) & T.dix_up.notna()]; keep = ((e.d > 0) & (e.dix_up == True)) | ((e.d < 0) & (e.dix_up == False)); res += judge("H2 DIX agrees with direction", e, keep)
k_ = T[T.taker.notna()]; agree = ((k_.d > 0) & (k_.taker > 0.5)) | ((k_.d < 0) & (k_.taker < 0.5))
res += judge("H3 crypto taker flow agrees", k_, agree); res += judge("H3b crypto taker flow against", k_, ~agree)
R = pd.DataFrame(res); pd.set_option("display.width", 250); print(R.to_string(index=False)); R.to_csv("flowfilter.csv", index=False); T.to_pickle("flowfilter_trades.pkl")
print("\nper EA, H1 (kept avgR vs skipped, 2016-22 | 2023-26):")
for c in sorted((BREAK | FADE) & EQUITY):
    s = T[(T.ea == c) & T.gex_pct.notna()]; keep = (s.gex_pct <= 0.4) if c in BREAK else (s.gex_pct > 0.4)
    q = lambda per: f"{s.R[keep & (s.period == per)].mean():+.2f} vs {s.R[~keep & (s.period == per)].mean():+.2f}"
    print(f"  {c:9s} {q('2016-22')} | {q('2023-26')}")
