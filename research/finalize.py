"""Add Summary/verdict, Top strategies and Portfolio sheets to the results workbook."""
import os, json, openpyxl
from openpyxl.styles import Font, Alignment
H = os.path.dirname(__file__); f = f"{H}/catalogue_results.xlsx"; wb = openpyxl.load_workbook(f)
ws = wb["1000 Strategy Ideas"]; mt = wb["Market tests"]; pf = json.load(open(f"{H}/results/portfolio.json")); me = json.load(open(f"{H}/results/micro_gross_edge.json"))
st = {ws.cell(i, 1).value: ws.cell(i, 9).value for i in range(2, 1002)}; fam = {ws.cell(i, 1).value: ws.cell(i, 2).value for i in range(2, 1002)}
rule = {ws.cell(i, 1).value: ws.cell(i, 13).value for i in range(2, 1002)}
hdr = [c.value for c in mt[1]]; rows = [dict(zip(hdr, [c.value for c in r])) for r in mt.iter_rows(min_row=2)]
import collections
cnt = collections.Counter("PASS (distinct)" if "PASS (distinct)" in (v or "") else "PASS (variation)" if "PASS" in (v or "") and "FAIL" not in v else "FAIL" if "FAIL" in (v or "") else "REJECTED artifact" if (v or "").startswith("REJECTED") else "BLOCKED/MERGED" for v in st.values())
P = sorted([r for r in rows if r["passed"] and "PASS (distinct)" in (st[r["id"]] or "")], key=lambda r: -(r["WF Sh"] or 0))
for n in ("Summary & verdict", "Top strategies", "Portfolio"):
    if n in wb.sheetnames: del wb[n]
t = wb.create_sheet("Top strategies", 0); t.append(["Rank", "Strategy ID", "Family", "Market", "Walk-forward Sharpe", "Walk-forward CAGR % (10-15% vol)", "Walk-forward max DD %", "Untouched test Sharpe", "Test Sharpe with 1-day delay", "Rules / params / notes"])
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
 ("Catalogue entries processed", "1,000 of 1,000 (every ID has a test record or a documented block/merge)"),
 ("Status counts", "; ".join(f"{k}: {v}" for k, v in cnt.items())),
 ("Market tests run", f"{len(rows)} strategy x market backtests with costs, train/validation/untouched-test split and expanding walk-forward"),
 ("Q1 Tested 1,000 distinct strategies?", "No. 1,000 entries were processed, but the catalogue is 100 families x 10 formulations; ~460 were testable with available data, many proved to be variations (weekly P&L correlation >= 0.7), and 534 are blocked by missing data (options chains, order-book L3, on-chain, single-stock events, futures curves, multi-exchange feeds)."),
 ("Q2 Profitable / Q3 passed out-of-sample", f"{cnt['PASS (distinct)']} entries pass every gate and are distinct; {cnt['PASS (variation)']} more pass but duplicate an earlier mechanism. 10 apparent winners were rejected as data artifacts (non-synchronous FRED swap fixings; weekly swaps priced off a 30-day vol index), 6 collapsed with a 1-day execution delay."),
 ("Q4 Best net annual return (validated)", "Single strategies: 15-36%/yr walk-forward CAGR at 10-15% vol (e.g. STRAT-0561 short variance after payrolls 36%, Sharpe 1.83, max DD -34%; STRAT-0720 crypto funding carry 18.5%, Sharpe 1.68, max DD -10%)."),
 ("Q5 Max drawdown", "Validated portfolio at 10% vol: -11.5% (2024-26, with crypto) / -12% (2011-26, without crypto)."),
 ("Q6 Best risk-adjusted single strategy", "STRAT-0720 Crypto funding carry (cross-sectional, traded only when the funding gap > 20%/yr): walk-forward Sharpe 1.68, untouched test Sharpe 2.16, 1.76 with a 1-day delay, beta 0.07."),
 ("Q7 Any strategy >= +300% net in 12 months?", "No single strategy. The diversified portfolio reaches +300% in 12 months only with ~8x leverage (80% vol): bootstrap P(+300%) = 23-29%, but P(max DD > 20%) = 99% and typical max DD ~ -70%. At the 20% drawdown limit (about 2x, 20% vol) the expected return is ~31-35%/yr and P(+300%) = 0."),
 ("Q8 Independently validated?", "Validated out-of-sample within this study (untouched test period + walk-forward + delay test). NOT independently validated: selection across ~2,000 trials inflates Sharpe (apply a ~50% haircut), no live/paper results yet."),
 ("Q9 Realistic execution costs", "Per side: crypto spot 6 bp, perps 5 bp, carry legs 10 bp, index CFD 1.5 bp, metals 2 bp, oil 4 bp, FX 1 bp, Treasuries 1 bp, industry ETFs 5 bp, variance swaps 0.5 vol pt, crypto variance 1 vol pt, BTC minute trading 4.5 bp taker / 2 bp maker. Microstructure signals have ~0 gross edge per round trip vs 9 bp cost."),
 ("Q10 Strongest candidate for paper trading", "STRAT-0720 (crypto cross-sectional funding carry on Binance USD-M perps), then the diversified 12-edge book at 10-20% vol. Variance-swap legs need listed-option replication (higher cost than modelled); energy-spread and credit legs are spot-index proxies that need futures/ETF implementation."),
 ("Why 300% is out of reach", "Max compound growth of a strategy with Sharpe S is ~exp(S^2/2)-1 at full-Kelly leverage with very deep drawdowns. +300% needs S >= 1.67 AND full-Kelly drawdowns; under a 20% drawdown cap it needs Sharpe well above 3, which nothing here (or in the literature at scale) delivers after costs."),
 ("Microstructure gross edge (BTCUSDT sample)", "; ".join(f"{k}: {v['gross_bp_per_round_trip']} bp/round trip" for k, v in me.items())),
 ("Data limitations", "Free/public data only: Binance archives, Dukascopy CFDs, FRED, Ken French library, CBOE indices, Deribit DVOL, DefiLlama, blockchain.info. Spot energy prices and Moody's yields are index proxies (not directly tradable); variance swaps are synthetic (VIX-family strikes)."),
]
s.append(["Item", "Result"])
for a, b in lines: s.append([a, b])
for c in s[1]: c.font = Font(bold=True)
s.column_dimensions["A"].width = 42; s.column_dimensions["B"].width = 160
for row in s.iter_rows(min_row=2):
    for c in row: c.alignment = Alignment(wrap_text=True, vertical="top")
wb.save(f); print("saved", f, dict(cnt))
