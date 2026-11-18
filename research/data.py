"""Daily market panels for the strategy research catalogue. Every series is built point-in-time from raw files;
nothing is forward-filled across more than 3 days. Panels are cached in RDATA/panels.pkl.
Sources: Binance spot klines (data.binance.vision), Dukascopy CFD bars, FRED (St. Louis Fed), Ken French data library."""
import os, glob, pickle, numpy as np, pandas as pd
SCR = os.environ.get("RSCRATCH", "/tmp/claude-0/-home-user-dbxfcvnbgfcn/0ea82c59-9b45-5b6c-b663-efd40f90c87c/scratchpad")
RDATA = f"{SCR}/rdata"
COST = {"crypto": 6.0, "index": 1.5, "metal": 2.0, "energy": 4.0, "fx": 1.0, "rates": 1.0, "industry": 5.0, "commod_spot": 5.0}  # bps per side (spread+fee+slippage)

def _crypto():
    out = {}
    for f in sorted(glob.glob(f"{SCR}/kh/*USDT.csv")):
        d = pd.read_csv(f, header=None, usecols=[0, 1, 2, 3, 4, 5, 9])
        d.columns = ["t", "o", "h", "l", "c", "v", "tbv"]
        t = d.t.astype("int64"); t = np.where(t > 1e14, t // 1000, t)
        d.index = pd.to_datetime(t, unit="ms", utc=True); d = d[~d.index.duplicated()].sort_index()
        out[os.path.basename(f)[:-8]] = d[["o", "h", "l", "c", "v", "tbv"]]
    return out

def _cfd():
    names = {"USATECHIDXUSD": "NQ", "USA500IDXUSD": "SPX", "USA30IDXUSD": "DJI", "USSC2000IDXUSD": "RUT", "XAUUSD": "GOLD", "XAGUSD": "SILVER", "LIGHTCMDUSD": "WTI"}
    out = {}
    for f, n in names.items():
        d = pd.read_csv(f"{SCR}/fut/{f}.csv", parse_dates=["t"]).set_index("t"); out[n] = d
    return out

def _fred(s):
    d = pd.read_csv(f"{RDATA}/fred/{s}.csv"); d.columns = ["date", s]
    d["date"] = pd.to_datetime(d["date"]); d[s] = pd.to_numeric(d[s], errors="coerce"); return d.set_index("date")[s].dropna()

def _par_bond_ret(y, n):
    """Daily total return of a constant-maturity par bond from a yield series (%): buy at yesterday's par yield, reprice at today's."""
    y = y / 100; yp = y.shift(1); c = yp / 2; m = 2 * n
    price = np.where(y > 0, c / (y / 2) * (1 - (1 + y / 2) ** (-m)) + (1 + y / 2) ** (-m), 1.0)
    return pd.Series(price - 1 + yp / 252, index=y.index).iloc[1:]

def _french(fn, block="Average Value Weighted Returns -- Daily"):
    lines = open(f"{RDATA}/french/{fn}").read().splitlines()
    i0 = next(i for i, l in enumerate(lines) if block in l) + 1
    hdr = [h.strip() for h in lines[i0].split(",")]; rows = []
    for l in lines[i0 + 1:]:
        p = l.split(",")
        if len(p) < 2 or not p[0].strip().isdigit(): break
        rows.append(p)
    d = pd.DataFrame(rows, columns=["date"] + hdr[1:]); d["date"] = pd.to_datetime(d["date"].str.strip(), format="%Y%m%d")
    d = d.set_index("date").apply(pd.to_numeric, errors="coerce").replace([-99.99, -999], np.nan) / 100
    return d

def build():
    P = {}
    cr = _crypto()
    P["crypto_h"] = cr                                                     # hourly OHLCV + taker-buy volume
    P["crypto"] = pd.DataFrame({k: v.c.resample("1D").last() for k, v in cr.items()})
    P["crypto_v"] = pd.DataFrame({k: (v.c * v.v).resample("1D").sum() for k, v in cr.items()})
    P["crypto_tb"] = pd.DataFrame({k: (v.tbv / v.v.replace(0, np.nan)).resample("1D").mean() for k, v in cr.items()})
    cf = _cfd(); P["cfd_h"] = cf
    P["cfd"] = pd.DataFrame({k: v.c.resample("1D").last() for k, v in cf.items()}).dropna(how="all")
    # FX: value of 1 unit of foreign currency in USD
    fx = {}
    for s, inv in [("DEXUSEU", 0), ("DEXUSUK", 0), ("DEXUSAL", 0), ("DEXUSNZ", 0), ("DEXJPUS", 1), ("DEXCAUS", 1), ("DEXSZUS", 1), ("DEXSDUS", 1), ("DEXNOUS", 1),
                   ("DEXMXUS", 1), ("DEXBZUS", 1), ("DEXKOUS", 1), ("DEXINUS", 1), ("DEXSFUS", 1)]:
        x = _fred(s); fx[s[3:5] if inv else s[5:]] = 1 / x if inv else x
    P["fx"] = pd.DataFrame(fx)
    P["bonds_ret"] = pd.DataFrame({f"UST{n}Y": _par_bond_ret(_fred(s), n) for s, n in [("DGS2", 2), ("DGS5", 5), ("DGS10", 10), ("DGS30", 30)]})
    P["yields"] = pd.DataFrame({s: _fred(s) for s in ["DGS3MO", "DGS2", "DGS5", "DGS10", "DGS30", "DFF"]})
    P["macro"] = {s: _fred(s) for s in ["VIXCLS", "T10Y2Y", "T10Y3M", "NFCI", "ICSA", "T10YIE", "DCOILWTICO", "DCOILBRENTEU", "DHHNGSP", "NASDAQCOM"]}
    P["ind49"] = _french("49_Industry_Portfolios_Daily.csv"); P["ind10"] = _french("10_Industry_Portfolios_Daily.csv")
    P["mom10"] = _french("10_Portfolios_Prior_12_2_Daily.csv")
    f5 = _french("F-F_Research_Data_5_Factors_2x3_daily.csv", block="Mkt-RF"); P["ff5"] = f5
    fund = {}
    for f in sorted(glob.glob(f"{SCR}/kf/*-fundingRate-*.csv")):
        s = os.path.basename(f).split("-")[0]
        d = pd.read_csv(f); d.index = pd.to_datetime(d.calc_time, unit="ms", utc=True)
        fund.setdefault(s, []).append(d.last_funding_rate)
    P["funding"] = pd.DataFrame({k: pd.concat(v).sort_index().resample("1D").sum() for k, v in fund.items()})
    return P

def load():
    p = f"{RDATA}/panels.pkl"
    if os.path.exists(p): return pickle.load(open(p, "rb"))
    P = build(); pickle.dump(P, open(p, "wb")); return P

if __name__ == "__main__":
    P = load()
    for k, v in P.items():
        if isinstance(v, pd.DataFrame): print(k, v.shape, v.index.min(), v.index.max())
        else: print(k, list(v)[:15])
