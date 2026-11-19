# "Fast pass" mode for FTMO 2-Step: higher eval risk, restart a fresh challenge after any failure; measure days until funded and attempts used.
import sys
exec(open("combo10.py").read().split('if __name__ == "__main__":')[0])
def until_funded(a):
    h0, es, names = a; t = h0; tries = 0
    while t < len(idx) - 24 * 200:
        tries += 1
        p, d1, i1, _ = acct(t, es, names, target=0.10)
        if p == "pass":
            p, d2, i2, _ = acct(i1 + 1, es, names, target=0.05)
            if p == "pass": return ((i2 - h0) / 24, tries)
            t = i2 + 24
        else: t = i1 + 24
        if tries > 20: break
    return (None, tries)
if __name__ == "__main__":
    base = list(NAMES); st = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    for es in (4.0, 5.0, 6.0, 8.0, 10.0):
        with Pool(os.cpu_count()) as p: d = pd.DataFrame(p.map(until_funded, [(h, es, base) for h in st]), columns=["days", "tries"])
        first = (d.tries == 1).mean()
        print(dict(eval_x=es, first_try_pass=round(100 * first), median_days_to_funded=d.days.median(), p25=d.days.quantile(.25), p75=d.days.quantile(.75),
                   within_30d=round(100 * (d.days <= 30).mean()), within_45d=round(100 * (d.days <= 45).mean()), avg_attempts=round(d.tries.mean(), 2), max_attempts=int(d.tries.max())), flush=True)
