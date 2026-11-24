# Book sims: 21 EAs alone vs + crypto A / B / both, hourly mark-to-market components. The5ers High Stakes 2-Step at 3x (eval and funded),
# all start dates (2020-09..2025-06) and holdout-only starts (2023-01..2025-06). Then the $20K Bootcamp (steps 3x, Pro 1.5x).
import sys
exec(open("firms.py").read().split('\nif __name__ == "__main__":')[0])
sys.argv = sys.argv[:1]
import cat1000 as K
TR = pd.read_pickle("csleeve_trades.pkl")
HB = {s: K.bars(s, "H1").reindex(idx, method="ffill") for s in ("ETH", "BTC")}
def comp(t, rf):
    R = np.zeros(len(idx)); Lw = np.zeros(len(idx)); Fl = np.zeros(len(idx)); hb = HB[t.sym.iloc[0]]
    Cl, Hi, Lo = hb.c.to_numpy(), hb.h.to_numpy(), hb.l.to_numpy()
    for r in t.itertuples():
        h0 = idx.searchsorted(r.t_in, "right") - 1; h1 = idx.searchsorted(r.t_out, "right") - 1
        if h0 < 0 or h1 >= len(idx): continue
        prev = r.e; cum = 0.0
        for h in range(h0, h1):
            inc = r.d * (Cl[h] - prev) / r.risk; worst = r.d * ((Lo[h] if r.d > 0 else Hi[h]) - prev) / r.risk; worst = max(worst, -1.0 - cum)
            R[h] += rf * inc; Lw[h] += rf * min(worst, inc, 0.0); Fl[h] += rf * inc; cum += inc; prev = Cl[h]
        last = r.R - cum; R[h1] += rf * last; Lw[h1] += rf * min(last, 0.0); Fl[h1] -= rf * cum
    return [R, Lw, Fl]
BASE_NAMES = list(NAMES)
def setbook(extra):
    for nm in [n for n in NAMES if n not in BASE_NAMES]: NAMES.remove(nm); COMP.pop(nm, None)
    for nm, c in extra.items(): COMP[nm] = c; PORT["21"][nm] = 1.0; BASE[nm] = 0.1; NAMES.append(nm)
def hs(starts, tag):
    with Pool(os.cpu_count()) as p: d = pd.DataFrame(p.map(uf, [(h, 3.0, "The5ers High Stakes 2-Step") for h in starts]), columns=["days", "tries", "i"])
    with Pool(os.cpu_count()) as p: g = pd.DataFrame(p.map(fund, [(h, 3.0, 3.0, "The5ers High Stakes 2-Step") for h in starts]), columns=["o", "pct"])
    ok = g[g.o.notna()]
    return dict(book=tag, median_days=d.days.median(), p75_days=d.days.quantile(.75), first_try=round(100 * (d.tries == 1).mean()), kept=round(100 * (ok.o == "kept").mean()),
                yr_median=round(100 * ok.pct.median(), 1), yr_p10=round(100 * ok.pct.quantile(.1), 1), yr_p90=round(100 * ok.pct.quantile(.9), 1))
def daily_stats():
    build({c: PORT["21"].get(c, 1.0) for c in NAMES}); d = pd.Series(EQ_R, idx).groupby(idx.normalize()).sum().loc["2020-09-01":]
    s = lambda x: round(x.mean() / x.std() * np.sqrt(365), 2); S_ = pd.Timestamp("2023-01-01", tz="UTC")
    eq = d.cumsum(); dd = (eq - eq.cummax()).min()
    return s(d[d.index < S_]), s(d[d.index >= S_]), round(100 * d.sum() / 6.2, 1), round(100 * dd, 1)
if __name__ == "__main__":
    ALL = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    HOLD = [idx.searchsorted(s) for s in pd.date_range("2023-01-01", "2025-06-30", freq="7D", tz="UTC")]
    t = TR[("A", 1.0)]; print("notional per trade as x of account at 0.6% risk (0.2% x3): median", round(0.006 * t.notional_x_risk.median(), 2), "| 90th pct", round(0.006 * t.notional_x_risk.quantile(.9), 2), "(ETH)")
    t = TR[("B", 1.0)]; print("                                                 median", round(0.006 * t.notional_x_risk.median(), 2), "| 90th pct", round(0.006 * t.notional_x_risk.quantile(.9), 2), "(BTC)", flush=True)
    CFG = [("21 EAs", {}, 1.0), ("+A 0.2%", {"A": 0.002}, 1.0), ("+B 0.2%", {"B": 0.002}, 1.0), ("+A+B 0.1% each", {"A": 0.001, "B": 0.001}, 1.0),
           ("+A+B 0.2% each", {"A": 0.002, "B": 0.002}, 1.0), ("+A+B 0.1% each, spread x2", {"A": 0.001, "B": 0.001}, 2.0), ("+A+B 0.2% each, spread x2", {"A": 0.002, "B": 0.002}, 2.0)]
    rows = []
    for tag, ex, cm in CFG:
        setbook({f"cr{w}": comp(TR[(w, cm)], rf) for w, rf in ex.items()})
        sa, sb, yr, dd = daily_stats()
        if ex:
            build({c: (PORT["21"].get(c, 1.0) if c in BASE_NAMES else 0) for c in NAMES}); bk = pd.Series(EQ_R, idx).groupby(idx.normalize()).sum()
            build({c: (1.0 if c not in BASE_NAMES else 0) for c in NAMES}); cr = pd.Series(EQ_R, idx).groupby(idx.normalize()).sum(); corr = round(bk.loc["2020-09-01":].corr(cr.loc["2020-09-01":]), 2)
        else: corr = np.nan
        for lab, stt in (("all starts", ALL), ("holdout starts", HOLD)):
            r = hs(stt, tag); r.update(starts=lab, sharpe_2020_22=sa, sharpe_2023_26=sb, pct_yr_x1=yr, maxdd_x1=dd, corr_with_book=corr); rows.append(r); print(r, flush=True)
    R = pd.DataFrame(rows); R.to_csv("csleeve_hs.csv", index=False); pd.set_option("display.width", 250)
    print("\nTHE5ERS HIGH STAKES (3x):"); print(R.to_string(index=False))
    # Bootcamp: steps 3x, Pro 1.5x (from bootcamp.py functions)
    src = open("bootcamp.py").read(); exec(src[src.index("def phase("):src.index('\nif __name__ == "__main__":')].replace("ARR[(pk, Xe)]", "ARR[pk, Xe]").replace("ARR[(pk, Xf)]", "ARR[pk, Xf]"))
    LEVELS = [20000, 25000, 30000, 40000, 50000, 60000, 80000, 100000]; SPLIT = lambda s: 0.5 if s == 20000 else 0.75
    globals().update(LEVELS=LEVELS, SPLIT=SPLIT); ARR = {}; globals()["ARR"] = ARR
    out = []
    for tag, ex, cm in (("21 EAs", {}, 1.0), ("+A+B 0.2% each", {"A": 0.002, "B": 0.002}, 1.0), ("+A+B 0.2% each, spread x2", {"A": 0.002, "B": 0.002}, 2.0)):
        setbook({f"cr{w}": comp(TR[(w, cm)], rf) for w, rf in ex.items()})
        for X_ in (1.5, 3.0):
            build({c: min(PORT["21"].get(c, 1.0) * X_, 1.0 / BASE[c]) for c in NAMES}); ARR[(tag, X_)] = (EQ_R.copy(), EQ_L.copy(), D_FLT.copy())
        for lab, stt in (("all starts", ALL), ("holdout starts", HOLD)):
            with Pool(os.cpu_count()) as p: D = pd.DataFrame(p.map(run, [(tag, 3.0, 1.5, 1.0, h) for h in stt]))
            F = D[D.status.isin(["kept", "breached"])]
            out.append(dict(book=tag, starts=lab, median_days=D.days.median(), first_try=round(100 * (D.tries == 1).mean()), pro_kept=round(100 * (F.status == "kept").mean()),
                            paid_median=round(F.paid.median()), paid_p10=round(F.paid.quantile(.1)), paid_p90=round(F.paid.quantile(.9)), median_level=f"${F.top.median():,.0f}")); print(out[-1], flush=True)
    print("\nBOOTCAMP $20K (steps 3x, Pro 1.5x):"); print(pd.DataFrame(out).to_string(index=False)); pd.DataFrame(out).to_csv("csleeve_bootcamp.csv", index=False)
