# Binance USD-M futures positioning data (5-min, from data.binance.vision "metrics"): open interest, top-trader and all-account long/short ratios, taker ratio.
# Never used before in this research. Price = the pack's BTC/ETH data; signals at each 1h close, entry next open, hold 24h (M3 also 72h), stop 2 x ATR14(1h), one at a time.
# Rules fixed before running (z-scores vs the previous 7 days of hourly values unless noted):
#  P1 retail crowding fade : z(log all-account L/S) > 2 -> short, < -2 -> long
#  P2 smart vs retail      : z(log top-trader position L/S) - z(log all-account L/S) > 2.5 -> long, < -2.5 -> short
#  P3 OI flush             : 24h OI change z (vs 30 days) < -2.5 and price down over 24h -> long  (hold 24h and 72h)
#  P4 new money trend      : 24h OI change z > 2 -> trade in the direction of the 24h price move
#  P5 move without money   : |24h price move| z > 2 and 24h OI change z < -1 -> fade the move (short covering / long liquidation)
#  P6 taker extreme        : z(24h mean taker buy/sell ratio) > 2 -> follow (P6f) / fade (P6r)
# Costs BTC 0.09%, ETH 0.227% round trip + 15%/yr swap. Train < 2023, holdout 2023+. Random-direction baseline (40 runs), double costs, one-bar delay.
import glob, zipfile, io, numpy as np, pandas as pd
exec(open("transfer.py").read().split("JOBS = ")[0])
COST.update(BTC=.0009, ETH=.00227)
def metrics(sym):
    parts = []
    for f in sorted(glob.glob(f"metrics_raw/{sym}USDT-metrics-*.zip")):
        try:
            with zipfile.ZipFile(f) as z: parts.append(pd.read_csv(z.open(z.namelist()[0])))
        except Exception: pass
    d = pd.concat(parts); d["t"] = pd.to_datetime(d.create_time, utc=True); d = d.drop_duplicates("t").set_index("t").sort_index()
    cols = ["sum_open_interest", "count_toptrader_long_short_ratio", "sum_toptrader_long_short_ratio", "count_long_short_ratio", "sum_taker_long_short_vol_ratio"]
    d = d[cols].apply(pd.to_numeric, errors="coerce"); d = d.where(d > 0)
    h = d.resample("1h", label="right", closed="right").last()                     # value known at the END of each hour
    h["taker"] = d.sum_taker_long_short_vol_ratio.resample("1h", label="right", closed="right").mean(); return h
def z(x, n): return (x - x.rolling(n, min_periods=n // 2).mean()) / x.rolling(n, min_periods=n // 2).std()
def signals(sym):
    b = K.rs(m5(sym), "1h").dropna(); M = metrics(sym)
    M.index = M.index - pd.Timedelta(hours=1)                                       # align: metrics at the end of bar t -> row of bar t (bar labelled by its start)
    M = M.reindex(b.index); px = np.log(b.c)
    oi = np.log(M.sum_open_interest); doi = oi - oi.shift(24); zdoi = z(doi, 720); r24 = px - px.shift(24); zr = z(r24, 720)
    zr_ret = z(np.log(M.count_long_short_ratio), 168); ztop = z(np.log(M.sum_toptrader_long_short_ratio), 168); ztk = z(np.log(M.taker).rolling(24).mean(), 168)
    S = {}
    S["P1 retail crowding fade"] = np.where(zr_ret > 2, -1, np.where(zr_ret < -2, 1, 0))
    dz = ztop - zr_ret; S["P2 smart vs retail"] = np.where(dz > 2.5, 1, np.where(dz < -2.5, -1, 0))
    S["P3 OI flush (24h)"] = np.where((zdoi < -2.5) & (r24 < 0), 1, 0); S["P3 OI flush (72h)"] = S["P3 OI flush (24h)"]
    S["P4 new money trend"] = np.where(zdoi > 2, np.sign(r24), 0)
    S["P5 move without money (fade)"] = np.where((zr.abs() > 2) & (zdoi < -1), -np.sign(r24), 0)
    S["P6f taker extreme follow"] = np.where(ztk > 2, 1, np.where(ztk < -2, -1, 0)); S["P6r taker extreme fade"] = -S["P6f taker extreme follow"]
    return b, {k: np.nan_to_num(v).astype(int) for k, v in S.items()}, M.sum_open_interest.notna().to_numpy()
def trades(b, sig, sym, hold=24, cm=1.0, delay=0, rand=None):
    O, H, L, C = (b[c].to_numpy() for c in "ohlc"); T = b.index; A = atr(b); out = []; busy = -1
    for k in np.where(sig != 0)[0]:
        if k <= busy or k + 2 + delay + hold >= len(C) or not np.isfinite(A[k]): continue
        d = sig[k] if rand is None else (1 if rand.random() < .5 else -1)
        e = O[k + 1 + delay]; stop = e - d * 2 * A[k]; x, q = walk(O, H, L, C, k + 1 + delay, k + 1 + delay + hold, d, e, stop, None)
        out.append((T[k], (d * (x - e) - cm * COST[sym] * e - SWAP[sym] / 365 * (q - k) / 24 * e) / (2 * A[k]))); busy = q
    return out
if __name__ == "__main__":
    rows = []; SP = pd.Timestamp("2023-01-01", tz="UTC"); tt = lambda v: round(v.mean() / v.std(ddof=1) * np.sqrt(len(v)), 2) if len(v) > 2 else np.nan
    for sym in ("BTC", "ETH"):
        b, S, have = signals(sym); print(sym, "metrics coverage", round(100 * have.mean()), "% of hours, from", b.index[have.argmax()].date(), flush=True)
        for name, sig in S.items():
            hold = 72 if "72h" in name else 24; D = pd.DataFrame(trades(b, sig, sym, hold), columns=["t", "R"])
            if len(D) < 30: rows.append(dict(market=sym, rule=name, trades=len(D))); continue
            A_, B_ = D[D.t < SP].R, D[D.t >= SP].R; y = D.groupby(D.t.dt.year).R.sum()
            rnd = [np.mean([x[1] for x in trades(b, sig, sym, hold, rand=np.random.default_rng(s))]) for s in range(40)]
            r = dict(market=sym, rule=name, trades=len(D), win=round(100 * (D.R > 0).mean()), avgR=round(D.R.mean(), 3), t_train=tt(A_), n_train=len(A_), avgR_hold=round(B_.mean(), 3), t_hold=tt(B_),
                     random=round(np.mean(rnd), 3), beats_random=round(100 * np.mean(np.array(rnd) < D.R.mean())), dbl_cost=round(np.mean([x[1] for x in trades(b, sig, sym, hold, cm=2)]), 3),
                     late_1h=round(np.mean([x[1] for x in trades(b, sig, sym, hold, delay=1)]), 3), pos_years=f"{(y > 0).sum()}/{len(y)}")
            rows.append(r); print(r, flush=True); D.to_pickle(f"pos_{sym}_{name.split()[0]}_{hold}.pkl")
    R = pd.DataFrame(rows); pd.set_option("display.width", 260); print(R.to_string(index=False)); R.to_csv("positioning.csv", index=False)
    R["ok"] = (R.t_train >= 2) & (R.t_hold >= 1.5) & (R.beats_random >= 95) & (R.dbl_cost > 0); print("\nSURVIVORS:\n", R[R.ok].to_string(index=False) if R.ok.any() else "none")
