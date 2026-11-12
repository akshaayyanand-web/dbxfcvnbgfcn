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

**Current MT5 set (8 EAs, every one 10%+/yr at 1% risk), fast preset since Nov 2026:** BTC_Dip_v3 0.75%,
Gold_Dip 0.625%, NQ_Opening_Range 0.625%, Gold_Asia_Breakout / Gold_Intraday_Momentum / NQ_Dip_2h / SPX_Dip_1h 0.3125%,
Oil_Dip_1h 0.1875%, max-loss stop -9.5% and a room cap (see "Fast preset" below and `mt5/README.md`). The figures in
this paragraph are for the earlier defaults (BTC 1.0%, Gold_Dip and ORB 0.5%, the next four 0.25%, oil 0.15%, stop -8%). It replaced NQ Intraday Momentum and the two dip grids (below 10%/yr) after a 2,292-version dip
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

## Fast preset: room cap + rebalanced risk (`tools/fast_preset_test.py`, Nov 2026)
Goal: pass faster while keeping 93%+ pass and 0 breaches. Picked on 2020-22 starts, checked on 2023-25.
- **Boosting after a profit cushion, a phase-2-only boost, CPPI sizing, flat 1.1-1.25x** (252 settings): all breached
  (best 92% pass, 2.8% breached). With the old defaults the account is right at the edge.
- **Why they breach:** two patterns. (1) The account is already ~7% down and a 2.5% day (mostly BTC) pushes it past 10%.
  (2) On 7 Sep 2021, BTC gapped through its stop in one hour (about -1.7R) while the account was already down on the day.
- **Fix:** a room cap that shrinks size between -7% and -10% (day-start balance), the hard stop moved from -8% to -9.5%,
  BTC trimmed to 0.75%, and the other seven EAs +25%. Of 480 settings, this one kept 0 breaches and 93%+ pass in both
  halves, and its neighbours (cap 3-8%, stop -9 to -9.5%) did too.
- **Result** (an attempt started every day): pass 96% / 95% (was 94% / 91%), median 80 / 70 days (was 89 / 77), funded
  within 60 days 31% / 39% (was 26% / 35%), funded year +58% / +91% (was +53% / +83%), 0 breaches. It also beats the
  old defaults at 1.5x, 2x and 3x costs (2x: 80% / 87% pass vs 79% / 84%).
- NQ_Breakout_15m at 0.1% on top caused 0.6% breaches, so it is now 0.05% (93% / 96% pass, 0 breaches, +64% / +97% funded).
- Not done: anything above these defaults. 1.1x more already breaches.
- **Follow-ups on top of the fast preset** (`tools/fast_preset_addons_test.py`, `tools/fast_preset_halt_test.py`, 234 settings):
  - New dip markets with the room cap (ETH, SOL, silver 1h, slower 144h gold/BTC dips, 0.1-0.3%, BTC 0.5-0.75%): only
    5 of 198 kept 93%+ / 0 breaches on 2020-22. On 2023-25, silver and the slow BTC dip breached in 9-12 of 33 funded
    years, and ETH lowered the pass rate (89-93%). None added.
  - Daily stop at 2.5-4% instead of 4%: no change. Phase 2 at 1.25x: 1.4-9% breaches. Phase 2 at 0.75x: 98% / 96%
    pass but 10 days slower. Another +10-20% on everything: breaches. The fast preset stays as it is.

## New strategy families, Nov 2026 (5m data 2019-2026, at 1% risk, costs and swaps included)
- **Calendar effects** (`tools/calendar_edges_test.py`, 44 versions):
  - Index overnight drift (16:00 to 09:30, with trend / after-down-day filters): -9 to +2%/yr once swaps are paid.
  - Turn of the month (S&P +3.8% / +0.6%) and pre-FOMC drift (+1%): about 1 trade a month, too small.
  - Gold Asia/London long: +2% in 2019-22, +24% in 2023-26. That is the 2023-26 gold rally, not an edge.
  - None added.
- **News reactions** (`tools/news_reaction_test.py`, 524 versions; 94 CPI, 94 NFP, 65 FOMC; entry 5-30 min after):
  - Following the first move loses on every market.
  - Fading Nasdaq after CPI/NFP makes about +0.2R a trade, but at ~1 trade a month that is only +1.5-4.5%/yr.
  - None added.
- **Failed breakouts (turtle soup on the previous day's high/low) and VWAP snap-backs** (`tools/reversal_test.py`, 72
  versions): -4 to +4%/yr, negative at double costs. Intraday fades don't work on these markets; breakouts do.
- **S&P 5m morning breakout** (`tools/spx_breakout_addon_test.py`): 8 neighbouring versions made 15-45%/yr in both
  halves. Added as the optional funded-account EA `SPX_Breakout_5m` at 0.1% (funded +71% / +98% vs +58% / +91%,
  0 breaches; evaluation pass 93% vs 95%).
- **Crypto timing** (`tools/crypto_timing_test.py`, 72 versions, BTC/ETH 1h 2020-2026):
  - US / Asia / Europe session drift loses (-1 to -13%/yr).
  - "CME gap fill" (fade the weekend move) loses.
  - **Following the weekend move works on BTC**: gap >2%, 1.5 ATR stop, 48h hold made +19% / +8%/yr at 1% risk, and
    every neighbouring BTC version was positive in both halves. Added as the 9th core EA `BTC_Weekend_Gap` at 0.5%
    (`tools/btc_weekend_gap_test.py`): pass 94% / 97%, 0 breaches, 70 / 66 days, funded +84% / +95% (vs 96% / 95%,
    80 / 70 days, +58% / +91%). Caveat: it lost in 2025 (-3.4%) and 2026 so far (-2.4%) at 0.5%.
- **Breakouts in other sessions** (`tools/session_breakout_test.py`, 192 versions): London, NY afternoon and Asia breakouts
  lose on Nasdaq, S&P and gold. Gold breakouts lose in every session. The edge exists only in the US morning on US indices.
- **DAX (Germany 40), Frankfurt session** (`tools/dax_test.py`, 184 versions, 1m data 2021-2026, ~6% of days missing from the
  data feed): opening-range and morning breakouts are strong (64 versions 10%+/yr in both halves). Dips are mixed.
  `DAX_Opening_Range` (30-min range, EMA50 trend, mid-range stop) was added as the 10th core EA at 0.2% (`tools/dax_addon_test.py`):
  pass 95% / 97%, 68 / 60 days, funded +93% / +109% (vs 94% / 97%, 70 / 66, +84% / +95%). The DAX 20/50-bar breakouts
  breached in funded years and were not used.
- **More DAX strategies** (`tools/dax_more_test.py`, 62 versions; `tools/dax_more_addon_test.py`):
  - US-open breakout (15:30 Frankfurt), afternoon momentum and the 09:00 gap (follow or fade): about 0 or negative.
  - Pre-market range (08:00-09:00): +34% / +38%/yr alone, but correlation 0.6 with the DAX ORB. Added on top it
    caused 0.6-2.5% breaches and 12 funded-year breaches.
  - ORB "second chance" (up to 2 trades a day): same result as the current ORB with twice the trades.
  - The current `DAX_Opening_Range` stays as it is.
- **DAX-style opening range on other markets** (`tools/world_index_test.py`, 184 versions each):
  - Nasdaq ORB with mid stop / no target / EMA50: median 0-5%/yr. Weaker than the current NQ ORB and the N-bar breakouts.
  - S&P: same picture as Nasdaq.
  - Gold at the London open: -12 to -50%/yr on 2023-26. At the NY open: about 0.
  - Gold's edge stays the dip rule. No changes.
- **Forex at the London open** (`tools/world_index_test.py` with EURUSD, EURUSD_ASIA, AUDCAD; ~530 versions): London opening
  range, Asian-range breakout and dips all lose or make under 4%/yr. FX at retail costs is not a fit.
- **Weekend-gap follow on altcoins** (`tools/altcoin_gap_test.py`): only BTC worked overall, and every coin lost in 2025 and 2026.
  `BTC_Weekend_Gap` was halved to 0.25% and put on probation (`tools/recent_period_check.py`).
- **Europe-direction filter on US breakouts** (`tools/europe_confirmation_test.py`, 2021-2026): US morning breakouts taken
  only in the direction of the DAX's 09:00-15:25 Frankfurt move. Trades with Europe were better for NQ 5m and S&P 5m
  but worse for NQ 15m (0.12R vs 0.32R against). That is inconsistent, so it was not used.
- **NQ_Opening_Range exits** (`tools/nq_orb_exit_test.py`): a 3R / 4R target or no target is +2-4%/yr better alone, but with
  the other 9 EAs it is within noise (about ±1 day, ±1% pass, ±3% funded). The DAX-style mid-range stop caused up to 4.6%
  breaches on Nasdaq. The current rules (other-side stop, 2R target) stay.
- **Drawdown brake** (`tools/drawdown_brake_test.py`, Nov 2026): attempts started in late May / early June 2026 mostly stopped at
  -9.5% (no breaches). Shrinking size from -3% (`InpRoomCapPct` 7) plus half size below -4% until back above -2% raised the
  pass rate to 100% in 2020-22, 2023-25 and 2026 starts, cut attempts that ever reached -8% from 10-32% to 0-0.1%, and kept the
  funded median (+81% / +109%). It is ~8-16 days slower on 2020-25 starts. It is now the default.
- **Negative risk:reward** (`tools/negative_rr_test.py`): small take-profit, wider stop.
  - On the DAX ORB entry, 0.25-0.5R targets win 68-80% of trades but make -10 to +2%/yr, against +43% / +29% with no target.
  - On the NQ ORB, 0.25-0.75R targets make -4 to +4%/yr, against +10% / +12% at 2R.
  - The classic 5m dip scalp (TP 0.5-1 ATR, SL 1.5-3 ATR, 1:3 to 1:4) wins 72-81% of trades but loses heavily on Nasdaq,
    gold and DAX once spreads are paid (-24 to -280%/yr at 1% risk, ~100-140 trades a month).
  - A high win rate doesn't make a strategy profitable. Rejected.
- **Breakeven and profit-lock stops** (`tools/breakeven_test.py`, on NQ ORB, DAX ORB, BTC Dip and Gold Dip): moving the stop to
  entry at +0.5R / +1R, or locking +0.25-1R after +1-2R, cuts the average loss to about -0.5R or lifts the win rate to 50%+, but lowers
  yearly profit in almost every case (e.g. DAX ORB +43% / +29% becomes +18-34% / +17-21%). The big winners first come back to entry
  before they run. Current exits kept.
- **Crypto intraday** (`tools/world_index_test.py` with BTCUSDT / ETHUSDT, Binance 5m data 2020-2026, 184 versions each):
  - BTC opening ranges and US-morning breakouts: -54% to +3%/yr on 2023-26. London-open versions: -6% to -164%/yr.
  - ETH 15m breakout: +32% / +24%/yr, but -14%/yr at double costs.
  - Rejected.
- **ETH dips with the drawdown brake** (`tools/eth_dip_addon_test.py`): EMA200 / EMA50 versions at 0.1-0.2% speed passing up by
  4-12 days and lift the funded median to +111-123%. But they breach on 0.1-1.9% of attempts: crash days hit the BTC and ETH dips
  together (correlation 0.5). Rejected under the 0-breach rule.
- **One EA with 5+ trades a day** (`tools/high_frequency_test.py`): N-bar trend breakouts traded all session on 1m / 3m / 5m on
  Nasdaq, S&P, DAX and gold (192 versions). 55 versions reached 5+ trades a day; **all 55 lose** (-130% to -290%/yr at 1% risk on
  2023-26) once spreads are paid. The busiest version that is positive in both halves and at double costs trades 1.3 times a day
  (Nasdaq 5m, 50-bar, EMA800, 2 ATR stop). No single EA reaches 5 trades a day profitably. The 12 EAs together average ~5.6.
- **Breakout Pack** (`MT5_EAs/pack/Breakout_Pack.mq5`, `tools/pack_addon_test.py`): one EA running six morning breakouts on four
  markets from one chart, about 5.3 trades a weekday. It is the same logic as the single EAs plus a Nasdaq 5m breakout at 0.05%
  (100% pass, 0 breaches, funded +119% together with the other 7 EAs). The NQ 5m breakout breached at 0.1% and above, and the DAX
  5m breakout breached on up to 17% of attempts (rejected).
- **Variations of the best EAs** (`tools/variants_test.py`, `tools/variants_combo_test.py`; added one at a time to the 12 EAs at 0.05-0.15%):
  - Safe alone at 0.05%: four DAX ORB versions (60-min range; 15- or 30-min range on 5m; EMA20 filter), BTC 1h dip and BTC 2h EMA200 dip.
  - Not safe even alone: Gold Dip EMA200 versions (2.7-14% breaches), SPX 20-bar breakout (0.7%), and NQ 15m 50-bar breakout (2026 near-misses).
  - Stacked together, the safe ones breached on 0.3-3.6% of attempts.
  - One variant added as an optional EA: `BTC_Dip_EMA200_2h` (0.05%, ~3 days faster, funded +118%).
- **BTC funding rates** (`tools/btc_funding_test.py`, Binance perpetual funding 2020-2026):
  - As a filter on BTC_Dip_v3: dips entered at the highest 20% of funding averaged 0.01R in 2020-22 but 0.35R in 2023-26, from
    only 43 trades. Not reliable enough to block trades.
  - As a signal on its own (buy when 24h funding < 0, hold 96h): +9% / +10%/yr at 1% risk, ~3 trades a month. Too small, and an
    MT5 EA would need live funding data from Binance through WebRequest.
  - Not used.
- **Oil and silver opening ranges** (`tools/oil_silver_orb_test.py`, hourly data 2016-2026, first-hour range at the NYMEX /
  London / NY opens, 48 versions):
  - Best oil version: +6% / +10%/yr at 1% risk, ~10 trades a month, +6%/yr at double costs.
  - Silver: never positive in both halves.
  - Too small. Rejected.
- **Asian-range breakouts on faster charts and on Nasdaq** (`tools/world_index_test.py` with XAUUSD_ASIA / USATECHIDXUSD_ASIA):
  - Gold Asia range on 5m / 15m: best +6% / +6%/yr at 1% risk, weaker than the current H1 Gold_Asia_Breakout (~+13%/yr).
  - The same idea on Nasdaq (00:00-07:00 London range, trade until 14:00 London): best +15% / +13%/yr, but +4%/yr at double
    costs and weak neighbours.
  - Both rejected.
- **DAX ORB exit time** (`tools/dax_exit_time_test.py`): closing at 19:00 / 20:30 / 21:55 instead of 17:25 Frankfurt gave
  +38% / +24%, +40% / +22% and +47% / +29%/yr vs +43% / +29%. The results go down and then up again, so this is noise. 17:25 stays.
- **Weekly opening range** (`tools/weekly_orb_test.py`): Monday's range traded Tuesday-Thursday, exit Friday, on 8 markets
  (96 versions, 2016-2026):
  - BTC: +30%/yr in 2016-21 but only +8%/yr since mid-2021.
  - Gold: +6-8%/yr.
  - Indices, oil and silver: ~0-3%/yr.
  - Nothing reached 10%/yr in both halves. Rejected.
- **Phase-2-only risk boost with the drawdown brake** (`tools/phase2_boost_test.py`, 12 EAs):
  - 1.25x in Phase 2: 16-22% breaches. 1.5x: 10-17%. 2x: 28-42%.
  - The brake stops slow slides toward -10%, but not a single bad day hitting the 5% daily limit.
  - Phase 2 stays at 1.0x.
- **DAX ORB on narrow-range mornings** (`tools/dax_range_width_test.py`, `tools/dax_narrow_addon_test.py`): breakouts after the
  narrowest 25% of opening ranges (threshold set on 2021-22 only: range < 0.21x daily ATR) averaged +0.73R in 2021-22 and +0.43R
  in 2023-26. Wide-range days: +0.01R / +0.13R. The effect is real, but an extra position on those days (0.1-0.3%) caused
  0.1-1.1% breaches next to the 12 EAs. Not added. The weekday pattern was noise.
- **DAX ORB on narrow days only, at higher risk** (`tools/dax_narrow_filter_test.py`; narrowest half, threshold from 2021-22):
  - At the same 0.2%: no gain (83 / 70 / 57 days, funded +114% vs 86 / 68 / 59, +116%).
  - At 0.3-0.4%: 0.1-0.8% breaches.
  - The DAX EA keeps trading every day.
- **Gold Asia breakout rules on other markets** (`tools/asia_breakout_other_markets_test.py`, hourly 2016-2026):
  - Only gold works: +15% / +11%/yr, 1 losing year.
  - Silver, S&P, Dow, Russell, oil and BTC: negative in at least one half, 4-8 losing years each.
  - Nasdaq: -1% / +16%/yr, 4 losing years.
  - The effect is specific to gold, which trades heavily in Asia. Rejected.
- **PAXG weekend move as a gold signal** (`tools/paxg_weekend_gold_test.py`; PAXG is tokenised gold that trades 24/7; 309 weekends,
  2020-2026):
  - The weekend PAXG move is mostly already in gold's Sunday reopen gap (correlation 0.41).
  - It only weakly predicts the next 24-48h (correlation 0.12 / 0.07).
  - Following moves over 0.3%: +0.00R in 2020-22 vs +0.25R in 2023-26, the gold bull market, so inconsistent. Over 1%: only 18 trades.
  - It would also need PAXG prices inside MT5. Rejected.
- **Nikkei 225 opening range, PRELIMINARY** (`tools/world_index_test.py JPNIDXJPY`, only Jan 2021 to May 2023 downloaded so far):
  - Tokyo 09:00 opening range, no trend filter, mid-range stop: positive every year so far (+10% to +24%/yr at 1% risk), and
    +9-13%/yr at double costs. Breakout versions failed at double costs.
  - It trades 19:00-20:00 New York time, a slot no current EA uses.
  - Waiting for 2023-2026 data (blocked by the data server's rate limit) before any portfolio test or EA.
- **Crypto hour-of-day effects** (`tools/crypto_hour_of_day_test.py`): no hour had the same sign every year for BTC or ETH
  (2020-2026). Typical hourly drift is 1-3 bp, against ~6 bp cost per trade. Rejected.
- **Monte Carlo of the 12 EAs** (`tools/monte_carlo_12_test.py`): 97.6% pass, 0% breached, 2.4% still open after ~1.4 years,
  median ~68 days.
- **Volatility-regime switching** (`tools/volatility_regime_test.py`; regime = yesterday's 20-day Nasdaq volatility vs its 1-year
  median):
  - Dip EAs earn more in volatile markets and breakout EAs in calm ones, in both halves.
  - Shifting risk toward the favoured side (x1.25/0.75 or x1.5/0.5) caused 3-26% breaches: volatile periods are crash periods.
  - Only cutting the weaker side (x0.75 / x0.5) stayed breach-free, but was slower with a lower funded year (+81-95% vs +107%).
  - Not used.
- **"Crash catcher" intraday short** (`tools/crash_short_test.py`): short Nasdaq / S&P once the day is down 1.5-2.5% from the
  open, hold to the close.
  - About breakeven (-2% to +2%/yr at 1% risk).
  - As a hedge: correlation +0.12 with the 12 EAs, and only +0.06% on their 30 worst days. It does not offset dip losses.
  - With the hedge, 1.1x / 1.25x risk on the 12 EAs still breached on 5-23% / 33-42% of attempts. Rejected.
  - Note: even +10% risk breaches, so the 12 EAs are already at their safe limit.
- **What breaks at 1.1x risk** (`tools/breach_anatomy_test.py`): all 237 breaching attempts fall on 11 hours. Gold_Dip is the
  biggest loser on most of them (-2.0% to -4.7% of the account in one day at 1x): a multi-day trade that was well in profit
  falls back to its stop during a gold crash (e.g. 2026-01-30, 2024-11-25).
  - The simulation counts open profit given back during the day as daily loss, the stricter reading of the daily-loss rule.
    Sources disagree on FTMO's exact measure, so ask FTMO before relying on extra headroom.
  - Risk stays at 1.0x.
- **FTMO's exact daily-loss rule** (`tools/ftmo_balance_rule_test.py`): the floor is the midnight balance minus 5% of the starting
  capital, so open losses carried overnight count. With it, the 12 EAs passed 75 / 86 / 92% (brake on balance), not 100%: many
  attempts slid to the −9.5% stop as the −4% guard closed underwater dip trades. Moving the drawdown brake to the day-start
  **equity** gives 89 / 96 / 98% pass, 0 breaches, 88 / 84 / 59 days. Now the default in all EAs. Earlier pass rates (100%)
  were based on an equity floor and were optimistic.
- **Fixed-dollar TP $1,000 / SL $2,000 with a big lot** (`tools/fixed_dollar_tp_sl_test.py`; Nasdaq and gold 1m; 6,000 entries each,
  random or with the trend):
  - Tiny distances (= a huge lot): the spread is 30-100% of the target, the win rate drops to 30-54%, and each trade loses
    $400-1,100 on average.
  - Wider distances: the win rate rises to ~66%, about the 66.7% needed to break even before costs, so the average is ~$0.
  - Rejected: it has no edge, and at 2% risk per trade, two or three losses in a day hit FTMO's 5% daily limit.
- **Small targets on the entries of all 10 EAs** (`tools/small_target_on_ea_entries_test.py`): TP at 0.25-0.75R with the same SL,
  or the SL doubled with TP at 1x / 2x the old risk (1:4 / 1:2).
  - Win rates rise to 57-85%, but every version makes about -14% to +4%/yr.
  - Current exits make +8% to +43%/yr.
  - Even the best entries lose their edge when winners are capped. Small-target / fixed-dollar TP is rejected for good.
- **Topstep / Lucid funded in 1-2 weeks** (`tools/topstep_two_week_test.py`; $50K: $3,000 target, $2,000 EOD trailing max loss,
  50% consistency, flat daily, micro contracts; an attempt every trading day 2020-2026, with $50 resets until funded):
  - Best: the 4 Topstep scripts (NQ ORB, NQ momentum, gold momentum, ES ORB) at $500-1,000 per trade. Funded within
    10 trading days (2 weeks) 20-24% of the time, within 20 days 47-51%, median 20-22 trading days, average cost incl. resets $190-370.
  - Adding more strategies (breakouts, Gold Asia) made it worse: more trades mean more ways to hit the tight $2,000 trailing loss.
    A daily stop changed little.
  - The fixed $1,000 TP / $2,000 SL style gives roughly a 2-3% chance per account of getting funded and paid.
- **80% chance of getting funded, fastest** (`tools/funded_80pct_test.py`; $50K EOD trailing, 50% consistency; LucidDaily prices
  $90 + $120 per retry):
  - One account, no resets: 80%+ only with NQ ORB + ES ORB + Gold mom at $150/trade (84%), median ~110 trading days.
  - Resetting until funded: 80% are funded within ~37-39 trading days (~8 weeks) at $400-500/trade (median 22-23 days),
    average cost $280-410.
  - 80% within 2 weeks is not reachable with real edges under these rules.
- **One-try fast pass** (`tools/fast_pass_sizing_test.py`; 50K and LucidFlex 25K with $1,250 or $1,500 targets; fixed-dollar
  sizing vs a % of the room above the max-loss line):
  - The single-attempt pass rate within 10 trading days never exceeded ~16%. The 25K was no easier.
  - Room-based sizing (15% of room) slightly improves the pass rate for the time taken: 58% in a median 41 days, vs 47% / 38 days at $200 fixed.
  - Real edges here give either a high single-attempt pass rate (84%, ~5 months) or speed (~30%, ~2 weeks), never both.
- **"Close any trade at +$1,000"** (`tools/take_profit_1000_test.py`, $100K account, all 10 EAs, simple sum per year):
  - $58,200/yr with the current exits vs $32,800/yr with the rule, -44%.
  - BTC Dip: $15.3k -> $4.3k. Gold Dip: $9.5k -> $0.5k.
  - Their biggest wins ($12-18k) are what pay for the losers.


## Nov 2026: new markets from RoboForex exports (US30, XAGUSD, GBPJPY) and a timeframe sweep
`tools/timeframe_sweep_test.py`. Split each data set in two halves; a strategy must be positive in both.
- **US30** (Apr 2025-Nov 2026): no timeframe works. ORB, breakouts and dips lose on M15/M30/H1/H2 alike (best: +3 R/yr).
- **XAGUSD** (Jun 2025-Nov 2026): dips look huge in the 2025 rally (+65 to +165 R/yr) but fall to +2-14 R/yr after it;
  only 11-22% of versions are positive in both halves. Lower timeframes (M15) did best, but this is one rally, not an edge.
- **GBPJPY** H1 2020-2026: the London ORB that worked on M5 in 2025-26 fails on H1 over 6 years (0% of versions positive).
  Dips on H2 are positive in both halves for 94% of versions, but small: +2 to +6 R/yr. Not worth a slot.
- SOL_Dip_1h (Binance 2020-2026, +26 R/yr both halves) remains the only new add-on worth running.

## Nov 2026: one-day-pass futures evals (LucidPro / Apex / Tradeify Growth style), 50K: +$3,000 target, $2,000 EOD trailing
- BTC+SOL dip, one trade at the full $2,000 risk (TP 1.5R): 42% win, median 7 days to funded with resets, 2.5 accounts on average
  (`tools/futures_one_shot_test.py`). But the trades take ~14 h to resolve and most futures firms require flat by the close: not usable.
- **NQ Opening Range, all-in each day** (risk = room to the trailing floor, target = what is left to +$3,000; `tools/futures_allin_test.py`):
  median 3.8 days, 78% within 7 days, 94% within 14 days, 2.24 accounts on average (42% on the first). Gold Asia Breakout: 3.8 days, 2.6 accounts.
  At 75% of the room: median 12.7 days, 2.4 accounts. Topstep / LucidFlex have a 50% best-day consistency rule, so this does not pass there in one day.

## Nov 2026: 50-lot Nasdaq scalp (+$300 ≈ 6 points) – loses
`tools/scalp_50_lots_test.py`: take-profit 3/6/10 points vs stop 5-40 points, spread 1-2 points, on NQ ORB entries and 6,000 random
New York entries, 1m data 2020-2026. **0 of 48 combinations made money**: −$42 to −$174 per trade at 50 lots. Win rates reach 79-91%
with wide stops, but always below the break-even win rate the spread creates. Tiny targets turn the spread into the whole game.
Follow-up search (`tools/scalp_search_test.py`, 288 versions: ORB / 1m breakout / 5-min thrust entries, spread 0.5-1 pt, market or
limit entries, TP 3-10, SL 3-20): **0 profitable** with fair fills. Closest: limit entry 1 pt better, TP 6 / SL 20, 0.5-pt spread:
−0.4 pt (−$20 at 50 lots) per trade, 76% wins. Only "best-case" fills (target counted first whenever target and stop sit in the
same minute) look profitable, and only with a 3-point stop: 1m bars cannot settle that; it needs tick data.

## Nov 2026: "pump" strategies (ride or fade sudden 5/15-minute moves) – no robust edge
`tools/pump_test.py`, 64 versions per market. Fading pumps loses everywhere (median −12 to −126 R/yr). Riding them: SPX, gold and BTC
have no version positive in both halves. NQ: riding 15-minute top-3% pumps shows +47 / +19 R/yr (stop 0.5x pump, 60-min exit) but only
+0.04R per trade; with a 2-point spread instead of 1 it falls to +25 / −0.2. Too thin to trade; NQ_Breakout_15m already holds the
part of this momentum effect that survives costs.
**Tick check (`tools/tick_scalp_test.py`, RoboForex .USTECHCash ticks Nov 6-12 2026, 900 entries, real bid/ask fills):** every
TP 3-10 / SL 3-20 combination loses 2.0-3.0 points per trade (−$100 to −$150 at 50 lots). The broker's New York spread is 2.1 points
(1.6-3.5), larger than assumed. The 3-point-stop "best case" was an illusion: a 3-point stop sits inside spread + noise and wins only
7-16% of the time. The 1m-bar "fair" count matched the tick truth; the best-case count did not.

## Nov 2026: fast scalps with bigger targets (held 15-60 minutes) – all lose
`tools/fast_scalp_test.py`: NQ opening drive, ORB 09:30-09:45 break and 5m breakout50 EMA800 entries, target 0.5-2R, forced exit after
15/30/60 min, cost 2.5 points (RoboForex tick spread 2.1 + slippage). **0 of 36 positive** (−5 to −77 R/yr). The same ORB and breakout
entries are profitable in the core EAs only because winners are held for hours (to 2R or the close): cutting them short removes the edge.
