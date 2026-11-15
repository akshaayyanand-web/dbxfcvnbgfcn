import os, numpy as np, pandas as pd
exec(open("frontier.py").read().split("def ev(args)")[0].split("for nm, w in PORTS.items()")[0])
BASE = {"btc": .75, "gdip": .625, "nq2h": .3125, "spx1h": .3125, "oil1h": .1875, "gasia": .3125, "gmom": .3125, "orb15": .625, "nqbo15": .2, "daxorb": .2,
        "spxbo5": .1, "btcgap": .25, "sol": .3, "goldvwap": .2, "spxfade": .25, "nikkei": .1, "solrev": .2, "btcrev": .2, "daxpm": .2}
def capped(w, scale, cap):
    return {c: min(w[c] * scale, cap / BASE[c]) for c in w}
EQ19 = eqrisk(NAMES)
def ev(args):
    scale, cap, Z = args; ww = capped(EQ19, scale, cap); build(ww)
    out = dict(scale=scale, max_risk_per_trade=cap, room=Z, biggest=max((round(ww[c] * BASE[c], 2), c) for c in ww))
    for lab, a, z in (("2020-22", "2020-09-01", "2022-12-31"), ("2023-26", "2023-01-01", "2026-05-01")):
        res = []
        for s in pd.date_range(a, z, freq="3D", tz="UTC"):
            if s.weekday() >= 5: continue
            h0 = idx.searchsorted(s); p1, i1, _ = core(h0, 1.0, Z, target=0.10, half=(0.03, 0.01))
            if p1 != "pass": res.append((p1, None)); continue
            p2, i2, _ = core(i1 + 1, 1.0, Z, target=0.05, half=(0.03, 0.01)); res.append((p2, (i2 - h0) / 24 if p2 == "pass" else None))
        d = pd.DataFrame(res, columns=["o", "d"]); d = d[d.o != "open"]; t = d.d.dropna()
        out[f"pass {lab}"] = round(100 * (d.o == "pass").mean(), 1); out[f"breach {lab}"] = round(100 * (d.o == "breach").mean(), 1)
        out[f"med {lab}"] = round(t.median()); out[f"<=30d {lab}"] = round(100 * (d.d <= 30).mean())
    return out
if __name__ == "__main__":
    jobs = [(sc, cap, 0.07) for cap in (0.75, 1.0) for sc in (3.0, 3.5, 4.0, 5.0, 6.0)]
    with Pool(os.cpu_count()) as p: rows = p.map(ev, jobs)
    pd.set_option("display.width", 260); print(pd.DataFrame(rows).to_string(index=False))
