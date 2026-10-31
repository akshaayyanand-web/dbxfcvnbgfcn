"""Independent backtest of strategies/ema_macd_5m_scalper.pine on Binance 5m klines.

Usage: python3 backtest_ema_macd.py KLINES.csv [--fee 0.05] [--rr 2.0] [--start 2025-01-01]

KLINES.csv is a concatenation of Binance archive files (data.binance.vision, spot/.../5m).
Signals use closed bars only and fill at the next bar's open; if stop and target are both
touched inside one bar the stop is assumed to hit first (conservative).
"""
import argparse

import numpy as np
import pandas as pd


def load(path):
    df = pd.read_csv(path, header=None, usecols=range(6), names=["t", "o", "h", "l", "c", "v"])
    t = df["t"].astype("int64")
    t = np.where(t > 10**14, t // 1000, t)  # Binance switched to microseconds in 2025
    df.index = pd.to_datetime(t, unit="ms", utc=True)
    return df.drop(columns="t").sort_index().loc[lambda d: ~d.index.duplicated()]


def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def bars_since(cond):
    idx = np.where(cond.to_numpy(), np.arange(len(cond)), np.nan)
    last = pd.Series(idx, index=cond.index).ffill()
    return (np.arange(len(cond)) - last).fillna(9999)


def signals(df, p):
    o, h, l, c, v = df.o, df.h, df.l, df.c, df.v
    emaF, emaS = ema(c, p.fast), ema(c, p.slow)
    # 4H EMA of closed 4H bars, applied only once that 4H bar has finished (== Pine [1] + lookahead_on)
    c4 = c.resample("4h").last()
    htf = ema(c4, p.trend_len).shift(1).reindex(df.index, method="ffill")
    macd = ema(c, 12) - ema(c, 26)
    sig = ema(macd, 9)
    hist = macd - sig

    cross_up_e = (emaF > emaS) & (emaF.shift() <= emaS.shift())
    cross_dn_e = (emaF < emaS) & (emaF.shift() >= emaS.shift())
    cross_up_m = (macd > sig) & (macd.shift() <= sig.shift())
    cross_dn_m = (macd < sig) & (macd.shift() >= sig.shift())
    ema_up = (emaF > emaS) & (bars_since(cross_up_e) <= p.win)
    ema_dn = (emaF < emaS) & (bars_since(cross_dn_e) <= p.win)
    macd_up = (macd > sig) & (hist > 0) & (bars_since(cross_up_m) <= p.win)
    macd_dn = (macd < sig) & (hist < 0) & (bars_since(cross_dn_m) <= p.win)

    body, rng = (c - o).abs(), h - l
    low_w, up_w = np.minimum(o, c) - l, h - np.maximum(o, c)
    bull_eng = (c > o) & (c.shift() < o.shift()) & (c >= o.shift()) & (o <= c.shift())
    bear_eng = (c < o) & (c.shift() > o.shift()) & (c <= o.shift()) & (o >= c.shift())
    hammer = (rng > 0) & (low_w >= 2 * body) & (up_w <= 0.25 * rng)
    star = (rng > 0) & (up_w >= 2 * body) & (low_w <= 0.25 * rng)

    top = np.maximum(emaF, emaS) * (1 + p.near / 100)
    bot = np.minimum(emaF, emaS) * (1 - p.near / 100)
    near = (l <= top) & (h >= bot)
    vol_ok = (v > v.rolling(20).mean() * p.vol_mult) & (v > v.shift())

    l_stop = l.rolling(p.swing).min() * (1 - p.buf / 100)
    s_stop = h.rolling(p.swing).max() * (1 + p.buf / 100)
    l_rp = (c - l_stop) / c * 100
    s_rp = (s_stop - c) / c * 100

    bull_pat = (bull_eng | hammer) | (not p.pattern)
    bear_pat = (bear_eng | star) | (not p.pattern)
    long_sig = (c > htf) & ema_up & macd_up & bull_pat & near & vol_ok & l_rp.between(p.min_risk, p.max_risk)
    short_sig = (c < htf) & ema_dn & macd_dn & bear_pat & near & vol_ok & s_rp.between(p.min_risk, p.max_risk)
    return long_sig, short_sig, l_stop, s_stop


def run(df, p):
    long_sig, short_sig, l_stop, s_stop = signals(df, p)
    df = df.loc[p.start:]
    LS, SS = long_sig.loc[p.start:].to_numpy(), short_sig.loc[p.start:].to_numpy()
    LST, SST = l_stop.loc[p.start:].to_numpy(), s_stop.loc[p.start:].to_numpy()
    O, H, L, C = (df[k].to_numpy() for k in "ohlc")
    days = df.index.floor("D").to_numpy()
    fee, slip = p.fee / 100, p.slip / 100

    eq, trades = p.capital, []
    day, day_start, halted = None, eq, False
    pos = None  # (dir, qty, entry, stop, tp, entry_i)
    pending = None
    for i in range(len(df)):
        if days[i] != day:
            day, day_start, halted = days[i], eq, False
        if pending is not None and pos is None:
            d, stop, tp, risk_unit = pending
            entry = O[i] * (1 + d * slip)
            qty = min(eq * p.risk / 100 / risk_unit, eq * p.max_lev / entry)
            entry_fee = qty * entry * fee
            eq -= entry_fee
            pos = (d, qty, entry, stop, tp, i, entry_fee)
        pending = None
        if pos is not None:
            d, qty, entry, stop, tp, ei, entry_fee = pos
            hit_stop = L[i] <= stop if d == 1 else H[i] >= stop
            hit_tp = H[i] >= tp if d == 1 else L[i] <= tp
            px = None
            if hit_stop:
                px = (min(O[i], stop) if d == 1 else max(O[i], stop)) * (1 - d * slip)
            elif hit_tp:
                px = tp
            elif eq + d * qty * (C[i] - entry) <= day_start * (1 - p.day_loss / 100):
                px, halted = C[i] * (1 - d * slip), True
            if px is not None:
                exit_pnl = d * qty * (px - entry) - qty * px * fee
                eq += exit_pnl
                trades.append((df.index[ei], d, entry, px, exit_pnl - entry_fee, i - ei))
                pos = None
                if eq <= day_start * (1 - p.day_loss / 100):
                    halted = True
                continue
        if pos is None and not halted:
            if LS[i]:
                pending = (1, LST[i], C[i] + p.rr * (C[i] - LST[i]), C[i] - LST[i])
            elif SS[i]:
                pending = (-1, SST[i], C[i] - p.rr * (SST[i] - C[i]), SST[i] - C[i])
    return eq, pd.DataFrame(trades, columns=["entry_time", "dir", "entry", "exit", "pnl", "bars"])


def report(name, eq, tr, p):
    if tr.empty:
        print(f"{name}: no trades")
        return
    curve = p.capital + tr.pnl.cumsum()
    dd = ((curve.cummax() - curve) / curve.cummax()).max() * 100
    wins, losses = tr.pnl[tr.pnl > 0], tr.pnl[tr.pnl <= 0]
    pf = wins.sum() / -losses.sum() if len(losses) else float("inf")
    months = (tr.entry_time.iloc[-1] - tr.entry_time.iloc[0]).days / 30.4
    print(f"{name}: {len(tr)} trades ({len(tr) / max(months, 1):.1f}/month) | win {100 * len(wins) / len(tr):.1f}% "
          f"| PF {pf:.2f} | return {100 * (eq / p.capital - 1):+.1f}% | max DD {dd:.1f}% "
          f"| longs {int((tr.dir == 1).sum())} shorts {int((tr.dir == -1).sum())}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("klines", nargs="+")
    ap.add_argument("--start", default="2025-01-01")
    ap.add_argument("--capital", type=float, default=10000)
    ap.add_argument("--fee", type=float, default=0.05, help="%% per side")
    ap.add_argument("--slip", type=float, default=0.01, help="%% per side on market fills")
    ap.add_argument("--rr", type=float, default=2.0)
    ap.add_argument("--risk", type=float, default=1.0)
    ap.add_argument("--max-lev", type=float, default=1.0)
    ap.add_argument("--day-loss", type=float, default=5.0)
    ap.add_argument("--fast", type=int, default=20)
    ap.add_argument("--slow", type=int, default=50)
    ap.add_argument("--trend-len", type=int, default=200)
    ap.add_argument("--win", type=int, default=6)
    ap.add_argument("--near", type=float, default=0.15)
    ap.add_argument("--vol-mult", type=float, default=1.2)
    ap.add_argument("--swing", type=int, default=10)
    ap.add_argument("--buf", type=float, default=0.05)
    ap.add_argument("--min-risk", type=float, default=0.25)
    ap.add_argument("--max-risk", type=float, default=1.5)
    ap.add_argument("--no-pattern", dest="pattern", action="store_false", help="drop the hammer/engulfing rule")
    p = ap.parse_args()
    for path in p.klines:
        eq, tr = run(load(path), p)
        report(path.rsplit("/", 1)[-1], eq, tr, p)
