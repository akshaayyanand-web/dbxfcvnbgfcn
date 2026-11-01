"""BTC dip-buying prop lab: exit styles, limit entries, lower timeframes and end-game sizing.

Signal (every timeframe): RSI(3) < 20, close > EMA(50), yesterday's daily close > 200-day SMA.
Exit styles (all keep the 2 x ATR initial stop and the 96-hour time exit):
  base        stop / time only
  tpX         take everything at entry + X x ATR
  beX         move the stop to break-even once price reaches entry + X x ATR
  halfX       take half at entry + X x ATR, then break-even on the rest
  trailA_B    after entry + A x ATR, trail the stop B x ATR under the highest high
Entries: market at the next open (taker fee) or a limit order at the signal close that must fill on
the next bar (maker fee); take-profits are maker, stops and time exits taker.
Several timeframes can be merged into one sequence (one BTC position at a time).

The prop simulator applies +10% target / static -6% / 3% daily (from the day's opening balance),
sizing each trade at a share of the buffer above the fail line, with optional end-game rules.
Parameters are ranked on attempts starting 2020-2023 and reported on attempts starting 2024-2025.
"""
import itertools
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

from backtest_ema_macd import load
from test_rsi2_dip import resample, rma, rsi

TAKER, MAKER = 0.06, 0.02
EXITS = ["base", "tp1.5", "tp2", "tp3", "be1", "be1.5", "half1", "half1.5", "trail1_1.5", "trail1.5_2"]
_FR = {}


def prepare(raw_1h, raw_5m):
    daily = raw_1h.c.resample("1D").last()
    up = (daily > daily.rolling(200).mean()).shift(1)
    for tf, src in (("15m", raw_5m), ("30m", raw_5m), ("1h", raw_1h), ("2h", raw_1h)):
        df = resample(src, {"15m": "15min", "30m": "30min"}.get(tf, tf)).loc["2019-09-01":]
        c = df.c
        tr = pd.concat([df.h - df.l, (df.h - c.shift()).abs(), (df.l - c.shift()).abs()], axis=1).max(axis=1)
        sig = (rsi(c, 3) < 20) & (c > c.ewm(span=50, adjust=False).mean())
        sig &= up.reindex(df.index.floor("D")).fillna(False).to_numpy().astype(bool)
        _FR[tf] = dict(t=df.index, O=df.o.to_numpy(), H=df.h.to_numpy(), L=df.l.to_numpy(), C=c.to_numpy(),
                       atr=rma(tr, 14).to_numpy(), sig=sig.to_numpy(), bar=pd.Timedelta(df.index[1] - df.index[0]))


def parse_exit(name):
    if name == "base":
        return {}
    if name.startswith("tp"):
        return {"tp": float(name[2:])}
    if name.startswith("be"):
        return {"be": float(name[2:])}
    if name.startswith("half"):
        return {"half": float(name[4:])}
    a, b = name[5:].split("_")
    return {"trail_start": float(a), "trail": float(b)}


def trades(tf, exit_name, limit_entry, stop_mult=2.0, hold_h=96):
    f = _FR[tf]
    t, O, H, L, C, atr, sig = f["t"], f["O"], f["H"], f["L"], f["C"], f["atr"], f["sig"]
    ex = parse_exit(exit_name)
    max_bars = max(1, round(hold_h * 3600 / f["bar"].total_seconds()))
    n, i, out = len(C), 0, []
    while i < n - 2:
        if not sig[i] or np.isnan(atr[i]):
            i += 1
            continue
        j = i + 1
        if limit_entry:
            if L[j] > C[i]:  # limit at the signal close did not fill on the next bar
                i += 1
                continue
            entry, fee_in = min(O[j], C[i]), MAKER
        else:
            entry, fee_in = O[j], TAKER
        R = stop_mult * atr[i]
        stop, rem, realized, fees = entry - R, 1.0, 0.0, fee_in / 100
        hh, worst, held, k, px, done = entry, min(0.0, L[j] / entry - 1), 1, j, None, False
        while k < n - 1 and not done:
            if held >= max_bars:
                px, k = O[k + 1], k + 1
                fees += rem * TAKER / 100
                break
            k += 1
            held += 1
            if L[k] <= stop:  # stop first (conservative)
                px = min(O[k], stop)
                worst = min(worst, realized + rem * (px / entry - 1))
                fees += rem * TAKER / 100
                break
            worst = min(worst, realized + rem * (L[k] / entry - 1))
            if "tp" in ex and H[k] >= entry + ex["tp"] * R:
                px = max(O[k], entry + ex["tp"] * R)
                fees += rem * MAKER / 100
                break
            if "half" in ex and rem == 1.0 and H[k] >= entry + ex["half"] * R:
                tp_px = max(O[k], entry + ex["half"] * R)
                realized += 0.5 * (tp_px / entry - 1)
                fees += 0.5 * MAKER / 100
                rem = 0.5
                stop = max(stop, entry * 1.0012)
            if "be" in ex and H[k] >= entry + ex["be"] * R:
                stop = max(stop, entry * 1.0012)
            if "trail" in ex:
                hh = max(hh, H[k])
                if hh >= entry + ex["trail_start"] * R:
                    stop = max(stop, hh - ex["trail"] * R)
        if px is None:
            break
        ret = realized + rem * (px / entry - 1) - fees
        out.append((t[j], t[k] + f["bar"], ret, worst - fees, R / entry))
        i = k
    return out


def merge(lists):
    """One BTC position at a time: walk all trades by entry time, skip those overlapping a held one."""
    allt = sorted((x for lst in lists for x in lst), key=lambda x: x[0])
    out, busy_until = [], None
    for x in allt:
        if busy_until is not None and x[0] < busy_until:
            continue
        out.append(x)
        busy_until = x[1]
    return out


def attempt(tr, start, end=None, frac=0.33, cap=0.022, max_x=1.5, endgame="none", target=0.10, max_loss=0.06, daily=0.03):
    bal, day, day_open = 1.0, None, 1.0
    i0 = np.searchsorted(tr["entry"], np.datetime64(start.tz_convert(None)))
    for idx in range(i0, len(tr["ret"])):
        d = tr["day"][idx]
        if end is not None and tr["entry"][idx] > np.datetime64(end.tz_convert(None)):
            return "open", None
        if d != day:
            day_open, day = bal, d
        buf = bal - (1 - max_loss)
        left = day_open * (daily - 0.002) - max(day_open - bal, 0)
        risk = min(frac * buf, cap * bal, left)
        gap = 1 + target - bal
        if endgame == "cap":      # never risk more than a 1R win needs to finish
            risk = min(risk, max(gap, 0.003))
        elif endgame == "boost":  # when within one full-size win of the target, go for it (still capped)
            if gap <= cap * 1.5:
                risk = min(max(risk, gap / 1.5), cap * bal, left)
        if risk <= 0.001:
            continue
        sp = tr["sp"][idx]
        size = min(risk / sp, max_x)
        if bal + size * tr["worst"][idx] <= 1 - max_loss or bal + size * tr["worst"][idx] <= day_open * (1 - daily):
            return "fail", None
        bal += size * tr["ret"][idx]
        if bal >= 1 + target:
            return "pass", int((tr["entry"][idx] - np.datetime64(start.tz_convert(None))) / np.timedelta64(1, "D"))
    return "open", None


def as_arrays(tr):
    e = np.array([x[0].tz_convert(None) for x in tr], dtype="datetime64[ns]")
    return dict(entry=e, day=e.astype("datetime64[D]"), ret=np.array([x[2] for x in tr]),
                worst=np.array([x[3] for x in tr]), sp=np.array([x[4] for x in tr]))


STARTS = pd.date_range("2020-04-01", "2025-10-01", freq="7D", tz="UTC")
TFSETS = [("2h",), ("1h",), ("30m",), ("15m",), ("1h", "2h"), ("30m", "1h", "2h"), ("15m", "30m", "1h", "2h")]
SIZING = [(0.33, 0.022, 1.5), (0.5, 0.025, 2.0)]


def evaluate(args):
    tfs, exit_name, limit_entry, (frac, cap, mx), endgame = args
    tr = as_arrays(merge([trades(tf, exit_name, limit_entry) for tf in tfs]))
    if len(tr["ret"]) < 30:
        return None
    outs = [attempt(tr, s, s + pd.Timedelta(days=365), frac, cap, mx, endgame) for s in STARTS]
    st = np.array([o[0] for o in outs])
    dd = np.array([o[1] if o[1] is not None else 9999 for o in outs])
    early = np.array([s.year <= 2023 for s in STARTS])
    row = dict(tfs="+".join(tfs), exit=exit_name, entry="limit" if limit_entry else "market",
               sizing=f"{int(frac * 100)}%/{cap * 100:.1f}%/{mx}x", endgame=endgame,
               trades_pm=len(tr["ret"]) / 79, avg_ret=100 * tr["ret"].mean())
    for name, m in (("tr", early), ("va", ~early)):
        row[f"{name}_p30"] = 100 * np.mean(dd[m] <= 30)
        row[f"{name}_p90"] = 100 * np.mean(dd[m] <= 90)
        row[f"{name}_p1y"] = 100 * np.mean(st[m] == "pass")
        row[f"{name}_fail"] = 100 * np.mean(st[m] == "fail")
    return row


if __name__ == "__main__":
    raw1, raw5 = load(sys.argv[1]).loc["2019-06-01":], load(sys.argv[2]).loc["2019-06-01":]
    combos = list(itertools.product(TFSETS, EXITS, [False, True], SIZING, ["none", "cap", "boost"]))
    with Pool(4, initializer=prepare, initargs=(raw1, raw5)) as pool:
        rows = [r for r in pool.map(evaluate, combos, chunksize=8) if r]
    res = pd.DataFrame(rows)
    res.to_pickle(sys.argv[1].rsplit("/", 1)[0] + "/btc_prop_lab.pkl")
    pd.set_option("display.width", 260)
    cols = ["tfs", "exit", "entry", "sizing", "endgame", "trades_pm", "tr_p30", "tr_p90", "tr_p1y", "tr_fail",
            "va_p30", "va_p90", "va_p1y", "va_fail"]
    base = res[(res.tfs == "1h+2h") & (res.exit == "base") & (res.entry == "market") & (res.sizing == "33%/2.2%/1.5x") & (res.endgame == "none")]
    print(f"{len(res)} combinations. tr_ = attempts starting 2020-2023 (used for ranking), va_ = 2024-2025 (unseen)\n")
    print("Reference (BTC 1h+2h, base exit, market, 33% buffer):")
    print(base[cols].round(0).to_string(index=False))
    pick = res[res.tr_fail <= 5].sort_values(["tr_p30", "tr_p90"], ascending=False)
    print("\nTop 15 by TRAIN 30-day pass with TRAIN fail <= 5%:")
    print(pick[cols].head(15).round(0).to_string(index=False))
    print("\nAverage effect of each idea (mean over all other settings):")
    for k in ("exit", "entry", "tfs", "endgame", "sizing"):
        g = res.groupby(k)[["tr_p30", "tr_fail", "va_p30", "va_p90", "va_fail"]].mean().round(0)
        print(f"\n{k}:\n{g.to_string()}")
