exec(open("wport2.py").read())
BASE = {"btc": .75, "gdip": .625, "nq2h": .3125, "spx1h": .3125, "oil1h": .1875, "gasia": .3125, "gmom": .3125, "orb15": .625, "nqbo15": .2, "daxorb": .2,
        "spxbo5": .1, "btcgap": .25, "sol": .3, "goldvwap": .2, "spxfade": .25, "nikkei": .1, "solrev": .2, "btcrev": .2, "daxpm": .2}
EQ19 = eqrisk(NAMES)
ww = {c: min(EQ19[c] * 4.0, 0.75 / BASE[c]) for c in EQ19}
tab = {c: round(ww[c] * BASE[c], 3) for c in sorted(ww, key=lambda c: -ww[c] * BASE[c])}
pd.to_pickle({"mult": ww, "risk": tab}, "final_risk.pkl")
print("RISK", tab)
