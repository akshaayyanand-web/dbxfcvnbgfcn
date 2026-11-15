# Full journey, corrected simulator: evaluation in Pass Mode (x1.5, room 9), funded at x1.0 (room 7), all profit withdrawn every 14 days.
import os, numpy as np, pandas as pd
exec(open("sim_fixed.py").read().split('if __name__ == "__main__":')[0])
def journey(h0, me=1.5, Ze=0.09, mf=1.0, Zf=0.07):
    p1, i1, _ = core(h0, me, Ze, target=0.10)
    if p1 != "pass": return dict(start=idx[h0], eval=p1, eval_days=None)
    p2, i2, _ = core(i1 + 1, me, Ze, target=0.05)
    if p2 != "pass": return dict(start=idx[h0], eval=p2 + " (phase 2)", eval_days=None)
    f0 = min(i2 + 48, len(EQ_R) - 1)
    out, iend, pays = core(f0, mf, Zf, days=365, every=14)
    return dict(start=idx[h0], eval="passed", eval_days=round((i2 - h0) / 24), funded_from=idx[f0], funded=out, funded_end=idx[iend],
                payouts=len(pays), withdrawn=200000 * sum(p for _, p in pays), biggest=200000 * max([p for _, p in pays], default=0), pays=pays)
if __name__ == "__main__":
    starts = pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")
    with Pool(os.cpu_count()) as p: J = p.map(journey, [idx.searchsorted(s) for s in starts])
    d = pd.DataFrame(J); pd.to_pickle(d, "journey3.pkl")
    ok = d[d["eval"] == "passed"]; full = ok[(ok.funded_end - ok.funded_from) >= pd.Timedelta(days=360)]
    print(f"journeys {len(d)} | evaluation: {d['eval'].value_counts().to_dict()}")
    print(f"days to pass: median {ok.eval_days.median():.0f}, 25% {ok.eval_days.quantile(.25):.0f}, 75% {ok.eval_days.quantile(.75):.0f}, 90% {ok.eval_days.quantile(.9):.0f}")
    print(f"funded year: {ok.funded.value_counts().to_dict()}")
    print(f"withdrawn (before split), full-year runs: median ${full.withdrawn.median():,.0f}, 25% ${full.withdrawn.quantile(.25):,.0f}, 75% ${full.withdrawn.quantile(.75):,.0f}, worst ${full.withdrawn.min():,.0f}, best ${full.withdrawn.max():,.0f}; payouts/yr median {full.payouts.median():.0f}; biggest single ${ok.biggest.max():,.0f}")
    lost = ok[ok.funded != "kept"]
    if len(lost): print("lost accounts:", [(r.start.date(), r.funded, r.funded_end.date(), round(r.withdrawn)) for r in lost.itertuples()])
    for when in ("2021-01-04", "2022-06-06", "2023-01-02", "2024-06-03", "2025-01-06"):
        r = d.iloc[(d.start - pd.Timestamp(when, tz="UTC")).abs().argmin()]
        if r["eval"] != "passed": print(f"EXAMPLE {r.start.date()}: {r['eval']}"); continue
        print(f"EXAMPLE start {r.start.date()}: passed in {r.eval_days:.0f} days; funded {r.funded_from.date()} -> {r.funded_end.date()} ({r.funded}); {r.payouts:.0f} payouts, ${r.withdrawn:,.0f}")
