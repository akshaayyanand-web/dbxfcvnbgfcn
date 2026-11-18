"""Final portfolio: walk-forward (out-of-sample) daily P&L of the distinct passing strategies, clustered by correlation (one per edge),
equal-risk combination, leverage sweep and a stationary block bootstrap of 12-month outcomes (P(>= +300%), P(max DD > 20%))."""
import os, json, pickle, numpy as np, pandas as pd, openpyxl
from data import SCR
H = os.path.dirname(__file__); D = f"{SCR}/rdata/pnl"
wb = openpyxl.load_workbook(f"{H}/catalogue_results.xlsx"); ws = wb["1000 Strategy Ideas"]; mt = wb["Market tests"]
st = {ws.cell(i, 1).value: ws.cell(i, 9).value for i in range(2, 1002)}
hdr = [c.value for c in mt[1]]; rows = [dict(zip(hdr, [c.value for c in r])) for r in mt.iter_rows(min_row=2)]
P = sorted([r for r in rows if r["passed"] and "PASS (distinct)" in (st[r["id"]] or "")], key=lambda r: -(r["WF Sh"] or 0))
S = {}
for r in P:
    s = pickle.load(open(f'{D}/{r["id"]}@{r["universe"]}.pkl', "rb")); s.index = pd.to_datetime(s.index); s.index = s.index.tz_localize(None) if s.index.tz is not None else s.index
    s = s.groupby(s.index.normalize()).sum(); s = s[s.index.dayofweek < 5] if r["universe"] not in ("perp", "crypto", "btc", "cashcarry", "qbasis") else s.resample("B").sum()
    S[f'{r["id"]}@{r["universe"]}'] = s / (s.std() * np.sqrt(252)) * 0.10       # each at 10% vol for comparability
A = pd.DataFrame(S).fillna(0); C = A.loc["2011":].replace(0, np.nan).corr()
# greedy clustering: keep the best (by walk-forward Sharpe) strategy, drop others with |corr| >= 0.5 to anything kept
keep = []
for k in A.columns:
    if all(abs(C.loc[k, j]) < 0.5 for j in keep if pd.notna(C.loc[k, j])): keep.append(k)
print("independent edges kept:", keep)
def stats(p, ann=252):
    eq = (1 + p).cumprod(); y = len(p) / ann; cagr = eq.iloc[-1] ** (1 / y) - 1; dd = (eq / eq.cummax() - 1).min()
    return dict(cagr=round(float(cagr), 4), vol=round(float(p.std() * np.sqrt(ann)), 4), sharpe=round(float(p.mean() / p.std() * np.sqrt(ann)), 2), maxdd=round(float(dd), 3))
out = {}
for name, start in (("all edges, 2024-01..2026-09 (crypto carry included)", "2024-01-01"), ("non-crypto edges, 2011-2026-09", "2011-01-01")):
    cols = [k for k in keep if (start == "2024-01-01") or not any(u in k for u in ("perp", "crypto", "btc"))]
    X = A.loc[start:"2026-09-30", cols]; X = X.loc[:, (X != 0).mean() > 0.3]
    w = 1 / X.std(); port = (X * w).sum(1) / w.sum(); port = port / (port.std() * np.sqrt(252)) * 0.10
    res = {"members": list(X.columns), "corr_avg": round(float(X.corr().values[np.triu_indices(X.shape[1], 1)].mean()), 2)}
    for L in (1, 2, 3, 5, 8, 12):
        res[f"x{L} ({10 * L}% vol)"] = stats((L * port).clip(lower=-0.95))
    # stationary block bootstrap of 1-year paths (blocks ~20 days)
    rng = np.random.default_rng(0); x = port.values; n = len(x); mc = {}
    for L in (1, 3, 5, 8, 12):
        fin, dds = [], []
        for _ in range(4000):
            i = rng.integers(n); path = []
            while len(path) < 252:
                path.append(x[i]); i = (i + 1) % n if rng.random() > 1 / 20 else rng.integers(n)
            q = np.clip(L * np.array(path), -0.95, None); eq = np.cumprod(1 + q); fin.append(eq[-1] - 1); dds.append((eq / np.maximum.accumulate(eq) - 1).min())
        fin, dds = np.array(fin), np.array(dds)
        mc[f"x{L}"] = dict(median_12m=round(float(np.median(fin)), 3), p5=round(float(np.percentile(fin, 5)), 3), p95=round(float(np.percentile(fin, 95)), 3),
                          P_ge_300pct=round(float((fin >= 3.0).mean()), 4), P_maxdd_gt_20pct=round(float((dds < -0.2).mean()), 3), P_loss_gt_50pct=round(float((fin < -0.5).mean()), 3))
    res["bootstrap_12m"] = mc; out[name] = res
    print("\n==", name, "| members", len(X.columns), "| avg corr", res["corr_avg"])
    for k, v in res.items():
        if k.startswith("x"): print(" ", k, v)
    for k, v in mc.items(): print("  MC", k, v)
json.dump(out, open(f"{H}/results/portfolio.json", "w"), indent=1)
pd.DataFrame(S).corr().round(2).to_csv(f"{H}/results/passer_correlations.csv")
