"""Run the strategy families from this project on index / metal / oil futures proxies (Dukascopy CFDs).

Engine A – stop-based dip / spike strategies (the BTC v2/v3 family and its mirror short):
    long : RSI(n) < buy and close > EMA(trend) [+ regime filter]; short: RSI(n) > 100 - buy and close < EMA
    regime: none | crash (no longs after a >X% 30-day drop, no shorts after a >X% 30-day rise) |
            sma200 (longs only above the daily 200-SMA, shorts only below)
    stop k x ATR(14) attached at entry, time exit after H hours, entry at the next bar's open.
Engine B – always-in / position strategies from the earlier labs (Donchian, time-series momentum,
    EMA cross, trend ensemble, Bollinger squeeze), 1x notional.

Mode "overnight": positions may be held for days. Mode "topstep": everything is closed before
15:00 Chicago time (Topstep requires flat by 15:10 CT) and no entries until the 17:00 CT reopen.

Train = 2016-2022, test = 2023-2026. Ranking uses train only.
Usage: python3 futures_lab.py DATA_DIR
"""
import glob
import itertools
import os
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

from research_lab2 import trend_ens
from research_lab3 import bb_squeeze
from strategy_lab import donchian, ema_cross, tsmom
from test_rsi2_dip import rma, rsi

COST = {"USATECHIDXUSD": 0.00012, "USA500IDXUSD": 0.00010, "USA30IDXUSD": 0.00012, "USSC2000IDXUSD": 0.00020,
        "XAUUSD": 0.00010, "XAGUSD": 0.00025, "LIGHTCMDUSD": 0.00030}  # round-trip cost as a fraction of price
NAMES = {"USATECHIDXUSD": "Nasdaq (NQ)", "USA500IDXUSD": "S&P 500 (ES)", "USA30IDXUSD": "Dow (YM)",
         "USSC2000IDXUSD": "Russell (RTY)", "XAUUSD": "Gold (GC)", "XAGUSD": "Silver (SI)", "LIGHTCMDUSD": "Crude (CL)"}
_D = {}


def load_csv(path):
    df = pd.read_csv(path, index_col=0)
    df.index = pd.to_datetime(df.index, utc=True)
    return df


def prep(data_dir):
    for p in sorted(glob.glob(os.path.join(data_dir, "*.csv"))):
        sym = os.path.basename(p)[:-4]
        if sym not in COST:
            continue
        raw = load_csv(p)
        daily = raw.c.resample("1D").last().dropna()
        for tf in ("1h", "2h", "4h"):
            df = raw if tf == "1h" else raw.resample(tf).agg({"o": "first", "h": "max", "l": "min", "c": "last", "v": "sum"}).dropna()
            ct = df.index.tz_convert("America/Chicago")
            bar_h = pd.Timedelta(tf).total_seconds() / 3600
            start_h = ct.hour + ct.minute / 60
            end_h = start_h + bar_h
            # a bar must be closed out if it covers any time in [15:00, 17:00) CT or the weekend break
            must_flat = ((start_h < 17) & (end_h > 15)) | (ct.dayofweek == 5) | ((ct.dayofweek == 4) & (end_h > 15)) | ((ct.dayofweek == 6) & (start_h < 17))
            tr = pd.concat([df.h - df.l, (df.h - df.c.shift()).abs(), (df.l - df.c.shift()).abs()], axis=1).max(axis=1)
            day_idx = df.index.floor("D")
            ch30 = (daily / daily.shift(30) - 1).shift(1).reindex(day_idx).to_numpy()
            above = (daily > daily.rolling(200).mean()).shift(1).reindex(day_idx).fillna(False).to_numpy().astype(bool)
            below = (daily < daily.rolling(200).mean()).shift(1).reindex(day_idx).fillna(False).to_numpy().astype(bool)
            _D[(sym, tf)] = dict(df=df, O=df.o.to_numpy(), H=df.h.to_numpy(), L=df.l.to_numpy(), C=df.c.to_numpy(),
                                 atr=rma(tr, 14).to_numpy(), flat=np.asarray(must_flat), t=df.index, bar_h=bar_h,
                                 rsi={n: rsi(df.c, n).to_numpy() for n in (2, 3)},
                                 ema={n: df.c.ewm(span=n, adjust=False).mean().to_numpy() for n in (50, 200)},
                                 ch30=ch30, above=above, below=below, cost=COST[sym])


def engine_a(key, rl, buy, trend, regime, stop_k, hold_h, side, mode, crash_pct=0.08):
    d = _D[key]
    O, H, L, C, atr, flat, t = d["O"], d["H"], d["L"], d["C"], d["atr"], d["flat"], d["t"]
    r, e = d["rsi"][rl], d["ema"][trend]
    if side == "long":
        sig = (r < buy) & (C > e)
        if regime == "crash":
            sig &= ~(d["ch30"] < -crash_pct)
        elif regime == "sma200":
            sig &= d["above"]
    else:
        sig = (r > 100 - buy) & (C < e)
        if regime == "crash":
            sig &= ~(d["ch30"] > crash_pct)
        elif regime == "sma200":
            sig &= d["below"]
    sig &= ~np.isnan(atr)
    if mode == "topstep":
        sig[:-1] &= ~flat[1:]  # never enter on a bar that must already be flat
    dr = 1 if side == "long" else -1
    max_bars = max(1, round(hold_h / d["bar_h"]))
    n, i, out = len(C), 0, []
    idx = np.flatnonzero(sig)
    p = 0
    while p < len(idx):
        i = idx[p]
        j = i + 1
        if j >= n - 1:
            break
        entry = O[j]
        st = C[i] - dr * stop_k * atr[i]
        risk = abs(entry - st) / entry
        if risk <= 0 or (dr * (entry - st) <= 0):
            p += 1
            continue
        k, px = j, None
        while k < n - 1:
            if (L[k] <= st) if dr == 1 else (H[k] >= st):
                px = min(O[k], st) if dr == 1 else max(O[k], st)
                break
            if k - j + 1 >= max_bars or (mode == "topstep" and flat[k + 1]):
                px, k = O[k + 1], k + 1
                break
            k += 1
        if px is None:
            break
        out.append((t[j], (dr * (px / entry - 1) - d["cost"]) / risk))
        p = np.searchsorted(idx, k, side="left")  # next signal from the exit bar on
    return out


def yearly_at_risk(trades, risk=0.01):
    if not trades:
        return {}
    df = pd.DataFrame(trades, columns=["t", "R"])
    return {y: 100 * (np.prod(1 + risk * g.R) - 1) for y, g in df.groupby(df.t.dt.year)}


def run_a(args):
    key = args[0]
    tr = engine_a(*args)
    if len(tr) < 30:
        return None
    yr = yearly_at_risk(tr)
    R = np.array([x[1] for x in tr])
    years = np.array([x[0].year for x in tr])
    a, b = R[years <= 2022], R[years >= 2023]
    tr_y = [v for y, v in yr.items() if y <= 2022]
    te_y = [v for y, v in yr.items() if y >= 2023]
    if len(a) < 20 or len(b) < 10:
        return None
    _, rl, buy, trend, regime, stop_k, hold_h, side, mode = args
    return dict(market=NAMES[key[0]], tf=key[1], engine="A dip/spike", strat=f"{side} RSI{rl}<{buy if side == 'long' else 100 - buy} EMA{trend} {regime} stop{stop_k} hold{hold_h}h",
                mode=mode, n_train=len(a), R_train=a.mean(), yr_train=np.mean(tr_y), worst_train=min(tr_y),
                n_test=len(b), R_test=b.mean(), yr_test=np.mean(te_y), worst_test=min(te_y), trades_per_month=len(R) / 125)


def run_b(args):
    key, fam, params, mode = args
    d = _D[key]
    df = d["df"]
    fn = {"donchian": donchian, "tsmom": tsmom, "ema_cross": ema_cross, "trend_ens": None, "bb_squeeze": bb_squeeze}[fam]
    if fam == "trend_ens":
        bpy = 365 * 24 / d["bar_h"]
        pos = trend_ens(df, None, key[1], params["vol"], params["shorts"], bpy)
    else:
        pos = fn(df, **params)
    pos = pd.Series(np.asarray(pos, dtype=float), index=df.index).fillna(0)
    if mode == "topstep":
        pos = pos.where(~pd.Series(d["flat"], index=df.index).shift(-1, fill_value=True), 0)
    p = pos.shift(1).fillna(0)
    r = p * (df.o.shift(-1) / df.o - 1).fillna(0) - p.diff().abs().fillna(p.abs()) * d["cost"] / 2
    bpy = 365 * 24 / d["bar_h"] * (5 / 7)
    out = {}
    for name, sl in (("train", r[r.index.year <= 2022]), ("test", r[r.index.year >= 2023])):
        if len(sl) < 100 or sl.std() == 0:
            return None
        out[name] = (sl.mean() / sl.std() * np.sqrt(bpy), 100 * ((1 + sl).prod() ** (bpy / len(sl)) - 1))
    return dict(market=NAMES[key[0]], tf=key[1], engine="B position", strat=f"{fam} {params}", mode=mode,
                sharpe_train=out["train"][0], yr1x_train=out["train"][1], sharpe_test=out["test"][0], yr1x_test=out["test"][1])


if __name__ == "__main__":
    prep(sys.argv[1])
    keys = sorted(_D)
    jobs_a = [(k, rl, buy, trend, reg, sk, hh, side, mode)
              for k in keys for (rl, buy) in ((2, 10), (3, 20)) for trend in (50, 200) for reg in ("none", "crash", "sma200")
              for sk in (1.5, 2.0, 3.0) for hh in (24, 96) for side in ("long", "short") for mode in ("overnight", "topstep")]
    fams = [("donchian", dict(n=n, m=m, shorts=s)) for n, m in ((20, 10), (55, 20), (100, 50)) for s in (False, True)] + \
           [("tsmom", dict(look=lb, shorts=s)) for lb in (24, 120, 480) for s in (False, True)] + \
           [("ema_cross", dict(fast=f, slow=sl, shorts=s)) for f, sl in ((20, 50), (50, 200)) for s in (False, True)] + \
           [("trend_ens", dict(vol=v, shorts=s)) for v in (20,) for s in (False, True)] + \
           [("bb_squeeze", dict(n=n, shorts=s)) for n in (50,) for s in (False, True)]
    jobs_b = [(k, f, p, mode) for k in keys for f, p in fams for mode in ("overnight", "topstep")]
    with Pool(4, initializer=prep, initargs=(sys.argv[1],)) as pool:
        ra = [r for r in pool.map(run_a, jobs_a, chunksize=16) if r]
        rb = [r for r in pool.map(run_b, jobs_b, chunksize=4) if r]
    A, B = pd.DataFrame(ra), pd.DataFrame(rb)
    A.to_pickle(os.path.join(sys.argv[1], "lab_A.pkl"))
    B.to_pickle(os.path.join(sys.argv[1], "lab_B.pkl"))
    pd.set_option("display.width", 260)
    pd.set_option("display.max_colwidth", 70)
    print(f"Engine A: {len(A)} configs, engine B: {len(B)} configs\n")
    colsA = ["market", "tf", "mode", "strat", "trades_per_month", "R_train", "yr_train", "worst_train", "R_test", "yr_test", "worst_test"]
    for mode in ("topstep", "overnight"):
        sub = A[(A["mode"] == mode) & (A.worst_train > -5)].sort_values("yr_train", ascending=False)
        print(f"=== Engine A, {mode}: top 15 by TRAIN avg year at 1% risk (worst train year > -5%) ===")
        print(sub[colsA].head(15).round(2).to_string(index=False))
        top = sub.head(30)
        print(f"   top-30 by train -> TEST avg {top.yr_test.mean():+.1f}%/yr, positive {(top.yr_test > 0).sum()}/30\n")
    colsB = ["market", "tf", "mode", "strat", "sharpe_train", "yr1x_train", "sharpe_test", "yr1x_test"]
    for mode in ("topstep", "overnight"):
        sub = B[B["mode"] == mode].sort_values("sharpe_train", ascending=False)
        print(f"=== Engine B, {mode}: top 10 by TRAIN Sharpe ===")
        print(sub[colsB].head(10).round(2).to_string(index=False))
        print()
