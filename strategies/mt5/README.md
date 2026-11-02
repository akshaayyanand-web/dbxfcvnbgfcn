# MT5 Expert Advisors – one per chart

| EA file | Chart (symbol names vary by broker) | Timeframe | Risk / trade | Magic |
|---|---|---|---|---|
| `BTC_Dip_v3.mq5` | BTCUSD | H2 | 1.0% | 1101 |
| `Gold_Dip.mq5` | XAUUSD | H1 | 0.5% | 1102 |
| `Gold_Asia_Breakout.mq5` | XAUUSD | H1 | 0.25% | 1103 |
| `Gold_Intraday_Momentum.mq5` | XAUUSD | H1 | 0.25% | 1104 |
| `NQ_Intraday_Momentum.mq5` | US100 / NAS100 / USTEC | H1 | 0.25% | 1105 |
| `NQ_Opening_Range.mq5` | US100 / NAS100 / USTEC | M5 | 0.5% | 1106 |
| `NQ_Dip_Grid.mq5` | US100 / NAS100 / USTEC | H1 | 0.5% per basket | 1107 |
| `SPX_Dip_Grid.mq5` | US500 / SPX500 | H1 | 0.5% per basket | 1108 |

## Install
1. MT5 → File → Open Data Folder → `MQL5/Experts/` → copy the eight `.mq5` files there.
2. Open MetaEditor (F4), open each file, press **Compile** (F7). Send any compile error back.
3. In MT5 open **eight charts** (gold three times, Nasdaq three times – one chart per EA), set each chart's timeframe as above,
   drag the EA onto it, tick **Allow Algo Trading**, and press the **Algo Trading** button in the toolbar.
4. In every EA's inputs set **InpAccountSize = your account's starting balance**. Leave the other inputs.

## What every EA does
- Enters on the close of the signal bar with the **stop (and the ORB target) on the order**.
- Time exits are automatic (4 days / 96 bars for the dip EAs, session closes for the day trades).
- **Dip grids** (`NQ_Dip_Grid`, `SPX_Dip_Grid`): buy when price closes 2 standard deviations below its 20-bar
  mean while above the 200 EMA, plus 2 equal buy-limits 1 and 2 ATR lower. All three share one hard stop
  3 ATR below the first entry, sized so the **whole basket** loses 0.5% at the stop. Once price is back at
  its mean, the limits are cancelled and the stop trails 1.5 ATR under the close (never below
  break-even). Time exit after 120 bars. These are equal-size levels, not martingale.
- **Account-level guard (shared by all EAs through MT5 global variables):** if the account is down
  `InpDailyStopPct` (4%) on the day, every EA closes its trades and stops for the day; if the account is
  down `InpMaxStopPct` (8%) from the start, every EA closes and stops for good. New trades are sized so
  they risk at most 60% of the room left before those lines.
- Session times (London / New York) are computed from the server time with daylight-saving rules.
  Live, the server offset is detected automatically; in the Strategy Tester set `InpServerGMTOffset`
  (2 for FTMO-style servers) and `InpServerUsesUSDST`.

## Passing faster (optional)
Simulated FTMO-style 2-step with **all eight EAs**, attempts started weekly. Settings were picked on 2020-22
starts and checked on 2023-25 starts. Phase 2 and the funded account always run at the defaults.

| Phase 1 settings | Pass (2020-22 / 2023-25) | Breached | Median days to funded | Funded within 3 months |
|---|---|---|---|---|
| Default: `InpRiskMultiplier 1.0`, `InpDailyStopPct 4.0` | 98% / 87% | 0% / 0% | 101 / 73 | 41% / 55% |
| **Fast: `InpRiskMultiplier 1.25`, `InpDailyStopPct 3.0`** | **91% / 82%** | **0% / 0%** | **83 / 58** | **49% / 63%** |
| 1.25 with the normal 4% daily stop | 89% / 82% | 3% / 1% | 86 / 57 | 47% / 63% |
| Faster: 1.5 with a 3% daily stop | 85% / 76% | 0% / 1% | 73 / 52 | 53% / 64% |

**Recommended for phase 1:** set `InpRiskMultiplier = 1.25` and `InpDailyStopPct = 3.0` in **every EA**. That's
about 2.5-3 weeks faster with no breaches, for ~5 points of pass rate (more attempts halted by the 8% guard).
Then set both back (`1.0` and `4.0`) for phase 2 and the funded account.

Also tested and rejected: boosting only some strategies, "house money" (boost once up 3-5%), and boosts
with a brake at -2/-3%. All were slower or caused 1-12% breaches.

## Notes
- MT5 only trades while it is running: keep the PC on or use a Windows VPS.
- Check your prop firm allows EAs and holding BTC / gold over nights and weekends.
- Run the EAs on a **demo / free-trial account for 2–4 weeks** before a paid evaluation, and compare the
  trades with the alerts from `all_in_one_alerts.pine` if you use it.
