# Round 5 (pre-registered). W: FX weekend-gap fade on 9 pairs (entry 30 min after the Sunday open; 60 min as robustness).
# F: crypto funding-crowding contrarian on 13 coins (z of 3-day funding vs 90 days > 2 -> fade, hold 72h).
import glob, pickle, numpy as np, pandas as pd
exec(open("newlab.py").read().split('\nif __name__ == "__main__":')[0])
trade_idx = trade
src = open("fxbook.py").read().split('\nif __name__ == "__main__":')[0]; exec(src)
CCOST = {"ETH": 0.001, "BNB": 0.002, "XRP": 0.002, "ADA": 0.0025, "DOGE": 0.0025, "LTC": 0.002, "LINK": 0.0025, "AVAX": 0.0025, "DOT": 0.0025, "BCH": 0.0025, "TRX": 0.003, "SOL": 0.0015, "BTC": 0.0006}
def funding(sym):
    parts = []
    for f in sorted(glob.glob(f"kf/{sym}USDT-fundingRate-*.csv")):
        d = pd.read_csv(f)
        if "last_funding_rate" in d: parts.append(d[["calc_time", "last_funding_rate"]])
    d = pd.concat(parts); t = d.calc_time.astype("int64"); d.index = pd.to_datetime(np.where(t > 1e14, t // 1000, t), unit="ms", utc=True)
    return d.last_funding_rate.astype(float).sort_index().resample("1D").mean()
def h_funding(sym, z=2.0, hold=72):
    m = Mkt(sym, load_crypto(sym), CCOST[sym]); fr = funding(sym)
    f3 = fr.rolling(3).mean(); zz = ((f3 - fr.rolling(90, min_periods=60).mean()) / fr.rolling(90, min_periods=60).std()).shift(1).dropna()
    out, busy = [], None
    for day, v in zz.items():
        if abs(v) <= z or (busy is not None and day < busy): continue
        i = m.t.searchsorted(day + pd.Timedelta(hours=1))
        if i + hold >= len(m.t): continue
        tr = trade_idx(m, i, i + hold, -int(np.sign(v)))
        if tr: out.append(tr[:3]); busy = tr[1]
    return out
def h_fx_gap(pair, delay_min, thr=0.3):
    m = FX(pair); d = pd.DataFrame({"o": m.o, "h": m.h, "l": m.l, "c": m.c}, index=m.t)
    daily = d.resample("1D").agg({"h": "max", "l": "min"}).dropna(); atr = (daily.h - daily.l).rolling(14).mean().shift(1)
    gaps = np.flatnonzero(pd.Series(m.t).diff().dt.total_seconds().to_numpy()[1:] > 30 * 3600) + 1        # first bar after a >30h pause = weekend reopen
    out = []
    for g in gaps:
        fri_close, sun_open, t0 = m.c[g - 1], m.o[g], m.t[g]
        a = atr.asof(t0.normalize())
        if not np.isfinite(a) or abs(sun_open - fri_close) < thr * a: continue
        d_ = -int(np.sign(sun_open - fri_close)); i = m.at(t0 + pd.Timedelta(minutes=delay_min))
        if i is None: continue
        e = m.o[i]
        if (fri_close - e) * d_ <= 0: continue                                 # already filled before entry
        st = e - d_ * abs(sun_open - fri_close); tgt = fri_close
        tout = pd.Timestamp(f"{(t0 + pd.Timedelta(days=1)).date()} 08:00", tz="Europe/London").tz_convert("UTC"); j = m.at(tout, "30min")
        if j is None or j <= i: continue
        x = None
        for q in range(i, j):
            if (d_ > 0 and m.l[q] <= st) or (d_ < 0 and m.h[q] >= st): x = st; break
            if (d_ > 0 and m.h[q] >= tgt) or (d_ < 0 and m.l[q] <= tgt): x = tgt; break
        x = m.o[j] if x is None else x; risk = abs(e - st)
        out.append((m.t[i], m.t[min(q, j)], d_ * (x - e) / risk - m.cost * e / risk))
    return out
if __name__ == "__main__":
    rows = []; TR = {}; S = pd.Timestamp("2023-01-01", tz="UTC")
    for delay in (30, 60):
        allt = []
        for p in PAIRS:
            t = h_fx_gap(p, delay); TR[("W", p, delay)] = t; allt += t
        rows.append(dict(test=f"W FX weekend-gap fade, entry +{delay} min, 9 pairs pooled", **stats(sorted(allt, key=lambda x: x[0]), S))); print(rows[-1], flush=True)
    allt = []
    for c in CCOST:
        t = h_funding(c); TR[("F", c)] = t; allt += t
        rows.append(dict(test=f"F funding crowding {c}", **stats(t, S)))
    rows.append(dict(test="F funding crowding, 13 coins POOLED", **stats(sorted(allt, key=lambda x: x[0]), S))); print(rows[-1], flush=True)
    R = pd.DataFrame(rows); pd.set_option("display.width", 250); print(R.to_string()); R.to_csv("lab5_results.csv", index=False); pickle.dump(TR, open("lab5_trades.pkl", "wb"))
