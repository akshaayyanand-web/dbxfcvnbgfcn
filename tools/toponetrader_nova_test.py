src = open("fundingpips_zero_test.py").read(); exec(src[:src.index("\nif __name__")])
BUF = 0.03
def acct2(h0, scale, target=None, DL=None, TD=0.06, cons=None, days=None, G=0.02, Z=None):
    build({c: min(PORT["21"][c] * scale, 1.0 / BASE[c]) for c in NAMES})
    Z = Z or TD * 0.8
    eq = 1.0; opn = 0.0; day = -1; hd = -1; peak = 1.0; floor = 1 - TD; pays = []; cyc = []; dstart = 1.0; ref = 1.0; mm = 1.0
    end = min(h0 + (days or 400) * 24, len(EQ_R)); nextpay = h0 + 14 * 24
    for i in range(h0, end):
        if DAYN[i] != day:
            if day != -1: cyc.append((eq - opn) - dstart)
            bal = eq - opn
            if target and bal >= 1 + target: return "pass", i, pays
            day = DAYN[i]; dstart = bal; ref = max(bal, eq); mm = max(0.0, min(1.0, (eq - floor) / Z))
            if days and i >= nextpay:
                prof = bal - 1.0
                if prof > BUF + 0.005 and max(cyc) <= cons * prof:
                    w = min(prof, eq - 1.0) - BUF; pays.append(w); eq -= w; cyc = []; nextpay = i + 14 * 24
                    if peak < 1 + TD: peak -= w; floor = peak - TD
        if hd == day or (EQ_R[i] == 0 and EQ_L[i] == 0):
            if hd == day: opn = 0.0
            continue
        low = eq * (1 + mm * EQ_L[i]); after = eq * (1 + mm * EQ_R[i])
        if DL and low <= ref - G: eq = min(after, max(low, ref - G - 0.003)); opn = 0.0; hd = day
        elif low <= floor or (DL and low <= ref - DL): return "breached", i, pays
        else: opn += eq * mm * D_FLT[i]; eq = after
        peak = max(peak, eq); floor = 1.0 if peak >= 1 + TD else max(floor, peak - TD)
        if eq <= floor: return "breached", i, pays
    return ("open" if target else "kept"), end - 1, pays
def job(a):
    h0, es, fs = a
    p, i, _ = acct2(h0, es, target=0.05, TD=0.06)
    if p != "pass": return (p, None, None, 0)
    o, j, pays = acct2(i + 48, fs, DL=0.03, TD=0.05, cons=0.20, days=365)
    return ("pass", (i - h0) / 24, o, 0.9 * 300000 * sum(pays))
if __name__ == "__main__":
    st = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    for es, fs in ((2.0, 0.75), (2.0, 1.0), (2.0, 1.5), (2.0, 2.0)):
        with Pool(os.cpu_count()) as p: d = pd.DataFrame(p.map(job, [(h, es, fs) for h in st]), columns=["ev", "days", "o", "you"])
        ok = d[d.ev == "pass"]
        print(f"eval x{es} funded x{fs} | passed {100*len(ok)/len(d):.0f}% median {ok.days.median():.0f}d 90% {ok.days.quantile(.9):.0f}d | funded {ok.o.value_counts().to_dict()} | to you/yr median ${ok.you.median():,.0f} 25% ${ok.you.quantile(.25):,.0f}")
