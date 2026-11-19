# Eval structure scan: per-EA risk cap (1x vs 2x of the tested cap) and separate phase-2 risk; restart after failures.
import sys
src = open("combo10.py").read().split('if __name__ == "__main__":')[0]
src = src.replace("build({c: (min(PORT[\"21\"][c] * scale, 1.0 / BASE[c]) if c in names else 0.0) for c in NAMES})",
                  "build({c: (min(PORT[\"21\"][c] * scale, CAP / BASE[c]) if c in names else 0.0) for c in NAMES})")
assert "CAP / BASE" in src
CAP = 1.0
exec(src)
def until_funded(a):
    h0, e1, e2, cap, names = a; global CAP; CAP = cap; t = h0; tries = 0
    while t < len(idx) - 24 * 200 and tries < 20:
        tries += 1
        p, d1, i1, _ = acct(t, e1, names, target=0.10)
        if p == "pass":
            p, d2, i2, _ = acct(i1 + 1, e2, names, target=0.05)
            if p == "pass": return ((i2 - h0) / 24, tries)
            t = i2 + 24
        else: t = i1 + 24
    return (None, tries)
if __name__ == "__main__":
    base = list(NAMES); st = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    for e1, e2, cap in ((5, 5, 2.0), (5, 7, 1.0), (5, 7, 2.0), (6, 8, 2.0), (4, 6, 2.0)):
        with Pool(os.cpu_count()) as p: d = pd.DataFrame(p.map(until_funded, [(h, e1, e2, cap, base) for h in st]), columns=["days", "tries"])
        print(dict(phase1_x=e1, phase2_x=e2, per_ea_cap=cap, first_try=round(100 * (d.tries == 1).mean()), median_days=d.days.median(), p25=d.days.quantile(.25), p75=d.days.quantile(.75),
                   within_30d=round(100 * (d.days <= 30).mean()), within_45d=round(100 * (d.days <= 45).mean()), avg_attempts=round(d.tries.mean(), 2)), flush=True)
