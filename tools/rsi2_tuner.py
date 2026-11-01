"""Tune the RSI dip strategy for prop evaluations (static max loss) with a train / validation split.

Signal grid: timeframe, RSI length and threshold, trend EMA, optional daily SMA-200 regime filter,
ATR stop multiple, exit style (time only / close above SMA(5) / RSI above 70) and maximum holding time.
Every configuration's trade list is pushed through a prop-evaluation simulator using the Prop Mode
sizing (risk 25% of the buffer above the fail line, max 2.2% per trade, max 1.5x position).

Train attempts start Apr 2020 - Jun 2023 and only see data up to 31 Dec 2023.
Validation attempts start Jan 2024 - Oct 2025 and run on data up to Oct 2026.

Usage: python3 rsi2_tuner.py BTCUSDT_1h.csv [--jobs 4]
"""
import argparse
import itertools
from multiprocessing import Pool

import numpy as np
import pandas as pd

from backtest_ema_macd import load
from test_rsi2_dip import resample, rma, rsi

FEE = 0.06
RULES = dict(target=0.10, max_loss=0.06, daily=0.03)
TRAIN_STARTS = pd.date_range("2020-04-01", "2023-06-30", freq="14D", tz="UTC")
VAL_STARTS = pd.date_range("2024-01-01", "2025-10-01", freq="14D", tz="UTC")
TRAIN_END = pd.Timestamp("2023-12-31 23:59", tz="UTC")

GRID = dict(tf=["1h", "2h", "3h", "4h", "6h"], rsi_len=[2, 3], rsi_buy=[5, 10, 15, 20], trend=[50, 100, 200],
            regime=[False, True], stop=[1.5, 2.0, 3.0], exit=["time", "sma5", "rsi70"], hold_h=[48, 96])

_DATA = {}


def prepare(raw):
    daily = raw.c.resample("1D").last()
    regime_ok = (daily > daily.rolling(200).mean()).shift(1)  # yesterday's close vs its 200-day SMA
    for tf in GRID["tf"]:
        df = resample(raw, tf)
        tr = pd.concat([df.h - df.l, (df.h - df.c.shift()).abs(), (df.l - df.c.shift()).abs()], axis=1).max(axis=1)
        _DATA[tf] = dict(df=df, atr=rma(tr, 14).to_numpy(), sma5=df.c.rolling(5).mean().to_numpy(),
                         rsi={n: rsi(df.c, n).to_numpy() for n in GRID["rsi_len"]},
                         ema={n: df.c.ewm(span=n, adjust=False).mean().to_numpy() for n in GRID["trend"]},
                         regime=regime_ok.reindex(df.index.floor("D")).fillna(False).to_numpy().astype(bool),
                         rsi2=rsi(df.c, 2).to_numpy())


def trades_for(p):
    d = _DATA[p["tf"]]
    df = d["df"]
    O, H, L, C = (df[k].to_numpy() for k in "ohlc")
    r, e, atr = d["rsi"][p["rsi_len"]], d["ema"][p["trend"]], d["atr"]
    sig = (r < p["rsi_buy"]) & (C > e)
    if p["regime"]:
        sig &= d["regime"]
    bar_h = pd.Timedelta(p["tf"]).total_seconds() / 3600
    max_bars = max(1, round(p["hold_h"] / bar_h))
    out, i, n = [], 0, len(C)
    t = df.index
    while i < n - 2:
        if not sig[i] or np.isnan(atr[i]):
            i += 1
            continue
        j = i + 1  # fill at next open
        entry = O[j]
        stop = entry - p["stop"] * atr[i]
        stop_pct = p["stop"] * atr[i] / entry
        worst, k, px = min(0.0, L[j] / entry - 1), j, None
        held = 1
        while px is None and k < n - 1:
            exit_now = held >= max_bars or (p["exit"] == "sma5" and C[k] > d["sma5"][k]) or \
                (p["exit"] == "rsi70" and d["rsi2"][k] > 70)
            if exit_now:
                px = O[k + 1]
                k += 1
                break
            k += 1
            held += 1
            if L[k] <= stop:
                px = min(O[k], stop)
                worst = min(worst, px / entry - 1)
                break
            worst = min(worst, L[k] / entry - 1)
        if px is None:
            break
        ret = (px * (1 - FEE / 100)) / (entry * (1 + FEE / 100)) - 1
        out.append((t[j], ret, worst - 2 * FEE / 100, stop_pct))
        i = k
    return out


def attempt(days, R, W, SP, i0, s0, end=None, frac=0.25, cap=0.022, max_x=1.5):
    bal, day, day_open = 1.0, None, 1.0
    for idx in range(i0, len(R)):
        d = days[idx]
        if end is not None and d > end:
            return "open", None
        if d != day:
            day_open, day = bal, d
        buf = bal - (1 - RULES["max_loss"])
        left = day_open * (RULES["daily"] - 0.002) - max(day_open - bal, 0)
        risk = min(frac * buf, cap * bal, left)
        if risk <= 0:
            continue
        size = min(risk / SP[idx], max_x)
        if bal + size * W[idx] <= 1 - RULES["max_loss"] or bal + size * W[idx] <= day_open * (1 - RULES["daily"]):
            return "fail", None
        bal += size * R[idx]
        if bal >= 1 + RULES["target"]:
            return "pass", (d - s0).days
    return "open", None


def evaluate(p, frac=0.25):
    tr = trades_for(p)
    if len(tr) < 20:
        return None
    days = pd.DatetimeIndex([x[0] for x in tr]).floor("D")
    R, W, SP = (np.array([x[k] for x in tr]) for k in (1, 2, 3))
    res = {}
    for name, starts, end in (("train", TRAIN_STARTS, TRAIN_END), ("val", VAL_STARTS, None)):
        outs = [attempt(days, R, W, SP, days.searchsorted(s), s, end, frac) for s in starts]
        passed = [o[1] for o in outs if o[0] == "pass"]
        res[f"{name}_pass"] = 100 * len(passed) / len(outs)
        res[f"{name}_fail"] = 100 * sum(o[0] == "fail" for o in outs) / len(outs)
        res[f"{name}_days"] = float(np.median(passed)) if passed else np.nan
    pre = days < TRAIN_END
    res["trades_per_month"] = len(tr) / (6.6 * 12)
    res["train_avg_ret"] = 100 * R[pre].mean() if pre.any() else np.nan
    return {**p, **res}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("klines")
    ap.add_argument("--jobs", type=int, default=4)
    a = ap.parse_args()
    raw = load(a.klines).loc["2019-06-01":]
    prepare(raw)
    combos = [dict(zip(GRID, c)) for c in itertools.product(*GRID.values())]
    with Pool(a.jobs, initializer=prepare, initargs=(raw,)) as pool:
        rows = [r for r in pool.map(evaluate, combos, chunksize=20) if r]
    res = pd.DataFrame(rows)
    res.to_pickle(a.klines.rsplit("/", 1)[0] + "/rsi2_tuner.pkl")
    pd.set_option("display.width", 250)
    cols = list(GRID) + ["trades_per_month", "train_pass", "train_fail", "train_days", "val_pass", "val_fail", "val_days"]
    print(f"{len(res)} configurations evaluated\n")
    base = res[(res.tf == "2h") & (res.rsi_len == 2) & (res.rsi_buy == 10) & (res.trend == 50) & (~res.regime)
               & (res.stop == 2.0) & (res.exit == "time") & (res.hold_h == 96)]
    print("Your current settings:")
    print(base[cols].round(1).to_string(index=False))
    print("\nTop 20 by TRAIN pass rate (validation never used for ranking):")
    print(res.sort_values(["train_pass", "train_days"], ascending=[False, True])[cols].head(20).round(1).to_string(index=False))
    print("\nMedian validation pass rate by setting (robustness view):")
    for k in GRID:
        print(f"  {k:8s}", res.groupby(k).val_pass.median().round(0).to_dict())


if __name__ == "__main__":
    main()
