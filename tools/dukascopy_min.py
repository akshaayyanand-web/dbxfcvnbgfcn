"""Download Dukascopy 1-minute candles (one .bi5 file per day) and save them as CSV.

Record layout as in dukascopy.py; times are seconds from the start of the day (UTC).
Usage: python3 dukascopy_min.py OUT_DIR SYMBOL START_YEAR END_YEAR
"""
import lzma
import os
import struct
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

import pandas as pd

URL = "https://datafeed.dukascopy.com/datafeed/{s}/{y}/{m:02d}/{d:02d}/BID_candles_min_1.bi5"


def fetch_day(sym, day):
    raw = None
    for k in range(5):
        try:
            with urllib.request.urlopen(URL.format(s=sym, y=day.year, m=day.month - 1, d=day.day), timeout=90) as r:
                raw = r.read()
            break
        except Exception:
            time.sleep(2 * (k + 1))
    if not raw:
        return []
    data = lzma.decompress(raw)
    base = datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp()
    out = []
    for k in range(0, len(data) - 23, 24):
        t, o, c, lo, hi, v = struct.unpack(">Iiiiif", data[k:k + 24])
        if v > 0:
            out.append((base + t, o / 1000, hi / 1000, lo / 1000, c / 1000, v))
    return out


if __name__ == "__main__":
    out_dir, sym, y0, y1 = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    os.makedirs(out_dir, exist_ok=True)
    days = [date(y0, 1, 1) + timedelta(n) for n in range((date(y1, 12, 31) - date(y0, 1, 1)).days + 1)]
    days = [d for d in days if d.weekday() < 5 and d < date.today()]
    with ThreadPoolExecutor(8) as ex:
        parts = list(ex.map(lambda d: fetch_day(sym, d), days))
    df = pd.DataFrame([r for p in parts for r in p], columns=["t", "o", "h", "l", "c", "v"])
    df["t"] = pd.to_datetime(df.t, unit="s", utc=True)
    df.drop_duplicates("t").set_index("t").sort_index().to_csv(os.path.join(out_dir, f"{sym}_1m.csv"))
    print(f"{sym}: {len(df)} minute bars, {sum(1 for p in parts if p)} of {len(days)} days")
