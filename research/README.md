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

## Post-review update (response to the 200-strategy review)
1. **Preservation** - every committed result version is in `results/archive/`; runs are append-only (`results/runs/<run_id>.jsonl`, each record carries
   run_id and code commit); the workbook sheet *Result history* shows all versions per strategy with the reason for each change.
2. **Duplicates** - `dup_review.py`: conceptual mechanism class + core/filter layer first, then weekly P&L correlation within the class
   (|corr| >= 0.9 = duplicate regardless). 499 tested entries -> ~118 mechanism classes (*Duplicate review* sheet).
3. **STRAT-0053** - independent code `independent/vcb.py` + Coinbase/Bitstamp/perp data (`independent/compare_0053.py`, `independent/sensitivity_0053.py`).
   Reproduces (P&L corr 0.995); found an engine bug (cash rate charged per calendar day x 252/365 too high on crypto) - fixed and crypto tests re-run.
   Verdict: broad-based but small, cost-sensitive, collapses with a 1-day execution delay, fails all multiple-testing corrections.
4. **Multiple testing** - `multiple_testing.py`: deflated Sharpe (raw / cleaned / MAD benchmarks), BH-FDR, HLZ t>3, Holm and Bonferroni on
   skew/kurtosis-adjusted Sharpe z, PBO (CSCV) per family. No strategy reaches DSR > 0.95; ~20 tests in ~11 classes survive Bonferroni over all 2,673 trials + delay test.
5. **Reproducibility** - `repro/fetch_data.py` (all sources), `repro/data_manifest.csv` (18,095 raw files, SHA-256), `repro/snapshot/` (25 MB processed data in git),
   `repro/snapshot.py import` + `repro/verify.py` re-run strategies from the snapshot alone (exact match).
6. **New mechanisms STRAT-1001..1033** (`strategies/batch011.py`, `batch011s.py`): see sheet *New mechanisms (1001+)*. NFCI timing (1009) rejected after
   real-time ALFRED vintages (1032) removed its alpha; betting-against-beta (1020) and the random-forest industry ranker (1013) survive.
7. **Portfolio** (7 surviving mechanism classes): out-of-sample Sharpe 1.65 (2011-26) / 1.91 (1995-26); ~17-20%/yr at 10% vol; +300% needs ~8x leverage with
   ~-75% drawdowns. Nothing is promoted to live trading on backtests alone.
