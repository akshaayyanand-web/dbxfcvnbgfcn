"""Independent replicas of two user-supplied Pine strategies, run on Binance klines.

mst_clone   "MST v13 (Clone)": Renko bricks of 1 x ATR(14) (previous closed 1h bar), built from the
            chart close bar by bar; stop-and-reverse whenever the brick direction flips; 100% of
            equity; orders fill at the signal bar's close (process_orders_on_close = true).
qqe_ssl_wae "QQE MOD + SSL Hybrid + Waddah Attar Explosion": long when a new QQE green bar, close above
            the SSL Keltner channel and baseline, and WAE up-trend above the explosion line (mirror
            for shorts); stop at the 10-bar swing low/high; size so the stop loses 2% of equity;
            close at the next open when the SSL exit line is crossed against the trade while it is
            in profit.
"""
import numpy as np
import pandas as pd


def rma(s, n):
    return s.ewm(alpha=1 / n, adjust=False).mean()


def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def wma(s, n):
    n = int(n)
    w = np.arange(1, n + 1, dtype=float)
    return s.rolling(n).apply(lambda x: np.dot(x, w) / w.sum(), raw=True)


def hma(s, n):
    return wma(2 * wma(s, n / 2) - wma(s, n), round(np.sqrt(n)))


def rsi(c, n):
    d = c.diff()
    return 100 - 100 / (1 + rma(d.clip(lower=0), n) / rma(-d.clip(upper=0), n))


def true_range(df):
    return pd.concat([df.h - df.l, (df.h - df.c.shift()).abs(), (df.l - df.c.shift()).abs()], axis=1).max(axis=1)


def resample(df, tf):
    return df.resample(tf).agg({"o": "first", "h": "max", "l": "min", "c": "last", "v": "sum"}).dropna()


# ─────────────────────────────── MST v13 clone ───────────────────────────────
def mst_clone(df, df_1h, fee=0.02, brick_mult=1.0):
    atr_h = rma(true_range(df_1h), 14).shift(1)  # previous closed 1h bar ([1] + lookahead_on)
    atr = atr_h.reindex(df.index, method="ffill").fillna(rma(true_range(df), 14)).to_numpy()
    C = df.c.to_numpy()
    r_open = r_close = C[0]
    r_dir = 0
    pos, eq, n_tr, wins = 0, 1.0, 0, 0
    entry_eq, entry_px = 1.0, 0.0
    peak, max_dd = 1.0, 0.0
    for i in range(len(C)):
        prev_dir = r_dir
        b = atr[i] * brick_mult
        if b > 0 and not np.isnan(b):
            for _ in range(50):
                c = C[i]
                if r_dir == 1:
                    up, dn = c >= r_close + b, c <= r_open - b
                elif r_dir == -1:
                    dn, up = c <= r_close - b, c >= r_open + b
                else:
                    up, dn = c >= r_close + b, c <= r_close - b
                if up:
                    if r_dir == -1:
                        r_close = r_open + b
                    else:
                        r_open, r_close = r_close, r_close + b
                    r_dir = 1
                elif dn:
                    if r_dir == 1:
                        r_close = r_open - b
                    else:
                        r_open, r_close = r_close, r_close - b
                    r_dir = -1
                else:
                    break
        cur = eq * (1 + pos * (C[i] / entry_px - 1)) if pos else eq
        new = 1 if (r_dir == 1 and prev_dir != 1) else -1 if (r_dir == -1 and prev_dir != -1) else 0
        if new and new != pos:
            if pos:  # close the old side at this close
                eq = cur * (1 - fee / 100)
                n_tr += 1
                wins += eq > entry_eq
            eq *= 1 - fee / 100  # open the new side
            pos, entry_px, entry_eq = new, C[i], eq
            cur = eq
        peak = max(peak, cur)
        max_dd = max(max_dd, (peak - cur) / peak)
    final = eq * (1 + pos * (C[-1] / entry_px - 1)) if pos else eq
    return final, max_dd * 100, n_tr, 100 * wins / max(n_tr, 1)


# ───────────────────────── QQE MOD + SSL Hybrid + WAE ─────────────────────────
def qqe_trend_line(rsi_ma, dar):
    R, D = rsi_ma.to_numpy(), dar.to_numpy()
    n = len(R)
    lb, sb, tl = np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)
    trend = 1
    for i in range(1, n):
        nl, ns = R[i] - D[i], R[i] + D[i]
        lb[i] = max(lb[i - 1], nl) if (R[i - 1] > lb[i - 1] and R[i] > lb[i - 1]) else nl
        sb[i] = min(sb[i - 1], ns) if (R[i - 1] < sb[i - 1] and R[i] < sb[i - 1]) else ns
        if i >= 2:
            a, a1, b, b1 = R[i], R[i - 1], sb[i - 1], sb[i - 2]
            up = (a > b and a1 <= b1) or (a < b and a1 >= b1)
            x, x1, y, y1 = lb[i - 1], lb[i - 2], R[i], R[i - 1]
            dn = (x > y and x1 <= y1) or (x < y and x1 >= y1)
            trend = 1 if up else -1 if dn else trend
        tl[i] = lb[i] if trend == 1 else sb[i]
    return pd.Series(tl, index=rsi_ma.index)


def qqe_signals(df):
    c, h, l = df.c, df.h, df.l
    rsi_ma = ema(rsi(c, 6), 6)
    dar = ema(ema((rsi_ma.shift() - rsi_ma).abs(), 11), 11) * 3
    tl = qqe_trend_line(rsi_ma, dar) - 50
    basis, dev = tl.rolling(50).mean(), 0.35 * tl.rolling(50).std(ddof=0)
    rsi_ma2 = ema(rsi(c, 6), 5)
    green = (rsi_ma2 - 50 > 3) & (rsi_ma - 50 > basis + dev)
    red = (rsi_ma2 - 50 < -3) & (rsi_ma - 50 < basis - dev)
    qqe_buy, qqe_sell = green & ~green.shift(fill_value=False), red & ~red.shift(fill_value=False)

    bbmc = hma(c, 60)
    rng = ema(true_range(df), 60)
    upperk, lowerk = bbmc + rng * 0.2, bbmc - rng * 0.2
    ssl_buy, ssl_sell = (c > upperk) & (c > bbmc), (c < lowerk) & (c < bbmc)
    ex_h, ex_l = hma(h, 15).to_numpy(), hma(l, 15).to_numpy()
    C = c.to_numpy()
    hlv, ssl_exit = 0, np.full(len(C), np.nan)
    for i in range(len(C)):
        hlv = 1 if C[i] > ex_h[i] else -1 if C[i] < ex_l[i] else hlv
        ssl_exit[i] = ex_h[i] if hlv < 0 else ex_l[i]
    se = pd.Series(ssl_exit, index=c.index)
    cross_long = (c > se) & (c.shift() <= se.shift())    # crossover(close, sslExit)
    cross_short = (se > c) & (se.shift() <= c.shift())   # crossover(sslExit, close)

    macd = ema(c, 20) - ema(c, 40)
    t1 = (macd - macd.shift()) * 180
    e1 = 4 * c.rolling(20).std(ddof=0)
    wae_buy, wae_sell = (t1 > 0) & (t1 > e1), (t1 < 0) & (-t1 > e1)
    return (qqe_buy & ssl_buy & wae_buy), (qqe_sell & ssl_sell & wae_sell), cross_long, cross_short


def qqe_ssl_wae(df, fee=0.01, risk=2.0, max_lev=None, swing=10):
    long_sig, short_sig, x_long, x_short = qqe_signals(df)
    lo_sw, hi_sw = df.l.rolling(swing).min().to_numpy(), df.h.rolling(swing).max().to_numpy()
    O, H, L, C = (df[k].to_numpy() for k in "ohlc")
    LS, SS, XL, XS = (x.to_numpy() for x in (long_sig, short_sig, x_long, x_short))
    eq, pos, qty, stop, entry = 1.0, 0, 0.0, 0.0, 0.0
    pending, pending_close = None, False
    peak, max_dd, n_tr, wins, eq_in = 1.0, 0.0, 0, 0, 1.0
    for i in range(len(C)):
        if pending is not None:
            d, st, q_cash = pending
            entry = O[i]
            qty = q_cash / C[i - 1]
            eq -= qty * entry * fee / 100
            pos, stop, eq_in, pending = d, st, eq, None
        elif pending_close and pos:
            eq += pos * qty * (O[i] - entry) - qty * O[i] * fee / 100
            n_tr += 1
            wins += eq > eq_in
            pos, pending_close = 0, False
        if pos:
            hit = L[i] <= stop if pos == 1 else H[i] >= stop
            if hit:
                px = min(O[i], stop) if pos == 1 else max(O[i], stop)
                eq += pos * qty * (px - entry) - qty * px * fee / 100
                n_tr += 1
                wins += eq > eq_in
                pos = 0
            else:
                in_profit = pos * (C[i] - entry) > 0
                if (pos == 1 and XS[i] or pos == -1 and XL[i]) and in_profit:
                    pending_close = True
        cur = eq + (pos * qty * (C[i] - entry) if pos else 0)
        if cur <= 0:
            return 0.0, 100.0, n_tr, 100 * wins / max(n_tr, 1)
        peak = max(peak, cur)
        max_dd = max(max_dd, (peak - cur) / peak)
        if pos == 0 and pending is None and not pending_close:
            for d, sig, st in ((1, LS[i], lo_sw[i]), (-1, SS[i], hi_sw[i])):
                if sig and not np.isnan(st):
                    stop_pct = abs(1 - st / C[i]) * 100
                    if stop_pct <= 0:
                        continue
                    cash = eq * risk / 100 / stop_pct * 100
                    if max_lev:
                        cash = min(cash, eq * max_lev)
                    pending = (d, st, cash)
                    break
    final = eq + (pos * qty * (C[-1] - entry) if pos else 0)
    return final, max_dd * 100, n_tr, 100 * wins / max(n_tr, 1)
