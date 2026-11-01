"""Download Dukascopy hourly candles (monthly .bi5 files) and save them as CSV.

Each monthly file holds big-endian records of 24 bytes:
  uint32 seconds since the start of the month, int32 open, close, low, high (price x 1000),
  float32 volume. Months are 0-based in the URL. Prices are BID.

Usage: python3 dukascopy.py OUT_DIR SYMBOL [SYMBOL ...] [--start 2016] [--end 2026]
Symbols used here: USATECHIDXUSD (Nasdaq 100), USA500IDXUSD (S&P 500), USA30IDXUSD (Dow),
USSC2000IDXUSD (Russell 2000), XAUUSD (gold), XAGUSD (silver), LIGHTCMDUSD (WTI crude).
"""
import argparse
import lzma
import os
import struct
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pandas as pd

URL = "https://datafeed.dukascopy.com/datafeed/{sym}/{y}/{m:02d}/BID_candles_hour_1.bi5"


def fetch_month(sym, y, m, tries=6):
    raw = None
    for k in range(tries):
        try:
            with urllib.request.urlopen(URL.format(sym=sym, y=y, m=m - 1), timeout=90) as r:
                raw = r.read()
            break
        except Exception:
            time.sleep(2 * (k + 1))
    if raw is None:
        print(f"  missing {sym} {y}-{m:02d}", flush=True)
        return []
    if not raw:
        return []
    data = lzma.decompress(raw)
    base = datetime(y, m, 1, tzinfo=timezone.utc).timestamp()
    rows = []
    for k in range(0, len(data) - 23, 24):
        t, o, c, lo, hi, v = struct.unpack(">Iiiiif", data[k:k + 24])
        rows.append((base + t, o, hi, lo, c, v))
    return rows


def download(sym, start, end, now):
    months = [(y, m) for y in range(start, end + 1) for m in range(1, 13) if (y, m) < (now.year, now.month)]
    with ThreadPoolExecutor(4) as ex:
        parts = list(ex.map(lambda ym: fetch_month(sym, *ym), months))
    rows = [r for p in parts for r in p]
    df = pd.DataFrame(rows, columns=["t", "o", "h", "l", "c", "v"])
    df["t"] = pd.to_datetime(df.t, unit="s", utc=True)
    df = df.drop_duplicates("t").set_index("t").sort_index()
    df[["o", "h", "l", "c"]] /= 1000.0
    return df[df.v > 0]  # drop closed-market placeholder hours


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("symbols", nargs="+")
    ap.add_argument("--start", type=int, default=2016)
    ap.add_argument("--end", type=int, default=2026)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    now = datetime.now(timezone.utc)
    for s in a.symbols:
        df = download(s, a.start, a.end, now)
        df.to_csv(os.path.join(a.out_dir, f"{s}.csv"))
        print(f"{s}: {len(df)} hourly bars {df.index[0]} .. {df.index[-1]}, last close {df.c.iloc[-1]:.2f}")
