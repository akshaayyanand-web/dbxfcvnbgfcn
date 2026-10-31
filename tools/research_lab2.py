"""Second research round: five pre-chosen strategy families on Binance 1h klines.

  trend_ens   average of 6 EMA/Donchian trend signals, sized to a target volatility
  seasonal    long/short only in UTC hour-of-week buckets that were significant in TRAIN data
  crash_rev   fade 1h moves larger than k standard deviations, hold H hours
  vol_break   intraday breakout of daily open +/- k * previous day's range, flat at day end
  ethbtc      mean reversion of the ETH/BTC ratio z-score (long one leg, short the other)

Parameters (and the seasonal buckets) come from the TRAIN window only; TEST is reported as-is.
Usage: python3 research_lab2.py DATA_DIR [--fee 0.07]   (DATA_DIR holds BTCUSDT.csv etc., 1h)
"""
import argparse
import itertools
import os

import numpy as np
import pandas as pd

from backtest_ema_macd import ema, load
from strategy_lab import resample

SYMS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


def bar_returns(df):
    return (df.o.shift(-1) / df.o - 1).fillna(0)


def run_pos(df, pos, fee):
    """Position decided at bar close is held from the next open. Returns per-bar return series."""
    p = pos.shift(1).fillna(0)
    return p * bar_returns(df) - p.diff().abs().fillna(p.abs()) * fee / 100


def stats(r, bpy):
    if len(r) < 50 or r.std() == 0:
        return dict(year=0.0, dd=0.0, sharpe=0.0)
    eq = (1 + r).clip(lower=0).cumprod()
    years = len(r) / bpy
    total = eq.iloc[-1]
    return dict(year=(total ** (1 / years) - 1) * 100 if total > 0 else -100.0,
                dd=((eq.cummax() - eq) / eq.cummax()).max() * 100,
                sharpe=r.mean() / r.std() * np.sqrt(bpy))


def vol_scale(df, target, cap, bpy):
    vol = df.c.pct_change().rolling(int(bpy / 365 * 30)).std() * np.sqrt(bpy)
    return (target / 100 / vol).clip(upper=cap).fillna(0)


def trend_ens(df, train_end, tf, target, shorts, bpy):
    c = df.c
    sigs = [np.sign(ema(c, f) - ema(c, s)) for f, s in ((10, 50), (20, 100), (50, 200))]
    for n in (20, 55, 100):
        hi, lo = df.h.rolling(n).max().shift(), df.l.rolling(n).min().shift()
        mid = (hi + lo) / 2
        sigs.append(np.sign(c - mid))
    s = sum(sigs) / len(sigs)
    if not shorts:
        s = s.clip(lower=0)
    return s * vol_scale(df, target, 3.0, bpy)


def seasonal(df, train_end, tmin, shorts):
    r = df.c.pct_change()
    key = df.index.dayofweek * 24 + df.index.hour
    tr = r.loc[:train_end]
    g = tr.groupby(key[: len(tr)])
    t = g.mean() / g.std() * np.sqrt(g.count())
    longs, shorts_set = set(t[t > tmin].index), set(t[t < -tmin].index) if shorts else set()
    # position for the NEXT bar's hour: decide at close of bar i for bar i+1
    nxt = pd.Series(key, index=df.index).shift(-1)
    return nxt.map(lambda k: 1.0 if k in longs else -1.0 if k in shorts_set else 0.0).fillna(0)


def crash_rev(df, train_end, k, hold_h, shorts):
    r = df.c.pct_change()
    sd = r.rolling(24 * 30).std()
    ent_long = (r < -k * sd).astype(float)
    ent_short = (r > k * sd).astype(float) if shorts else 0 * ent_long
    raw = ent_long - ent_short
    if hold_h == 1:
        return raw.fillna(0)
    # hold for hold_h bars after the signal bar
    return raw.replace(0, np.nan).ffill(limit=hold_h - 1).fillna(0)


def vol_break(df, train_end, k, shorts, trend):
    day = df.index.floor("D")
    d_open = df.o.groupby(day).transform("first")
    d = df.resample("1D").agg({"h": "max", "l": "min", "c": "last"})
    prev_rng = (d.h - d.l).shift(1).reindex(day).to_numpy()
    up, dn = d_open + k * prev_rng, d_open - k * prev_rng
    dc = d.c.reindex(day).to_numpy()
    ema_d = pd.Series(ema(d.c, 50).shift(1).reindex(day).to_numpy(), index=df.index)
    long_ok = (df.c > ema_d) if trend else True
    short_ok = (df.c < ema_d) if trend else True
    sig = pd.Series(np.where((df.c > up) & long_ok, 1.0, np.where((df.c < dn) & short_ok & shorts, -1.0, np.nan)), index=df.index)
    pos = sig.groupby(day).ffill().fillna(0)  # stay in once triggered, reset each day
    last_bar = pd.Series(df.index, index=df.index).groupby(day).transform("max") == df.index
    return pos.where(~last_bar, 0)


def ethbtc(eth, btc, look, z_in, fee):
    idx = eth.index.intersection(btc.index)
    eth, btc = eth.loc[idx], btc.loc[idx]
    lr = np.log(eth.c / btc.c)
    z = (lr - lr.rolling(look).mean()) / lr.rolling(look).std()
    pos, p = np.zeros(len(z)), 0
    zz = z.to_numpy()
    for i in range(len(zz)):
        if p == 0 and zz[i] > z_in:
            p = -1
        elif p == 0 and zz[i] < -z_in:
            p = 1
        elif p == 1 and zz[i] >= 0 or p == -1 and zz[i] <= 0:
            p = 0
        pos[i] = p
    pos = pd.Series(pos, index=idx)
    # +1 = long ETH / short BTC, half the capital in each leg
    return 0.5 * run_pos(eth, pos, fee) + 0.5 * run_pos(btc, -pos, fee)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data_dir")
    ap.add_argument("--fee", type=float, default=0.07)
    ap.add_argument("--train-end", default="2024-12-31")
    ap.add_argument("--test-start", default="2025-01-01")
    a = ap.parse_args()
    raw = {s: load(os.path.join(a.data_dir, s + ".csv")).loc["2020-06-01":] for s in SYMS}
    tr0, tr1, te0 = "2021-01-01", a.train_end, a.test_start

    rows = []

    def record(family, params, rets_by_sym, bpy):
        tr = [stats(r.loc[tr0:tr1], bpy) for r in rets_by_sym.values()]
        te = [stats(r.loc[te0:], bpy) for r in rets_by_sym.values()]
        rows.append(dict(family=family, params=params,
                         train_sharpe=np.mean([x["sharpe"] for x in tr]), train_year=np.mean([x["year"] for x in tr]),
                         test_sharpe=np.mean([x["sharpe"] for x in te]), test_year=np.mean([x["year"] for x in te]),
                         test_dd=np.mean([x["dd"] for x in te]),
                         **{f"{s[:3]}_test_year": x["year"] for s, x in zip(rets_by_sym, te)}))

    for tf, target, shorts in itertools.product(["4h", "1d"], [20, 40, 60], [False, True]):
        frames = {s: resample(d, tf) for s, d in raw.items()}
        bpy = 365 * (6 if tf == "4h" else 1)
        record("trend_ens", dict(tf=tf, vol=target, shorts=shorts),
               {s: run_pos(f, trend_ens(f, tr1, tf, target, shorts, bpy), a.fee) for s, f in frames.items()}, bpy)
    for tmin, shorts in itertools.product([2.0, 2.5, 3.0], [False, True]):
        record("seasonal", dict(t=tmin, shorts=shorts),
               {s: run_pos(f, seasonal(f, tr1, tmin, shorts), a.fee) for s, f in raw.items()}, 365 * 24)
    for k, h, shorts in itertools.product([2.5, 3.5, 5.0], [1, 3, 6, 12, 24], [False, True]):
        record("crash_rev", dict(k=k, hold=h, shorts=shorts),
               {s: run_pos(f, crash_rev(f, tr1, k, h, shorts), a.fee) for s, f in raw.items()}, 365 * 24)
    for k, shorts, trend in itertools.product([0.3, 0.5, 0.7, 1.0], [False, True], [False, True]):
        record("vol_break", dict(k=k, shorts=shorts, trend=trend),
               {s: run_pos(f, vol_break(f, tr1, k, shorts, trend), a.fee) for s, f in raw.items()}, 365 * 24)
    for look, z in itertools.product([24 * 7, 24 * 14, 24 * 30], [1.5, 2.0, 2.5]):
        r = ethbtc(raw["ETHUSDT"], raw["BTCUSDT"], look, z, a.fee)
        record("ethbtc", dict(look_h=look, z=z), {"ETHBTC": r}, 365 * 24)

    res = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 50)
    print(f"{len(res)} configurations, fee {a.fee}%/side. Train 2021-2024, test 2025-Oct 2026.\n")
    print("Best 3 per family by TRAIN Sharpe, with unseen TEST results (yearly %, averaged over coins):")
    best = res.sort_values("train_sharpe", ascending=False).groupby("family").head(3)
    print(best.round(2).to_string(index=False))
    print("\nShare of configs with positive TEST return by family:")
    print(res.assign(pos=res.test_year > 0).groupby("family").pos.mean().mul(100).round(0).to_string())
    res.to_pickle(os.path.join(a.data_dir, "lab2_results.pkl"))


if __name__ == "__main__":
    main()
