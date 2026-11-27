import sys
exec(open("joat.py").read().split('\nif __name__ == "__main__":')[0])
K._cache[("NQ", "M5")] = K.rs(K.MK["NQ"][0](), "5min").pipe(lambda b: b[(b.h >= b.l) & (b.c > 0)])
src = open("joat.py").read(); fn = src[src.index("def run(job):"):src.index('\nif __name__ == "__main__":')].replace('(0.25 if tf == "M15" else 1.0)', '({"M5": 5 / 60, "M15": 0.25}.get(tf, 1.0))')
exec(fn)
if __name__ == "__main__":
    D = pd.DataFrame(run(("NQ", "M5"))); D = D[D.n > 0]; S = D.copy()
    pd.set_option("display.width", 230); print(S[["rule", "exit", "n", "win", "avgR_train", "t_train", "avgR_hold", "t_hold", "n_train", "n_hold"]].round(3).to_string(index=False))
    D.to_csv("joat_nq_m5.csv", index=False)
