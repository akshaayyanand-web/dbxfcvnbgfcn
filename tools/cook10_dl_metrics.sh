#!/bin/bash
# Binance USD-M futures daily "metrics" files (5-min OI / long-short ratios), sequential with a pause between requests.
cd "$(dirname "$0")/metrics_raw"
for sym in BTCUSDT ETHUSDT; do
  d=2020-09-01
  while [[ "$d" < "2026-11-26" ]]; do
    f="$sym-metrics-$d.zip"
    if [ ! -s "$f" ]; then
      code=$(curl -s --retry 3 -o "$f" -w "%{http_code}" "https://data.binance.vision/data/futures/um/daily/metrics/$sym/$f")
      [ "$code" != "200" ] && rm -f "$f"
      sleep 0.25
    fi
    d=$(date -I -d "$d + 1 day")
  done
  echo "$sym done $(ls $sym-* 2>/dev/null | wc -l)"
done
echo DONE
