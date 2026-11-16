src = open("y2026.py").read(); exec(src[:src.index("\nif __name__")])
NOWK = {"btcgap": 0.0, "btc": 0.0}          # multi-day crypto holds cross weekends: dropped
def run(a):
    h0, scale, fg = a
    build({c: min(PORT["21"][c] * scale, 1.0 / BASE[c]) * NOWK.get(c, WKD.get(c, 1.0)) for c in NAMES})
    eq = 1.0; opn = 0.0; day = -1; hd = -1; peak = 1.0; floor = 0.95; pays = []; nextpay = h0 + 14 * 24; cyc = []; dstart = 1.0; mm = 1.0; ref = 1.0
    end = min(h0 + 365 * 24, len(EQ_R))
    for i in range(h0, end):
        if DAYN[i] != day:
            if day != -1: cyc.append((eq - opn) - dstart)
            day = DAYN[i]; dstart = eq - opn; ref = max(eq - opn, eq); mm = max(0.0, min(1.0, (eq - floor) / 0.04))
            if i >= nextpay:
                bal = eq - opn; prof = bal - 1.0; wd = min(bal, eq) - 1.03; c30 = cyc[-30:]
                if wd >= 0.01 and sum(x >= 0.0025 for x in c30) >= 7 and max(cyc) <= 0.15 * prof:
                    pays.append(wd); eq -= wd; cyc = []; nextpay = i + 14 * 24
        if hd == day or (EQ_R[i] == 0 and EQ_L[i] == 0):
            if hd == day: opn = 0.0
            continue
        low = eq * (1 + mm * EQ_L[i]); after = eq * (1 + mm * EQ_R[i])
        if low <= ref - 0.02: eq = min(after, max(low, ref - 0.023)); opn = 0.0; hd = day
        elif low <= floor or low <= ref - 0.03: return "lost", sum(pays)
        else:
            opn_new = opn + eq * mm * D_FLT[i]; fl = min(opn_new + (low - after), opn_new)
            if fl <= -fg: eq = (eq - opn) - fg - 0.002; opn = 0.0; hd = day
            else: opn = opn_new; eq = after
        if eq <= floor: return "lost", sum(pays)
        peak = max(peak, eq); floor = 1.0 if peak >= 1.05 else max(floor, peak - 0.05)
        if eq <= floor + 0.003: return "stopped", sum(pays)
    return "kept", sum(pays)
if __name__ == "__main__":
    st = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-10-30", freq="7D", tz="UTC")]
    for sc in (0.5, 1.0, 1.5, 2.0, 3.0):
        with Pool(os.cpu_count()) as p: R = pd.DataFrame(p.map(run, [(h, sc, 0.008) for h in st]), columns=["o", "pct"])
        print(sc, R.o.value_counts().to_dict(), "median %/yr withdrawn", round(100 * R.pct.median(), 1), "25%", round(100 * R.pct.quantile(.25), 1), "75%", round(100 * R.pct.quantile(.75), 1))
