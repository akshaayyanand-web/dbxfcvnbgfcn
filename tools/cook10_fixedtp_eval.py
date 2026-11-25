# The5ers High Stakes $10K with fixed-dollar trades: risk $L per trade, target r x $L. One trade open at a time across the chosen EAs
# (chronological), stop trading for the day after a loss. Phase 1: +$800 and 3 profitable days (>= $50); Phase 2: +$500 and 3 profitable days.
# Fail: equity <= -$1,000 (static) or a day's loss > $500. On a fail, restart the next day (new challenge). Start weekly 2020-09..2025-06.
import sys, numpy as np, pandas as pd
exec(open("fixedtp.py").read().split('\nif __name__ == "__main__":')[0])
def pool(eas, k, r, mode):
    allt = []
    for c in eas:
        D = resim(c, k, r, mode); D["ea"] = c; allt.append(D)
    T = pd.concat(allt).sort_values("et").reset_index(drop=True); return T
def challenge(T, L, start, target, days_limit=3650):
    """run one phase from `start`; returns (result, end_time, profit_days)"""
    eq = 0.0; busy_until = start; pdays = {}; lost_day = None; day_pnl = {}
    sub = T[T.et >= start]
    for t in sub.itertuples():
        if t.et < busy_until: continue
        dkey = (t.et + pd.Timedelta(hours=2)).date()                # server day ~ UTC+2
        if lost_day == dkey: continue
        pnl = L * t.R; eq += pnl; busy_until = t.xt; xd = (t.xt + pd.Timedelta(hours=2)).date()
        day_pnl[xd] = day_pnl.get(xd, 0) + pnl
        if pnl < 0: lost_day = dkey
        if day_pnl[xd] < -500 or eq <= -1000: return "fail", t.xt
        if eq >= target and sum(v >= 50 for v in day_pnl.values()) >= 3: return "pass", t.xt
    return "open", None
def run_eval(T, L, starts):
    out = []
    for s in starts:
        t0 = s; tries = 0
        while tries < 15:
            tries += 1
            r1, t1 = challenge(T, L, t0, 800)
            if r1 == "pass":
                r2, t2 = challenge(T, L, t1 + pd.Timedelta(days=1), 500)
                if r2 == "pass": out.append(dict(start=s, tries=tries, days=(t2 - s).days, first=tries == 1)); break
                if r2 == "open": out.append(dict(start=s, tries=tries, days=np.nan, first=False)); break
                t0 = t2 + pd.Timedelta(days=1); continue
            if r1 == "open": out.append(dict(start=s, tries=tries, days=np.nan, first=False)); break
            t0 = t1 + pd.Timedelta(days=1)
    return pd.DataFrame(out)
if __name__ == "__main__":
    W = pd.read_csv("fixedtp_winrates.csv")
    starts = list(pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC"))
    rows = []
    SC = [("$350 per win, risk $400", 400, 0.875), ("$350 per win, risk $350", 350, 1.0), ("$350 per win, risk $200", 200, 1.75),
          ("$1,000 in one trade, risk $400", 400, 2.5), ("High win rate: win $100, risk $400", 400, 0.25), ("High win rate: win $200, risk $400", 400, 0.5)]
    for name, L, r in SC:
        for k in (1, 2):
            for mode in ("native", "hold"):
                cand = W[(W.k == k) & (W["mode"] == mode) & (np.isclose(W.r, r) if r in (0.25, 0.5, 0.875, 2.5) else (W.r == 0.875))]
                if r not in (0.25, 0.5, 0.875, 2.5):
                    eas = list(W[(W.k == k) & (W["mode"] == mode) & (W.r == 0.875)].sort_values("avgR", ascending=False).head(6).ea)
                else:
                    eas = list(cand[cand.avgR > 0].sort_values("win", ascending=False).head(6).ea)
                if not eas: continue
                T = pool(eas, k, r, mode); R = run_eval(T, L, starts)
                wr = 100 * (T.res == "win").mean()
                rows.append(dict(scenario=name, stop_k=k, exit=mode, eas=",".join(eas), trades_per_yr=round(len(T) / 6.2), win_rate=round(wr, 1), avg_trade_usd=round(L * T.R.mean(), 1),
                                 pass_first_try=round(100 * R["first"].mean()), passed_ever=round(100 * R.days.notna().mean()), median_days=R.days.median(), p75_days=R.days.quantile(.75), avg_tries=round(R.tries.mean(), 2)))
                print(rows[-1], flush=True)
    X = pd.DataFrame(rows); X.to_csv("fixedtp_eval.csv", index=False); pd.set_option("display.width", 260); pd.set_option("display.max_colwidth", 60)
    print(X.to_string(index=False))
