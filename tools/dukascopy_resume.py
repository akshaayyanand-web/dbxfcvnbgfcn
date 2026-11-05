# Resumable Dukascopy 1m downloader: one small CSV per day, skips days already saved.
import os, sys, time, lzma, struct, urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
out, sym, y0, y1 = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
URL = "https://datafeed.dukascopy.com/datafeed/{s}/{y}/{m:02d}/{d:02d}/BID_candles_min_1.bi5"
def get(day):
    fn = os.path.join(out, f"{day.isoformat()}.csv")
    if os.path.exists(fn): return 1
    for k in range(8):
        try:
            with urllib.request.urlopen(URL.format(s=sym, y=day.year, m=day.month - 1, d=day.day), timeout=60) as r: raw = r.read()
            break
        except Exception: time.sleep(1.5 * (k + 1))
    else: return 0
    base = datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp(); rows = []
    if raw:
        data = lzma.decompress(raw)
        for k in range(0, len(data) - 23, 24):
            t, o, c, lo, hi, v = struct.unpack(">Iiiiif", data[k:k + 24])
            if v > 0: rows.append(f"{int(base + t)},{o/1000},{hi/1000},{lo/1000},{c/1000},{v}")
    with open(fn + ".tmp", "w") as f: f.write("\n".join(rows))
    os.replace(fn + ".tmp", fn); return 1
days = [date(y0, 1, 1) + timedelta(n) for n in range((date(y1, 12, 31) - date(y0, 1, 1)).days + 1)]
days = [d for d in days if d.weekday() < 5 and d < date.today()]
done = 0
with ThreadPoolExecutor(8) as ex:
    for i, ok in enumerate(ex.map(get, days)):
        done += ok
        if i % 100 == 0: print(f"{i}/{len(days)} days processed, {done} saved", flush=True)
print(f"finished: {done} of {len(days)} days saved", flush=True)
