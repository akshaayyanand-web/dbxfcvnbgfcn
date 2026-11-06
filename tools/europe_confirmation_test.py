# Run from the scratchpad (needs DAX day files).
import sys, numpy as np, pandas as pd
sys.path.insert(0, "/home/user/dbxfcvnbgfcn/tools")
from portfolio_prop import load_csv, rma
SP = "."; src = open("lowtf_port.py").read(); exec("def bars1" + src.split("def bars1", 1)[1].split("def cands")[0])
import glob, io
parts = [pd.read_csv(io.StringIO(open(f).read().strip()), header=None, names=["t","o","h","l","c","v"]) for f in sorted(glob.glob("eu1m/days/*.csv")) if open(f).read().strip()]
dax = pd.concat(parts); dax["t"] = pd.to_datetime(dax.t, unit="s", utc=True); dax = dax.drop_duplicates("t").set_index("t").sort_index().c
fr = dax.index.tz_convert("Europe/Berlin"); fm = fr.hour * 60 + fr.minute; fday = fr.normalize().tz_localize(None)
op = dax[fm == 540].groupby(fday[fm == 540]).first()                  # 09:00 Frankfurt
nowp = dax[(fm >= 920) & (fm < 925)].groupby(fday[(fm >= 920) & (fm < 925)]).last()   # ~15:25 Frankfurt = 09:25 NY
eu = np.sign(nowp / op.reindex(nowp.index) - 1).dropna()
print("days with a Europe direction:", len(eu))
FILES = {"nq": ("fut1m/USATECHIDXUSD_1m.csv", 0.00012), "spx": ("fut1m/USA500IDXUSD_1m.csv", 0.0001)}
rows = []
for mk, tf, N, en, sm in (("nq", "15min", 20, 200, 1.0), ("nq", "5min", 50, 800, 1.0), ("spx", "5min", 50, 200, 2.0), ("spx", "5min", 20, 800, 2.0), ("nq", "15min", 50, 200, 1.0)):
    b = bars1(FILES[mk][0], tf); cost = FILES[mk][1]; c = b.c; Cc = c.to_numpy()
    atr = rma(pd.concat([b.h - b.l, (b.h - c.shift()).abs(), (b.l - c.shift()).abs()], axis=1).max(axis=1), 14).to_numpy()
    ny = b.index.tz_convert("America/New_York"); m = (ny.hour * 60 + ny.minute).to_numpy()
    win = (m >= 570) & (m < 720); flat = m >= 950
    hi = b.h.rolling(N).max().shift(1).to_numpy(); lo = b.l.rolling(N).min().shift(1).to_numpy(); e = c.ewm(span=en, adjust=False).mean().to_numpy()
    tr = simT(b, win & (Cc > hi) & (Cc > e), win & (Cc < lo) & (Cc < e), sm * atr, 10 ** 6, flat)
    tr = [t for t in tr if t[0] >= pd.Timestamp("2021-01-04", tz="UTC")]
    R = np.array([(px - en_) / abs(en_ - st) * np.sign(en_ - st) - cost * en_ / abs(en_ - st) for et, xt, en_, st, px in tr])
    R2 = R - np.array([cost * en_ / abs(en_ - st) for et, xt, en_, st, px in tr])
    d = np.array([np.sign(en_ - st) for et, xt, en_, st, px in tr]); day = pd.DatetimeIndex([t[0].tz_convert("Europe/Berlin").normalize().tz_localize(None) for t in tr])
    ed = eu.reindex(day).to_numpy(); t = pd.DatetimeIndex([x[0] for x in tr]); A = t < pd.Timestamp("2023-01-01", tz="UTC")
    for lab, keep in (("all trades", np.ones(len(R), bool)), ("with Europe", ed == d), ("against Europe", ed == -d)):
        ya = (t[A][-1] - t[A][0]).days / 365.25; yb = (t[~A][-1] - t[~A][0]).days / 365.25
        rows.append(dict(strategy=f"{mk} {tf} {N}-bar EMA{en} stop{sm}", filter=lab, trades_mo=keep.sum() / ((t[-1] - t[0]).days / 30.4),
                         avgR=R[keep].mean(), yrA=R[keep & A].sum() / ya, yrB=R[keep & ~A].sum() / yb, yrB_cost2=R2[keep & ~A].sum() / yb))
pd.set_option("display.width", 250); print(pd.DataFrame(rows).round(2).to_string(index=False))
