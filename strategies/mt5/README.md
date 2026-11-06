# MT5 Expert Advisors – one per chart

| EA file | Chart (symbol names vary by broker) | Timeframe | Risk / trade | Magic |
|---|---|---|---|---|
| `BTC_Dip_v3.mq5` | BTCUSD | H2 | 0.75% | 1101 |
| `Gold_Dip.mq5` | XAUUSD | H1 | 0.625% | 1102 |
| `Gold_Asia_Breakout.mq5` | XAUUSD | H1 | 0.3125% | 1103 |
| `Gold_Intraday_Momentum.mq5` | XAUUSD | H1 | 0.3125% | 1104 |
| `NQ_Opening_Range.mq5` | US100 / NAS100 / USTEC | M5 | 0.625% | 1106 |
| `NQ_Dip_2h.mq5` | US100 / NAS100 / USTEC | **H2** | 0.3125% | 1109 |
| `SPX_Dip_1h.mq5` | US500 / SPX500 | H1 | 0.3125% | 1110 |
| `Oil_Dip_1h.mq5` | WTI / USOIL / XTIUSD (RoboForex: search "WTI" or "OIL") | H1 | 0.1875% | 1111 |
| `BTC_Weekend_Gap.mq5` (core, **on probation**) | BTCUSD (must trade at weekends) | H1 | 0.25% | 1114 |
| `DAX_Opening_Range.mq5` (**10th core EA, Nov 2026**) | GER40 / DE40 / DAX40 | **M15** | 0.2% | 1115 |
| `NQ_Breakout_15m.mq5` (optional) | US100 / NAS100 / USTEC | **M15** | 0.05% | 1112 |
| `SPX_Breakout_5m.mq5` (optional, funded account) | US500 / SPX500 | M5 | 0.1% | 1113 |

**`BTC_Weekend_Gap` halved to 0.25% (6 Nov 2026), on probation** (`tools/altcoin_gap_test.py`, `tools/recent_period_check.py`).
Following the weekend move lost money in **2025 and 2026 on every coin tested** (BTC -6.5 / -4.9 R a year, ETH -13 / -7,
XRP -25 / -2, SOL, BNB, ADA, DOGE, LINK, LTC all negative). The effect seems to have changed. With the 10 core EAs, on starts
from mid-2024 to 2025, pass rates are 100% with or without it and it still saves ~2-4 days (59 vs 63), but calendar 2025 / 2026
are better without it (+140% / +38% vs +131% / +34%). At 0.25% it keeps most of the evaluation speed (61.9 vs 59.6 days on
2023-25 starts, 96% pass) and halves the cost if the edge is gone. If it is still losing by mid-2027, set `InpRiskPct` to 0.

**New 10th core EA, `DAX_Opening_Range`** (`tools/dax_test.py`, `tools/dax_addon_test.py`, DAX 1m data 2021-2026).
It takes the 09:00-09:30 Frankfurt range, then the first 15-minute close beyond it between 09:30 and 12:00, in the
direction of the daily EMA(50). Stop at the middle of the range, no target, flat at 17:25 Frankfurt. About 11 trades
a month, at 03:30-11:25 New York time, when the other EAs are mostly quiet (correlation 0.06). On its own at 1% risk it made
+42%/yr (2021-22) and +29%/yr (2023-26), and +28%/yr at double costs. 64 of 184 DAX versions were 10%+/yr in both
halves; Frankfurt breakouts are the strongest new market found. DAX dips were mixed and are not used.

| | 9 core EAs | **10 core EAs (with DAX)** |
|---|---|---|
| 2-step pass (2020-22 / 2023-25 starts) | 94% / 97% | **95% / 97%** |
| Breached | 0.1% / 0% | 0.1% / 0% |
| Median days to funded | 70 / 66 | **68 / 60** |
| Funded within 60 days | 38% / 45% | **40% / 49%** |
| Funded year (median) | +84% / +95% | **+93% / +109%**, 0 breaches |

Keep it at 0.2%: at 0.25% the pass rate falls to 92% / 95% with 0.6% breaches. It needs a GER40 M15 chart; the EA
converts the server clock to Frankfurt time itself, using the same EU/UK daylight-saving rule. (The 2020 tests run without DAX, since the data starts in 2021.)

**New 9th core EA, `BTC_Weekend_Gap`** (`tools/btc_weekend_gap_test.py`). CME bitcoin futures close from Friday 17:00 to
Sunday 18:00 New York, but spot BTC keeps trading. When BTC has moved more than 2% over that weekend, the EA trades
**in the direction of the move** at the Sunday reopen, with a 1.5 ATR stop and a 48h exit. About 1-2 trades a month.
The popular "CME gap fill" idea (trading back toward Friday's close) **loses** money. The follow-through wins: 34%
winners, average +0.87R, correlation with the other 8 EAs 0.03. Added to the 8 EAs (fast preset, attempt started every day 2020-2025):

| | 8 EAs | **9 EAs with BTC_Weekend_Gap** |
|---|---|---|
| 2-step pass (2020-22 / 2023-25 starts) | 96% / 95% | 94% / **97%** |
| Breached | 0% | 0.1% / 0% |
| Median days to funded | 80 / 70 | **70 / 66** |
| Funded within 60 days | 31% / 39% | **38% / 45%** |
| Funded year (median) | +58% / +91% | **+84% / +95%**, 0 breaches |
| Costs x2: pass / days / funded | 80% / 87%, 83 / 76 d, +44% / +71% | 82% / 89%, 70 / 70 d, +66% / +77% |
| Max drawdown 2020-2026 | 15.1% | 13.3% |

On its own at 0.5%: 2020 +5.5%, 2021 +12.4%, 2022 +14.2%, 2023 +11.9%, 2024 +5.8%, **2025 -3.4%, 2026 -2.4%** (to Oct).
The last two years were losing, so watch it. If it keeps losing through 2027, remove it. Your broker must quote BTC at
weekends (FTMO does), and the EA needs its own BTCUSD H1 chart, separate from BTC_Dip_v3 (H2).

Every EA makes 10%+ a year at 1% risk (2020-2026). **The defaults are the "fast preset" (Nov 2026)**: BTC trimmed to
0.75%, every other EA +25%, the max-loss stop moved from -8% to -9.5%, and a new **room cap** (`InpRoomCapPct` 3) that
shrinks every new trade once the day starts more than 7% down (full size at -7%, 0 at -10%). Compared with the old
defaults (simulated 2-step, an attempt started every day 2020-2025): pass **96% / 95%** (was 94% / 91%), 0 breaches,
median **80 / 70 days** (was 89 / 77), funded year **+58% / +91%** (was +53% / +83%), for 2020-22 / 2023-25 starts.
If you already run the EAs, re-copy all files and re-attach them so the new defaults load (MT5 keeps old input values).
**Optional 9th EA, `NQ_Breakout_15m`**: about one extra trade per weekday, now at **0.05%** risk (0.1% caused
breaches with the fast preset). With it: pass 93% / 96%, 0 breaches, median 78 / 71 days, funded +64% / +97%.
**Optional funded-account add-on, `SPX_Breakout_5m`** (Nov 2026, `tools/spx_breakout_addon_test.py`): the S&P version of
the morning breakout (50-bar high/low, EMA200, 2 ATR stop, flat 15:50 NY), ~26 trades a month at 0.1%. On its own
it made +47%/yr (2019-22) and +20%/yr (2023-26) at 1% risk, and +15%/yr at double costs. Next to the 8 EAs:
funded year **+71% / +98%** (vs +58% / +91%), 0 breaches, also at double costs. In the evaluation the pass rate is
93% instead of 95-96% and it's only ~2 days faster, so add it once funded. Don't run it at more than 0.1%:
at 0.15-0.2% the pass rate falls to 83-90%. The older `NQ_Intraday_Momentum`, `NQ_Dip_Grid` and `SPX_Dip_Grid`
(below 10%) were replaced and are kept in `retired/` for reference. Don't run them together with the new set.

## Step 1 – Get MT5 and a demo account
- Use the MT5 that your prop firm gives you (FTMO, The5ers, etc. each have a download plus free-trial/demo logins),
  or install MT5 from metatrader5.com and open a demo account with any broker that has **gold, US100, US500, oil (WTI) and BTC**.
- Check the symbol names in **Market Watch** (Ctrl+M → right-click → *Show All*): e.g. `XAUUSD`, `US100.cash`,
  `US500.cash`, `BTCUSD`. Any name works; the EAs trade whatever chart they're attached to.

## Step 2 – Install the EAs
1. MT5 → **File → Open Data Folder** → open `MQL5` → `Experts`. Copy the ten core `.mq5` files into it (plus any optional ones).
2. Press **F4** (MetaEditor). In the Navigator on the left, open each file under *Experts* and press **F7** (Compile).
   The bottom panel must say `0 errors`. If it shows errors, screenshot them and send them back.
3. Back in MT5, right-click **Expert Advisors** in the Navigator → **Refresh**. The EAs appear.

## Step 3 – Run them live (demo first)
1. Open **ten charts** (File → New Chart): gold ×3, US100 ×2, US500 ×1, oil ×1, BTC ×2 (H2 for BTC_Dip_v3, H1 for BTC_Weekend_Gap), GER40 ×1 (M15). Set each chart's timeframe
   from the table above (`NQ_Opening_Range` is M5; `BTC_Dip_v3` and `NQ_Dip_2h` are H2).
2. Drag one EA onto each chart. In the window that opens:
   - **Common** tab: tick **Allow Algo Trading**.
   - **Inputs** tab: set `InpAccountSize` = your account's starting balance (e.g. 100000). Leave the rest.
3. Press the **Algo Trading** button in the top toolbar (it turns green). Each chart shows a small hat icon
   top-right. If the icon is grey, algo trading is off.
4. Check the **Experts** tab (Ctrl+T → Experts) for start-up messages or warnings ("attach this EA to a … chart"
   means the timeframe is wrong).
5. Save the setup: **File → Profiles → Save As…** so all 8 charts reopen together.
6. MT5 only trades while it's open: keep the PC on 24/5 or use a Windows VPS (many prop firms give one free).

## Step 4 – Backtest one EA yourself
1. Press **Ctrl+R** (Strategy Tester). Choose **Expert**: e.g. `Gold_Dip`.
2. **Symbol** = the chart's symbol, **Timeframe** = from the table, **Date**: Custom, e.g. 2020-01-01 to today.
3. **Modelling**: *1 minute OHLC* (fast, good enough) or *Every tick based on real ticks* (slow, most accurate).
4. **Deposit** = the same as `InpAccountSize` (e.g. 100000 USD). **Leverage** = your firm's (e.g. 1:30 or 1:100).
5. **Inputs** tab (bottom): set `InpAccountSize` = the deposit. For the session-based EAs (Asia breakout, both
   momentum EAs, Opening Range), set `InpServerGMTOffset` to your broker's winter GMT offset (FTMO and most
   EU brokers: 2) and `InpServerUsesUSDST = true` if their clock shifts with US daylight saving (most do).
   Everything else stays as it is.
6. Press **Start**. Use the **Backtest**, **Graph** and **Trades** tabs for results. Tick *Visual mode* to watch it trade.
7. The first run downloads history and can take a while. If a symbol has little history (common for BTC and
   indices on some brokers), the test only covers what the broker has.

**What each EA should roughly show on its own** (Python test 2020 – Oct 2026, at the default risk, room cap not included; MT5 will differ a
little because of broker prices, spreads and compounding):

| EA | Risk | Trades / month | Per year (at that risk) | Per year at 1% risk | Max DD | 2022 | 2024 | 2025 |
|---|---|---|---|---|---|---|---|---|
| BTC_Dip_v3 | 0.75% | 2.7 | +14.9% | +19.9% | 7.3% | -1.0% | +17.9% | +16.1% |
| Gold_Dip | 0.625% | 6.5 | +11.4% | +18.1% | 16.8% | +10.8% | +24.4% | +31.9% |
| NQ_Opening_Range | 0.625% | 22 | +8.6% | +13.8% | 18.5% | +11.8% | +9.5% | +17.9% |
| Gold_Asia_Breakout | 0.3125% | 28 | +4.0% | +12.8% | 11.5% | +0.9% | +1.0% | +3.8% |
| Gold_Intraday_Momentum | 0.3125% | 8.3 | +3.6% | +11.8% | 6.6% | +1.8% | -2.5% | +3.9% |
| NQ_Dip_2h | 0.3125% | 4.4 | +4.1% | +13.4% | 6.1% | -2.9% | +3.2% | +1.0% |
| SPX_Dip_1h | 0.3125% | 8.9 | +3.6% | +11.7% | 10.0% | -3.8% | +8.6% | 0.0% |
| Oil_Dip_1h | 0.1875% | 4.7 | +2.8% | +14.9% | 5.9% | +0.1% | +0.8% | +4.1% |

Individually most look small. The ~+70%/yr comes from running all eight together on one account, because
they rarely lose on the same days. A losing year for one EA is normal (see the columns).

**Limits of MT5's tester:** it runs one EA at a time, so it can't reproduce the combined portfolio or the shared
account guard (each test has its own). The news block is also off in the tester (no calendar). To see the
combined result, run all eight on a demo account, which is the real test anyway.

## What every EA does
- Enters on the close of the signal bar with the **stop (and the ORB target) on the order**.
- Time exits are automatic (4 days / 96 bars for the dip EAs, session closes for the day trades).
- **Dip EAs** (BTC, Gold, NQ 2h, S&P 1h, Oil 1h): buy a sharp short-term drop (low RSI) while price is above its
  trend EMA, skip after a crash (big 30-day fall), stop 2 x ATR on the order, and exit after a fixed number of bars.
- **Account-level guard (shared by all EAs through MT5 global variables):** if the account is down
  `InpDailyStopPct` (4%) on the day, every EA closes its trades and stops for the day; if the account is
  down `InpMaxStopPct` (9.5%) from the start, every EA closes and stops for good. New trades are sized so
  they risk at most 60% of the room left before those lines.
- **Drawdown brake (Nov 2026 default): `InpRoomCapPct` 7, `InpHalfBelowPct` 4, `InpHalfUntilPct` 2.** Size starts shrinking
  once the day starts 3% below the starting balance (full size at -3%, zero at -10%). In addition, all EAs trade at **half size**
  once a day starts 4% down, until a day starts no more than 2% down again (shared through the `PP_HALF` global variable).
  Tested (`tools/drawdown_brake_test.py`), with an attempt started every weekday:

  | | Old brake (shrink below -7%) | **New brake** |
  |---|---|---|
  | 2-step pass (2020-22 / 2023-25 / 2026 starts) | 95% / 96% / 86% | **100% / 100% / 100%** |
  | Attempts that ever fell below -8% | 10% / 11% / 32% | **0% / 0.1% / 0%** |
  | Median days to funded | 72 / 62 / 57 | 89 / 70 / 53 |
  | Funded year: median / worst (2023-25 starts) | +109% / -9.6% (stopped) | +109% / **+23%** |

  It costs about 8-16 days of speed in 2020-25, but it removes almost every near-miss with the 10% line.
  **When you start a new account, delete the old guard variables first:** in MT5 press **F3** (Global Variables) and delete
  every `PP_...` entry. Otherwise a halt or half-size flag from the previous account carries over.
- **Room cap details** (`InpRoomCapPct`, `InpFirmMaxLossPct` 10): when the day starts more than 7% below the starting
  balance, every new trade is shrunk in proportion to the room left before the firm's 10% line (e.g. 2/3 size at
  -8%, 1/3 at -9%). This is what lets the account recover from a bad stretch instead of breaching. If your firm's
  max loss isn't 10%, set `InpFirmMaxLossPct` to it and `InpMaxStopPct` to 0.5 below it.
- **News rule (funded accounts):** `InpNewsBlockMin` (default 2) stops any EA opening a new trade within
  2 minutes of a high-impact USD event (CPI, jobs report, Fed, ...), using MT5's built-in economic calendar.
  It only works live, since the Strategy Tester has no calendar. Set it to 0 to switch it off, or match it to
  your firm's rule. Stops can still be hit during news; check how your firm treats that.
- **Spread filter:** `InpMaxSpreadPct` (default 15). If the spread is more than 15% of a new trade's stop distance
  (for the dip grids, of one grid spacing), the EA **waits** and retries on every tick for up to 15 minutes, entering
  as soon as the spread is normal again. Only after that does it skip. This matters most at the daily reopen
  (18:00 New York), when Gold Dip and the BTC/index dips often trigger and spreads are briefly very wide. Those
  trades are good ones (Gold Dip's rollover-hour trades averaged +1.15R), so waiting keeps them but at a normal
  spread. The intraday EAs never trade in that window. Waits are logged in the Experts tab. Set 0 to switch it off.
- Session times (London / New York) are computed from the server time with daylight-saving rules.
  Live, the server offset is detected automatically; in the Strategy Tester set `InpServerGMTOffset`
  (2 for FTMO-style servers) and `InpServerUsesUSDST`.

## Passing faster
The defaults are already the fastest setup that kept 93%+ pass and 0 breaches in every test (`tools/fast_preset_test.py`).
Simulated FTMO-style 2-step, an attempt started **every day** 2020-2025; phase 2 and funded use the same settings.

| Setup | Pass (2020-22 / 2023-25) | Breached | Median days to funded | Funded within 60 days | Funded year |
|---|---|---|---|---|---|
| Old defaults (BTC 1%, others as before, stop -8%) | 94% / 91% | 0% | 89 / 77 | 26% / 35% | +53% / +83% |
| Old defaults + room cap, stop -9.5% | 98% / 94% | 0% | 90 / 78 | 26% / 35% | +53% / +83% |
| **New defaults (fast preset)** | **96% / 95%** | **0%** | **80 / 70** | **31% / 39%** | **+58% / +91%** |
| Fast preset with double costs | 80% / 87% | 0.2% / 0% | 83 / 76 | 24% / 33% | +44% / +71% |
| Old defaults with double costs | 79% / 84% | 0.3% / 0% | 92 / 84 | 22% / 29% | +38% / +67% |

Full history with the new defaults: 2020 +50%, 2021 +88%, 2022 +16%, 2023 +58%, 2024 +82%, 2025 +114%,
2026 +37% (to Oct); funded-year median +77%, 0/67 breaches.

**Turbo (optional, evaluation only): `InpRiskMultiplier` 1.5 and `InpDailyStopPct` 2.5 on every EA.** No new files
needed. Tested in `tools/turbo_preset_test.py` (attempt every 3 days, 2020-22 / 2023-25 starts):

| Setup | Pass | Breached | Median days (passers) | Funded within 30 days | within 45 days |
|---|---|---|---|---|---|
| Default (fast preset) | 95% / 95% | 0% | 79 / 70 | 9% / 10% | 21% / 27% |
| 1.5x phase 1 only (phase 2 at 0.5x), daily 2.5 | 79% / 87% | 2% / 2% | 68 / 61 | 13% / 14% | 25% / 31% |
| **Turbo: 1.5x both phases, daily 2.5** | **53% / 71%** | **12% / 9%** | **37 / 37** | **21% / 28%** | **33% / 40%** |
| **Safer turbo (below)** | **57% / 74%** | **2% / 3%** | **40 / 41** | **18% / 23%** | **32% / 40%** |
| 2x both phases, daily 2.5 | 53% / 51% | 22% / 20% | 23 / 22 | 36% / 36% | 42% / 43% |
| 2.5x both phases, daily 2.5 | 41% / 39% | 44% / 44% | 15 / 14 | 36% / 34% | 39% / 37% |

**Safer turbo** (`tools/turbo_safer_test.py`, best of 432 settings with a median of 42 days or less, picked on 2020-22):
on every EA set `InpDailyStopPct` 3.0, `InpRoomCapPct` 5 and `InpHalfBelowPct` 0 (turbo was tested without the half-size mode). Phase 1: `InpRiskMultiplier` 1.5. Phase 2: `InpRiskMultiplier`
1.125. It is about as fast as Turbo, and breaches fall from ~10% to ~2-3%: size starts shrinking at -5% instead of -7%,
and Phase 2 (only +5% needed) runs a bit smaller. Neighbouring settings (daily 2-3%, room cap 3-5%) gave 55-57% / 59-75% pass with 0.6-3.4% breaches.
Boosting BTC less than the others, or easing off near the Phase 1 target, didn't help.

No setting reached 70-80% pass **and** a ~30-day median: about 35% of attempts funded within 30 days is the ceiling,
and getting there costs half the attempts. Once funded, set every EA back to 1.0 and 4.0.

**Outside turbo, don't raise `InpRiskMultiplier` above 1.0.** Going from these defaults to 1.1x already caused 3% breaches, and
1.5x caused 7-17%. Every breach came from days like 7 Sep 2021, when BTC gapped through its stop in one hour while
the account was already down on the day.

## Notes
- MT5 only trades while it is running: keep the PC on or use a Windows VPS.
- Check your prop firm allows EAs and holding BTC / gold over nights and weekends.
- Run the EAs on a **demo / free-trial account for 2–4 weeks** before a paid evaluation, and compare the
  trades with the alerts from `all_in_one_alerts.pine` if you use it.
