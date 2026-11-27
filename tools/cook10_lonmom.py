# Post-hoc idea from moments.py: NQ fade at the London open lost in train AND holdout -> test the opposite (follow the first-15-min move).
# Same rules as FADE but direction = sign of the move; stop = the move's size; exit 30 min later. Also hold 60/120 min and a 1-bar delay.
import numpy as np, pandas as pd
exec(open("transfer.py").read().split("JOBS = ")[0])
COST.update(NQ=.00015)
HOME.update({"ASIA": ("America/New_York", 18, 0)})
def MOM(sym, home, hold=6, costm=1.0, delay=0, mult=1.5, rand=None):
    b = m5(sym); mins, day = session(b, home); O, H, L, C = (b[c].to_numpy() for c in "ohlc"); T = b.index; rows = []
    for d_ in np.unique(day):
        ix = np.where(day == d_)[0]; m = mins[ix]; a = ix[m == 0]; z = ix[m == 15]
        if len(a) and len(z): rows.append((d_, a[0], z[0], C[z[0] - 1] - O[a[0]]))
    mv = pd.Series([r[3] for r in rows]); med = mv.abs().rolling(60, min_periods=30).median().shift(1).to_numpy(); out = []
    for (d_, a, z, m_), md in zip(rows, med):
        if not np.isfinite(md) or abs(m_) < mult * md: continue
        dr = int(np.sign(m_)) if rand is None else (1 if rand.random() < .5 else -1)
        z2 = z + delay
        if z2 + hold >= len(C): continue
        e = O[z2]; risk = abs(m_); stop = e - dr * risk
        if risk <= 3 * COST[sym] * e: continue
        x, _ = walk(O, H, L, C, z2, z2 + hold, dr, e, stop, None); out.append((T[z], (dr * (x - e) - costm * COST[sym] * e) / risk))
    return out
S = pd.Timestamp("2023-01-01", tz="UTC"); tt = lambda v: round(v.mean() / v.std(ddof=1) * np.sqrt(len(v)), 2) if len(v) > 2 else np.nan
rows = []
for home in ("LDN", "ASIA"):
    for nm, kw in (("base 30m", {}), ("hold 60m", dict(hold=12)), ("hold 120m", dict(hold=24)), ("double costs", dict(costm=2.0)), ("1 bar late", dict(delay=1)), ("move>1.2x", dict(mult=1.2)), ("move>2x", dict(mult=2.0))):
        D = pd.DataFrame(MOM("NQ", home, **kw), columns=["t", "R"]); A, B = D[D.t < S].R, D[D.t >= S].R; y = D.groupby(D.t.dt.year).R.sum()
        r = dict(open=home, variant=nm, trades=len(D), win=round(100 * (D.R > 0).mean()), avgR=round(D.R.mean(), 3), t_train=tt(A), avgR_hold=round(B.mean(), 3), t_hold=tt(B), pos_years=f"{(y > 0).sum()}/{len(y)}")
        if nm == "base 30m":
            rnd = [np.mean([x[1] for x in MOM("NQ", home, rand=np.random.default_rng(s))]) for s in range(40)]; r["beats_random"] = f"{100*np.mean(np.array(rnd) < D.R.mean()):.0f}%"; r["random_mean"] = round(np.mean(rnd), 3)
            D.to_pickle(f"lonmom_{home}.pkl")
        rows.append(r); print(r, flush=True)
R = pd.DataFrame(rows); pd.set_option("display.width", 250); print(R.to_string(index=False)); R.to_csv("lonmom.csv", index=False)
