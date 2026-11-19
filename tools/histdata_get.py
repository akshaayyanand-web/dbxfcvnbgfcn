"""Fetch HistData.com free 1-minute ASCII files the way the site's own download form does. Sequential, with pauses.
Usage: python3 hd_get.py OUT_DIR PAIR YEAR [MONTH]"""
import re, sys, time, urllib.request, urllib.parse
out, pair, year = sys.argv[1], sys.argv[2].lower(), sys.argv[3]; month = sys.argv[4] if len(sys.argv) > 4 else None
page = f"https://www.histdata.com/download-free-forex-historical-data/?/ascii/1-minute-bar-quotes/{pair}/{year}" + (f"/{int(month)}" if month else "")
html = urllib.request.urlopen(page, timeout=60).read().decode("utf-8", "ignore")
tk = re.search(r'name="tk" id="tk" value="([0-9a-f]+)"', html).group(1)
dm = re.search(r'name="datemonth" id="datemonth" value="(\d+)"', html).group(1)
data = urllib.parse.urlencode(dict(tk=tk, date=year, datemonth=dm, platform="ASCII", timeframe="M1", fxpair=pair.upper())).encode()
req = urllib.request.Request("https://www.histdata.com/get.php", data=data, headers={"Referer": page})
raw = urllib.request.urlopen(req, timeout=180).read()
fn = f"{out}/{pair.upper()}_{dm}.zip"; open(fn, "wb").write(raw); print(fn, len(raw), raw[:2])
