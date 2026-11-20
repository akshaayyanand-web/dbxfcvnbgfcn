# EURUSD structure scalps (1m, 2019-2026). Pre-registered: R1 round-number fade, R2 round-number break, N1 NFP 5-minute follow.
import numpy as np, pandas as pd
d = pd.read_csv("fx1m/EURUSD_1m.csv", index_col=0); d.index = pd.to_datetime(d.index, utc=True); d = d[~d.index.duplicated()].sort_index()
d.columns = ["o", "h", "l", "c", "v"][: d.shape[1]]
O, H, L, C = (d[k].to_numpy(float) / 100 for k in "ohlc"); T = d.index; PIP = 0.0001
LDN = T.tz_convert("Europe/London"); MIN = LDN.hour * 60 + LDN.minute; DAY = np.array(LDN.date)
NY = T.tz_convert("America/New_York")
def run_level(mode, cost_pips):
    out = []; step = 50 * PIP
    starts = np.r_[0, np.flatnonzero(DAY[1:] != DAY[:-1]) + 1, len(DAY)]
    for a, b in zip(starts[:-1], starts[1:]):
        if pd.Timestamp(DAY[a]).weekday() >= 5: continue
        ix = np.arange(a, b); ix = ix[(MIN[a:b] >= 420) & (MIN[a:b] < 1200)]
        if len(ix) < 100: continue
        used = set(); armed = {}
        k = 0
        while k < len(ix) - 1:
            i = ix[k]; mid = C[i]; lv_lo = np.floor(mid / step) * step; lv_hi = lv_lo + step
            for lv in (lv_lo, lv_hi):
                if abs(mid - lv) >= 10 * PIP: armed[round(lv, 5)] = np.sign(lv - mid)       # +1: level above price
            hit = None
            for lv, side in list(armed.items()):
                if lv in used: continue
                if mode == "fade" and ((side > 0 and H[i] >= lv) or (side < 0 and L[i] <= lv)): hit = (lv, side); break
                if mode == "break" and ((side > 0 and C[i] >= lv + 2 * PIP) or (side < 0 and C[i] <= lv - 2 * PIP)): hit = (lv, side); break
            if hit is None: k += 1; continue
            lv, side = hit; used.add(lv); armed.pop(lv, None)
            if mode == "fade":
                dr = -int(side); e = lv; tp, sl = e + dr * 6 * PIP, e - dr * 6 * PIP; j0 = k          # limit fill at the level; same bar checked for the stop (worst case)
            else:
                dr = int(side); j0 = k + 1
                if j0 >= len(ix): break
                e = O[ix[j0]]; tp, sl = e + dr * 8 * PIP, e - dr * 5 * PIP
            x = None; q = j0
            for q in range(j0, min(j0 + 60, len(ix))):
                bi = ix[q]
                if (dr > 0 and L[bi] <= sl) or (dr < 0 and H[bi] >= sl): x = sl; break
                if q > j0 or mode == "break":
                    if (dr > 0 and H[bi] >= tp) or (dr < 0 and L[bi] <= tp): x = tp; break
            if x is None: x = C[ix[q]]
            risk = abs(e - sl); out.append((T[ix[j0]], T[ix[q]], (dr * (x - e) - cost_pips * PIP) / risk)); k = q + 1
    return out
def run_nfp(cost_pips):
    out = []
    for y in range(2019, 2027):
        for mth in range(1, 13):
            fri = pd.Timestamp(y, mth, 1) + pd.offsets.Week(weekday=4)
            if fri.month != mth: fri = pd.Timestamp(y, mth, 1)
            t0 = pd.Timestamp(f"{fri.date()} 08:30", tz="America/New_York").tz_convert("UTC")
            i0 = T.searchsorted(t0)
            if i0 + 70 >= len(T) or T[i0] - t0 > pd.Timedelta("2min"): continue
            hi, lo = H[i0:i0 + 5].max(), L[i0:i0 + 5].min(); mv = C[i0 + 4] - O[i0]
            if mv == 0: continue
            dr = int(np.sign(mv)); e = O[i0 + 6]; sl = lo if dr > 0 else hi
            if (e - sl) * dr <= 0: continue
            x = None
            for q in range(i0 + 6, i0 + 66):
                if (dr > 0 and L[q] <= sl) or (dr < 0 and H[q] >= sl): x = sl; break
            x = C[i0 + 65] if x is None else x
            out.append((T[i0 + 6], T[q], (dr * (x - e) - cost_pips * PIP) / abs(e - sl)))
    return out
def stats(trs, split=pd.Timestamp("2023-01-01", tz="UTC")):
    if len(trs) < 20: return dict(n=len(trs))
    r = np.array([x[2] for x in trs]); t = pd.DatetimeIndex([x[0] for x in trs]); a, b = r[t < split], r[t >= split]
    f = lambda v: round(v.mean() / v.std(ddof=1) * np.sqrt(len(v)), 2) if len(v) > 2 else np.nan
    yrs = (t[-1] - t[0]).days / 365.25
    return dict(n=len(r), per_yr=round(len(r) / yrs), meanR=round(r.mean(), 3), win=round(100 * (r > 0).mean()), t_2019_22=f(a), t_2023_26=f(b), R_per_yr=round(r.sum() / yrs, 1))
if __name__ == "__main__":
    rows = []
    for cost in (0.8, 0.5):
        rows.append(dict(test="R1 round-number fade (00/50 levels)", cost_pips=cost, **stats(run_level("fade", cost))))
        rows.append(dict(test="R2 round-number break (follow)", cost_pips=cost, **stats(run_level("break", cost))))
        rows.append(dict(test="N1 NFP 5-min follow to 9:30 ET", cost_pips=cost, **stats(run_nfp(cost))))
        for r in rows[-3:]: print(r, flush=True)
    pd.set_option("display.width", 250); R = pd.DataFrame(rows); print(R.to_string()); R.to_csv("eurlab_results.csv", index=False)
