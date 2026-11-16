src = open("y2026.py").read(); exec(src[:src.index("\nif __name__")])
code = open("fs_funded2.py").read(); code = code[code.index("def acct("):code.index("def weights(")]
code = code.replace("pdays >= 3:", "pdays >= NQ:").replace(">= 0.005;", ">= QT;")
QT, NQ = 0.008, 5; exec(code)
def job(a):
    h0, two = a
    build(W(FTMO_EVAL))
    if two:
        p, i, _, _ = acct(h0, target=0.08, DL=0.05, G=0.04)
        if p == "pass": p, i, _, _ = acct(i + 1, target=0.05, DL=0.05, G=0.04)
    else:
        p, i, _, _ = acct(h0, target=0.10, DL=0.04, G=0.03)
    if p != "pass": return (p, None, 0)
    build(W(FTMO_FUND)); o, j, v, pays = acct(i + 48, days=365, DL=0.05 if two else 0.04, G=0.04 if two else 0.03, flimit=9)
    return (o, (i - h0) / 24, 0.8 * 200000 * sum(pays))
if __name__ == "__main__":
    st = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    for two, name in ((True, "2-Step (8% + 5%, 5% daily, 10% static)"), (False, "1-Step (10%, 4% daily, 10% static)")):
        with Pool(os.cpu_count()) as p: d = pd.DataFrame(p.map(job, [(h, two) for h in st]), columns=["o", "days", "you"])
        ok = d[d.days.notna()]
        print(name, "| passed", round(100 * len(ok) / len(d), 1), "% | median days", ok.days.median(), "| 90%", ok.days.quantile(.9), "| funded", ok.o.value_counts().to_dict(), "| to you/yr (80%)", round(ok.you.median()))
