exec(open("combo10.py").read().split('\nif __name__ == "__main__":')[0])
build({c: PORT["21"][c] for c in NAMES})
d = pd.Series(EQ_R, idx).groupby(idx.normalize()).sum(); d = d[d.index.weekday < 5].loc["2020-09-01":]
r30 = d.rolling(30).sum()          # book return over next... use trailing 30 trading days
fwd = d[::-1].rolling(30).sum()[::-1].shift(-1)   # forward 30-day book return from each day
px = {s: load_duka(s).c for s in ("USA500IDXUSD", "XAUUSD", "LIGHTCMDUSD", "USATECHIDXUSD")} if False else None
exec(open("newlab.py").read().split('\nif __name__ == "__main__":')[0].split("class Mkt")[0])
F = pd.DataFrame(index=d.index)
for s, nm in (("USA500IDXUSD", "spx"), ("XAUUSD", "gold"), ("LIGHTCMDUSD", "oil")):
    c = load_duka(s).c.resample("1D").last().dropna(); c.index = c.index.normalize()
    lr = np.log(c).diff()
    F[nm + "_ret60"] = (c / c.shift(60) - 1).reindex(F.index, method="ffill")
    F[nm + "_vol20"] = (lr.rolling(20).std() * np.sqrt(252)).reindex(F.index, method="ffill")
    F[nm + "_trend"] = ((c / c.shift(60) - 1).abs() / (lr.rolling(60).std() * np.sqrt(60))).reindex(F.index, method="ffill")   # trend strength
b = load_crypto("BTC").c.resample("1D").last(); b.index = b.index.normalize()
F["btc_ret60"] = (b / b.shift(60) - 1).reindex(F.index, method="ffill"); F["btc_vol20"] = (np.log(b).diff().rolling(20).std() * np.sqrt(365)).reindex(F.index, method="ffill")
F["book_fwd30"] = fwd; F = F.dropna()
q = F.book_fwd30.quantile([.2, .8]); slow = F[F.book_fwd30 <= q.iloc[0]]; fast = F[F.book_fwd30 >= q.iloc[1]]
print("book forward-30-day return at x1: slowest 20% <=", round(100 * q.iloc[0], 1), "%  fastest 20% >=", round(100 * q.iloc[1], 1), "%")
print(pd.DataFrame({"slow (worst 20%)": slow.mean(), "all": F.mean(), "fast (best 20%)": fast.mean()}).round(3).to_string())
print("\ncorrelation of book forward-30d return with each condition:"); print(F.corr()["book_fwd30"].drop("book_fwd30").round(2).to_string())
yr = d.groupby(d.index.to_period("Q")).sum(); print("\nbook return by quarter at x1 (%):"); print((100 * yr).round(1).to_string())
