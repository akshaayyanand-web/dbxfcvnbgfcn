"""Find months with no data in the Dukascopy hourly CSVs and fetch them again, slowly and with retries.

Usage: python3 fill_gaps.py DATA_DIR SYMBOL [SYMBOL ...]
"""
import sys
import time

import pandas as pd

from dukascopy import fetch_month
from futures_lab import load_csv

if __name__ == "__main__":
    d = sys.argv[1]
    for sym in sys.argv[2:]:
        df = load_csv(f"{d}/{sym}.csv")
        have = set(zip(df.index.year, df.index.month))
        first = (df.index[0].year, df.index[0].month)
        months = [(y, m) for y in range(first[0], 2027) for m in range(1, 13) if first <= (y, m) <= (2026, 10)]
        missing = [ym for ym in months if ym not in have]
        got = []
        for y, m in missing:
            rows = fetch_month(sym, y, m, tries=10)
            if rows:
                got.extend(rows)
            time.sleep(1)
        if got:
            add = pd.DataFrame(got, columns=["t", "o", "h", "l", "c", "v"])
            add["t"] = pd.to_datetime(add.t, unit="s", utc=True)
            add = add.set_index("t")
            add[["o", "h", "l", "c"]] /= 1000.0
            df = pd.concat([df, add[add.v > 0]]).sort_index()
            df = df[~df.index.duplicated()]
            df.to_csv(f"{d}/{sym}.csv")
        still = [ym for ym in months if ym not in set(zip(df.index.year, df.index.month))]
        print(f"{sym}: {len(missing)} missing months, {len(missing) - len(still)} filled, still missing: {still}", flush=True)
