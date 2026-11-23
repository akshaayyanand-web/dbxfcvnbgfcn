# The5ers High Stakes scaling on 2026: funded $10K from 2 Jan; at balance >= +10% of the level (3+ profitable days) the profit is paid (80%)
# and the account moves to the next level (new floor/daily limit from the new size). Same 3x risk as % of the account.
exec(open("y2026_5ers.py").read().split('\nif __name__ == "__main__":')[0])
LEVELS = [10000, 12500, 15000, 20000, 25000, 30000, 40000, 50000, 60000, 70000, 80000, 100000, 125000, 150000, 175000, 200000, 250000, 300000, 350000, 400000, 450000, 500000]
SPLIT = {175000: .85, 200000: .85, 250000: .9, 300000: .9, 350000: 1.0, 400000: 1.0, 450000: 1.0, 500000: 1.0}
def scale_run(h0, h_end):
    build({c: min(PORT["21"][c] * X, 1.0 / BASE[c]) for c in NAMES})
    lv = 0; eq = 1.0; opn = 0.0; day = -1; hd = -1; floor = 0.90; ref = 1.0; Z = 0.08; dstart = 1.0; pdays = 0; log = []; paid = 0.0
    for i in range(h0, h_end):
        if DAYN[i] != day:
            bal = eq - opn
            if day != -1 and bal - dstart > 0.005 * 1.0: pdays += 1
            if bal >= 1.10 and pdays >= 3 and lv + 1 < len(LEVELS):
                size = LEVELS[lv]; prof = (bal - 1.0) * size; you = prof * SPLIT.get(size, .8); paid += you
                log.append(dict(date=str(idx[i].date()), level=f"${size:,}", profit=round(prof), to_you=round(you), next_level=f"${LEVELS[lv+1]:,}"))
                lv += 1; eq = 1.0; opn = 0.0; bal = 1.0; pdays = 0
            day = DAYN[i]; dstart = bal; ref = max(bal, eq); mm = max(0.0, min(1.0, (eq - floor) / Z))
        if hd == day or (EQ_R[i] == 0 and EQ_L[i] == 0):
            if hd == day: opn = 0.0
            continue
        low = eq * (1 + mm * EQ_L[i]); after = eq * (1 + mm * EQ_R[i])
        if low <= ref - 0.04: eq = min(after, max(low, ref - 0.043)); opn = 0.0; hd = day
        elif low <= floor or low <= ref - 0.05: return "BREACHED", log, paid, lv, eq
        else: opn += eq * mm * D_FLT[i]; eq = after
    return "kept", log, paid, lv, eq
if __name__ == "__main__":
    for lab, start in (("A) funded from 2 Jan 2026", "2026-01-02"), ("B) challenge from 2 Jan, funded 20 Mar 2026", "2026-03-22")):
        st, log, paid, lv, eq = scale_run(idx.searchsorted(pd.Timestamp(start, tz="UTC")), len(idx) - 1)
        size = LEVELS[lv]
        print(f"\n{lab}: {st}; reached the ${size:,} level; paid to you ${paid:,.0f}; open profit on 30 Oct ${(eq-1)*size:,.0f} (to you at 80%: ${0.8*(eq-1)*size:,.0f})")
        print(pd.DataFrame(log).to_string(index=False))
