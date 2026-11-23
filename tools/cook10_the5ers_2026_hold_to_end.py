exec(open("y2026_5ers.py").read().split('\nif __name__ == "__main__":')[0])
def hold_log(h0, h_end):
    build({c: min(PORT["21"][c] * X, 1.0 / BASE[c]) for c in NAMES})
    eq = 1.0; opn = 0.0; day = -1; hd = -1; floor = 0.90; ref = 1.0; Z = 0.08; month = {}; low_pt = 1.0
    for i in range(h0, h_end):
        if DAYN[i] != day:
            bal = eq - opn; day = DAYN[i]; ref = max(bal, eq); mm = max(0.0, min(1.0, (eq - floor) / Z))
            month.setdefault(idx[i].strftime("%Y-%m"), eq)
        if hd == day or (EQ_R[i] == 0 and EQ_L[i] == 0):
            if hd == day: opn = 0.0
            continue
        low = eq * (1 + mm * EQ_L[i]); after = eq * (1 + mm * EQ_R[i])
        if low <= ref - 0.04 * 1.0: eq = min(after, max(low, ref - 0.043)); opn = 0.0; hd = day
        elif low <= floor or low <= ref - 0.05: return "BREACHED", month, eq, low_pt
        else: opn += eq * mm * D_FLT[i]; eq = after
        low_pt = min(low_pt, eq)
    month["end"] = eq; return "kept", month, eq, low_pt
if __name__ == "__main__":
    hE = len(idx) - 1
    for lab, start in (("A) funded from 2 Jan 2026", pd.Timestamp("2026-01-02", tz="UTC")), ("B) challenge from 2 Jan, funded 20 Mar 2026", pd.Timestamp("2026-03-22", tz="UTC"))):
        h0 = idx.searchsorted(start); st, month, eq, lowp = hold_log(h0, hE); ks = list(month)
        rows = [dict(month=a, made_pct=round(100 * (month[b] / month[a] - 1), 1), balance_end=round(SIZE * month[b])) for a, b in zip(ks[:-1], ks[1:])]
        gross = SIZE * (eq - 1)
        print(f"\n{lab}: {st}; balance 30 Oct ${SIZE*eq:,.0f}; profit ${gross:,.0f}; to you at 80% ${0.8*gross:,.0f}; lowest balance on the way ${SIZE*lowp:,.0f}")
        print(pd.DataFrame(rows).to_string(index=False))
