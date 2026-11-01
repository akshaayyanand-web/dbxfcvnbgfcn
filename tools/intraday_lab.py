"""Intraday (day-trade) setups on hourly Nasdaq and gold data; every trade is closed the same day.

gold_asia_bo  London session break of the Asian range (00:00-07:00 London): enter on the first
              hourly close outside the range between 07:00 and 14:00 London, stop at the other side of
              the range (or half-way), optional target in range multiples, flat by 20:00 London.
nq_onr_bo     New York break of the overnight range (18:00-09:00 NY): first hourly close outside the
              range between 10:00 and 13:00 NY, stop at the range middle or other side, flat at 15:00 NY.
nq_mom / fade Intraday momentum: return from the previous 16:00 NY close to 11:00 NY; if it exceeds a
              threshold, follow it (mom) or fade it (fade) from 11:00 to 15:00 NY, ATR safety stop.
gold_mom/fade Same idea for gold on the London clock (previous 17:00 to 10:00 London, hold to 16:00).

All flat by 15:00 NY for Nasdaq, so the Nasdaq setups are Topstep-compliant. Results per trade in R
(1R = stop distance) and per year at 1% risk; train 2016-2022, test 2023-2026.
Usage: python3 intraday_lab.py FUTURES_DIR
"""
import itertools
import sys

import numpy as np
import pandas as pd

from futures_lab import load_csv
from test_rsi2_dip import rma

COST = {"XAUUSD": 0.0001, "USATECHIDXUSD": 0.00012}


def sessions(df, tz):
    loc = df.index.tz_convert(tz)
    return loc, loc.hour.to_numpy(), pd.DatetimeIndex(loc.date)


def run_trades(df, plans, cost):
    """plans: list of (entry_bar_index, dir, stop_px, target_px or None, last_bar_index). Fill at entry bar open."""
    O, H, L = df.o.to_numpy(), df.h.to_numpy(), df.l.to_numpy()
    T = df.index
    bar = pd.Timedelta("1h")
    out = []
    for j, dr, st, tg, last in plans:
        e = O[j]
        if dr * (e - st) <= 0 or (tg is not None and dr * (tg - e) <= 0):
            continue
        px, xt = None, None
        for k in range(j, last + 1):
            if (L[k] <= st) if dr == 1 else (H[k] >= st):
                px, xt = (min(O[k], st) if dr == 1 else max(O[k], st)), T[k] + bar  # exit inside bar k
                break
            if tg is not None and ((H[k] >= tg) if dr == 1 else (L[k] <= tg)):
                px, xt = tg, T[k] + bar
                break
        if px is None:
            px, xt = (O[last + 1] if last + 1 < len(O) else df.c.iloc[last]), T[min(last + 1, len(T) - 1)]
        if xt - T[j] > pd.Timedelta(days=2):  # a day trade spanning missing data: drop it
            continue
        risk = abs(e - st) / e
        out.append((T[j], xt, e, st, px, (dr * (px / e - 1) - cost) / risk))
    return out


def range_breakout(df, tz, r0, r1, w0, w1, flat_h, stop_mode, target, both, cost):
    loc, hr, day = sessions(df, tz)
    C = df.c.to_numpy()
    plans = []
    dser = pd.Series(np.arange(len(df)), index=day)
    for d, ix in dser.groupby(level=0):
        ix = ix.to_numpy()
        h = hr[ix]
        rng = ix[(h >= r0) & (h < r1)]
        if len(rng) < max(2, (r1 - r0) // 2):
            continue
        hi, lo = df.h.to_numpy()[rng].max(), df.l.to_numpy()[rng].min()
        mid, width = (hi + lo) / 2, hi - lo
        win = ix[(h >= w0) & (h < w1)]
        flat = ix[h >= flat_h]
        if len(win) == 0 or len(flat) == 0 or width <= 0:
            continue
        last = flat[0] - 1
        for k in win:
            dr = 1 if C[k] > hi else (-1 if (both and C[k] < lo) else 0)
            if dr == 0 or k + 1 > last:
                continue
            st = (lo if dr == 1 else hi) if stop_mode == "other" else mid
            tg = None if target is None else (C[k] + dr * target * width)
            plans.append((k + 1, dr, st, tg, last))
            break
    return run_trades(df, plans, cost)


def intraday_momentum(df, tz, ref_h, sig_h, flat_h, thr, follow, both, cost, stop_atr=1.5):
    loc, hr, day = sessions(df, tz)
    C = df.c.to_numpy()
    tr = pd.concat([df.h - df.l, (df.h - df.c.shift()).abs(), (df.l - df.c.shift()).abs()], axis=1).max(axis=1)
    atr = rma(tr, 24).to_numpy()
    ref_close = pd.Series(np.where(hr == ref_h - 1, C, np.nan), index=df.index).ffill().to_numpy()  # close of the bar ending at ref_h
    plans = []
    dser = pd.Series(np.arange(len(df)), index=day)
    for d, ix in dser.groupby(level=0):
        ix = ix.to_numpy()
        h = hr[ix]
        s = ix[h == sig_h - 1]  # bar ending at sig_h
        f = ix[h >= flat_h]
        if len(s) == 0 or len(f) == 0:
            continue
        k = s[0]
        prev_ref = ref_close[ix[0] - 1] if ix[0] > 0 else np.nan
        if np.isnan(prev_ref) or np.isnan(atr[k]):
            continue
        move = C[k] / prev_ref - 1
        if abs(move) < thr:
            continue
        dr = int(np.sign(move)) * (1 if follow else -1)
        if dr == -1 and not both:  # long-only variant
            continue
        st = C[k] - dr * stop_atr * atr[k]
        plans.append((k + 1, dr, st, None, f[0] - 1))
    return run_trades(df, plans, cost)


def summarize(name, trades):
    if len(trades) < 40:
        return None
    df = pd.DataFrame(trades, columns=["et", "xt", "e", "st", "px", "R"])
    yr = {y: 100 * (np.prod(1 + 0.01 * g.R) - 1) for y, g in df.groupby(df.et.dt.year)}
    a, b = df[df.et.dt.year <= 2022], df[df.et.dt.year >= 2023]
    if len(a) < 30 or len(b) < 10:
        return None
    return dict(setup=name, trades_pm=len(df) / ((df.et.iloc[-1] - df.et.iloc[0]).days / 30.4), win=100 * (df.R > 0).mean(),
                R_train=a.R.mean(), yr_train=np.mean([v for y, v in yr.items() if y <= 2022]), worst_train=min(v for y, v in yr.items() if y <= 2022),
                R_test=b.R.mean(), yr_test=np.mean([v for y, v in yr.items() if y >= 2023]), worst_test=min(v for y, v in yr.items() if y >= 2023))


def main():
    gold = load_csv(f"{sys.argv[1]}/XAUUSD.csv")
    nq = load_csv(f"{sys.argv[1]}/USATECHIDXUSD.csv")
    rows = []
    for stop_mode, target, both in itertools.product(["other", "mid"], [None, 1.0, 2.0], [False, True]):
        rows.append(summarize(f"gold Asia-range breakout stop={stop_mode} target={target} {'long+short' if both else 'long'}",
                              range_breakout(gold, "Europe/London", 0, 7, 7, 14, 20, stop_mode, target, both, COST["XAUUSD"])))
        rows.append(summarize(f"NQ overnight-range breakout stop={stop_mode} target={target} {'long+short' if both else 'long'}",
                              range_breakout(nq, "America/New_York", 0, 9, 10, 13, 15, stop_mode, target, both, COST["USATECHIDXUSD"])))
    for thr, follow, both in itertools.product([0.003, 0.006, 0.01], [True, False], [False, True]):
        tag = f"{'follow' if follow else 'fade'} >{thr * 100:.1f}% {'long+short' if both else 'long'}"
        rows.append(summarize(f"NQ intraday {tag}", intraday_momentum(nq, "America/New_York", 16, 11, 15, thr, follow, both, COST["USATECHIDXUSD"])))
        rows.append(summarize(f"gold intraday {tag}", intraday_momentum(gold, "Europe/London", 17, 10, 16, thr, follow, both, COST["XAUUSD"])))
    res = pd.DataFrame([r for r in rows if r])
    pd.set_option("display.width", 240)
    pd.set_option("display.max_colwidth", 70)
    print("Per trade in R (1R = stop distance, costs included); yearly % at 1% risk. Train 2016-22, test 2023-26.\n")
    print(res.sort_values("yr_train", ascending=False).round(2).to_string(index=False))
    sel = res[res.yr_train > 3]
    print(f"\nSetups with train > +3%/yr: {len(sel)} -> test avg {sel.yr_test.mean():+.1f}%/yr, positive {(sel.yr_test > 0).sum()}/{len(sel)}")
    res.to_pickle(f"{sys.argv[1]}/intraday_lab.pkl")


if __name__ == "__main__":
    main()
