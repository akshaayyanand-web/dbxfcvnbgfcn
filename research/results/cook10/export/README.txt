pack21_daily_pnl.csv - simulated daily P&L of the 21-EA The5ers High Stakes pack ($10K, 3x preset risks)
- Rows: server days (UTC+2), 2020-04-01 to 2026-10-30 (first date where all data sources overlap; crypto EAs start later where noted in the risk table).
- Columns: one per EA, BOOK_total (sum), BOOK_worst_intraday (lowest point of the book inside the day vs the day's start, from hourly marks).
- Units: % of the STARTING balance (not compounded). Costs included (spread, commission where modelled, swap).
- Built from backtested trades, not live fills. NO account guard applied: the real pack stops a day at -4% and shrinks size near the limits,
  so raw sums here are higher-variance than the live pack (the -5.1% / -5.5% worst days would be cut at about -4.3% by the guard).
- Annual figures are simple sums of daily %; the challenge/funded simulations (75%/yr funded) include the guard, the payout buffer and payouts.
pack21_risk_table.csv - risk per trade (% of balance) each EA uses in the 10K pack, and its first trade day in the file.
