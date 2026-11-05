# Run from the scratchpad (needs calendar_lab.py there).
# News-reaction strategies: trade the first move after CPI / NFP (8:30 NY) and FOMC (14:00 NY), entering 5+ minutes after.
import sys, numpy as np, pandas as pd
sys.argv = ["x", "."]
exec(open("calendar_lab.py").read().split('if __name__')[0])
NY = "America/New_York"
fomc = [d for d in open("news/fomc_dates.txt").read().split() if d not in ("20191011", "20200331", "20200827", "20250822")]
FOMC = [pd.Timestamp(f"{d[:4]}-{d[4:6]}-{d[6:]} 14:00", tz=NY).tz_convert("UTC") for d in fomc]
m1 = pd.read_csv("fut1m/USATECHIDXUSD_1m.csv", usecols=[0, 5], index_col=0); m1.index = pd.to_datetime(m1.index, utc=True).tz_convert(NY)
mm = m1.index.hour * 60 + m1.index.minute; dte = m1.index.normalize()
v830 = m1.v[(mm >= 510) & (mm < 515)].groupby(dte[(mm >= 510) & (mm < 515)]).sum()
v820 = m1.v[(mm >= 500) & (mm < 505)].groupby(dte[(mm >= 500) & (mm < 505)]).sum()
ratio = (v830 / v820.reindex(v830.index)).replace([np.inf], np.nan).dropna()
nfp, cpi = [], []
for (y, mo), g in ratio.groupby([ratio.index.year, ratio.index.month]):
    early = g[(g.index.day <= 10)]; fri = early[early.index.weekday == 4]
    if len(fri) and fri.iloc[0] >= 3: nfp.append(fri.index[0])
    elif len(early): nfp.append(early.idxmax())
    mid = g[(g.index.day >= 9) & (g.index.day <= 16)]
    if len(mid): cpi.append(mid.idxmax())
DATA = [(d + pd.Timedelta(hours=8, minutes=30)).tz_convert("UTC") for d in nfp + cpi]
print(f"{len(FOMC)} FOMC, {len(nfp)} NFP, {len(cpi)} CPI", flush=True)
rows, TR = [], {}
for mk in ("nq", "spx", "gold"):
    c5 = B[mk].c; atr, _ = daily_atr(B[mk]); atrd = atr.reindex(c5.index.floor("D"), method="ffill"); atrd.index = c5.index
    for evname, EVS in (("CPI/NFP", DATA), ("FOMC", FOMC)):
        for delay in (5, 15, 30):
            for thr in (0.0, 0.1, 0.2):
                for mode in ("follow", "fade"):
                    for hold in ((60, 150, "close") if evname == "CPI/NFP" else (45, "close")):
                        ent = []
                        for ev in EVS:
                            t0 = ev - pd.Timedelta("5min"); t1 = ev + pd.Timedelta(minutes=delay - 5)
                            if t0 not in c5.index or t1 not in c5.index: continue
                            mv = c5[t1] / c5[t0] - 1; a = atrd[t1] / c5[t1]
                            if not np.isfinite(a) or abs(mv) < thr * a or mv == 0: continue
                            d = (1 if mv > 0 else -1) * (1 if mode == "follow" else -1)
                            et = ev + pd.Timedelta(minutes=delay)
                            xt = (ET(ev).normalize().replace(hour=15, minute=55).tz_convert("UTC") if hold == "close" else et + pd.Timedelta(minutes=hold))
                            ent.append((et, xt, d))
                        if len(ent) < 20: continue
                        for sa in (0.25, 0.5):
                            tr = window_trades(mk, ent, sa, swap=0); nm = f"{mk} {evname} {mode} +{delay}m thr{thr} hold{hold} stop{sa}"
                            if len(tr) < 20: continue
                            rows.append(stats(tr, MK[mk][1], nm) | dict(n=len(tr))); TR[nm] = (mk, tr)
df = pd.DataFrame(rows); df["minhalf"] = df[["yrA", "yrB"]].min(axis=1)
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 300)
print(f"{len(df)} versions; positive both halves: {(df.minhalf > 0).sum()}; >=3%/yr both halves: {(df.minhalf >= 3).sum()}")
print(df.sort_values("minhalf", ascending=False).head(30).round(2).to_string(index=False))
print("\nmedian by group:"); df["grp"] = df.edge.str.split(" +").str[:3].str.join(" "); print(df.groupby("grp")[["yrA", "yrB", "avgR"]].median().round(2).to_string())
pd.to_pickle((df, TR), "news_lab.pkl")
