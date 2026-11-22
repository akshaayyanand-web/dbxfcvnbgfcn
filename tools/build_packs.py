"""Build preconfigured EA packs (risk + guard inputs baked into each file) for FTMO 2-step, CTI Instant and FundedSquad 1-Step Flex."""
import os, re, shutil, sys, zipfile
SRC = {"btc": "MT5_EAs/BTC_Dip_v3.mq5", "gdip": "MT5_EAs/Gold_Dip.mq5", "nq2h": "MT5_EAs/NQ_Dip_2h.mq5", "spx1h": "MT5_EAs/SPX_Dip_1h.mq5",
       "oil1h": "MT5_EAs/Oil_Dip_1h.mq5", "gasia": "MT5_EAs/Gold_Asia_Breakout.mq5", "gmom": "MT5_EAs/Gold_Intraday_Momentum.mq5",
       "orb15": "MT5_EAs/NQ_Opening_Range.mq5", "nqbo15": "MT5_EAs/NQ_Breakout_15m.mq5", "daxorb": "MT5_EAs/DAX_Opening_Range.mq5",
       "spxbo5": "MT5_EAs/SPX_Breakout_5m.mq5", "btcgap": "MT5_EAs/BTC_Weekend_Gap.mq5", "sol": "MT5_EAs/optional/SOL_Dip_1h.mq5",
       "goldvwap": "MT5_EAs/optional/Gold_VWAP_Pullback_5m.mq5", "spxfade": "MT5_EAs/optional/Open_Fade_1m.mq5", "nikkei": "MT5_EAs/optional/Nikkei_Breakout_5m.mq5",
       "solrev": "MT5_EAs/optional/SOL_Revert_5m.mq5", "btcrev": "MT5_EAs/optional/BTC_Revert_5m.mq5", "daxpm": "MT5_EAs/optional/DAX_Premarket_15m.mq5"}
SYMB = {"btc": "BTCUSD", "gdip": "XAUUSD", "nq2h": "US100", "spx1h": "US500", "oil1h": "USOIL/WTI", "gasia": "XAUUSD", "gmom": "XAUUSD", "orb15": "US100",
        "nqbo15": "US100", "daxorb": "GER40/DE40", "spxbo5": "US500", "btcgap": "BTCUSD", "sol": "SOLUSD", "goldvwap": "XAUUSD", "spxfade": "US500",
        "nikkei": "JP225", "solrev": "SOLUSD", "btcrev": "BTCUSD", "daxpm": "GER40/DE40", "nqfade": "US100", "xrprev": "XRPUSD"}
def bake(text, risk, guards, magic=None, extra=(), moff=0):
    text = re.sub(r"input double InpRiskPct = [0-9.]+;", f"input double InpRiskPct = {risk};", text)
    for name, val in guards.items(): text = re.sub(rf"(input \w+\s+{name}\s*=\s*)[^;]+;", rf"\g<1>{val};", text)
    if magic: text = re.sub(r"input long   InpMagic   = \d+;", f"input long   InpMagic   = {magic};", text)
    if moff: text = re.sub(r"input long   InpMagic   = (\d+);", lambda m: f"input long   InpMagic   = {int(m.group(1)) + moff};", text)
    for a, b in extra: assert a in text, a; text = text.replace(a, b)
    return text
def build(name, risks, G, guard_vals, header, funded=None, moff=0):
    out = f"MT5_EAs/packs/{name}"; shutil.rmtree(out, ignore_errors=True); os.makedirs(out); rows = []
    for k, r in risks.items():
        if k == "nqfade":
            t = bake(open(SRC["spxfade"]).read(), r, G, 1121 + moff, (("input int    InpLookMin = 15;", "input int    InpLookMin = 10;"), ("input double InpMovePts = 25;", "input double InpMovePts = 98;"))); fn = "NQ_Open_Fade_1m.mq5"
        elif k == "xrprev":
            t = bake(open(SRC["btcrev"]).read(), r, G, 1126 + moff, (("input double InpMovePct  = 6.97;", "input double InpMovePct  = 14.1;"),)).replace('"BTC Revert"', '"XRP Revert"'); fn = "XRP_Revert_5m.mq5"
        else: t = bake(open(SRC[k]).read(), r, G, moff=moff); fn = os.path.basename(SRC[k])
        open(f"{out}/{fn}", "w").write(t); tf = re.search(r"#define REQUIRED_TF PERIOD_(\w+)", t).group(1)
        rows.append((fn, SYMB[k] + " " + tf, r, funded.get(k) if funded else None))
    g = open("MT5_EAs/guards/Account_Equity_Guard.mq5").read()
    for nm, v in guard_vals.items(): g = re.sub(rf"(input \w+\s+{nm}\s*=\s*)[^;]+;", rf"\g<1>{v};", g)
    open(f"{out}/Account_Equity_Guard.mq5", "w").write(g)
    lines = [header, "", f"{'EA file':32s} {'Chart':20s} InpRiskPct" + ("   funded InpRiskPct" if funded else "")]
    lines += [f"{fn:32s} {ch:20s} {r:<10}" + (f"   {fr}" if funded else "") for fn, ch, r, fr in sorted(rows, key=lambda x: -x[2])]
    lines += ["", "Account_Equity_Guard.mq5 -> any one extra chart (watches the whole account). Its settings: " + ", ".join(f"{a}={b}" for a, b in guard_vals.items()),
              "Already set inside every EA: " + ", ".join(f"{a}={b}" for a, b in G.items()), ""]
    open(f"{out}/SETUP.txt", "w").write("\n".join(lines))
    with zipfile.ZipFile(f"MT5_EAs/packs/{name}.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for fn in sorted(os.listdir(out)): z.write(f"{out}/{fn}", f"{name}/{fn}")
    print(name, len(os.listdir(out)), "files")
FTMO_G = {"InpAccountSize": 200000, "InpDailyStopPct": 4.0, "InpMaxStopPct": 9.5, "InpRoomCapPct": 7.0, "InpHalfBelowPct": 3.0, "InpHalfUntilPct": 1.0, "InpFirmMaxLossPct": 10.0, "InpRiskMultiplier": 1.0}
CTI_G = {"InpAccountSize": 40000, "InpDailyStopPct": 4.0, "InpMaxStopPct": 5.7, "InpRoomCapPct": 4.2, "InpHalfBelowPct": 1.8, "InpHalfUntilPct": 0.6, "InpFirmMaxLossPct": 6.0, "InpRiskMultiplier": 1.0}
FS_G = {"InpAccountSize": 200000, "InpDailyStopPct": 2.0, "InpMaxStopPct": 9.5, "InpRoomCapPct": 7.0, "InpHalfBelowPct": 7.0, "InpHalfUntilPct": 1.0, "InpFirmMaxLossPct": 10.0,
        "InpRiskMultiplier": 1.0, "InpMaxPosPerSymbol": 2, "InpNoOpposite": "true", "InpNoWeekendEntries": "true", "InpDailyResetUTC": "true",
        "InpDailyRefHigher": "true", "InpNewsBlockMin": 10, "InpMinHoldSec": 130}
FTMO_EVAL = {"btcrev": .75, "spxfade": .75, "btc": .75, "goldvwap": .75, "nq2h": .75, "btcgap": .65, "gdip": .64, "solrev": .63, "gmom": .62, "orb15": .57, "spx1h": .53,
             "oil1h": .52, "sol": .45, "daxorb": .40, "nikkei": .36, "gasia": .35, "daxpm": .33, "nqbo15": .27, "spxbo5": .24}
FTMO_FUND = {"btcrev": .75, "spxfade": .75, "btc": .50, "goldvwap": .43, "nq2h": .40, "btcgap": .33, "gdip": .32, "solrev": .32, "gmom": .31, "orb15": .29, "spx1h": .27,
             "oil1h": .26, "sol": .22, "daxorb": .20, "nikkei": .18, "gasia": .17, "daxpm": .16, "nqbo15": .13, "spxbo5": .12}
CTI_R = {"btcrev": 1.0, "xrprev": 1.0, "spxfade": 1.0, "nqfade": 1.0, "btc": .49, "goldvwap": .42, "nq2h": .39, "btcgap": .32, "gdip": .31, "solrev": .31, "gmom": .30,
         "orb15": .28, "spx1h": .26, "oil1h": .25, "sol": .22, "daxorb": .19, "nikkei": .17, "gasia": .17, "daxpm": .16, "nqbo15": .13, "spxbo5": .12}
FS_R = {"btcrev": 1.0, "xrprev": 1.0, "spxfade": 1.0, "nqfade": 1.0, "btc": .68, "goldvwap": .58, "nq2h": .55, "gdip": .44, "solrev": .43, "gmom": .42,
        "orb15": .39, "spx1h": .36, "oil1h": .35, "sol": .30, "daxorb": .27, "nikkei": .24, "gasia": .23, "daxpm": .22, "nqbo15": .18, "spxbo5": .16}
NOVA_R = {"btcrev": 1.0, "spxfade": 1.0, "nqfade": 0.96, "btc": .39, "goldvwap": .33, "nq2h": .31, "gdip": .25, "btcgap": .25, "gmom": .24, "orb15": .22,
          "spx1h": .21, "daxorb": .16, "nikkei": .14, "gasia": .13, "daxpm": .13, "nqbo15": .10, "spxbo5": .09}
NOVA_G = {"InpAccountSize": 300000, "InpDailyStopPct": 50.0, "InpMaxStopPct": 5.7, "InpRoomCapPct": 4.8, "InpHalfBelowPct": 0, "InpHalfUntilPct": 0,
          "InpFirmMaxLossPct": 6.0, "InpTrailingMaxLoss": "true", "InpNoOpposite": "true", "InpMaxPosPerSymbol": 2, "InpNewsBlockMin": 2, "InpMinHoldSec": 310}
NOVA_MULT = [1.0, 1.0, 0.95, 0.95, 0.9, 0.9]   # slightly different size per account
FS_FUND = {k: round(v * 1.5 / 3.5, 2) for k, v in FS_R.items()}   # funded scale 1.5 vs eval 3.5 (best payouts with the 1.2% floating guard)
def build_nova():
    for k, mult in enumerate(NOVA_MULT, 1):
        build(f"TopOneTrader_NOVA_300K_Eval_Account{k}", NOVA_R, dict(NOVA_G, InpRiskMultiplier=mult),
              {"InpStartBalance": 300000, "InpDailyLossPct": 50.0, "InpMaxLossPct": 5.9, "InpMaxFloatingPct": 1.8, "InpFloatHaltDay": "false", "InpTrailLossPct": 5.5},
              f"""TOPONETRADER NOVA 300K - EVALUATION ONLY - ACCOUNT {k} of 6 - 17 EAs + Account Equity Guard
Use this folder on account {k} only. Every account's folder has its own magic numbers (+{100 * k}) and size (InpRiskMultiplier = {mult}),
so no two accounts send identical orders.
Rules: 5% target, 6% trailing max loss (follows the highest equity, locks at $300,000), no daily limit, EquityShield closes trades
at a 2-2.5% open loss, stop loss required on every order, no trades shorter than 5 minutes again and again, weekend holding allowed.
Built in: every order carries a real stop loss on the server; nothing closes before 310 s (an emergency stop at 1.5x sits on the
order for the first 310 s); trailing max-loss sizing (InpTrailingMaxLoss); no opposite trades on one symbol.
Guard: closes everything at a 1.8% open loss and keeps trading (beats EquityShield to it), closes everything for good at 5.5%
below the highest equity (before the firm's 6%). If it ever halts: reset the evaluation (free) and reset the guard.
IMPORTANT: one MT5 terminal installation per account (the EAs share safety flags inside a terminal).
Backtest: ~95% passed, median ~44 days (slowest 10%: ~6 months). Failed attempt -> free reset.
WHEN YOU PASS: remove EVERY EA from the account before trading it. EAs are not allowed on NOVA funded accounts.
Symbols (their MT5): BTCUSD, XAUUSD, US100, US500, GER40, JPN225.""", moff=100 * k)
# The5ers High Stakes (2-Step): 8% + 5% targets, 5% daily (from the higher of day-start balance/equity), 10% static, weekends allowed.
# Risks = tested risk x min(weight x scale, 1%/tested) from the 21-EA model at scale 3x, used unchanged in evaluation AND funded.
T5_EVAL = None   # set below: the SAME risk in evaluation and funded (The5ers flags size changes between stages)
T5_FUND = {"btcrev": 1.0, "spxfade": 1.0, "nqfade": 1.0, "xrprev": 1.0, "btc": .58, "goldvwap": .50, "nq2h": .47, "btcgap": .38, "gdip": .37, "solrev": .37,
           "gmom": .36, "orb15": .33, "spx1h": .31, "oil1h": .30, "sol": .26, "daxorb": .23, "nikkei": .21, "gasia": .20, "daxpm": .19, "nqbo15": .16, "spxbo5": .14}
T5_EVAL = T5_FUND
T5_G = {"InpAccountSize": 100000, "InpDailyStopPct": 4.0, "InpMaxStopPct": 9.5, "InpRoomCapPct": 8.0, "InpHalfBelowPct": 0, "InpHalfUntilPct": 0,
        "InpFirmMaxLossPct": 10.0, "InpRiskMultiplier": 1.0, "InpDailyRefHigher": "true", "InpNewsBlockMin": 5,
        "InpMaxOpenTotal": 6, "InpStaggerSec": 90}
def build_the5ers(size=100000):
    name = "The5ers_HighStakes_2Step_21" + ("" if size == 100000 else f"_{size // 1000}K")
    build(name, T5_EVAL, dict(T5_G, InpAccountSize=size), {"InpStartBalance": size, "InpDailyLossPct": 4.5, "InpMaxLossPct": 9.5, "InpProfitLockPct": 8, "InpMaxFloatingPct": 0},
          """THE5ERS HIGH STAKES (2-STEP) - 21 EAs + Account Equity Guard
Rules assumed (confirm on The5ers' site before buying): Phase 1 +8%, Phase 2 +5%, 5% daily loss (from the higher of the day's
starting balance or equity, reset at server midnight), 10% static max loss, unlimited time, minimum 3 profitable days per phase,
EAs and weekend holding allowed, 2-minute pause on high-impact news.

SETUP (every EA): attach to its chart (table below), Algo Trading on. Account size is set inside every file (see the bottom line). Different size? Change
InpAccountSize on every EA and InpStartBalance on the guard. One MT5 terminal per account (the EAs share safety flags).
Built in: daily stop at 4% measured the The5ers way (InpDailyRefHigher), stop everything at -9.5%, size shrinks once the day starts
more than 2% down (InpRoomCapPct 8, reaching 0 at the 10% limit), no NEW trades 5 min either side of high-impact USD news,
at most 6 open positions on the account (InpMaxOpenTotal), and no two EAs enter within 90 s of each other (InpStaggerSec:
the later one waits and retries, the slot is claimed atomically).
Request budget (all EAs together, per server day): warning in the Experts log at 500 and 750 server requests, no NEW entries
at 1,000 (closes always allowed); one EA trying 5+ entries within 10 minutes is blocked until the next day (malfunction guard).
The guard prints an hourly line: requests today, positions opened today, open now, margin used. Normal: ~15-70 requests a day.
Guard: closes everything at -4.5% today or -9.5% total, and closes everything once the phase target is reached (InpProfitLockPct).

PHASE 1: use as is (guard InpProfitLockPct = 8).
When the target is hit the guard closes everything and stops ALL the EAs (flags AEG_HALT and PP_HALT). To trade again:
in MT5 press F3 (Global Variables) and delete AEG_HALT and PP_HALT.
PHASE 2: delete those two flags, set the guard's InpProfitLockPct = 5 (InpStartBalance stays the account size).
FUNDED:  delete the flags, guard InpProfitLockPct = 0. Keep every EA's InpRiskPct exactly as it is (same size as the evaluation).
3 profitable days: if the target is hit before you have 3 profitable days, delete the flags, raise InpProfitLockPct by 0.5
and let the EAs trade on until the third profitable day.

Backtest (corrected simulator, 21 EAs, 2020-2025 start dates, rules above, same risk in both stages): passed first try 100%,
median ~57 days to funded without the execution limits; the 6-position cap + 90 s stagger add ~5 days and cost ~6 points a year
in the trade-level test, so expect ~62 days and ~70%/yr median to you (80% split), bad year ~40%; 100% of accounts kept 1 yr.
Expect live results to be lower: the EAs were chosen on the same history.

THE5ERS TERMS - how this pack stays inside them (read their prohibited-practices list yourself):
- SAME position sizes in evaluation and funded: do NOT raise or cut InpRiskPct between stages (they flag size changes).
- Risk is moderate and spread out: max 1% per trade with a hard stop on every order; all open trades together risk ~2.6% of
  the account 99% of the time (max seen ~4.9%); the stock-index EAs together ~1.4% (max ~3.5%).
- Execution footprint: never two entries within 90 s, at most 6 positions open (typically 4), ~8 trades a day, one order
  modification at most per trade.
- ONE The5ers account per pack. Do not run the same EAs on several The5ers accounts (their copy-trading / coordinated-trading
  rule). Spread across different firms instead, always the same direction, never opposite positions.
- Your own EAs with full source code (not third-party), no HFT/tick scalping (median holds 15 min to 4 days), no rollover
  scalping, no news brackets, ~9 trades a day in total.
- Grey areas to clear IN WRITING with The5ers support before buying: (1) 21 EAs running together (several positions open at
  once, typically 4, max 6; entries at least 90 s apart) vs their 'bulk trading' rule;
  (2) the dip EAs only buy (about 70% of all trades are longs) vs their 'one-sided bets' rule.

LEVERAGE CHECK: these risks need about 1:10 or more on indices and gold (1:30 is comfortable). Check margin on a demo first.
NEWS: the EAs only avoid OPENING trades near news; a stop or target can still fill inside the 2-minute window. Ask The5ers whether
that counts on the funded account.
Symbols: BTCUSD, SOLUSD, XRPUSD, XAUUSD, US100/NAS100, US500/SPX500, GER40/DAX40, JP225, USOIL/WTI (names differ per broker).
Leave out any EA whose symbol your account lacks (SOL/XRP are the likely ones).""", T5_FUND)

# Tiny personal account ($9, BlackBull): only the 6 EAs whose 0.01-lot trade fits; 5% risk per trade; firm-style guards opened up (no prop rules).
B9_R = {"spxbo5": 5.0, "spx1h": 5.0, "spxfade": 5.0, "nqbo15": 5.0, "daxorb": 5.0, "oil1h": 5.0}
B9_G = {"InpAccountSize": 9, "InpDailyStopPct": 50.0, "InpMaxStopPct": 95.0, "InpRoomCapPct": 0, "InpHalfBelowPct": 0, "InpHalfUntilPct": 0, "InpFirmMaxLossPct": 100.0,
        "InpRiskMultiplier": 1.0, "InpMaxOpenTotal": 0, "InpStaggerSec": 0, "InpNewsBlockMin": 2}
def build_b9():
    build("BlackBull_9USD_6EAs", B9_R, B9_G, {"InpStartBalance": 9, "InpDailyLossPct": 50.0, "InpMaxLossPct": 95.0, "InpProfitLockPct": 0, "InpMaxFloatingPct": 0},
          """BLACKBULL $9 PERSONAL ACCOUNT - 6 EAs (high-risk compounding test, NOT a prop-firm pack)
Only these 6 EAs can place a 0.01-lot trade on $9 without risking most of the account. Every EA risks 5% of the balance per trade
and compounds automatically as the balance grows. Leverage 1:500-1:1000 is fine (leverage does not change the risk per trade).
Backtest (12-month windows 2021-2025, trade by trade, 0.01-lot steps): with the full backtest edge, 49% of windows reached +500% and the
median ended at ~$52, but the median worst drop on the way was -85%. With half the edge (more realistic live) only ~9% reached +500%
and the median ended at ~$5.50. Expect deep drops; only use money you are fully prepared to lose.
Check BlackBull's contract sizes: assumed US500/US100/GER40 1 lot = 1 index point x 1 (0.01 lot = 1 cent per point) and USOIL 1 lot =
100 barrels. Different contracts change the risk - send me the specs if unsure. Symbol names differ (SPX500, NAS100, GER40, USOIL ...).
Account_Equity_Guard is optional here (only closes everything at -95%).""")

if __name__ == "__main__":
    if sys.argv[1:2] == ["b9"]: build_b9(); sys.exit()
    if sys.argv[1:2] == ["the5ers"]: build_the5ers(int(sys.argv[2]) if len(sys.argv) > 2 else 100000); sys.exit()
    build_nova()
    build("FTMO_2Step_FastPass19", FTMO_EVAL, FTMO_G, {"InpStartBalance": 200000, "InpDailyLossPct": 4.0, "InpMaxLossPct": 8.0, "InpMaxFloatingPct": 0},
          """FTMO 2-STEP 200K - FAST PASS 19 (19 EAs + Account Equity Guard)
Risk and guard inputs are already set inside each file for the EVALUATION. Every EA: attach to its chart, Algo Trading on.
Different account size? Change InpAccountSize (and the guard's InpStartBalance) on every EA.
After you are FUNDED: set each EA's InpRiskPct to the 'funded' column below (half the risk, same guards).
Backtest (corrected simulator, FTMO exact rule): 100% passed, median ~44-49 days; funded 1 yr with 2-weekly payouts: 100% kept.
Symbols: BTCUSD, SOLUSD, XAUUSD, US100, US500, GER40, JP225, USOIL. Leave out any EA whose symbol your account lacks.""", FTMO_FUND)
    build("CTI_Instant_21", CTI_R, CTI_G, {"InpStartBalance": 40000, "InpDailyLossPct": 50.0, "InpMaxLossPct": 5.8, "InpMaxFloatingPct": 0},
          """CTI INSTANT FUNDING 80K (starts at $40K) - 21 EAs + Account Equity Guard
Rules assumed: 6% static max loss from the starting balance, no daily limit. Risk/guard inputs are already set inside each file.
STAGE 1 ($40K balance): use as is (InpAccountSize = 40000).
STAGE 2 (after +10% the account becomes $80K): set InpAccountSize = 80000 on every EA and InpStartBalance = 80000 on the guard.
Backtest: reached the $80K stage in 100% of runs, median ~50 days; then kept 1 yr in 100%, ~$31K/yr after the 70% split.
Confirm with CTI in writing that these count as 'personal EAs' and that ~21 EAs on one account is allowed.
Symbols: BTCUSD, XRPUSD, SOLUSD, XAUUSD, US100, US500, GER40, JP225, USOIL. Leave out any EA whose symbol your account lacks.""")
    build("FundedSquad_1StepFlex_200K", FS_R, FS_G, {"InpStartBalance": 200000, "InpDailyLossPct": 2.6, "InpMaxLossPct": 9.0, "InpMaxFloatingPct": 0},
          """FUNDEDSQUAD 1-STEP FLEX 200K - 20 EAs + Account Equity Guard
Rules: 9% target, 3% daily (from the HIGHER of balance/equity at 00:00 UTC), 10% static max, 3 min days, 1:50; no hedging,
max 2 open positions per asset, max 70% margin, no new trades at the weekend, 3 days with +0.5% profit, 2-minute minimum hold,
1.5% max floating loss (all open trades together), no VPN, inactivity breach after 21 days.
Built in (every EA): no opposite trade on a symbol (InpNoOpposite), max 2 per symbol (InpMaxPosPerSymbol), no weekend entries
(InpNoWeekendEntries), daily stop at 2% measured FundedSquad's way (InpDailyResetUTC + InpDailyRefHigher), no new trades 10 min
either side of high-impact news, and a 130 s minimum hold (InpMinHoldSec): for the first 130 s only an emergency stop at 1.5x the
normal distance is on the order; after that the real stop/target go on, or the trade closes if price is already past one.
BTC_Weekend_Gap is NOT in this pack (it enters at the weekend, which FundedSquad bans).
EVALUATION: use as is. Backtest with all these filters: 100% passed, median ~44 days.
FUNDED: set every EA's InpRiskPct to the 'funded' column and the guard's InpMaxFloatingPct = 1.2 (closes all and stops the EAs
for the day before the 1.5% floating rule). Backtest funded 1 yr: 100% kept, 0 floating violations, ~$54K/yr per account to you
(80% split + 20% eval bonus). Two accounts: run the SAME pack with the same settings on both (never opposite trades).
VPS: FundedSquad's rules say VPS/VPN not allowed - get written OK from support before running this on a VPS.
Symbols: BTCUSD, XRPUSD, SOLUSD, XAUUSD, US100, US500, GER40, JP225, USOIL. Leave out any EA whose symbol your account lacks.""", FS_FUND)
