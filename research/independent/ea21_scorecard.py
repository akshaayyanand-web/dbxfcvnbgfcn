src = open("y2026.py").read(); exec(src[:src.index("\nif __name__")])
import math, json, numpy as np, pandas as pd
from scipy.stats import skew, kurtosis, norm
TL = pd.read_pickle("dir_trades.pkl")
D = pd.DataFrame({c: pd.Series(COMP[c][0], idx).groupby(idx.tz_convert(None).normalize()).sum() for c in NAMES}).loc["2020-04-01":"2026-10-29"]
D = D[D.index.dayofweek < 5].add(D[D.index.dayofweek >= 5].reindex(D.index, fill_value=0) * 0, fill_value=0)
def sh(p): return float(p.mean() / p.std() * math.sqrt(252)) if p.std() > 0 else 0.0
def mdd(p): eq = (1 + p / p.std() * 0.10 / math.sqrt(252)).cumprod(); return float((eq / eq.cummax() - 1).min())
book = (D * pd.Series(PORT["21"])).sum(1); N_TR = 2673 + 500; zc = norm.ppf(1 - 0.05 / N_TR)
rows = []
for c in NAMES:
    p = D[c]; p = p[p.index >= p.ne(0).idxmax()]; s_ = sh(p) / math.sqrt(252); T = len(p); sk, ku = skew(p), kurtosis(p, fisher=False)
    z = s_ * math.sqrt(T - 1) / math.sqrt(max(1e-9, 1 - sk * s_ + (ku - 1) / 4 * s_ ** 2))
    t = np.array([x[3] for x in TL[c]]) if c in TL else np.array([])
    wo = (D.drop(columns=c) * pd.Series(PORT["21"]).drop(c)).sum(1)
    rows.append(dict(EA=c, sharpe_all=round(sh(p), 2), sh_2020_22=round(sh(p.loc[:"2022"]), 2), sh_2023_24=round(sh(p.loc["2023":"2024"]), 2), sh_2025_26=round(sh(p.loc["2025":]), 2),
                     maxdd_at_10vol=round(mdd(p), 3), psr_z=round(z, 2), bonferroni=bool(z > zc), trades=int(len(t)), win=round(float((t > 0).mean()), 2) if len(t) else None,
                     book_sharpe_drop_without=round(sh(book) - sh(wo), 3), corr_to_rest=round(float(p.corr(wo.reindex(p.index))), 2)))
E = pd.DataFrame(rows).sort_values("psr_z", ascending=False); E.to_csv("/home/user/dbxfcvnbgfcn/research/results/ea21_scorecard.csv", index=False)
print("Bonferroni z needed:", round(zc, 2), "| book Sharpe:", round(sh(book), 2)); print(E.to_string(index=False))
# out-of-sample check of pruning: pick EAs with positive marginal contribution using 2020-22 only, test 2023-26
W = pd.Series(PORT["21"]); trn, tst = D.loc[:"2022"], D.loc["2023":]
def bk(X, w): return (X[w.index] * w).sum(1)
keep = [c for c in NAMES if sh(bk(trn, W)) - sh(bk(trn.drop(columns=c), W.drop(c))) > 0]
print("\nkept by 2020-22 marginal contribution:", len(keep), sorted(keep)); print("dropped:", sorted(set(NAMES) - set(keep)))
for lab, X in (("2020-22 (selection)", trn), ("2023-26 (unseen)", tst)):
    print(f"{lab}: all 21 Sharpe {sh(bk(X, W)):.2f} | pruned {len(keep)} Sharpe {sh(bk(X, W[keep])):.2f}")
