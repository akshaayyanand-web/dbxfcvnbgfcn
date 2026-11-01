"""Replica of the "RSI2 Dip Aggressive v2" Pine strategy for an independent check on Binance klines.

Rules (as in the Pine script): buy at the next open when RSI(2) < 10 and close > EMA(50) and flat;
stop = entry price - 2 x ATR(14) of the signal bar (active from the bar after the fill); close at the
next open once the position has been held 48 bars on 2h (24 on 4h); 100% of equity, 0.075% fee per
side; no new entries after a 30% drawdown from the equity peak.

Usage: python3 test_rsi2_dip.py KLINES_1h.csv [--tf 2h] [--start 2025-02-01] [--end 2026-12-31]
"""
import argparse

import numpy as np
import pandas as pd

from backtest_ema_macd import load


def rma(s, n):
    return s.ewm(alpha=1 / n, adjust=False).mean()


def rsi(c, n):
    d = c.diff()
    up, dn = rma(d.clip(lower=0), n), rma(-d.clip(upper=0), n)
    return 100 - 100 / (1 + up / dn)


def resample(df, tf):
    return df.resample(tf).agg({"o": "first", "h": "max", "l": "min", "c": "last", "v": "sum"}).dropna()


def backtest(df, tf, start, end, rsi_buy=10.0, ema_len=50, stop_mult=2.0, bars_2h=48, fee=0.075,
             kill_dd=30.0, rsi_len=2, atr_len=14, signal=None):
    max_bars = max(1, round(bars_2h * 7200 / pd.Timedelta(tf).total_seconds())) if bars_2h else 0
    c = df.c
    tr = pd.concat([df.h - df.l, (df.h - c.shift()).abs(), (df.l - c.shift()).abs()], axis=1).max(axis=1)
    atr, ema_t, r = rma(tr, atr_len), c.ewm(span=ema_len, adjust=False).mean(), rsi(c, rsi_len)
    sig = ((r < rsi_buy) & (c > ema_t)).to_numpy() if signal is None else signal
    O, H, L, C, A = (x.to_numpy() for x in (df.o, df.h, df.l, c, atr))
    t = df.index
    lo, hi = t.searchsorted(pd.Timestamp(start, tz="UTC")), t.searchsorted(pd.Timestamp(end, tz="UTC"), side="right")

    eq, peak, max_dd, trades = 1.0, 1.0, 0.0, []
    qty = entry = stop = None
    pending_entry = pending_exit = False
    held, entry_i, sig_atr = 0, 0, 0.0
    for i in range(lo, hi):
        if pending_entry:  # fill at this bar's open
            entry = O[i]
            qty = eq * (1 - fee / 100) / entry
            eq_entry, entry_i, held, stop, worst = eq, i, 0, None, 0.0
            pending_entry = False
        elif pending_exit and qty is not None:
            px = O[i]
            eq = qty * px * (1 - fee / 100)
            trades.append((t[entry_i], eq / eq_entry - 1, "time", worst))
            qty, pending_exit = None, False
        if qty is not None:
            # deepest open loss of the trade (floating P&L, capped at the stop once it is active)
            worst = min(worst, (max(L[i], stop) if stop is not None else L[i]) / entry - 1)
            if stop is not None and L[i] <= stop:
                px = min(O[i], stop)
                eq = qty * px * (1 - fee / 100)
                trades.append((t[entry_i], eq / eq_entry - 1, "stop", worst))
                qty = None
            else:
                if stop is None:
                    stop = entry - stop_mult * sig_atr
                held += 1
                if max_bars and held >= max_bars:
                    pending_exit = True
        cur = qty * C[i] if qty is not None else eq
        peak = max(peak, cur)
        dd = (peak - cur) / peak * 100
        max_dd = max(max_dd, dd)
        if qty is None and not pending_entry and sig[i] and not np.isnan(A[i]) and not (kill_dd and dd >= kill_dd):
            pending_entry, sig_atr = True, A[i]
    final = qty * C[hi - 1] if qty is not None else eq
    tr_df = pd.DataFrame(trades, columns=["entry", "ret", "exit", "worst"])
    return final, max_dd, tr_df


def summary(final, dd, tr):
    n = len(tr)
    win = 100 * (tr.ret > 0).mean() if n else 0.0
    return f"{100 * (final - 1):+8.1f}%  maxDD {dd:5.1f}%  trades {n:3d}  win {win:4.0f}%"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("klines")
    ap.add_argument("--tf", default="2h")
    ap.add_argument("--start", default="2025-02-01")
    ap.add_argument("--end", default="2026-12-31")
    a = ap.parse_args()
    df = resample(load(a.klines), a.tf)
    print(a.tf, a.start, "->", a.end, summary(*backtest(df, a.tf, a.start, a.end)))
