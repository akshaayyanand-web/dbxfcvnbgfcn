# Full journey with the corrected simulator: 16 EAs at risk x0.75 -> FTMO evaluation -> funded 200K, all profit withdrawn every 14 days, 1 year.
import os, numpy as np, pandas as pd
exec(open("sim_fixed.py").read().split('if __name__ == "__main__":')[0])
def journey(h0, m=0.75, Z=0.07):
    p1, i1, _ = core(h0, m, Z, target=0.10)
    if p1 != "pass": return dict(start=idx[h0], eval=p1, eval_days=None)
    p2, i2, _ = core(i1 + 1, m, Z, target=0.05)
    if p2 != "pass": return dict(start=idx[h0], eval=p2 + " (phase 2)", eval_days=None)
    f0 = min(i2 + 48, len(EQ_R) - 1)
    out, iend, pays = core(f0, m, Z, days=365, every=14)
    return dict(start=idx[h0], eval="passed", eval_days=round((i2 - h0) / 24), funded_from=idx[f0], funded=out, funded_end=idx[iend],
                payouts=len(pays), withdrawn=200000 * sum(p for _, p in pays), biggest=200000 * max([p for _, p in pays], default=0), pays=pays)
if __name__ == "__main__":
    starts = pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")
    with Pool(os.cpu_count()) as p: J = p.map(journey, [idx.searchsorted(s) for s in starts])
    d = pd.DataFrame(J); pd.to_pickle(d, "journey2.pkl")
    ok = d[d["eval"] == "passed"]; full = ok[(ok.funded_end - ok.funded_from) >= pd.Timedelta(days=360)]
    print(f"journeys {len(d)} | evaluation: {d['eval'].value_counts().to_dict()}")
    print(f"days to pass both phases: median {ok.eval_days.median():.0f}, 25% {ok.eval_days.quantile(.25):.0f}, 75% {ok.eval_days.quantile(.75):.0f}, 90% {ok.eval_days.quantile(.9):.0f}")
    print(f"funded year: {ok.funded.value_counts().to_dict()}  (full-year runs: {len(full)})")
    print(f"withdrawn in the funded year (before split), full-year runs: median ${full.withdrawn.median():,.0f}, 25% ${full.withdrawn.quantile(.25):,.0f}, 75% ${full.withdrawn.quantile(.75):,.0f}, worst ${full.withdrawn.min():,.0f}, best ${full.withdrawn.max():,.0f}")
    print(f"biggest single 2-week payout seen: ${ok.biggest.max():,.0f}; payouts per year median {full.payouts.median():.0f} of 26")
    for when in ("2021-01-04", "2022-06-06", "2023-01-02", "2024-06-03", "2025-01-06"):
        r = d.iloc[(d.start - pd.Timestamp(when, tz="UTC")).abs().argmin()]
        if r["eval"] != "passed": print(f"\nEXAMPLE start {r.start.date()}: evaluation {r['eval']}"); continue
        q = pd.Series([v * 200000 for _, v in r.pays], index=[t for t, _ in r.pays]).resample("QE").sum() if r.pays else pd.Series(dtype=float)
        print(f"\nEXAMPLE start {r.start.date()}: passed in {r.eval_days:.0f} days; funded {r.funded_from.date()} -> {r.funded_end.date()} ({r.funded}); {r.payouts:.0f} payouts, ${r.withdrawn:,.0f}")
        print("   by quarter:", {f"{t.year}Q{(t.month-1)//3+1}": int(round(v)) for t, v in q.items()})
