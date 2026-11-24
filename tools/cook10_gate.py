# G1: regime gating of the 21-EA book. Signals known at the prior US close (lagged one day):
#  TS  : VIX / VIX3M (>1 = backwardation, stress)        S9 : VIX9D / VIX (short-term panic)
#  HY  : 20-day change in high-yield OAS (BAMLH0A0HYM2)  NF : NFCI level (>0 = tighter than average)
#  VX  : VIX level
# Step 1: book daily P&L by regime bucket (pre-2023 / 2023+). Step 2 (pre-registered gates): x0.5 in stress, x1.25 in calm; book Sharpe + The5ers sim.
import sys
exec(open("firms.py").read().split('\nif __name__ == "__main__":')[0])
def cboe(n): v = pd.read_csv(f"rdata/cboe/{n}.csv"); v.index = pd.to_datetime(v.DATE, format="%m/%d/%Y"); return v.CLOSE
def fred(n): v = pd.read_csv(f"rdata/fred/{n}.csv"); v.index = pd.to_datetime(v.iloc[:, 0]); return pd.to_numeric(v.iloc[:, 1], errors="coerce")
vix, v3, v9 = cboe("VIX"), cboe("VIX3M"), cboe("VIX9D"); hy = fred("BAMLH0A0HYM2").dropna(); nf = fred("NFCI").dropna()
SIG = pd.DataFrame({"TS": vix / v3, "S9": v9 / vix, "VX": vix, "HY": hy - hy.shift(20)}).ffill()
SIG["NF"] = nf.reindex(SIG.index, method="ffill")
SIG = SIG.shift(1)                                                     # use yesterday's close only
SIG.index = SIG.index.tz_localize("UTC")
build({c: PORT["21"][c] for c in NAMES}); R0, L0, F0 = EQ_R.copy(), EQ_L.copy(), D_FLT.copy()
day = idx.normalize(); bd = pd.Series(R0, idx).groupby(day).sum().loc["2020-09-01":]
S = SIG.reindex(bd.index, method="ffill"); SPLIT = pd.Timestamp("2023-01-01", tz="UTC")
print("Book daily P&L (bp of account at 1x) by regime bucket:")
buckets = {"TS": [0, 0.85, 0.95, 1.0, 9], "S9": [0, 0.85, 1.0, 1.1, 9], "VX": [0, 15, 20, 30, 99], "HY": [-9, -0.3, 0, 0.3, 9], "NF": [-9, -0.5, -0.3, 0, 9]}
for k, b in buckets.items():
    cut = pd.cut(S[k], b)
    for per, m in (("pre2023", bd.index < SPLIT), ("2023on", bd.index >= SPLIT)):
        g = bd[m].groupby(cut[m], observed=True).agg(["count", "mean", "std"])
        print(f"  {k} {per}: " + " | ".join(f"{iv}: n={int(r['count'])} {1e4*r['mean']:+.1f}bp sh={r['mean']/r['std']*np.sqrt(365):.1f}" for iv, r in g.iterrows()))
GATES = {"TS>1 x0.5": lambda s: np.where(s.TS > 1.0, 0.5, 1.0), "S9>1.1 x0.5": lambda s: np.where(s.S9 > 1.1, 0.5, 1.0),
         "HY chg>0.3 x0.5": lambda s: np.where(s.HY > 0.3, 0.5, 1.0), "NFCI>0 x0.5": lambda s: np.where(s.NF > 0, 0.5, 1.0),
         "TS<0.85 x1.25": lambda s: np.where(s.TS < 0.85, 1.25, 1.0), "VIX>30 x0.5": lambda s: np.where(s.VX > 30, 0.5, 1.0)}
def sharpe(x): x = x.loc["2020-09-01":]; s = lambda y: round(y.mean() / y.std() * np.sqrt(365), 2); return s(x[x.index < SPLIT]), s(x[x.index >= SPLIT]), round(100 * x.sum() / 6.2, 1)
print("\nBOOK at 1x: Sharpe 2020-22 / 2023-26 / %/yr:", sharpe(bd))
st = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
def firm_sim(tag):
    with Pool(os.cpu_count()) as p: d = pd.DataFrame(p.map(uf, [(h, 3.0, "The5ers High Stakes 2-Step") for h in st]), columns=["days", "tries", "i"])
    with Pool(os.cpu_count()) as p: g = pd.DataFrame(p.map(fund, [(h, 3.0, 3.0, "The5ers High Stakes 2-Step") for h in st]), columns=["o", "pct"])
    ok = g[g.o.notna()]; print("   ", dict(book=tag, median_days=d.days.median(), first_try=round(100 * (d.tries == 1).mean()), kept=round(100 * (ok.o == "kept").mean()),
                                         yr_median=round(100 * ok.pct.median(), 1), yr_p10=round(100 * ok.pct.quantile(.1), 1)), flush=True)
if __name__ == "__main__":
    pass
    SAVE = {c: [a.copy() for a in COMP[c]] for c in NAMES}
    for nm, f in GATES.items():
        gh = pd.Series(f(SIG.reindex(idx.normalize(), method="ffill").ffill()), idx).fillna(1.0).to_numpy()
        for c in NAMES: COMP[c] = [SAVE[c][0] * gh, SAVE[c][1] * gh, SAVE[c][2] * gh]
        build({c: PORT["21"][c] for c in NAMES}); print(f"\n{nm}: share of days gated {100*(gh[::24]!=1).mean():.0f}% | Sharpe 2020-22 / 2023-26 / %/yr:", sharpe(pd.Series(EQ_R, idx).groupby(day).sum()), flush=True)
        firm_sim(nm)
    for c in NAMES: COMP[c] = SAVE[c]
