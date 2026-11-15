import os, numpy as np, pandas as pd
exec(open("sim_fixed2.py").read())
def ev(cfg):
    m, Z, cap = cfg; res = []
    for s in pd.date_range("2020-09-01", "2026-05-01", freq="3D", tz="UTC"):
        if s.weekday() >= 5: continue
        h0 = idx.searchsorted(s)
        p1, i1, _ = core(h0, m, Z, target=0.10, half=(0.03, 0.01), cap=cap)
        if p1 != "pass": res.append((p1, None)); continue
        p2, i2, _ = core(i1 + 1, m, Z, target=0.05, half=(0.03, 0.01), cap=cap)
        res.append((p2, (i2 - h0) / 24 if p2 == "pass" else None))
    d = pd.DataFrame(res, columns=["out", "days"]); d = d[d.out != "open"]; t = d.days.dropna()
    return dict(risk=m, room=Z, grow_cap=cap, pass_pct=round(100 * (d.out == "pass").mean(), 1), breach=round(100 * (d.out == "breach").mean(), 1),
                med_days=round(t.median()), p75=round(t.quantile(.75)), p90=round(t.quantile(.9)), within30=round(100 * (d.days <= 30).mean(), 1), within45=round(100 * (d.days <= 45).mean(), 1))
cfgs = [(m, Z, cap) for m in (1.0, 1.5) for Z in (0.05, 0.07, 0.10) for cap in (1.0, 1.5, 2.0, 3.0)]
if __name__ == "__main__":
    with Pool(os.cpu_count()) as p: rows = p.map(ev, cfgs)
    pd.set_option("display.width", 250); print(pd.DataFrame(rows).sort_values(["pass_pct", "med_days"], ascending=[False, True]).to_string(index=False))
