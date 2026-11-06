# Run from the scratchpad.
import sys, numpy as np, pandas as pd
exec(open('recent_check.py').read().split('RULE = ("room", 1.0, 1.0, 0.03, 0.905, -1)\ngap')[0])
RULE = ("room", 1.0, 1.0, 0.03, 0.905, -1); gap = V[(0.02, "48h")]
RB["cur"] = (TEN[0] - 0.25 * gap[0], TEN[1] - 0.25 * gap[1])
r_, lo_ = RB["cur"]
def attempt(h0, target):
    """Same rules as run4 (daily -4% halt, room cap, -9.5% stop, 10% / 5% firm limits), also returns the lowest equity."""
    eq = 1.0; day = -1; hd = -1; low = 1.0; m = 1.0
    for i in range(h0, len(r_)):
        dd_ = DAYN[i]
        if dd_ != day: day = dd_; dopen = eq; m = mult(RULE, 1, eq)
        if hd == dd_ or (r_[i] == 0 and lo_[i] == 0): continue
        x = eq * (1 + m * lo_[i]); low = min(low, x)
        if x <= 0.90 or x <= dopen * 0.95: return "BREACH", i, low
        eq *= 1 + m * r_[i]
        if eq >= 1 + target: return "pass", i, low
        if 1 - eq / dopen >= 0.04: hd = dd_
        if eq <= 0.905: return "stopped -9.5%", i, low
    return "still running", len(r_) - 1, low
rows = []
for s in pd.date_range("2026-05-15", "2026-08-31", freq="1D", tz="UTC"):
    if s.weekday() >= 5: continue
    h0 = idx.searchsorted(s); a, i1, l1 = attempt(h0, 0.10)
    res = dict(start=s.date(), phase1=a, p1_days=round((idx[i1] - s).days), p1_lowest=round(100 * (l1 - 1), 1))
    if a == "pass":
        b, i2, l2 = attempt(i1 + 1, 0.05); res |= dict(phase2=b, funded_on=idx[i2].date() if b == "pass" else None, total_days=(idx[i2] - s).days, p2_lowest=round(100 * (l2 - 1), 1))
    rows.append(res)
df = pd.DataFrame(rows); pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
print(df.to_string(index=False))
print("\nphase 1 outcomes:", df.phase1.value_counts().to_dict()); print("phase 2 outcomes:", df.phase2.value_counts().to_dict() if "phase2" in df else {})
print("lowest point of any attempt in phase 1: %.1f%%" % df.p1_lowest.min())
