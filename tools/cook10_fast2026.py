# Faster pass vs risk: The5ers High Stakes $10K (8% then 5%, 5% daily from the higher of day-start balance/equity, 10% static, 3 profitable days),
# EA guard 4%. Challenge risk x {3,4,5,6,8}; book = 21 EAs or 21 + BTC #448 at 0.1% (real costs). Failed attempt -> new one the next day.
# Then the 2026 replay: challenge from 2 Jan 2026 at the fast setting, funded at 3x with the scaling plan to 31 Oct 2026.
import sys
exec(open("csleeve_sim.py").read().split('\nif __name__ == "__main__":')[0])
src = open("y2026_scale.py").read(); exec(src[src.index("LEVELS = "):src.index("def scale_run")]); exec(src[src.index("def scale_run"):src.index('\nif __name__ == "__main__":')])
def phase(R, L, F, h0, target, end):
    eq = 1.0; opn = 0.0; day = -1; hd = -1; floor = 0.90; Z = 0.08; dp = []; dstart = 1.0; ref = 1.0; mm = 1.0
    for i in range(h0, end):
        if DAYN[i] != day:
            bal = eq - opn
            if day != -1: dp.append(bal - dstart)
            if bal >= 1 + target and sum(x > 0.005 for x in dp) >= 3: return "pass", i
            day = DAYN[i]; dstart = bal; ref = max(bal, eq); mm = max(0.0, min(1.0, (eq - floor) / Z))
        if hd == day or (R[i] == 0 and L[i] == 0):
            if hd == day: opn = 0.0
            continue
        low = eq * (1 + mm * L[i]); after = eq * (1 + mm * R[i])
        if low <= ref - 0.04: eq = min(after, max(low, ref - 0.043)); opn = 0.0; hd = day
        elif low <= floor or low <= ref - 0.05: return "fail", i
        else: opn += eq * mm * F[i]; eq = after
    return "open", end
def attempt(arr, h0, end=None):
    R, L, F = arr; end = end or len(R); t = h0; tries = 0
    while t < end - 48 and tries < 12:
        tries += 1; a, i = phase(R, L, F, t, 0.08, end)
        if a == "pass":
            b, j = phase(R, L, F, i + 24, 0.05, end)
            if b == "pass": return tries, (j - h0) / 24, j
            if b == "open": return tries, np.nan, None
            t = j + 24; continue
        if a == "open": return tries, np.nan, None
        t = i + 24
    return tries, np.nan, None
if __name__ == "__main__":
    ALL = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    Y26 = [idx.searchsorted(s) for s in pd.date_range("2026-01-02", "2026-08-28", freq="7D", tz="UTC")]
    rows = []; ARRS = {}
    for book, ex in (("21 EAs", {}), ("21 EAs + BTC #448 0.1%", {"B": 0.001})):
        setbook({f"cr{w}": comp(TR[(w, "real")], rf) for w, rf in ex.items()})
        for X_ in (3.0, 4.0, 5.0, 6.0, 8.0):
            build({c: min(PORT["21"].get(c, 1.0) * X_, 1.0 / BASE[c]) for c in NAMES}); arr = (EQ_R.copy(), EQ_L.copy(), D_FLT.copy()); ARRS[(book, X_)] = arr
            for lab, st in (("2020-25 starts", ALL), ("2026 starts", Y26)):
                res = [attempt(arr, h) for h in st]; tr = np.array([r[0] for r in res]); dd = np.array([r[1] for r in res])
                rows.append(dict(book=book, risk_x=X_, starts=lab, first_try=round(100 * np.mean(tr == 1)), avg_attempts=round(tr.mean(), 2), median_days=np.nanmedian(dd),
                                 within_30d=round(100 * np.mean(dd <= 30)), within_45d=round(100 * np.mean(dd <= 45)), never=round(100 * np.mean(np.isnan(dd))))); print(rows[-1], flush=True)
    P = pd.DataFrame(rows); P.to_csv("fast2026.csv", index=False); pd.set_option("display.width", 220); print(P.to_string(index=False))
    print("\n2026 REPLAY: challenge from 2 Jan 2026 at risk X, then funded at 3x with the scaling plan to 31 Oct 2026 ($10K start):")
    h0 = idx.searchsorted(pd.Timestamp("2026-01-02", tz="UTC")); out = []
    for book, ex in (("21 EAs", {}), ("21 EAs + BTC #448 0.1%", {"B": 0.001})):
        setbook({f"cr{w}": comp(TR[(w, "real")], rf) for w, rf in ex.items()})
        for X_ in (3.0, 4.0, 5.0, 6.0, 8.0):
            tries, days, j = attempt(ARRS[(book, X_)], h0)
            if j is None: out.append(dict(book=book, challenge_risk=X_, attempts=tries, funded_on="not funded")); continue
            globals()["X"] = 3.0; st, log, paid, lv, eq = scale_run(j + 48, len(idx) - 1); size = LEVELS[lv]
            openp = (eq - 1) * size * SPLIT.get(size, .8)
            out.append(dict(book=book, challenge_risk=X_, attempts=tries, days_to_funded=days, funded_on=str(idx[j].date()), status=st, level_on_31_oct=f"${size:,}",
                            paid_to_you=round(paid), plus_open_profit_share=round(openp), total_2026=round(paid + max(openp, 0)), pct_of_10k=round(100 * (paid + max(openp, 0)) / 10000)))
            print(out[-1], flush=True)
    print(pd.DataFrame(out).to_string(index=False))
