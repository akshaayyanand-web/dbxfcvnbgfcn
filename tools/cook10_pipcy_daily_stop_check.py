exec(open("pipcy.py").read().split('\nif __name__ == "__main__":')[0])
def f1(a):
    h0, es, fs, G = a; d, tries, i = until_funded_p((h0, es, "1-Step", G))
    if i is None or tries > 1: return (d, tries, None, 0.0, np.nan)
    o, _, _, pays = acct(i + 48, fs, list(NAMES), days=365, DL=1.0, ML=ML, G=G, buf=0.02)
    return (d, tries, o, 0.8 * sum(pays), np.nan)
if __name__ == "__main__":
    st = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    build({c: min(PORT["21"][c] * 6.0, 1.0 / BASE[c]) for c in NAMES}); dd_ = pd.Series(EQ_R, idx).groupby(idx.normalize()).sum()
    print("worst single days at 6x (no stops, %):", (100 * dd_.nsmallest(5)).round(1).tolist(), flush=True)
    for G in (0.06, 0.08, 0.99):
        for es, fs in ((6.0, 4.0), (8.0, 4.0), (6.0, 5.0)):
            with Pool(os.cpu_count()) as p: d = pd.DataFrame(p.map(f1, [(h, es, fs, G) for h in st]), columns=["days", "tries", "o", "pct", "x"])
            ok = d[d.o.notna()]
            print(dict(firm="Pipcy 1-Step", ea_daily_stop=("off" if G > 0.5 else f"{G:.0%}"), eval_x=es, funded_x=fs, first_try=round(100 * (d.tries == 1).mean()), median_days=d.days.median(),
                       within_30d=round(100 * (d.days <= 30).mean()), p75=d.days.quantile(.75), funded_kept=round(100 * (ok.o == "kept").mean()),
                       yr_median=round(100 * ok.pct.median(), 1), yr_p10=round(100 * ok.pct.quantile(.1), 1)), flush=True)
