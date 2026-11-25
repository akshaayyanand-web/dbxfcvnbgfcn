import numpy as np, pandas as pd
exec(open("fade_lab.py").read().split('\nif __name__ == "__main__":')[0])
def trades(sym):
    days, gap = DATA[sym]; L, M = SYM[sym][1], SYM[sym][2]; out = []
    for day, x in days.items():
        m = x.m.to_numpy(); c = x.c.to_numpy(); o = x.o.to_numpy(); h = x.h.to_numpy(); l = x.l.to_numpy(); s = x.slope.to_numpy(); T = len(c)
        for k in range(L, T - 2):
            if m[k] < 570 or m[k] >= 600 or m[k] - m[k - L] != L: continue
            mv = c[k] - c[k - L]
            if abs(mv) < M: continue
            sg = 1 if mv > 0 else -1
            if s[k] != sg: continue
            d = -sg; e = o[k + 1]; sd = abs(mv); stop = e - d * sd; end = min(k + 31, T - 1); xp = c[end]
            for q in range(k + 1, end + 1):
                if (d > 0 and l[q] <= stop) or (d < 0 and h[q] >= stop): xp = min(o[q], stop) if d > 0 else max(o[q], stop); break
            out.append((day, d, (d * (xp - e) - COST * e) / sd)); break
    return pd.DataFrame(out, columns=["day", "d", "R"]).set_index("day")
for s in SYM: DATA[s] = prep(s)
a, b = trades("SPX"), trades("NQ"); j = a.join(b, lsuffix="_spx", rsuffix="_nq", how="outer")
both = j.dropna(); same = both[both.d_spx == both.d_nq]
print(f"S&P fade days {len(a)}, Nasdaq fade days {len(b)}, both on the same day {len(both)} ({len(same)} in the same direction)")
print(f"same-day same-direction: R correlation {same.R_spx.corr(same.R_nq):.2f}; both lose {100*((same.R_spx<0)&(same.R_nq<0)).mean():.0f}%, both win {100*((same.R_spx>0)&(same.R_nq>0)).mean():.0f}%; avg combined {same.R_spx.add(same.R_nq).mean():+.2f}R")
solo = pd.concat([j.R_spx[j.R_nq.isna()].dropna(), j.R_nq[j.R_spx.isna()].dropna()]); print(f"days with only one fade: avg {solo.mean():+.3f}R ({len(solo)} days)")
for lab, w in (("current (1% each, always)", 1.0), ("halve both when both fire the same way", 0.5)):
    tot = j.R_spx.fillna(0) + j.R_nq.fillna(0)
    sm = (j.d_spx == j.d_nq) & j.R_spx.notna() & j.R_nq.notna(); tot2 = tot.where(~sm, w * tot)
    yr = tot2.groupby(tot2.index.year).sum(); eq = tot2.cumsum(); dd = (eq - eq.cummax()).min()
    print(f"{lab}: total {tot2.sum():.1f}R over {len(yr)} yrs ({tot2.sum()/7.8:.1f} R/yr), worst day {tot2.min():.2f}R, worst drawdown {dd:.1f}R, days <= -1.5R: {(tot2<=-1.5).sum()}")
