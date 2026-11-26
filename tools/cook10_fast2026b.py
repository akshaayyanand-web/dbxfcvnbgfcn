# Same risk in both stages (The5ers wants consistent risk between the challenge and funded): 4x everywhere vs 3x everywhere.
import sys
exec(open("fast2026.py").read().split('\nif __name__ == "__main__":')[0])
if __name__ == "__main__":
    ALL = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]; h0 = idx.searchsorted(pd.Timestamp("2026-01-02", tz="UTC"))
    for book, ex in (("21 EAs", {}), ("21 EAs + BTC #448 0.1%", {"B": 0.001})):
        setbook({f"cr{w}": comp(TR[(w, "real")], rf) for w, rf in ex.items()})
        for X_ in (3.0, 4.0):
            with Pool(os.cpu_count()) as p: g = pd.DataFrame(p.map(fund, [(h, X_, X_, "The5ers High Stakes 2-Step") for h in ALL]), columns=["o", "pct"])
            ok = g[g.o.notna()]
            build({c: min(PORT["21"].get(c, 1.0) * X_, 1.0 / BASE[c]) for c in NAMES}); tries, days, j = attempt((EQ_R.copy(), EQ_L.copy(), D_FLT.copy()), h0)
            globals()["X"] = X_; st, log, paid, lv, eq = scale_run(j + 48, len(idx) - 1); size = LEVELS[lv]
            print(dict(book=book, risk_both_stages=X_, funded_kept=round(100 * (ok.o == "kept").mean()), funded_yr_median=round(100 * ok.pct.median(), 1), funded_yr_bad10=round(100 * ok.pct.quantile(.1), 1),
                       y2026_days_to_funded=days, y2026_status=st, y2026_level=f"${size:,}", y2026_paid=round(paid), y2026_pct=round(100 * paid / 10000)), flush=True)
