"""Pattern mining for long scalps on 5-minute candles.

Every pattern is a condition known at a bar's close; the trade would enter at the next bar's open.
For each pattern x context filter x holding time we measure the forward return net of fees
(limit entry 0.02% + market exit 0.06%) on TRAIN (2020-2023) and TEST (2024-2026) separately.
Patterns are ranked on TRAIN only; TEST and other coins are the out-of-sample check.

Usage: python3 scalp_lab.py BTC_5m.csv
"""
import itertools
import sys

import numpy as np
import pandas as pd

from backtest_ema_macd import load
from test_rsi2_dip import rma, rsi

FEES = 0.0008
HOLDS = [6, 12, 24, 48]  # 30 min, 1 h, 2 h, 4 h


def features(df):
    o, h, l, c, v = df.o, df.h, df.l, df.c, df.v
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr = rma(tr, 14)
    body, rng = (c - o).abs(), h - l
    red = c < o
    reds = red.groupby((~red).cumsum()).cumsum()
    mid, sd = c.rolling(20).mean(), c.rolling(20).std()
    day = df.index.floor("D")
    vwap = (c * v).groupby(day).cumsum() / v.groupby(day).cumsum()
    r2, r3 = rsi(c, 2), rsi(c, 3)
    pat = {
        "rsi2<5": r2 < 5,
        "rsi2<10": r2 < 10,
        "rsi3<15": r3 < 15,
        "3 red in a row": reds >= 3,
        "5 red in a row": reds >= 5,
        "drop 30m >2 ATR": (c - c.shift(6)) < -2 * atr,
        "drop 1h >3 ATR": (c - c.shift(12)) < -3 * atr,
        "close < BB(20,2)": c < mid - 2 * sd,
        "close < BB(20,2.5)": c < mid - 2.5 * sd,
        "hammer": (rng > 0) & ((np.minimum(o, c) - l) >= 2 * body) & (c >= l + 0.6 * rng),
        "bull engulfing": (c > o) & red.shift(fill_value=False) & (c >= o.shift()) & (o <= c.shift()),
        "capitulation vol": red & (v > 3 * v.rolling(20).mean()),
        "2 ATR below VWAP": c < vwap - 2 * atr,
        "new 24h low": l <= l.rolling(288).min(),
    }
    d = c.resample("1D").last()
    crash = (d / d.shift(30) - 1 < -0.15).shift(1).reindex(day).fillna(False).to_numpy().astype(bool)
    hour = df.index.hour
    ctx = {
        "any": np.ones(len(df), bool),
        "1h trend up": (c > c.ewm(span=600, adjust=False).mean()).to_numpy(),  # ~ EMA50 of 1h candles
        "no crash": ~crash,
        "trend up & no crash": (c > c.ewm(span=600, adjust=False).mean()).to_numpy() & ~crash,
        "US session 13-21 UTC": (hour >= 13) & (hour < 21),
        "Asia 0-8 UTC": hour < 8,
    }
    return {k: v.fillna(False).to_numpy().astype(bool) for k, v in pat.items()}, ctx


def forward(df):
    o, c = df.o.to_numpy(), df.c.to_numpy()
    n = len(c)
    out = {}
    for hld in HOLDS:
        r = np.full(n, np.nan)
        e = o[1:n - hld]
        x = c[hld:n - 1]
        r[: n - hld - 1] = x / e - 1 - FEES
        out[hld] = r
    return out


def mine(df):
    pats, ctx = features(df)
    fw = forward(df)
    yrs = df.index.year.to_numpy()
    tr_m, te_m = yrs <= 2023, yrs >= 2024
    base = {h: (np.nanmean(fw[h][tr_m]), np.nanmean(fw[h][te_m])) for h in HOLDS}
    rows = []
    patlist = list(pats.items())
    combos = [((a, pa),) for a, pa in patlist] + list(itertools.combinations(patlist, 2))
    for combo in combos:
        cond = np.logical_and.reduce([p for _, p in combo])
        name = " + ".join(k for k, _ in combo)
        for cn, cm in ctx.items():
            m = cond & cm
            # one signal per cluster: skip a signal if another fired in the previous 6 bars
            idx = np.flatnonzero(m)
            if len(idx) == 0:
                continue
            keep = np.concatenate([[True], np.diff(idx) > 6])
            sel = np.zeros(len(m), bool)
            sel[idx[keep]] = True
            for h in HOLDS:
                r = fw[h]
                a, b = r[sel & tr_m], r[sel & te_m]
                a, b = a[~np.isnan(a)], b[~np.isnan(b)]
                if len(a) < 150 or len(b) < 50:
                    continue
                rows.append(dict(pattern=name, context=cn, hold_min=h * 5, n_tr=len(a), net_tr=100 * a.mean(),
                                 t_tr=a.mean() / a.std() * np.sqrt(len(a)), win_tr=100 * (a > 0).mean(),
                                 n_te=len(b), net_te=100 * b.mean(), win_te=100 * (b > 0).mean(),
                                 base_tr=100 * base[h][0], base_te=100 * base[h][1]))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    btc = load(sys.argv[1]).loc["2019-12-01":]
    res = mine(btc)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 48)
    cols = ["pattern", "context", "hold_min", "n_tr", "net_tr", "t_tr", "win_tr", "n_te", "net_te", "win_te"]
    print(f"{len(res)} pattern x context x hold combinations (net of 0.08% fees, per trade, %)\n")
    print("Unconditional average per trade (any 5m bar):",
          {h * 5: (round(100 * np.nanmean(forward(btc)[h][btc.index.year <= 2023]), 3)) for h in HOLDS})
    top = res[res.t_tr > 3].sort_values("net_tr", ascending=False)
    print(f"\nPatterns with TRAIN t-stat > 3: {len(top)}; of these positive on TEST: {(top.net_te > 0).sum()}")
    print("\nTop 25 by TRAIN net return per trade (t > 3), with TEST (2024-26):")
    print(top[cols].head(25).round(3).to_string(index=False))
    res.to_pickle(sys.argv[1].rsplit("/", 1)[0] + "/scalp_lab.pkl")
