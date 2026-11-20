# Volatility-managed sizing of the 21-EA book (no new signals). Uses only past data (factor for day t from days < t).
#  "book": whole-book risk x clip(expanding-median(sigma20)/sigma20, 0.5, 2)
#  "per_ea": each EA's risk x clip(expanding-median(sigma60_c)/sigma60_c, 0.5, 2)
import sys
exec(open("fast10.py").read().split('\nif __name__ == "__main__":')[0])
ARG = ARGV[1] if len(ARGV) > 1 else "base"
DAY = idx.normalize(); UD = DAY.unique(); pos = UD.get_indexer(DAY)
def factor(daily, win):
    s = daily.rolling(win, min_periods=win // 2).std()
    f = (s.expanding(min_periods=60).median() / s).clip(0.5, 2.0).shift(1).fillna(1.0)
    return f.to_numpy()
ORIG = {c: [a.copy() for a in COMP[c]] for c in NAMES}
if ARG == "book":
    build({c: PORT["21"][c] for c in NAMES}); d = pd.Series(EQ_R, idx).groupby(DAY).sum().reindex(UD).fillna(0)
    fh = factor(d, 20)[pos]
    for c in NAMES: COMP[c] = [a * fh for a in ORIG[c]]
elif ARG == "per_ea":
    for c in NAMES:
        d = pd.Series(ORIG[c][0], idx).groupby(DAY).sum().reindex(UD).fillna(0); fh = factor(d, 60)[pos]
        COMP[c] = [a * fh for a in ORIG[c]]
build({c: PORT["21"][c] for c in NAMES}); d = pd.Series(EQ_R, idx).groupby(DAY).sum(); d = d[d.index.weekday < 5]
a, b = d[:"2022-12-31"], d["2023-01-01":]
print(ARG, "Sharpe 2020-22 / 2023-26:", round(a.mean() / a.std() * np.sqrt(252), 2), round(b.mean() / b.std() * np.sqrt(252), 2), "| %/yr x1:", round(100 * d.sum() / 6.58, 1),
      "| worst day x1:", round(100 * d.min(), 2), flush=True)
if __name__ == "__main__":
    base = list(NAMES); st = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    for es in (4.0, 5.0):
        with Pool(os.cpu_count()) as p: dd = pd.DataFrame(p.map(until_funded, [(h, es, base) for h in st]), columns=["days", "tries"])
        print(dict(sizing=ARG, eval_x=es, first_try=round(100 * (dd.tries == 1).mean()), median_days=dd.days.median(), p75=dd.days.quantile(.75),
                   within_30d=round(100 * (dd.days <= 30).mean()), within_45d=round(100 * (dd.days <= 45).mean())), flush=True)
    for fs in (3.0, 3.5):
        with Pool(os.cpu_count()) as p: dd = pd.DataFrame(p.map(two_step, [(h, 5.0, fs, base) for h in st]), columns=["ev", "days", "o", "pct"])
        ok = dd[dd.ev == "pass"]
        print(dict(sizing=ARG, funded_x=fs, kept=round(100 * (ok.o == "kept").mean()), yr_median=round(100 * ok.pct.median(), 1), yr_p10=round(100 * ok.pct.quantile(.1), 1)), flush=True)
