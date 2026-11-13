# Tick microstructure: does the last 5-60 s of NQ movement predict the next 10-120 s by more than the spread? (RoboForex ticks Nov 6-12 2026)
import numpy as np, pandas as pd
t = pd.read_csv("ticks_in/.USTECHCash_202611061900_202611121702.csv", sep="\t", usecols=[0, 1, 2, 3]); t.columns = ["d", "tm", "bid", "ask"]
t[["bid", "ask"]] = t[["bid", "ask"]].ffill(); t = t.dropna()
ts = pd.to_datetime(t.d + " " + t.tm, format="%Y.%m.%d %H:%M:%S.%f") - pd.Timedelta(hours=2)
s = pd.DataFrame({"bid": t.bid.values, "ask": t.ask.values}, index=ts.values)
s = s[~s.index.duplicated(keep="last")]
sec = s.resample("1s").last().ffill(); cnt = s.bid.resample("1s").count()
ny = sec.index.tz_localize("UTC").tz_convert("America/New_York"); m = ny.hour * 60 + ny.minute
mid = (sec.bid + sec.ask) / 2; spread = (sec.ask - sec.bid)
rows = []
for back in (5, 15, 30, 60):
    past = mid - mid.shift(back); act = cnt.rolling(back).sum()
    for fwd in (10, 30, 60, 120):
        fut = mid.shift(-fwd) - mid
        df = pd.DataFrame({"past": past, "act": act, "fut": fut, "sp": spread, "m": m}).dropna()
        df = df[(df.m >= 570) & (df.m < 960)]
        for lab, sel in (("top 10% moves", df.past.abs() >= df.past.abs().quantile(0.9)), ("top 2% moves", df.past.abs() >= df.past.abs().quantile(0.98)),
                         ("top 2% moves + busy tape", (df.past.abs() >= df.past.abs().quantile(0.98)) & (df.act >= df.act.quantile(0.8)))):
            g = df[sel]
            follow = (np.sign(g.past) * g.fut)              # points gained by trading WITH the move (before costs)
            rows.append(dict(look_back_s=back, hold_s=fwd, signal=lab, samples=len(g), follow_pts=round(follow.mean(), 2), fade_pts=round(-follow.mean(), 2),
                             best_after_spread=round(abs(follow.mean()) - g.sp.mean(), 2), spread=round(g.sp.mean(), 2)))
r = pd.DataFrame(rows).sort_values("best_after_spread", ascending=False)
pd.set_option("display.width", 250); print(r.head(15).to_string(index=False))
print("\nany signal beating the spread on average:", (r.best_after_spread > 0).sum(), "of", len(r))
