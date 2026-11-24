# Round 11, pre-registered (rules fixed before running). Costs per symbol round trip; R = move / initial risk minus cost.
#  T1 trend-day continuation (daily, UTC days): range >= 1.5 ATR14 and close in top/bottom 10% -> next day open in that direction,
#     stop = trend day's midpoint, exit next day's close.
#  T2 round-number stop run (5m): bar pierces the nearest round level by < 0.1% and closes back -> fade at that close, stop just past the bar
#     extreme, target 2R, flat at day end. Steps: NQ 250, SPX 50, DAX 250, XAU 25, BTC 1000, ETH 100.
#  T3 weekend gap fill (1h, indices/metals/oil): entry at the close of the first hour after the weekend reopen if > 0.25% of the gap remains;
#     target Friday's close, stop = same distance beyond, max 24h. Cost x1.5 (wider weekend spreads).
#  T4 jobless claims (1m, Thursday 08:30 New York): follow the 08:30-08:35 move from 08:35, stop at the 08:30 price, exit 09:25.
import numpy as np, pandas as pd
from multiprocessing import Pool
exec(open("smc.py").read().split("def run_symbol(")[0])
def atr(h, l, c, n=14):
    pc = np.r_[c[0], c[:-1]]; tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc))); return pd.Series(tr).rolling(n).mean().shift(1).to_numpy()
def duka(sym): d = pd.read_csv(f"fut/{sym}.csv", index_col=0); d.index = pd.to_datetime(d.index, utc=True); return d[["o", "h", "l", "c"]]
SYMS = {"NQ": (SRC["NQ"][0], 0.00015, 250), "SPX": (SRC["SPX"][0], 0.00015, 50), "DAX": (SRC["DAX"][0], 0.00015, 250), "XAU": (SRC["XAU"][0], 0.00012, 25),
        "BTC": (SRC["BTC"][0], 0.0006, 1000), "ETH": (SRC["ETH"][0], 0.001, 100), "XAG": (lambda: duka("XAGUSD"), 0.0008, None), "WTI": (lambda: duka("LIGHTCMDUSD"), 0.0003, None),
        "DOW": (lambda: duka("USA30IDXUSD"), 0.00015, None)}
def run(sym):
    loader, cost, step = SYMS[sym]; raw = loader(); out = []
    b = rs(raw, "5min") if (raw.index[1] - raw.index[0]) < pd.Timedelta("5min") else raw
    ONLY = __import__('os').environ.get('ONLY', '')
    # T1
    d = rs(b, "1D"); O, H, L, C = (d[c].to_numpy() for c in "ohlc"); A = atr(H, L, C)
    for k in (range(15, len(d) - 1) if not ONLY else []):
        rg = H[k] - L[k]
        if not np.isfinite(A[k]) or rg < 1.5 * A[k]: continue
        pos = (C[k] - L[k]) / rg; dn = 1 if pos >= 0.9 else (-1 if pos <= 0.1 else 0)
        if not dn: continue
        e = O[k + 1]; stop = (H[k] + L[k]) / 2; risk = dn * (e - stop)
        if risk <= 3 * cost * e: continue
        x = stop if (dn > 0 and L[k + 1] <= stop) or (dn < 0 and H[k + 1] >= stop) else C[k + 1]
        out.append((sym, "T1 trend-day continuation", d.index[k + 1], (dn * (x - e) - cost * e) / risk))
    # T2 (5m symbols with a step)
    if not ONLY and step and (b.index[1] - b.index[0]) <= pd.Timedelta("5min"):
        O5, H5, L5, C5, T5 = b.o.to_numpy(), b.h.to_numpy(), b.l.to_numpy(), b.c.to_numpy(), b.index; dayn = (T5.normalize().asi8 // 86_400_000_000_000)
        q = 1; n = len(C5)
        while q < n - 1:
            up = np.ceil(C5[q - 1] / step) * step; dnl = np.floor(C5[q - 1] / step) * step; sig = None
            if H5[q] > up and C5[q] < up and (H5[q] - up) / up < 0.001: sig = (-1, H5[q] * 1.0001)
            elif L5[q] < dnl and C5[q] > dnl and (dnl - L5[q]) / dnl < 0.001: sig = (1, L5[q] * 0.9999)
            if not sig: q += 1; continue
            dn, stop = sig; e = C5[q]; risk = dn * (e - stop)
            if risk <= 3 * cost * e: q += 1; continue
            tp = e + dn * 2 * risk; x = None; j = q + 1
            while j < n and dayn[j] == dayn[q]:
                if (dn > 0 and L5[j] <= stop) or (dn < 0 and H5[j] >= stop): x = stop; break
                if (dn > 0 and H5[j] >= tp) or (dn < 0 and L5[j] <= tp): x = tp; break
                j += 1
            if x is None: j = min(j, n) - 1; x = C5[j]
            out.append((sym, "T2 round-number stop run", T5[q], (dn * (x - e) - cost * e) / risk)); q = j + 1
    # T3 weekend gap (not crypto)
    if sym not in ("BTC", "ETH"):
        h = rs(b, "1h") if (b.index[1] - b.index[0]) < pd.Timedelta("1h") else b
        T = h.index; Oh, Hh, Lh, Ch = (h[c].to_numpy() for c in "ohlc"); gaps = np.where(pd.Series(T).diff().dt.total_seconds().to_numpy()[1:] > 40 * 3600)[0]
        for g in gaps:
            f = g + 1; cfri = Ch[g]; e = Ch[f]; rem = np.log(e / cfri)
            if abs(rem) < 0.0025 or f + 25 >= len(Ch): continue
            dn = -np.sign(rem); risk = abs(e - cfri); stop = e - dn * risk; x = Ch[min(f + 24, len(Ch) - 1)]
            for j in range(f + 1, min(f + 25, len(Ch))):
                if (dn > 0 and Lh[j] <= stop) or (dn < 0 and Hh[j] >= stop): x = stop; break
                if (dn > 0 and Hh[j] >= cfri) or (dn < 0 and Lh[j] <= cfri): x = cfri; break
            out.append((sym, "T3 weekend gap fill", T[f], (dn * (x - e) - 1.5 * cost * e) / risk))
    # T4 claims (1m data)
    if not ONLY and sym in ("NQ", "SPX", "XAU") and (raw.index[1] - raw.index[0]) <= pd.Timedelta("1min"):
        m = raw.copy(); m.index = m.index.tz_convert("America/New_York"); m = m[(m.index.dayofweek == 3) & (m.index.hour >= 8) & (m.index.hour < 10)]
        for dte, x in m.groupby(m.index.date):
            t = x.index.hour * 60 + x.index.minute; c_ = x.c.to_numpy(); h_ = x.h.to_numpy(); l_ = x.l.to_numpy()
            k0, k5, kx = (np.searchsorted(t, v) for v in (509, 515, 565))         # 08:29 close = pre-release price, 08:35, 09:25
            if max(k0, k5, kx) >= len(t) or t[k0] != 509 or t[k5] != 515 or t[kx] != 565: continue
            p0, e = c_[k0], c_[k5]; mv = e - p0
            if abs(mv) <= 3 * cost * e: continue
            dn = np.sign(mv); stop = p0; risk = abs(mv); xx = c_[kx]
            for j in range(k5 + 1, kx + 1):
                if (dn > 0 and l_[j] <= stop) or (dn < 0 and h_[j] >= stop): xx = stop; break
            out.append((sym, "T4 jobless-claims momentum", pd.Timestamp(dte, tz="UTC"), (dn * (xx - e) - cost * e) / risk))
    print(sym, len(out), flush=True); return out
if __name__ == "__main__":
    with Pool(4) as p: res = p.map(run, list(SYMS))
    D = pd.DataFrame([r for o in res for r in o], columns=["sym", "test", "t", "R"]); D.to_pickle("round11_trades.pkl"); S = pd.Timestamp("2023-01-01", tz="UTC")
    def summ(g):
        a, b_ = g[g.t < S].R, g[g.t >= S].R; tt = lambda v: round(v.mean() / v.std(ddof=1) * np.sqrt(len(v)), 2) if len(v) > 2 else np.nan
        yrs = g.groupby(g.t.dt.year).R.sum()
        return pd.Series(dict(trades=len(g), win=round(100 * (g.R > 0).mean()), avgR=round(g.R.mean(), 3), t_pre2023=tt(a), t_2023on=tt(b_), pos_years=f"{(yrs > 0).sum()}/{len(yrs)}"))
    pd.set_option("display.width", 200); pd.set_option("display.max_rows", 200)
    print("\nPOOLED:"); print(D.groupby("test").apply(summ).to_string()); print("\nBY SYMBOL:"); print(D.groupby(["test", "sym"]).apply(summ).to_string())
