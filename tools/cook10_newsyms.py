# New markets through both catalogue engines (+ Noise Band / Session Open Momentum on the new indices).
import sys, glob, numpy as np, pandas as pd
from multiprocessing import Pool
sys.argv = sys.argv[:1]
import cat1000 as K
def kh(sym):
    p = []
    for f in sorted(glob.glob(f"kh/{sym}USDT-1h-*.csv")):
        x = pd.read_csv(f, header=None, usecols=[0, 1, 2, 3, 4, 5], names=["t", "o", "h", "l", "c", "v"]); x["t"] = np.where(x.t > 1e14, x.t // 1000, x.t); p.append(x)
    x = pd.concat(p); x.index = pd.to_datetime(x.t, unit="ms", utc=True); return x[["o", "h", "l", "c", "v"]].astype(float).sort_index().loc[lambda z: ~z.index.duplicated()]
NEW = {"HSI": ("HKXHKD", .0004, .05, ("Asia/Hong_Kong", 9, 30), "index"), "ASX": ("AUXAUD", .0002, .05, ("Australia/Sydney", 10, 0), "index"),
       "CAC": ("FRXEUR", .00015, .05, ("Europe/Paris", 9, 0), "index"), "STOXX": ("ETXEUR", .0003, .05, ("Europe/Berlin", 9, 0), "index"),
       "BRENT": ("BCOUSD", .0005, .05, ("Europe/London", 8, 0), "oil"), "USDMXN": ("USDMXN", .0006, .06, ("America/New_York", 8, 0), "fx"),
       "USDZAR": ("USDZAR", .0008, .06, ("Europe/London", 8, 0), "fx"), "AUDJPY": ("AUDJPY", .00015, .02, ("Asia/Tokyo", 9, 0), "fx"), "CADJPY": ("CADJPY", .00018, .02, ("America/New_York", 8, 0), "fx")}
for s, (p, c, sw, ses, cl) in NEW.items():
    K.MK[s] = ((lambda p=p: K.hd(p)), None, c, sw, ses, cl); K.PAIR[s] = None; K.LEAD[s] = "SPX" if cl == "index" else None
ALTS = ["ADA", "AVAX", "BCH", "BNB", "DOGE", "DOT", "LINK", "LTC", "TRX"]
for s in ALTS: K.MK[s] = (None, (lambda s=s: kh(s)), .002, .15, ("America/New_York", 9, 30), "crypto"); K.PAIR[s] = None; K.LEAD[s] = "BTC"
import cat2000 as K2
def job(j):
    eng, sym, tf = j
    try: rows = K.run((sym, tf)) if eng == "cat1" else K2.run((sym, tf))
    except Exception as ex:
        print("FAIL", j, ex, flush=True); rows = []
    for r in rows: r["engine"] = eng
    return rows
SESS = {"HSI": ("Asia/Hong_Kong", 570, 960), "ASX": ("Australia/Sydney", 600, 960), "CAC": ("Europe/Paris", 540, 1050), "STOXX": ("Europe/Berlin", 540, 1050)}
def nb_som(sym):
    src = open("ql.py").read(); ns = {}; exec(src.split("if __name__")[0], ns)
    tz, o_, c_ = SESS[sym]; L = c_ - o_
    def sessions(_):
        d = K.hd(NEW[sym][0]).copy(); d.index = d.index.tz_convert(tz); d = d[d.index.dayofweek < 5]; mn = d.index.hour * 60 + d.index.minute; d = d[(mn >= o_) & (mn < c_)]
        d["m"] = (d.index.hour * 60 + d.index.minute) - o_; d["v"] = 1.0; out = {}
        for day, x in d.groupby(d.index.normalize()):
            if len(x) > 0.6 * L and x.m.iloc[0] <= 2: out[day] = x
        return out, L
    ns["sessions"] = sessions; ns["COST"] = NEW[sym][1]; res = []
    for f, a, lab in ((ns["noise_band"], (sym, 1.0), "Noise Band k=1"), (ns["noise_band"], (sym, 2.0), "Noise Band k=2"), (ns["som"], (sym, 2.0, "6h"), "Session Open Mom 2x/6h")):
        tr = f(a)[3]; D = pd.DataFrame(tr, columns=["day", "R"])
        if len(D) < 30: continue
        D["day"] = pd.to_datetime(D.day).dt.tz_localize(None); A, B = D[D.day < "2023-01-01"].R, D[D.day >= "2023-01-01"].R
        tt = lambda v: round(v.mean() / v.std(ddof=1) * np.sqrt(len(v)), 2) if len(v) > 2 else np.nan
        res.append(dict(market=sym, system=lab, trades=len(D), avgR_train=round(A.mean(), 3), t_train=tt(A), avgR_hold=round(B.mean(), 3), t_hold=tt(B)))
    return res
if __name__ == "__main__":
    avail = [s for s in NEW if len(glob.glob(f"hd/raw/{NEW[s][0]}_*.zip")) >= 15]; print("HistData markets available:", avail, flush=True)
    jobs = [(e, s, tf) for s in avail for tf in ("M15", "H1") for e in ("cat1", "cat2")] + [(e, s, "H1") for s in ALTS for e in ("cat1", "cat2")]
    with Pool(4) as p: out = p.map(job, jobs, chunksize=1)
    D = pd.DataFrame([r for o in out for r in o]); D.to_pickle("newsyms_results.pkl")
    from math import erf, sqrt
    pn = lambda z: 0.5 * (1 + erf(z / sqrt(2))); ptr, pho = 1 - pn(2.5), 1 - pn(2.0)
    D = D[D.n > 0].copy(); D["ptr"] = (D.t_train >= 2.5) & (D.n_train >= 100); D["pall"] = D.ptr & (D.t_hold >= 2) & (D.avgR_hold >= 0.05) & (D.n_hold >= 50) & (D.pos_years >= 0.7 * D.years)
    M = int((D.n_train >= 100).sum()); print(f"\nALL NEW MARKETS: {M} tests | passed train {D.ptr.sum()} (luck ~{M*ptr:.0f}) | passed both {D.pall.sum()} (luck ~{M*ptr*pho:.1f})")
    g = D.groupby("sym").agg(tests=("n", "size"), med_train=("avgR_train", "median"), med_hold=("avgR_hold", "median"), pass_train=("ptr", "sum"), pass_both=("pall", "sum"))
    print(g.round(3).to_string())
    pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 40)
    S = D[D.pall].sort_values("t_hold", ascending=False); print("\nSURVIVORS:"); print(S[["engine", "sym", "tf", "ID", "sid", "exit", "n_train", "n_hold", "avgR_train", "avgR_hold", "t_train", "t_hold", "pos_years", "years"]].round(3).to_string(index=False) if len(S) else "none")
    print("\nNOISE BAND / SESSION OPEN MOMENTUM on the new indices:")
    with Pool(4) as p: nb = p.map(nb_som, [s for s in SESS if s in avail])
    print(pd.DataFrame([r for o in nb for r in o]).to_string(index=False))
