import numpy as np, pandas as pd
exec(open("wport.py").read().split('if __name__ == "__main__":')[0])
names = list(COMP)
day = pd.Series(idx.normalize(), index=idx)
D = pd.DataFrame({c: pd.Series(COMP[c][0], idx).groupby(idx.normalize()).sum() for c in names})
TR = D.loc["2020-09-01":"2022-12-31"]; TE = D.loc["2023-01-01":]
def stats(df, w):
    p = df.values @ np.array([w[c] for c in names]); eq = np.cumsum(p); dd = (eq - np.maximum.accumulate(eq)).min()
    ann = p.mean() * 252; vol = p.std() * np.sqrt(252)
    return ann, vol, dd, ann / vol, ann / max(-dd, 1e-9)
def score(w): ann, vol, dd, sh, cal = stats(TR, w); return 0.5 * sh + 0.5 * cal / 3     # blend of Sharpe and return/drawdown
w = {c: 1.0 for c in names}; best = score(w); grid = (0.0, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0)
for rnd in range(4):
    for c in names:
        for g in grid:
            t = dict(w); t[c] = g; s = score(t)
            if s > best + 1e-6: best, w = s, t
print("weights:", {c: w[c] for c in names})
for lab, df in (("train 2020-22", TR), ("test 2023-26", TE)):
    for nm, ww in (("current", {c: 1.0 for c in names}), ("optimised", w)):
        ann, vol, dd, sh, cal = stats(df, ww)
        print(f"{lab:14s} {nm:9s}: return {100*ann:5.1f}%/yr  vol {100*vol:4.1f}%  max DD {100*dd:5.1f}%  Sharpe {sh:4.2f}  return/DD {cal:4.2f}")
pd.to_pickle(w, "wopt_weights.pkl")
