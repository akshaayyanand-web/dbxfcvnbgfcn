import os, numpy as np, pandas as pd
exec(open("frontier3.py").read().split("for k, w in PORT.items()")[0])
def acct(h0, ML=0.06, target=None, days=365, every=14, G=0.04, slip=0.003):
    """Static max loss ML from the initial balance (on balance = equity minus open P&L), no firm daily limit; own daily guard G.
    target: stop when the balance reaches +target (Instant's 50% stage). Otherwise run `days`, withdrawing closed profit above start every `every` days."""
    floor = 1 - ML; Z = 0.7 * ML; half = (0.3 * ML, 0.1 * ML)
    eq = 1.0; opn = 0.0; day = -1; hd = -1; halfmode = False; mm = 0.0; pays = []
    end = min(h0 + days * 24, len(EQ_R)); nextpay = h0 + every * 24
    for i in range(h0, end):
        if target is None and i >= nextpay:
            nextpay += every * 24; bal = eq - opn
            if bal > 1.0 and eq > 1.0: w = min(bal, eq) - 1.0; pays.append(w); eq -= w
        if DAYN[i] != day:
            day = DAYN[i]; ref = eq - opn; g = ref
            if target is not None and ref >= 1 + target: return "reached", i, pays
            room = g - floor
            if g <= 1 - half[0]: halfmode = True
            elif g >= 1 - half[1]: halfmode = False
            mm = max(0.0, min(1.0, room / Z)) * (0.5 if halfmode else 1.0)
        if hd == day or (EQ_R[i] == 0 and EQ_L[i] == 0):
            if hd == day: opn = 0.0
            continue
        low = eq * (1 + mm * EQ_L[i]); after = eq * (1 + mm * EQ_R[i])
        if low <= ref - G:
            eq = min(after, max(low, ref - G - slip)); opn = 0.0; hd = day
            if eq <= floor: return "lost", i, pays
            continue
        opn += eq * mm * D_FLT[i]; eq = after
        if eq - opn <= floor + 0.003: return "lost", i, pays          # balance at the line (EAs' own stop just above it)
    return ("kept" if target is None else "open"), end - 1, pays
def ev(scale):
    w = PORT["21"]; build({c: min(w[c] * scale, 1.0 / BASE[c]) for c in NAMES})
    starts = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    D, I = [], []
    for h0 in starts:
        o, i, pays = acct(h0); D.append((o, sum(pays)))
        o2, i2, _ = acct(h0, target=0.10, days=3000)                     # Instant: reach +10% on the half-size balance
        if o2 == "reached":
            o3, _, pays3 = acct(i2 + 24); I.append(("reached", (i2 - h0) / 24, o3, sum(pays3)))
        else: I.append((o2, None, None, 0.0))
    d = pd.DataFrame(D, columns=["o", "w"]); ins = pd.DataFrame(I, columns=["stage1", "days", "o", "w"]); r = ins[ins.stage1 == "reached"]
    return dict(scale=scale,
                direct_kept_1yr=round(100 * (d.o == "kept").mean(), 1), direct_withdrawn_80k_70pct_median=round(80000 * 0.7 * d.w.median()),
                direct_withdrawn_25pct=round(80000 * 0.7 * d.w.quantile(.25)),
                instant_reached_80k_pct=round(100 * (ins.stage1 == "reached").mean(), 1), instant_days_median=round(r.days.median()) if len(r) else None,
                instant_kept_after=round(100 * (r.o == "kept").mean(), 1) if len(r) else None, instant_withdrawn_80k_70pct_median=round(80000 * 0.7 * r.w.median()) if len(r) else None)
if __name__ == "__main__":
    with Pool(os.cpu_count()) as p: rows = p.map(ev, (0.75, 1.0, 1.5, 2.0))
    pd.set_option("display.width", 300); print(pd.DataFrame(rows).to_string(index=False))
