exec(open("combo10.py").read().split('\nif __name__ == "__main__":')[0])
LONGONLY = {"btc", "gdip", "nq2h", "spx1h", "oil1h", "sol"}
for lab, nm in (("full 21", list(NAMES)), ("lean 15", [c for c in NAMES if c not in LONGONLY])):
    for sc in (1.0, 3.0):
        build({c: (min(PORT["21"][c] * sc, 1.0 / BASE[c]) if c in nm else 0.0) for c in NAMES})
        d = pd.Series(EQ_R, idx).groupby(idx.year).sum()
        print(lab, f"x{sc}", "return by year %:", (100 * d).round(1).to_dict(), flush=True)
