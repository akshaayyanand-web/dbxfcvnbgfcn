# Run from the scratchpad (needs fund_check.py chain, dax_lab.pkl, DAX day files).
# Trade management: breakeven / profit-lock stops on NQ ORB, DAX ORB, BTC Dip, Gold Dip.
import sys, numpy as np, pandas as pd
exec(open('fund_check.py').read().split("C = [")[0])
import orb_lab as O
from portfolio_prop import resample
def manage(trades, bars, act, lock):
    """After the bar where price reaches +act R, the stop moves to entry + lock R (from the next bar on)."""
    if act is None: return trades
    T = bars.index; Op, H, L = bars.o.to_numpy(), bars.h.to_numpy(), bars.l.to_numpy(); out = []
    for et, xt, e, st, px in trades:
        d = 1 if st < e else -1; R = abs(e - st); s = st; j = T.searchsorted(et); new = None
        k = j
        while k < len(T) and T[k] < xt:
            if (L[k] <= s) if d == 1 else (H[k] >= s):
                if s != st: new = ((min(Op[k], s) if d == 1 else max(Op[k], s)), T[k]); break
            if (H[k] >= e + act * R) if d == 1 else (L[k] <= e - act * R): s = (max(s, e + lock * R) if d == 1 else min(s, e - lock * R))
            k += 1
        out.append((et, new[1], e, st, new[0]) if new else (et, xt, e, st, px))
    return out
def stats(trades, cost, name):
    R = np.array([(px - e) / abs(e - st) * np.sign(e - st) - cost * e / abs(e - st) for et, xt, e, st, px in trades])
    t = pd.DatetimeIndex([x[0] for x in trades]); A = t < split
    ya = (t[A][-1] - t[A][0]).days / 365.25; yb = (t[~A][-1] - t[~A][0]).days / 365.25
    return dict(test=name, win_pct=100 * (R > 0).mean(), avg_win=R[R > 0].mean(), avg_loss=R[R <= 0].mean(), full_losses_pct=100 * (R < -0.9).mean(),
                yrA=R[A].sum() / ya, yrB=R[~A].sum() / yb)
SETS = {}
nq5 = O.five_min(load_csv("fut1m/USATECHIDXUSD_1m.csv")); cq = O.COST["USATECHIDXUSD"]
SETS["NQ ORB"] = ([a[:5] for a in O.orb(nq5, "America/New_York", (9, 30), (11, 30), (15, 55), 15, "other", 2.0, True, cq)], nq5, cq)
dfd, TRD = pd.read_pickle("dax_lab.pkl")
import glob, io
parts = [pd.read_csv(io.StringIO(open(f).read().strip()), header=None, names=["t", "o", "h", "l", "c", "v"]) for f in sorted(glob.glob("eu1m/days/*.csv")) if open(f).read().strip()]
dax = pd.concat(parts); dax["t"] = pd.to_datetime(dax.t, unit="s", utc=True); dax = dax.drop_duplicates("t").set_index("t").sort_index()
dax15 = dax.resample("15min").agg(dict(o="first", h="max", l="min", c="last")).dropna()
SETS["DAX ORB"] = (TRD["DAX 15min ORB30 trend50 target0 stop-mid"], dax15, 0.0001)
bt, cb = P.dip_trades(btc, "2h", 3, 20, 0.15, P.FEE_CRYPTO); SETS["BTC Dip"] = (bt, resample(btc, "2h"), cb)
gt, cg = P.dip_trades(gold, "1h", 2, 10, 0.08, P.COST["XAUUSD"]); SETS["Gold Dip"] = (gt, gold, cg)
rows = []
for nm, (tr, bars, cost) in SETS.items():
    for act, lock in ((None, None), (0.5, 0.0), (1.0, 0.0), (1.5, 0.5), (2.0, 1.0), (1.0, 0.25)):
        lab = "current exits" if act is None else f"at +{act}R move stop to {'entry' if lock == 0 else f'+{lock}R'}"
        rows.append(stats(manage(tr, bars, act, lock), cost, f"{nm}: {lab}"))
df = pd.DataFrame(rows); pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 60)
print(df.round(2).to_string(index=False)); df.to_pickle("be_test.pkl")
