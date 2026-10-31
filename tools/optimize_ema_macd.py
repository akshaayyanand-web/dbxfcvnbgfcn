"""Grid-search the EMA/MACD strategy on one symbol with an out-of-sample check.

Parameters are ranked on the training window only; the test window is never used for
selection, so its numbers are an honest estimate of how the chosen settings would have done.

Usage: python3 optimize_ema_macd.py BTCUSDT-5m.csv [--fee 0.05] [--top 15]
"""
import argparse
import itertools
import time
from types import SimpleNamespace

import pandas as pd

from backtest_ema_macd import load, run

BASE = dict(capital=10000, slip=0.01, risk=1.0, max_lev=1.0, day_loss=5.0, fast=20, slow=50,
            near=0.15, buf=0.05, max_risk=1.5)
GRID = dict(tf=["5min", "15min", "1h"], rr=[1.5, 2.0, 3.0], win=[3, 6, 12], pattern=[True, False],
            vol_mult=[1.0, 1.5], swing=[5, 10, 20], trend_len=[100, 200], min_risk=[0.25, 0.5])


def resample(df, tf):
    if tf == "5min":
        return df
    return df.resample(tf).agg({"o": "first", "h": "max", "l": "min", "c": "last", "v": "sum"}).dropna()


def stats(eq, tr, capital):
    if tr.empty:
        return dict(n=0, ret=0.0, pf=0.0, dd=0.0, win=0.0)
    curve = capital + tr.pnl.cumsum()
    dd = ((curve.cummax() - curve) / curve.cummax()).max() * 100
    gains, losses = tr.pnl[tr.pnl > 0].sum(), -tr.pnl[tr.pnl <= 0].sum()
    return dict(n=len(tr), ret=100 * (eq / capital - 1), pf=gains / losses if losses else 99.0,
                dd=dd, win=100 * (tr.pnl > 0).mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("klines")
    ap.add_argument("--fee", type=float, default=0.05)
    ap.add_argument("--train", default="2025-01-01:2025-12-31")
    ap.add_argument("--test", default="2026-01-01:2026-12-31")
    ap.add_argument("--min-trades", type=int, default=25)
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    (tr0, tr1), (te0, _) = a.train.split(":"), a.test.split(":")

    raw = load(a.klines)
    frames = {tf: resample(raw, tf) for tf in GRID["tf"]}
    keys = list(GRID)
    rows, t0 = [], time.time()
    for combo in itertools.product(*GRID.values()):
        g = dict(zip(keys, combo))
        df = frames[g["tf"]]
        p = SimpleNamespace(**BASE, **{k: v for k, v in g.items() if k != "tf"}, fee=a.fee)
        p.start = tr0
        s_tr = stats(*run(df.loc[:tr1], p), p.capital)
        p.start = te0
        s_te = stats(*run(df, p), p.capital)
        rows.append({**g, **{f"train_{k}": v for k, v in s_tr.items()}, **{f"test_{k}": v for k, v in s_te.items()}})
    res = pd.DataFrame(rows)
    print(f"{len(res)} combinations in {time.time() - t0:.0f}s, fee {a.fee}%/side\n")
    if a.out:
        res.to_csv(a.out, index=False)

    ok = res[res.train_n >= a.min_trades].sort_values("train_ret", ascending=False)
    cols = keys + ["train_n", "train_win", "train_pf", "train_ret", "train_dd", "test_n", "test_pf", "test_ret", "test_dd"]
    pd.set_option("display.width", 250)
    print(f"Top {a.top} by TRAINING return (min {a.min_trades} trades) and how they did on unseen TEST data:")
    print(ok[cols].head(a.top).round(2).to_string(index=False))
    print(f"\nShare of all combos profitable: train {100 * (res.train_ret > 0).mean():.0f}%, "
          f"test {100 * (res.test_ret > 0).mean():.0f}%")
    top = ok.head(a.top)
    print(f"Top-{a.top} (train-selected) average test return {top.test_ret.mean():+.1f}%, "
          f"profitable on test: {(top.test_ret > 0).sum()}/{len(top)}")
    print("Correlation of train vs test return across all combos: "
          f"{res[['train_ret', 'test_ret']].corr().iloc[0, 1]:.2f}")


if __name__ == "__main__":
    main()
