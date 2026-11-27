# Out-of-sample confirmation: the positioning rules from positioning.py, UNCHANGED, on SOL and XRP (never used to find them).
# Key question: does "P4 new money trend" (+0.20R on BTC/ETH in every period) hold up on coins it has not seen?
import numpy as np, pandas as pd
src = open("positioning.py").read(); exec(src[:src.index('if __name__ == "__main__":')])
COST.update(SOL=.0015, XRP=.002); SWAP.update(SOL=.15, XRP=.15)
rows = []; SP = pd.Timestamp("2023-01-01", tz="UTC"); tt = lambda v: round(v.mean() / v.std(ddof=1) * np.sqrt(len(v)), 2) if len(v) > 2 else np.nan
for sym in ("SOL", "XRP"):
    b, S, have = signals(sym); print(sym, "metrics coverage", round(100 * have.mean()), "% of hours, from", b.index[have.argmax()].date(), flush=True)
    for name, sig in S.items():
        hold = 72 if "72h" in name else 24; D = pd.DataFrame(trades(b, sig, sym, hold), columns=["t", "R"])
        if len(D) < 20: rows.append(dict(market=sym, rule=name, trades=len(D))); continue
        A_, B_ = D[D.t < SP].R, D[D.t >= SP].R; y = D.groupby(D.t.dt.year).R.sum()
        rnd = [np.mean([x[1] for x in trades(b, sig, sym, hold, rand=np.random.default_rng(s))]) for s in range(40)]
        rows.append(dict(market=sym, rule=name, trades=len(D), win=round(100 * (D.R > 0).mean()), avgR=round(D.R.mean(), 3), t_all=tt(D.R), avgR_train=round(A_.mean(), 3), avgR_hold=round(B_.mean(), 3), t_hold=tt(B_),
                         random=round(np.mean(rnd), 3), beats_random=round(100 * np.mean(np.array(rnd) < D.R.mean())), dbl_cost=round(np.mean([x[1] for x in trades(b, sig, sym, hold, cm=2)]), 3),
                         late_1h=round(np.mean([x[1] for x in trades(b, sig, sym, hold, delay=1)]), 3), pos_years=f"{(y > 0).sum()}/{len(y)}")); print(rows[-1], flush=True)
        D.to_pickle(f"pos_{sym}_{name.split()[0]}_{hold}.pkl")
R = pd.DataFrame(rows); pd.set_option("display.width", 260); print(R.to_string(index=False)); R.to_csv("positioning_oos.csv", index=False)
