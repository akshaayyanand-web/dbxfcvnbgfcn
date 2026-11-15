# Funded 200K with all 16 EAs (guards on, FTMO exact rule): withdraw everything above the start every 14 days; survival and payouts over one year.
import os, numpy as np, pandas as pd
exec(open("all_optional_pass_mode_test.py").read().split("combos = [")[0])
EQ_R, EQ_L, FLT = BASE_R.copy(), BASE_L.copy(), BASE_FLT.copy()
EQ_R = EQ_R + 0.003 * R_sol; EQ_L = EQ_L + 0.003 * L_sol; FLT = FLT + 0.003 * (np.cumsum(R_sol) - np.cumsum(rl_sol))
for k in ("gold", "spx_fade", "nikkei"): r, l = ADD[k]; EQ_R = EQ_R + W[k] / 100 * r; EQ_L = EQ_L + W[k] / 100 * l
def funded(h0, m, days=365, every=14, Z=0.07, G=0.04):
    sl, half = 0.905, (0.04, 0.02); eq = 1.0; day = -1; hd = -1; halfmode = False; paid = 0.0; npay = 0
    end = min(h0 + days * 24, len(EQ_R)); nextpay = h0 + every * 24; flt0 = FLT[h0]
    for i in range(h0, end):
        if i >= nextpay:
            nextpay += every * 24
            if eq > 1.0: paid += eq - 1.0; eq = 1.0; npay += 1
        if DAYN[i] != day:
            day = DAYN[i]; bal = eq - m * (FLT[i] - flt0); ref = bal; g = eq
            if g <= 1 - half[0]: halfmode = True
            elif g >= 1 - half[1]: halfmode = False
            mm = m * max(0.0, min(1.0, (g - 0.90) / Z)) * (0.5 if halfmode else 1.0)
        if hd == day or (EQ_R[i] == 0 and EQ_L[i] == 0): continue
        x = eq * (1 + mm * EQ_L[i])
        if x <= ref - G and not hd == day:
            eq = ref - G - 0.003; hd = day
            if eq <= 0.90: return "lost (breach)", paid, (i - h0) / 24, npay
            if eq <= sl: return "lost (EA stop at -9.5%)", paid, (i - h0) / 24, npay
            continue
        if x <= 0.90 or x <= ref - 0.05: return "lost (breach)", paid, (i - h0) / 24, npay
        eq *= 1 + mm * EQ_R[i]
        if ref - eq >= G: hd = day
        if eq <= sl: return "lost (EA stop at -9.5%)", paid, (i - h0) / 24, npay
    return "survived the year", paid + max(0.0, eq - 1.0), (end - h0) / 24, npay
def ev(m):
    res = []
    for s in pd.date_range("2020-09-01", "2025-10-15", freq="7D", tz="UTC"):
        res.append(funded(idx.searchsorted(s), m))
    d = pd.DataFrame(res, columns=["out", "paid", "days", "npay"])
    lost = d.out.str.startswith("lost")
    return dict(risk=f"x{m}", starts=len(d), survived_1yr_pct=round(100 * (~lost).mean(), 1), lost_pct=round(100 * lost.mean(), 1),
                median_days_when_lost=round(d[lost].days.median()) if lost.any() else None,
                avg_withdrawn_usd=round(200000 * d.paid.mean()), median_withdrawn_usd=round(200000 * d.paid.median()),
                withdrawn_if_survived=round(200000 * d[~lost].paid.median()), withdrawn_if_lost=round(200000 * d[lost].paid.median()) if lost.any() else None)
with Pool(os.cpu_count()) as p: rows = p.map(ev, (1.0, 0.75, 0.5))
pd.set_option("display.width", 300); print(pd.DataFrame(rows).to_string(index=False))
