# Result archive (append-only)
Every committed version of results.jsonl is kept here; nothing is deleted.
- results_781b93f.jsonl - batch 1 (STRAT-0001..0100), first committed run: total returns (no cash deduction), benchmark gate on.
- results_790bf26.jsonl - batches 1-6 after the excess-of-cash correction (all funded assets measured over the cash rate).
- results_942e10e.jsonl - batches 1-10 (all 1,000 entries).
- batch1_first_run_log_pre_benchmark_gate.txt - console log of the very first batch-1 run (before the buy-and-hold gate); its JSON was overwritten
  before the first commit, so only this log survives.
Why results changed between versions is recorded per strategy in the workbook sheet "Result history".
Policy from now on: every run appends to results/runs/<run-id>.jsonl; results.jsonl is rebuilt from runs and never edited in place.
