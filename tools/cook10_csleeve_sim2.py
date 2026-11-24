import sys
exec(open("csleeve_sim.py").read().split('\nif __name__ == "__main__":')[0])
if __name__ == "__main__":
    ALL = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    HOLD = [idx.searchsorted(s) for s in pd.date_range("2023-01-01", "2025-06-30", freq="7D", tz="UTC")]
    rows = []
    for tag, ex in (("21 EAs", {}), ("+B 0.1% (real cost)", {"B": 0.001}), ("+B 0.2% (real cost)", {"B": 0.002}), ("+A+B 0.1% each (real cost)", {"A": 0.001, "B": 0.001}), ("+A 0.05% +B 0.1% (real cost)", {"A": 0.0005, "B": 0.001})):
        setbook({f"cr{w}": comp(TR[(w, "real")], rf) for w, rf in ex.items()}); sa, sb, yr, dd = daily_stats()
        for lab, stt in (("all starts", ALL), ("holdout starts", HOLD)):
            r = hs(stt, tag); r.update(starts=lab, sharpe_2020_22=sa, sharpe_2023_26=sb, pct_yr_x1=yr, maxdd_x1=dd); rows.append(r); print(r, flush=True)
    R = pd.DataFrame(rows); R.to_csv("csleeve_hs_real.csv", index=False); pd.set_option("display.width", 250); print(R.to_string(index=False))
