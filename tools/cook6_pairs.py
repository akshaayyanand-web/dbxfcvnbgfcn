# New candidates vs the 8-EA portfolio. Standalone (1% risk) by halves, then portfolio add-on at 0.25 / 0.5.
import sys, numpy as np, pandas as pd
SP = sys.argv[1]
exec(open(SP + "/speed8.py").read().split("V2 = [")[0])
from multiprocessing import Pool
R0, LO0 = R.copy(), LO.copy()
CAND = {}
spx = load_csv(SP + "/fut/USA500IDXUSD.csv"); dow = load_csv(SP + "/fut/USA30IDXUSD.csv"); rut = load_csv(SP + "/fut/USSC2000IDXUSD.csv")
slv = load_csv(SP + "/fut/XAGUSD.csv"); eth = load(SP + "/kh/ETHUSDT.csv").loc["2019-06-01":]
def pair(A, B, ca, cb, n, zin, hold, zstop=4.0, risk=0.01):
    """Long A / short B (or the reverse) when the log spread is zin sigmas from its n-hour mean; exit at the mean,
    after `hold` hours, or at zstop (the stop: sized so hitting it loses `risk`)."""
    a = A.reindex(idx).ffill(); b = B.reindex(idx).ffill(); ok = A.c.reindex(idx).notna().to_numpy() & B.c.reindex(idx).notna().to_numpy()
    s = np.log(a.c) - np.log(b.c); mu = s.rolling(n, min_periods=n // 2).mean().shift(1); sd = s.rolling(n, min_periods=n // 2).std().shift(1)
    S, MU, SD = s.to_numpy(), mu.to_numpy(), sd.to_numpy()
    sa_lo = (np.log(a.l) - np.log(b.h)).to_numpy(); sa_hi = (np.log(a.h) - np.log(b.l)).to_numpy()     # adverse spread inside the hour
    r, lo = np.zeros(len(idx)), np.zeros(len(idx)); pos = 0; t0 = 0; pend = 0
    for i in range(1, len(idx)):
        if pend != 0:                                    # signal on the previous close -> enter at this close
            pos, pend, t0 = pend, 0, i; r[i] -= notional * (ca + cb); continue
        if pos != 0:
            prev = S[i - 1]; stop_s = m0 - pos * zstop * sd0
            hit = (S[i] <= stop_s) if pos == 1 else (S[i] >= stop_s)              # stop judged on the spread's hourly close
            r[i] = notional * pos * (S[i] - prev); lo[i] = min(r[i], 0) * 1.5      # inside-hour adverse: 1.5x the close-to-close loss
            if hit: pos = 0; continue
            z = (S[i] - m0) / sd0
            if pos * z >= 0 or i - t0 >= hold: pos = 0
            continue
        if not ok[i] or np.isnan(SD[i]) or SD[i] <= 0: continue
        z = (S[i] - MU[i]) / SD[i]
        if abs(z) >= zin and abs(z) < zstop - 0.5:
            pend = -1 if z > 0 else 1; m0, sd0 = MU[i], SD[i]
            notional = risk / ((zstop - abs(z)) * sd0)                                        # ~loses `risk` if the stop is hit
    return r, lo
PAIRS = {"NQ/SPX": (nq, spx, 0.00012, 0.0001), "Gold/Silver": (gold, slv, 0.0001, 0.00025), "BTC/ETH": (btc, eth, 0.0012, 0.0012),
         "SPX/Dow": (spx, dow, 0.0001, 0.00012), "NQ/Russell": (nq, rut, 0.00012, 0.0002)}
for nm, (A, B, ca, cb) in PAIRS.items():
    for n in (120, 480):
        for zin in (2.0, 2.5):
            CAND[f"pair {nm} {n}h z{zin}"] = pair(A, B, ca, cb, n, zin, n)
yrs = (idx[-1] - idx[0]).days / 365.25; cut = idx.searchsorted(split); f = cut / len(idx)
d = pd.DataFrame({k: v[0] for k, v in CAND.items()} | {k: R0[names.index(k)] for k in names}, index=idx).resample("1D").sum(); d = d[d.abs().sum(axis=1) > 0]
rows = []
for k, (r, lo) in CAND.items():
    eq = np.cumsum(r); rows.append(dict(cand=k, yr=100 * r.sum() / yrs, yr_2020_22=100 * r[:cut].sum() / (f * yrs), yr_2023_26=100 * r[cut:].sum() / ((1 - f) * yrs),
                                        maxdd=100 * np.max(np.maximum.accumulate(eq) - eq), max_corr=d.corr().loc[k, names].abs().max()))
st = pd.DataFrame(rows); pd.set_option("display.width", 250); print("STANDALONE at 1% risk:"); print(st.round(2).to_string(index=False), flush=True)
good = st[(st.yr_2020_22 > 0) & (st.yr_2023_26 > 0)].cand.tolist()
def run3(w, Rm, LOm, h0, h1, target, halt=0.8, maxl=0.10, daily=0.05):
    r = (Rm[:, h0:h1] * w[:, None]).sum(0); lo = (LOm[:, h0:h1] * w[:, None]).sum(0); eq = 1.0; day = None; hd = None
    for i in range(len(r)):
        dd_ = days[h0 + i]
        if dd_ != day: day = dd_; dopen = eq
        if hd == dd_: continue
        if eq * (1 + lo[i]) <= 1 - maxl or eq * (1 + lo[i]) <= dopen * (1 - daily): return "fail", i, eq - 1
        eq *= 1 + r[i]
        if target and eq >= 1 + target: return "pass", i, eq - 1
        if 1 - eq / dopen >= halt * daily: hd = dd_
        if eq <= 1 - 0.8 * maxl: return "stopped", i, eq - 1
    return "open", len(r), eq - 1
wst = pd.date_range("2020-04-01", "2025-10-01", freq="MS", tz="UTC")
def job(v):
    k, wt = v
    if k is None: Rm, LOm, w = R0, LO0, W
    else: Rm = np.vstack([R0, CAND[k][0]]); LOm = np.vstack([LO0, CAND[k][1]]); w = np.append(W, wt)
    res = []
    for s_ in est:
        h0 = idx.searchsorted(s_); a, i1, _ = run3(w, Rm, LOm, h0, len(idx), 0.10)
        if a != "pass": res.append((s_, a, None)); continue
        b, i2, _ = run3(w, Rm, LOm, h0 + i1 + 1, len(idx), 0.05); res.append((s_, b, (i1 + i2) / 24 if b == "pass" else None))
    yrs_ = [(s_, *run3(w, Rm, LOm, idx.searchsorted(s_), idx.searchsorted(s_ + pd.DateOffset(years=1)), None)) for s_ in wst]
    out = dict(add=k or "8 EAs (current)", weight=wt)
    for p, sel in (("A", lambda s: s < split), ("B", lambda s: s >= split)):
        rr = [x for x in res if sel(x[0])]; t = [x[2] for x in rr if x[2] is not None]; yy = [y for y in yrs_ if sel(y[0])]
        out |= {f"{p}_pass": 100 * np.mean([x[1] == "pass" for x in rr]), f"{p}_breach": 100 * np.mean([x[1] == "fail" for x in rr]), f"{p}_days": np.median(t),
                f"{p}_fund": 100 * np.median([y[3] for y in yy]), f"{p}_fbr": sum(y[1] == "fail" for y in yy)}
    return out
jobs = [(None, 0)] + [(k, wt) for k in good for wt in (0.25, 0.5)]
print(f"\nportfolio tests for {good}", flush=True)
with Pool(3) as p: out = p.map(job, jobs)
print(pd.DataFrame(out).round(1).to_string(index=False))
