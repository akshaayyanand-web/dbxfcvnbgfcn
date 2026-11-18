"""Add Summary/verdict, Top strategies and Portfolio sheets to the results workbook."""
import os, json, openpyxl, pandas as pd
from openpyxl.styles import Font, Alignment
H = os.path.dirname(__file__); f = f"{H}/catalogue_results.xlsx"; wb = openpyxl.load_workbook(f)
ws = wb["1000 Strategy Ideas"]; mt = wb["Market tests"]; pf = json.load(open(f"{H}/results/portfolio.json")); me = json.load(open(f"{H}/results/micro_gross_edge.json"))
st = {ws.cell(i, 1).value: ws.cell(i, 9).value for i in range(2, ws.max_row + 1)}; fam = {ws.cell(i, 1).value: ws.cell(i, 2).value for i in range(2, ws.max_row + 1)}
rule = {ws.cell(i, 1).value: ws.cell(i, 13).value for i in range(2, ws.max_row + 1)}
hdr = [c.value for c in mt[1]]; rows = [dict(zip(hdr, [c.value for c in r])) for r in mt.iter_rows(min_row=2)]
import collections
cnt = collections.Counter("PASS (distinct)" if "PASS (distinct)" in (v or "") else "PASS (variation)" if "PASS" in (v or "") and "FAIL" not in v else "FAIL" if "FAIL" in (v or "") else "REJECTED artifact" if (v or "").startswith("REJECTED") else "BLOCKED/MERGED" for v in st.values())
MT = pd.read_csv(f"{H}/results/multiple_testing.csv"); RB = json.load(open(f"{H}/results/robustness.json"))
okb = {(a, b) for a, b, z in zip(MT.id, MT.universe, MT.bonf_trials) if z}
P = sorted([r for r in rows if r["passed"] and (r["id"], r["universe"]) in okb and not RB.get(f'{r["id"]}@{r["universe"]}', {}).get("fragile", False) and not (st[r["id"]] or "").startswith(("REJECTED", "CONTROL"))], key=lambda r: -(r["WF Sh"] or 0))
for n in ("Summary & verdict", "Top strategies", "Portfolio"):
    if n in wb.sheetnames: del wb[n]
t = wb.create_sheet("Top strategies", 0); t.append(["Rank", "Strategy ID", "Family", "Market", "Walk-forward Sharpe", "Walk-forward CAGR % (10-15% vol)", "Walk-forward max DD %", "Untouched test Sharpe", "Test Sharpe with 1-day delay", "Rules / params / notes (survive gate + Bonferroni over all trials + delay test + artifact screen)"])
for i, r in enumerate(P, 1):
    t.append([i, r["id"], fam[r["id"]], r["universe"], r["WF Sh"], r["WF CAGR %"], r["WF maxDD %"], r["test Sh"], r["test Sh with 1-day delay"], rule[r["id"]]])
for c in t[1]: c.font = Font(bold=True)
p = wb.create_sheet("Portfolio", 1)
for name, res in pf.items():
    p.append([name]); p[p.max_row][0].font = Font(bold=True)
    p.append(["Members (one per independent edge, |corr| < 0.5)", ", ".join(res["members"])]); p.append(["Average pairwise correlation", res["corr_avg"]])
    p.append(["Leverage", "CAGR", "Vol", "Sharpe", "Max DD"])
    for k, v in res.items():
        if k.startswith("x"): p.append([k, v["cagr"], v["vol"], v["sharpe"], v["maxdd"]])
    p.append(["Bootstrap 12-month (4,000 paths, 20-day blocks)", "median", "5th pct", "95th pct", "P(>= +300%)", "P(max DD > 20%)", "P(loss > 50%)"])
    for k, v in res["bootstrap_12m"].items(): p.append([k, v["median_12m"], v["p5"], v["p95"], v["P_ge_300pct"], v["P_maxdd_gt_20pct"], v["P_loss_gt_50pct"]])
    p.append([])
s = wb.create_sheet("Summary & verdict", 0)
lines = [
 ("Catalogue entries processed", "1,000 of 1,000 plus 33 new mechanisms (STRAT-1001..1033) added after the review"),
 ("Status counts", "; ".join(f"{k}: {v}" for k, v in cnt.items())),
 ("Market tests run", f"{len(rows)} strategy x market backtests (latest record each; older versions in Result history)"),
 ("Q1 1,000 distinct strategies?", "No. About 500 entries were testable; the two-stage duplicate review finds ~118 distinct mechanism classes among them; 534 entries are blocked by missing data."),
 ("Q2/Q3 profitable and validated", f"{len(P)} market tests pass the gate AND Bonferroni over all trials AND the 1-day delay test AND the artifact screen; they collapse to about 11 mechanism classes. No strategy reaches a 95% deflated Sharpe ratio."),
 ("Q4 Best validated return", "single strategies 7-36%/yr walk-forward CAGR at 10-15% vol; e.g. STRAT-0561 (short variance after payrolls) 36%, Sharpe 1.83, max DD -34%"),
 ("Q5/Q6 Portfolio", "7 surviving mechanism classes (variance premium, trend gated by curve slope, crack spread, industry momentum, betting-against-beta, location basis, stock-bond-correlation risk parity): out-of-sample Sharpe 1.65 (2011-26) / 1.91 (1995-26); at 10% vol ~17-20%/yr, max DD ~-13%"),
 ("Q7 +300% in 12 months?", "Only with ~8x leverage (80% vol): bootstrap P(+300%) 30-42% but P(drawdown > 20%) 99% and typical max DD ~-75%. Within a 20% drawdown budget (~2x) the expectation is ~36-44%/yr and P(+300%) = 0. Expect less live: members were chosen after seeing the history."),
 ("Q8 Independently validated?", "Within this study only (untouched test, walk-forward, delay test, family-wise multiple-testing control, independent re-implementation for STRAT-0053). No paper/live record yet; two legs are synthetic or spot-index proxies."),
 ("Q9 Costs", "Per side: crypto spot 6 bp, perps 5 bp, carry legs 10 bp, index CFD 1.5 bp, metals 2 bp, oil 4 bp, FX 1 bp, Treasuries 1 bp, industry ETFs 5 bp, variance swaps 0.5 vol pt."),
 ("Q10 Paper-trading candidates", "industry momentum + betting-against-beta via sector ETFs; trend gated by curve slope via futures; stock-bond-correlation risk parity via ETFs/futures; variance premium via listed SPX options (costs higher than modelled); crack/location spreads via NYMEX futures."),
 ("Rejected look-alikes", "swap spreads (non-synchronous fixings), weekly variance swaps (instrument mismatch), NFCI timing (revisions: real-time alpha t -0.1), STRAT-0053 (needs same-close fills), several energy spreads (collapse with 1-day delay)."),
 ("Why 300% is out of reach", "Max compound growth ~exp(S^2/2)-1 at full Kelly; +300% needs S >= 1.67 with full-Kelly drawdowns, or Sharpe well above 3 under a 20% drawdown cap."),
]
s.append(["Item", "Result"])
for a, b in lines: s.append([a, b])
for c in s[1]: c.font = Font(bold=True)
s.column_dimensions["A"].width = 42; s.column_dimensions["B"].width = 160
for row in s.iter_rows(min_row=2):
    for c in row: c.alignment = Alignment(wrap_text=True, vertical="top")
wb.save(f); print("saved", f, dict(cnt))
