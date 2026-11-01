"""Opening-range breakout (ORB) scalps on 1-minute data, resampled to 5-minute bars.

Nasdaq: range = first N minutes after the 09:30 New York open; trade the first 5-minute close outside
        the range until 11:30 NY; stop at the other side or the middle of the range; optional target in
        multiples of risk; otherwise flat at 15:55 NY (inside Topstep's 15:10 CT cut-off).
Gold:   the same around the 08:00 London open (entries until 11:00 London, flat at 16:30 London) and
        around the 08:20 New York COMEX open (entries until 10:30 NY, flat at 13:30 NY).
One trade per session; entry at the next 5-minute bar's open; stop and target checked on each bar
(stop first if both are touched). Results in R and per year at 1% risk; train 2019-2022, test 2023-2026.

Usage: python3 orb_lab.py MINUTE_DIR   (MINUTE_DIR holds USATECHIDXUSD_1m.csv and XAUUSD_1m.csv)
"""
import itertools
import sys

import numpy as np
import pandas as pd

from futures_lab import load_csv

COST = {"USATECHIDXUSD": 0.00012, "XAUUSD": 0.0001}
SESSIONS = {
    "NQ NY open": ("USATECHIDXUSD", "America/New_York", (9, 30), (11, 30), (15, 55)),
    "Gold London open": ("XAUUSD", "Europe/London", (8, 0), (11, 0), (16, 30)),
    "Gold NY open": ("XAUUSD", "America/New_York", (8, 20), (10, 30), (13, 30)),
}


def five_min(df):
    return df.resample("5min").agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()


def orb(df5, tz, start, last_entry, flat, minutes, stop_mode, target, both, cost):
    loc = df5.index.tz_convert(tz)
    mins = loc.hour * 60 + loc.minute
    day = pd.Index(loc.date)
    O, H, L, C = (df5[k].to_numpy() for k in "ohlc")
    s0, le, fl = start[0] * 60 + start[1], last_entry[0] * 60 + last_entry[1], flat[0] * 60 + flat[1]
    out = []
    for d, ix in pd.Series(np.arange(len(df5)), index=day).groupby(level=0):
        ix = ix.to_numpy()
        m = mins[ix]
        rng = ix[(m >= s0) & (m < s0 + minutes)]
        if len(rng) < minutes // 5:
            continue
        hi, lo = H[rng].max(), L[rng].min()
        mid = (hi + lo) / 2
        cand = ix[(m >= s0 + minutes) & (m < le)]
        ex = ix[m >= fl]
        if len(cand) == 0 or len(ex) == 0 or hi <= lo:
            continue
        for k in cand:
            dr = 1 if C[k] > hi else (-1 if both and C[k] < lo else 0)
            if dr == 0:
                continue
            j = k + 1
            if j >= ex[0]:
                break
            e = O[j]
            st = (lo if dr == 1 else hi) if stop_mode == "other" else mid
            if dr * (e - st) <= 0:
                break
            tg = None if target is None else e + dr * target * abs(e - st)
            px, xt = None, None
            for q in range(j, ex[0]):
                if (L[q] <= st) if dr == 1 else (H[q] >= st):
                    px, xt = (min(O[q], st) if dr == 1 else max(O[q], st)), df5.index[q] + pd.Timedelta("5min")
                    break
                if tg is not None and ((H[q] >= tg) if dr == 1 else (L[q] <= tg)):
                    px, xt = tg, df5.index[q] + pd.Timedelta("5min")
                    break
            if px is None:
                px, xt = O[ex[0]], df5.index[ex[0]]
            out.append((df5.index[j], xt, e, st, px, (dr * (px / e - 1) - cost) / (abs(e - st) / e)))
            break
    return out


def summarize(name, trades):
    if len(trades) < 60:
        return None
    df = pd.DataFrame(trades, columns=["et", "xt", "e", "st", "px", "R"])
    yr = {y: 100 * (np.prod(1 + 0.01 * g.R) - 1) for y, g in df.groupby(df.et.dt.year)}
    tr, te = [v for y, v in yr.items() if y <= 2022], [v for y, v in yr.items() if y >= 2023]
    a, b = df[df.et.dt.year <= 2022], df[df.et.dt.year >= 2023]
    if not tr or not te:
        return None
    return dict(setup=name, trades_pm=len(df) / max(1, (df.et.iloc[-1] - df.et.iloc[0]).days / 30.4), win=100 * (df.R > 0).mean(),
                R_train=a.R.mean(), yr_train=np.mean(tr), worst_train=min(tr), R_test=b.R.mean(), yr_test=np.mean(te), worst_test=min(te))


def main():
    data = {s: five_min(load_csv(f"{sys.argv[1]}/{s}_1m.csv")) for s in COST}
    rows = []
    for sess, (sym, tz, st, le, fl) in SESSIONS.items():
        for minutes, stop_mode, target, both in itertools.product([5, 15, 30], ["other", "mid"], [None, 1.0, 2.0], [False, True]):
            name = f"{sess} ORB {minutes}m stop={stop_mode} target={target} {'long+short' if both else 'long'}"
            rows.append(summarize(name, orb(data[sym], tz, st, le, fl, minutes, stop_mode, target, both, COST[sym])))
    res = pd.DataFrame([r for r in rows if r])
    pd.set_option("display.width", 240)
    pd.set_option("display.max_colwidth", 70)
    print("Per trade in R (costs included); yearly % at 1% risk. Train 2019-22, test 2023-26.\n")
    print(res.sort_values("yr_train", ascending=False).head(25).round(2).to_string(index=False))
    sel = res[res.yr_train > 3]
    print(f"\nSetups with train > +3%/yr: {len(sel)} -> test avg {sel.yr_test.mean():+.1f}%/yr, positive {(sel.yr_test > 0).sum()}/{len(sel)}")
    print(f"All setups: {len(res)}, positive on test {(res.yr_test > 0).sum()}")
    res.to_pickle(f"{sys.argv[1]}/orb_lab.pkl")


if __name__ == "__main__":
    main()
