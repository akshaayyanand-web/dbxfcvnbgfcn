# The5ers $20K Bootcamp (official site, Nov 2026): Steps 1-3 at $5K/$10K/$15K, 6% target, 5% static max loss, no daily limit, no min days.
# Pro: $20K, 4% static max loss of the level, 3% daily pause (trades closed, resume next day - not a breach), scale on every +5%:
# 20K(50/50) -> 25K -> 30K -> 40K -> 50K -> 60K -> 80K -> 100K (75/25). ASSUMPTION: the 5% profit is paid at the split when the level scales
# and the next level starts 2 days later. Fees $22 per Step-1 attempt + $50 activation. Books: all 21 EAs, Pack A (breakout/momentum), Pack B (dip/reversion).
import sys
exec(open("firms.py").read().split('\nif __name__ == "__main__":')[0])
PACK = {"21": list(NAMES),
        "A": ["orb15", "nqbo15", "spxbo5", "daxorb", "daxpm", "nikkei", "gasia", "gmom"],
        "B": ["btc", "sol", "gdip", "nq2h", "spx1h", "oil1h", "spxfade", "nqfade", "btcrev", "solrev", "xrprev", "goldvwap", "btcgap"]}
LEVELS = [20000, 25000, 30000, 40000, 50000, 60000, 80000, 100000]; SPLIT = lambda s: 0.5 if s == 20000 else 0.75
XS = (1.0, 1.5, 2.0, 3.0, 4.0); ARR = {}
for pk, nm in PACK.items():
    for X in XS:
        build({c: (min(PORT["21"][c] * X, 1.0 / BASE[c]) if c in nm else 0.0) for c in NAMES}); ARR[(pk, X)] = (EQ_R.copy(), EQ_L.copy(), D_FLT.copy())
def phase(R, L, F, h0, target, ML, G):
    """Evaluation step: static floor 1-ML, EA daily guard G (fraction, from day-start max(balance, equity)). Returns (result, end index)."""
    eq = 1.0; opn = 0.0; day = -1; hd = -1; floor = 1 - ML; Z = 0.8 * ML; ref = 1.0; mm = 1.0
    for i in range(h0, len(R)):
        if DAYN[i] != day:
            bal = eq - opn
            if bal >= 1 + target: return "pass", i
            day = DAYN[i]; ref = max(bal, eq); mm = max(0.0, min(1.0, (eq - floor) / Z))
        if hd == day or (R[i] == 0 and L[i] == 0):
            if hd == day: opn = 0.0
            continue
        low = eq * (1 + mm * L[i]); after = eq * (1 + mm * R[i])
        if low <= floor: return "fail", i
        if low <= ref - G: eq = min(after, max(low, ref - G - 0.003)); opn = 0.0; hd = day
        else: opn += eq * mm * F[i]; eq = after
    return "open", len(R)
def pro(R, L, F, h0, days=365):
    """Pro stage with scaling. Returns (status, paid $, top level, number of scale-ups)."""
    lv = 0; eq = 1.0; opn = 0.0; day = -1; hd = -1; ref = 1.0; paid = 0.0; ups = 0; resume = h0; end = min(h0 + days * 24, len(R))
    for i in range(h0, end):
        if i < resume: continue
        if DAYN[i] != day:
            bal = eq - opn
            if bal >= 1.05:
                size = LEVELS[lv]; paid += 0.05 * size * SPLIT(size); ups += 1
                if lv + 1 < len(LEVELS): lv += 1
                eq = 1.0; opn = 0.0; bal = 1.0; resume = i + 48; day = DAYN[i]; continue
            day = DAYN[i]; ref = max(bal, eq); mm = max(0.0, min(1.0, (eq - 0.96) / 0.032))
        if hd == day or (R[i] == 0 and L[i] == 0):
            if hd == day: opn = 0.0
            continue
        low = eq * (1 + mm * L[i]); after = eq * (1 + mm * R[i])
        if low <= 0.96: return "breached", paid, LEVELS[lv], ups
        if low <= ref - 0.03: eq = min(after, max(low, ref - 0.033)); opn = 0.0; hd = day     # 3% daily pause (firm closes trades)
        else: opn += eq * mm * F[i]; eq = after
    return ("kept" if end - h0 >= days * 24 else "short"), paid, LEVELS[lv], ups
def run(a):
    pk, Xe, Xf, Ge, h0 = a; Re, Le, Fe = ARR[(pk, Xe)]; Rf, Lf, Ff = ARR[(pk, Xf)]; t = h0; tries = 0
    while t < len(Re) - 24 * 30 and tries < 30:
        tries += 1; i = t; ok = True
        for step in range(3):
            res, i = phase(Re, Le, Fe, i if step == 0 else i + 24, 0.06, 0.05, Ge)
            if res != "pass": ok = False; break
        if ok:
            st, paid, top, ups = pro(Rf, Lf, Ff, i + 48)
            return dict(days=(i - h0) / 24, tries=tries, status=st, paid=paid, top=top, ups=ups, h0=h0)
        if res == "open": break
        t = i + 24
    return dict(days=np.nan, tries=tries, status="never", paid=0.0, top=0, ups=0, h0=h0)
if __name__ == "__main__":
    st = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    cfgs = [(pk, Xe, Xf, Ge) for pk in ("21", "A", "B") for Xe in (1.5, 2.0, 3.0, 4.0) for Xf in (1.0, 1.5, 2.0) for Ge in (0.03, 1.0)]
    rows = []; keep = {}
    for c in cfgs:
        with Pool(os.cpu_count()) as p: D = pd.DataFrame(p.map(run, [c + (h,) for h in st]))
        F = D[D.status.isin(["kept", "breached"])]; keep[c] = D
        rows.append(dict(pack=c[0], eval_x=c[1], pro_x=c[2], eval_guard="3%" if c[3] < 1 else "off", median_days=D.days.median(), p75_days=D.days.quantile(.75),
                         first_try=round(100 * (D.tries == 1).mean()), avg_fees=round(22 * D.tries.mean() + 50), pro_kept=round(100 * (F.status == "kept").mean()),
                         paid_median=round(F.paid.median()), paid_p10=round(F.paid.quantile(.1)), paid_p90=round(F.paid.quantile(.9)), median_top=f"${F.top.median():,.0f}"))
        print(rows[-1], flush=True)
    R = pd.DataFrame(rows); pd.set_option("display.width", 250); R.to_csv("bootcamp_grid.csv", index=False)
    print("\nFULL GRID:"); print(R.to_string(index=False))
    pd.to_pickle(keep, "bootcamp_runs.pkl")
