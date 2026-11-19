exec(open("combo10.py").read().split('if __name__ == "__main__":')[0])
FXT = pickle.load(open("fxlab_trades.pkl", "rb"))
got = [(pd.Timestamp(et), pd.Timestamp(xt), r) for et, xt, r in FXT[("F1 gotobi", "USDJPY", "long 08:00->09:55 JST on gotobi days")]]
add_components(["fomc"]); _u = comp_from_paths(load_new("fomc"), None, 1.0); COMP["fomc"] = [a * 0.003 for a in _u]
COMP["gotobi"] = intraday(got, 1.0)
tgt = np.median([PORT["21"][c] * pd.Series(COMP[c][0], idx).groupby(idx.normalize()).sum().loc["2020-09-01":"2022-12-31"].std() for c in NAMES])
sd = pd.Series(COMP["gotobi"][0], idx).groupby(idx.normalize()).sum().loc["2020-09-01":"2022-12-31"].std(); COMP["gotobi"] = [a * 0.003 for a in COMP["gotobi"]]
PORT["21"]["gotobi"] = 1.0; BASE["gotobi"] = 0.1; NAMES.append("gotobi")
base = [c for c in NAMES if c not in ("fomc", "gotobi", "gnight")]
for lab, nm in (("21 EAs", base), ("+ gotobi", base + ["gotobi"]), ("+ FOMC", base + ["fomc"]), ("+ both", base + ["gotobi", "fomc"])):
    print(lab, "Sharpe 2020-22 / 2023-26 / %/yr at x1:", daily_sharpe(nm), flush=True)
st = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
for lab, nm in (("+ gotobi 0.3%", base + ["gotobi"]), ("+ gotobi + FOMC 0.3%", base + ["gotobi", "fomc"])):
    table(two_step, nm, (5.0,), (3.0, 3.5), st, lab)
