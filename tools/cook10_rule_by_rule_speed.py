# Which rule makes passing quicker? Start from FTMO 2-Step and change ONE rule at a time (then combinations). Eval only, restart after failures.
exec(open("fast10.py").read().split('\nif __name__ == "__main__":')[0])
def uf(a):
    h0, es, tg, DL, ML, G = a; t = h0; tries = 0
    while t < len(idx) - 24 * 200 and tries < 20:
        tries += 1; ok = True; i = t
        for k, target in enumerate(tg):
            p, d, i, _ = acct(i if k == 0 else i + 1, es, list(NAMES), target=target, DL=DL, ML=ML, G=G)
            if p != "pass": ok = False; break
        if ok: return ((i - h0) / 24, tries)
        t = i + 24
    return (None, tries)
CFG = [("FTMO 2-Step (10%+5%, 5% daily, 10% static)", (0.10, 0.05), 0.05, 0.10, 0.04),
       ("  change: NO daily limit", (0.10, 0.05), 1.0, 0.10, 0.08),
       ("  change: 12% max loss", (0.10, 0.05), 0.05, 0.12, 0.04),
       ("  change: one phase, 15% target", (0.15,), 0.05, 0.10, 0.04),
       ("  change: one phase, 10% target", (0.10,), 0.05, 0.10, 0.04),
       ("  change: lower targets 8%+5%", (0.08, 0.05), 0.05, 0.10, 0.04),
       ("No daily limit + 12% max loss (2-Step 10%+5%)", (0.10, 0.05), 1.0, 0.12, 0.08),
       ("Pipcy 2-Step (12%+6%, no daily, 12%)", (0.12, 0.06), 1.0, 0.12, 0.08),
       ("Pipcy 1-Step (18%, no daily, 12%)", (0.18,), 1.0, 0.12, 0.08),
       ("Dream: 1-Step 10%, no daily, 12%", (0.10,), 1.0, 0.12, 0.08)]
if __name__ == "__main__":
    st = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    for lab, tg, DL, ML, G in CFG:
        best = None
        for es in (5.0, 6.0, 8.0):
            with Pool(os.cpu_count()) as p: d = pd.DataFrame(p.map(uf, [(h, es, tg, DL, ML, G) for h in st]), columns=["days", "tries"])
            r = dict(rules=lab, eval_x=es, first_try=round(100 * (d.tries == 1).mean()), median_days=d.days.median(), within_30d=round(100 * (d.days <= 30).mean()), p75=d.days.quantile(.75))
            if r["first_try"] >= 90 and (best is None or r["median_days"] < best["median_days"]): best = r
        print(best, flush=True)
