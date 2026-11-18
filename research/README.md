# Strategy research catalogue — progress log

Workbook: `catalogue_results.xlsx` (the 1,000-entry catalogue with status/metrics filled in, plus sheets *Market tests*,
*Duplicates & replacements*, *Progress*). Raw records: `results/results.jsonl` (one line per strategy x market).

## Resume
```
cd research
python3 data.py                      # rebuilds data panels (needs the raw files listed in the Progress sheet)
python3 run.py STRAT-0001 STRAT-0100 # daily families (skips ids already in results.jsonl)
python3 run_orb.py                   # family 5, 1-minute opening-range tests
python3 update_workbook.py           # writes results into the workbook
```
All 1,000 ids processed. Daily batches: `BATCH=batchNNN python3 run.py`; stream batches (intraday, volatility, microstructure): `python3 run_streams.py strategies.batchNNN`;
then `python3 uniqueness.py; python3 robustness.py; python3 update_workbook.py; python3 portfolio.py; python3 finalize.py`.

## Protocol (identical for every entry)
Rules and a small parameter grid are fixed in code before the run. Positions use data up to the close of day t and earn day t+1.
Parameters are picked on the first 60% of the sample (Sharpe); the next 20% is validation; the last 20% is an untouched test reported once.
Expanding walk-forward re-selects parameters each year using only past data. Costs per side: crypto 6 bp, index CFDs 1.5 bp,
metals 2 bp, oil 4 bp, FX 1 bp, Treasuries 1 bp, industry portfolios 5 bp. Books are vol-targeted to 15%/yr with gross exposure capped
at 4x (crypto 2x). Pass gate: validation Sharpe > 0, test Sharpe > 0.3, walk-forward Sharpe > 0.3, >= 30 test trades, alpha t >= 1.5,
and long-biased books must beat an equal-risk buy-and-hold of the same market. Uniqueness: walk-forward daily P&L correlation >= 0.7 with an
earlier strategy on the same market = variation (not counted).

## Final status (all 1,000 entries)
| Status | Count |
|---|---|
| Pass, distinct | 26 |
| Pass, variation of an earlier entry (not counted) | 15 |
| Fail (incl. 6 that collapse with a 1-day execution delay) | 415 |
| Rejected as data artifacts (non-synchronous swap fixings; weekly swaps struck at 30-day vol) | 10 |
| Blocked / merged (data not available here, or same instrument as an earlier entry) | 534 |

Extra safeguards added during the study: excess-of-cash returns for funded assets, buy-and-hold benchmark gate for long-biased books,
weekly-correlation uniqueness, one-day-delay robustness, artifact overrides, gross-edge diagnostics for microstructure.

**Independent edges that survive** (one per correlation cluster): short variance after payrolls (0561), crypto cross-sectional funding carry
(0720, 0718), conditional gamma/variance (0618, 0564), trend gated by a positive curve slope (0036), industry momentum (0002), crack and
location energy spreads (0203, 0233, 0239), stock-bond-correlation risk parity (0608), VIX-gated credit carry (0359), FX carry (0256),
commodity spread reversion (0195).

**Portfolio** (equal risk, out-of-sample walk-forward P&L): Sharpe 1.45 (2024-26 incl. crypto) / 1.59 (2011-26 excl. crypto), avg corr 0.06.
At 10% vol: ~15-17%/yr, max DD -12%. At 20% vol (the 20% drawdown budget): ~31-35%/yr. +300% in 12 months needs ~8x (80% vol): bootstrap
P(+300%) 23-29% with P(drawdown > 20%) 99% and typical max DD ~-70%. Selection across ~2,000 trials means live Sharpe should be expected
well below these figures (a ~50% haircut is a reasonable prior). Results: `results/portfolio.json`, `results/passer_correlations.csv`.
