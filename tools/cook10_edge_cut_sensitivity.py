# What if every EA earns X% less than the backtest? Shave each EA's average result per trade (same swings), then The5ers High Stakes at 3x.
exec(open("firms.py").read().split('\nif __name__ == "__main__":')[0])
ORIG = {c: [a.copy() for a in COMP[c]] for c in NAMES}
def apply_cut(f):
    for c in NAMES:
        R = ORIG[c][0].copy(); nz = R != 0
        if nz.any(): R[nz] -= f * R.sum() / nz.sum()
        COMP[c] = [R, np.minimum(ORIG[c][1], R) if f > 0 else ORIG[c][1].copy(), ORIG[c][2].copy()]
if __name__ == "__main__":
    st = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    for f in (0.0, 0.2, 0.5):
        apply_cut(f)
        build({c: PORT["21"][c] for c in NAMES}); dd = pd.Series(EQ_R, idx).groupby(idx.normalize()).sum().loc["2020-09-01":]
        with Pool(os.cpu_count()) as p: d = pd.DataFrame(p.map(uf, [(h, 3.0, "The5ers High Stakes 2-Step") for h in st]), columns=["days", "tries", "i"])
        with Pool(os.cpu_count()) as p: g = pd.DataFrame(p.map(fund, [(h, 3.0, 3.0, "The5ers High Stakes 2-Step") for h in st]), columns=["o", "pct"])
        ok = g[g.o.notna()]
        print(dict(edge=f"{100*(1-f):.0f}% of backtest", book_pct_yr_1x=round(100 * dd.sum() / 6.2, 1), first_try=round(100 * (d.tries == 1).mean()), median_days=d.days.median(),
                   funded_kept=round(100 * (ok.o == "kept").mean()), yr_median=round(100 * ok.pct.median(), 1), yr_p10=round(100 * ok.pct.quantile(.1), 1)), flush=True)
