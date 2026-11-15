import os, sys, numpy as np, pandas as pd
sys.path.insert(0, "/home/user/dbxfcvnbgfcn/tools")
exec(open("fs_funded2.py").read().split('if __name__ == "__main__":')[0])
bp = open("/home/user/dbxfcvnbgfcn/tools/build_packs.py").read().split('if __name__ == "__main__":')[0]; bp = bp[bp.index("FTMO_G"):]; exec(bp)
def W(risks, fs=False): return {c: risks.get(c, 0) / BASE[c] * (WKD.get(c, 1.0) if fs else 1.0) for c in NAMES}
END = len(EQ_R) - 1
def fs_run(h0):
    build(W(FS_R, True)); p, i, _, _ = acct(h0, target=0.09)
    if p != "pass": return dict(firm="FS", start=idx[h0], ev=p)
    build(W(FS_FUND, True)); o, j, v, pays = acct(i + 48, days=(END - i - 48) // 24, fguard=0.012)
    gross = 200000 * sum(pays); you = 0.8 * gross + (0.2 * 0.09 * 200000 if gross > 0 else 0)
    return dict(firm="FS", start=idx[h0], ev="pass", days=(i - h0) / 24, funded=o, gross=gross, you=you, npay=len(pays))
def ftmo_run(h0):
    build(W(FTMO_EVAL)); p, i, _, _ = acct(h0, target=0.10, DL=0.05, G=0.04)
    if p != "pass": return dict(firm="FTMO", start=idx[h0], ev=p)
    p, i2, _, _ = acct(i + 1, target=0.05, DL=0.05, G=0.04)
    if p != "pass": return dict(firm="FTMO", start=idx[h0], ev=p + " ph2")
    build(W(FTMO_FUND)); o, j, v, pays = acct(i2 + 48, days=(END - i2 - 48) // 24, DL=0.05, G=0.04, flimit=9)
    gross = 200000 * sum(pays)
    return dict(firm="FTMO", start=idx[h0], ev="pass", days=(i2 - h0) / 24, funded=o, gross=gross, you=0.8 * gross, npay=len(pays))
def job(a): f, h0 = a; return fs_run(h0) if f == "FS" else ftmo_run(h0)
if __name__ == "__main__":
    starts = [idx.searchsorted(s) for s in pd.date_range("2026-01-02", "2026-01-30", freq="1D", tz="UTC") if s.weekday() < 5]
    allst = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    with Pool(os.cpu_count()) as p:
        R = pd.DataFrame(p.map(job, [(f, h) for f in ("FS", "FTMO") for h in starts]))
        A = pd.DataFrame(p.map(lambda a: None, []) or [])
    pd.set_option("display.width", 250)
    for f in ("FS", "FTMO"):
        d = R[R.firm == f]; ok = d[d.ev == "pass"]
        print(f, "2026 starts (Jan weekdays):", len(d), "| passed", len(ok), "| eval days median", ok.days.median(), "min", ok.days.min(), "max", ok.days.max(),
              "| funded", ok.funded.value_counts().to_dict(), "| gross median", round(ok.gross.median()), "| to you median", round(ok.you.median()),
              "min", round(ok.you.min()), "max", round(ok.you.max()), "| payouts median", ok.npay.median())
    print(R[R.start.dt.day == 2].to_string())
    # full-history eval time check for FTMO with the pack's settings
    from multiprocessing import Pool as P2
    with P2(os.cpu_count()) as p: F = pd.DataFrame(p.map(job, [("FTMO", h) for h in allst]))
    ok = F[F.ev == "pass"]; print("FTMO 2020-25: passed", round(100 * len(ok) / len(F), 1), "% median days", ok.days.median(), "kept 1yr+ funded", (ok.funded == "kept").mean())
