import sys
exec(open("rules_speed.py").read().split('\nif __name__ == "__main__":')[0])
def comp_tr(D, rf):
    R = np.zeros(len(idx)); Lw = np.zeros(len(idx)); h = idx.searchsorted(pd.DatetimeIndex(D.tx)); ok = h < len(idx)
    np.add.at(R, h[ok], rf * D.R.to_numpy()[ok]); np.add.at(Lw, h[ok], rf * np.minimum(D.R.to_numpy()[ok], 0)); return [R, Lw, np.zeros(len(idx))]
SIS = {"ORB30_NQ": ("sister_ORB_NQ_30.pkl", "orb15"), "DIP1h_BTC": ("sister_DIP_BTC_1h.pkl", "btc"), "DIP4h_XAU": ("sister_DIP_XAU_4h.pkl", "gdip"), "DIP1h_NQ": ("sister_DIP_NQ_1h.pkl", "nq2h")}
BASE_N = list(NAMES)
def setb(ex):
    for nm in [n for n in NAMES if n not in BASE_N]: NAMES.remove(nm); COMP.pop(nm, None)
    for nm, rf in ex.items(): COMP[nm] = comp_tr(pd.read_pickle(SIS[nm][0]), rf); PORT["21"][nm] = 1.0; BASE[nm] = 0.1; NAMES.append(nm)
if __name__ == "__main__":
    day = idx.normalize(); dd = lambda a: pd.Series(a, idx).groupby(day).sum().loc["2020-09-01":]
    setb({k: 0.001 for k in SIS})
    for k, (f, rel) in SIS.items(): print(f"{k}: daily corr with its pack sibling {rel}: {dd(COMP[k][0]).corr(dd(COMP[rel][0])):.2f}")
    ALL = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]; HS = RULES["The5ers High Stakes (8%+5%, 5% daily, 10% static)"]
    for tag, ex in (("21 EAs", {}), ("+ ORB30 NQ", {"ORB30_NQ": .002}), ("+ Dip1h BTC", {"DIP1h_BTC": .002}), ("+ Dip4h gold", {"DIP4h_XAU": .002}), ("+ Dip1h NQ", {"DIP1h_NQ": .002}),
                    ("+ all four 0.15% each", {k: .0015 for k in SIS})):
        setb(ex)
        for X_ in (3.0, 4.0):
            build({c: min(PORT["21"][c] * X_, 1.0 / BASE[c]) for c in NAMES}); arr = (EQ_R.copy(), EQ_L.copy(), D_FLT.copy())
            res = [attempt(arr, h, HS) for h in ALL]; tr = np.array([r[0] for r in res]); dys = np.array([r[1] for r in res])
            with Pool(os.cpu_count()) as p: g = pd.DataFrame(p.map(fund, [(h, X_, X_, "The5ers High Stakes 2-Step") for h in ALL]), columns=["o", "pct"])
            ok = g[g.o.notna()]
            print(f"{tag:24s} {X_:.0f}x | first try {100*np.mean(tr==1):.0f}% | median {np.nanmedian(dys):.0f} d | within 30d {100*np.mean(dys<=30):.0f}% | kept {100*(ok.o=='kept').mean():.0f}% | yr median {100*ok.pct.median():.1f}% | bad yr {100*ok.pct.quantile(.1):.1f}%", flush=True)
