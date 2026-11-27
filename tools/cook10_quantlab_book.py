import sys
exec(open("rules_speed.py").read().split('\nif __name__ == "__main__":')[0])
Q = pd.read_pickle("ql_trades.pkl")
def comp_from(D, rf):
    R = np.zeros(len(idx)); Lw = np.zeros(len(idx))
    t = (pd.DatetimeIndex(D.day).tz_localize("America/New_York") + pd.Timedelta(hours=15, minutes=30)).tz_convert("UTC"); h = idx.searchsorted(t); ok = h < len(idx)
    np.add.at(R, h[ok], rf * D.R.to_numpy()[ok]); np.add.at(Lw, h[ok], rf * np.minimum(D.R.to_numpy()[ok], 0)); return [R, Lw, np.zeros(len(idx))]
CAND = {"SOM": Q[("SessionOpenMom", "NQ", "stop 2.0x candle, exit 6h")], "NB": Q[("NoiseBand", "NQ", "k=1.0")]}
BASE_N = list(NAMES)
def setb(ex):
    for nm in [n for n in NAMES if n not in BASE_N]: NAMES.remove(nm); COMP.pop(nm, None)
    for nm, rf in ex.items(): COMP["ql" + nm] = comp_from(CAND[nm], rf); PORT["21"]["ql" + nm] = 1.0; BASE["ql" + nm] = 0.1; NAMES.append("ql" + nm)
if __name__ == "__main__":
    day = idx.normalize(); dd = lambda arr: pd.Series(arr, idx).groupby(day).sum().loc["2020-09-01":]
    setb({"SOM": 0.001, "NB": 0.001}); build({c: PORT["21"][c] for c in BASE_N}); bk = dd(EQ_R)
    for nm in ("SOM", "NB"):
        s = dd(COMP["ql" + nm][0]); print(f"{nm}: corr with book {bk.corr(s):.2f} | with NQ ORB {dd(COMP['orb15'][0]).corr(s):.2f} | NQ breakout {dd(COMP['nqbo15'][0]).corr(s):.2f} | NQ fade {dd(COMP['nqfade'][0]).corr(s):.2f}")
    print(f"SOM vs NB: {dd(COMP['qlSOM'][0]).corr(dd(COMP['qlNB'][0])):.2f}", flush=True)
    ALL = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    HS = RULES["The5ers High Stakes (8%+5%, 5% daily, 10% static)"]
    for tag, ex in (("21 EAs", {}), ("+ Session Open Momentum 0.2%", {"SOM": 0.002}), ("+ Noise Band 0.2%", {"NB": 0.002}), ("+ both 0.2% each", {"SOM": 0.002, "NB": 0.002}), ("+ both 0.33% each", {"SOM": 0.0033, "NB": 0.0033})):
        setb(ex)
        for X_ in (3.0, 4.0):
            build({c: min(PORT["21"][c] * X_, 1.0 / BASE[c]) for c in NAMES}); arr = (EQ_R.copy(), EQ_L.copy(), D_FLT.copy())
            res = [attempt(arr, h, HS) for h in ALL]; tr = np.array([r[0] for r in res]); dys = np.array([r[1] for r in res])
            with Pool(os.cpu_count()) as p: g = pd.DataFrame(p.map(fund, [(h, X_, X_, "The5ers High Stakes 2-Step") for h in ALL]), columns=["o", "pct"])
            ok = g[g.o.notna()]
            print(f"{tag:30s} {X_:.0f}x | first try {100*np.mean(tr==1):.0f}% | median {np.nanmedian(dys):.0f} d | within 30d {100*np.mean(dys<=30):.0f}% | funded kept {100*(ok.o=='kept').mean():.0f}% | yr median {100*ok.pct.median():.1f}% | bad yr {100*ok.pct.quantile(.1):.1f}%", flush=True)
