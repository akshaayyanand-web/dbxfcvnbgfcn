# Confirmation test for the watch-list "VIX9D / VIX > 1.10 -> buy, hold 5 days" (found on the S&P in xa.py). Same rule, unchanged, on markets it was not found on:
# Nasdaq, Dow, Russell 2000, DAX, FTSE 100 (European indices enter at their next open after the US close). Plus nearby thresholds on the S&P.
import numpy as np, pandas as pd
src = open("xa.py").read(); exec(src[:src.index("rows = []")])
def daily_any(sym):
    if sym in ("DOW", "RUT"): b = h1(sym).dropna()
    elif sym == "FTSE": b = K.rs(K.hd("UKXGBP"), "1h").dropna()
    else: b = K.rs(m5(sym), "1h").dropna()
    tz = {"DAX": "Europe/Berlin", "FTSE": "Europe/London"}.get(sym, "America/New_York"); lt = b.index.tz_convert(tz)
    hrs = {"DAX": (9, 17), "FTSE": (8, 16)}.get(sym, (9, 16)); m = (lt.hour >= hrs[0]) & (lt.hour < hrs[1]); b = b[m]; key = lt[m].normalize()
    d = b.groupby(key.date).agg({"o": "first", "h": "max", "l": "min", "c": "last"}); d.index = pd.DatetimeIndex(d.index).tz_localize("UTC") + pd.Timedelta(hours=21); return d
def vix(n): v = pd.read_csv(f"rdata/cboe/{n}.csv"); v.index = pd.DatetimeIndex(pd.to_datetime(v.DATE, format="%m/%d/%Y")).tz_localize("UTC") + pd.Timedelta(hours=21); return v.CLOSE
def rand_days(n, N, hold, s): g = np.random.default_rng(s); return [(int(k), 1, hold) for k in np.sort(g.choice(np.arange(20, N - hold - 2), n, replace=False))]
COST.update(FTSE=.0002); SWAP.update(FTSE=.05)
ratio_s = (vix("VIX9D") / vix("VIX")).dropna(); rows = []
def test(sym, thr, label):
    d = daily_any(sym); sig = ratio_s[ratio_s > thr].index; ks = sorted({int(d.index.searchsorted(t, "right") - 1) for t in sig if d.index.searchsorted(t, "right") - 1 >= 20})
    ev = [(k, 1, 5) for k in ks]; tr = sim(d, ev, sym, stopx=2.0, bar_h=24)
    base = [np.mean([x[1] for x in sim(d, rand_days(len(ev), len(d), 5, s), sym, stopx=2.0, bar_h=24)]) for s in range(60)]
    rows.append(report(label, tr, base))
for sym in ("SPX", "NQ", "DOW", "RUT", "DAX", "FTSE"): test(sym, 1.10, f"VIX9D/VIX > 1.10 -> buy {sym}, 5 days")
for thr in (1.05, 1.15, 1.20): test("SPX", thr, f"nearby: VIX9D/VIX > {thr:.2f} -> buy SPX, 5 days")
R = pd.DataFrame(rows); pd.set_option("display.width", 250); print(R.to_string(index=False)); R.to_csv("vixpanic.csv", index=False)
print("\nsignal days by year:", ratio_s[ratio_s > 1.10].groupby(ratio_s[ratio_s > 1.10].index.year).size().to_dict())
