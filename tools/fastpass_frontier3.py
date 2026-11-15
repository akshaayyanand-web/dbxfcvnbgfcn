import os, numpy as np, pandas as pd
exec(open("wport2.py").read())
MT = pd.read_pickle("more_trades.pkl")
COMP["nqfade"] = intraday(MT["nqfade"], 0.0025); COMP["xrprev"] = intraday(MT["xrprev"], 0.002)
NAMES = list(COMP)
DAILY = pd.DataFrame({c: pd.Series(COMP[c][0], idx).groupby(idx.normalize()).sum() for c in NAMES}); TRN = DAILY.loc["2020-09-01":"2022-12-31"]
BASE = {"btc": .75, "gdip": .625, "nq2h": .3125, "spx1h": .3125, "oil1h": .1875, "gasia": .3125, "gmom": .3125, "orb15": .625, "nqbo15": .2, "daxorb": .2,
        "spxbo5": .1, "btcgap": .25, "sol": .3, "goldvwap": .2, "spxfade": .25, "nikkei": .1, "solrev": .2, "btcrev": .2, "daxpm": .2, "nqfade": .25, "xrprev": .2}
def eqr(names): v = 1 / TRN[names].std(); v = v / v.mean(); return {c: float(v[c]) for c in names}
P19 = [c for c in NAMES if c not in ("nqfade", "xrprev")]
PORT = {"19": eqr(P19), "21": eqr(NAMES)}
for k, w in PORT.items():
    p = DAILY[list(w)].values @ np.array(list(w.values()))
    s = pd.Series(p, DAILY.index); a = s[:"2022-12-31"]; b = s["2023-01-01":]
    print(f"{k} EAs equal risk: Sharpe 2020-22 {a.mean()/a.std()*np.sqrt(252):.2f}, 2023-26 {b.mean()/b.std()*np.sqrt(252):.2f}", flush=True)
def ev(args):
    port, scale, cap, Z, half = args; w = PORT[port]; build({c: (min(w[c] * scale, cap / BASE[c]) if c in w else 0.0) for c in NAMES})
    res = []
    for s in pd.date_range("2020-09-01", "2026-05-01", freq="3D", tz="UTC"):
        if s.weekday() >= 5: continue
        h0 = idx.searchsorted(s); p1, i1, _ = core(h0, 1.0, Z, target=0.10, half=half)
        if p1 != "pass": res.append((p1, None)); continue
        p2, i2, _ = core(i1 + 1, 1.0, Z, target=0.05, half=half); res.append((p2, (i2 - h0) / 24 if p2 == "pass" else None))
    d = pd.DataFrame(res, columns=["o", "d"]); d = d[d.o != "open"]; t = d.d.dropna()
    return dict(eas=port, scale=scale, cap=cap, room=Z, half=str(half), pass_pct=round(100 * (d.o == "pass").mean(), 1), breach=round(100 * (d.o == "breach").mean(), 1),
                med=round(t.median()), p25=round(t.quantile(.25)), p75=round(t.quantile(.75)), within30=round(100 * (d.d <= 30).mean()))
if __name__ == "__main__":
    jobs = [(pt, sc, cap, Z, hf) for pt in ("19", "21") for sc in (4.0, 4.5) for cap in (0.75, 1.0) for Z in (0.07,) for hf in ((0.03, 0.01), (0.02, 0.005))]
    with Pool(os.cpu_count()) as p: rows = p.map(ev, jobs)
    pd.set_option("display.width", 250); print(pd.DataFrame(rows).sort_values(["pass_pct", "med"], ascending=[False, True]).to_string(index=False))
