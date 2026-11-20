# Staggered challenges: start one new challenge every 7 days (N in parallel). Time from the first purchase to the FIRST funded account.
exec(open("fast10.py").read().split('\nif __name__ == "__main__":')[0])
def one(a):
    h0, es = a; p, d1, i1, _ = acct(h0, es, list(NAMES), target=0.10)
    if p != "pass": return np.nan
    p, d2, i2, _ = acct(i1 + 1, es, list(NAMES), target=0.05)
    return (i2 - h0) / 24 if p == "pass" else np.nan
if __name__ == "__main__":
    days = pd.date_range("2020-09-01", "2025-07-30", freq="7D", tz="UTC"); st = [idx.searchsorted(s) for s in days]
    for es in (4.0, 5.0):
        with Pool(os.cpu_count()) as p: D = np.array(p.map(one, [(h, es) for h in st]))
        rows = []
        for n in (1, 2, 3, 4):
            first = []; npass = []
            for k in range(len(D) - n):
                c = [7 * j + D[k + j] for j in range(n) if np.isfinite(D[k + j])]
                first.append(min(c) if c else np.nan); npass.append(sum(np.isfinite(D[k + j]) for j in range(n)))
            f = np.array(first)
            rows.append(dict(eval_x=es, challenges_staggered_weekly=n, median_days_to_first_funded=np.nanmedian(f), within_30d=round(100 * np.mean(f <= 30)),
                             within_45d=round(100 * np.mean(f <= 45)), p75=np.nanpercentile(f, 75), avg_accounts_passing=round(np.mean(npass), 2)))
        print(pd.DataFrame(rows).to_string(index=False), flush=True)
