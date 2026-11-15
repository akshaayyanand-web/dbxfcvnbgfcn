src = open("y2026.py").read(); exec(src[:src.index("\nif __name__")])
END = 0
def f(h0):
    build(W(FTMO_EVAL)); p, i, _, _ = acct(h0, target=0.10, DL=0.05, G=0.04)
    if p != "pass": return None
    p, i2, _, _ = acct(i + 1, target=0.05, DL=0.05, G=0.04)
    if p != "pass": return None
    build(W(FTMO_FUND)); o, j, v, pays = acct(i2 + 48, days=365, DL=0.05, G=0.04, flimit=9)
    return (i2 - h0) / 24, o, 0.8 * 200000 * sum(pays)
if __name__ == "__main__":
    st = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    with Pool(os.cpu_count()) as p: R = [r for r in p.map(f, st) if r]
    d = pd.DataFrame(R, columns=["days", "o", "you"]); print(len(st), len(d), d.days.median(), d.o.value_counts().to_dict(), d.you.median(), d.you.quantile(.25))
