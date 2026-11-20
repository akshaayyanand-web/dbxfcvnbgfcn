exec(open("fast10.py").read().split('\nif __name__ == "__main__":')[0])
P = pickle.load(open("tsmom_sleeve.pkl", "rb"))
tot = pd.concat({s: p for s, (p, w) in P.items()}, axis=1, sort=True).fillna(0).sum(axis=1); tot.index = pd.DatetimeIndex(tot.index).tz_convert("UTC") if tot.index.tz else pd.DatetimeIndex(tot.index).tz_localize("UTC")
build({c: PORT["21"][c] for c in NAMES}); bd = pd.Series(EQ_R, idx).groupby(idx.normalize()).sum()
j = pd.concat([bd, tot], axis=1, keys=["book", "trend"], sort=True).dropna().loc["2020-09-01":]
fwd = j.book[::-1].rolling(30).sum()[::-1]; tf = j.trend[::-1].rolling(30).sum()[::-1]
slow = fwd <= fwd.quantile(.2)
scale = j.book.std() / j.trend.std()
print("daily corr book vs trend:", round(j.book.corr(j.trend), 2), "| trend 30d return (scaled to book vol) in book's slowest 20% of windows:",
      round(100 * (tf[slow] * scale).mean(), 2), "% vs all windows:", round(100 * (tf * scale).mean(), 2), "% | book in those windows:", round(100 * fwd[slow].mean(), 2), "%", flush=True)
R = np.zeros(len(idx)); h = idx.searchsorted(tot.index + pd.Timedelta(hours=20)); ok = h < len(idx)
np.add.at(R, h[ok], tot.to_numpy()[ok])
for k in (0.25, 0.5):
    COMP["trend"] = [R * scale * k, np.minimum(R * scale * k, 0) * 1.5, np.zeros(len(idx))]; PORT["21"]["trend"] = 1.0; BASE["trend"] = 0.1
    nm = [c for c in NAMES if c != "trend"] + ["trend"]
    if "trend" not in NAMES: NAMES.append("trend")
    build({c: PORT["21"][c] for c in NAMES}); d = pd.Series(EQ_R, idx).groupby(idx.normalize()).sum(); d = d[d.index.weekday < 5]
    print(f"trend at {k}x book vol: Sharpe 2020-22 {d[:'2022-12-31'].mean()/d[:'2022-12-31'].std()*np.sqrt(252):.2f} 2023-26 {d['2023-01-01':].mean()/d['2023-01-01':].std()*np.sqrt(252):.2f} %/yr x1 {100*d.sum()/6.58:.1f}", flush=True)
    st = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    with Pool(os.cpu_count()) as p: dd = pd.DataFrame(p.map(until_funded, [(hh, 5.0, nm) for hh in st]), columns=["days", "tries"])
    print(dict(trend_weight=k, eval_x=5.0, first_try=round(100 * (dd.tries == 1).mean()), median_days=dd.days.median(), p75=dd.days.quantile(.75), within_30d=round(100 * (dd.days <= 30).mean()), within_45d=round(100 * (dd.days <= 45).mean())), flush=True)
    with Pool(os.cpu_count()) as p: dd = pd.DataFrame(p.map(two_step, [(hh, 5.0, 3.0, nm) for hh in st]), columns=["ev", "days", "o", "pct"])
    ok_ = dd[dd.ev == "pass"]; print(dict(trend_weight=k, funded_x=3.0, kept=round(100 * (ok_.o == "kept").mean()), yr_median=round(100 * ok_.pct.median(), 1), yr_p10=round(100 * ok_.pct.quantile(.1), 1)), flush=True)
