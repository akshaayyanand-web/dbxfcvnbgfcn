import os, itertools, numpy as np, pandas as pd
exec(open("sim_fixed.py").read().split('if __name__ == "__main__":')[0])
def ev(cfg):
    m1, m2, Z, G, half = cfg
    res = []
    for s in pd.date_range("2020-09-01", "2026-05-01", freq="3D", tz="UTC"):
        if s.weekday() >= 5: continue
        h0 = idx.searchsorted(s)
        p1, i1, _ = core(h0, m1, Z, target=0.10, G=G, half=half)
        if p1 != "pass": res.append((p1, None, s)); continue
        p2, i2, _ = core(i1 + 1, m2, Z, target=0.05, G=G, half=half)
        res.append((p2, (i2 - h0) / 24 if p2 == "pass" else None, s))
    d = pd.DataFrame(res, columns=["out", "days", "s"]); d = d[d.out != "open"]
    t = d.days.dropna()
    return dict(p1=m1, p2=m2, room=Z, guard=G, half=str(half), n=len(d), pass_pct=round(100 * (d.out == "pass").mean(), 1),
                breach_pct=round(100 * (d.out == "breach").mean(), 1), stopped_pct=round(100 * (d.out == "stopped").mean(), 1),
                med_days=round(t.median()), p25=round(t.quantile(.25)), p75=round(t.quantile(.75)), p90=round(t.quantile(.9)), within30=round(100 * (d.days <= 30).mean(), 1))
cfgs = [(m1, m2, Z, G, half) for m1 in (1.5, 2.0, 2.5, 3.0, 4.0) for m2 in (m1, 1.0) for Z in (0.07, 0.12) for G in (0.04,) for half in ((0.04, 0.02), (0.03, 0.01))]
with Pool(os.cpu_count()) as p: rows = p.map(ev, cfgs)
df = pd.DataFrame(rows); df.to_pickle("speed_grid.pkl")
pd.set_option("display.width", 300); pd.set_option("display.max_rows", 100)
print(df.sort_values(["pass_pct", "med_days"], ascending=[False, True]).to_string(index=False))
