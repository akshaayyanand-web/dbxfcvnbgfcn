"""Fourth research round: broad sweep of candlestick patterns and classic indicator systems.

Every rule runs on 1h / 4h / 1d candles of every coin, long-only, short-only and both, with and
without a 200-EMA trend filter. Signals are decided on the bar close and filled at the next open.

Selection is done in two stages that never look at the final test years:
  train      2021-2023  average Sharpe across coins must exceed 0.5
  validate   2024       average return > 0 and positive on at least 8 of 13 coins
Survivors are then reported on 2025 and 2026 (final test). A placebo of random entries with the
same holding time goes through the identical filter, showing how many "winners" luck alone gives.

Usage: python3 research_lab4.py DATA_DIR
"""
import argparse
import glob
import itertools
import os

import numpy as np
import pandas as pd

from backtest_ema_macd import ema, load
from strategy_lab import resample, rsi

FEE = 0.07
BPY = {"1h": 365 * 24, "4h": 365 * 6, "1d": 365}
PERIODS = {"train": ("2021-01-01", "2023-12-31"), "val": ("2024-01-01", "2024-12-31"),
           "y2025": ("2025-01-01", "2025-12-31"), "y2026": ("2026-01-01", "2026-12-31")}


def state(enter, exit_):
    """1 from an entry until the next exit (vectorised position holding)."""
    s = pd.Series(np.where(enter, 1.0, np.where(exit_, 0.0, np.nan)), index=enter.index)
    return s.ffill().fillna(0)


def hold_for(sig, h):
    return sig.astype(float).rolling(h, min_periods=1).max()


def candle_signals(d):
    o, h, l, c = d.o, d.h, d.l, d.c
    body, rng = (c - o).abs(), h - l
    lw, uw = np.minimum(o, c) - l, h - np.maximum(o, c)
    green, red = c > o, c < o
    inside_prev = (h.shift() < h.shift(2)) & (l.shift() > l.shift(2))
    doji_prev = (body.shift() < 0.1 * rng.shift())
    return {
        "engulfing": (green & red.shift(fill_value=False) & (c >= o.shift()) & (o <= c.shift()),
                      red & green.shift(fill_value=False) & (c <= o.shift()) & (o >= c.shift())),
        "hammer_star": ((rng > 0) & (lw >= 2 * body) & (uw <= 0.25 * rng),
                        (rng > 0) & (uw >= 2 * body) & (lw <= 0.25 * rng)),
        "inside_break": (inside_prev & (c > h.shift()), inside_prev & (c < l.shift())),
        "three_bar": (green & green.shift(fill_value=False) & green.shift(2, fill_value=False) & (c > c.shift()) & (c.shift() > c.shift(2)),
                      red & red.shift(fill_value=False) & red.shift(2, fill_value=False) & (c < c.shift()) & (c.shift() < c.shift(2))),
        "outside_rev": ((h > h.shift()) & (l < l.shift()) & green & (c > l + 0.75 * rng),
                        (h > h.shift()) & (l < l.shift()) & red & (c < h - 0.75 * rng)),
        "doji_rev": (doji_prev & red.shift(2, fill_value=False) & (c > h.shift()),
                     doji_prev & green.shift(2, fill_value=False) & (c < l.shift())),
    }


def indicator_states(d):
    c, h, l = d.c, d.h, d.l
    r14 = rsi(c, 14)
    mid, sd = c.rolling(20).mean(), c.rolling(20).std()
    atr = (pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)).ewm(span=14, adjust=False).mean()
    e20 = ema(c, 20)
    macd = ema(c, 12) - ema(c, 26)
    sig = ema(macd, 9)
    k = 100 * (c - l.rolling(14).min()) / (h.rolling(14).max() - l.rolling(14).min())
    out = {}
    for lv in (25, 30):
        out[f"rsi_mr_{lv}"] = (state(r14 < lv, r14 > 50), state(r14 > 100 - lv, r14 < 50))
    out["bb_mr"] = (state(c < mid - 2 * sd, c > mid), state(c > mid + 2 * sd, c < mid))
    for n in (20, 55):
        hi, lo = h.rolling(n).max().shift(), l.rolling(n).min().shift()
        xhi, xlo = h.rolling(n // 2).max().shift(), l.rolling(n // 2).min().shift()
        out[f"donchian_{n}"] = (state(c > hi, c < xlo), state(c < lo, c > xhi))
    for f, s in ((9, 21), (20, 50), (50, 200)):
        up = ema(c, f) > ema(c, s)
        out[f"ema_{f}_{s}"] = (up.astype(float), (~up).astype(float))
    out["macd"] = ((macd > sig).astype(float), (macd < sig).astype(float))
    out["keltner"] = (state(c > e20 + 2 * atr, c < e20), state(c < e20 - 2 * atr, c > e20))
    out["stoch_mr"] = (state(k < 20, k > 50), state(k > 80, k < 50))
    return out


def bar_rets(d, pos):
    p = pos.shift(1).fillna(0)
    r = (d.o.shift(-1) / d.o - 1).fillna(0)
    return p * r - p.diff().abs().fillna(p.abs()) * FEE / 100


def period_stats(r, bpy):
    out = {}
    for name, (a, b) in PERIODS.items():
        x = r.loc[a:b]
        if len(x) < 50 or x.std() == 0:
            out[name] = (np.nan, np.nan)
            continue
        total = (1 + x).clip(lower=0).prod()
        out[name] = ((total ** (bpy / len(x)) - 1) * 100 if total > 0 else -100.0, x.mean() / x.std() * np.sqrt(bpy))
    return out


def combine(long_pos, short_pos, side, trend_ok_long, trend_ok_short, use_trend):
    lp = long_pos * (trend_ok_long if use_trend else 1)
    sp = short_pos * (trend_ok_short if use_trend else 1)
    if side == "long":
        return lp
    if side == "short":
        return -sp
    return (lp - sp).clip(-1, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data_dir")
    ap.add_argument("--placebo", type=int, default=300)
    a = ap.parse_args()
    raw = {os.path.basename(p)[:-4][:-4]: load(p).loc["2020-06-01":]
           for p in sorted(glob.glob(os.path.join(a.data_dir, "*USDT.csv")))}
    rng = np.random.default_rng(7)
    rows = []
    for tf in ("1h", "4h", "1d"):
        bpy = BPY[tf]
        frames = {s: resample(d, tf) for s, d in raw.items()}
        per_coin = {}
        for coin, d in frames.items():
            t200 = ema(d.c, 200)
            up, dn = (d.c > t200).astype(float), (d.c < t200).astype(float)
            rules = {}
            for name, (ls, ss) in candle_signals(d).items():
                for h in (1, 3, 6, 12, 24):
                    rules[(f"candle:{name}", f"hold {h}")] = (hold_for(ls, h), hold_for(ss, h))
            for name, (lp, sp) in indicator_states(d).items():
                rules[(f"ind:{name}", "")] = (lp, sp)
            for i in range(a.placebo):
                h = int(rng.choice([1, 3, 6, 12, 24]))
                p = float(rng.choice([0.01, 0.03, 0.1]))
                rl = pd.Series(rng.random(len(d)) < p, index=d.index)
                rs = pd.Series(rng.random(len(d)) < p, index=d.index)
                rules[(f"placebo:{i}", f"hold {h}")] = (hold_for(rl, h), hold_for(rs, h))
            for (rule, extra), (lp, sp) in rules.items():
                sides = ["long", "short", "both"] if not rule.startswith("placebo") else [["long", "short", "both"][int(rule.split(":")[1]) % 3]]
                trends = [False, True] if not rule.startswith("placebo") else [False]
                for side, use_t in itertools.product(sides, trends):
                    pos = combine(lp, sp, side, up, dn, use_t)
                    per_coin.setdefault((tf, rule, extra, side, use_t), {})[coin] = period_stats(bar_rets(d, pos), bpy)
        for key, coins in per_coin.items():
            row = dict(tf=key[0], rule=key[1], hold=key[2], side=key[3], trend=key[4])
            for per in PERIODS:
                yrs = [v[per][0] for v in coins.values() if not np.isnan(v[per][0])]
                shs = [v[per][1] for v in coins.values() if not np.isnan(v[per][1])]
                row[f"{per}_year"] = np.mean(yrs) if yrs else np.nan
                row[f"{per}_sharpe"] = np.mean(shs) if shs else np.nan
                row[f"{per}_coins_up"] = sum(y > 0 for y in yrs)
            rows.append(row)
        print(f"{tf} done", flush=True)

    res = pd.DataFrame(rows)
    res["placebo"] = res.rule.str.startswith("placebo")
    passed = res[(res.train_sharpe > 0.5) & (res.val_year > 0) & (res.val_coins_up >= 8)]
    real, plac = res[~res.placebo], res[res.placebo]
    pr, pp = passed[~passed.placebo], passed[passed.placebo]
    pd.set_option("display.width", 250)
    print(f"\nReal strategies tested: {len(real)} | passed train+2024 screen: {len(pr)} ({100 * len(pr) / len(real):.1f}%)")
    print(f"Random placebos tested: {len(plac)} | passed the same screen: {len(pp)} ({100 * len(pp) / max(len(plac), 1):.1f}%)")
    cols = ["tf", "rule", "hold", "side", "trend", "train_year", "train_sharpe", "val_year", "val_coins_up",
            "y2025_year", "y2025_coins_up", "y2026_year", "y2026_coins_up"]
    print("\nAll real survivors of the screen, with FINAL TEST results (2025, 2026; average %/yr across 13 coins):")
    print(pr.sort_values("train_sharpe", ascending=False)[cols].round(1).to_string(index=False))
    if len(pr):
        both = pr[(pr.y2025_year > 0) & (pr.y2026_year > 0)]
        print(f"\nSurvivors profitable in BOTH 2025 and 2026: {len(both)}/{len(pr)}; "
              f"mean final-test return of all survivors: 2025 {pr.y2025_year.mean():+.1f}%, 2026 {pr.y2026_year.mean():+.1f}%")
    if len(pp):
        print(f"Placebo survivors on the final test: 2025 {pp.y2025_year.mean():+.1f}%, 2026 {pp.y2026_year.mean():+.1f}%")
    res.to_pickle(os.path.join(a.data_dir, "lab4_results.pkl"))


if __name__ == "__main__":
    main()
