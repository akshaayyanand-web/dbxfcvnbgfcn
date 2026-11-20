# Pipcy Classic (per third-party reviews): 2-Step 12%/6%, 1-Step 18%; 12% static max loss; NO daily loss limit; no time limit.
# Funded assumed: 12% static max loss, no daily limit, 80% split, payouts every 14 days (buffer 2%), no consistency rule.
exec(open("fast10.py").read().split('\nif __name__ == "__main__":')[0])
ML = 0.12
def until_funded_p(a):
    h0, es, kind, G = a; t = h0; tries = 0; names = list(NAMES)
    tg = (0.12, 0.06) if kind == "2-Step" else (0.18,)
    while t < len(idx) - 24 * 200 and tries < 20:
        tries += 1; ok = True; i = t
        for k, target in enumerate(tg):
            p, d, i, _ = acct(i if k == 0 else i + 1, es, names, target=target, DL=1.0, ML=ML, G=G)
            if p != "pass": ok = False; break
        if ok: return ((i - h0) / 24, tries, i)
        t = i + 24
    return (None, tries, None)
def funded_p(a):
    h0, es, fs, kind, G = a; d, tries, i = until_funded_p((h0, es, kind, G))
    if i is None or tries > 1: return (d, tries, None, 0.0)
    o, _, _, pays = acct(i + 48, fs, list(NAMES), days=365, DL=1.0, ML=ML, G=G, buf=0.02)
    return (d, tries, o, 0.8 * sum(pays))
if __name__ == "__main__":
    st = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    for kind in ("2-Step", "1-Step"):
        for G in (0.04, 0.99):
            for es in (4.0, 6.0, 8.0):
                with Pool(os.cpu_count()) as p: dd = pd.DataFrame(p.map(until_funded_p, [(h, es, kind, G) for h in st]), columns=["days", "tries", "i"])
                print(dict(firm="Pipcy " + kind, ea_daily_stop="4%" if G < 0.5 else "off", eval_x=es, first_try=round(100 * (dd.tries == 1).mean()), median_days=dd.days.median(),
                           p75=dd.days.quantile(.75), within_30d=round(100 * (dd.days <= 30).mean()), within_45d=round(100 * (dd.days <= 45).mean()), avg_attempts=round(dd.tries.mean(), 2)), flush=True)
    for G in (0.04, 0.99):
        for fs in (3.0, 4.0, 5.0):
            with Pool(os.cpu_count()) as p: dd = pd.DataFrame(p.map(funded_p, [(h, 6.0, fs, "2-Step", G) for h in st]), columns=["days", "tries", "o", "pct"])
            ok = dd[dd.o.notna()]
            print(dict(firm="Pipcy 2-Step funded", ea_daily_stop="4%" if G < 0.5 else "off", funded_x=fs, kept=round(100 * (ok.o == "kept").mean()), yr_median=round(100 * ok.pct.median(), 1),
                       yr_p10=round(100 * ok.pct.quantile(.1), 1), yr_p25=round(100 * ok.pct.quantile(.25), 1)), flush=True)
