# Run from the scratchpad (needs recent_check.py chain). Funded-year check: safer_fund.py (below).
import sys, numpy as np, pandas as pd
exec(open('recent_check.py').read().split('RULE = ("room", 1.0, 1.0, 0.03, 0.905, -1)\ngap')[0])
gap = V[(0.02, "48h")]; r_, lo_ = (TEN[0] - 0.25 * gap[0], TEN[1] - 0.25 * gap[1])
def attempt(h0, target, Z, sl, half):
    eq = 1.0; day = -1; hd = -1; low = 1.0; m = 1.0; halfmode = False
    for i in range(h0, len(r_)):
        dd_ = DAYN[i]
        if dd_ != day:
            day = dd_; dopen = eq
            if half:
                if eq <= 1 - half[0]: halfmode = True
                elif eq >= 1 - half[1]: halfmode = False
            m = max(0.0, min(1.0, (eq - 0.90) / Z)) * (0.5 if halfmode else 1.0)
        if hd == dd_ or (r_[i] == 0 and lo_[i] == 0): continue
        x = eq * (1 + m * lo_[i]); low = min(low, x)
        if x <= 0.90 or x <= dopen * 0.95: return "breach", i, low
        eq *= 1 + m * r_[i]
        if eq >= 1 + target: return "pass", i, low
        if 1 - eq / dopen >= 0.04: hd = dd_
        if eq <= sl: return "stopped", i, low
    return "open", len(r_) - 1, low
def ev(cfg):
    Z, sl, half = cfg; out = {"size shrinks below": f"-{round(100 * (0.10 - Z))}%", "hard stop": f"-{round(100 * (1 - sl), 1)}%",
                             "half-size mode": f"below -{int(half[0]*100)}% until back above -{int(half[1]*100)}%" if half else "off"}
    for lab, a, z in (("2020-22", "2020-04-01", "2022-12-31"), ("2023-25", "2023-01-01", "2025-09-01"), ("2026", "2026-01-01", "2026-08-15")):
        res = []
        for s in pd.date_range(a, z, freq="1D", tz="UTC"):
            if s.weekday() >= 5: continue
            h0 = idx.searchsorted(s); p1, i1, l1 = attempt(h0, 0.10, Z, sl, half)
            if p1 != "pass": res.append((p1, None, l1)); continue
            p2, i2, l2 = attempt(i1 + 1, 0.05, Z, sl, half); res.append((p2, (i2 - h0) / 24 if p2 == "pass" else None, min(l1, l2)))
        n = len([x for x in res if x[0] != "open"]); t = [x[1] for x in res if x[1] is not None]
        out[f"{lab} pass%"] = 100 * sum(x[0] == "pass" for x in res) / n; out[f"{lab} breach%"] = 100 * sum(x[0] == "breach" for x in res) / n
        out[f"{lab} days"] = np.median(t) if t else np.nan; out[f"{lab} ever below -8%"] = 100 * np.mean([x[2] < 0.92 for x in res])
        out[f"{lab} ever below -6%"] = 100 * np.mean([x[2] < 0.94 for x in res])
    return out
CFG = [(0.03, 0.905, None), (0.05, 0.905, None), (0.07, 0.905, None), (0.08, 0.905, None), (0.05, 0.92, None), (0.07, 0.92, None),
       (0.03, 0.905, (0.04, 0.02)), (0.05, 0.905, (0.04, 0.02)), (0.03, 0.905, (0.03, 0.01)), (0.05, 0.92, (0.04, 0.02)),
       (0.05, 0.905, (0.05, 0.03)), (0.05, 0.905, (0.03, 0.01)), (0.07, 0.905, (0.04, 0.02))]
if __name__ == "__main__":
    with Pool(4) as p: rows = p.map(ev, CFG)
    df = pd.DataFrame(rows); pd.set_option("display.width", 400); pd.set_option("display.max_columns", 40)
    df.to_pickle("safer_dd.pkl"); print(df.round(1).to_string(index=False))

"""
import sys, numpy as np, pandas as pd
exec(open('safer_dd.py').read().split("def ev(cfg)")[0])
def fund(cfg):
    Z, sl, half = cfg; out = {"cfg": str(cfg)}
    for lab, a, z in (("2020-22", "2020-04-01", "2022-12-01"), ("2023-25", "2023-01-01", "2025-10-01")):
        ys = []
        for s in pd.date_range(a, z, freq="MS", tz="UTC"):
            h0 = idx.searchsorted(s); h1 = idx.searchsorted(s + pd.DateOffset(years=1))
            eq = 1.0; day = -1; hd = -1; halfmode = False; res = "ok"; low = 1
            for i in range(h0, h1):
                dd_ = DAYN[i]
                if dd_ != day:
                    day = dd_; dopen = eq
                    if half:
                        if eq <= 1 - half[0]: halfmode = True
                        elif eq >= 1 - half[1]: halfmode = False
                    m = max(0.0, min(1.0, (eq - 0.90) / Z)) * (0.5 if halfmode else 1.0)
                if hd == dd_ or (r_[i] == 0 and lo_[i] == 0): continue
                x = eq * (1 + m * lo_[i]); low = min(low, x)
                if x <= 0.90 or x <= dopen * 0.95: res = "breach"; break
                eq *= 1 + m * r_[i]
                if 1 - eq / dopen >= 0.04: hd = dd_
                if eq <= sl: res = "stopped"; break
            ys.append((res, eq - 1, low))
        out[f"{lab} funded median %"] = 100 * np.median([y[1] for y in ys]); out[f"{lab} funded worst %"] = 100 * min(y[1] for y in ys)
        out[f"{lab} breaches"] = sum(y[0] == "breach" for y in ys); out[f"{lab} stopped"] = sum(y[0] == "stopped" for y in ys)
        out[f"{lab} years below -8% at some point"] = sum(y[2] < 0.92 for y in ys)
    return out
with Pool(3) as p: rows = p.map(fund, [(0.03, 0.905, None), (0.07, 0.905, (0.04, 0.02)), (0.05, 0.905, (0.04, 0.02))])
pd.set_option("display.width", 300); print(pd.DataFrame(rows).round(1).to_string(index=False))
"""
