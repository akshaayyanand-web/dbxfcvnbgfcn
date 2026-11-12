# One-shot with resets: take the next BTC/SOL dip at 4.5% risk, buy a new account after each loss; days and fees to funded.
import numpy as np, pandas as pd
exec(open("one_trade_test.py").read().split("rows = []")[0])
# resolve every BTC + SOL dip entry at +2.2R and +1.1R targets: (entry time, exit time, win?)
ev = []
for lab, (sym, pk, nm, cost) in SETS.items():
    df, TR = pd.read_pickle(pk)
    if nm is None: nm = df[df.edge.str.contains("dip")].sort_values("minhalf", ascending=False).edge.iloc[0]
    bars = h1(sym); H, L, T = bars.h.to_numpy(), bars.l.to_numpy(), bars.index
    for et, xt, e, st, px in TR[nm]:
        R = e - st; k = T.searchsorted(et); res = {}
        for tpR in (1.1, 2.2):
            tp = e + tpR * R + cost * e; out = (False, T[min(k + 720, len(T) - 1)])
            for j in range(k, min(k + 720, len(T))):
                if L[j] <= st: out = (False, T[j]); break
                if H[j] >= tp: out = (True, T[j]); break
            res[tpR] = out
        ev.append((pd.Timestamp(et), res))
ev.sort(key=lambda x: x[0]); ET = pd.DatetimeIndex([x[0] for x in ev]).as_unit("ns")
def run(start, fee):
    t = start; accounts = 1; phase = 1; phase_start = start
    while True:
        k = ET.searchsorted(pd.Timestamp(t).as_unit("ns"))
        if k >= len(ev): return None
        et, res = ev[k]; win, done = res[2.2 if phase == 1 else 1.1]
        if not win: accounts += 1; phase = 1; t = done + pd.Timedelta("1h"); phase_start = t; continue
        end = max(done, phase_start + pd.Timedelta(days=5.6))     # 4 trading days minimum (~5.6 calendar days)
        if phase == 1: phase = 2; t = end + pd.Timedelta(days=1); phase_start = t; continue
        return (end - start).days, accounts, accounts * fee
out = [run(s, 250) for s in pd.date_range("2020-10-01", "2026-03-01", freq="1D", tz="UTC")]
out = [o for o in out if o]
d = np.array([o[0] for o in out]); a = np.array([o[1] for o in out]); c = np.array([o[2] for o in out])
print(f"starts: {len(out)}; signals per month: {len(ev) / ((ET[-1] - ET[0]).days / 30.4):.1f}")
print(f"days to funded: median {np.median(d):.0f}, 25% {np.percentile(d, 25):.0f}, 75% {np.percentile(d, 75):.0f}, 90% {np.percentile(d, 90):.0f}")
print(f"funded within 14 days {100*(d<=14).mean():.0f}%, 30 days {100*(d<=30).mean():.0f}%, 60 days {100*(d<=60).mean():.0f}%")
print(f"accounts bought: median {np.median(a):.0f}, mean {a.mean():.1f}, 90% {np.percentile(a, 90):.0f}, max {a.max()}; fees at $250: mean ${c.mean():.0f}, 90% ${np.percentile(c, 90):.0f}")
