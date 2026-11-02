# Prop portfolio – setup guide

All scripts are TradingView Pine v6 strategies. Each one attaches its stop to the entry order and has a
safety guard that (1) sizes every trade inside the remaining daily / max-loss room and (2) closes its
positions if 80% of its daily share is used. Set **Initial capital = your account size** in every script.
The script defaults below already match the main preset.

Tested in Python with hour-by-hour mark-to-market on one 10% static / 5% daily account (FTMO-style,
daily limit from the day's opening balance), 2020 – Oct 2026. Weights were chosen on 2020-2022 windows
only. Backtests overstate live results; paper trade all scripts together for 2–4 weeks first.

## Main preset (evaluation AND funded)

| Script | Chart | Risk / trade | Daily share | Guard share |
|---|---|---|---|---|
| `btc_dip_v3.pine` | BINANCE:BTCUSDT 2h | 1.0% | 1.8 | 60 |
| `gold_dip_prop.pine` | XAUUSD or GC/MGC 1h | 0.5% | 0.9 | 60 |
| `gold_asia_breakout.pine` | XAUUSD or GC/MGC 1h | 0.25% | 0.45 | 60 |
| `nq_intraday_momentum.pine` | NQ/MNQ 1h | 0.25% | 0.45 | 60 |
| `gold_intraday_momentum.pine` | XAUUSD or GC/MGC 1h | 0.25% | 0.45 | 60 |
| `nq_orb_prop.pine` | NQ/MNQ **5-minute** | 0.5% | 0.95 | 60 |

Daily shares add up to 5%; every max-loss input stays at the account's full 10% as a backstop.

**Upgrade (MT5 only): add the two dip grids** `NQ_Dip_Grid.mq5` and `SPX_Dip_Grid.mq5` (H1, 0.5% per basket
worst case; see `mt5/README.md`). Same test, with the six above:
- 2-step: 93% passed, 0% breached, median **~88 days** (was ~101).
- Funded year: median +60%, average +64%, 0/67 breaches. Max drawdown 15.9% (was 13.3%).
- Calendar years: 2020 +52%, 2021 +69%, 2022 +21%, 2023 +55%, 2024 +77%, 2025 +104%, 2026 +31% (to Oct).
- A gold version, or 0.75% per basket, caused breaches (5% of evaluations), so it is left out.
- Caveat: the same rules lost money on the Dow and Russell, so the edge is real but thin. Demo it first.

Results (one account, 10% / 5% rules, guard on):
- FTMO-style 2-step (+10% then +5%): ~93% passed, 0% breached, median ~3.4 months.
- Funded year (67 rolling 12-month windows): median +57%, average +54%, 0 breaches.
- Calendar years: 2020 +37%, 2021 +58%, 2022 +22%, 2023 +45%, 2024 +71%, 2025 +90%, 2026 +32% (to Oct).
- Max drawdown 2020-2026: 13.3%.

About 2–3 new trades per weekday: gold around the London open, Nasdaq around the New York open (09:30–11:30
NY) and at 11:00 NY, BTC/gold dip signals at any time.

## Only 1–2 indicators allowed on your TradingView plan?
Use **`all_in_one_alerts.pine`** instead of the six scripts: one indicator on one **5-minute Nasdaq chart**
(e.g. OANDA:NAS100USD – real-time on free plans) and **one alert** ("Any alert() function call").
It runs all six strategies with the same rules (other symbols/timeframes are pulled in from closed bars,
so nothing repaints) and messages every entry with direction, price, STOP, risk in $, size and exit
time, plus a reminder when a time exit is due. Place the orders at your prop firm with the stop from
the alert. It cannot see your fills or P&L, so apply the safety rule yourself: stop for the day at -4%,
stop everything at -8% from the start.

## Optional add-ons (not in the main preset)
`btc_ny_momentum.pine` and `eth_ny_momentum.pine` (crypto New York-session momentum) also held up out of
sample, but with the main preset in place they add little and lower the evaluation pass rate. If you add
them, shrink the other daily shares so the total stays at 5%.

## Before buying an evaluation
- Confirm the firm allows holding BTC and gold positions overnight and over weekends (the dip scripts hold
  for days) and measures the daily limit from the opening balance.
- Topstep does not allow overnight positions: only `nq_intraday_momentum.pine` and `nq_orb_prop.pine` are
  Topstep-compliant.
- The intraday edges are thin (~0.05–0.10R per trade): use micro contracts / tight spreads.

## Martingale (tested, rejected)
Tested in `tools/martingale_sizing_test.py` (sizing up after losses on the six scripts) and
`tools/grid_martingale_test.py` (classic grid EA: add 2x size every 1–2 ATR against you, close the basket
1 ATR past the average, on 12 markets: gold, silver, Nasdaq, S&P, Dow, Russell, oil, BTC, ETH, SOL, XRP, DOGE).
- On the six scripts: x2 after each loss (up to 1-2-4-8) → 2-step pass 32%, 54% breached, 62/67 funded years
  breached. x1.5 → 57% pass, 20% breached. Scaled down until it stops breaching, it gives the same result as
  flat sizing at the same average risk (100% pass but ~210 days, +24%/yr = flat at 0.5x). It adds nothing.
- Grid martingale: lost money on almost every market and setting (median year down to -170% of the start
  balance). The best case was silver with a trend filter (+14% median year), and it still passed only 38%.
  Pass rates were 0–38%, mostly under 10%, with breaches of up to 95% when the basket stop was past the 10% limit.
Keep flat sizing.

## "Kavach Grid" (tested from its sales-page description, rejected)
Replica in `tools/kavach_grid_replica.py`: a Z-score fade on M15 with a 3-test trend gate, a frozen grid
basket, a hard stop and a take-profit that tightens as levels fill.
- Gold and Nasdaq M15 2019-2026: **0 of 64 settings profitable, even with zero costs**. The best was
  -4%/yr with a 98% win rate and a 35% drawdown. The trend gate halves the losses but doesn't remove them.
- Bigger take-profits (`tools/kavach_bigger_tp.py`, 1-12 ATR): the win rate falls as fast as the wins grow,
  so the result stays at zero or below.
- Hybrid with what worked here (`tools/kavach_dip_hybrid.py`): long-only dips above the 200 EMA on Nasdaq H1,
  3 levels, exit when price is back at its 20-bar mean, 48h time exit. About +5%/yr at 2% worst case per
  basket, positive in both 2019-22 and 2023-26, 12-17% drawdown. As a 7th script
  (`tools/kavach_portfolio_addon.py`) it is uncorrelated (≈0) but only adds +1-3% to the funded median, and
  it doesn't change the pass rate (93%) or the time to pass (~100 days).
- Loss caps and bigger wins (`tools/dipgrid_exits.py`): tighter stops, early cuts and fewer levels all made it
  worse. Trailing 1.5 ATR once price is back at its mean made it better: Nasdaq +7.7%, S&P +11.1%, gold +8.1%/yr
  at 2% worst case, 2016-2026. Nasdaq + S&P at 0.5% each became the two MT5 dip-grid EAs (see the upgrade above).

## Also tested against the 8-EA setup (rejected)
- **Different exits on BTC Dip / Gold Dip** (`tools/dip_exit_variants.py`): exiting at the mean or trailing
  cut the yearly return from +19.9% (BTC) / +18.1% (gold) to between -1% and +8%. Their profit comes from dips
  that turn into multi-day rallies, and the 4-day time exit already lets those run. Keep the time exits.
- **New candidates** (`tools/cook1_candidates.py`, 1% risk, needed to be positive in both 2020-22 and 2023-26):
  S&P 500 intraday momentum (+7%/yr in 2020-22, then -1 to -2%/yr), Dow momentum (negative), silver
  Asia breakout (+9% then -9%), silver London momentum (mixed), BTC / ETH dip grid (negative). None passed.
- **Round 2** (`tools/cook2_candidates.py`): daily RSI-2 dips on S&P / Nasdaq / Dow / Russell are positive in both
  halves but tiny (+0.2 to +1.2%/yr at 1% risk, few trades). Adding them changes nothing (same pass rate and
  speed, +1-3% funded). Gold opening-range breakout: 5 of 6 variants lose; the one winner (08:20 NY, 30 min,
  +5.7%/yr) caused 10% breaches in the portfolio. Nasdaq gap fade: +4-5%/yr in 2020-22, negative since 2023.
- **Kavach on forex (EURUSD, AUDCAD M15, 2019-2026)**: 0 of 64 settings profitable at normal costs. AUDCAD does
  mean-revert (52/64 profitable with zero costs), but even at very tight prop costs (0.8 pip AUDCAD, 0.5 pip
  EURUSD all-in) the best setting is about 0%/yr, and none were positive in both halves.
- **Round 3** (`tools/cook3_candidates.py`): short "rally fades" in downtrends (BTC, gold, Nasdaq, S&P) all lose,
  -1 to -11%/yr. The dip rules on new markets (ETH, SOL, S&P, Nasdaq, silver, oil, ...) are often profitable
  alone (silver 1h +11%/yr, Nasdaq 1h +10%/yr), but adding them to the 8 EAs causes **~10% breaches in 2020-22**,
  even at 0.25% risk. Every long dip loses on the same crash days (March 2020, 2022), so more of them
  stacks the risk on one day. Only oil and Russell were breach-free, and they add nothing. None added.
- **Losing-trade autopsy** (`tools/loser_autopsy.py`): every trade of the 8 EAs was tagged with the conditions at
  entry (volatility regime, 200-day trend, 1-day and 5-day move, distance from the 20-day high, BTC/Nasdaq
  volatility, weekday, hour). "Bad conditions" were picked on 2020-22 only and checked on 2023-26. Only 5 were
  found (about what chance alone produces), and 4 of them turned profitable on the unseen data. Blocking them
  lifted the 2020-22 funded median from +54% to +65%, but did nothing on 2023-25 (+74% vs +73%), so that gain
  was curve-fitting. Every strategy is profitable per trade in both halves; the losses are random, not a fixable
  pattern. No filters added.
- **Portfolio risk overlays** (`tools/cook5_risk_overlays.py`): volatility targeting that also sizes **up** in calm
  markets caused 8-10% breaches in 2020-22 (it was large going into the crash). Down-only volatility targeting was
  breach-free but slower (108 vs 101 days, 85 vs 73 on 2023-25) and earned less (funded +63% vs +74% on 2023-25).
  Equity-curve filters (pause or halve a strategy after a losing 30/60/90 days) made everything worse: pass
  rates down to 44-98%, the time to pass up to 2x, funded returns roughly halved. These strategies tend to
  recover right after a bad stretch, so pausing them skips the rebound. None added.
- **News filters** (`tools/news_filter_test.py`; 65 Fed decisions from federalreserve.gov, 94 jobs reports and
  94 CPI releases dated from the 8:30 ET volume spike): trades near news are **profitable** on average. Blocking
  entries 1h around news changed nothing; blocking news days or the 24h before news made things worse (2023-25
  funded +59% / +71% vs +74%, and slower). Only ~6 trades in 6.7 years opened or closed within 2 minutes of news,
  so the EAs now carry a 2-minute compliance block (`InpNewsBlockMin`) for funded-account news rules,
  not as a performance filter.
- **Kavach loss caps / win-focused exits on forex** (`tools/kavach_exits.py`, 450 settings each on EURUSD and AUDCAD M15): every setting lost money; the best was -6.5%/yr (AUDCAD) and -7.8%/yr (EURUSD). Kavach is rejected on every market tested.
- **Pairs trading** (`tools/cook6_pairs.py`; Nasdaq/S&P, gold/silver, BTC/ETH, S&P/Dow, Nasdaq/Russell; fade a 2-2.5 sigma spread over 5 or 20 days): truly uncorrelated with the 8 EAs (0.03-0.12), but every pair lost money over the full period (-1.7 to -52%/yr at 1% risk). These spreads trend more than they snap back. None added.
- **Round 8** (`tools/cook7_trend_breakouts.py`): Donchian trend following (20/10 and 55/20 day, long + short) lost
  money on 6 of 7 markets. Volatility breakout made +11-16%/yr in 2020-22 but faded to ~0-5% since 2023. NR7
  breakouts made +0-3%/yr. Every add-on that was positive in both halves still caused ~8-12% breaches in 2020-22. None added.

## Safety margin of the 8 EAs (`tools/worst_days_check.py`)
Worst days for the 8 EAs (no guard, measured on equity, which is stricter than FTMO's balance-based daily rule):
2021-09-07 -4.98% (BTC flash crash; BTC Dip gave back open profit and was stopped), 2024-11-25 -4.64% (Gold Dip),
2020-09-02 -4.49%, 2024-03-12 -4.38%. So on a few days a year-plus apart the account gets close to the 5% daily
limit, and the account guard (stop for the day at 4%, or 3% in phase-1 fast mode) is what keeps it safe. This
is why every extra strategy, even a small uncorrelated one, created breaches. **Don't raise risk above the
tested settings, and don't run other EAs or manual trades on the same account.**
- **Profit lock on BTC Dip / Gold Dip** (`tools/profit_lock_test.py`; move the stop to +0.5-2R once a trade is +2-4R): the worst day stayed at -5.0% in 4 of 5 versions (the BTC flash crash blew through the locked stop). The one version that cut it to -4.1% (lock +1R at +2R) cost Gold Dip 8%/yr and the funded median fell from +74% to +58% (2023-25). Others added 1-3% breaches. Rejected; the blocked add-ons stay blocked.
