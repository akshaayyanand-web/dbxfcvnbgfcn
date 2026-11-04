# MT5 Expert Advisors – one per chart

| EA file | Chart (symbol names vary by broker) | Timeframe | Risk / trade | Magic |
|---|---|---|---|---|
| `BTC_Dip_v3.mq5` | BTCUSD | H2 | 1.0% | 1101 |
| `Gold_Dip.mq5` | XAUUSD | H1 | 0.5% | 1102 |
| `Gold_Asia_Breakout.mq5` | XAUUSD | H1 | 0.25% | 1103 |
| `Gold_Intraday_Momentum.mq5` | XAUUSD | H1 | 0.25% | 1104 |
| `NQ_Opening_Range.mq5` | US100 / NAS100 / USTEC | M5 | 0.5% | 1106 |
| `NQ_Dip_2h.mq5` | US100 / NAS100 / USTEC | **H2** | 0.25% | 1109 |
| `SPX_Dip_1h.mq5` | US500 / SPX500 | H1 | 0.25% | 1110 |
| `Oil_Dip_1h.mq5` | WTI / USOIL / XTIUSD (RoboForex: search "WTI" or "OIL") | H1 | 0.15% | 1111 |
| `NQ_Breakout_15m.mq5` (optional 9th) | US100 / NAS100 / USTEC | **M15** | 0.1% | 1112 |

Every EA makes 10%+ a year at 1% risk (2020-2026). **Optional 9th EA, `NQ_Breakout_15m`**: about one extra trade per
weekday at 0.1% risk. With it the 2-step pass rate is ~89% instead of ~94% (0 breaches either way), the median time
is a bit shorter, and the funded year is higher (+59% / +93% vs +53% / +83% for 2020-22 / 2023-25 starts). The older `NQ_Intraday_Momentum`, `NQ_Dip_Grid` and `SPX_Dip_Grid`
(below 10%) were replaced and are kept in `retired/` for reference. Don't run them together with the new set.

## Step 1 – Get MT5 and a demo account
- Use the MT5 that your prop firm gives you (FTMO, The5ers, etc. each have a download plus free-trial/demo logins),
  or install MT5 from metatrader5.com and open a demo account with any broker that has **gold, US100, US500, oil (WTI) and BTC**.
- Check the symbol names in **Market Watch** (Ctrl+M → right-click → *Show All*): e.g. `XAUUSD`, `US100.cash`,
  `US500.cash`, `BTCUSD`. Any name works; the EAs trade whatever chart they're attached to.

## Step 2 – Install the EAs
1. MT5 → **File → Open Data Folder** → open `MQL5` → `Experts`. Copy the eight `.mq5` files into it.
2. Press **F4** (MetaEditor). In the Navigator on the left, open each file under *Experts* and press **F7** (Compile).
   The bottom panel must say `0 errors`. If it shows errors, screenshot them and send them back.
3. Back in MT5, right-click **Expert Advisors** in the Navigator → **Refresh**. The eight EAs appear.

## Step 3 – Run them live (demo first)
1. Open **eight charts** (File → New Chart): gold ×3, US100 ×2, US500 ×1, oil ×1, BTC ×1. Set each chart's timeframe
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

**What each EA should roughly show on its own** (Python test 2020 – Oct 2026, at the default risk; MT5 will differ a
little because of broker prices, spreads and compounding):

| EA | Risk | Trades / month | Per year (at that risk) | Per year at 1% risk | Max DD | 2022 | 2024 | 2025 |
|---|---|---|---|---|---|---|---|---|
| BTC_Dip_v3 | 1.0% | 2.7 | +19.9% | +19.9% | 9.7% | -1.4% | +23.9% | +21.5% |
| Gold_Dip | 0.5% | 6.5 | +9.1% | +18.1% | 13.4% | +8.6% | +19.5% | +25.5% |
| NQ_Opening_Range | 0.5% | 22 | +6.9% | +13.8% | 14.8% | +9.4% | +7.6% | +14.3% |
| Gold_Asia_Breakout | 0.25% | 28 | +3.2% | +12.8% | 9.2% | +0.7% | +0.8% | +3.0% |
| Gold_Intraday_Momentum | 0.25% | 8.3 | +2.9% | +11.8% | 5.3% | +1.4% | -2.0% | +3.1% |
| NQ_Dip_2h | 0.25% | 4.4 | +3.3% | +13.4% | 4.9% | -2.3% | +2.6% | +0.8% |
| SPX_Dip_1h | 0.25% | 8.9 | +2.9% | +11.7% | 8.0% | -3.0% | +6.9% | 0.0% |
| Oil_Dip_1h | 0.15% | 4.7 | +2.2% | +14.9% | 4.7% | +0.1% | +0.6% | +3.3% |

Individually most look small. The ~+65-70%/yr comes from running all eight together on one account, because
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
  down `InpMaxStopPct` (8%) from the start, every EA closes and stops for good. New trades are sized so
  they risk at most 60% of the room left before those lines.
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

## Passing faster (optional)
Simulated FTMO-style 2-step with **the eight EAs above**, attempts started weekly 2020-2025. Phase 2 and the funded
account always run at the defaults.

| Phase 1 settings | Pass | Breached | Median days to funded | Funded within 90 days |
|---|---|---|---|---|
| **Default: `InpRiskMultiplier 1.0`, `InpDailyStopPct 4.0`** | **94%** | **0%** | **84** | 51% |
| `InpRiskMultiplier 1.25`, `InpDailyStopPct 3.0` | 83% | 1.4% | 68 | 58% |
| `InpRiskMultiplier 1.25`, `InpDailyStopPct 4.0` | 79% | 5.7% | 64 | 55% |
| `InpRiskMultiplier 1.5`, `InpDailyStopPct 3.0` | 76% | 0.4% | 56 | 58% |

**Recommended: keep the defaults (1.0 and 4.0) in every phase.** With this set the default is already ~84 days, and
every boost costs pass rate (more attempts halted at -8%) and adds a small breach risk. If you boost anyway, use a
3% daily stop, in phase 1 only.

## Notes
- MT5 only trades while it is running: keep the PC on or use a Windows VPS.
- Check your prop firm allows EAs and holding BTC / gold over nights and weekends.
- Run the EAs on a **demo / free-trial account for 2–4 weeks** before a paid evaluation, and compare the
  trades with the alerts from `all_in_one_alerts.pine` if you use it.
