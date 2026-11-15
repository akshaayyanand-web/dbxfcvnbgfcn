import os, numpy as np, pandas as pd
exec(open("funded_payout.py").read().split("def funded(")[0])
D_FLT = np.diff(np.concatenate([[0.0], FLT]))           # hourly change of the open (floating) P&L, 1x
def core(h0, m, Z, target=None, days=None, every=None, G=0.04, slip=0.003, sl=0.905, half=(0.04, 0.02), cap=1.0):
    """One account under FTMO's rule. target: eval phase (stop at +target). days/every: funded with payouts every `every` days."""
    eq = 1.0; opn = 0.0; day = -1; hd = -1; halfmode = False; pays = []; mm = 0.0
    end = len(EQ_R) if days is None else min(h0 + days * 24, len(EQ_R)); nextpay = h0 + (every or 10**6) * 24
    for i in range(h0, end):
        if every and i >= nextpay:
            nextpay += every * 24
            bal_now = eq - opn
            if bal_now > 1.0 and eq > 1.0:                  # withdraw closed profit above the start (equity must also be above it)
                w = min(bal_now, eq) - 1.0; pays.append((idx[i], w)); eq -= w
        if DAYN[i] != day:
            day = DAYN[i]; ref = eq - opn                   # midnight balance = equity minus open P&L (FTMO's daily base)
            g = eq
            if g <= 1 - half[0]: halfmode = True
            elif g >= 1 - half[1]: halfmode = False
            mm = m * max(0.0, min(cap, (g - 0.90) / Z)) * (0.5 if halfmode else 1.0)
        if hd == day or (EQ_R[i] == 0 and EQ_L[i] == 0):
            if hd == day: opn = 0.0                         # flat after the guard
            continue
        low = eq * (1 + mm * EQ_L[i]); after = eq * (1 + mm * EQ_R[i])
        if low <= ref - G:                                   # guard closes everything at the line (never better than the hour's end)
            eq = min(after, max(low, ref - G - slip)); opn = 0.0; hd = day
            if eq <= 0.90: return "breach", i, pays
            if eq <= sl: return "stopped", i, pays
            continue
        if low <= 0.90 or low <= ref - 0.05: return "breach", i, pays
        opn += eq * mm * D_FLT[i]; eq = after
        if target is not None and eq >= 1 + target: return "pass", i, pays
        if eq <= sl: return "stopped", i, pays
    return ("open" if target is not None else "kept"), end - 1, pays
