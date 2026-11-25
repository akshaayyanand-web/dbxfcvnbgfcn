import sys
exec(open("firms.py").read().split('\nif __name__ == "__main__":')[0])
def hs(starts, tag):
    with Pool(os.cpu_count()) as p: d = pd.DataFrame(p.map(uf, [(h, 3.0, "The5ers High Stakes 2-Step") for h in starts]), columns=["days", "tries", "i"])
    with Pool(os.cpu_count()) as p: g = pd.DataFrame(p.map(fund, [(h, 3.0, 3.0, "The5ers High Stakes 2-Step") for h in starts]), columns=["o", "pct"])
    ok = g[g.o.notna()]; return dict(book=tag, median_days=d.days.median(), p75=d.days.quantile(.75), first_try=round(100 * (d.tries == 1).mean()), kept=round(100 * (ok.o == "kept").mean()),
                                    yr_median=round(100 * ok.pct.median(), 1), yr_p10=round(100 * ok.pct.quantile(.1), 1))
ALL = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
HOLD = [idx.searchsorted(s) for s in pd.date_range("2023-01-01", "2025-06-30", freq="7D", tz="UTC")]
if __name__ == "__main__":
    for lab, st in (("all starts", ALL), ("2023+ starts", HOLD)): print(lab, hs(st, "current"), flush=True)
    day = idx.normalize(); act = lambda c: pd.Series(np.abs(COMP[c][0]) + np.abs(COMP[c][1]), idx).groupby(day).transform("sum").to_numpy() > 0
    both = act("spxfade") & act("nqfade"); w = np.where(both, 0.5, 1.0); print("hours on shared fade days:", int(both.sum()))
    for c in ("spxfade", "nqfade"): COMP[c] = [COMP[c][0] * w, COMP[c][1] * w, COMP[c][2] * w]
    for lab, st in (("all starts", ALL), ("2023+ starts", HOLD)): print(lab, hs(st, "halve both fades on shared days"), flush=True)
