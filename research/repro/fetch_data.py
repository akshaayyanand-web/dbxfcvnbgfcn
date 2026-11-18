"""Download every raw dataset used by the research into $RSCRATCH (default: the original scratch path). Re-runnable (skips existing files).
Usage: RSCRATCH=/path/to/data python3 repro/fetch_data.py [--skip-intraday]"""
import os, sys, json, time, subprocess, urllib.request, datetime as dt
H = os.path.dirname(os.path.abspath(__file__)); S = os.environ.get("RSCRATCH", "/tmp/claude-0/-home-user-dbxfcvnbgfcn/0ea82c59-9b45-5b6c-b663-efd40f90c87c/scratchpad")
TOOLS = os.path.join(os.path.dirname(os.path.dirname(H)), "tools")
def get(url, path, tries=4):
    if os.path.exists(path) and os.path.getsize(path) > 0: return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "research-client"}); data = urllib.request.urlopen(req, timeout=120).read(); open(path, "wb").write(data); return
        except Exception as e:
            if "404" in str(e): return
            time.sleep(2 ** k)
def url_list(fname, sub, extract_zip_csv=False):
    for u in open(os.path.join(H, fname)).read().split():
        get(u, os.path.join(S, sub, os.path.basename(u)))
if __name__ == "__main__":
    skip_intra = "--skip-intraday" in sys.argv
    url_list("urls_binance_spot_1h.txt", "kh"); url_list("urls_binance_funding.txt", "kf")
    for u in open(os.path.join(H, "urls_binance_derivatives.txt")).read().split():
        sub = "cdata/" + ("um" if "/um/monthly/klines" in u else "prem" if "premiumIndex" in u else "met" if "metrics" in u else "cm"); get(u, os.path.join(S, sub, os.path.basename(u)))
    for s in open(os.path.join(H, "fred_series.txt")).read().split(): get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={s}", f"{S}/rdata/fred/{s}.csv")
    for z in ["F-F_Research_Data_5_Factors_2x3_daily_CSV", "F-F_Research_Data_Factors_daily_CSV", "49_Industry_Portfolios_daily_CSV", "10_Industry_Portfolios_daily_CSV", "F-F_Momentum_Factor_daily_CSV", "10_Portfolios_Prior_12_2_Daily_CSV", "F-F_ST_Reversal_Factor_daily_CSV"]:
        p = f"{S}/rdata/french/{z}.zip"; get(f"https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/{z}.zip", p); subprocess.run(["unzip", "-o", "-q", p, "-d", f"{S}/rdata/french"])
    for f in ["SKEW", "VIX9D", "VVIX", "VIX3M", "VIX"]: get(f"https://cdn.cboe.com/api/global/us_indices/daily_prices/{f}_History.csv", f"{S}/rdata/cboe/{f}.csv")
    for c in ["BTC", "ETH"]:
        for a, b in (("1614556800000", "1700000000000"), ("1700000000000", "1800000000000")): get(f"https://www.deribit.com/api/v2/public/get_volatility_index_data?currency={c}&start_timestamp={a}&end_timestamp={b}&resolution=1D", f"{S}/cdata/misc/dvol_{c}_{a}.json")
    get("https://stablecoins.llama.fi/stablecoincharts/all", f"{S}/cdata/misc/stablecoins.json")
    for ch in ["hash-rate", "miners-revenue", "difficulty", "n-transactions"]: get(f"https://api.blockchain.info/charts/{ch}?timespan=all&format=json&sampled=false", f"{S}/cdata/misc/{ch}.json")
    # independent sources for the STRAT-0053 reproduction
    for p in ["BTC", "ETH", "LTC", "XRP", "BCH", "LINK", "ADA", "DOGE", "SOL", "AVAX", "DOT"]: get(f"https://www.cryptodatadownload.com/cdd/Bitstamp_{p}USD_d.csv", f"{S}/indep/bs/{p}USD.csv")
    os.makedirs(f"{S}/indep/cb", exist_ok=True)
    for c in ["BTC", "ETH", "ADA", "AVAX", "BCH", "DOGE", "DOT", "LINK", "LTC", "SOL", "XRP"]:
        if os.path.exists(f"{S}/indep/cb/{c}.json"): continue
        rows = []; s = dt.datetime(2019, 1, 1); end = dt.datetime(2026, 11, 1)
        while s < end:
            e = min(s + dt.timedelta(days=299), end)
            try: rows += json.load(urllib.request.urlopen(urllib.request.Request(f"https://api.exchange.coinbase.com/products/{c}-USD/candles?granularity=86400&start={s:%Y-%m-%dT00:00:00Z}&end={e:%Y-%m-%dT00:00:00Z}", headers={"User-Agent": "research-client"}), timeout=30))
            except Exception: pass
            s = e + dt.timedelta(days=1); time.sleep(0.25)
        json.dump(rows, open(f"{S}/indep/cb/{c}.json", "w"))
    # Dukascopy CFDs (hourly 2016+, 1-minute 2019+/2021+) via the repository's own fetchers
    subprocess.run([sys.executable, f"{TOOLS}/dukascopy.py", f"{S}/fut", "USATECHIDXUSD", "USA500IDXUSD", "USA30IDXUSD", "USSC2000IDXUSD", "XAUUSD", "XAGUSD", "LIGHTCMDUSD", "--start", "2016", "--end", "2026"])
    if not skip_intra:
        for sym, y0, sub in (("USATECHIDXUSD", 2019, "fut1m"), ("USA500IDXUSD", 2019, "fut1m"), ("XAUUSD", 2019, "fut1m"), ("DEUIDXEUR", 2021, "eu1m"), ("EURUSD", 2019, "fx1m"), ("AUDCAD", 2019, "fx1m")):
            subprocess.run([sys.executable, f"{TOOLS}/dukascopy_min.py", f"{S}/{sub}", sym, str(y0), "2026"])
        for u in open(os.path.join(H, "urls_binance_microstructure_sample.txt")).read().split():
            sub = "mdata/" + ("agg" if "aggTrades" in u else "depth" if "bookDepth" in u else "k1"); get(u, os.path.join(S, sub, os.path.basename(u)))
    print("done")
