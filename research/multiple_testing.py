"""Multiple-testing corrections over every market test (latest record per strategy x market):
- Deflated Sharpe Ratio (Bailey & Lopez de Prado 2014) vs the expected maximum Sharpe of N unskilled trials (N = market tests, and N = all grid trials).
- Benjamini-Hochberg false discovery rate on one-sided alpha p-values (q = 5% and 10%); Harvey-Liu-Zhu t > 3 hurdle.
- Probability of Backtest Overfitting (CSCV, Bailey et al. 2015) per family: chance that the in-sample-best formulation is below the median out of sample."""
import os, json, pickle, itertools, math, numpy as np, pandas as pd
from scipy.stats import norm, skew, kurtosis
from data import SCR
H = os.path.dirname(__file__); D = f"{SCR}/rdata/pnl"
recs = {}
for l in open(f"{H}/results/results.jsonl"):
    r = json.loads(l)
    if r.get("universe") != "BLOCKED": recs[(r["id"], r["universe"])] = r       # latest record wins
rows = []
for (sid, u), r in recs.items():
    f = f"{D}/{sid}@{u}.pkl"
    if not os.path.exists(f): continue
    p = pickle.load(open(f, "rb")).dropna(); p = p[p != 0] if (p == 0).mean() > 0.95 else p
    if len(p) < 60 or p.std() == 0: continue
    ann = 365 if u in ("crypto", "btc", "perp", "cashcarry", "qbasis") else 252
    rows.append(dict(id=sid, universe=u, name=r["name"], T=len(p), sr=p.mean() / p.std(), sr_ann=p.mean() / p.std() * math.sqrt(ann), skew=float(skew(p)), kurt=float(kurtosis(p, fisher=False)),
                     trials=r.get("trials", 1), alpha_t=r.get("alpha_t", 0) or 0, passed=r.get("passed", False)))
M = pd.DataFrame(rows)
def sr0(N, V):
    g = 0.5772156649; return math.sqrt(V) * ((1 - g) * norm.ppf(1 - 1 / N) + g * norm.ppf(1 - 1 / (N * math.e)))
V = float(M.sr.var()); N_tests = len(M); N_trials = int(M.trials.sum())
for lab, N in (("tests", N_tests), ("trials", N_trials)):
    s0 = sr0(N, V)
    M[f"dsr_{lab}"] = [float(norm.cdf((r.sr - s0) * math.sqrt(r.T - 1) / math.sqrt(max(1e-12, 1 - r.skew * r.sr + (r.kurt - 1) / 4 * r.sr ** 2)))) for r in M.itertuples()]
    M.attrs[f"sr0_{lab}"] = s0
M["p_one_sided"] = 1 - norm.cdf(M.alpha_t)
def bh(p, q):
    n = len(p); o = np.argsort(p); thr = q * np.arange(1, n + 1) / n; ok = p[o] <= thr; k = np.max(np.where(ok)[0]) + 1 if ok.any() else 0
    res = np.zeros(n, bool); res[o[:k]] = True; return res
M["fdr5"] = bh(M.p_one_sided.values, 0.05); M["fdr10"] = bh(M.p_one_sided.values, 0.10); M["hlz_t3"] = M.alpha_t >= 3.0
M["survives_all"] = M.passed & (M.dsr_tests > 0.95) & M.fdr5 & M.hlz_t3
# PBO by family (CSCV, S = 10 blocks)
def pbo(mat, S=10):
    T = len(mat); bl = np.array_split(np.arange(T), S); lam = []
    for comb in itertools.combinations(range(S), S // 2):
        IS = np.concatenate([bl[i] for i in comb]); OS = np.concatenate([bl[i] for i in range(S) if i not in comb])
        sr_is = mat[IS].mean(0) / (mat[IS].std(0) + 1e-12); sr_os = mat[OS].mean(0) / (mat[OS].std(0) + 1e-12)
        b = int(np.argmax(sr_is)); w = (np.argsort(np.argsort(sr_os))[b] + 1) / (mat.shape[1] + 1); lam.append(math.log(w / (1 - w)))
    return float(np.mean(np.array(lam) <= 0))
fam = {}
for (sid, u), r in recs.items():
    f = f"{D}/{sid}@{u}.pkl"
    if os.path.exists(f): fam.setdefault((r["name"].split(" — ")[0], u), []).append(f)
PB = []
for (fname, u), files in fam.items():
    if len(files) < 4: continue
    S = []
    for f in files:
        s = pickle.load(open(f, "rb")); s.index = pd.to_datetime(s.index); s.index = s.index.tz_localize(None) if s.index.tz is not None else s.index; S.append(s.groupby(s.index.normalize()).sum())
    X = pd.concat(S, axis=1).dropna()
    X = X.loc[:, X.std() > 0]
    if len(X) < 400 or X.shape[1] < 4: continue
    PB.append(dict(family=fname, universe=u, members=X.shape[1], days=len(X), pbo=round(pbo(X.values), 3)))
PB = pd.DataFrame(PB).sort_values("pbo")
M.to_csv(f"{H}/results/multiple_testing.csv", index=False); PB.to_csv(f"{H}/results/pbo_by_family.csv", index=False)
print(f"market tests {N_tests}, total grid trials {N_trials}, cross-trial var(SR per period) {V:.2e}")
print(f"expected max Sharpe of unskilled trials (annualised, 252): N=tests {M.attrs['sr0_tests'] * math.sqrt(252):.2f}, N=trials {M.attrs['sr0_trials'] * math.sqrt(252):.2f}")
print("passed gate:", int(M.passed.sum()), "| DSR>0.95 (tests):", int((M.passed & (M.dsr_tests > 0.95)).sum()), "| DSR>0.95 (trials):", int((M.passed & (M.dsr_trials > 0.95)).sum()),
      "| BH-FDR 5%:", int((M.passed & M.fdr5).sum()), "| t>3:", int((M.passed & M.hlz_t3).sum()), "| all corrections:", int(M.survives_all.sum()))
print(M[M.passed].sort_values("dsr_tests", ascending=False)[["id", "universe", "sr_ann", "T", "alpha_t", "dsr_tests", "dsr_trials", "fdr5", "hlz_t3", "survives_all"]].round(3).to_string(index=False))
print("\nPBO by family (lower is better; >0.5 = picking the in-sample best formulation is no better than chance):")
print(PB.to_string(index=False))
r0053 = M[(M.id == "STRAT-0053") & (M.universe == "crypto")]; print("\nSTRAT-0053 crypto:", r0053[["sr_ann", "alpha_t", "dsr_tests", "dsr_trials", "fdr5", "hlz_t3"]].round(3).to_dict("records"))

# ---- robust variants of the DSR benchmark (the raw cross-trial variance is inflated by broken/sampled-day streams) ----
EXCL_U = {"F91", "F92", "F93", "F95", "F96", "F97", "F98", "F99", "F100"}
ART = {f"STRAT-{i:04d}" for i in range(321, 330)} | {"STRAT-0560", "STRAT-0580"}
base = M[~M.universe.isin(EXCL_U) & ~M.id.isin(ART)]
V_clean = float(base.sr.var()); mad = float(np.median(np.abs(base.sr - base.sr.median()))) * 1.4826; V_mad = mad ** 2
out = {}
for lab, Vx, N in (("clean_tests", V_clean, len(base)), ("clean_trials", V_clean, int(base.trials.sum())), ("mad_tests", V_mad, len(base)), ("mad_trials", V_mad, int(base.trials.sum()))):
    s0 = sr0(N, Vx); out[lab] = s0
    M[f"dsr_{lab}"] = [float(norm.cdf((r.sr - s0) * math.sqrt(r.T - 1) / math.sqrt(max(1e-12, 1 - r.skew * r.sr + (r.kurt - 1) / 4 * r.sr ** 2)))) for r in M.itertuples()]
print("\nexpected max Sharpe of unskilled trials (annualised x sqrt252):", {k: round(v * math.sqrt(252), 2) for k, v in out.items()})
M["survives_robust"] = M.passed & ~M.id.isin(ART) & (M.dsr_mad_trials > 0.95) & M.fdr5 & M.hlz_t3
print("passed & not artifact:", int((M.passed & ~M.id.isin(ART)).sum()), "| + DSR>0.95 clean/tests:", int((M.passed & ~M.id.isin(ART) & (M.dsr_clean_tests > 0.95)).sum()),
      "| clean/trials:", int((M.passed & ~M.id.isin(ART) & (M.dsr_clean_trials > 0.95)).sum()), "| MAD/trials:", int((M.passed & ~M.id.isin(ART) & (M.dsr_mad_trials > 0.95)).sum()),
      "| MAD/trials + FDR5 + t>3:", int(M.survives_robust.sum()))
print(M[M.passed & ~M.id.isin(ART)].sort_values("dsr_mad_trials", ascending=False)[["id", "universe", "sr_ann", "T", "alpha_t", "dsr_clean_tests", "dsr_clean_trials", "dsr_mad_trials", "fdr5", "hlz_t3", "survives_robust"]].round(3).head(30).to_string(index=False))
M.to_csv(f"{H}/results/multiple_testing.csv", index=False)
json.dump({"n_tests": N_tests, "n_trials": N_trials, "sr0_ann": {k: v * math.sqrt(252) for k, v in {**out, "raw_tests": M.attrs["sr0_tests"], "raw_trials": M.attrs["sr0_trials"]}.items()}}, open(f"{H}/results/multiple_testing_summary.json", "w"), indent=1)

# ---- family-wise control: skew/kurtosis-adjusted Sharpe z (PSR vs 0) against Bonferroni / Holm critical values ----
M["psr_z"] = [r.sr * math.sqrt(r.T - 1) / math.sqrt(max(1e-12, 1 - r.skew * r.sr + (r.kurt - 1) / 4 * r.sr ** 2)) for r in M.itertuples()]
zc_tests, zc_trials = norm.ppf(1 - 0.05 / N_tests), norm.ppf(1 - 0.05 / N_trials)
p = 1 - norm.cdf(M.psr_z.values); o = np.argsort(p); n = len(p); holm = np.zeros(n, bool)
for rank, i in enumerate(o):
    if p[i] <= 0.05 / (n - rank): holm[i] = True
    else: break
M["holm5"] = holm; M["bonf_trials"] = M.psr_z > zc_trials
cand = M[M.passed & ~M.id.isin(ART)].sort_values("psr_z", ascending=False)
print(f"\nBonferroni critical z: tests {zc_tests:.2f}, trials {zc_trials:.2f}")
print("passed & not artifact:", len(cand), "| Holm 5% (tests):", int(cand.holm5.sum()), "| Bonferroni over all trials:", int(cand.bonf_trials.sum()), "| + PBO<0.5 family:", "see pbo_by_family.csv")
print(cand[["id", "universe", "name", "sr_ann", "T", "skew", "kurt", "psr_z", "holm5", "bonf_trials", "dsr_mad_trials"]].round(2).to_string(index=False))
M.to_csv(f"{H}/results/multiple_testing.csv", index=False)
