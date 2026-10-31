"""Compare strategy families on Binance 1h klines with a train / unseen-test split.

Families: Donchian breakout (trend), time-series momentum, EMA crossover, RSI(2) mean reversion.
Every parameter set is run on all symbols; sets are ranked by their average TRAIN Sharpe ratio,
then reported on the TEST window that played no part in the choice.

Usage: python3 strategy_lab.py BTCUSDT.csv ETHUSDT.csv SOLUSDT.csv [--fee 0.07]
"""
import argparse
import itertools

import numpy as np
import pandas as pd

from backtest_ema_macd import ema, load

TF = {"1h": "1h", "4h": "4h", "1d": "1D"}


def resample(df, tf):
    if tf == "1h":
        return df
    return df.resample(TF[tf]).agg({"o": "first", "h": "max", "l": "min", "c": "last", "v": "sum"}).dropna()


def rsi(c, n):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def hold(enter_long, exit_long, enter_short, exit_short):
    """Turn entry/exit booleans into a -1/0/+1 position held between signals."""
    el, xl, es, xs = (x.to_numpy() for x in (enter_long, exit_long, enter_short, exit_short))
    pos = np.zeros(len(el))
    p = 0
    for i in range(len(el)):
        if p == 1 and xl[i]:
            p = 0
        elif p == -1 and xs[i]:
            p = 0
        if p == 0:
            p = 1 if el[i] else -1 if es[i] else 0
        pos[i] = p
    return pd.Series(pos, index=enter_long.index)


def donchian(df, n, m, shorts):
    hi, lo = df.h.rolling(n).max().shift(), df.l.rolling(n).min().shift()
    xhi, xlo = df.h.rolling(m).max().shift(), df.l.rolling(m).min().shift()
    no = pd.Series(False, index=df.index)
    return hold(df.c > hi, df.c < xlo, (df.c < lo) if shorts else no, df.c > xhi)


def tsmom(df, look, shorts):
    r = df.c / df.c.shift(look) - 1
    return np.sign(r).clip(lower=-1 if shorts else 0).fillna(0)


def ema_cross(df, fast, slow, shorts):
    d = np.sign(ema(df.c, fast) - ema(df.c, slow))
    return d.clip(lower=-1 if shorts else 0)


def rsi2(df, entry, trend, shorts):
    r, t, e5 = rsi(df.c, 2), ema(df.c, trend), ema(df.c, 5)
    no = pd.Series(False, index=df.index)
    return hold((df.c > t) & (r < entry), df.c > e5,
                ((df.c < t) & (r > 100 - entry)) if shorts else no, df.c < e5)


FAMILIES = {
    "donchian": (donchian, dict(n=[20, 55, 100], m=[10, 20, 50], shorts=[False, True])),
    "tsmom": (tsmom, dict(look=[24, 72, 168, 336], shorts=[False, True])),
    "ema_cross": (ema_cross, dict(fast=[10, 20, 50], slow=[50, 100, 200], shorts=[False, True])),
    "rsi2": (rsi2, dict(entry=[5, 10, 20], trend=[100, 200], shorts=[False, True])),
}


def equity(df, pos, fee, lev=1.0):
    """Signal on bar close -> position from next bar's open. Returns per-bar equity multipliers."""
    p = pos.shift(1).fillna(0) * lev
    r = df.o.shift(-1) / df.o - 1
    cost = p.diff().abs().fillna(p.abs()) * fee / 100
    step = (1 + p * r.fillna(0) - cost).clip(lower=0)
    return step.cumprod()


def metrics(eq, bars_per_year, turns):
    if len(eq) < 2:
        return dict(month=0.0, dd=0.0, sharpe=0.0, trades=0)
    rets = eq.pct_change().fillna(0)
    years = len(eq) / bars_per_year
    total = eq.iloc[-1] / eq.iloc[0]
    month = (total ** (1 / (years * 12)) - 1) * 100 if total > 0 else -100.0
    dd = ((eq.cummax() - eq) / eq.cummax()).max() * 100
    sharpe = rets.mean() / rets.std() * np.sqrt(bars_per_year) if rets.std() > 0 else 0.0
    return dict(month=month, dd=dd, sharpe=sharpe, trades=int(turns))


def evaluate(frames, fn, params, fee, window, lev=1.0):
    out = {}
    for sym, df in frames.items():
        pos = fn(df, **params)
        eq = equity(df, pos, fee, lev).loc[window[0]:window[1]]
        bpy = 365 * 24 / (df.index[1] - df.index[0]).total_seconds() * 3600
        turns = (pos.loc[window[0]:window[1]].diff().abs() > 0).sum()
        out[sym] = metrics(eq, bpy, turns)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("klines", nargs="+")
    ap.add_argument("--fee", type=float, default=0.07, help="%% per side incl. slippage")
    ap.add_argument("--train", default="2021-01-01:2024-12-31")
    ap.add_argument("--test", default="2025-01-01:2026-12-31")
    ap.add_argument("--top", type=int, default=12)
    a = ap.parse_args()
    train, test = a.train.split(":"), a.test.split(":")
    raw = {p.rsplit("/", 1)[-1].split(".")[0]: load(p) for p in a.klines}

    rows = []
    for tf in TF:
        frames = {s: resample(d, tf) for s, d in raw.items()}
        for fam, (fn, grid) in FAMILIES.items():
            for combo in itertools.product(*grid.values()):
                params = dict(zip(grid, combo))
                if fam == "ema_cross" and params["fast"] >= params["slow"]:
                    continue
                if fam == "donchian" and params["m"] >= params["n"]:
                    continue
                tr = evaluate(frames, fn, params, a.fee, train)
                te = evaluate(frames, fn, params, a.fee, test)
                row = dict(tf=tf, family=fam, params=params,
                           train_sharpe=np.mean([v["sharpe"] for v in tr.values()]),
                           train_month=np.mean([v["month"] for v in tr.values()]),
                           test_sharpe=np.mean([v["sharpe"] for v in te.values()]),
                           test_month=np.mean([v["month"] for v in te.values()]),
                           test_dd=np.mean([v["dd"] for v in te.values()]),
                           test_trades_per_month=np.mean([v["trades"] for v in te.values()]) / 22)
                for s, v in te.items():
                    row[f"{s}_test_month"] = v["month"]
                    row[f"{s}_test_dd"] = v["dd"]
                rows.append(row)
    res = pd.DataFrame(rows).sort_values("train_sharpe", ascending=False)
    pd.set_option("display.width", 260)
    pd.set_option("display.max_colwidth", 60)
    print(f"{len(res)} parameter sets x {len(raw)} symbols, fee {a.fee}%/side, 1x (no leverage)\n")
    print("Top by TRAIN Sharpe (2021-2024), with results on unseen TEST data (2025-Oct 2026), averaged over symbols:")
    print(res.head(a.top).round(2).to_string(index=False))
    print("\nBest of each family (by train Sharpe):")
    print(res.groupby("family").head(1).round(2).to_string(index=False))
    res.to_pickle(a.klines[0].rsplit("/", 1)[0] + "/lab_results.pkl")


if __name__ == "__main__":
    main()
