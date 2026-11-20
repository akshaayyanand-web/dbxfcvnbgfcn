# The5ers High Stakes with the SAME risk in evaluation and funded (no size change between stages).
exec(open("firms.py").read().split('\nif __name__ == "__main__":')[0])
f = "The5ers High Stakes 2-Step"
if __name__ == "__main__":
    st = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    for x in (3.0, 3.5, 4.0):
        with Pool(os.cpu_count()) as p: d = pd.DataFrame(p.map(uf, [(h, x, f) for h in st]), columns=["days", "tries", "i"])
        with Pool(os.cpu_count()) as p: g = pd.DataFrame(p.map(fund, [(h, x, x, f) for h in st]), columns=["o", "pct"])
        ok = g[g.o.notna()]
        print(dict(same_risk_x=x, first_try=round(100 * (d.tries == 1).mean()), median_days=d.days.median(), p75=d.days.quantile(.75), funded_kept=round(100 * (ok.o == "kept").mean()),
                   yr_median=round(100 * ok.pct.median(), 1), yr_p10=round(100 * ok.pct.quantile(.1), 1)), flush=True)
