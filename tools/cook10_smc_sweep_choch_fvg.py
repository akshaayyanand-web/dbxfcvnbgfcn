# ICT / SMC model: HTF liquidity sweep -> 5m CHoCH -> 5m FVG limit entry. Pre-registered rules (see message). 20 symbols, 4 sweep TFs, 2R/3R, all hours vs killzones.
import glob, io, zipfile, sys, numpy as np, pandas as pd
from multiprocessing import Pool
def m1_csv(path):
    d = pd.read_csv(path, index_col=0); d.index = pd.to_datetime(d.index, utc=True); d = d[~d.index.duplicated()].sort_index().iloc[:, :4]; d.columns = list("ohlc"); return d
def hd(pair):
    parts = []
    for f in sorted(glob.glob(f"hd/raw/{pair}_*.zip")):
        try: z = zipfile.ZipFile(f)
        except zipfile.BadZipFile: continue
        nm = [n for n in z.namelist() if n.lower().endswith(".csv")]
        if nm: parts.append(pd.read_csv(io.BytesIO(z.read(nm[0])), sep=";", header=None, names=["t", "o", "h", "l", "c", "v"]))
    d = pd.concat(parts); d.index = pd.DatetimeIndex(pd.to_datetime(d.t, format="%Y%m%d %H%M%S")).tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT").tz_convert("UTC"); d = d[d.index.notna()]
    return d[["o", "h", "l", "c"]].astype(float).loc[lambda x: ~x.index.duplicated()].sort_index()
def crypto(sym):
    p = []
    for f in sorted(glob.glob(f"k5full/{sym}USDT-5m-*.csv")):
        x = pd.read_csv(f, header=None, usecols=[0, 1, 2, 3, 4], names=["t", "o", "h", "l", "c"]); x["t"] = np.where(x.t > 1e14, x.t // 1000, x.t); p.append(x)
    x = pd.concat(p); x.index = pd.to_datetime(x.t, unit="ms", utc=True); return x[["o", "h", "l", "c"]].astype(float).sort_index().loc[lambda z: ~z.index.duplicated()]
def jpn():
    parts = [pd.read_csv(io.StringIO(open(f).read().strip()), header=None, names=["t", "o", "h", "l", "c", "v"]) for f in sorted(glob.glob("world1m/JPNIDXJPY/*.csv")) if open(f).read().strip()]
    x = pd.concat(parts); x.index = pd.to_datetime(x.t, unit="s", utc=True); return x[~x.index.duplicated()].sort_index()[["o", "h", "l", "c"]]
SRC = {"NQ": (lambda: m1_csv("fut1m/USATECHIDXUSD_1m.csv"), 0.00015, "index"), "SPX": (lambda: m1_csv("fut1m/USA500IDXUSD_1m.csv"), 0.00015, "index"),
       "DAX": (lambda: m1_csv("eu1m/DEUIDXEUR_1m.csv"), 0.00015, "index"), "JPN225": (jpn, 0.0002, "index"), "XAU": (lambda: m1_csv("fut1m/XAUUSD_1m.csv"), 0.00012, "gold"),
       "EURUSD": (lambda: m1_csv("fx1m/EURUSD_1m.csv"), 0.00008, "fx"), "AUDCAD": (lambda: m1_csv("fx1m/AUDCAD_1m.csv"), 0.00018, "fx"),
       "USDJPY": (lambda: hd("USDJPY"), 0.00007, "fx"), "GBPUSD": (lambda: hd("GBPUSD"), 0.00009, "fx"), "AUDUSD": (lambda: hd("AUDUSD"), 0.0001, "fx"),
       "USDCAD": (lambda: hd("USDCAD"), 0.0001, "fx"), "USDCHF": (lambda: hd("USDCHF"), 0.00012, "fx"), "NZDUSD": (lambda: hd("NZDUSD"), 0.00014, "fx"),
       "EURJPY": (lambda: hd("EURJPY"), 0.0001, "fx"), "GBPJPY": (lambda: hd("GBPJPY"), 0.00015, "fx"),
       "BTC": (lambda: crypto("BTC"), 0.0006, "crypto"), "ETH": (lambda: crypto("ETH"), 0.001, "crypto"), "SOL": (lambda: crypto("SOL"), 0.0015, "crypto"), "XRP": (lambda: crypto("XRP"), 0.002, "crypto")}
def rs(d, rule): return d.resample(rule).agg({"o": "first", "h": "max", "l": "min", "c": "last"}).dropna()
def swings(H, L):
    """Fractal swings (2 bars each side). Returns arrays of the latest CONFIRMED swing high/low level known at each bar (confirmation = 2 bars later)."""
    n = len(H); sh = np.full(n, np.nan); sl = np.full(n, np.nan); last_h = last_l = np.nan
    for j in range(4, n):
        k = j - 2
        if H[k] > H[k - 1] and H[k] > H[k - 2] and H[k] > H[k + 1] and H[k] > H[k + 2]: last_h = H[k]
        if L[k] < L[k - 1] and L[k] < L[k - 2] and L[k] < L[k + 1] and L[k] < L[k + 2]: last_l = L[k]
        sh[j] = last_h; sl[j] = last_l
    return sh, sl
def run_symbol(name):
    loader, cost, cls = SRC[name]
    try: raw = loader()
    except Exception as ex: return name, [], str(ex)
    b5 = rs(raw, "5min") if (raw.index[1] - raw.index[0]) < pd.Timedelta("5min") else raw
    O, H, L, C = (b5[k].to_numpy(float) for k in "ohlc"); T = b5.index; n = len(C)
    s5h, s5l = swings(H, L); out = []
    for tf in ("5min", "15min", "1h", "4h"):
        hb = b5 if tf == "5min" else rs(b5, tf); hH, hL, hC = hb.h.to_numpy(), hb.l.to_numpy(), hb.c.to_numpy(); sh, sl = swings(hH, hL)
        close_t = hb.index + pd.Timedelta(tf)
        for k in range(5, len(hb)):
            for side in (-1, 1):            # -1: swept a HIGH -> look for shorts; +1: swept a LOW -> longs
                lvl = sh[k - 1] if side < 0 else sl[k - 1]
                if not np.isfinite(lvl): continue
                if side < 0 and not (hH[k] > lvl and hC[k] < lvl): continue
                if side > 0 and not (hL[k] < lvl and hC[k] > lvl): continue
                i0 = T.searchsorted(close_t[k])                       # first 5m bar after the sweep candle closed
                if i0 + 80 >= n: continue
                ext = hH[k] if side < 0 else hL[k]
                ny_h = close_t[k].tz_convert("America/New_York").hour; kz = (2 <= ny_h < 5) or (7 <= ny_h < 10)
                # 5m CHoCH within 36 bars: close beyond the latest 5m swing (low for shorts / high for longs)
                ch = None
                for q in range(i0, i0 + 36):
                    if (side < 0 and H[q] > ext) or (side > 0 and L[q] < ext): break     # sweep extreme taken out first -> invalid
                    ref = s5l[q] if side < 0 else s5h[q]
                    if np.isfinite(ref) and ((side < 0 and C[q] < ref) or (side > 0 and C[q] > ref)): ch = q; break
                if ch is None: continue
                # last FVG in the leg (from 6 bars before i0 to the CHoCH bar)
                fvg = None
                for q in range(ch, max(i0 - 6, 2), -1):
                    if side < 0 and L[q - 2] > H[q]: fvg = H[q]; break        # bearish gap: entry at its near (lower) edge
                    if side > 0 and H[q - 2] < L[q]: fvg = L[q]; break        # bullish gap: entry at its near (upper) edge
                if fvg is None: continue
                e = fvg; stp = ext * (1 + 0.0001) if side < 0 else ext * (1 - 0.0001); risk = abs(stp - e)
                if risk < 3 * cost * e or (side < 0 and e >= stp) or (side > 0 and e <= stp): continue
                fill = None
                for q in range(ch + 1, min(ch + 25, n)):
                    if (side < 0 and H[q] >= e) or (side > 0 and L[q] <= e): fill = q; break
                if fill is None: continue
                for tgt in (2.0, 3.0):
                    tp = e + side * -1 * 0 if False else (e - tgt * risk if side < 0 else e + tgt * risk); res = None
                    for q in range(fill, min(fill + 48, n)):
                        if (side < 0 and H[q] >= stp) or (side > 0 and L[q] <= stp): res = -1.0; break
                        if q > fill and ((side < 0 and L[q] <= tp) or (side > 0 and H[q] >= tp)): res = tgt; break
                    if res is None:
                        q = min(fill + 48, n - 1); res = (C[q] - e) / risk * (1 if side > 0 else -1)
                    out.append((name, cls, tf, tgt, kz, T[fill], res - cost * e / risk))
    return name, out, None
if __name__ == "__main__":
    with Pool(4) as p: res = p.map(run_symbol, list(SRC))
    rows = []
    for name, out, err in res:
        if err: print("SKIP", name, err)
        rows += out
    D = pd.DataFrame(rows, columns=["sym", "cls", "tf", "tgt", "kz", "t", "R"]); D.to_pickle("smc_trades.pkl")
    S = pd.Timestamp("2023-01-01", tz="UTC")
    def summ(g):
        a, b = g[g.t < S].R, g[g.t >= S].R; tt = lambda v: round(v.mean() / v.std(ddof=1) * np.sqrt(len(v)), 2) if len(v) > 2 else np.nan
        return pd.Series(dict(trades=len(g), win=round(100 * (g.R > 0).mean()), avgR=round(g.R.mean(), 3), t_pre2023=tt(a), t_2023on=tt(b)))
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 400)
    print("POOLED ALL SYMBOLS (the actual test):"); print(D.groupby(["tf", "tgt", "kz"]).apply(summ).to_string())
    print("\nBY ASSET CLASS (all hours, 2R):"); print(D[(D.tgt == 2.0)].groupby(["cls", "tf"]).apply(summ).to_string())
    print("\nBY SYMBOL (1h sweeps, 2R, all hours):"); print(D[(D.tgt == 2.0) & (D.tf == "1h")].groupby("sym").apply(summ).to_string())
