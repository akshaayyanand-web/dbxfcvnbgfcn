import sys, numpy as np, pandas as pd
SP = sys.argv[1]
exec(open(SP + "/portfolio5.py").read().split("evalw=")[0])
K = {}
exec(open(SP + "/kavach_dip_hybrid.py").read().split("GRID =")[0], K)
d15, cost = K["m15"]("Nasdaq"); d = d15.resample("1h").agg(dict(o="first", h="max", l="min", c="last")).dropna()
z, atr, adx, vr, don = K["indicators"](d, 20); gate_arr = (vr > 1.1) | (adx > 25) | don | np.isnan(vr)
ema = d.c.ewm(span=200).mean().to_numpy(); o, h, l, c = (d[k].to_numpy() for k in "ohlc")
variants = {}
for nm, (zth, mult) in {"nqdip_eq": (2.0, 1.0), "nqdip_x2": (2.0, 2.0), "nqdip_z25": (2.5, 1.0)}.items():
    r, lo, nb, w = K["basket2"](o, h, l, c, z, atr, ema, gate_arr, cost, zth, True, False, 3, mult, 1.0, "z0", 48)
    s = pd.DataFrame({"r": r / 2, "lo": lo / 2}, index=d.index)          # 2% worst case -> 1% worst case = weight 1.0
    s.index = s.index.tz_convert("UTC") if s.index.tz is not None else s.index.tz_localize("UTC")
    s = s.reindex(idx).fillna(0.0); variants[nm] = (s.r.to_numpy(), s.lo.to_numpy())
dd = pd.DataFrame({k: v[0] for k, v in variants.items()} | {k: C[k][0] for k in ("nqmom", "orb15", "gdip", "btc")}, index=idx).resample("1D").sum()
print("daily correlation:"); print(dd[dd.abs().sum(axis=1) > 0].corr().round(2).loc[list(variants)].to_string())
base = dict(btc=1.0, gdip=0.5, gasia=0.25, nqmom=0.25, gmom=0.25, orb15=0.5)
names0 = list(names); R0, LO0 = R, LO
est = pd.date_range("2020-04-01", "2025-09-01", freq="7D", tz="UTC"); wst = pd.date_range("2020-04-01", "2025-10-01", freq="MS", tz="UTC")
tr1 = pd.Timestamp("2024-01-01", tz="UTC"); trs = pd.date_range("2020-04-01", "2022-12-01", freq="MS", tz="UTC")
print(f"\n{'portfolio':<34} | {'2-step pass':>11}{'breach':>7}{'halted':>7}{'median':>8} | {'funded med':>10}{'avg':>7}{'breach':>8} | {'2020-23 train med':>17}")
for nm, wt in [("current six", 0)] + [(v, x) for v in variants for x in (0.25, 0.5, 0.75)]:
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
    print(f"{nm + (f' {wt}' if wt else ''):<34} | {100*(rr=='pass').mean():10.0f}%{100*(rr=='fail').mean():6.0f}%{100*(rr=='stopped').mean():6.0f}%{np.median(tm):7.0f}d | "
          f"{np.median(yr):+9.1f}%{np.mean(yr):+6.1f}%{br:5d}/67 | {100*np.median(trn):+16.1f}%", flush=True)
