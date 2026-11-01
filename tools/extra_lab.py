"""Extra candidate components for the prop portfolio.

crypto intraday  the session-range breakout and intraday momentum families on BTC and ETH (hourly)
overnight drift  long Nasdaq / S&P from the 16:00 New York close to the next 09:00 New York, ATR safety stop
turn of month    long Nasdaq / S&P from 15:00 NY on the last trading day of the month to 15:00 NY on the
                 N-th trading day of the new month, ATR safety stop

Results per trade in R (1R = stop distance, costs included) and per year at 1% risk.
Train = up to 2022, test = 2023-2026.
Usage: python3 extra_lab.py DATA_DIR   (DATA_DIR holds kh/BTCUSDT.csv, kh/ETHUSDT.csv, fut/*.csv)
"""
import itertools
import sys

import numpy as np
import pandas as pd

from backtest_ema_macd import load
from futures_lab import load_csv
from intraday_lab import intraday_momentum, range_breakout, run_trades, summarize
from test_rsi2_dip import rma


def atr_series(df, n=24):
    tr = pd.concat([df.h - df.l, (df.h - df.c.shift()).abs(), (df.l - df.c.shift()).abs()], axis=1).max(axis=1)
    return rma(tr, n).to_numpy()


def overnight(df, stop_atr, cost, weekdays=(0, 1, 2, 3)):
    """Enter at the open of the 16:00 NY bar (Mon-Thu), exit at the open of the 09:00 NY bar next day."""
    loc = df.index.tz_convert("America/New_York")
    hr, dow = loc.hour.to_numpy(), loc.dayofweek.to_numpy()
    C, atr = df.c.to_numpy(), atr_series(df)
    plans = []
    entries = np.flatnonzero((hr == 16) & np.isin(dow, weekdays))
    nine = np.flatnonzero(hr == 9)
    for j in entries:
        k = nine[np.searchsorted(nine, j)] if np.searchsorted(nine, j) < len(nine) else None
        if k is None or (df.index[k] - df.index[j]) > pd.Timedelta(hours=20) or np.isnan(atr[j - 1]):
            continue
        plans.append((j, 1, C[j - 1] - stop_atr * atr[j - 1], None, k - 1))
    return run_trades(df, plans, cost)


def turn_of_month(df, days_after, stop_atr, cost):
    loc = df.index.tz_convert("America/New_York")
    C, atr = df.c.to_numpy(), atr_series(df)
    dates = pd.Series(loc.date, index=range(len(df)))
    tdays = pd.Index(sorted(set(loc.date)))
    months = pd.Series(tdays, index=tdays).groupby([pd.Index(tdays).map(lambda d: (d.year, d.month))])
    plans = []
    hr = loc.hour.to_numpy()
    for _, g in months:
        last = g.iloc[-1]
        nxt = tdays[tdays > last]
        if len(nxt) < days_after:
            continue
        exit_day = nxt[days_after - 1]
        j = np.flatnonzero((dates.to_numpy() == last) & (hr == 15))
        k = np.flatnonzero((dates.to_numpy() == exit_day) & (hr == 15))
        if len(j) == 0 or len(k) == 0 or np.isnan(atr[j[0] - 1]):
            continue
        plans.append((j[0], 1, C[j[0] - 1] - stop_atr * atr[j[0] - 1], None, k[0] - 1))
    return run_trades(df, plans, cost)


def main():
    d = sys.argv[1]
    crypto = {s: load(f"{d}/kh/{s}USDT.csv").loc["2019-06-01":] for s in ("BTC", "ETH")}
    fut = {"NQ": load_csv(f"{d}/fut/USATECHIDXUSD.csv"), "ES": load_csv(f"{d}/fut/USA500IDXUSD.csv")}
    rows = []
    for s, df in crypto.items():
        for fee in (0.0008,):  # futures-style round trip (maker entry / taker exit)
            for stop, both in itertools.product(["mid", "other"], [False, True]):
                rows.append(summarize(f"{s} Asia-range BO (London) stop={stop} {'L+S' if both else 'L'}",
                                      range_breakout(df, "Europe/London", 0, 7, 7, 14, 20, stop, None, both, fee)))
            for sig, thr, both, satr in itertools.product([10, 11, 12], [0.01, 0.02], [False, True], [1.0, 1.5]):
                rows.append(summarize(f"{s} NY momentum sig {sig}:00 >{thr * 100:.0f}% stop {satr}ATR {'L+S' if both else 'L'}",
                                      intraday_momentum(df, "America/New_York", 16, sig, 16, thr, True, both, fee, satr)))
    for s, df in fut.items():
        cost = 0.00012 if s == "NQ" else 0.0001
        for satr in (2.0, 3.0, 5.0):
            rows.append(summarize(f"{s} overnight drift Mon-Thu stop {satr}ATR", overnight(df, satr, cost)))
        for n, satr in itertools.product([2, 3, 4], [3.0, 5.0]):
            rows.append(summarize(f"{s} turn-of-month to day {n} stop {satr}ATR", turn_of_month(df, n, satr, cost)))
    res = pd.DataFrame([r for r in rows if r])
    res.to_pickle(f"{d}/extra_lab.pkl")
    pd.set_option("display.width", 240)
    pd.set_option("display.max_colwidth", 60)
    cols = ["setup", "trades_pm", "win", "R_train", "yr_train", "worst_train", "R_test", "yr_test", "worst_test"]
    print("Per trade in R (costs included); yearly % at 1% risk. Train up to 2022, test 2023-2026.\n")
    print(res.sort_values("yr_train", ascending=False)[cols].round(2).to_string(index=False))
    for fam in ("BTC", "ETH", "NQ", "ES"):
        sub = res[res.setup.str.startswith(fam)]
        print(f"{fam}: {len(sub)} settings, positive train {(sub.yr_train > 0).sum()}, positive test {(sub.yr_test > 0).sum()}")


if __name__ == "__main__":
    main()
