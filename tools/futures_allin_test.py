# Futures 50K all-in: each day take the intraday EA's signal risking the room left to the trailing floor, target = what is left to +3,000; new account on bust.
import sys, numpy as np, pandas as pd
sys.path.insert(0, "/home/user/dbxfcvnbgfcn/tools")
from portfolio_prop import load_csv
# 1) how long do the BTC/SOL dip one-shots take to resolve at 1.5R?
exec(open("one_trade_test.py").read().split("rows = []")[0])
for lab, (sym, pk, nm, cost) in ([] if True else SETS.items()):
    df, TR = pd.read_pickle(pk)
    if nm is None: nm = df[df.edge.str.contains("dip")].sort_values("minhalf", ascending=False).edge.iloc[0]
    b = h1(sym); H, L, T = b.h.to_numpy(), b.l.to_numpy(), b.index; hrs = []; sameday = 0
    for et, xt, e, st, px in TR[nm]:
        R = e - st; tp = e + 1.5 * R; k = T.searchsorted(et)
        for j in range(k, min(k + 720, len(T))):
            if L[j] <= st or H[j] >= tp: hrs.append(j - k + 1); break
    hrs = np.array(hrs); print(f"{lab}: hours to stop/target at 1.5R: median {np.median(hrs):.0f}, resolved within 6h {100*(hrs<=6).mean():.0f}%, within 24h {100*(hrs<=24).mean():.0f}%")
# 2) intraday EAs, all-in each day on a 50K (target +3,000, EOD trailing max loss 2,000), flat at the strategy's own end-of-day exit
TRL = pd.read_pickle("ea_trades.pkl")
DATA = {"NQ_Opening_Range": "fut1m/USATECHIDXUSD_1m.csv", "Gold_Intraday_Momentum": "fut1m/XAUUSD_1m.csv", "Gold_Asia_Breakout": "fut1m/XAUUSD_1m.csv"}
cache = {}
rows = []
for nm, path in DATA.items():
    if path not in cache: cache[path] = load_csv(path)
    m1 = cache[path]; H1_, L1_, T1 = m1.h.to_numpy(), m1.l.to_numpy(), m1.index
    tr, cost = TRL[nm][0], TRL[nm][1]; tr = [x for x in tr if x[0] >= pd.Timestamp("2020-01-01", tz="UTC")]
    # outcome of each trade for a target of k R: +k (target), -1 (stop) or the R at the strategy's own exit
    def outcome(t, kR):
        et, xt, e, st, px = t; d = 1 if e > st else -1; R = abs(e - st); tp = e + d * (kR + cost * e / R) * R
        a, z = T1.searchsorted(et), T1.searchsorted(xt)
        for j in range(a, z):
            if (L1_[j] <= st) if d == 1 else (H1_[j] >= st): return -1.0 - cost * e / R
            if (H1_[j] >= tp) if d == 1 else (L1_[j] <= tp): return kR
        return max((px - e) / R * d, -1.0) - cost * e / R
    for buf in (1.0, 0.75):          # risk all the room left (100%) or 75% of it
        D, A = [], []
        dates = pd.DatetimeIndex([x[0] for x in tr])
        for s in pd.date_range("2020-02-01", "2026-03-01", freq="3D", tz="UTC"):
            k = dates.searchsorted(s); acc = 1; bal = 0.0; peak = 0.0; ok = False
            while k < len(tr):
                floor = min(peak - 2000.0, 0.0); room = bal - floor; risk = buf * room
                kR = (3000.0 - bal) / risk
                r = outcome(tr[k], kR); bal += r * risk; peak = max(peak, bal)
                if bal >= 3000 - 1e-6: ok = True; break
                if bal - min(peak - 2000.0, 0.0) < 100: acc += 1; bal = 0.0; peak = 0.0
                k += 1
            if ok: D.append((tr[k][1] - s).total_seconds() / 86400); A.append(acc)
        D, A = np.array(D), np.array(A)
        rows.append(dict(strategy=nm, risk=f"{int(buf*100)}% of room", trades_per_month=round(len(tr) / ((tr[-1][0] - tr[0][0]).days / 30.4), 1),
                         median_days=round(np.median(D), 1), within_7d=f"{100*(D<=7).mean():.0f}%", within_14d=f"{100*(D<=14).mean():.0f}%",
                         within_30d=f"{100*(D<=30).mean():.0f}%", first_try=f"{100*(A==1).mean():.0f}%", mean_accounts=round(A.mean(), 2), p90_accounts=int(np.percentile(A, 90))))
pd.set_option("display.width", 250); print(pd.DataFrame(rows).to_string(index=False))
