"""Scan the two intraday setup families that held up (session-range breakout, intraday momentum) across
all seven futures proxies with a parameter grid, to find extra day-trade components for the portfolio.

Metals / crude run on the London clock (Asia range then London session); indices on the New York clock
(overnight range then the cash session). Every trade closes the same day. Parameters are judged on
2016-2022 (train); 2023-2026 is reported as-is, plus the share of neighbouring settings that stay positive.

Usage: python3 intraday_scan.py FUTURES_DIR
"""
import itertools
import sys
from multiprocessing import Pool

import pandas as pd

from futures_lab import load_csv
from intraday_lab import intraday_momentum, range_breakout, summarize

COST = {"USATECHIDXUSD": 0.00012, "USA500IDXUSD": 0.0001, "USA30IDXUSD": 0.00012, "USSC2000IDXUSD": 0.0002,
        "XAUUSD": 0.0001, "XAGUSD": 0.00025, "LIGHTCMDUSD": 0.0003}
NAME = {"USATECHIDXUSD": "NQ", "USA500IDXUSD": "ES", "USA30IDXUSD": "YM", "USSC2000IDXUSD": "RTY",
        "XAUUSD": "Gold", "XAGUSD": "Silver", "LIGHTCMDUSD": "Crude"}
LONDON = {"XAUUSD", "XAGUSD", "LIGHTCMDUSD"}
_DATA = {}


def init(d):
    for s in COST:
        _DATA[s] = load_csv(f"{d}/{s}.csv")


def jobs():
    out = []
    for s in COST:
        if s in LONDON:
            for r_end, w_end, flat, stop, both in itertools.product([6, 7, 8], [12, 14, 16], [18, 20], ["mid", "other"], [False, True]):
                out.append((s, "range_bo", dict(tz="Europe/London", r0=0, r1=r_end, w0=r_end, w1=w_end, flat_h=flat, stop_mode=stop, target=None, both=both)))
            for sig, thr, both, satr in itertools.product([9, 10, 11], [0.003, 0.006, 0.01], [False, True], [1.0, 1.5, 2.0]):
                out.append((s, "momentum", dict(tz="Europe/London", ref_h=17, sig_h=sig, flat_h=16, thr=thr, follow=True, both=both, stop_atr=satr)))
        else:
            for w_end, stop, target, both in itertools.product([12, 13, 14], ["mid", "other"], [None, 2.0], [False, True]):
                out.append((s, "range_bo", dict(tz="America/New_York", r0=0, r1=9, w0=10, w1=w_end, flat_h=15, stop_mode=stop, target=target, both=both)))
            for sig, thr, both, satr in itertools.product([10, 11, 12], [0.004, 0.006, 0.008], [False, True], [1.0, 1.5, 2.0]):
                out.append((s, "momentum", dict(tz="America/New_York", ref_h=16, sig_h=sig, flat_h=15, thr=thr, follow=True, both=both, stop_atr=satr)))
    return out


def run(job):
    s, fam, p = job
    df = _DATA[s]
    if fam == "range_bo":
        tr = range_breakout(df, p["tz"], p["r0"], p["r1"], p["w0"], p["w1"], p["flat_h"], p["stop_mode"], p["target"], p["both"], COST[s])
    else:
        tr = intraday_momentum(df, p["tz"], p["ref_h"], p["sig_h"], p["flat_h"], p["thr"], p["follow"], p["both"], COST[s], p["stop_atr"])
    r = summarize(f"{NAME[s]} {fam}", tr)
    if r:
        r.update(market=NAME[s], family=fam, params={k: v for k, v in p.items() if k not in ("tz", "follow", "r0")})
    return r


if __name__ == "__main__":
    with Pool(4, initializer=init, initargs=(sys.argv[1],)) as pool:
        res = pd.DataFrame([r for r in pool.map(run, jobs(), chunksize=4) if r])
    res.to_pickle(f"{sys.argv[1]}/intraday_scan.pkl")
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 110)
    g = res.groupby(["market", "family"])
    summ = g.apply(lambda x: pd.Series(dict(configs=len(x), train_pos=100 * (x.yr_train > 0).mean(), test_pos=100 * (x.yr_test > 0).mean(),
                                            med_test=x.yr_test.median()))).round(1)
    print("Neighbourhood view – share of ALL settings positive (train / test) and median test %/yr at 1% risk:")
    print(summ.to_string(), "\n")
    best = res[(res.worst_train > -8)].sort_values("yr_train", ascending=False).groupby(["market", "family"]).head(1)
    cols = ["market", "family", "params", "trades_pm", "R_train", "yr_train", "worst_train", "R_test", "yr_test", "worst_test"]
    print("Best setting per market x family, picked on TRAIN (worst train year > -8%):")
    print(best[cols].round(2).to_string(index=False))
