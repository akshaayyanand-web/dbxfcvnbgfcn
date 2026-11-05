# Fast preset search for the 8 EAs (Nov 2026).
# Step 1 (cushion grid, logs/cushion.log): boosting risk after a profit cushion, a phase-2-only boost or CPPI sizing all
#   breached (best: 92% pass, 2.8% breached) - the 8 EAs sit right at the edge at 1.0x.
# Step 2 (this grid): per-EA scaling (BTC 1.0/0.75/0.5, others x1.0-2.0) x a room cap that shrinks size as the
#   day-start equity nears the 10% line, x the hard stop line (-8 / -9 / -9.5%). Picked on 2020-22 weekly starts,
#   checked on 2023-25. Winner: BTC 0.75, others x1.25, room cap 3%, stop -9.5%.
# Step 3 (run with "check"): daily starts, funded years, neighbours. Step 4 (run with "stress <mult>"): costs x mult.
# Usage: python3 fast_preset_test.py <scratchpad> [check | stress 2]
# Phase-aware sizing for the 8 (and 9) EAs: boost risk only once the account has a profit cushion,
# room-based (CPPI) sizing, and a Phase-2-only boost. Picked on 2020-22 starts, judged on 2023-25.
import sys, numpy as np, pandas as pd
SP = sys.argv[1]
MODE = sys.argv[2] if len(sys.argv) > 2 else "grid"
if MODE == "stress":
    import portfolio_prop as P
    _o = P.trade_series; CM = float(sys.argv[3])
    P.trade_series = lambda trades, cost, h1, idx: _o(trades, cost * CM, h1, idx)
src = open(SP + "/weightopt.py").read().split("wst = pd.date_range")[0]
exec(src)
from multiprocessing import Pool
DAYN = ((idx - idx[0]) // pd.Timedelta("1D")).to_numpy().astype(np.int64)
W8 = BASE.copy(); W8[-1] = 0.0
def mk(w): return ((RM * w[:, None]).sum(0), (LM * w[:, None]).sum(0))
SETS = {}
for nb, use9 in (("8", False), ("9", True)):
    for btcw in (1.0, 0.75, 0.5):
        for k in (1.0, 1.25, 1.5, 1.75, 2.0):
            w = (BASE if use9 else W8) * k; w = w.copy(); w[0] = btcw; SETS[f"{nb}|btc{btcw}|x{k}"] = w
RB = {k: mk(v) for k, v in SETS.items()}
RB0 = {"8": ((RM * W8[:, None]).sum(0), (LM * W8[:, None]).sum(0)), "9": ((RM * BASE[:, None]).sum(0), (LM * BASE[:, None]).sum(0))}

def mult(rule, phase, eq):
    kind = rule[0]
    if kind == "flat":
        _, m1, m2 = rule; return m1 if phase == 1 else m2
    if kind == "cushion":                       # (c_up, boost, c_dn, cut, p2)
        _, cu, bo, cd, cut, p2 = rule; base = 1.0 if phase == 1 else p2
        if eq - 1 >= cu: return base * bo
        if cd and eq - 1 <= -cd: return base * cut
        return base
    if kind == "room":                          # (m1, m2, Z, stopline, cu): boost, capped so a Z-sized bad day can't reach -10%
        _, m1, m2, Z, sl, cu = rule; base = (m1 if (eq - 1 >= cu) else 1.0) if phase == 1 else m2
        return max(0.0, min(base, (eq - 0.90) / Z))
    if kind == "cppi":                          # risk proportional to room above the -8% stop line
        _, k, hi, p2 = rule; base = 1.0 if phase == 1 else p2
        return base * min(hi, max(0.25, k * (eq - 0.92) / 0.08))
def run4(set_, rule, phase, h0, target, halt=0.8, maxl=0.10, daily=0.05):
    stopl = rule[4] if rule[0] == "room" else 1 - 0.8 * maxl
    r_, lo_ = RB[set_]; eq = 1.0; day = -1; hd = -1; m = 1.0; n = len(r_)
    for i in range(h0, n):
        dd_ = DAYN[i]
        if dd_ != day: day = dd_; dopen = eq; m = mult(rule, phase, eq)   # size set from the day's opening equity
        if hd == dd_: continue
        if r_[i] == 0.0 and lo_[i] == 0.0: continue
        x = eq * (1 + m * lo_[i])
        if x <= 1 - maxl or x <= dopen * (1 - daily): return "fail", i - h0
        eq *= 1 + m * r_[i]
        if eq >= 1 + target: return "pass", i - h0
        if 1 - eq / dopen >= halt * daily: hd = dd_
        if eq <= stopl: return "stopped", i - h0
    return "open", n - h0
EST = [s for s in est]
def ev(args):
    set_, rule, part = args
    sel = [s for s in EST if (s < split) == (part == "A")]; res = []
    for s_ in sel:
        h0 = idx.searchsorted(s_); a, i1 = run4(set_, rule, 1, h0, 0.10)
        if a != "pass": res.append((a, None)); continue
        b2, i2 = run4(set_, rule, 2, h0 + i1 + 1, 0.05); res.append((b2, (i1 + i2) / 24 if b2 == "pass" else None))
    t = np.array([x[1] for x in res if x[1] is not None])
    return dict(set=set_, rule=str(rule), part=part, pass_=100 * np.mean([x[0] == "pass" for x in res]), breach=100 * np.mean([x[0] == "fail" for x in res]),
                days=float(np.median(t)) if len(t) else 999, d90=100 * np.mean([x[1] is not None and x[1] <= 90 for x in res]),
                d60=100 * np.mean([x[1] is not None and x[1] <= 60 for x in res]))
rules = [("flat", 1.0, 1.0)] + [("room", 1.0, 1.0, Z, sl, -1) for Z in (0.03, 0.04, 0.05, 0.06, 0.08) for sl in (0.92, 0.91, 0.905)]
if __name__ == "__main__" and MODE == "grid":
    jobs = [(s, r, "A") for s in SETS for r in rules]
    with Pool(4) as p: A = p.map(ev, jobs, chunksize=4)
    dA = pd.DataFrame(A); dA.to_pickle(SP + "/nobtc_A.pkl")
    pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 60)
    ok = dA[(dA.breach == 0) & (dA.pass_ >= 93)].sort_values("days")
    print(f"{len(ok)} of {len(dA)} kept >=93% pass, 0 breaches on 2020-22", flush=True)
    print(ok.head(30).round(1).to_string(index=False), flush=True)
    pick = pd.concat([dA[dA.set.isin(["8|btc1.0|x1.0", "9|btc1.0|x1.0"]) & (dA.rule == str(("flat", 1.0, 1.0)))], ok.head(30)])
    with Pool(4) as p: B = p.map(ev, [(r.set, eval(r.rule), "B") for r in pick.itertuples()])
    dB = pd.DataFrame(B); m = pick.merge(dB, on=["set", "rule"], suffixes=("_A", "_B")).drop(columns=["part_A", "part_B"])
    m.to_pickle(SP + "/nobtc_AB.pkl"); print(m.round(1).to_string(index=False), flush=True)

# ---- step 3/4: daily starts + funded years ----
def run5(set_, rule, h0, h1, target):
    stopl = rule[4] if rule[0] == "room" else 0.92
    r_, lo_ = RB[set_]; eq = 1.0; day = -1; hd = -1; m = 1.0
    for i in range(h0, h1):
        dd_ = DAYN[i]
        if dd_ != day: day = dd_; dopen = eq; m = mult(rule, 1, eq)
        if hd == dd_: continue
        if r_[i] == 0.0 and lo_[i] == 0.0: continue
        x = eq * (1 + m * lo_[i])
        if x <= 0.90 or x <= dopen * 0.95: return "fail", eq - 1
        eq *= 1 + m * r_[i]
        if target and eq >= 1 + target: return "pass", i - h0
        if 1 - eq / dopen >= 0.04: hd = dd_
        if eq <= stopl: return "stopped", eq - 1
    return "open", eq - 1
wst = pd.date_range("2020-04-01", "2025-10-01", freq="MS", tz="UTC")
C = [("8|btc1.0|x1.0", ("flat", 1.0, 1.0), "current 8 EAs"),
     ("8|btc1.0|x1.0", ("room", 1.0, 1.0, 0.03, 0.905, -1), "current 8 + room cap"),
     ("8|btc0.75|x1.25", ("room", 1.0, 1.0, 0.03, 0.905, -1), "NEW: BTC 0.75, others x1.25, room cap Z3 stop 9.5"),
     ("8|btc0.75|x1.25", ("room", 1.0, 1.0, 0.04, 0.905, -1), "  neighbour Z4"),
     ("8|btc0.75|x1.25", ("room", 1.0, 1.0, 0.05, 0.91, -1), "  neighbour Z5 stop 9"),
     ("8|btc0.75|x1.25", ("room", 1.0, 1.0, 0.08, 0.905, -1), "  neighbour Z8"),
     ("9|btc1.0|x1.0", ("flat", 1.0, 1.0), "current 9 EAs"),
     ("9|btc1.0|x1.0", ("room", 1.0, 1.0, 0.04, 0.905, -1), "9 EAs + room cap Z4")]
dst = pd.date_range("2020-04-01", "2025-09-01", freq="1D", tz="UTC")
def job(c):
    set_, rule, lab = c; out = dict(setup=lab)
    for part, sel in (("A", lambda s: s < split), ("B", lambda s: s >= split)):
        ys = [run5(set_, rule, idx.searchsorted(s), idx.searchsorted(s + pd.DateOffset(years=1)), None) for s in wst if sel(s)]
        out[f"{part}_fund_med"] = 100 * np.median([y[1] for y in ys]); out[f"{part}_fund_br"] = sum(y[0] == "fail" for y in ys); out[f"{part}_fund_stop"] = sum(y[0] == "stopped" for y in ys)
        res = []
        for s in dst:
            if not sel(s): continue
            h0 = idx.searchsorted(s); a, i1 = run4(set_, rule, 1, h0, 0.10)
            if a != "pass": res.append((a, None)); continue
            b, i2 = run4(set_, rule, 2, h0 + i1 + 1, 0.05); res.append((b, (i1 + i2) / 24 if b == "pass" else None))
        t = [x[1] for x in res if x[1] is not None]
        out[f"{part}_pass_daily"] = 100 * np.mean([x[0] == "pass" for x in res]); out[f"{part}_breach_daily"] = 100 * np.mean([x[0] == "fail" for x in res])
        out[f"{part}_days"] = np.median(t); out[f"{part}_in60"] = 100 * np.mean([x[1] is not None and x[1] <= 60 for x in res]); out[f"{part}_in90"] = 100 * np.mean([x[1] is not None and x[1] <= 90 for x in res])
    return out
if __name__ == "__main__" and MODE != "grid":
    if MODE == "stress": C = [C[0], C[2]]
    with Pool(4) as p: rows = p.map(job, C)
    pd.set_option("display.width", 300); print(pd.DataFrame(rows).round(1).to_string(index=False))
