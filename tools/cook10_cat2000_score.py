import numpy as np, pandas as pd
from math import erf, sqrt
names = [l.strip() for l in open("cat2000/list2.txt") if l.strip()]; assert len(names) == 1000
I = pd.read_pickle("cat2000/results_intraday.pkl"); I = I[I.n > 0].copy(); Dd = pd.read_pickle("cat2000/results_daily.pkl"); Dd = Dd[Dd.n >= 10].copy()
pnorm = lambda z: 0.5 * (1 + erf(z / sqrt(2))); p_tr, p_ho = 1 - pnorm(2.5), 1 - pnorm(2.0)
I["pass_train"] = (I.t_train >= 2.5) & (I.n_train >= 100); I["pass_all"] = I.pass_train & (I.t_hold >= 2) & (I.avgR_hold >= 0.05) & (I.n_hold >= 50) & (I.pos_years >= 0.7 * I.years)
Dd["pass_train"] = (Dd.t_train >= 2.5) & (Dd.n_train >= 30); Dd["pass_all"] = Dd.pass_train & (Dd.t_hold >= 2) & (Dd.avg_hold_bp > 0) & (Dd.n_hold >= 15) & (Dd.pos_years >= 0.7 * Dd.years)
Mi = int((I.n_train >= 100).sum()); Md = int((Dd.n_train >= 30).sum())
print(f"INTRADAY: {Mi:,} tests | passed train {I.pass_train.sum()} (luck ~{Mi*p_tr:.0f}) | passed both {I.pass_all.sum()} (luck ~{Mi*p_tr*p_ho:.1f})")
print(f"   median avgR train {I.avgR_train.median():+.3f}, holdout {I.avgR_hold.median():+.3f}; train-passers in holdout: median {I[I.pass_train].avgR_hold.median():+.3f}, positive {100*(I[I.pass_train].avgR_hold>0).mean():.0f}%")
print(f"DAILY: {Md:,} tests | passed train {Dd.pass_train.sum()} (luck ~{Md*p_tr:.1f}) | passed both {Dd.pass_all.sum()} (luck ~{Md*p_tr*p_ho:.2f})")
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 300); pd.set_option("display.max_colwidth", 55)
I["name"] = I.sid.map(lambda i: names[i - 1])
print("\nINTRADAY SURVIVORS:"); s = I[I.pass_all].sort_values("t_hold", ascending=False)
print(s[["sid", "name", "sym", "tf", "exit", "n_train", "n_hold", "avgR_train", "avgR_hold", "t_train", "t_hold", "win", "pf", "pos_years", "years"]].round(3).to_string(index=False) if len(s) else "none")
print("\nINTRADAY train-passers (top 25 by holdout t):"); print(I[I.pass_train].sort_values("t_hold", ascending=False).head(25)[["sid", "name", "sym", "tf", "exit", "n_train", "n_hold", "avgR_train", "avgR_hold", "t_train", "t_hold"]].round(3).to_string(index=False))
print("\nDAILY SURVIVORS:"); s2 = Dd[Dd.pass_all]; print(s2.round(2).to_string(index=False) if len(s2) else "none")
print("\nDAILY best 25 by holdout t:"); print(Dd.sort_values("t_hold", ascending=False).head(25)[["id", "name", "mkt", "H", "long_only", "n_train", "n_hold", "avg_train_bp", "avg_hold_bp", "t_train", "t_hold", "pos_years", "years"]].round(2).to_string(index=False))
fam = I.groupby("sid").agg(cells=("sym", "size"), med_hold=("avgR_hold", "median"), pass_train=("pass_train", "sum"), pass_all=("pass_all", "sum"))
fam["name"] = [names[i - 1] for i in fam.index]
print("\nINTRADAY setups ranked by median holdout R (top 20 / bottom 5):"); f2 = fam.sort_values("med_hold", ascending=False); print(f2.head(20).round(3).to_string()); print(f2.tail(5).round(3).to_string())
# ---------------------------------------------------------------- triage of all 1000 names
def rng(a, b): return list(range(a, b + 1))
tested_i = set(I.sid.unique()) | set(pd.read_pickle("cat2000/results_intraday.pkl").sid.unique()); tested_d = set(Dd.id.unique())
MIR = {16: 15, 17: 18, 25: 26, 55: 54, 115: 114, 117: 116, 118: 119, 126: 125, 156: 157, 207: 206, 209: 208, 222: 221, 224: 223, 234: 233, 271: 270, 419: 418, 633: 632, 642: 641}
C1 = "catalogue 1 "
DUP = {7: "#6 (LVN traversal)", 8: C1 + "base 43 previous-day liquidity grab", 12: "#4 (80% value-area rule)", 19: "#14", 21: C1 + "base 43", 22: C1 + "base 43", 23: C1 + "base 23", 24: C1 + "base 23",
       27: C1 + "base 29", 30: C1 + "bases 27/66", 31: C1 + "bases 27/66", 32: C1 + "base 6", 33: C1 + "base 6", 34: C1 + "base 45", 35: C1 + "base 45", 36: C1 + "base 33", 37: "SMC sweep/CHoCH/FVG round + catalogue 1 base 93",
       38: "SMC round + catalogue 1 base 93", 40: C1 + "base 45", 41: C1 + "base 41", 42: C1 + "base 42", 45: C1 + "bases 1/33", 49: "linear-regression channel fade (MSNR/CRT/LRC round)", 50: C1 + "base 82",
       52: C1 + "base 28", 53: C1 + "base 28", 57: C1 + "base 66", 58: C1 + "base 66", 59: C1 + "base 62", 61: C1 + "base 16", 62: C1 + "bases 16/35", 63: C1 + "base 24", 64: C1 + "bases 33/38", 65: C1 + "base 33",
       66: "#46", 67: C1 + "base 35", 68: C1 + "base 35", 69: C1 + "base 70", 70: C1 + "base 80 + Open Fade EA", 71: C1 + "base 21", 75: C1 + "base 22", 76: C1 + "base 71", 77: C1 + "base 72",
       78: C1 + "base 44", 79: C1 + "base 44", 81: C1 + "base 45", 83: C1 + "base 36", 85: "#84", 87: "#86", 88: "#86", 89: C1 + "base 45", 92: C1 + "base 43", 93: C1 + "bases 60/91/97", 94: C1 + "bases 60/91/97",
       95: C1 + "base 6", 96: C1 + "bases 61-63", 97: C1 + "bases 61-63", 98: C1 + "bases 61-63",
       101: C1 + "base 32", 107: C1 + "base 26", 129: "#112", 130: "#112", 132: "#121", 133: "#113", 134: "#104/#125", 136: "#106", 137: "#106", 140: C1 + "base 30", 141: C1 + "base 64", 142: "#112", 143: "#113",
       144: C1 + "base 70", 145: C1 + "base 80", 150: C1 + "base 80 + Open Fade EA", 151: C1 + "base 32", 152: "#113", 158: C1 + "base 40", 159: C1 + "base 40", 162: "#153", 163: "#153", 164: "#121", 165: "#121",
       168: "#121", 180: "#113", 181: C1 + "base 40", 182: C1 + "base 40", 183: "#91", 186: "#155", 188: C1 + "base 88", 191: "#135", 192: "#104", 195: "#194 (conflict = stand aside)",
       215: "#1 (value migration)", 216: "#5", 227: C1 + "base 58", 228: "#211", 231: "#214", 232: "#214", 236: "#223", 241: "#225", 242: "#225", 243: "#225", 245: "#244", 246: "#244", 247: "#235", 248: C1 + "base 14",
       249: C1 + "base 14", 250: C1 + "bases 58/92", 251: C1 + "bases 58/92", 266: "#214/#206", 267: "#214/#206", 268: "#206", 269: "#206", 276: "#5", 277: "#1", 278: "#5", 279: "#5", 280: "#6", 281: "#6",
       285: "#11", 286: "#11", 287: "#3", 288: "#4", 292: "#291", 294: "#6", 295: "#6", 296: "#1",
       401: C1 + "base 61", 402: C1 + "base 62", 403: C1 + "bases 25/63", 404: C1 + "base 11", 407: C1 + "base 24", 408: C1 + "base 35", 412: C1 + "base 62", 414: "#413 (estimator variant)", 415: "#413 (estimator variant)",
       416: "#413 (estimator variant)", 420: "#418", 423: "#421", 429: "#428", 433: C1 + "base 62", 434: C1 + "base 61", 435: C1 + "base 65", 436: C1 + "base 65", 439: C1 + "base 35", 440: C1 + "base 33", 447: "#449",
       453: C1 + "base 25", 454: C1 + "base 67", 461: C1 + "base 30", 462: C1 + "base 64", 463: C1 + "base 35", 464: C1 + "base 62", 470: "#467", 479: C1 + "base 86", 480: "#525", 481: C1 + "base 88", 482: C1 + "base 86",
       483: "#541", 490: "intraday ML walk-forward (G2) + #962", 501: C1 + "bases 15/81", 503: "#502", 505: C1 + "base 82", 506: "MSNR/CRT/LRC round", 508: "#507", 509: C1 + "base 83", 511: "#509/#510", 512: "#509/#510",
       513: "#509/#510", 514: "#521", 515: "#509", 516: "#510", 517: C1 + "bases 65/86 + ML (G2)", 518: C1 + "base 65", 519: C1 + "base 65", 520: C1 + "base 65", 523: "#521", 524: "#521", 527: C1 + "base 88",
       528: C1 + "base 88", 529: "#543", 530: C1 + "base 86", 531: "#478", 532: "#534", 533: "#534", 535: C1 + "base 85 (lead-lag)", 536: "#534 / ML", 537: "#534", 538: "#534", 539: C1 + "base 86", 540: C1 + "base 86",
       542: "#541", 544: "#543", 545: "#543", 551: "#504", 552: "ML (G2)", 554: "#553", **{i: "pairs/spreads round (16 pairs) + catalogue 1 base 84" for i in rng(556, 568)},
       569: "ML (G2) + lead-lag", 570: "ML (G2) + lead-lag", **{i: "earlier 1000-strategy research catalogue (PCA / factor residual families)" for i in rng(571, 580)}, **{i: "#581/#582" for i in rng(583, 590)},
       601: "news lab (FOMC reaction) + pre-FOMC drift", 602: "news lab (FOMC)", 603: "news lab (FOMC)", 604: "news lab (FOMC)", 605: "news lab (CPI reaction)", 606: "news lab (CPI reaction)", 610: "news lab (NFP reaction)",
       638: "#635/#637", 643: "#641", 646: "#645", 647: "#645", 673: "oil round (EIA inventory surprise)", 678: "#635", 679: "#660", 680: "silver round (gold/silver ratio)", 689: "seasonality round",
       **{i: "news lab (CPI/NFP/FOMC) + pre-FOMC" for i in rng(691, 697)},
       710: "currency momentum round", 711: "currency momentum round", 712: "currency momentum round", 715: "#660", **{i: "currency strength / dollar momentum round" for i in rng(716, 720)}, 723: "#722",
       724: "silver round + pairs round (gold/silver)", 737: "#708", 750: "pairs round (NQ/SPX)", 751: "pairs round (NQ/RUT)", 752: "pairs round (SPX/DOW)", 760: "pairs round (SPX/RUT)", 762: "#660", 766: "#427",
       767: "Nasdaq round (VIX-spike reversal)", 769: "#428", 770: "#428", 773: "#703", 774: "#632", 787: "pairs round", 788: "pairs round", 789: C1 + "base 85", 790: "#581", 791: "earlier research catalogue (PCA)", 792: "earlier research catalogue (PCA)",
       801: "round 11 (weekend gap)", 802: "seasonality round (day of week)", 803: "seasonality round (day of week)", 804: "seasonality round (day of week)", 810: "#468", 813: "seasonality round (month-end fade) + TOM",
       814: "seasonality round (TOM)", 815: "seasonality round (month-end fade)", 817: "#816", 818: "#816", 819: "#816", 833: "seasonality round (pre-holiday)", 834: "seasonality round (pre-holiday)", 835: "seasonality round (pre-holiday)",
       836: "seasonality round (pre-holiday)", 837: "#821-832", 838: "#820", 839: "#816/#820", 840: "#816/#820", **{i: "newlab round 3 (fix reversal / continuation)" for i in rng(841, 845)},
       **{i: C1 + "session bases 71-78" for i in rng(846, 852)}, 853: C1 + "bases 73/74 + DAX pre-market EA", 854: C1 + "bases 73/74", 856: "#855 (opposite side)", 859: "#80", 860: "newlab round 3 (MOC window)",
       861: "Nasdaq session-momentum round", 862: "Nasdaq session-momentum round", 863: "options-expiry round (afternoon follow)", 864: "options-expiry round (afternoon fade)", 871: "seasonality round (overnight)",
       872: "seasonality round (overnight)", 873: C1 + "base 70", 874: C1 + "base 80", 875: "round 11 (weekend gap)", 876: "round 11 (weekend gap)", 877: "round 11 (weekend gap)", 878: "seasonality round",
       880: "newlab round 1 (time of day)", 881: "newlab round 1 (time of day)", 885: C1 + "filters", 886: C1 + "filters", 887: C1 + "filters", 888: C1 + "filters", **{i: C1 + "session bases" for i in rng(891, 897)},
       901: C1 + "base 60", 902: C1 + "hybrids", 903: C1 + "filter 1 (HTF)", 904: C1 + "hybrids", 905: C1 + "hybrids", 906: C1 + "bases 58/92", 907: C1 + "base 61", 909: "regime gating (G1) + #641", 911: C1 + "bases 94/98",
       912: C1 + "base 94", 913: C1 + "base 14", 914: C1 + "base 94", 915: C1 + "base 92", 916: "#202", 917: "regime gating (G1)", 919: C1 + "base 95", 920: "#208", 921: C1 + "base 19", 922: C1 + "base 93", 923: "#421",
       924: "#701/#721", 925: C1 + "bases 65/86", 926: C1 + "bases 65/86", 927: C1 + "bases 65/86", **{i: "intraday ML walk-forward (G2: gradient boosting, 6 markets)" for i in (941, 944, 945, 946, 947, 948, 949, 950, 951, 971, 972, 973, 974)},
       **{i: "intraday ML walk-forward (G2); deep sequence models not run (no deep-learning library here)" for i in rng(952, 957)}, **{i: "regime work: catalogue 1 bases 65/86 + G2" for i in rng(962, 965)}}
NODATA = {**{i: "needs real bid/ask order-flow or trade-by-trade data (CFD feeds only have tick volume)" for i in (203, 204, 217, 218, 219, 220, 237, 238, 239, 240, 259, 260, 261, 262, 263, 264, 265, 297, 298)},
          **{i: "needs a live order book / quote data (not available for CFDs, and not tradable at CFD latency)" for i in list(rng(301, 379)) + list(rng(391, 400))},
          430: "needs option skew data", 431: "needs option smile data", 432: "needs option surface data", 166: "bar-to-bar gaps almost never happen on 24-hour CFDs", 167: "bar-to-bar gaps almost never happen on 24-hour CFDs",
          **{i: "needs economic consensus forecasts (surprise = actual - consensus)" for i in list(rng(607, 609)) + list(rng(611, 627))}, 628: "needs Treasury auction results", 629: "needs Treasury auction results",
          634: "only 1-2 curve un-inversion events in the data", 639: "needs foreign sovereign spreads", 640: "needs foreign sovereign spreads", 644: "high-yield spread series only has 3 years here",
          **{i: "needs central-bank balance-sheet / foreign policy-rate data" for i in rng(648, 659)}, **{i: "needs event/news data (geopolitics, elections, policy, tariffs, OPEC)" for i in list(rng(662, 672))},
          **{i: "needs energy fundamentals not in the data" for i in rng(674, 677)}, **{i: "needs commodity markets not in the data (copper, agriculture, curves)" for i in list(rng(681, 688)) + [690]},
          698: "needs economic consensus forecasts", 699: "needs an event calendar with expectations", 704: "needs EU rates", 705: "needs UK rates", 706: "needs China growth data", 707: "needs a commodity index",
          725: "needs copper", 727: "needs platinum/palladium", **{i: "needs industrial metals" for i in rng(730, 735)}, **{i: "needs natural gas / products / energy equities" for i in rng(741, 744)}, 747: "needs commodity sectors",
          748: "needs agricultural commodities", 753: "needs Euro Stoxx", 754: "needs FTSE", 756: "needs Hang Seng / China equities", 757: "needs China equities", 758: "needs EM equities", 759: "needs growth/value indices",
          771: "needs bond prices", 772: "needs bond prices", **{i: "needs foreign yields / inflation / growth data" for i in rng(775, 781)}, **{i: "needs global liquidity / breadth / funding data" for i in rng(782, 786)}, 908: "needs liquidity data"}
NOTSTRAT = {**{i: "execution tool, not an entry signal" for i in rng(380, 390)}, **{i: "volatility forecast / risk filter / sizing tool, not an entry signal" for i in list(rng(424, 426)) + list(rng(441, 446)) + [450] + list(rng(455, 460)) + [465, 466, 476, 477] + list(rng(484, 489)) + list(rng(491, 500))},
            **{i: "volatility model, used as a filter not an entry" for i in rng(546, 550)}, 555: "risk filter", **{i: "model selection / meta-method, not an entry signal" for i in rng(591, 600)},
            **{i: "portfolio construction, not an entry signal" for i in rng(793, 800)}, **{i: "seasonality / cost forecast used as a filter" for i in list(rng(865, 870)) + [879, 882, 883, 884, 889, 890, 898, 899, 900]},
            **{i: "position management / sizing / meta-method, not an entry signal" for i in list(rng(928, 940)) + [942, 943] + list(rng(958, 961)) + list(rng(966, 970)) + list(rng(975, 1000))}}
VAGUE = {i: "name only, no mechanical rule implied" for i in (90, 99, 100, 170, 184, 185, 187, 190, 193, 200, 229, 230, 272, 273, 274, 275, 282, 283, 284, 293, 299, 300, 471, 472, 473, 474, 475, 553 - 553, 583, 700, 910, 918)}
VAGUE.pop(0, None)
rows = []
bi = I.sort_values("t_hold", ascending=False).groupby("sid").head(1).set_index("sid"); bd = Dd.sort_values("t_hold", ascending=False).groupby("id").head(1).set_index("id")
ai = I.groupby("sid").agg(cells=("sym", "size"), ptr=("pass_train", "sum"), pall=("pass_all", "sum"), med=("avgR_hold", "median"))
ad = Dd.groupby("id").agg(cells=("mkt", "size"), ptr=("pass_train", "sum"), pall=("pass_all", "sum"), med=("avg_hold_bp", "median"))
for k in range(1, 1001):
    nm = names[k - 1]; r = dict(No=k, Strategy=nm)
    src = None
    if k in ai.index: src = ("intraday", k)
    elif k in ad.index: src = ("daily", k)
    elif k in MIR and (MIR[k] in ai.index or MIR[k] in ad.index): src = ("intraday" if MIR[k] in ai.index else "daily", MIR[k])
    if src:
        typ, kk = src; a = (ai if typ == "intraday" else ad).loc[kk]; b_ = (bi if typ == "intraday" else bd).loc[kk]
        r["Category"] = "Tested" + (f" (same test as #{kk}: the engine trades both directions)" if kk != k else "")
        r["How"] = "intraday M15/H1, 10 markets, 3 exits" if typ == "intraday" else "daily, macro/intermarket signal"
        r["Cells tested"] = int(a.cells); r["Passed train"] = int(a.ptr); r["Passed train + holdout"] = int(a.pall)
        r["Median holdout"] = round(float(a.med), 3); r["Unit"] = "R/trade" if typ == "intraday" else "bp/trade"
        r["Best cell"] = (f"{b_.sym} {b_.tf} / {b_.exit}" if typ == "intraday" else f"{b_.mkt} hold {int(b_.H)}d")
        r["Best holdout t"] = round(float(b_.t_hold), 2); r["Best train t"] = round(float(b_.t_train), 2)
        r["Result"] = "CANDIDATE" if a.pall > 0 else "Rejected"
    elif k in DUP: r["Category"] = "Already tested"; r["How"] = DUP[k]; r["Result"] = "see earlier result (rejected unless noted)"
    elif k in MIR: r["Category"] = "Already tested"; r["How"] = f"#{MIR[k]}"; r["Result"] = "see #" + str(MIR[k])
    elif k in NODATA: r["Category"] = "Not testable with this data"; r["How"] = NODATA[k]; r["Result"] = "-"
    elif k in NOTSTRAT: r["Category"] = "Not an entry strategy"; r["How"] = NOTSTRAT[k]; r["Result"] = "-"
    elif k in VAGUE: r["Category"] = "Too vague to test"; r["How"] = VAGUE[k]; r["Result"] = "-"
    else: r["Category"] = "UNASSIGNED"; r["How"] = ""; r["Result"] = ""
    rows.append(r)
T = pd.DataFrame(rows); print("\nTRIAGE:", T.Category.str.replace(r" \(same test.*", "", regex=True).value_counts().to_dict())
print("unassigned:", list(T[T.Category == "UNASSIGNED"].No))
with pd.ExcelWriter("cat2000/Strategy_List_2_RESULTS.xlsx") as xw:
    T.to_excel(xw, sheet_name="All 1000", index=False)
    I.drop(columns=["name"]).to_excel(xw, sheet_name="Intraday cells", index=False); Dd.to_excel(xw, sheet_name="Daily cells", index=False)
print("written cat2000/Strategy_List_2_RESULTS.xlsx")
