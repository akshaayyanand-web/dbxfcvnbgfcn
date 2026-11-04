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

**Current MT5 set (8 EAs, every one 10%+/yr at 1% risk):** BTC_Dip_v3 1.0%, Gold_Dip 0.5%, NQ_Opening_Range 0.5%,
Gold_Asia_Breakout 0.25%, Gold_Intraday_Momentum 0.25%, NQ_Dip_2h 0.25%, SPX_Dip_1h 0.25%, Oil_Dip_1h 0.15% (see
`mt5/README.md`). It replaced NQ Intraday Momentum and the two dip grids (below 10%/yr) after a 2,292-version dip
search (`tools/dip_search.py`, `tools/replace_test*.py`). Same test:
- 2-step: **94% passed, 0% breached**, median **~84 days** (2020-22 starts 95%, 2023-25 starts 92%).
- Funded year: median **+72%**, average +64%, 0/67 breaches. Max drawdown **13.7%**.
- Calendar years: 2020 +47%, 2021 +75%, 2022 +13%, 2023 +68%, 2024 +78%, 2025 +100%, 2026 +38% (to Oct).
- Caveat: the three new EAs were chosen using the whole 2020-2026 history (both halves had to be 10%+/yr and
  neighbouring settings had to work too), so live results will likely be lower. Demo first.
- Longer-hold upgrades of BTC Dip / Gold Dip (6-day holds, +30%/yr alone) caused 13-15% breaches together and were rejected.

Older results for reference (TradingView six-script preset):
Results (one account, 10% / 5% rules, guard on):
- FTMO-style 2-step (+10% then +5%): ~93% passed, 0% breached, median ~3.4 months.
- Funded year (67 rolling 12-month windows): median +57%, average +54%, 0 breaches.
- Calendar years: 2020 +37%, 2021 +58%, 2022 +22%, 2023 +45%, 2024 +71%, 2025 +90%, 2026 +32% (to Oct).
- Max drawdown 2020-2026: 13.3%.

About 2–3 new trades per weekday: gold around the London open, Nasdaq around the New York open (09:30–11:30
NY) and at 11:00 NY, BTC/gold dip signals at any time.

## TradingView backtests of each strategy
One Pine **strategy** per EA, for TradingView's Strategy Tester (defaults: $100,000, Live mode at the portfolio risk,
trades from 2020-01-01; TradingView only loads as much history as your plan allows):

| # | Script | Chart |
|---|---|---|
| 1 | `btc_dip_v3.pine` | BINANCE:BTCUSDT 2h |
| 2 | `gold_dip_prop.pine` | OANDA:XAUUSD 1h |
| 3 | `gold_asia_breakout.pine` | OANDA:XAUUSD 1h |
| 4 | `gold_intraday_momentum.pine` | OANDA:XAUUSD 1h |
| 5 | `nq_orb_prop.pine` | OANDA:NAS100USD 5m |
| 6 | `nq_dip_2h.pine` | OANDA:NAS100USD 2h |
| 7 | `spx_dip_1h.pine` | OANDA:SPX500USD 1h |
| 8 | `oil_dip_1h.pine` | OANDA:WTICOUSD 1h |

## TradingView: all 8 strategies in one indicator, with a paper account
**`all_in_one_alerts.pine`**: one indicator on one **5-minute Nasdaq chart** (OANDA:NAS100USD, real-time on free plans)
and **one alert** ("Any alert() function call"). It runs **the same 8 strategies as the MT5 EAs** and includes:
- **A paper (dummy) account** that starts at "Paper account start": every signal opens a virtual position sized by
  risk %, closed at its stop, target or time exit. The table shows balance, equity, today's P&L and every open
  position with its P&L and stop.
- **An account guard**: down 4% on the day (from that day's starting balance, daily reset at midnight Prague by
  default, like most EU prop firms) closes all paper positions, sends a "CLOSE ALL" alert and blocks new trades
  until the reset. Down 8% from the start closes everything and stops for good.
- **A news block**: no new trades 13:55-14:10 New York on Fed decision days (2026-2027 dates included, editable).
  CPI and jobs reports are at 08:30 NY, when none of the strategies can enter. A "Pause new trades" switch blocks
  entries by hand.
- **No spread filter**: TradingView has no live spread data, so that one exists only in the MT5 EAs.
Each alert lists the entries, exits (with paper P&L), skipped trades and guard actions, so you can copy the trades
onto TradingView Paper Trading or a broker demo by hand.

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
- **S&P 500 opening-range breakout** (`tools/cook4_spx_orb.py`, S&P 1-minute data 2019-2026, 16 versions): profitable on its own in both halves (e.g. 30-min range, 3R target: +15%/yr then +8%/yr at 1% risk), but ~0.5 correlated with the Nasdaq ORB. Added to the 8 EAs it lowered the pass rate (98→86-96% / 87→68-85%), cut the 2023-25 funded median from +74% to +44-69%, and several versions caused breaches. Rejected.
- **Swapping a "weak" EA for a stronger reject** (`tools/swap_test.py`): e.g. NQ dip grid → silver dip looked better
  on 2020-22 (93 vs 101 days), but 2023-25 was the same (72 vs 73 days, +73% vs +74%). Removing Gold Asia breakout
  caused 11% breaches. Its small returns come on the days the others lose. No swap.
- **The big strategy list** (`tools/cook9_strategy_list.py`; 126 versions on gold, Nasdaq, S&P, BTC, silver: MA crosses,
  Supertrend, Heikin Ashi, triple EMA, RSI/Bollinger/Stochastic/CCI/Keltner/MACD divergence, Bollinger squeeze,
  engulfing, pin bars, yesterday high/low rejection, weekly sweep, weekly-open reversion, SMT divergence, Asian
  sweep / Judas swing, Silver Bullet FVG, post-news 15-min, VWAP reversion): only 11 were positive in both halves,
  and only 3 made more than +2%/yr in both. **Every ICT/SMC-style rule lost money**: Silver Bullet -16%/yr, Judas
  swing -13%, pin bars -19%, yesterday high/low rejection -15%, SMT divergence -64%. The best was gold triple EMA
  (+5% then +22%/yr, 34% drawdown); added to the 8 EAs it was faster but caused 10% breaches. S&P Bollinger
  bounce and S&P Stochastic (both with trend) changed nothing out of sample. None added.

## Stress test of the 8 EAs (`tools/stress_test.py`)
Same 2-step test with higher trading costs than assumed (spread + commission per trade):

| Costs | 2-step pass | Breached | Median days | Funded year (median) | Per year (simple) |
|---|---|---|---|---|---|
| As tested | 93% | 0% | 88 | +60% | +50% |
| x1.5 | 90% | 0% | 92 | +53% | +45% |
| x2 | 86% | 0% | 100 | +47% | +41% |
| x3 | 70% | 7% | 97 | +34% | +32% |
| Intraday EAs x3, rest normal | 83% | 0% | 100 | +44% | +39% |

Monte Carlo (2,000 reshuffled histories in 20-day blocks so crash clusters stay together): **86% pass, 0.4% breach**,
13.6% halted by the guard, median ~95 days at normal costs; at double costs 73% pass, 4.8% breach. Treat ~85% as
the realistic pass rate, not the 93% from the single history. **Costs matter most:** use the cheapest account
(raw spread + commission / ECN, or a prop firm with tight spreads), and check that spreads are near the table in
`mt5/README.md` before going live.
- **Time-of-day momentum search** (`tools/momentum_search.py`; 2,880 versions on gold London/NY, Nasdaq, S&P, silver London/NY, oil, BTC, ETH; signal hour, exit, threshold, stop, long-only or both): 16 versions made 10%+/yr in both halves, **0 made 15%+**, and none had stable neighbouring settings (they were isolated lucky spots). The current Gold Intraday Momentum stays.
- **Breakout family search** (`tools/breakout_search.py`; 1,600 versions of 1h range breakouts on 7 markets and 5m opening ranges on Nasdaq, S&P and gold): 31 made 10%+/yr in both halves, 2 made 15%+ (both NQ opening-range variants). Inside the 8-EA account (`tools/replace_test3.py`): NQ ORB with a 3R target and entries until 13:00 dropped the 2020-22 pass rate to 86%. The 2R/13:00 version was a dead heat with the current EA (94.0% vs 93.6% pass, same speed and profit). Hold-to-close caused 6% breaches. S&P 60-min ORB instead of S&P Dip 1h cut the 2023-25 funded median from +83% to +64%. No change.

## Topstep ($50K Trading Combine)
Topstep only allows futures, positions must be flat by 15:10 CT, the $2,000 Maximum Loss Limit trails the highest
end-of-day balance, the target is $3,000 with a best-day consistency rule, and it doesn't use MT5 (bots only via its
API from your own computer, not a VPS). So the multi-day dip EAs are out. Simulation (`tools/topstep_sim.py`, whole
micro contracts, ~$1.60 fees per micro round trip, Combine started every week 2020-2025):

| Setup | Pass (2020-22 / 2023-25 starts) | Hit max loss | Median time |
|---|---|---|---|
| **NQ Opening Range only, $150 risk/trade (`topstep_nq_orb.pine`)** | **86% / 100%** | **0% / 0%** | ~8-9 months |
| NQ ORB only, $200 risk | 74% / 99% | 26% / 0% | 5-9 months |
| NQ ORB + Gold Momentum + ES ORB, $150 | 93% / 74% | 7% / 26% | ~5 months |
| NQ ORB + NQ Mom + Gold Mom + Gold Asia, $150 | 46% / 42% | 54% / 58% | 2-3 months |
| Any set at $250+ per trade | 20-50% | 50-80% | 2-5 weeks |

**Fast plan (pass in about 1-2 months, accepting resets):** `topstep_nq_orb.pine` + `topstep_es_orb.pine` +
`topstep_gold_mom.pine` + `topstep_nq_mom.pine`, each at **$400 risk per trade**. Picked from 267 combinations of 8
intraday strategies (`tools/topstep_cook.py`) on 2020-22 Combine starts, restarting after every fail:

| Starts | Funded within 1 month | 2 months | 3 months | Median trading days | Avg resets |
|---|---|---|---|---|---|
| 2020-22 (picked here) | 47% | 85% | 99% | 22 | 1.6 |
| 2023-25 (unseen) | 40% | 81% | 93% | 26 | 1.7 |

The 3-strategy version without NQ momentum: 32% / 73% / 97% on 2023-25. After passing, drop to ~$150 per trade on
the funded account (same $2,000 trailing limit).

The intraday edges are thin (~+0.05R per trade) next to a $2,000 trailing limit, so Topstep is slow if you want to
avoid failing. The FTMO-style 8-EA set (multi-day holds allowed) passes faster with a higher pass rate.
`topstep_nq_orb.pine` sizes in whole MNQ contracts and tracks the target, the trailing Maximum Loss line, the
consistency rule and a daily loss guard on the chart. Check Topstep's current rules in their Help Center first.

## Breakout (crypto-only prop firm) – tested, poor fit
Breakout Classic 1-Step: +10% target, 6% static max loss, 3% daily loss; crypto only, and bots may not be allowed
(trade the alerts by hand). Simulation (`tools/breakout_sim.py`, guard on, evaluations started weekly Oct 2020 – Sep 2025):

| Setup | Risk per trade | Pass (2020-22 / 2023-25) | Breached | Median days |
|---|---|---|---|---|
| BTC Dip v3 only | 0.75% | 97% / 100% | 0% / 0% | ~220-290 |
| BTC Dip v3 only | 1.0% | 60% / 99% | 25% / 0% | ~145-185 |
| BTC + ETH (+ SOL) dips | 0.5-1.25% | 16-54% | 9-63% | 6-70 |

Crypto moves too much for a 3% daily / 6% max limit. Safe means 7-10 months; anything faster breaches often.
The FTMO $10K 2-Step (Swing) with the 8 EAs is the better cheap option.

## FTMO 1-Step vs 2-Step with the 8 EAs (`tools/ftmo_1step_vs_2step.py`)
1-Step as reported for 2026: +10%, 3% daily loss, 10% max loss trailing the highest end-of-day balance (stops at the
start balance), best day at most 50% of positive-day profit. Risk multiplier = `InpRiskMultiplier` on all 8 EAs.

| Challenge | Risk | Pass | Breached | Stopped by guard | Median days | Funded within 60 / 90 days | Funded year (median) | Funded years breached |
|---|---|---|---|---|---|---|---|---|
| **2-Step** | **1.0** | **94%** | **0%** | 6% | **84** | 30% / 51% | **+72%** | **0/67** |
| 2-Step fast | 1.25 (+3% daily stop) | 83% | 1.4% | 16% | 68 | 36% / 58% | +72% | 0/67 |
| 1-Step | 0.5 | 100% | 0% | 0% | 114 | 17% / 33% | +31% | 5/67 |
| 1-Step | 0.6 | 91% | 6% | 4% | 93 | 25% / 43% | +27% | 39/67 |
| 1-Step | 1.0 | 64% | 18% | 18% | 44 | 42% / 57% | +13% | 56/67 |

The 1-Step's 3% daily limit and trailing max loss force the risk down to half, so it passes slower and earns about
half as much once funded. Use the 2-Step.

## Low-timeframe (5m / 15m) search (`tools/lowtf_search.py`, `tools/lowtf_portfolio.py`)
408 versions of dip buying, session breakouts and big-candle follow/fade on 5m and 15m gold, Nasdaq and S&P.
- 5m dip buying looked strong (+38-46%/yr at 1%) but collapsed at double costs (+9-10%/yr) and caused 5-14%
  breaches inside the account. Rejected. Big-candle strategies lost money.
- Nasdaq morning breakouts (20/50-bar high/low with the 200/800 EMA, stop 1 ATR, flat at the close) held up:
  15m +44% / +48%/yr at 1% risk, +27%/yr at double costs. Replacing NQ ORB with it lowered the pass rate.
  **Added as an optional 9th EA at 0.1% risk** (`NQ_Breakout_15m.mq5`): pass ~89% (vs ~94%), 0 breaches,
  funded year +59% / +93% (vs +53% / +83%), about 22 trades a month.
- **Risk-weight optimiser for the 9 EAs** (`tools/risk_weight_optimiser.py`; 200 random mixes of 0.5-1.5x each EA's
  risk, picked on 2020-22, checked on 2023-25): the best 2020-22 mixes landed at the same place on 2023-25 as the
  current weights (pass 89-92% vs 91%, 0 breaches, 69-92 days vs 76, funded +66% to +97% vs +93%), and one
  "optimised" mix breached 21 of 33 funded years on 2023-25. The current weights stay; further tuning is noise.
