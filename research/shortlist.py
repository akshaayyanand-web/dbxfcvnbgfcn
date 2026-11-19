"""Shortlist of every strategy that passed the gate (latest record per strategy x market), tiered by the post-review checks, plus the 21-EA scorecard."""
import os, json, pandas as pd, openpyxl
from openpyxl.styles import Font
H = os.path.dirname(os.path.abspath(__file__)); f = f"{H}/catalogue_results.xlsx"; wb = openpyxl.load_workbook(f); ws = wb["1000 Strategy Ideas"]
st = {ws.cell(i, 1).value: ws.cell(i, 9).value for i in range(2, ws.max_row + 1)}; fam = {ws.cell(i, 1).value: ws.cell(i, 2).value for i in range(2, ws.max_row + 1)}
L = {}
for l in open(f"{H}/results/results.jsonl"):
    r = json.loads(l)
    if r.get("universe") != "BLOCKED": L[(r["id"], r["universe"])] = r
MT = pd.read_csv(f"{H}/results/multiple_testing.csv").set_index(["id", "universe"]); RB = json.load(open(f"{H}/results/robustness.json")); DR = pd.read_csv(f"{H}/results/duplicate_review.csv").set_index("id")
PROP = {"cfd": "yes (index/metal/oil CFDs)", "crypto": "yes if the firm lists the coins", "btc": "yes (BTC CFD)", "macro_long": "partly (FX, Nasdaq, oil yes; Treasuries usually not)",
        "energy": "partly (WTI/Brent only; products not listed)", "commod": "partly (gold/silver/WTI/Brent)", "perp": "no (needs exchange funding)", "fx_tr": "no (prop swaps replace carry)"}
rows = []
for (sid, u), r in L.items():
    if not r["passed"]: continue
    s = st.get(sid) or ""; m = MT.loc[(sid, u)] if (sid, u) in MT.index else None; frag = RB.get(f"{sid}@{u}", {}).get("fragile", False)
    if s.startswith(("REJECTED", "CONTROL")): tier = "C - rejected (artifact / look-ahead)"
    elif frag: tier = "C - fails 1-day delay"
    elif m is not None and bool(m["bonf_trials"]): tier = "A - survives every check"
    else: tier = "B - passes gate, fails multiple-testing correction"
    rows.append(dict(tier=tier, id=sid, family=fam.get(sid), market=u, mechanism_class=DR.mechanism_class.get(sid), duplicate_review=str(DR.review.get(sid, ""))[:60],
                     wf_sharpe=r["walkforward"]["sharpe"], wf_cagr_pct=round(100 * r["walkforward"]["cagr"], 1), test_sharpe=r["test"]["sharpe"], psr_z=None if m is None else round(float(m["psr_z"]), 2),
                     prop_firm_tradable=PROP.get(u, "no (options / ETFs / bonds / synthetic)")))
S = pd.DataFrame(rows).sort_values(["tier", "psr_z"], ascending=[True, False])
E = pd.read_csv(f"{H}/results/ea21_scorecard.csv")
for n in ("Shortlist (all winners)", "21 EAs scorecard"):
    if n in wb.sheetnames: del wb[n]
for name, df, note in (("Shortlist (all winners)", S, f"{len(S)} market tests passed the gate; tiers: " + "; ".join(f"{k}: {v}" for k, v in S.tier.value_counts().sort_index().items())),
                       ("21 EAs scorecard", E, "Each EA alone at its base risk (2020-04..2026-10). psr_z vs Bonferroni z 4.16. book_sharpe_drop_without = book Sharpe lost if this EA is removed. Pruning test: choosing EAs by 2020-22 contribution lowered the 2023-26 book Sharpe from 2.71 to 2.32 - keep all 21.")):
    s = wb.create_sheet(name, 1); s.append([note]); s.append(list(df.columns))
    for r in df.itertuples(index=False): s.append(list(r))
    for c in s[2]: c.font = Font(bold=True)
wb.save(f); print(S.tier.value_counts().sort_index().to_dict()); print(S[S.tier.str.startswith("A")][["id", "family", "market", "mechanism_class", "wf_sharpe", "test_sharpe", "prop_firm_tradable"]].to_string(index=False))
