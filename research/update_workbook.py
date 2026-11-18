"""Write results.jsonl into the catalogue workbook (status + metrics per STRAT id, every market test, duplicates, progress)."""
import json, os, collections, openpyxl
from openpyxl.styles import PatternFill, Font
H = os.path.dirname(__file__); SRC = f"{H}/catalogue_source.xlsx"; OUT = f"{H}/catalogue_results.xlsx"
recs = [json.loads(l) for l in open(f"{H}/results/results.jsonl")]
by = collections.OrderedDict()
for r in recs: by.setdefault(r["id"], []).append(r)
def pct(x): return None if x is None else round(100 * x, 1)
def classify(rs):
    prim = rs[0]; win = [r for r in rs if r["passed"]]
    best = max(win, key=lambda r: r["walkforward"]["sharpe"]) if win else max(rs, key=lambda r: r["walkforward"]["sharpe"])
    var = (abs(best["max_corr"]) >= 0.7, best["max_corr_with"], best["max_corr"])
    if win and not var[0]: st = "TESTED - PASS (distinct)"
    elif win: st = f"TESTED - PASS, VARIATION of {var[1]} (corr {var[2]}) - not counted"
    elif var[0]: st = f"TESTED - FAIL; VARIATION of {var[1]} (corr {var[2]})"
    else: st = "TESTED - FAIL"
    return st, best
wb = openpyxl.load_workbook(SRC); ws = wb["1000 Strategy Ideas"]
G = PatternFill("solid", fgColor="C6EFCE"); Rd = PatternFill("solid", fgColor="FFC7CE"); Y = PatternFill("solid", fgColor="FFEB9C")
rowof = {ws.cell(i, 1).value: i for i in range(2, ws.max_row + 1)}; summary = collections.Counter(); dups = []
for sid, rs in by.items():
    i = rowof[sid]; st, b = classify(rs); summary[st.split(";")[0].split(",")[0]] += 1
    if "VARIATION" in st: dups.append((sid, b["max_corr_with"], b["max_corr"], b["name"]))
    wf, te, va = b["walkforward"], b["test"], b["val"]
    ws.cell(i, 9).value = st
    ws.cell(i, 10).value = f"{pct(wf['cagr'])}% walk-forward CAGR net of costs at 15% vol target ({b['universe']}, {b['period']}); Sharpe {wf['sharpe']}"
    ws.cell(i, 11).value = f"{pct(wf['maxdd'])}% (walk-forward); test {pct(te['maxdd'])}%"
    ws.cell(i, 12).value = (f"Untouched test ({b['split'].split('|')[-1].strip()}): Sharpe {te['sharpe']}, CAGR {pct(te['cagr'])}%, trades {b['test_trades']['trades']}, "
                            f"win {b['test_trades']['win']}, PF {b['test_trades']['pf']}; validation Sharpe {va['sharpe']}")
    mk = "; ".join(f"{r['universe']}: WF Sh {r['walkforward']['sharpe']} / test Sh {r['test']['sharpe']}{' PASS' if r['passed'] else ''}" for r in rs)
    l300 = f"+300%/yr needs {b['lev_for_300']}x this risk (max DD {pct(b['maxdd_at_300'])}%)" if b["lev_for_300"] else "+300%/yr unreachable at <=40x"
    ws.cell(i, 13).value = (f"Rule: {b['mechanism']}. Params chosen on train: {b['params']} ({b['trials']} trials). Alpha t {b['alpha_t']}, beta {b['beta']}"
                            f"{', bench test Sh ' + str(b['bench_test_sharpe']) if b.get('bench_test_sharpe') is not None else ''}. Markets: {mk}. {l300}.")
    ws.cell(i, 9).fill = G if "PASS (distinct)" in st else Y if "PASS" in st else Rd
# every market test
d = wb.create_sheet("Market tests"); cols = ["id", "name", "universe", "period", "params", "trials", "train Sh", "val Sh", "test Sh", "test CAGR %", "test maxDD %",
     "WF CAGR %", "WF Sh", "WF Sortino", "WF Calmar", "WF maxDD %", "test trades", "test win", "test PF", "alpha t", "beta", "grid share Sh>0", "max corr", "corr with", "lev for 300%", "DD at 300% lev", "passed"]
d.append(cols)
for r in recs:
    d.append([r["id"], r["name"], r["universe"], r["period"], json.dumps(r["params"]), r["trials"], r["train"]["sharpe"], r["val"]["sharpe"], r["test"]["sharpe"], pct(r["test"]["cagr"]),
              pct(r["test"]["maxdd"]), pct(r["walkforward"]["cagr"]), r["walkforward"]["sharpe"], r["walkforward"]["sortino"], r["walkforward"]["calmar"], pct(r["walkforward"]["maxdd"]),
              r["test_trades"]["trades"], r["test_trades"]["win"], r["test_trades"]["pf"], r["alpha_t"], r["beta"], r["grid_positive_share"], r["max_corr"], r["max_corr_with"],
              r["lev_for_300"], pct(r["maxdd_at_300"]), r["passed"]])
for c in d[1]: c.font = Font(bold=True)
# duplicates -> replacements queue
q = wb.create_sheet("Duplicates & replacements"); q.append(["Catalogue id", "Duplicate of", "WF return correlation", "Formulation", "Replacement hypothesis (new mechanism, to test as STRAT-R###)"])
REPL = ["Hurst-exponent regime switch (trend vs revert by fractal persistence)", "Permutation-entropy filter (trade only low-entropy, predictable states)",
        "Hidden-Markov 2-state return regime allocation", "Kalman-filter dynamic hedge-ratio spread", "Volume-profile value-area rejection (auction theory)",
        "Turn-of-the-month equity flow effect", "Overnight vs intraday return decomposition (night premium)", "Lyapunov/recurrence predictability gate",
        "Bayesian online change-point trend restart", "Realised skewness cross-sectional sort", "Max-daily-return lottery effect (MAX)", "Betting-against-beta within universe",
        "Idiosyncratic-vol puzzle sort", "Weekend crypto gap fill vs continuation", "Funding-rate cross-sectional carry (crypto perps)", "Yield-curve carry-and-roll-down",
        "FX carry via rate differentials (FRED short rates)", "Commodity seasonality calendar (spot energy)", "Time-of-day intraday seasonality (half-hour returns)", "Correlation-breakdown cross-asset reversion"]
for k, (sid, w, c, n) in enumerate(dups): q.append([sid, w, c, n, REPL[k % len(REPL)] + (" (queued)" if k < len(REPL) else " (queue: needs new idea)")])
# progress + protocol notes
p = wb.create_sheet("Progress"); last = max(by)
for row in [["Last completed id", last], ["Next id", f"STRAT-{int(last[-4:]) + 1:04d}"], ["Market tests run", len(recs)], ["Strategies tested", len(by)],
            *[[k, v] for k, v in summary.items()],
            ["Protocol", "Rules + small grid fixed in code before testing; parameters picked on first 60% (train) by Sharpe; next 20% validation; last 20% untouched test reported once; expanding walk-forward re-selected yearly; costs per side: crypto 6bp, index 1.5bp, metals 2bp, oil 4bp, FX 1bp, Treasuries 1bp, industry portfolios 5bp; positions decided at close t, earn t+1; portfolio vol target 15%, gross cap 4x (crypto 2x)."],
            ["Pass gate", "validation Sharpe>0, test Sharpe>0.3, walk-forward Sharpe>0.3, >=30 test trades, alpha t>=1.5, and long-biased books must beat equal-risk buy-and-hold (alpha t>=2 and higher test Sharpe)."],
            ["Uniqueness", "walk-forward daily pnl correlated with every earlier strategy on the same market; |corr|>=0.7 -> variation (not counted)."],
            ["Data", "Binance spot 1h (13 coins, 2020-2026) + funding; Dukascopy CFD 1h/1m (NQ, SPX, DJI, RUT, gold, silver, WTI 2016-2026; DAX 1m 2021+; EURUSD 1m 2019+); FRED FX (14, 1971+), Treasury yields -> par-bond returns (1962+), VIX, curve, credit, oil/gas spot; Ken French 49/10 industries (1926+), factors."],
            ["Not available here", "options chains/IV surfaces, order books/trade-by-trade, on-chain data, single-stock fundamentals/earnings/insider/short interest, bond/commodity futures curves, ADR/dual-listing prices, CEX-DEX data: families needing these will be marked BLOCKED, not guessed."]]:
    p.append(row)
wb.save(OUT); print(OUT, dict(summary), "dups", len(dups))
