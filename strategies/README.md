# Prop portfolio – setup guide

All scripts are TradingView Pine v6 strategies. Each one attaches its stop to the entry order and has a
safety guard that (1) sizes every trade inside the remaining daily / max-loss room and (2) closes its
positions if 80% of its daily share is used. Set **Initial capital = your account size** in every script.

Tested in Python with hour-by-hour mark-to-market on one 10% static / 5% daily account (FTMO-style,
daily limit measured from the day's opening balance), 2020 – Oct 2026. Weights were chosen on 2020-2022
data only. Backtests overstate live results; paper trade all scripts together for 2–4 weeks first.

## Preset 1 – Evaluation (highest pass rate)

| Script | Chart | Risk / trade | Daily share | Guard share |
|---|---|---|---|---|
| `btc_dip_v3.pine` | BINANCE:BTCUSDT 2h | 1.0% | 2.25 | 50 |
| `gold_dip_prop.pine` | XAUUSD or GC/MGC 1h | 0.5% | 1.25 | 50 |
| `gold_asia_breakout.pine` | XAUUSD or GC/MGC 1h | 0.25% | 0.5 | 50 |
| `nq_intraday_momentum.pine` | NQ/MNQ 1h | 0.25% | 0.5 | 50 |
| `gold_intraday_momentum.pine` | XAUUSD or GC/MGC 1h | 0.25% | 0.5 | 50 |

FTMO-style 2-step (+10% then +5%): ~89% passed, 0% breached, median ~3.8 months (the rest were halted by the
guard or still running). Funded year: median +42%, average +43%, 0 breaches in 67 windows.

## Preset 2 – Funded account (more income)

| Script | Chart | Risk / trade | Daily share | Guard share |
|---|---|---|---|---|
| `btc_dip_v3.pine` | BINANCE:BTCUSDT 2h | 1.0% | 1.65 | 60 |
| `gold_dip_prop.pine` | XAUUSD or GC/MGC 1h | 0.5% | 0.85 | 60 |
| `gold_asia_breakout.pine` | XAUUSD or GC/MGC 1h | 0.25% | 0.4 | 60 |
| `nq_intraday_momentum.pine` | NQ/MNQ 1h | 0.25% | 0.4 | 60 |
| `gold_intraday_momentum.pine` | XAUUSD or GC/MGC 1h | 0.25% | 0.4 | 60 |
| `btc_ny_momentum.pine` | BINANCE:BTCUSDT 1h | 0.5% | 0.85 | 60 |
| `eth_ny_momentum.pine` | BINANCE:ETHUSDT 1h | 0.25% | 0.45 | 60 |

Funded year: median +49%, average +48%, 0 breaches in 67 windows. Calendar years 2020-2026:
+74%, +40%, +12%, +59%, +58%, +68%, +44% (2026 to Oct).

In both presets the daily shares add up to 5% and every script's max-loss input stays at the account's full
10% as a backstop.

## Before buying an evaluation
- Confirm the firm allows holding BTC and gold positions overnight and over weekends (swing scripts hold for
  days), allows crypto CFDs (preset 2) and measures the daily limit from the opening balance.
- Topstep does not allow overnight positions: only `nq_intraday_momentum.pine` is Topstep-compliant.
- The intraday edges are thin (~0.05–0.10R per trade): use micro contracts / tight spreads.
