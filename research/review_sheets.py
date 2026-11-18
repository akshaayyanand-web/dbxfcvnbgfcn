"""Add the post-review sheets: Review response, Result history, Duplicate review, Multiple testing, PBO by family, STRAT-0053 deep dive,
New mechanisms (STRAT-1001+), Reproducibility."""
import os, json, glob, subprocess, collections, pandas as pd, openpyxl
from openpyxl.styles import Font, Alignment
H = os.path.dirname(os.path.abspath(__file__)); f = f"{H}/catalogue_results.xlsx"; wb = openpyxl.load_workbook(f)
def sheet(name, df=None, rows=None, pos=None, widths=None):
    if name in wb.sheetnames: del wb[name]
    s = wb.create_sheet(name) if pos is None else wb.create_sheet(name, pos)
    if df is not None:
        s.append(list(df.columns))
        for r in df.itertuples(index=False): s.append([None if (isinstance(v, float) and v != v) else v for v in r])
    for r in rows or []: s.append(r)
    for c in s[1]: c.font = Font(bold=True)
    for k, w in (widths or {}).items(): s.column_dimensions[k].width = w
    return s
commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=H).stdout.strip()
# ---- result history ----
vers = [("v1 batch-1 (total returns)", "results/archive/results_781b93f.jsonl"), ("v2 excess-of-cash", "results/archive/results_790bf26.jsonl"), ("v3 all 1,000", "results/archive/results_942e10e.jsonl"), ("current", "results/results.jsonl")]
hist = collections.OrderedDict()
for lab, p in vers:
    for l in open(f"{H}/{p}"):
        r = json.loads(l)
        if r.get("universe") == "BLOCKED": continue
        hist.setdefault((r["id"], r["universe"]), {})[lab] = (r["test"]["sharpe"], r["test"]["cagr"], r["walkforward"]["cagr"], r["passed"], r.get("run_id", lab))
rows = []
for (sid, u), d in sorted(hist.items()):
    vals = [d.get(l) for l, _ in vers]; changed = len({v[:4] for v in vals if v}) > 1
    row = [sid, u]
    for v in vals: row += ([v[0], round(100 * v[1], 1), round(100 * v[2], 1), v[3]] if v else [None] * 4)
    reasons = []
    if changed and d.get(vers[0][0]) and d.get(vers[1][0]): reasons.append("v1->v2: funded assets measured over the cash rate (no free leverage)")
    if changed and u in ("crypto", "btc", "cashcarry", "qbasis") and d.get("current") and d["current"][4] == "rf_calendar_fix": reasons.append("current: crypto cash rate charged per calendar day (bug found by the independent STRAT-0053 reproduction)")
    row.append("; ".join(reasons)); rows.append(row)
cols = ["Strategy ID", "Market"] + [f"{l} {m}" for l, _ in vers for m in ("test Sharpe", "test CAGR %", "WF CAGR %", "passed")] + ["Why it changed"]
sheet("Result history", pd.DataFrame(rows, columns=cols), widths={"A": 12, "B": 12})
# ---- duplicate review / multiple testing / PBO ----
sheet("Duplicate review", pd.read_csv(f"{H}/results/duplicate_review.csv"), widths={"B": 50, "C": 40, "E": 110})
MT = pd.read_csv(f"{H}/results/multiple_testing.csv"); summ = json.load(open(f"{H}/results/multiple_testing_summary.json"))
cols = ["id", "universe", "name", "T", "sr_ann", "skew", "kurt", "alpha_t", "passed", "dsr_tests", "dsr_trials", "dsr_mad_trials", "fdr5", "hlz_t3", "psr_z", "holm5", "bonf_trials"]
s = sheet("Multiple testing", MT[cols].sort_values("psr_z", ascending=False).round(3), widths={"C": 55})
s.insert_rows(1, 4)
s["A1"] = f"Trials: {summ['n_tests']} market tests, {summ['n_trials']} grid trials. Expected best Sharpe of unskilled trials (annualised): " + ", ".join(f"{k} {v:.2f}" for k, v in summ["sr0_ann"].items())
s["A2"] = "DSR = deflated Sharpe ratio (Bailey-Lopez de Prado); fdr5 = Benjamini-Hochberg 5% on one-sided alpha p-values; hlz_t3 = Harvey-Liu-Zhu t>3; psr_z = skew/kurtosis-adjusted Sharpe z; holm5 = Holm 5% across market tests; bonf_trials = Bonferroni 5% across all grid trials (z > 4.12)."
s["A3"] = "Reading: no strategy reaches DSR > 0.95 with the cross-trial Sharpe variance (very conservative when strategies genuinely differ); family-wise Bonferroni over all trials leaves the survivors listed in Top strategies."
sheet("PBO by family", pd.read_csv(f"{H}/results/pbo_by_family.csv"))
# ---- STRAT-0053 deep dive ----
dd = json.load(open(f"{H}/results/strat0053_deep_dive.json")); rows = [["Section", "Case", "CAGR", "Sharpe", "Max DD", "Days"]]
for sec in ("sources", "costs", "variants", "regimes", "years"):
    for k, v in dd[sec].items(): rows.append([sec, str(k), v["cagr"], v["sharpe"], v["maxdd"], v["days"]])
G = pd.DataFrame(dd["grid"]); rows += [["parameter grid", f"{len(G)} combos: share Sharpe>0 {round((G.sharpe > 0).mean(), 2)}, median {round(G.sharpe.median(), 2)}, min {G.sharpe.min()}, max {G.sharpe.max()}"], ["bootstrap", f"95% CI of Sharpe {dd['bootstrap_sharpe_ci']}"]]
RB = json.load(open(f"{H}/results/robustness.json")).get("STRAT-0053@crypto", {})
m53 = MT[(MT.id == "STRAT-0053") & (MT.universe == "crypto")].iloc[0]
s = sheet("STRAT-0053 deep dive", rows=[], widths={"B": 60})
for r in [["STRAT-0053 volatility-compression breakout (crypto) - deep dive"], [],
          ["Reproduction", "Independent code (research/independent/vcb.py, plain loops, own loaders) vs engine on the same Binance data: daily P&L correlation 0.995; CAGR 12.6% vs 12.8%; Sharpe 0.77 vs 0.81."],
          ["Bug found", "The engine charged the daily cash rate on every calendar day for 7-day markets (365/252 = 1.45x too much). Fixed; all crypto spot / carry tests re-run and appended (run rf_calendar_fix)."],
          ["Current gate result", "after the fix: test CAGR 14.75%, test Sharpe 0.89, alpha t 1.56 -> passes the original gate"],
          ["1-day execution delay", f"test Sharpe {RB.get('test_sharpe')} -> {RB.get('test_sharpe_lag1')} when entered the next day: the edge needs a fill at the very close that triggered the breakout (not achievable) -> FRAGILE"],
          ["Multiple testing", f"DSR {round(m53.dsr_tests, 3)} / {round(m53.dsr_trials, 3)}, Benjamini-Hochberg 5%: {bool(m53.fdr5)}, t>3: {bool(m53.hlz_t3)}, Bonferroni: {bool(m53.bonf_trials)}; family PBO 0.90 (picking the best formulation in-sample is no better than chance)"],
          ["Verdict", "Real but small and fragile: reproducible, positive on Coinbase (0.60) / Bitstamp (0.64) / perps (0.78), all 48 parameter combos > 0, but cost-sensitive (Sharpe 0.26 at 50 bp), collapses with a 1-day delay, and fails every multiple-testing correction. NOT a deployment candidate."], []] + rows:
    s.append(r)
# ---- new mechanisms ----
cur = {}
for l in open(f"{H}/results/results.jsonl"):
    r = json.loads(l)
    if int(r["id"][-4:]) > 1000: cur[(r["id"], r["universe"])] = r
rows = []
for (sid, u), r in sorted(cur.items()):
    mt = MT[(MT.id == sid) & (MT.universe == u)]; rb = json.load(open(f"{H}/results/robustness.json")).get(f"{sid}@{u}", {})
    rows.append([sid, r["name"].split(" — ")[0], u, r["mechanism"], r["walkforward"]["sharpe"], round(100 * r["walkforward"]["cagr"], 1), r["test"]["sharpe"], r["alpha_t"], r["passed"], rb.get("test_sharpe_lag1"),
                 bool(mt.bonf_trials.iloc[0]) if len(mt) else None])
sheet("New mechanisms (1001+)", pd.DataFrame(rows, columns=["ID", "Mechanism", "Market", "Rule", "WF Sharpe", "WF CAGR %", "Test Sharpe", "Alpha t", "Passed gate", "Test Sharpe 1-day delay", "Bonferroni (all trials)"]), widths={"B": 50, "D": 90})
# ---- reproducibility ----
man = pd.read_csv(f"{H}/repro/data_manifest.csv"); snap = sorted(glob.glob(f"{H}/repro/snapshot/**/*.gz", recursive=True))
rows = [["Item", "Detail"], ["Code", f"git repository, folder research/ (commit {commit}); every result record stores run_id and code_commit"],
        ["Raw data (3.7 GB)", f"repro/fetch_data.py downloads every source; repro/data_manifest.csv lists {len(man)} raw files with SHA-256 ({round(man.bytes.sum() / 1e9, 2)} GB)"],
        ["Processed data (25 MB, in git)", f"repro/snapshot/ ({len(snap)} gz files): daily panels, crypto derivatives panels, opening-range / FX-fix / microstructure tables, FRED / French / CBOE source files"],
        ["Re-run without downloading", "RSCRATCH=/new/dir python3 repro/snapshot.py import; RSCRATCH=/new/dir python3 repro/verify.py (re-runs STRAT-0002 and STRAT-0720 from the snapshot: test Sharpes match the records exactly)"],
        ["Re-run everything", "python3 repro/fetch_data.py; python3 data.py; python3 crypto2.py; BATCH=batchNNN python3 run.py; python3 run_streams.py strategies.batchNNN; python3 uniqueness.py; python3 robustness.py; python3 multiple_testing.py; python3 dup_review.py; python3 update_workbook.py; python3 portfolio.py; python3 finalize.py; python3 review_sheets.py"],
        ["Needs raw data (not in snapshot)", "market-making simulations (STRAT-0941..0960) replay 2 GB of BTCUSDT trades; intraday tables are in the snapshot but rebuilding them needs the 1-minute files"],
        ["Result policy", "append-only: results/runs/<run_id>.jsonl per run, results/archive/ holds every committed version; nothing is deleted; the workbook shows the latest record per strategy x market and the Result history sheet shows all versions"]]
sheet("Reproducibility", rows=rows[1:], widths={"A": 32, "B": 160}).insert_rows(1); wb["Reproducibility"]["A1"], wb["Reproducibility"]["B1"] = "Item", "Detail"
# ---- review response ----
rr = [["Review point", "What was done", "Result"],
      ["1. Preserve all original results", "Recovered every committed results version from git into results/archive/; engine is now append-only (results/runs/<run_id>.jsonl, run_id + code commit on every record); Result history sheet shows all versions side by side with the reason for each change.", "No failed strategy deleted; superseded numbers visible (e.g. STRAT-0053 test CAGR 15.3% v1 -> 13.3% v2 -> 14.75% current)."],
      ["2. Reassess duplicates", "Two-stage review: conceptual mechanism class + core-vs-filter layer for every tested entry, then weekly P&L correlation only within the same class; |corr| >= 0.9 = duplicate whatever the label.", "See Duplicate review sheet: 118 mechanism classes among 499 tested entries; of the 146 earlier correlation-only flags, 134 are confirmed duplicates, the rest reclassified (variants or correlated-but-distinct)."],
      ["3. Deep-dive STRAT-0053", "Independent code + independent data (Coinbase, Bitstamp, Binance perps), costs 0-50 bp, slippage, 48-parameter grid, long-only, majors vs alts, BTC vol/trend regimes, years, bootstrap, 1-day delay, multiple testing.", "Reproducible and broad-based but small, cost-sensitive and fragile to a 1-day execution delay; fails every multiple-testing correction -> not a candidate."],
      ["4. Reproduce independently", "Separately written backtester (research/independent/vcb.py); found and fixed a cash-rate bug in the main engine.", "P&L correlation 0.995 with the engine on identical data; all affected crypto tests re-run (appended)."],
      ["5. Sensitivity", "costs, slippage, liquidity (majors/alts), vol & trend regimes, instruments/exchanges", "See STRAT-0053 deep dive sheet."],
      ["6. Multiple-testing corrections", "DSR (raw, cleaned, MAD-robust benchmarks), Benjamini-Hochberg FDR, Harvey-Liu-Zhu t>3, Holm and Bonferroni on skew/kurtosis-adjusted Sharpe z, PBO (CSCV) per family.", "No strategy reaches DSR > 0.95. Survivors of gate + Bonferroni(all 2,673 trials) + 1-day delay + artifact screen: ~20 tests in ~11 mechanism classes (Top strategies)."],
      ["7. No live deployment from backtests", "Nothing is promoted to live. Next stage proposed: paper trading of the surviving classes with tradable instruments.", "Variance-swap legs are synthetic and energy/credit legs are spot-index proxies: they need instrument mapping before paper trading."],
      ["New mechanisms", "STRAT-1001..1033: EIA supply-demand, FOMC/claims events, NFCI and news-uncertainty alt data, Bayesian change-point, gradient boosting, random forest, logistic, k-NN, Q-learning, Thompson bandit, Hurst/DFA, ordinal patterns, BAB/IVOL/MAX, lead-lag network, cross-exchange crypto, DeFi TVL, NVT, Merton residual, rebalancing premium, vol-managed equity, Cochrane-Piazzesi.",
       "Pass and survive corrections: betting-against-beta (1020), random-forest industry ranker (1013, overlaps momentum), Bayesian-gated variance selling (1011, a variant of the variance premium), Thompson bandit (1017, allocator over existing streams). NFCI timing (1009) REJECTED: its edge disappears with real-time ALFRED vintages (1032 vs 1033). Everything else fails."],
      ["Data that would unlock blocked families", "option chains / IV surfaces, L2-L3 order books, on-chain flows, single-stock prices + corporate events, commodity futures curves, multi-exchange synchronous feeds, real-time macro vintages beyond NFCI", "534 entries remain BLOCKED rather than guessed."]]
s = sheet("Review response", rows=rr[1:], pos=0, widths={"A": 34, "B": 110, "C": 110}); s.insert_rows(1)
for j, v in enumerate(rr[0]): s.cell(1, j + 1).value = v; s.cell(1, j + 1).font = Font(bold=True)
for row in s.iter_rows(min_row=2):
    for c in row: c.alignment = Alignment(wrap_text=True, vertical="top")
wb.save(f); print("saved", f, wb.sheetnames)
