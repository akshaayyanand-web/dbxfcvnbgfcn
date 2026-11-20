# Pipcy funded with the reported 4% maximum floating loss on open positions.
exec(open("pipcy.py").read().split('\nif __name__ == "__main__":')[0])
src = open("combo10.py").read(); a0 = src.index("def acct("); a1 = src.index("def two_step(")
fsrc = src[a0:a1].replace("def acct(", "def acct_f(").replace("split=0.8):", "split=0.8, FG=None, hard=False):")
fsrc = fsrc.replace("        else: opn += eq * mm * D_FLT[i]; eq = after\n",
"""        else:
            opn_new = opn + eq * mm * D_FLT[i]; fl = min(opn_new + (low - after), opn_new)
            if FG is not None and fl <= -FG:
                if hard: return "breached", (i - h0) / 24, i, pays
                eq = (eq - opn) - FG - 0.002; opn = 0.0; hd = day
            else: opn = opn_new; eq = after
""")
assert "opn_new" in fsrc; exec(fsrc)
def job(a):
    h0, fs, FG, hard = a; d, tries, i = until_funded_p((h0, 6.0, "1-Step", 0.08))
    if i is None or tries > 1: return (None, 0.0)
    o, _, _, pays = acct_f(i + 48, fs, list(NAMES), days=365, DL=1.0, ML=ML, G=0.08, buf=0.02, FG=FG, hard=hard)
    return (o, 0.8 * sum(pays))
if __name__ == "__main__":
    st = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    for lab, FG, hard in (("(a) no floating rule", None, False), ("(b) EA closes all at -3.5% open loss", 0.035, False), ("(c) no guard: -4% open loss = breach", 0.04, True)):
        for fs in (2.0, 3.0, 4.0):
            with Pool(os.cpu_count()) as p: d = pd.DataFrame(p.map(job, [(h, fs, FG, hard) for h in st]), columns=["o", "pct"])
            ok = d[d.o.notna()]
            print(dict(rule=lab, funded_x=fs, kept=round(100 * (ok.o == "kept").mean()), yr_median=round(100 * ok.pct.median(), 1), yr_p10=round(100 * ok.pct.quantile(.1), 1), yr_p25=round(100 * ok.pct.quantile(.25), 1)), flush=True)
