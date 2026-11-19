import numpy as np, pandas as pd
d = pd.read_csv("fut1m/XAUUSD_1m.csv", index_col=0); d.index = pd.to_datetime(d.index, utc=True); d.columns = ["o","h","l","c","v"][:len(d.columns)]
c = d.c; ldn = d.index.tz_convert("Europe/London"); summer = pd.Series(ldn.dst().total_seconds() > 0 if hasattr(ldn,'dst') else 0, index=d.index)
dst = pd.Series([x.utcoffset().total_seconds() > 0 for x in ldn[:1]], dtype=bool)
off = pd.Series(d.index.tz_convert("Europe/London").map(lambda x: x.utcoffset().total_seconds() > 0), index=d.index) if False else None
cost = 0.00012
rows = []
days = pd.Series(d.index.normalize().unique())
idxpos = pd.Series(np.arange(len(d)), index=d.index)
def px_at(ts):
    k = d.index.searchsorted(ts)
    return (c.iloc[k - 1], d.index[k]) if 0 < k < len(d) and (d.index[k] - ts) <= pd.Timedelta("10min") else (None, None)
for ent in ("22:00", "22:30", "23:00", "23:05", "23:15", "23:30", "00:00"):
    for ex in ("03:00",):
        rr = []
        for day in days:
            if day.weekday() not in (6, 0, 1, 2, 3): continue
            t_in = pd.Timestamp(f"{day.date()} {ent}", tz="UTC") if ent >= "12" else pd.Timestamp(f"{day.date()} {ent}", tz="UTC") + pd.Timedelta(days=1)
            t_out = pd.Timestamp(f"{day.date()} {ex}", tz="UTC") + pd.Timedelta(days=1)
            k_in = d.index.searchsorted(t_in); k_out = d.index.searchsorted(t_out)
            if k_in >= len(d) or k_out >= len(d) or d.index[k_in] - t_in > pd.Timedelta("10min") or d.index[k_out] - t_out > pd.Timedelta("10min"): continue
            e = d.o.iloc[k_in]; x = d.o.iloc[k_out]
            summer_ = pd.Timestamp(day).tz_convert("America/New_York").utcoffset().total_seconds() == -4 * 3600
            rr.append((day, summer_, x / e - 1 - cost))
        r = pd.DataFrame(rr, columns=["day", "summer", "ret"])
        for lab, sub in (("all", r), ("US summer time", r[r.summer]), ("US winter time", r[~r.summer])):
            v = sub.ret; rows.append(dict(entry_utc=ent, exit_utc=ex, season=lab, n=len(v), mean_bp=round(1e4 * v.mean(), 2), t=round(v.mean() / v.std() * np.sqrt(len(v)), 2),
                                          t_2019_22=round((lambda w: w.mean() / w.std() * np.sqrt(len(w)))(v[sub.day < "2023-01-01"]), 2), t_2023_26=round((lambda w: w.mean() / w.std() * np.sqrt(len(w)))(v[sub.day >= "2023-01-01"]), 2)))
print(pd.DataFrame(rows).to_string())
