"""Build preconfigured EA packs (risk + guard inputs baked into each file) for FTMO 2-step, CTI Instant and FundedSquad 1-Step Flex."""
import os, re, shutil, zipfile
SRC = {"btc": "MT5_EAs/BTC_Dip_v3.mq5", "gdip": "MT5_EAs/Gold_Dip.mq5", "nq2h": "MT5_EAs/NQ_Dip_2h.mq5", "spx1h": "MT5_EAs/SPX_Dip_1h.mq5",
       "oil1h": "MT5_EAs/Oil_Dip_1h.mq5", "gasia": "MT5_EAs/Gold_Asia_Breakout.mq5", "gmom": "MT5_EAs/Gold_Intraday_Momentum.mq5",
       "orb15": "MT5_EAs/NQ_Opening_Range.mq5", "nqbo15": "MT5_EAs/NQ_Breakout_15m.mq5", "daxorb": "MT5_EAs/DAX_Opening_Range.mq5",
       "spxbo5": "MT5_EAs/SPX_Breakout_5m.mq5", "btcgap": "MT5_EAs/BTC_Weekend_Gap.mq5", "sol": "MT5_EAs/optional/SOL_Dip_1h.mq5",
       "goldvwap": "MT5_EAs/optional/Gold_VWAP_Pullback_5m.mq5", "spxfade": "MT5_EAs/optional/Open_Fade_1m.mq5", "nikkei": "MT5_EAs/optional/Nikkei_Breakout_5m.mq5",
       "solrev": "MT5_EAs/optional/SOL_Revert_5m.mq5", "btcrev": "MT5_EAs/optional/BTC_Revert_5m.mq5", "daxpm": "MT5_EAs/optional/DAX_Premarket_15m.mq5"}
SYMB = {"btc": "BTCUSD", "gdip": "XAUUSD", "nq2h": "US100", "spx1h": "US500", "oil1h": "USOIL/WTI", "gasia": "XAUUSD", "gmom": "XAUUSD", "orb15": "US100",
        "nqbo15": "US100", "daxorb": "GER40/DE40", "spxbo5": "US500", "btcgap": "BTCUSD", "sol": "SOLUSD", "goldvwap": "XAUUSD", "spxfade": "US500",
        "nikkei": "JP225", "solrev": "SOLUSD", "btcrev": "BTCUSD", "daxpm": "GER40/DE40", "nqfade": "US100", "xrprev": "XRPUSD"}
def bake(text, risk, guards, magic=None, extra=()):
    text = re.sub(r"input double InpRiskPct = [0-9.]+;", f"input double InpRiskPct = {risk};", text)
    for name, val in guards.items(): text = re.sub(rf"(input \w+\s+{name}\s*=\s*)[^;]+;", rf"\g<1>{val};", text)
    if magic: text = re.sub(r"input long   InpMagic   = \d+;", f"input long   InpMagic   = {magic};", text)
    for a, b in extra: assert a in text, a; text = text.replace(a, b)
    return text
def build(name, risks, G, guard_vals, header, funded=None):
    out = f"MT5_EAs/packs/{name}"; shutil.rmtree(out, ignore_errors=True); os.makedirs(out); rows = []
    for k, r in risks.items():
        if k == "nqfade":
            t = bake(open(SRC["spxfade"]).read(), r, G, 1121, (("input int    InpLookMin = 15;", "input int    InpLookMin = 10;"), ("input double InpMovePts = 25;", "input double InpMovePts = 98;"))); fn = "NQ_Open_Fade_1m.mq5"
        elif k == "xrprev":
            t = bake(open(SRC["btcrev"]).read(), r, G, 1126, (("input double InpMovePct  = 6.97;", "input double InpMovePct  = 14.1;"),)).replace('"BTC Revert"', '"XRP Revert"'); fn = "XRP_Revert_5m.mq5"
        else: t = bake(open(SRC[k]).read(), r, G); fn = os.path.basename(SRC[k])
        open(f"{out}/{fn}", "w").write(t); tf = re.search(r"#define REQUIRED_TF PERIOD_(\w+)", t).group(1)
        rows.append((fn, SYMB[k] + " " + tf, r, funded.get(k) if funded else None))
    g = open("MT5_EAs/guards/Account_Equity_Guard.mq5").read()
    for nm, v in guard_vals.items(): g = re.sub(rf"(input double {nm}\s*=\s*)[^;]+;", rf"\g<1>{v};", g)
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
        "InpRiskMultiplier": 1.0, "InpMaxPosPerSymbol": 2, "InpNoOpposite": "true"}
FTMO_EVAL = {"btcrev": .75, "spxfade": .75, "btc": .75, "goldvwap": .75, "nq2h": .75, "btcgap": .65, "gdip": .64, "solrev": .63, "gmom": .62, "orb15": .57, "spx1h": .53,
             "oil1h": .52, "sol": .45, "daxorb": .40, "nikkei": .36, "gasia": .35, "daxpm": .33, "nqbo15": .27, "spxbo5": .24}
FTMO_FUND = {"btcrev": .75, "spxfade": .75, "btc": .50, "goldvwap": .43, "nq2h": .40, "btcgap": .33, "gdip": .32, "solrev": .32, "gmom": .31, "orb15": .29, "spx1h": .27,
             "oil1h": .26, "sol": .22, "daxorb": .20, "nikkei": .18, "gasia": .17, "daxpm": .16, "nqbo15": .13, "spxbo5": .12}
CTI_R = {"btcrev": 1.0, "xrprev": 1.0, "spxfade": 1.0, "nqfade": 1.0, "btc": .49, "goldvwap": .42, "nq2h": .39, "btcgap": .32, "gdip": .31, "solrev": .31, "gmom": .30,
         "orb15": .28, "spx1h": .26, "oil1h": .25, "sol": .22, "daxorb": .19, "nikkei": .17, "gasia": .17, "daxpm": .16, "nqbo15": .13, "spxbo5": .12}
FS_R = {"btcrev": 1.0, "xrprev": 1.0, "spxfade": 1.0, "nqfade": 1.0, "btc": .68, "goldvwap": .58, "nq2h": .55, "btcgap": .44, "gdip": .44, "solrev": .43, "gmom": .42,
        "orb15": .39, "spx1h": .36, "oil1h": .35, "sol": .30, "daxorb": .27, "nikkei": .24, "gasia": .23, "daxpm": .22, "nqbo15": .18, "spxbo5": .16}
FS_FUND = {k: round(v / 2, 2) for k, v in FS_R.items()}
if __name__ == "__main__":
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
          """FUNDEDSQUAD 1-STEP FLEX 200K - 21 EAs + Account Equity Guard
Rules: 9% target, 3% daily, 10% static max, 3 min days, 1:50; no hedging (no buy+sell on the same asset), max 2 open positions per asset,
max 70% margin; funded stage adds a 1.5% max floating loss (all open trades together).
Built in: every EA skips a trade if the opposite direction is open on that symbol (InpNoOpposite=true) or 2 positions are already
open there (InpMaxPosPerSymbol=2); daily stop at 2% (InpDailyStopPct) so the 3% limit is never reached.
EVALUATION: use as is. Backtest: 100% passed, median ~35-37 days with these filters (scale 3.5).
FUNDED: set every EA's InpRiskPct to the 'funded' column (half) and the guard's InpMaxFloatingPct = 1.2 (closes all and stops the
EAs for the day before the 1.5% floating rule). Two accounts: run the SAME pack with the same settings on both (never opposite trades).
Symbols: BTCUSD, XRPUSD, SOLUSD, XAUUSD, US100, US500, GER40, JP225, USOIL. Leave out any EA whose symbol your account lacks.""", FS_FUND)
