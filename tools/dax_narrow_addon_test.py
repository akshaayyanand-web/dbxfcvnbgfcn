# Run from the scratchpad (needs spx_add11.py chain).
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
r0 = r0 + 0.1 * CAND["SPX 5m breakout"][0]; l0 = l0 + 0.1 * CAND["SPX 5m breakout"][1]      # current 12 EAs
_ns = {}; sys.argv = ["x", "DEUIDXEUR"]; exec(open("world_lab.py").read().split("rows, TR = [], {}")[0], _ns)
_, TRD = pd.read_pickle("dax_lab.pkl"); trd = TRD["DAX 15min ORB30 trend50 target0 stop-mid"]
bd = _ns["bars"]("15min"); frd = bd.index.tz_convert("Europe/Berlin"); fmd = frd.hour * 60 + frd.minute; fdd = frd.normalize()
inr = (fmd >= 540) & (fmd < 570)
gd = pd.DataFrame({"h": np.where(inr, bd.h, np.nan), "l": np.where(inr, bd.l, np.nan), "d": fdd}).groupby("d").agg(h=("h", "max"), l=("l", "min"))
drg = (bd.h.resample("1D").max() - bd.l.resample("1D").min()).dropna(); datr = drg.ewm(alpha=1 / 14, adjust=False).mean().shift(1)
wid = []
for et, xt, e, st, px in trd:
    dd_ = et.tz_convert("Europe/Berlin").normalize(); wid.append((gd.h.get(dd_, np.nan) - gd.l.get(dd_, np.nan)) / datr.asof(et.normalize()))
wid = np.array(wid); tt = pd.DatetimeIndex([x[0] for x in trd]); thr = np.nanquantile(wid[tt < pd.Timestamp("2023-01-01", tz="UTC")], 0.25)
print(f"narrow threshold from 2021-22 only: range < {thr:.3f} x daily ATR", flush=True)
narrow = [x for x, w in zip(trd, wid) if np.isfinite(w) and w < thr]
Rn = np.array([(px - e) / abs(e - st) * np.sign(e - st) - 0.0001 * e / abs(e - st) for et, xt, e, st, px in narrow]); tn = pd.DatetimeIndex([x[0] for x in narrow])
print(f"narrow-day trades: {len(narrow)}, avg R 2021-22 {Rn[tn < pd.Timestamp('2023-01-01', tz='UTC')].mean():.2f}, 2023-26 {Rn[tn >= pd.Timestamp('2023-01-01', tz='UTC')].mean():.2f}", flush=True)
dh1 = _ns["raw"].resample("1h").agg(dict(o="first", h="max", l="min", c="last")).dropna()
CAND["DAX narrow-range extra"] = P.trade_series(narrow, 0.0001, dh1, idx)
JOBS = [("current 12 EAs", None, 0)] + [("DAX narrow-range extra", "DAX narrow-range extra", w) for w in (0.1, 0.2, 0.3)]
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
