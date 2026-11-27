import sys; sys.argv = ["x"]
import cat1000 as K, numpy as np, pandas as pd
d = K.hd("UKXGBP"); print(len(d), d.index[0], "->", d.index[-1]); print(d.c.resample("YE").last().round(0).to_dict())
lt = d.index.tz_convert("Europe/London"); hrs = pd.Series(1, index=lt).groupby(lt.hour).count(); print("bars by London hour:", (hrs / hrs.max()).round(2).to_dict())
dd = d.c.resample("1D").last().dropna(); print("days", len(dd), "| median 1m bars/day", int(pd.Series(1, d.index).groupby(d.index.date).count().median()))
r = np.log(dd).diff().dropna(); print("biggest daily moves %", (100 * r.abs().nlargest(5)).round(1).to_dict())
x = K.duka_h("USA500IDXUSD").c; s = d.c.resample("1h").last(); j = pd.concat([np.log(s).diff(), np.log(x).diff()], axis=1, join="inner").dropna(); j.columns = ["ftse", "spx"]
print("corr FTSE vs SPX hourly at lags:", {k: round(j.ftse.corr(j.spx.shift(-k)), 3) for k in (-1, 0, 1)})
