# 21-EA pack on other challenge rules. Guard = firm daily limit - 1% (EA daily stop). Trailing max loss follows the highest closed balance.
import sys
exec(open("firms.py").read().split('\nif __name__ == "__main__":')[0])
def phase(R, L, F, h0, target, DL, ML, trailing, end):
    eq = 1.0; opn = 0.0; day = -1; hd = -1; dp = []; dstart = 1.0; ref = 1.0; hi = 1.0; G = DL - 0.01
    for i in range(h0, end):
        if DAYN[i] != day:
            bal = eq - opn
            if day != -1: dp.append(bal - dstart)
            hi = max(hi, bal) if trailing else 1.0
            if bal >= 1 + target and sum(x > 0.005 for x in dp) >= 3: return "pass", i
            day = DAYN[i]; dstart = bal; ref = max(bal, eq); floor = hi - ML; mm = max(0.0, min(1.0, (eq - floor) / (0.8 * ML)))
        if hd == day or (R[i] == 0 and L[i] == 0):
            if hd == day: opn = 0.0
            continue
        low = eq * (1 + mm * L[i]); after = eq * (1 + mm * R[i])
        if low <= ref - G: eq = min(after, max(low, ref - G - 0.003)); opn = 0.0; hd = day
        elif low <= floor or low <= ref - DL: return "fail", i
        else: opn += eq * mm * F[i]; eq = after
    return "open", end
def attempt(arr, h0, phases):
    R, L, F = arr; t = h0; tries = 0
    while t < len(R) - 48 and tries < 12:
        tries += 1; ok = True; s = t
        for (tg, DL, ML, tr) in phases:
            a, i = phase(R, L, F, s, tg, DL, ML, tr, len(R))
            if a != "pass": ok = False; break
            s = i + 24
        if ok: return tries, (i - h0) / 24
        if a == "open": return tries, np.nan
        t = i + 24
    return tries, np.nan
RULES = {"The5ers High Stakes (8%+5%, 5% daily, 10% static)": [(0.08, 0.05, 0.10, False), (0.05, 0.05, 0.10, False)],
         "Account A (8%+5%, 4% daily, 9% static)": [(0.08, 0.04, 0.09, False), (0.05, 0.04, 0.09, False)],
         "Account B (10% one phase, 4% daily, 7% trailing)": [(0.10, 0.04, 0.07, True)]}
if __name__ == "__main__":
    ALL = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    for X_ in (3.0, 4.0, 5.0):
        build({c: min(PORT["21"][c] * X_, 1.0 / BASE[c]) for c in NAMES}); arr = (EQ_R.copy(), EQ_L.copy(), D_FLT.copy())
        for nm, ph in RULES.items():
            res = [attempt(arr, h, ph) for h in ALL]; tr = np.array([r[0] for r in res]); dd = np.array([r[1] for r in res])
            print(f"{X_:.0f}x | {nm}: first try {100*np.mean(tr==1):.0f}% | avg attempts {tr.mean():.2f} | median days {np.nanmedian(dd):.0f} | within 30d {100*np.mean(dd<=30):.0f}% | within 20d {100*np.mean(dd<=20):.0f}%", flush=True)
