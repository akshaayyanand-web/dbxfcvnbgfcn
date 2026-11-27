# FTSE 100 through both catalogue engines (cat1000: 1,000 rows; cat2000: 158 setups x 3 exits), M15 and H1, plus FTSE intermarket catch-up trades.
import sys, numpy as np, pandas as pd
from multiprocessing import Pool
sys.argv = sys.argv[:1]
import cat1000 as K
K.MK["UKX"] = (lambda: K.hd("UKXGBP"), None, 0.00015, 0.05, ("Europe/London", 8, 0), "index"); K.PAIR["UKX"] = "SPX"; K.LEAD["UKX"] = "SPX"
import cat2000 as K2
def job(j):
    eng, tf = j
    try: return eng, tf, (K.run(("UKX", tf)) if eng == "cat1" else K2.run(("UKX", tf)))
    except Exception as ex:
        import traceback; traceback.print_exc(); return eng, tf, []
if __name__ == "__main__":
    with Pool(4) as p: out = p.map(job, [("cat1", "M15"), ("cat1", "H1"), ("cat2", "M15"), ("cat2", "H1")], chunksize=1)
    A = pd.DataFrame([r for e, t, rows in out if e == "cat1" for r in rows]); B = pd.DataFrame([r for e, t, rows in out if e == "cat2" for r in rows])
    A.to_pickle("ftse_cat1.pkl"); B.to_pickle("ftse_cat2.pkl")
    from math import erf, sqrt
    pn = lambda z: 0.5 * (1 + erf(z / sqrt(2))); ptr, pho = 1 - pn(2.5), 1 - pn(2.0)
    for nm, D, idc in (("Catalogue 1 (1,000 rows)", A, "ID"), ("List 2 (158 setups)", B, "sid")):
        D = D[D.n > 0].copy(); M = int((D.n_train >= 100).sum())
        D["ptr"] = (D.t_train >= 2.5) & (D.n_train >= 100); D["pall"] = D.ptr & (D.t_hold >= 2) & (D.avgR_hold >= 0.05) & (D.n_hold >= 50) & (D.pos_years >= 0.7 * D.years)
        print(f"\n{nm}: {M} tests | median avgR train {D.avgR_train.median():+.3f}, holdout {D.avgR_hold.median():+.3f} | passed train {D.ptr.sum()} (luck ~{M*ptr:.1f}) | passed both {D.pall.sum()} (luck ~{M*ptr*pho:.2f})")
        top = D.sort_values("t_hold", ascending=False).head(10)[[idc, "tf", "exit", "n_train", "n_hold", "avgR_train", "avgR_hold", "t_train", "t_hold", "pos_years", "years"]]
        if idc == "sid": names = [l.strip() for l in open("cat2000/list2.txt")]; top.insert(1, "name", top.sid.map(lambda i: names[i - 1]))
        else: cat = pd.read_excel("cat1000/cat.xlsx"); top.insert(1, "name", top.ID.map(dict(zip(cat.ID, cat["Strategy hypothesis"]))))
        pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 50); print(top.round(3).to_string(index=False))
        if D.pall.sum(): print("SURVIVORS:"); print(D[D.pall].round(3).to_string(index=False))
    # ---- intermarket catch-up (daily closes 21:00 UTC), hold 5 days, no overlap
    exec(open("cat2000_daily.py").read().split("TESTS = []")[0], globals())
    P = PX.copy(); P["UKX"] = daily(K.hd("UKXGBP").c.resample("1h").last().dropna()); RET2 = np.log(P).diff()
    rows = []
    def test(name, sig, H=5, skip=0):
        r = RET2.UKX.fillna(0).to_numpy(); s = sig.reindex(P.index).fillna(0).to_numpy(); out = []; k = 0
        while k < len(r) - H - skip - 1:
            if s[k] != 0: a = k + skip; out.append((P.index[a], s[k] * r[a + 1:a + 1 + H].sum() - 0.00015 - 0.05 / 365 * 1.4 * H)); k = a + H
            else: k += 1
        D = pd.DataFrame(out, columns=["t", "net"]); A_, B_ = D[D.t < "2023-01-01"].net, D[D.t >= "2023-01-01"].net
        tt = lambda v: round(v.mean() / v.std() * np.sqrt(len(v)), 2) if len(v) > 2 else np.nan
        rows.append(dict(test=name, trades=len(D), avg_bp_train=round(1e4 * A_.mean(), 1), t_train=tt(A_), avg_bp_hold=round(1e4 * B_.mean(), 1), t_hold=tt(B_)))
    L5_ = lambda s: np.log(s) - np.log(s.shift(5)); al_ = lambda s: s.reindex(P.index, method="ffill")
    for nm, x in (("GBPUSD", L5_(P.GBPUSD)), ("SPX", L5_(P.SPX)), ("DAX", L5_(P.DAX)), ("DXY", L5_(al_(fred("DTWEXBGS"))))):
        test(f"FTSE catches up with {nm} (5-day residual)", catchup(L5_(P.UKX), x))
    m20 = np.log(P.UKX).diff(20); test("FTSE 20-day momentum", sig_from(m20 > 0, m20 < 0))
    r5 = z(L5_(P.UKX), 250); test("FTSE 5-day 2-sigma reversal", sig_from(r5 < -2, r5 > 2))
    print("\nFTSE INTERMARKET / DAILY:"); print(pd.DataFrame(rows).to_string(index=False))
