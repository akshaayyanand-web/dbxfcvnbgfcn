# Run from the scratchpad (needs fund_check.py chain, ea_trades.pkl, DAX day files).
import sys, numpy as np, pandas as pd
exec(open('fund_check.py').read().split("C = [")[0])
from portfolio_prop import resample
import glob, io
TRL = pd.read_pickle("ea_trades.pkl")
parts = [pd.read_csv(io.StringIO(open(f).read().strip()), header=None, names=["t","o","h","l","c","v"]) for f in sorted(glob.glob("eu1m/days/*.csv")) if open(f).read().strip()]
dax = pd.concat(parts); dax["t"] = pd.to_datetime(dax.t, unit="s", utc=True); dax = dax.drop_duplicates("t").set_index("t").sort_index()
dax15 = dax.resample("15min").agg(dict(o="first", h="max", l="min", c="last")).dropna()
import orb_lab as O
nq5 = O.five_min(load_csv("fut1m/USATECHIDXUSD_1m.csv"))
BARS = {"BTC_Dip_v3": resample(btc, "2h"), "Gold_Dip": gold, "Gold_Asia_Breakout": gold, "Gold_Intraday_Momentum": gold, "NQ_Opening_Range": nq5,
        "NQ_Dip_2h": resample(nq, "2h"), "SPX_Dip_1h": spx, "Oil_Dip_1h": oil, "BTC_Weekend_Gap": btc, "DAX_Opening_Range": dax15}
def resim(tr, bars, tpR, slx):
    T = bars.index; Op, H, L = bars.o.to_numpy(), bars.h.to_numpy(), bars.l.to_numpy(); out = []
    for et, xt, e, st, px in tr:
        d = 1 if st < e else -1; R = abs(e - st); s2 = e - d * slx * R; tg = e + d * tpR * R
        j = T.searchsorted(et); k = j; new = None
        while k < len(T) and T[k] < xt:
            if (L[k] <= s2) if d == 1 else (H[k] >= s2): new = (min(Op[k], s2) if d == 1 else max(Op[k], s2)); break
            if (H[k] >= tg) if d == 1 else (L[k] <= tg): new = (max(Op[k], tg) if d == 1 else min(Op[k], tg)); break
            k += 1
        if new is None: new = px if slx == 1 else px          # original time exit (or original stop if slx==1 and hit at the exit bar)
        out.append((et, e, s2, new))
    return out
rows = []
for nm, (tr, cost, risk) in TRL.items():
    for tpR, slx in ((None, 1), (0.25, 1), (0.33, 1), (0.5, 1), (0.75, 1), (1.0, 2.0), (0.5, 2.0)):
        if tpR is None: res = [(et, e, st, px) for et, xt, e, st, px in tr]
        else: res = resim(tr, BARS[nm], tpR, slx)
        R = np.array([(px - e) / abs(e - st) * np.sign(e - st) - cost * e / abs(e - st) for et, e, st, px in res])
        t = pd.DatetimeIndex([x[0] for x in res]); A = t < pd.Timestamp("2023-01-01", tz="UTC")
        ya = max((t[A][-1] - t[A][0]).days / 365.25, .5); yb = max((t[~A][-1] - t[~A][0]).days / 365.25, .5)
        lab = "current exits" if tpR is None else (f"TP {tpR}R, same SL" if slx == 1 else f"SL x2, TP {tpR * 2:g}x old risk (1:{2 / tpR / 2 * 2:g})")
        rows.append(dict(EA=nm, exit=lab, win=100 * (R > 0).mean(), yrA=R[A].sum() / ya, yrB=R[~A].sum() / yb))
df = pd.DataFrame(rows); df["minhalf"] = df[["yrA", "yrB"]].min(axis=1)
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
print(df.round(1).to_string(index=False)); df.to_pickle("negrr_eas.pkl")
