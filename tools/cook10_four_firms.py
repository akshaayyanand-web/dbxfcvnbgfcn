# Four firm candidates on the rules as described by the user's research (unverified). Phases: (target, daily, maxloss, EA daily stop).
exec(open("fast10.py").read().split('\nif __name__ == "__main__":')[0])
FIRMS = {
 "Audacity Ability 2-Step": dict(phases=[(0.10, 0.075, 0.15, 0.065), (0.05, 0.05, 0.10, 0.04)], funded=(0.05, 0.10, 0.04), split=0.75, every=14),
 "The Concept Empire 1-Step": dict(phases=[(0.10, 1.0, 0.10, 0.08)], funded=(1.0, 0.10, 0.08), split=0.50, every=30),
 "FundingPips 1-Step Flex": dict(phases=[(0.12, 0.03, 0.12, 0.022)], funded=(0.03, 0.12, 0.022), split=0.80, every=14),
 "The5ers High Stakes 2-Step": dict(phases=[(0.08, 0.05, 0.10, 0.04), (0.05, 0.05, 0.10, 0.04)], funded=(0.05, 0.10, 0.04), split=0.80, every=14)}
def uf(a):
    h0, es, f = a; F = FIRMS[f]; t = h0; tries = 0
    while t < len(idx) - 24 * 200 and tries < 20:
        tries += 1; ok = True; i = t
        for k, (tg, DL, ML, G) in enumerate(F["phases"]):
            p, d, i, _ = acct(i if k == 0 else i + 1, es, list(NAMES), target=tg, DL=DL, ML=ML, G=G)
            if p != "pass": ok = False; break
        if ok: return ((i - h0) / 24, tries, i)
        t = i + 24
    return (None, tries, None)
def fund(a):
    h0, es, fs, f = a; F = FIRMS[f]; d, tries, i = uf((h0, es, f))
    if i is None or tries > 1: return (None, 0.0)
    DL, ML, G = F["funded"]; o, _, _, pays = acct(i + 48, fs, list(NAMES), days=365, DL=DL, ML=ML, G=G, buf=0.02, every=F["every"])
    return (o, F["split"] * sum(pays))
if __name__ == "__main__":
    st = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    for f in FIRMS:
        best = None
        for es in (4.0, 5.0, 6.0, 8.0):
            with Pool(os.cpu_count()) as p: d = pd.DataFrame(p.map(uf, [(h, es, f) for h in st]), columns=["days", "tries", "i"])
            r = dict(firm=f, eval_x=es, first_try=round(100 * (d.tries == 1).mean()), median_days=d.days.median(), within_30d=round(100 * (d.days <= 30).mean()), p75=d.days.quantile(.75))
            print("  eval", r, flush=True)
            if r["first_try"] >= 90 and (best is None or r["median_days"] < best["median_days"]): best = r
        print("BEST EVAL", best, flush=True)
        for fs in (2.0, 3.0, 3.5, 4.0):
            with Pool(os.cpu_count()) as p: d = pd.DataFrame(p.map(fund, [(h, best["eval_x"], fs, f) for h in st]), columns=["o", "pct"])
            ok = d[d.o.notna()]
            print("FUNDED", dict(firm=f, funded_x=fs, kept=round(100 * (ok.o == "kept").mean()), yr_median_to_you=round(100 * ok.pct.median(), 1), yr_p10=round(100 * ok.pct.quantile(.1), 1)), flush=True)
