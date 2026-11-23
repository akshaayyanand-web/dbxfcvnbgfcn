# The5ers High Stakes $10K on 2026 data, pack settings (3x risk in both stages). Monthly % and 2-week payout log.
exec(open("firms.py").read().split('\nif __name__ == "__main__":')[0])
SIZE = 10000; X = 3.0
def funded_log(h0, h_end):
    build({c: min(PORT["21"][c] * X, 1.0 / BASE[c]) for c in NAMES})
    eq = 1.0; opn = 0.0; day = -1; hd = -1; floor = 0.90; dstart = 1.0; ref = 1.0; Z = 0.08; nextpay = h0 + 14 * 24
    log, pays = [], []; month_eq = {}; withdrawn = 0.0
    for i in range(h0, h_end):
        if DAYN[i] != day:
            bal = eq - opn
            if i >= nextpay:
                w = min(bal, eq) - 1 - 0.02
                ok = w > 0.005
                log.append(dict(date=str(idx[i].date()), balance=round(SIZE * bal), payout_to_you=round(SIZE * 0.8 * w) if ok else 0, paid=ok))
                if ok: pays.append((idx[i], w)); eq -= w; withdrawn += w; bal = eq - opn
                nextpay = i + 14 * 24
            day = DAYN[i]; dstart = bal; ref = max(bal, eq); mm = max(0.0, min(1.0, (eq - floor) / Z))
            month_eq.setdefault(idx[i].strftime("%Y-%m"), (eq, withdrawn))
        if hd == day or (EQ_R[i] == 0 and EQ_L[i] == 0):
            if hd == day: opn = 0.0
            continue
        low = eq * (1 + mm * EQ_L[i]); after = eq * (1 + mm * EQ_R[i])
        if low <= ref - 0.04: eq = min(after, max(low, ref - 0.043)); opn = 0.0; hd = day
        elif low <= floor or low <= ref - 0.05: return "BREACHED", log, month_eq, eq, withdrawn
        else: opn += eq * mm * D_FLT[i]; eq = after
    month_eq["end"] = (eq, withdrawn)
    return "kept", log, month_eq, eq, withdrawn
def monthly(month_eq):
    ks = list(month_eq); out = []
    for a, b in zip(ks[:-1], ks[1:]):
        (e0, w0), (e1, w1) = month_eq[a], month_eq[b]
        out.append(dict(month=a, made_pct=round(100 * ((e1 + (w1 - w0)) / e0 - 1), 1), made_usd=round(SIZE * (e1 + (w1 - w0) - e0))))
    return out
if __name__ == "__main__":
    h0 = idx.searchsorted(pd.Timestamp("2026-01-02", tz="UTC")); hE = len(idx) - 1
    print("data ends", idx[-1].date())
    st, log, meq, eq, wd = funded_log(h0, hE)
    M = pd.DataFrame(monthly(meq)); L = pd.DataFrame(log)
    print(f"\nA) FUNDED from 2 Jan 2026: {st}; payouts {int(L.paid.sum())} of {len(L)} two-week windows; paid to you ${L.payout_to_you.sum():,} (80%); balance now ${SIZE*eq:,.0f}")
    print(M.to_string(index=False)); print(L.to_string(index=False))
    d, tries, i = uf((h0, X, "The5ers High Stakes 2-Step"))
    print(f"\nB) CHALLENGE from 2 Jan 2026: funded after {d:.0f} days ({idx[i].date() if i else '-'}), attempts {tries}")
    if i:
        st, log, meq, eq, wd = funded_log(i + 48, hE); L = pd.DataFrame(log)
        print(f"   then funded until {idx[hE].date()}: {st}; payouts {int(L.paid.sum())} of {len(L)} windows; paid to you ${L.payout_to_you.sum():,}")
        print(pd.DataFrame(monthly(meq)).to_string(index=False))
