import sys, numpy as np, pandas as pd
SP = sys.argv[1]
exec(open(SP + "/portfolio5.py").read().split("evalw=")[0])
K = {}
exec(open(SP + "/dipgrid_exits.py").read().split("GRID =")[0], K)
variants = {}
for nm, (m, ex) in {"nq_trail": ("Nasdaq", "trail"), "spx_trail": ("S&P 500", "trail"), "gold_trail": ("Gold", "trail"), "nq_z0": ("Nasdaq", "z0")}.items():
    f, cost = K["MK"][m]; d = K["load_csv"](SP + "/" + f).loc["2016-01-01":]
    z, atr, *_ = K["K"]["indicators"](d, 20); ema = d.c.ewm(span=200).mean().to_numpy(); o, h, l, c = (d[k].to_numpy() for k in "ohlc")
    r, lo, _ = K["basket3"](o, h, l, c, z, atr, ema, cost, 2.0, 3, 1.0, ex, 0, 120 if ex == "trail" else 48)
    s = pd.DataFrame({"r": r / 2, "lo": lo / 2}, index=d.index).reindex(idx).fillna(0.0); variants[nm] = (s.r.to_numpy(), s.lo.to_numpy())
V = dict(variants); variants = {}
for nm, ws in {"+NQ&SPX 0.5": (0.5, 0.5, 0), "+NQ&SPX 0.5 +gold 0.25": (0.5, 0.5, 0.25), "+NQ&SPX 0.5 +gold 0.5": (0.5, 0.5, 0.5), "+NQ&SPX 0.75": (0.75, 0.75, 0)}.items():
    variants[nm] = tuple(ws[0] * V["nq_trail"][j] + ws[1] * V["spx_trail"][j] + ws[2] * V["gold_trail"][j] for j in (0, 1))
dd = pd.DataFrame({k: v[0] for k, v in variants.items()} | {k: C[k][0] for k in ("nqmom", "orb15", "gdip", "btc")}, index=idx).resample("1D").sum()

base = dict(btc=1.0, gdip=0.5, gasia=0.25, nqmom=0.25, gmom=0.25, orb15=0.5)
names0 = list(names); R0, LO0 = R, LO
est = pd.date_range("2020-04-01", "2025-09-01", freq="7D", tz="UTC"); wst = pd.date_range("2020-04-01", "2025-10-01", freq="MS", tz="UTC")
tr1 = pd.Timestamp("2024-01-01", tz="UTC"); trs = pd.date_range("2020-04-01", "2022-12-01", freq="MS", tz="UTC")
print(f"\n{'portfolio':<34} | {'2-step pass':>11}{'breach':>7}{'halted':>7}{'median':>8} | {'funded med':>10}{'avg':>7}{'breach':>8} | {'2020-23 train med':>17}")
for nm, wt in [("current six", 0)] + [(v, x) for v in variants for x in (1.0,)]:
    if nm == "current six": R, LO, names = R0, LO0, names0
    else:
        names = names0 + [nm]; R = np.vstack([R0, variants[nm][0]]); LO = np.vstack([LO0, variants[nm][1]])
    w = np.array([base.get(k, 0) for k in names0] + ([wt] if nm != "current six" else []), float)
    res = []; tm = []
    for s_ in est:
        h0 = idx.searchsorted(s_); a, i1, _ = run(w, h0, len(idx), 0.10)
        if a != "pass": res.append(a); continue
        b, i2, _ = run(w, h0 + i1 + 1, len(idx), 0.05); res.append(b)
        if b == "pass": tm.append((i1 + i2) / 24)
    yr = []; br = 0
    for s_ in wst:
        st, _, ret = run(w, idx.searchsorted(s_), idx.searchsorted(s_ + pd.DateOffset(years=1))); yr.append(100 * ret); br += st == "fail"
    trn = [run(w, idx.searchsorted(s_), idx.searchsorted(min(s_ + pd.DateOffset(years=1), tr1)), maxl=0.08, daily=0.04)[2] for s_ in trs]
    rr = pd.Series(res)
    cal = {y: round(100 * run(w, idx.searchsorted(pd.Timestamp(f"{y}-01-01", tz="UTC")), idx.searchsorted(pd.Timestamp(f"{y+1}-01-01", tz="UTC")))[2]) for y in range(2020, 2027)}
    eqc = np.cumprod(1 + (R * w[:, None]).sum(0)); mdd = 100 * np.max(1 - eqc / np.maximum.accumulate(eqc))
    print(f"{nm + (f' {wt}' if wt else ''):<34} | {100*(rr=='pass').mean():10.0f}%{100*(rr=='fail').mean():6.0f}%{100*(rr=='stopped').mean():6.0f}%{np.median(tm):7.0f}d | "
          f"{np.median(yr):+9.1f}%{np.mean(yr):+6.1f}%{br:5d}/67 | {100*np.median(trn):+16.1f}% | maxDD {mdd:.1f}% | years {cal}", flush=True)
