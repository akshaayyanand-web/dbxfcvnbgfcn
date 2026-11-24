# Monte Carlo of the 21-EA book on The5ers High Stakes: shuffle 5-day blocks of the real hourly book (all EAs together), 300 synthetic
# 3-year paths, run the evaluation (8% + 5%, 5% daily, 10% static) and a funded year (2-week payouts, 80% split) at the pack's 3x risk.
import numpy as np
exec(open("firms.py").read().split('\nif __name__ == "__main__":')[0])
rng = np.random.default_rng(7)
build({c: min(PORT["21"][c] * 3.0, 1.0 / BASE[c]) for c in NAMES})
R0, L0, F0 = EQ_R.copy(), EQ_L.copy(), D_FLT.copy()
start = idx.searchsorted(pd.Timestamp("2020-09-01", tz="UTC")); nday = (len(R0) - start) // 24
blocks = [(start + 24 * d, start + 24 * (d + 5)) for d in range(0, nday - 5)]
def make_path(seed, days=3 * 365):
    r = np.random.default_rng(seed); parts = []
    while sum(b - a for a, b in parts) < days * 24: parts.append(blocks[r.integers(len(blocks))])
    sel = np.concatenate([np.arange(a, b) for a, b in parts])[: days * 24]
    return R0[sel], L0[sel], F0[sel]
def sim(seed):
    global EQ_R, EQ_L, D_FLT, DAYN
    R, L, F = make_path(seed); EQ_R, EQ_L, D_FLT = R, L, F; DAYN = np.arange(len(R)) // 24
    import builtins
    # evaluation with the firm's rules (uses acct with the synthetic arrays; build() is bypassed)
    F_ = FIRMS["The5ers High Stakes 2-Step"]; i = 0; days = 0
    for k, (tg, DL, ML, G) in enumerate(F_["phases"]):
        p, d, i2, _ = acct_raw(i, tg, DL, ML, G)
        if p != "pass": return (p, None, None, 0.0)
        days += d; i = i2 + 1
    o, pays = funded_raw(i + 48)
    return ("pass", days, o, 0.8 * sum(pays))
def acct_raw(h0, target, DL, ML, G):
    eq = 1.0; opn = 0.0; day = -1; hd = -1; floor = 1 - ML; Z = ML * 0.8; dp = []; dstart = 1.0; ref = 1.0
    for i in range(h0, len(EQ_R)):
        if DAYN[i] != day:
            bal = eq - opn
            if day != -1: dp.append(bal - dstart)
            if bal >= 1 + target and sum(x > 0.005 for x in dp) >= 3: return "pass", (i - h0) / 24, i, None
            day = DAYN[i]; dstart = bal; ref = max(bal, eq); mm = max(0.0, min(1.0, (eq - floor) / Z))
        if hd == day or (EQ_R[i] == 0 and EQ_L[i] == 0):
            if hd == day: opn = 0.0
            continue
        low = eq * (1 + mm * EQ_L[i]); after = eq * (1 + mm * EQ_R[i])
        if low <= ref - G: eq = min(after, max(low, ref - G - 0.003)); opn = 0.0; hd = day
        elif low <= floor or low <= ref - DL: return "breached", (i - h0) / 24, i, None
        else: opn += eq * mm * D_FLT[i]; eq = after
    return "open", None, len(EQ_R), None
def funded_raw(h0, days=365):
    eq = 1.0; opn = 0.0; day = -1; hd = -1; floor = 0.90; Z = 0.08; ref = 1.0; pays = []; nextpay = h0 + 14 * 24
    for i in range(h0, min(h0 + days * 24, len(EQ_R))):
        if DAYN[i] != day:
            bal = eq - opn
            if i >= nextpay:
                w = min(bal, eq) - 1.02
                if w > 0.005: pays.append(w); eq -= w; bal = eq - opn; nextpay = i + 14 * 24
                else: nextpay = i + 24
            day = DAYN[i]; ref = max(bal, eq); mm = max(0.0, min(1.0, (eq - floor) / Z))
        if hd == day or (EQ_R[i] == 0 and EQ_L[i] == 0):
            if hd == day: opn = 0.0
            continue
        low = eq * (1 + mm * EQ_L[i]); after = eq * (1 + mm * EQ_R[i])
        if low <= ref - 0.04: eq = min(after, max(low, ref - 0.043)); opn = 0.0; hd = day
        elif low <= floor or low <= ref - 0.05: return "breached", pays
        else: opn += eq * mm * D_FLT[i]; eq = after
    return "kept", pays
if __name__ == "__main__":
    with Pool(os.cpu_count()) as p: res = p.map(sim, range(300))
    D = pd.DataFrame(res, columns=["ev", "days", "funded", "paid"]); ok = D[D.ev == "pass"]
    print(f"Monte Carlo, 300 shuffled 3-year histories, The5ers High Stakes at 3x:")
    print(f"  evaluation: passed {100*len(ok)/len(D):.0f}% | breached {100*(D.ev=='breached').mean():.0f}% | still open after 3 years {100*(D.ev=='open').mean():.0f}%")
    print(f"  days to pass: median {ok.days.median():.0f}, 25% {ok.days.quantile(.25):.0f}, 75% {ok.days.quantile(.75):.0f}, 90% {ok.days.quantile(.9):.0f}")
    print(f"  funded year: kept {100*(ok.funded=='kept').mean():.0f}% | paid to you (% of account): median {100*ok.paid.median():.0f}%, 10% {100*ok.paid.quantile(.1):.0f}%, 25% {100*ok.paid.quantile(.25):.0f}%, 75% {100*ok.paid.quantile(.75):.0f}%, 90% {100*ok.paid.quantile(.9):.0f}%")
    print(f"  on a $10K account: median ${10000*ok.paid.median():,.0f}/yr, bad case (10%) ${10000*ok.paid.quantile(.1):,.0f}, good case (90%) ${10000*ok.paid.quantile(.9):,.0f}")
