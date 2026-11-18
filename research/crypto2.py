"""Crypto derivatives panels (daily, UTC 00:00 closes): USD-M perpetual closes, premium index (perp vs index basis), funding (daily sum),
5-minute OI/taker metrics aggregated daily, COIN-M quarterly futures basis, Deribit DVOL, stablecoin supply, BTC miner data."""
import os, glob, json, zipfile, io, pickle, numpy as np, pandas as pd
from data import SCR, RDATA
C = f"{SCR}/cdata"
def _zips(pattern, cols=None):
    out = []
    for f in sorted(glob.glob(pattern)):
        try:
            with zipfile.ZipFile(f) as z: raw = z.read(z.namelist()[0]).decode()
        except Exception: continue
        d = pd.read_csv(io.StringIO(raw), header=None if not raw[:1].isalpha() else 0)
        if cols is None and not raw[:1].isalpha() is False: pass
        out.append(d)
    return out
def _kl(frames):
    frames = [f.set_axis(range(f.shape[1]), axis=1) for f in frames]
    d = pd.concat(frames); d = d.iloc[:, :6]; d.columns = ["t", "o", "h", "l", "c", "v"]
    t = pd.to_numeric(d.t, errors="coerce"); d = d[t.notna()]; t = t[t.notna()].astype("int64"); t = np.where(t > 1e14, t // 1000, t)
    d.index = pd.to_datetime(t, unit="ms", utc=True).normalize(); d = d[~d.index.duplicated()].sort_index()
    return d[["o", "h", "l", "c", "v"]].astype(float)
def build():
    P = {}; syms = sorted({os.path.basename(f).split("-")[0] for f in glob.glob(f"{C}/um/*.zip")})
    P["perp"] = pd.DataFrame({s[:-4]: _kl(_zips(f"{C}/um/{s}-1d-*.zip")).c for s in syms})
    P["prem"] = pd.DataFrame({s[:-4]: _kl(_zips(f"{C}/prem/{s}-1d-*.zip")).c for s in syms})      # premium index close (perp/index - 1)
    met = {}
    for s in ["BTC", "ETH", "SOL", "XRP", "DOGE"]:
        fr = _zips(f"{C}/met/{s}USDT-metrics-*.zip")
        if not fr: continue
        d = pd.concat(fr); d["create_time"] = pd.to_datetime(d["create_time"]); d = d.set_index("create_time").sort_index()
        g = d.resample("1D")
        met[s] = pd.DataFrame({"oi": g["sum_open_interest_value"].last(), "toptrader_ls": g["sum_toptrader_long_short_ratio"].mean(),
                               "count_ls": g["count_long_short_ratio"].mean(), "taker_ls": g["sum_taker_long_short_vol_ratio"].mean()})
        met[s].index = met[s].index.tz_localize("UTC")
    P["metrics"] = met
    cm = {}
    for s in ["BTC", "ETH"]:
        rows = []
        for f in sorted(glob.glob(f"{C}/cm/{s}USD_*-1d-*.zip")):
            exp = pd.Timestamp("20" + os.path.basename(f).split("_")[1][:6], tz="UTC") + pd.Timedelta(hours=8)
            fr = _zips(f)
            if not fr: continue
            k = _kl(fr); k["exp"] = exp; k["ret"] = k.c.pct_change(); rows.append(k)
        if rows:
            d = pd.concat(rows).reset_index().rename(columns={"index": "date"})
            d["dte"] = (d.exp - d.date).dt.total_seconds() / 86400
            d = d[d.dte > 7].sort_values(["date", "dte"]).groupby("date").first()    # nearest quarterly with > 7 days left
            cm[s] = d[["c", "dte", "exp", "ret"]]
    P["cm"] = cm
    from engine import P as EP
    P["fund"] = EP["funding"].copy()
    dv = {}
    for c in ["BTC", "ETH"]:
        pts = []
        for f in glob.glob(f"{C}/misc/dvol_{c}_*.json"): pts += json.load(open(f))["result"]["data"]
        s = pd.DataFrame(pts, columns=["t", "o", "h", "l", "c"]).drop_duplicates("t"); s.index = pd.to_datetime(s.t, unit="ms", utc=True); dv[c] = s.c.sort_index()
    P["dvol"] = pd.DataFrame(dv)
    st = json.load(open(f"{C}/misc/stablecoins.json")); s = pd.Series({pd.Timestamp(int(x["date"]), unit="s", tz="UTC"): x["totalCirculatingUSD"].get("peggedUSD", np.nan) for x in st})
    P["stable"] = s.sort_index()
    mi = {}
    for ch in ["hash-rate", "miners-revenue", "difficulty", "n-transactions"]:
        v = json.load(open(f"{C}/misc/{ch}.json"))["values"]; mi[ch] = pd.Series({pd.Timestamp(x["x"], unit="s", tz="UTC").normalize(): x["y"] for x in v})
    P["miners"] = pd.DataFrame(mi).sort_index()
    return P
def load():
    p = f"{RDATA}/crypto2.pkl"
    if os.path.exists(p): return pickle.load(open(p, "rb"))
    P = build(); pickle.dump(P, open(p, "wb")); return P
if __name__ == "__main__":
    P = load()
    for k, v in P.items():
        if isinstance(v, dict): print(k, {a: (b.shape, str(b.index.min())[:10], str(b.index.max())[:10]) for a, b in v.items()})
        else: print(k, v.shape, str(v.index.min())[:10], str(v.index.max())[:10])
