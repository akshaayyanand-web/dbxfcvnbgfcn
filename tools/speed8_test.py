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
for nm, ws in {"EIGHT EAs": (0.5, 0.5, 0)}.items():
    variants[nm] = tuple(ws[0] * V["nq_trail"][j] + ws[1] * V["spx_trail"][j] + ws[2] * V["gold_trail"][j] for j in (0, 1))
dd = pd.DataFrame({k: v[0] for k, v in variants.items()} | {k: C[k][0] for k in ("nqmom", "orb15", "gdip", "btc")}, index=idx).resample("1D").sum()

base = dict(btc=1.0, gdip=0.5, gasia=0.25, nqmom=0.25, gmom=0.25, orb15=0.5)
names0 = list(names); R0, LO0 = R, LO
est = pd.date_range("2020-04-01", "2025-09-01", freq="7D", tz="UTC"); wst = pd.date_range("2020-04-01", "2025-10-01", freq="MS", tz="UTC")
tr1 = pd.Timestamp("2024-01-01", tz="UTC"); trs = pd.date_range("2020-04-01", "2022-12-01", freq="MS", tz="UTC")

from multiprocessing import Pool
names = names0 + ["nqdip", "spxdip"]
R = np.vstack([R0, V["nq_trail"][0], V["spx_trail"][0]]); LO = np.vstack([LO0, V["nq_trail"][1], V["spx_trail"][1]])
W = np.array([base.get(k, 0) for k in names0] + [0.5, 0.5], float)
grp = {"crypto": ["btc"], "gold": ["gdip", "gasia", "gmom"], "nqday": ["nqmom", "orb15"], "dips": ["nqdip", "spxdip"]}
def gvec(gm):
    v = np.ones(len(names))
    for g, m in gm.items():
        for k in grp[g]: v[names.index(k)] = m
    return v
def run2(w, h0, h1, target, mlo=1.0, mhi=1.0, up=None, brake_at=None, brake_m=1.0, halt=0.8, maxl=0.10, daily=0.05):
    r = (R[:, h0:h1] * w[:, None]).sum(0); lo = (LO[:, h0:h1] * w[:, None]).sum(0); eq = 1.0; day = None; hd = None; m = mlo
    for i in range(len(r)):
        d = days[h0 + i]
        if d != day:
            day = d; dopen = eq
            m = mhi if (up is not None and eq - 1 >= up) else mlo
            if brake_at is not None and eq - 1 <= -brake_at: m = brake_m
        if hd == d: continue
        if eq * (1 + m * lo[i]) <= 1 - maxl or eq * (1 + m * lo[i]) <= dopen * (1 - daily): return "fail", i
        eq *= 1 + m * r[i]
        if eq >= 1 + target: return "pass", i
        if 1 - eq / dopen >= halt * daily: hd = d
        if eq <= 1 - 0.8 * maxl: return "stopped", i
    return "open", len(r)
est = pd.date_range("2020-04-01", "2025-09-01", freq="7D", tz="UTC"); split = pd.Timestamp("2023-01-01", tz="UTC")
def evaluate(v):
    name, gm, kw = v; w1 = W * gvec(gm); out = []
    for s_ in est:
        h0 = idx.searchsorted(s_); a, i1 = run2(w1, h0, len(idx), 0.10, **kw)
        if a != "pass": out.append((s_, a, None)); continue
        b, i2 = run2(W, h0 + i1 + 1, len(idx), 0.05); out.append((s_, b, (i1 + i2) / 24 if b == "pass" else None))
    return name, out
V2 = [("flat x1.0", {}, {})] + [(f"flat x{m}", {}, dict(mlo=m)) for m in (1.1, 1.15, 1.2, 1.25)]
V2 += [(f"flat x{m}, daily guard 60%", {}, dict(mlo=m, halt=0.6)) for m in (1.25, 1.5)]
import itertools
for c, g, n, d in itertools.product([1, 1.5], [1, 1.5], [1, 1.5], [1, 1.5]):
    if (c, g, n, d) != (1, 1, 1, 1): V2.append((f"boost crypto{c} gold{g} nqday{n} dips{d}", dict(crypto=c, gold=g, nqday=n, dips=d), {}))
V2 += [(f"house money: x{mh} once up {int(u*100)}%", {}, dict(mhi=mh, up=u)) for mh in (1.5, 2.0) for u in (0.03, 0.05)]
V2 += [("x1.5, brake to x1.0 at -2%", {}, dict(mlo=1.5, brake_at=0.02, brake_m=1.0)), ("x1.5, brake to x0.75 at -3%", {}, dict(mlo=1.5, brake_at=0.03, brake_m=0.75)),
       ("x1.25, brake to x0.75 at -2%", {}, dict(mlo=1.25, brake_at=0.02, brake_m=0.75))]
with Pool(3) as p: res = p.map(evaluate, V2)
rows = []
for name, out in res:
    for part, sel in (("train", lambda s: s < split), ("test", lambda s: s >= split)):
        o = [x for x in out if sel(x[0])]; t = np.array([x[2] for x in o if x[2] is not None])
        rows.append(dict(variant=name, part=part, n=len(o), pass_=100 * np.mean([x[1] == "pass" for x in o]), breach=100 * np.mean([x[1] == "fail" for x in o]),
                         halted=100 * np.mean([x[1] == "stopped" for x in o]), median_d=np.median(t) if len(t) else np.nan, le60=100 * np.sum(t <= 60) / len(o), le90=100 * np.sum(t <= 90) / len(o)))
df = pd.DataFrame(rows); df.to_pickle(SP + "/speed8.pkl")
pv = df.pivot_table(index="variant", columns="part", values=["pass_", "breach", "median_d", "le90"]).round(0)
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 100)
pv.columns = [f"{a}_{b}" for a, b in pv.columns]
print(pv.sort_values("median_d_train").to_string())
