src = open("fpzero.py").read(); exec(src[:src.index("\nif __name__")])
def go(a):
    h0, scale, fg = a
    build({c: min(PORT["21"][c] * scale, 1.0 / BASE[c]) for c in NAMES})      # weekend/news holding allowed here
    eq = 1.0; opn = 0.0; day = -1; hd = -1; peakbal = 1.0; floor = 0.95; days = []; dstart = 1.0; ref = 1.0; mm = 1.0; soft = 0
    for i in range(h0, min(h0 + 365 * 24, len(EQ_R))):
        if DAYN[i] != day:
            if day != -1: days.append((eq - opn) - dstart)
            bal = eq - opn; prof = bal - 1.0
            if prof >= 0.05 and sum(x > 0 for x in days) >= 5 and max(days) <= 0.15 * prof:
                return "paid", (i - h0) / 24, soft
            day = DAYN[i]; dstart = bal; ref = max(bal, eq); peakbal = max(peakbal, bal); floor = 1.0 if peakbal >= 1.05 else max(floor, peakbal - 0.05)
            mm = max(0.0, min(1.0, (bal - floor) / 0.04))
            if prof >= 0.05: mm = min(mm, 0.25)       # at the cap: trade small, just to dilute the best day
        if hd == day or (EQ_R[i] == 0 and EQ_L[i] == 0):
            if hd == day: opn = 0.0
            continue
        low = eq * (1 + mm * EQ_L[i]); after = eq * (1 + mm * EQ_R[i])
        if low <= ref - 0.02: eq = min(after, max(low, ref - 0.023)); opn = 0.0; hd = day; continue
        if low <= floor or low <= ref - 0.03: return "breached", (i - h0) / 24, soft
        opn_new = opn + eq * mm * D_FLT[i]; fl = min(opn_new + (low - after), opn_new)
        if fl <= -0.01: soft += 1; eq = (eq - opn) - 0.01; opn = 0.0; hd = day
        elif fl <= -fg: eq = (eq - opn) - fg - 0.002; opn = 0.0; hd = day
        else: opn = opn_new; eq = after
        if soft >= 2: return "breached (shield x2)", (i - h0) / 24, soft
        if eq <= floor: return "breached", (i - h0) / 24, soft
    return "not yet after 1 yr", 365, soft
if __name__ == "__main__":
    st = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-10-30", freq="7D", tz="UTC")]
    for sc in (0.5, 1.0, 1.5):
        with Pool(os.cpu_count()) as p: d = pd.DataFrame(p.map(go, [(h, sc, 0.008) for h in st]), columns=["o", "days", "soft"])
        pd_ = d[d.o == "paid"]
        print(sc, (d.o.value_counts(normalize=True) * 100).round(1).to_dict(), "| median days to payout", pd_.days.median(), "| 90%", pd_.days.quantile(.9), "| shield hit once", round(100 * (d.soft == 1).mean(), 1))
