# The Concept Trading Empire 1-Step: eval +10%, 10% static, no daily limit. Funded: each level target +10%.
# Lock path: first +10% pays 50%, then lock size -> 90% split, weekly payouts. Scaling path: each +10% pays 50%, size x1.5, fresh 10% floor.
exec(open("firms.py").read().split('\nif __name__ == "__main__":')[0])
def lock_path(a):
    h0, fs = a; d, tries, i = uf((h0, 6.0, "The Concept Empire 1-Step"))
    if i is None or tries > 1: return (None, 0.0, 0.0)
    end = i + 48 + 365 * 24
    p, dd, j, _ = acct(i + 48, fs, list(NAMES), target=0.10, DL=1.0, ML=0.10, G=0.08)
    if p != "pass" or j >= end: return ("no first target" if p != "breached" else "breached", 0.0, 0.0)
    first = 0.5 * 0.10
    o, _, _, pays = acct(j + 1, fs, list(NAMES), days=(end - j - 1) // 24, DL=1.0, ML=0.10, G=0.08, buf=0.02, every=7)
    return (o, first + 0.9 * sum(pays), (j - i - 48) / 24)
def scale_path(a):
    h0, fs = a; d, tries, i = uf((h0, 6.0, "The Concept Empire 1-Step"))
    if i is None or tries > 1: return (None, 0.0, 0)
    t = i + 48; end = t + 365 * 24; size = 1.0; paid = 0.0; lv = 0
    while t < end:
        p, dd, j, _ = acct(t, fs, list(NAMES), target=0.10, DL=1.0, ML=0.10, G=0.08)
        if p != "pass" or j >= end: return ("breached" if p == "breached" else "kept", paid, lv)
        paid += 0.5 * 0.10 * size; size *= 1.5; lv += 1; t = j + 1
    return ("kept", paid, lv)
if __name__ == "__main__":
    st = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    for fs in (3.0, 4.0):
        with Pool(os.cpu_count()) as p: d = pd.DataFrame(p.map(lock_path, [(h, fs) for h in st]), columns=["o", "paid", "days_first"])
        ok = d[d.o.notna()]
        print(dict(path="LOCK (50% on first +10%, then 90% weekly)", funded_x=fs, kept=round(100 * (ok.o == "kept").mean()), first_target_median_days=ok.days_first.median(),
                   yr_paid_pct_of_10k_median=round(100 * ok.paid.median(), 1), p10=round(100 * ok.paid.quantile(.1), 1)), flush=True)
        with Pool(os.cpu_count()) as p: d = pd.DataFrame(p.map(scale_path, [(h, fs) for h in st]), columns=["o", "paid", "levels"])
        ok = d[d.o.notna()]
        print(dict(path="SCALE (50% each +10%, size x1.5 per level)", funded_x=fs, ended_breached=round(100 * (ok.o == "breached").mean()), levels_per_yr_median=ok.levels.median(),
                   yr_paid_pct_of_10k_median=round(100 * ok.paid.median(), 1), p10=round(100 * ok.paid.quantile(.1), 1)), flush=True)
