exec(open("firms.py").read().split('\nif __name__ == "__main__":')[0])
LONGONLY = {"btc", "gdip", "nq2h", "spx1h", "oil1h", "sol"}
F = FIRMS["The5ers High Stakes 2-Step"]
def ufn(a):
    h0, es, names = a; t = h0; tries = 0
    while t < len(idx) - 24 * 200 and tries < 20:
        tries += 1; ok = True; i = t
        for k, (tg, DL, ML, G) in enumerate(F["phases"]):
            p, d, i, _ = acct(i if k == 0 else i + 1, es, names, target=tg, DL=DL, ML=ML, G=G)
            if p != "pass": ok = False; break
        if ok: return ((i - h0) / 24, tries, i)
        t = i + 24
    return (None, tries, None)
def fundn(a):
    h0, x, names = a; d, tries, i = ufn((h0, x, names))
    if i is None or tries > 1: return (None, 0.0)
    DL, ML, G = F["funded"]; o, _, _, pays = acct(i + 48, x, names, days=365, DL=DL, ML=ML, G=G, buf=0.02, every=14)
    return (o, F["split"] * sum(pays))
if __name__ == "__main__":
    lean = [c for c in NAMES if c not in LONGONLY]
    build({c: (PORT["21"][c] if c in lean else 0) for c in NAMES}); d_ = pd.Series(EQ_R, idx).groupby(idx.normalize()).sum(); d_ = d_[d_.index.weekday < 5]
    print("lean 15 EAs Sharpe 2020-22 / 2023-26:", round(d_[:"2022-12-31"].mean() / d_[:"2022-12-31"].std() * np.sqrt(252), 2), round(d_["2023-01-01":].mean() / d_["2023-01-01":].std() * np.sqrt(252), 2), "| %/yr x1:", round(100 * d_.sum() / 6.58, 1), flush=True)
    st = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    for x in (3.0, 4.0, 5.0, 6.0):
        with Pool(os.cpu_count()) as p: d = pd.DataFrame(p.map(ufn, [(h, x, lean) for h in st]), columns=["days", "tries", "i"])
        with Pool(os.cpu_count()) as p: g = pd.DataFrame(p.map(fundn, [(h, x, lean) for h in st]), columns=["o", "pct"])
        ok = g[g.o.notna()]
        print(dict(book="15 two-way EAs", same_risk_x=x, first_try=round(100 * (d.tries == 1).mean()), median_days=d.days.median(), p75=d.days.quantile(.75),
                   funded_kept=round(100 * (ok.o == "kept").mean()), yr_median=round(100 * ok.pct.median(), 1), yr_p10=round(100 * ok.pct.quantile(.1), 1)), flush=True)
