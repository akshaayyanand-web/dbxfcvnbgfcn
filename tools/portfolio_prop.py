"""Combine the robust strategies into one prop-compliant portfolio, marked to market hour by hour.

Components (unit sizes):
  btc_dip   BTC Dip v3 on 2h (RSI3<20, EMA50, 30-day crash filter, 2xATR stop at entry, 96h exit), 1% risk
  gold_dip  Gold 1h (RSI2<10, EMA50, 8% crash filter, 2xATR stop at entry, 96h exit), 1% risk
  nq_mom    Nasdaq 2h time-series momentum (long while close > close 120 bars ago), 1x notional
  si_trend  Silver 2h EMA20 > EMA50, long only, 1x notional
  es_trend  S&P 500 2h EMA20 > EMA50, long only, 1x notional

Hourly portfolio return = sum(weight x component return); the hourly low assumes every component hits
its low in the same hour (conservative). Weights are chosen on 12-month windows started in 2020-2022 (from a fresh account) to maximise the
median return while never touching an 8% max loss or a 4% daily loss (limits 10% / 5%), then checked on 2024-2026 and on rolling
12-month prop windows with a guard that flattens everything at 80% of the daily or max loss.

Usage: python3 portfolio_prop.py BTCUSDT_1h.csv FUTURES_DIR
"""
import itertools
import sys

import numpy as np
import pandas as pd

from backtest_ema_macd import load
from futures_lab import load_csv
from test_rsi2_dip import resample, rma, rsi

FEE_CRYPTO, COST = 0.0012, {"XAUUSD": 0.0001, "USATECHIDXUSD": 0.00012, "XAGUSD": 0.00025, "USA500IDXUSD": 0.0001}


def dip_trades(raw1h, tf, rl, buy, crash_pct, cost):
    b = resample(raw1h, tf) if tf != "1h" else raw1h
    c = b.c
    d = raw1h.c.resample("1D").last().dropna()
    crash = (d / d.shift(30) - 1 < -crash_pct).shift(1).reindex(b.index.floor("D")).fillna(False).to_numpy().astype(bool)
    sig = ((rsi(c, rl) < buy) & (c > c.ewm(span=50, adjust=False).mean())).to_numpy() & ~crash
    tr = pd.concat([b.h - b.l, (b.h - c.shift()).abs(), (b.l - c.shift()).abs()], axis=1).max(axis=1)
    atr = rma(tr, 14).to_numpy()
    O, H, L, C, T = b.o.to_numpy(), b.h.to_numpy(), b.l.to_numpy(), c.to_numpy(), b.index
    bar = T[1] - T[0]
    max_bars = int(pd.Timedelta("96h") / bar)
    out, i = [], 0
    while i < len(C) - 2:
        if not sig[i] or np.isnan(atr[i]):
            i += 1
            continue
        j = i + 1
        e, st = O[j], C[i] - 2 * atr[i]
        if e <= st:
            i += 1
            continue
        k, px = j, None
        while k < len(C) - 1:
            if L[k] <= st:
                px, xt = min(O[k], st), T[k] + bar
                break
            if k - j + 1 >= max_bars:
                px, xt = O[k + 1], T[k + 1]
                k += 1
                break
            k += 1
        if px is None:
            break
        if xt - T[j] <= pd.Timedelta(days=10):  # longer means the trade spans missing data: drop it
            out.append((T[j], xt, e, st, px))
        i = k
    return out, cost


def trade_series(trades, cost, h1, idx):
    """Hourly return and hourly low-return for 1% risk per trade (notional = 1% / stop distance).
    Shorts are trades whose stop is above the entry; their adverse move is the hourly high."""
    r, lo = np.zeros(len(idx)), np.zeros(len(idx))
    C, L, H = (h1[k].reindex(idx).ffill().to_numpy() for k in ("c", "l", "h"))
    for et, xt, e, st, px in trades:
        a, z = idx.searchsorted(et), idx.searchsorted(xt)
        if a >= len(idx) or xt <= idx[0]:
            continue
        z = max(z, a + 1)  # a trade always spans at least the hour it was entered in
        dr = 1 if st < e else -1
        n = 0.01 / (abs(e - st) / e)
        prev = e
        for h in range(a, min(z, len(idx))):
            last = h == min(z, len(idx)) - 1
            cur = px if last else C[h]
            r[h] += n * dr * (cur / prev - 1)
            adverse = max(min(L[h], cur), st) if dr == 1 else min(max(H[h], cur), st)
            lo[h] += n * dr * (adverse / prev - 1)
            prev = cur
        r[a] -= n * cost
    return r, lo


def position_series(raw1h, tf, kind, cost, idx):
    b = resample(raw1h, tf)
    c = b.c
    if kind == "mom":
        pos = (c > c.shift(120)).astype(float)
    else:
        pos = (c.ewm(span=20, adjust=False).mean() > c.ewm(span=50, adjust=False).mean()).astype(float)
    pos = pos.shift(1).reindex(idx, method="ffill").fillna(0)   # decided on the bar close, held from the next bar
    C = raw1h.c.reindex(idx).ffill()
    L = raw1h.l.reindex(idx).ffill()
    ret = (C / C.shift(1) - 1).fillna(0)
    lo = (np.minimum(L, C) / C.shift(1) - 1).fillna(0)
    turn = pos.diff().abs().fillna(0)
    return (pos * ret - turn * cost / 2).to_numpy(), (pos * lo).to_numpy()


def evaluate(R, LO, idx, w, start=None, end=None, guard=False, max_loss=0.10, daily=0.05):
    m = np.ones(len(idx), bool)
    if start is not None:
        m &= idx >= start
    if end is not None:
        m &= idx < end
    r, lo = (R[:, m] * w[:, None]).sum(0), (LO[:, m] * w[:, None]).sum(0)
    days = idx[m].floor("D")
    if not guard:  # vectorised path for the weight search
        eq = np.cumprod(1 + r)
        prev = np.concatenate([[1.0], eq[:-1]])
        low = prev * (1 + lo)
        peak = np.maximum.accumulate(np.concatenate([[1.0], eq]))[:-1]
        d = pd.Series(prev, index=days)
        day_open = d.groupby(level=0).transform("first").to_numpy()
        dd = 1 - low / peak
        dl = 1 - low / day_open
        breach = bool((low <= 1 - max_loss).any() or (dl >= daily).any())
        return dict(breach=breach, ret=eq[-1] - 1, dd=dd.max(), worst_day=dl.max())
    eq, peak, max_dd, worst_day, day, day_open, halted_day = 1.0, 1.0, 0.0, 0.0, None, 1.0, None
    for h in range(len(r)):
        if days[h] != day:
            day, day_open = days[h], eq
        if guard and halted_day == day:
            continue
        low = eq * (1 + lo[h])
        if low <= 1 - max_loss or low <= day_open * (1 - daily):
            return dict(breach=True, ret=eq - 1, dd=max(max_dd, 1 - low / peak), worst_day=max(worst_day, 1 - low / day_open))
        worst_day = max(worst_day, 1 - low / day_open)
        max_dd = max(max_dd, 1 - low / peak)
        eq *= 1 + r[h]
        peak = max(peak, eq)
        if guard and (1 - eq / day_open >= 0.8 * daily):
            halted_day = day  # flatten everything for the rest of the day
        if guard and eq <= 1 - 0.8 * max_loss:
            return dict(breach=False, ret=eq - 1, dd=max_dd, worst_day=worst_day, stopped=True)
    return dict(breach=False, ret=eq - 1, dd=max_dd, worst_day=worst_day)


def main():
    btc = load(sys.argv[1]).loc["2019-06-01":]
    fut = {s: load_csv(f"{sys.argv[2]}/{s}.csv") for s in COST}
    idx = pd.date_range(pd.Timestamp("2020-04-01", tz="UTC"), pd.Timestamp("2026-10-30", tz="UTC"), freq="1h")
    comps = {}
    tr, c = dip_trades(btc, "2h", 3, 20, 0.15, FEE_CRYPTO)
    comps["btc_dip"] = trade_series(tr, c, btc, idx)
    tr, c = dip_trades(fut["XAUUSD"], "1h", 2, 10, 0.08, COST["XAUUSD"])
    comps["gold_dip"] = trade_series(tr, c, fut["XAUUSD"], idx)
    comps["nq_mom"] = position_series(fut["USATECHIDXUSD"], "2h", "mom", COST["USATECHIDXUSD"], idx)
    comps["si_trend"] = position_series(fut["XAGUSD"], "2h", "ema", COST["XAGUSD"], idx)
    comps["es_trend"] = position_series(fut["USA500IDXUSD"], "2h", "ema", COST["USA500IDXUSD"], idx)
    names = list(comps)
    R = np.array([comps[k][0] for k in names])
    LO = np.array([comps[k][1] for k in names])
    tr0, tr1 = pd.Timestamp("2020-04-01", tz="UTC"), pd.Timestamp("2024-01-01", tz="UTC")

    print("Daily return correlation between components (2020-2026):")
    daily = pd.DataFrame(R.T, index=idx, columns=names).resample("1D").sum()
    print(daily[daily.abs().sum(axis=1) > 0].corr().round(2).to_string(), "\n")

    grid = dict(btc_dip=[0, 1, 1.5, 2, 2.5, 3], gold_dip=[0, 0.5, 1, 1.5, 2], nq_mom=[0, 0.25, 0.5, 0.75, 1.0],
                si_trend=[0, 0.25, 0.5], es_trend=[0, 0.25, 0.5])
    # prop-style selection: 12-month windows from a fresh account, started monthly in 2020-2022 (train only)
    train_starts = pd.date_range("2020-04-01", "2022-12-01", freq="MS", tz="UTC")
    rows = []
    for combo in itertools.product(*grid.values()):
        w = np.array(combo, dtype=float)
        if not w.any():
            continue
        wins = [evaluate(R, LO, idx, w, s, min(s + pd.DateOffset(years=1), tr1), max_loss=0.08, daily=0.04) for s in train_starts]
        p = np.array([x["ret"] for x in wins]) * 100
        rows.append(dict(zip(names, combo), breaches_tr=sum(x["breach"] for x in wins), med_tr=np.median(p), worst_tr=p.min(),
                         day_tr=100 * max(x["worst_day"] for x in wins)))
    res = pd.DataFrame(rows)
    ok = res[res.breaches_tr == 0].sort_values("med_tr", ascending=False)
    pd.set_option("display.width", 220)
    print(f"{len(res)} weight sets; {len(ok)} never came within 2% of the max-loss line or 1% of the daily limit in any 2020-22 window. Top 10:")
    print(ok.head(10).round(1).to_string(index=False))

    single = np.array([2.0 if k == "btc_dip" else 0 for k in names])  # BTC v3 alone at 2% risk as a reference
    picks = {"BEST PORTFOLIO (picked on 2020-22 windows)": ok.iloc[0][names].to_numpy(dtype=float),
             "BTC v3 alone, 1.5% risk": np.array([1.5 if k == "btc_dip" else 0 for k in names]),
             "BTC v3 alone, 2.0% risk": single}
    yrs_te = (idx[-1] - tr1).days / 365
    starts = pd.date_range("2020-04-01", "2025-10-01", freq="MS", tz="UTC")
    print("\nOut-of-sample check and prop simulation (10% static / 5% daily, guard ON):")
    for name, w in picks.items():
        te = evaluate(R, LO, idx, w, tr1, None)
        wins = [evaluate(R, LO, idx, w, s, s + pd.DateOffset(years=1), guard=True) for s in starts]
        p = np.array([x["ret"] for x in wins]) * 100
        print(f"  {name:<36} weights {dict(zip(names, w))}")
        print(f"     2024-26: {100 * ((1 + te['ret']) ** (1 / yrs_te) - 1):+.1f}%/yr, max DD {100 * te['dd']:.1f}%, worst day {100 * te['worst_day']:.1f}%"
              f" | 12-month prop windows: median {np.median(p):+.1f}%, avg {p.mean():+.1f}%, >=40%: {np.mean(p >= 40) * 100:.0f}%,"
              f" breaches {sum(x['breach'] for x in wins)}/{len(wins)}, worst window {p.min():+.1f}%")
    years = {}
    w = picks["BEST PORTFOLIO (picked on 2020-22 windows)"]
    for y in range(2020, 2027):
        s = evaluate(R, LO, idx, w, pd.Timestamp(f"{y}-01-01", tz="UTC"), pd.Timestamp(f"{y + 1}-01-01", tz="UTC"))
        years[y] = f"{100 * s['ret']:+.0f}% (dd {100 * s['dd']:.0f}%)"
    print("\n  Best portfolio by calendar year:", years)


if __name__ == "__main__":
    main()
