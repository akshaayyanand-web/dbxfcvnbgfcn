"""Third research round: wider universe + portfolio construction.

Families (run on every coin, results averaged across coins):
  vol_break   intraday breakout of session open +/- k * previous session range; sessions start at
              an anchor hour (0 = Asia, 8 = Europe, 13 = US) and positions are closed at session end
  trend_ens   6 averaged EMA/Donchian trend signals on 4h, sized to a target volatility
  bb_squeeze  Bollinger band breakout after the band width hits an N-bar low, exit at the middle band

The parameter set per family is chosen on 2021-2024 only. The chosen sets are then combined into a
risk-balanced portfolio (weights from 2021-2024 volatility) and reported on 2025 and 2026 separately.
Usage: python3 research_lab3.py DATA_DIR
"""
import argparse
import glob
import itertools
import os

import numpy as np
import pandas as pd

from backtest_ema_macd import load
from research_lab2 import run_pos, trend_ens
from strategy_lab import resample

TRAIN = ("2021-01-01", "2024-12-31")


def vol_break(df, k, anchor, shorts, trend):
    shifted = df.index - pd.Timedelta(hours=anchor)
    sess = shifted.floor("D")
    s_open = df.o.groupby(sess).transform("first")
    agg = pd.DataFrame({"h": df.h.to_numpy(), "l": df.l.to_numpy(), "c": df.c.to_numpy()}, index=shifted)
    d = agg.resample("1D").agg({"h": "max", "l": "min", "c": "last"}).dropna()
    prev_rng = (d.h - d.l).shift(1).reindex(sess).to_numpy()
    ema_d = d.c.ewm(span=50, adjust=False).mean().shift(1).reindex(sess).to_numpy()
    up, dn = s_open + k * prev_rng, s_open - k * prev_rng
    long_ok = (df.c > ema_d) if trend else True
    short_ok = (df.c < ema_d) if trend else True
    sig = np.where((df.c > up) & long_ok, 1.0, np.where((df.c < dn) & short_ok & shorts, -1.0, np.nan))
    pos = pd.Series(sig, index=df.index).groupby(sess).ffill().fillna(0)
    last_bar = pd.Series(df.index, index=df.index).groupby(sess).transform("max") == df.index
    return pos.where(~last_bar, 0)


def bb_squeeze(df, n, shorts):
    mid = df.c.rolling(20).mean()
    sd = df.c.rolling(20).std()
    up, lo = mid + 2 * sd, mid - 2 * sd
    width = (up - lo) / mid
    squeezed = (width <= width.rolling(n).min() * 1.1).rolling(5).max().astype(bool)
    el, es = squeezed & (df.c > up), squeezed & (df.c < lo) & shorts
    c, m = df.c.to_numpy(), mid.to_numpy()
    ela, esa = el.to_numpy(), es.to_numpy()
    pos, p = np.zeros(len(c)), 0
    for i in range(len(c)):
        if p == 1 and c[i] < m[i] or p == -1 and c[i] > m[i]:
            p = 0
        if p == 0:
            p = 1 if ela[i] else -1 if esa[i] else 0
        pos[i] = p
    return pd.Series(pos, index=df.index)


def daily(r):
    return (1 + r).groupby(r.index.floor("D")).prod() - 1


def stats(r):
    r = r.dropna()
    if len(r) < 30 or r.std() == 0:
        return dict(year=np.nan, dd=np.nan, sharpe=np.nan)
    eq = (1 + r).clip(lower=0).cumprod()
    yrs = len(r) / 365
    return dict(year=(eq.iloc[-1] ** (1 / yrs) - 1) * 100 if eq.iloc[-1] > 0 else -100.0,
                dd=((eq.cummax() - eq) / eq.cummax()).max() * 100, sharpe=r.mean() / r.std() * np.sqrt(365))


def family_runs(coins, fee):
    """Yield (family, params, daily return of the equal-weight average across coins)."""
    h4 = {s: resample(d, "4h") for s, d in coins.items()}
    for k, anchor, shorts, trend in itertools.product([0.5, 0.7, 1.0], [0, 8, 13], [False, True], [False, True]):
        rs = [daily(run_pos(d, vol_break(d, k, anchor, shorts, trend), fee)) for d in coins.values()]
        yield "vol_break", dict(k=k, anchor=anchor, shorts=shorts, trend=trend), pd.concat(rs, axis=1).mean(axis=1)
    for target, shorts in itertools.product([20, 40], [False, True]):
        rs = [daily(run_pos(d, trend_ens(d, None, "4h", target, shorts, 6 * 365), fee)) for d in h4.values()]
        yield "trend_ens", dict(vol=target, shorts=shorts), pd.concat(rs, axis=1).mean(axis=1)
    for tf, n, shorts in itertools.product(["1h", "4h"], [50, 100], [False, True]):
        frames = coins if tf == "1h" else h4
        rs = [daily(run_pos(d, bb_squeeze(d, n, shorts), fee)) for d in frames.values()]
        yield "bb_squeeze", dict(tf=tf, n=n, shorts=shorts), pd.concat(rs, axis=1).mean(axis=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data_dir")
    ap.add_argument("--fee", type=float, default=0.07)
    ap.add_argument("--funding", type=float, default=5.0, help="yearly %% paid on leveraged exposure")
    a = ap.parse_args()
    coins = {os.path.basename(p)[:-4]: load(p).loc["2020-06-01":]
             for p in sorted(glob.glob(os.path.join(a.data_dir, "*USDT.csv")))}
    print(f"{len(coins)} coins: {', '.join(c[:-4] for c in coins)}\n")

    rows, series = [], {}
    for fam, params, r in family_runs(coins, a.fee):
        key = f"{fam} {params}"
        series[key] = r
        rows.append(dict(family=fam, params=params, key=key,
                         **{f"train_{x}": v for x, v in stats(r.loc[TRAIN[0]:TRAIN[1]]).items()},
                         **{f"y2025_{x}": v for x, v in stats(r.loc["2025"]).items()},
                         **{f"y2026_{x}": v for x, v in stats(r.loc["2026"]).items()}))
    res = pd.DataFrame(rows).sort_values("train_sharpe", ascending=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 70)
    cols = ["family", "params", "train_sharpe", "train_year", "y2025_year", "y2025_dd", "y2026_year", "y2026_dd"]
    print("Top 4 per family by TRAIN Sharpe (2021-2024); 2025 and 2026 are unseen:")
    print(res.groupby("family").head(4)[cols].round(2).to_string(index=False))

    picks = res.groupby("family").head(1)
    picks = picks[picks.train_sharpe > 0.5]
    # extra vol_break anchors (different sessions trade at different times), best train Sharpe per anchor
    vb = res[res.family == "vol_break"].copy()
    vb["anchor"] = vb.params.map(lambda p: p["anchor"])
    picks = pd.concat([picks, vb.groupby("anchor").head(1)]).drop_duplicates("key")
    P = pd.concat({k: series[k] for k in picks.key}, axis=1).fillna(0)
    print("\nPortfolio components (chosen on train only):")
    for k in P:
        print("  ", k)
    print("\nDaily correlation of components (2025-2026):")
    print(P.loc["2025":].corr().round(2).to_string())
    w = 1 / P.loc[TRAIN[0]:TRAIN[1]].std()
    w = w / w.sum()
    port = (P * w).sum(axis=1)
    print("\nPortfolio (risk-balanced on 2021-2024 volatility):")
    for lev in (1, 3, 5):
        r = port * lev - a.funding / 100 / 365 * lev * 0.5  # funding on roughly half of the book being long
        for label, sl in (("train 21-24", slice(*TRAIN)), ("2025 unseen", "2025"), ("2026 unseen", "2026")):
            s = stats(r.loc[sl])
            m = (1 + r.loc[sl]).groupby(r.loc[sl].index.to_period("M")).prod() - 1
            print(f"  {lev}x {label}: {s['year']:+7.1f}%/yr  maxDD {s['dd']:5.1f}%  Sharpe {s['sharpe']:4.2f}  "
                  f"months up {100 * (m > 0).mean():3.0f}%  worst month {100 * m.min():+5.1f}%")
    port.to_pickle(os.path.join(a.data_dir, "lab3_portfolio.pkl"))
    P.to_pickle(os.path.join(a.data_dir, "lab3_components.pkl"))


if __name__ == "__main__":
    main()
