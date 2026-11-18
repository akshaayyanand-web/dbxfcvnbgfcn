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
Next id: **STRAT-0101** (Pairs distance trading). New batches go in `strategies/batchNNN.py`.

## Protocol (identical for every entry)
Rules and a small parameter grid are fixed in code before the run. Positions use data up to the close of day t and earn day t+1.
Parameters are picked on the first 60% of the sample (Sharpe); the next 20% is validation; the last 20% is an untouched test reported once.
Expanding walk-forward re-selects parameters each year using only past data. Costs per side: crypto 6 bp, index CFDs 1.5 bp,
metals 2 bp, oil 4 bp, FX 1 bp, Treasuries 1 bp, industry portfolios 5 bp. Books are vol-targeted to 15%/yr with gross exposure capped
at 4x (crypto 2x). Pass gate: validation Sharpe > 0, test Sharpe > 0.3, walk-forward Sharpe > 0.3, >= 30 test trades, alpha t >= 1.5,
and long-biased books must beat an equal-risk buy-and-hold of the same market. Uniqueness: walk-forward daily P&L correlation >= 0.7 with an
earlier strategy on the same market = variation (not counted).

## Batch 1 (STRAT-0001..0100, families: time-series momentum, cross-sectional momentum, dual momentum, breakout continuation,
opening-range expansion, volatility-compression breakout, trend pullback, trend exhaustion, MA regime allocation, Donchian)
- 100 entries, 259 market tests run, all on real data with costs.
- 10 entries pass the gate; 7 pass and are distinct, 3 pass but are variations (|corr| >= 0.7) of an earlier one; 43 entries are variations overall.
- Opening-range expansion (0041-0050) on NQ, SPX, gold, DAX, EURUSD, NQ/SPX: 0 of 10 pass; the plain breakout loses after costs.
- Best validated: cross-sectional/time-series momentum on US industries (walk-forward Sharpe ~0.9-1.0, test Sharpe ~0.4-0.5),
  trend/breakout gated by a positively sloped yield curve on the long multi-asset book (walk-forward Sharpe ~0.95-1.05),
  crypto volatility-compression breakout (walk-forward Sharpe 0.69, test Sharpe 0.92).
- **+300%/yr:** not reached by any entry at any leverage up to 40x. A strategy with Sharpe S can compound at most ~exp(S^2/2)-1 per
  year at full-Kelly leverage; +300% needs S >= 1.67 *and* full-Kelly drawdowns. The 7 distinct passers combined (2021-2026 overlap)
  give Sharpe 0.50: 6.6%/yr at 15% vol (max DD -23%); doubling leverage gives 11%/yr with -42% DD; 8x loses 95%.
