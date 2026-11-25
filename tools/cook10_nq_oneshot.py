# "One trade = $1K" on NQ for The5ers High Stakes $10K. Risk $480 (just under the $500 daily limit), target $1,000 (2.08x the stop).
# Entries: the NQ EAs' real signals. Stop = k x the EA's own stop distance (position sized to lose $480 there). Hold until TP or SL (10-day cap).
# Challenge: Phase 1 +$800, Phase 2 +$500, max loss $1,000, one trade at a time, max one losing trade per day; after a $1K win the
# 3-profitable-days rule is assumed met with two micro trades (not modelled). Fail = can no longer afford a full $480 shot without breaching.
import sys, numpy as np, pandas as pd
exec(open("fixedtp.py").read().split('\nif __name__ == "__main__":')[0])
RISK, TP = 480.0, 1000.0; r = TP / RISK
def phase(T, start, target):
    eq = 0.0; busy = start; lost_day = None
    for t in T[T.et >= start].itertuples():
        if t.et < busy: continue
        dk = (t.et + pd.Timedelta(hours=2)).date()
        if lost_day == dk: continue
        if eq - RISK * 1.05 <= -1000: return "fail", t.et                  # cannot afford another full shot
        pnl = RISK * t.R; eq += pnl; busy = t.xt
        if pnl < 0: lost_day = dk
        if eq <= -1000: return "fail", t.xt
        if eq >= target: return "pass", t.xt
    return "open", None
def sim(T, starts):
    out = []
    for s in starts:
        t0 = s; tries = 0
        while tries < 30:
            tries += 1; a, t1 = phase(T, t0, 800)
            if a == "pass":
                b, t2 = phase(T, t1 + pd.Timedelta(days=1), 500)
                if b == "pass": out.append((tries, (t2 - s).days)); break
                if b == "open": out.append((tries, np.nan)); break
                t0 = t2 + pd.Timedelta(days=1); continue
            if a == "open": out.append((tries, np.nan)); break
            t0 = t1 + pd.Timedelta(days=1)
    return pd.DataFrame(out, columns=["tries", "days"])
if __name__ == "__main__":
    starts = list(pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")); rows = []
    sets = {"NQ Opening Range": ["orb15"], "NQ Breakout 15m": ["nqbo15"], "NQ Dip 2h": ["nq2h"], "NQ Open Fade": ["nqfade"], "all 4 NQ EAs": ["orb15", "nqbo15", "nq2h", "nqfade"]}
    for nm, eas in sets.items():
        for k in (1, 2, 3):
            T = pd.concat([resim(c, k, r, "hold").assign(ea=c) for c in eas]).sort_values("et").reset_index(drop=True)
            if len(T) < 30: continue
            p = (T.res == "win").mean(); R = sim(T, starts); S_ = pd.Timestamp("2023-01-01", tz="UTC")
            rows.append(dict(setup=nm, stop_x=k, trades=len(T), win_rate=round(100 * p, 1), win_2023on=round(100 * (T[T.et >= S_].res == "win").mean(), 1),
                             avg_trade=round(RISK * T.R.mean()), p_pass_both_2shots=round(100 * (1 - (1 - p) ** 2) ** 2),
                             pass_first_try=round(100 * (R.tries == 1).mean()), avg_tries=round(R.tries.mean(), 2), median_days=R.days.median(), p75_days=R.days.quantile(.75)))
            print(rows[-1], flush=True)
    X = pd.DataFrame(rows); X.to_csv("nq_oneshot.csv", index=False); pd.set_option("display.width", 220); print(X.to_string(index=False))
