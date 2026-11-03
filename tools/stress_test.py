# Stress test of the 8 EAs: higher trading costs, and a block-bootstrap Monte Carlo of the 2-step evaluation.
import sys, numpy as np, pandas as pd
SP = sys.argv[1]
src = open(SP + "/losers.py").read().split("FEATS = [")[0].replace("0.00012 if df is nq else 0.0001", "(0.00012 if df is nq else 0.0001) * GRIDCOST")
GRIDCOST = 1.0
exec(src)
_l = open(SP + "/losers.py").read(); exec("def run3" + _l.split("def run3", 1)[1].split("wst =")[0])
INTRA = {"gasia", "nqmom", "gmom", "orb15"}
def build(mult_all, mult_intra):
    global GRIDCOST
    Rm, LOm = R.copy(), LO.copy()
    for k in USED:
        i = names.index(k); m = mult_all * (mult_intra if k in INTRA else 1.0)
        if k in ("nqdip", "spxdip"):
            GRIDCOST = m; r, lo, _ = grid_run(nq if k == "nqdip" else spx); GRIDCOST = 1.0
        else:
            trades, cost, h1 = TR[k]; r, lo = P.trade_series(trades, cost * m, h1, idx)
        Rm[i], LOm[i] = r, lo
    return Rm, LOm
wst = pd.date_range("2020-04-01", "2025-10-01", freq="MS", tz="UTC")
def evaluate(Rm, LOm):
    res = []
    for s_ in est:
        h0 = idx.searchsorted(s_); a, i1, _ = run3(W, Rm, LOm, h0, len(idx), 0.10)
        if a != "pass": res.append(a); continue
        b, i2, _ = run3(W, Rm, LOm, h0 + i1 + 1, len(idx), 0.05); res.append(b if b != "pass" else (i1 + i2) / 24)
    yy = [run3(W, Rm, LOm, idx.searchsorted(s_), idx.searchsorted(s_ + pd.DateOffset(years=1)), None) for s_ in wst]
    t = [x for x in res if not isinstance(x, str)]
    return dict(pass_=100 * len(t) / len(res), breach=100 * sum(x == "fail" for x in res) / len(res), days=np.median(t),
                funded_med=100 * np.median([y[2] for y in yy]), funded_breach=sum(y[0] == "fail" for y in yy),
                per_year=100 * (Rm * W[:, None]).sum() / ((idx[-1] - idx[0]).days / 365.25))
rows = []
for lab, ma, mi in (("costs as tested", 1, 1), ("costs x1.5", 1.5, 1), ("costs x2", 2, 1), ("costs x3", 3, 1), ("intraday EAs x3, rest x1", 1, 3)):
    Rm, LOm = build(ma, mi); rows.append(dict(scenario=lab, **evaluate(Rm, LOm))); print(rows[-1], flush=True)
    if lab == "costs as tested": BASE = (Rm, LOm)
    if lab == "costs x2": X2 = (Rm, LOm)
pd.set_option("display.width", 220); print(pd.DataFrame(rows).round(1).to_string(index=False), flush=True)
# Monte Carlo: block bootstrap of whole days (20-day blocks keep crash clusters together)
def days_table(Rm, LOm):
    r = (Rm * W[:, None]).sum(0); lo = (LOm * W[:, None]).sum(0); ds = pd.Series(days); out = []
    for d, ix in ds.groupby(ds).groups.items():
        ix = np.array(sorted(ix)); cum = np.concatenate([[0], np.cumsum(r[ix])[:-1]])
        out.append((r[ix].sum(), np.min(cum + lo[ix])))
    return np.array(out)
rng = np.random.default_rng(7)
def mc(D, n=2000, guard=0.04, maxl=0.10, daily=0.05, horizon=500):
    res = []
    for _ in range(n):
        seq = np.concatenate([D[s:s + 20] for s in rng.integers(0, len(D) - 20, size=horizon // 20 + 2)])[:horizon]
        eq, phase, t0, out = 0.0, 1, 0, "open"
        for t, (cl, worst) in enumerate(seq):
            if worst <= -daily or eq + worst <= -maxl: out = "breach"; break      # guard can't save a gap through the limit
            cl = -guard if worst <= -guard else cl                                # guard closed everything at -4%: the day ends there
            eq += cl
            if eq <= -0.8 * maxl: out = "halted"; break
            if phase == 1 and eq >= 0.10: phase, eq = 2, 0.0
            elif phase == 2 and eq >= 0.05: out = t; break
        res.append(out)
    t = np.array([x for x in res if not isinstance(x, str)])
    return dict(pass_=100 * len(t) / n, breach=100 * sum(x == "breach" for x in res) / n, halted=100 * sum(x == "halted" for x in res) / n,
                median_trading_days=np.median(t), within_60=100 * np.sum(t <= 42) / n, within_120=100 * np.sum(t <= 84) / n)
print("\nMonte Carlo (2,000 reshuffled histories, 2-step +10% then +5%, 10% max / 5% daily, guard at -4%):")
for lab, (Rm, LOm) in (("costs as tested", BASE), ("costs x2", X2)):
    print(lab, {k: round(v, 1) for k, v in mc(days_table(Rm, LOm)).items()}, flush=True)
