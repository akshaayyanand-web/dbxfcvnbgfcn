# Run from the scratchpad (needs fund_check.py etc.; see tools/fast_preset_test.py).
import sys, numpy as np, pandas as pd
exec(open('fund_check.py').read().split("C = [")[0])
exec("dst =" + open('fund_check.py').read().split("dst =")[1].split("with Pool")[0])
b5 = bars1("fut1m/USA500IDXUSD_1m.csv", "5min"); c = b5.c; Cc = c.to_numpy()
atr5 = rma(pd.concat([b5.h - b5.l, (b5.h - c.shift()).abs(), (b5.l - c.shift()).abs()], axis=1).max(axis=1), 14).to_numpy()
ny = b5.index.tz_convert("America/New_York"); nym = ny.hour * 60 + ny.minute; win = (nym >= 570) & (nym < 720); flat = nym >= 950
V = {}
for N, en, sm in ((20, 800, 2.0), (20, 200, 1.0), (50, 200, 2.0), (20, 800, 1.0)):
    hi = b5.h.rolling(N).max().shift(1).to_numpy(); lo_ = b5.l.rolling(N).min().shift(1).to_numpy(); e = c.ewm(span=en, adjust=False).mean().to_numpy()
    tr = simT(b5, win & (Cc > hi) & (Cc > e), win & (Cc < lo_) & (Cc < e), sm * atr5, 10 ** 6, flat)
    for cm in (1, 2):
        V[(N, en, sm, cm)] = P.trade_series(tr, 0.0001 * cm, spx, idx)
    yrs = (idx[-1] - idx[0]).days / 365.25; r1 = V[(N, en, sm, 1)][0]; r2 = V[(N, en, sm, 2)][0]
    A = idx < split
    dd = pd.DataFrame({"spxbo": r1, "orb15": RM[KEYS.index("orb15")], "nqbo15": RM[KEYS.index("nqbo15")], "port": RB["8|btc0.75|x1.25"][0]}, index=idx).resample("1D").sum()
    print(f"SPX 5m breakout {N}-bar EMA{en} stop{sm}: {len(tr)/(yrs*12):.0f}/mo, %/yr@1%: A {100*r1[A].sum()/(yrs*(A.mean())):+.1f} B {100*r1[~A].sum()/(yrs*(1-A.mean())):+.1f} costs x2 {100*r2.sum()/yrs:+.1f} | corr orb {dd.corr().loc['spxbo','orb15']:.2f} nqbo {dd.corr().loc['spxbo','nqbo15']:.2f} portfolio {dd.corr().loc['spxbo','port']:.2f}", flush=True)
RULE = ("room", 1.0, 1.0, 0.03, 0.905, -1)
C = [("8|btc0.75|x1.25", RULE, "fast preset")]
for key in V:
    if key[3] != 1: continue
    for w in (0.05, 0.1, 0.15, 0.2):
        for cm in (1, 2):
            nm = f"+SPX bo {key[0]}/{key[1]}/{key[2]} @{w} costs{cm}"; r_, l_ = V[key[:3] + (cm,)]
            RB[nm] = (RB["8|btc0.75|x1.25"][0] + w * r_ * (1 if cm == 1 else 1), RB["8|btc0.75|x1.25"][1] + w * l_); C.append((nm, RULE, nm))
if __name__ == "__main__":
    with Pool(4) as p: rows = p.map(job, C)
    pd.set_option("display.width", 300); print(pd.DataFrame(rows).round(1).to_string(index=False), flush=True)
