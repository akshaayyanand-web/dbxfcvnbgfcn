import sys
src = open("bootcamp.py").read().split('\nif __name__ == "__main__":')[0]
src = src.replace('"B": ["btc"', '"C": ["btc", "sol", "btcrev", "solrev", "xrprev", "btcgap", "gdip", "goldvwap", "gasia", "gmom"],\n        "D": ["nq2h", "spx1h", "oil1h", "orb15", "nqbo15", "daxorb", "spxbo5", "spxfade", "nikkei", "daxpm", "nqfade"],\n        "B": ["btc"')
exec(src)
if __name__ == "__main__":
    st = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    cfgs = [(pk, Xe, Xf, 1.0) for pk in ("21", "B", "C", "D") for Xe in (2.0, 3.0, 4.0) for Xf in (1.5, 2.0)]
    rows = []; keep = {}
    for c in cfgs:
        with Pool(os.cpu_count()) as p: D = pd.DataFrame(p.map(run, [c + (h,) for h in st]))
        keep[c] = D; F = D[D.status.isin(["kept", "breached"])]
        rows.append(dict(pack=c[0], eval_x=c[1], pro_x=c[2], median_days=D.days.median(), p75_days=D.days.quantile(.75), within_60d=round(100 * (D.days <= 60).mean()),
                         first_try=round(100 * (D.tries == 1).mean()), avg_fees=round(22 * D.tries.mean() + 50), pro_kept=round(100 * (F.status == "kept").mean()),
                         paid_median=round(F.paid.median()), paid_p10=round(F.paid.quantile(.1)), paid_p90=round(F.paid.quantile(.9)), median_top=f"${F.top.median():,.0f}"))
        print(rows[-1], flush=True)
    R = pd.DataFrame(rows); pd.set_option("display.width", 250); print("\nGRID:"); print(R.to_string(index=False)); pd.to_pickle(keep, "bootcamp2_runs.pkl")
    # two accounts started the same week: C and D side by side vs the single 21-EA account (same start dates, eval 3x / pro 1.5x)
    for xe, xf in ((3.0, 1.5), (4.0, 1.5), (3.0, 2.0)):
        a, b, s = keep[("C", xe, xf, 1.0)], keep[("D", xe, xf, 1.0)], keep[("21", xe, xf, 1.0)]
        ok = a.status.isin(["kept", "breached"]) & b.status.isin(["kept", "breached"]) & s.status.isin(["kept", "breached"])
        tot = a.paid[ok] + b.paid[ok]
        print(f"\nTWO ACCOUNTS C+D (eval {xe}x, pro {xf}x): median combined paid ${tot.median():,.0f}, p10 ${tot.quantile(.1):,.0f}, p90 ${tot.quantile(.9):,.0f}; "
              f"both pro kept {100*((a.status[ok]=='kept')&(b.status[ok]=='kept')).mean():.0f}%; corr of paid {np.corrcoef(a.paid[ok], b.paid[ok])[0,1]:.2f} | "
              f"ONE 21-EA account same starts: median ${s.paid[ok].median():,.0f}, p10 ${s.paid[ok].quantile(.1):,.0f}; fees C+D ${22*(a.tries+b.tries).mean()+100:.0f}")
        print(f"   days until BOTH funded: median {np.maximum(a.days, b.days).median():.0f} vs 21-EA {s.days.median():.0f}")
