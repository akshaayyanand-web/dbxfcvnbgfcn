"""RSI dip / spike strategy across several coins and both directions, plus a portfolio prop simulator.

Long:  RSI(n) < buy  and close > EMA(trend) and yesterday's daily close > its 200-day SMA
Short: RSI(n) > 100 - buy and close < EMA(trend) and yesterday's daily close < its 200-day SMA
Entry at the next open, stop = stop_mult x ATR(14) from entry, exit at the next open after hold_h hours.

The portfolio simulator walks an hourly timeline, marks every open position to market with the
hour's adverse extreme, and applies prop rules (static max loss from the start balance, daily loss
limit from the day's opening balance or equity, profit target). New positions are sized as a share of the buffer
above the fail line and only opened while the total open risk stays inside the limits.
"""
import numpy as np
import pandas as pd

from test_rsi2_dip import resample, rma, rsi

FEE = 0.06


def signal_trades(raw_1h, coin, tf="2h", rsi_len=3, buy=20.0, trend=50, stop_mult=2.0, hold_h=96, side="long"):
    df = resample(raw_1h, tf)
    c = df.c
    tr = pd.concat([df.h - df.l, (df.h - c.shift()).abs(), (df.l - c.shift()).abs()], axis=1).max(axis=1)
    atr = rma(tr, 14).to_numpy()
    r = rsi(c, rsi_len).to_numpy()
    e = c.ewm(span=trend, adjust=False).mean().to_numpy()
    daily = raw_1h.c.resample("1D").last()
    up = (daily > daily.rolling(200).mean()).shift(1)
    dn = (daily < daily.rolling(200).mean()).shift(1)
    day_idx = df.index.floor("D")
    reg = (up if side == "long" else dn).reindex(day_idx).fillna(False).to_numpy().astype(bool)
    C, O, H, L = c.to_numpy(), df.o.to_numpy(), df.h.to_numpy(), df.l.to_numpy()
    sig = ((r < buy) & (C > e) if side == "long" else (r > 100 - buy) & (C < e)) & reg
    d = 1 if side == "long" else -1
    max_bars = max(1, round(hold_h / (pd.Timedelta(tf).total_seconds() / 3600)))
    out, i, n, t = [], 0, len(C), df.index
    while i < n - 2:
        if not sig[i] or np.isnan(atr[i]):
            i += 1
            continue
        j = i + 1
        entry = O[j]
        stop = entry - d * stop_mult * atr[i]
        k, held, px, exit_t = j, 1, None, None
        while k < n - 1:
            if held >= max_bars:  # time exit at the next bar's open
                px, k = O[k + 1], k + 1
                exit_t = t[k]
                break
            k += 1
            held += 1
            if (L[k] <= stop) if d == 1 else (H[k] >= stop):  # stopped inside bar k
                px = min(O[k], stop) if d == 1 else max(O[k], stop)
                exit_t = t[k] + pd.Timedelta(tf)
                break
        if px is None:
            break
        ret = d * (px / entry - 1) - 2 * FEE / 100
        out.append(dict(coin=coin, side=d, entry_t=t[j], exit_t=exit_t,
                        entry=entry, exit=px, stop=stop, ret=ret, stop_pct=abs(entry - stop) / entry))
        i = k
    return out


def portfolio_attempt(trades, hourly, start, target=0.10, max_loss=0.06, daily=0.03, frac=0.33, cap=0.022,
                      max_open_risk=0.028, max_x=1.5, horizon_days=None, daily_basis="balance"):
    """trades: DataFrame sorted by entry_t. hourly: {coin: DataFrame(h, l, c)} on a 1h index."""
    bal, fail_line = 1.0, 1 - max_loss
    open_pos = []  # dicts: coin, side, entry, size, risk, exit_t, exit, ret
    tr = trades[trades.entry_t >= start].reset_index(drop=True)
    ti, n = 0, len(tr)
    end = start + pd.Timedelta(days=horizon_days) if horizon_days else None
    day, day_open = None, 1.0
    hours = hourly["__index__"]
    h0 = hours.searchsorted(start)
    for hi in range(h0, len(hours)):
        now = hours[hi]
        if end is not None and now > end:
            return "open", None
        if now.floor("D") != day:
            day = now.floor("D")
            floating = sum(p["size"] * p["side"] * (hourly[p["coin"]]["c"][hi - 1] / p["entry"] - 1) for p in open_pos)
            # firms measure the daily limit from the closed balance or from equity (incl. open P&L)
            day_open = bal + floating if daily_basis == "equity" else bal
        # close positions whose exit time has come (realise P&L)
        still = []
        for p in open_pos:
            if p["exit_t"] <= now:
                bal += p["size"] * p["ret"]
            else:
                still.append(p)
        open_pos = still
        if bal >= 1 + target and not open_pos:
            return "pass", (now - start).days
        # open new positions that start this hour
        while ti < n and tr.entry_t[ti] <= now:
            row = tr.iloc[ti]
            ti += 1
            if any(p["coin"] == row.coin for p in open_pos):
                continue
            used = sum(p["risk"] for p in open_pos)
            buf = bal - fail_line - used
            day_left = day_open * (daily - 0.002) - max(day_open - bal, 0) - used
            risk = min(frac * buf, cap * bal, max_open_risk - used, day_left)
            if risk <= 0.001:
                continue
            size = min(risk / row.stop_pct, max_x)
            open_pos.append(dict(coin=row.coin, side=row.side, entry=row.entry, size=size, risk=size * row.stop_pct,
                                 exit_t=row.exit_t, ret=row.ret))
        # mark to market at this hour's adverse extremes
        if open_pos:
            low = bal
            for p in open_pos:
                hd = hourly[p["coin"]]
                adverse = hd["l"][hi] if p["side"] == 1 else hd["h"][hi]
                low += p["size"] * max(p["side"] * (adverse / p["entry"] - 1), -p["risk"] / p["size"] - 0.0012)
            if low <= fail_line or low <= day_open * (1 - daily):
                return "fail", None
            mtm = bal + sum(p["size"] * p["side"] * (hourly[p["coin"]]["c"][hi] / p["entry"] - 1) for p in open_pos)
            if mtm >= 1 + target:
                return "pass", (now - start).days
    return "open", None
