# NQ ORB All-In: one-day-pass EA (MT5)

**For evaluations with no consistency rule and no minimum days only.** It blows about 58% of the accounts it runs on, on purpose:
you buy a new account and run it again. Never run it on a funded account.

## What it does
- Chart: Nasdaq 100 (US100 / NAS100 / USTEC / NQ / MNQ), **M5**. Same entry as the core NQ_Opening_Range EA: range 09:30-09:45
  New York, first M5 close outside it until 11:30, stop at the other side of the range, one trade a day, flat 15:55 New York.
- **Size:** risks `InpRoomShare`% (default 100%) of the room left above the max-loss line, minus `InpSafety` ($75).
  With a daily loss limit set, it also stays inside that.
- **Take-profit:** exactly what is still needed to reach the target (+ commission). On a fresh 50K: risk ~$1,925, target $3,000.
- **Max-loss line:** `InpMaxLoss` under the highest end-of-day balance, never above the start balance (`InpTrailingEOD = false` for a static line).
- Closes everything at the max-loss line, and stops for good once the balance reaches the target.

## Settings for a 50K ($3,000 target, $2,000 trailing drawdown)
`InpStartBalance 50000`, `InpProfitTarget 3000`, `InpMaxLoss 2000`, `InpDailyLoss 0` (or the firm's limit), `InpMaxLots` = the
firm's contract limit, `InpCommission` = your round-turn commission per lot.

## Backtest (Python, 2020-2026, a start every 3 days, `tools/futures_allin_test.py`)
| Room risked | Median days to funded | ≤7 days | ≤14 days | ≤30 days | First account passes | Accounts on average |
|---|---|---|---|---|---|---|
| **100% (default)** | **3.8** | **78%** | **94%** | 100% | 42% | 2.2 |
| 75% | 12.7 | 37% | 54% | 79% | 36% | 2.4 |

## Before using it
- **Platform:** futures firms (Topstep, Lucid, Apex, Tradeify) run on Tradovate / Rithmic / NinjaTrader, not MT5. This EA needs an MT5
  account whose evaluation has no consistency rule and no minimum days. For a futures firm it has to be rebuilt for NinjaTrader 8.
- Topstep and LucidFlex have a 50% best-day consistency rule: a one-day pass is not possible there.
- A daily loss limit smaller than the max loss makes it much slower (the first trade needs ~3R instead of 1.5R).
- Check that the firm allows EAs / automated trading on the evaluation.
- Not compiled or tested in MT5 here: compile it in MetaEditor and run it in the Strategy Tester and on a demo first.
