import numpy as np, pandas as pd
exec(open("wport.py").read().split('if __name__ == "__main__":')[0])
CT = pd.read_pickle("crypto_trades.pkl")
COMP["solrev"] = intraday(CT["solrev"], 0.002); COMP["btcrev"] = intraday(CT["btcrev"], 0.002)
dtr = pd.read_pickle("dax_more.pkl")[1]["DAX 15min pre-market range trend50 stop-mid"]
COMP["daxpm"] = intraday([(et, xt, (px - e) / abs(e - st) * np.sign(e - st) - 0.0001 * e / abs(e - st)) for et, xt, e, st, px in dtr], 0.002)
NAMES = list(COMP)
DAILY = pd.DataFrame({c: pd.Series(COMP[c][0], idx).groupby(idx.normalize()).sum() for c in NAMES})
TRN = DAILY.loc["2020-09-01":"2022-12-31"]
def eqrisk(names):
    v = 1 / TRN[names].std(); v = v / v.mean(); return {c: float(v[c]) for c in names}
build({})
