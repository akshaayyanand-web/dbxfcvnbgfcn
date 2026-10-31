"""Cross-sectional momentum (coin rotation) lab on Binance daily klines.

Every R days, rank all coins with enough history by their L-day return and hold the top K
(equal weight). Variants: long-only, long-only only while BTC is above its F-day SMA (else cash),
and long top K / short bottom K. Signals use the daily close; trades fill at the next day's open.
Parameter sets are ranked on the TRAIN window and reported on the unseen TEST window.

Usage: python3 xsmom_lab.py DATA_DIR [--fee 0.1]   (DATA_DIR holds BTC.csv, ETH.csv, ...)
"""
import argparse
import glob
import itertools
import os

import numpy as np
import pandas as pd

from backtest_ema_macd import load

CUTOFF = {"LUNA": "2022-05-13"}  # original LUNA collapsed; the ticker was later reused by a new token


def panel(data_dir):
    opens, closes = {}, {}
    for path in sorted(glob.glob(os.path.join(data_dir, "*.csv"))):
        name = os.path.basename(path)[:-4]
        if "-" in name:
            continue
        df = load(path)
        if name in CUTOFF:
            df = df.loc[:CUTOFF[name]]
        opens[name], closes[name] = df.o, df.c
    return pd.DataFrame(opens).sort_index(), pd.DataFrame(closes).sort_index()


def weights(closes, look, k, every, mode, sma):
    mom = closes / closes.shift(look) - 1
    btc_up = closes["BTC"] > closes["BTC"].rolling(sma).mean()
    w = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)
    last = None
    for i, t in enumerate(closes.index):
        if i % every == 0 or last is None:
            m = mom.loc[t].dropna()
            row = pd.Series(0.0, index=closes.columns)
            if len(m) >= 2 * k:
                ranked = m.sort_values()
                if mode == "long_short":
                    row[ranked.index[-k:]] = 0.5 / k
                    row[ranked.index[:k]] = -0.5 / k
                elif mode == "long" or (mode == "long_btc_filter" and btc_up.loc[t]):
                    row[ranked.index[-k:]] = 1.0 / k
            last = row
        w.loc[t] = last
    return w


def backtest(opens, closes, w, fee):
    """Weights set at day t's close are held from day t+1's open to day t+2's open."""
    r = (opens.shift(-1) / opens - 1).fillna(0)
    held = w.shift(1).fillna(0)
    gross = (held * r).sum(axis=1)
    turnover = held.diff().abs().sum(axis=1).fillna(held.abs().sum(axis=1))
    return (1 + gross - turnover * fee / 100).clip(lower=0).cumprod()


def stats(eq):
    if len(eq) < 30:
        return dict(month=np.nan, year=np.nan, dd=np.nan, sharpe=np.nan)
    rets = eq.pct_change().fillna(0)
    total = eq.iloc[-1] / eq.iloc[0]
    years = len(eq) / 365
    return dict(month=(total ** (1 / (12 * years)) - 1) * 100, year=(total ** (1 / years) - 1) * 100,
                dd=((eq.cummax() - eq) / eq.cummax()).max() * 100,
                sharpe=rets.mean() / rets.std() * np.sqrt(365) if rets.std() > 0 else 0.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data_dir")
    ap.add_argument("--fee", type=float, default=0.1, help="%% per side incl. slippage")
    ap.add_argument("--train", default="2021-01-01:2024-12-31")
    ap.add_argument("--test", default="2025-01-01:2026-12-31")
    ap.add_argument("--top", type=int, default=12)
    a = ap.parse_args()
    (tr0, tr1), (te0, te1) = a.train.split(":"), a.test.split(":")
    opens, closes = panel(a.data_dir)
    print(f"{closes.shape[1]} coins, {closes.index[0].date()} .. {closes.index[-1].date()}, fee {a.fee}%/side\n")

    grid = dict(look=[7, 14, 30, 60, 90], k=[1, 3, 5], every=[1, 3, 7],
                mode=["long", "long_btc_filter", "long_short"], sma=[50, 100])
    rows = []
    for look, k, every, mode, sma in itertools.product(*grid.values()):
        if mode != "long_btc_filter" and sma != 50:
            continue
        eq = backtest(opens, closes, weights(closes, look, k, every, mode, sma), a.fee)
        tr, te = stats(eq.loc[tr0:tr1]), stats(eq.loc[te0:te1])
        rows.append(dict(look=look, k=k, every=every, mode=mode, sma=sma if mode == "long_btc_filter" else "",
                         **{f"train_{x}": v for x, v in tr.items()}, **{f"test_{x}": v for x, v in te.items()}))
    res = pd.DataFrame(rows).sort_values("train_sharpe", ascending=False)
    pd.set_option("display.width", 220)
    print("Top by TRAIN Sharpe (2021-2024) and the same settings on unseen TEST data (2025-Oct 2026):")
    print(res.head(a.top).round(2).to_string(index=False))
    print("\nBest of each mode by train Sharpe:")
    print(res.groupby("mode").head(1).round(2).to_string(index=False))
    btc = closes["BTC"].loc[te0:te1]
    print(f"\nBTC buy & hold on test: {100 * (btc.iloc[-1] / btc.iloc[0] - 1):+.0f}%")
    res.to_pickle(os.path.join(a.data_dir, "xsmom_results.pkl"))


if __name__ == "__main__":
    main()
