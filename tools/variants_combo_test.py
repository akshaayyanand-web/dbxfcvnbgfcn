# Run from the scratchpad.
# Re-test previously rejected add-ons with the new drawdown brake (room cap 7, half size below -4% until -2%), NQ ORB at half.
import sys, numpy as np, pandas as pd
exec(open('trim_weak.py').read().split("VAR = {")[0])
CFG = (0.07, 0.905, (0.04, 0.02))
exec("def ev(cfg)" + open('safer_dd.py').read().split("def ev(cfg)")[1].split("CFG = [")[0])
r0 = BASE[0].copy(); l0 = BASE[1].copy()          # NQ ORB at full 0.625
b5 = bars1("fut1m/USA500IDXUSD_1m.csv", "5min"); c5 = b5.c; C5 = c5.to_numpy()
a5 = rma(pd.concat([b5.h - b5.l, (b5.h - c5.shift()).abs(), (b5.l - c5.shift()).abs()], axis=1).max(axis=1), 14).to_numpy()
ny = b5.index.tz_convert("America/New_York"); m5 = ny.hour * 60 + ny.minute; w5 = (m5 >= 570) & (m5 < 720)
hi = b5.h.rolling(50).max().shift(1).to_numpy(); lo5 = b5.l.rolling(50).min().shift(1).to_numpy(); e5 = c5.ewm(span=200, adjust=False).mean().to_numpy()
spxbo = P.trade_series(simT(b5, w5 & (C5 > hi) & (C5 > e5), w5 & (C5 < lo5) & (C5 < e5), 2 * a5, 10 ** 6, m5 >= 950), 0.0001, spx, idx)
CAND = {"silver 1h dip": SER["silver1h"], "ETH 1h dip": SER["eth1h"], "SOL 1h dip": SER["sol1h"], "gold 1h dip (6-day hold)": SER["gold1h144"],
        "BTC 1h dip (6-day hold)": SER["btc1h144"], "NQ 15m breakout": bo, "SPX 5m breakout": spxbo}
bq = bars1("fut1m/USATECHIDXUSD_1m.csv", "15min"); cq = bq.c; Cq = cq.to_numpy()
aq = rma(pd.concat([bq.h - bq.l, (bq.h - cq.shift()).abs(), (bq.l - cq.shift()).abs()], axis=1).max(axis=1), 14).to_numpy()
nyq = bq.index.tz_convert("America/New_York"); mq = nyq.hour * 60 + nyq.minute; wq = (mq >= 570) & (mq < 720)
hiq = bq.h.rolling(20).max().shift(1).to_numpy(); loq = bq.l.rolling(20).min().shift(1).to_numpy(); eq_ = cq.ewm(span=200, adjust=False).mean().to_numpy()
BO_TR = simT(bq, wq & (Cq > hiq) & (Cq > eq_), wq & (Cq < loq) & (Cq < eq_), aq, 10 ** 6, mq >= 950)
print("check NQ bo rebuilt == bo:", np.allclose(P.trade_series(BO_TR, 0.00012, nq, idx)[0], bo[0]), flush=True)
CAND["NQ bo 0.2 + SPX bo 0.1"] = (0.2 * bo[0] + 0.1 * spxbo[0], 0.2 * bo[1] + 0.1 * spxbo[1])
CAND["NQ bo 0.2, NQ bo costs x2"] = (0.2 * P.trade_series(BO_TR, 0.00024, nq, idx)[0], 0.2 * P.trade_series(BO_TR, 0.00024, nq, idx)[1])
r0 = r0 + 0.2 * bo[0]; l0 = l0 + 0.2 * bo[1]          # current 11 EAs
SB_TR = simT(b5, w5 & (C5 > hi) & (C5 > e5), w5 & (C5 < lo5) & (C5 < e5), 2 * a5, 10 ** 6, m5 >= 950)
SBS = P.trade_series(SB_TR, 0.0001, spx, idx); r0 = r0 + 0.1 * SBS[0]; l0 = l0 + 0.1 * SBS[1]      # current 12 EAs
import glob, io
parts = [pd.read_csv(io.StringIO(open(f).read().strip()), header=None, names=["t", "o", "h", "l", "c", "v"]) for f in sorted(glob.glob("eu1m/days/*.csv")) if open(f).read().strip()]
dax = pd.concat(parts); dax["t"] = pd.to_datetime(dax.t, unit="s", utc=True); dax = dax.drop_duplicates("t").set_index("t").sort_index()
dh1 = dax.resample("1h").agg(dict(o="first", h="max", l="min", c="last")).dropna()
SRC = {"DEU": ("world_DEUIDXEUR.pkl", dh1, 0.0001), "USATECH": ("world_USATECHIDXUSD.pkl", nq, 0.00012), "USA500": ("world_USA500IDXUSD.pkl", spx, 0.0001),
       "XAU": ("world_XAUUSD.pkl", gold, 0.0001), "BTC": ("world_BTCUSDT.pkl", btc, P.FEE_CRYPTO)}
VARS = [("DEU", "DEU 15min ORB60 trend50 target0 stop-mid", "DAX ORB 60-min range"), ("DEU", "DEU 5min ORB15 trend50 target0 stop-mid", "DAX ORB 15-min range (5m)"),
        ("DEU", "DEU 5min ORB30 trend50 target0 stop-mid", "DAX ORB 30-min range (5m)"), ("DEU", "DEU 15min ORB30 trend20 target0 stop-mid", "DAX ORB EMA20 filter"),
        ("USATECH", "USA 15min breakout50 EMA200 stop1.0ATR", "NQ 15m 50-bar breakout"), ("USA500", "USA 5min breakout20 EMA800 stop2.0ATR", "SPX 5m 20-bar/EMA800 breakout"),
        ("XAU", "XAU 1h dip RSI2<15 EMA200 hold96", "Gold dip EMA200 4-day"), ("XAU", "XAU 1h dip RSI2<25 EMA200 hold144", "Gold dip EMA200 6-day"),
        ("BTC", "BTC 1h dip RSI2<15 EMA50 hold96", "BTC 1h dip 4-day"), ("BTC", "BTC 2h dip RSI2<10 EMA200 hold144", "BTC 2h dip EMA200 6-day")]
CAND = {}
for mk, key, lab in VARS:
    f, h1, cost = SRC[mk]; _, TRX = pd.read_pickle(f)
    if key not in TRX: print("missing", key); continue
    CAND[lab] = P.trade_series(TRX[key], cost, h1, idx)
    dd = pd.DataFrame({"x": CAND[lab][0], "port": r0}, index=idx).resample("1D").sum(); dd = dd[dd.abs().sum(axis=1) > 0]
    pass  # print(f"{lab}: corr with 12 EAs {dd.corr().iloc[0, 1]:.2f}", flush=True)
def combo(keys, w=0.05): return (sum(w * CAND[k][0] for k in keys), sum(w * CAND[k][1] for k in keys))
SURV = ["DAX ORB 60-min range", "DAX ORB 15-min range (5m)", "DAX ORB 30-min range (5m)", "DAX ORB EMA20 filter", "BTC 1h dip 4-day", "BTC 2h dip EMA200 6-day"]
CAND["all 6 survivors"] = combo(SURV)
CAND["2 DAX (60-min, 15-min 5m) + 2 BTC"] = combo(["DAX ORB 60-min range", "DAX ORB 15-min range (5m)", "BTC 1h dip 4-day", "BTC 2h dip EMA200 6-day"])
CAND["1 DAX (60-min) + 1 BTC (2h EMA200)"] = combo(["DAX ORB 60-min range", "BTC 2h dip EMA200 6-day"])
CAND["4 DAX versions only"] = combo(SURV[:4])
CAND["2 BTC versions only"] = combo(SURV[4:])
JOBS = [("current 12 EAs", None, 0)] + [(k, k, 1.0) for k in ("all 6 survivors", "2 DAX (60-min, 15-min 5m) + 2 BTC", "1 DAX (60-min) + 1 BTC (2h EMA200)", "4 DAX versions only", "2 BTC versions only")]
def runc(job):
    nm, k, w = job
    global r_, lo_
    r_ = r0 + (w * CAND[k][0] if k else 0); lo_ = l0 + (w * CAND[k][1] if k else 0)
    out = ev(CFG); out = {"add-on": nm if not k else f"+ {k} @{w}%"} | {kk: v for kk, v in out.items() if not kk.startswith(("size", "hard", "half"))}
    rr = pd.Series(r_, index=idx); out["2026 %"] = 100 * ((1 + rr[rr.index.year == 2026]).prod() - 1)
    ys = [(1 + rr[idx.searchsorted(s):idx.searchsorted(s + pd.DateOffset(years=1))]).prod() - 1 for s in pd.date_range("2020-04-01", "2025-10-01", freq="MS", tz="UTC")]
    out["funded yr median %"] = 100 * np.median(ys); return out
with Pool(4) as p: rows = p.map(runc, JOBS)
df = pd.DataFrame(rows); pd.set_option("display.width", 400); pd.set_option("display.max_columns", 40)
keep = ["add-on"] + [c for c in df.columns if ("pass" in c or "breach" in c or "days" in c or "-8%" in c)] + ["2026 %", "funded yr median %"]
print(df[keep].round(1).to_string(index=False)); df.to_pickle("readd.pkl")
