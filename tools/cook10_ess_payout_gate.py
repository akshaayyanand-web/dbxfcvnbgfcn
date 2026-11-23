# ESS gate on payouts: (largest winning day + |largest losing day|) / cycle profit * 100 <= LIMIT. Funded $ account, 5% daily / 10% static,
# payout attempt every 14 days (else retried daily), 2% buffer left in. 3x risk. Compared with no ESS rule.
exec(open("firms.py").read().split('\nif __name__ == "__main__":')[0])
def run(a):
    h0, x, limit = a
    build({c: min(PORT["21"][c] * x, 1.0 / BASE[c]) for c in NAMES})
    eq = 1.0; opn = 0.0; day = -1; hd = -1; floor = 0.90; ref = 1.0; Z = 0.08; dstart = 1.0; dp = []; pays = []; nextpay = h0 + 14 * 24; ess_seen = []
    end = min(h0 + 365 * 24, len(EQ_R))
    for i in range(h0, end):
        if DAYN[i] != day:
            bal = eq - opn
            if day != -1: dp.append(bal - dstart)
            if i >= nextpay:
                w = min(bal, eq) - 1 - 0.02; prof = sum(dp)
                ess = (max(max(dp), 0) + abs(min(min(dp), 0))) / prof * 100 if prof > 0 and dp else 999
                if w > 0.005: ess_seen.append(ess)
                if w > 0.005 and (limit is None or ess <= limit): pays.append(w); eq -= w; dp = []; nextpay = i + 14 * 24; bal = eq - opn
                else: nextpay = i + 24
            day = DAYN[i]; dstart = bal; ref = max(bal, eq); mm = max(0.0, min(1.0, (eq - floor) / Z))
        if hd == day or (EQ_R[i] == 0 and EQ_L[i] == 0):
            if hd == day: opn = 0.0
            continue
        low = eq * (1 + mm * EQ_L[i]); after = eq * (1 + mm * EQ_R[i])
        if low <= ref - 0.04: eq = min(after, max(low, ref - 0.043)); opn = 0.0; hd = day
        elif low <= floor or low <= ref - 0.05: return ("breached", 0.8 * sum(pays), len(pays), np.median(ess_seen) if ess_seen else np.nan)
        else: opn += eq * mm * D_FLT[i]; eq = after
    return ("kept", 0.8 * sum(pays), len(pays), np.median(ess_seen) if ess_seen else np.nan)
if __name__ == "__main__":
    st = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    for lim in (None, 30, 20):
        with Pool(os.cpu_count()) as p: d = pd.DataFrame(p.map(run, [(h, 3.0, lim) for h in st]), columns=["o", "pct", "n", "ess"])
        print(dict(ess_rule="none" if lim is None else f"ESS <= {lim}%", kept=round(100 * (d.o == "kept").mean()), payouts_per_yr=d.n.median(),
                   yr_median_to_you=round(100 * d.pct.median(), 1), yr_p10=round(100 * d.pct.quantile(.1), 1), typical_ESS_at_payout_time=round(d.ess.median(), 0)), flush=True)
