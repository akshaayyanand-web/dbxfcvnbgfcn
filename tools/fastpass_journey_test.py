import os, numpy as np, pandas as pd
exec(open("final_weights.py").read().split("tab = {")[0])
WE = {c: min(EQ19[c] * 4.0, 0.75 / BASE[c]) for c in EQ19}
WF = {sc: {c: min(EQ19[c] * sc, 0.75 / BASE[c]) for c in EQ19} for sc in (1.5, 2.0, 2.5)}
def journey(args):
    h0, sc = args
    build(WE); p1, i1, _ = core(h0, 1.0, 0.07, target=0.10, half=(0.03, 0.01))
    if p1 != "pass": return dict(eval=p1)
    p2, i2, _ = core(i1 + 1, 1.0, 0.07, target=0.05, half=(0.03, 0.01))
    if p2 != "pass": return dict(eval=p2)
    build(WF[sc]); f0 = min(i2 + 48, len(EQ_R) - 1)
    out, iend, pays = core(f0, 1.0, 0.07, days=365, every=14)
    return dict(eval="passed", days=(i2 - h0) / 24, funded_scale=sc, funded=out, full=(idx[iend] - idx[f0]).days >= 360, withdrawn=200000 * sum(p for _, p in pays))
if __name__ == "__main__":
    starts = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    with Pool(os.cpu_count()) as p: J = p.map(journey, [(h, sc) for sc in (1.5, 2.0, 2.5) for h in starts])
    d = pd.DataFrame(J); ok = d[d["eval"] == "passed"]
    print("evaluations:", d.drop_duplicates(subset=None)["eval"].value_counts().to_dict() if False else (d[d.funded_scale == 1.5]["eval"].value_counts().to_dict()))
    e = ok[ok.funded_scale == 1.5].days; print(f"days to pass: median {e.median():.0f}, 25% {e.quantile(.25):.0f}, 75% {e.quantile(.75):.0f}, 90% {e.quantile(.9):.0f}, within 30 days {100*(e<=30).mean():.0f}%")
    for sc in (1.5, 2.0, 2.5):
        g = ok[(ok.funded_scale == sc)]; f = g[g.full]
        print(f"funded scale {sc}: kept {100*(g.funded=='kept').mean():.1f}%, withdrawn per year median ${f.withdrawn.median():,.0f} (25% ${f.withdrawn.quantile(.25):,.0f}, worst ${f.withdrawn.min():,.0f})")
