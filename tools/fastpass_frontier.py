import os, numpy as np, pandas as pd
exec(open("wport2.py").read())
core16 = [c for c in NAMES if c not in ("solrev", "btcrev", "daxpm")]
PORTS = {"16 EAs (current)": {c: 1.0 for c in core16} | {"solrev": 0, "btcrev": 0, "daxpm": 0},
         "16 EAs, equal risk": eqrisk(core16) | {"solrev": 0, "btcrev": 0, "daxpm": 0},
         "19 EAs, equal risk": eqrisk(NAMES)}
def sharpe(w, a, z):
    p = DAILY.loc[a:z].values @ np.array([w[c] for c in NAMES]); return p.mean() / p.std() * np.sqrt(252), p.mean() * 252
for nm, w in PORTS.items():
    s1, r1 = sharpe(w, "2020-09-01", "2022-12-31"); s2, r2 = sharpe(w, "2023-01-01", "2026-12-31")
    print(f"{nm:20s}: Sharpe 2020-22 {s1:.2f} (ret {100*r1:.0f}%/yr)   Sharpe 2023-26 {s2:.2f} (ret {100*r2:.0f}%/yr)", flush=True)
def ev(args):
    nm, scale, Z = args; build({c: v * scale for c, v in PORTS[nm].items()})
    out = dict(portfolio=nm, risk_scale=scale, room=Z)
    for lab, a, z in (("2020-22", "2020-09-01", "2022-12-31"), ("2023-26", "2023-01-01", "2026-05-01")):
        res = []
        for s in pd.date_range(a, z, freq="3D", tz="UTC"):
            if s.weekday() >= 5: continue
            h0 = idx.searchsorted(s); p1, i1, _ = core(h0, 1.0, Z, target=0.10, half=(0.03, 0.01))
            if p1 != "pass": res.append((p1, None)); continue
            p2, i2, _ = core(i1 + 1, 1.0, Z, target=0.05, half=(0.03, 0.01)); res.append((p2, (i2 - h0) / 24 if p2 == "pass" else None))
        d = pd.DataFrame(res, columns=["o", "d"]); d = d[d.o != "open"]; t = d.d.dropna()
        out[f"pass {lab}"] = round(100 * (d.o == "pass").mean(), 1); out[f"med {lab}"] = round(t.median()); out[f"<=30d {lab}"] = round(100 * (d.d <= 30).mean())
    return out
if __name__ == "__main__":
    jobs = [(nm, sc, Z) for nm, scs in (("16 EAs (current)", (1.5, 2.0)), ("16 EAs, equal risk", (2.0, 2.5, 3.0)), ("19 EAs, equal risk", (2.0, 2.5, 3.0, 3.5))) for sc in scs for Z in (0.07, 0.10)]
    with Pool(os.cpu_count()) as p: rows = p.map(ev, jobs)
    pd.set_option("display.width", 250); print(pd.DataFrame(rows).to_string(index=False))
