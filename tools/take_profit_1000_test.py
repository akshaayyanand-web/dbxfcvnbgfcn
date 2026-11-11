# Run from the scratchpad (needs negrr_eas.py chain).
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
    rUSD = 100000 * risk / 100                           # dollars risked per trade on a $100K account
    tpR = 1000.0 / rUSD                                   # +$1,000 expressed in R
    for lab, res in (("current exits", [(et, e, st, px) for et, xt, e, st, px in tr]), ("close at +$1,000", resim(tr, BARS[nm], tpR, 1))):
        R = np.array([(px - e) / abs(e - st) * np.sign(e - st) - cost * e / abs(e - st) for et, e, st, px in res])
        t = pd.DatetimeIndex([x[0] for x in res]); yrs = (t[-1] - t[0]).days / 365.25
        rows.append(dict(EA=nm, risk_usd=rUSD, rule=lab, tp_in_R=round(tpR, 2), win_pct=100 * (R > 0).mean(), usd_per_year=R.sum() * rUSD / yrs,
                         biggest_win_usd=R.max() * rUSD))
df = pd.DataFrame(rows); pd.set_option("display.width", 250); print(df.round(0).to_string(index=False))
tot = df.groupby("rule").usd_per_year.sum(); print("\nall 10 EAs, $ per year on a $100K account:", tot.round(0).to_dict())
