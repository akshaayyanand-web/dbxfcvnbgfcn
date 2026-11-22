# $9 compounding test: 6 EAs that can trade at 0.01 lot, sized like the EAs (risk% of balance, floored to 0.01-lot steps, skip if below 0.01).
exec(open("human_profile.py").read().split("def select(")[0])
exec(open("newlab.py").read().split('\nif __name__ == "__main__":')[0].split("class Mkt")[0])
SIX = {"spxbo5": ("USA500IDXUSD", 0.0018, 1.0), "spx1h": ("USA500IDXUSD", 0.0036, 1.0), "spxfade": ("USA500IDXUSD", 0.0030, 1.0),
       "nqbo15": ("USATECHIDXUSD", 0.0018, 1.0), "oil1h": ("LIGHTCMDUSD", 0.0106, 100.0)}
PX = {s: load_duka(s).c for s in {"USA500IDXUSD", "USATECHIDXUSD", "LIGHTCMDUSD"}}
dax = pd.read_csv("eu1m/DEUIDXEUR_1m.csv", index_col=0); dax.index = pd.to_datetime(dax.index, utc=True); PX["DAX"] = dax.iloc[:, 3].resample("1h").last().dropna()
SIX["daxorb"] = ("DAX", 0.0027, 1.1)
TT = []
for et, xt, c, r, w, d in T:
    if c not in SIX: continue
    sym, sf, mult = SIX[c]; p = PX[sym].asof(et)
    if not np.isfinite(p): continue
    TT.append((et, xt, c, r, sf * p * 0.01 * mult))            # $ lost at the stop for 0.01 lot
TT.sort(key=lambda x: x[1])
print("min-lot $ risk at the stop (median):", pd.DataFrame(TT, columns=["et", "xt", "ea", "r", "mr"]).groupby("ea").mr.median().round(2).to_dict())
def run(start, riskpct):
    bal = 9.0; t1 = start + pd.Timedelta(days=365); peak = bal; mdd = 0
    for et, xt, c, r, mr in TT:
        if et < start or xt > t1: continue
        steps = np.floor(bal * riskpct / mr)
        if steps < 1: continue
        bal += steps * mr * r; peak = max(peak, bal); mdd = min(mdd, bal / peak - 1)
        if bal < 1.0: return 0.0, -1.0
    return bal, mdd
rows = []
starts = pd.date_range("2021-02-01", "2025-10-01", freq="MS", tz="UTC")
for rp in (0.02, 0.05, 0.10, 0.20):
    res = [run(s, rp) for s in starts]; fin = np.array([x[0] for x in res]); dd = np.array([x[1] for x in res])
    rows.append(dict(risk_per_trade=f"{rp:.0%}", reach_500pct=f"{100*np.mean(fin >= 54):.0f}%", end_up=f"{100*np.mean(fin > 9):.0f}%", bust=f"{100*np.mean(fin < 1):.0f}%",
                     median_after_1yr=f"${np.median(fin):.2f}", worst_10pct=f"${np.quantile(fin, .1):.2f}", best_10pct=f"${np.quantile(fin, .9):.2f}", median_max_drop=f"{100*np.median(dd):.0f}%"))
pd.set_option("display.width", 250); print(pd.DataFrame(rows).to_string(index=False))
mu = pd.DataFrame(TT, columns=["et", "xt", "ea", "r", "mr"]).groupby("ea").r.mean().to_dict()
TT = [(et, xt, c, r - 0.5 * mu[c], mr) for et, xt, c, r, mr in TT]
rows = []
for rp in (0.03, 0.05, 0.10):
    res = [run(s, rp) for s in starts]; fin = np.array([x[0] for x in res]); dd = np.array([x[1] for x in res])
    rows.append(dict(edge="HALF (realistic live)", risk_per_trade=f"{rp:.0%}", reach_500pct=f"{100*np.mean(fin >= 54):.0f}%", end_up=f"{100*np.mean(fin > 9):.0f}%", bust=f"{100*np.mean(fin < 1):.0f}%",
                     median_after_1yr=f"${np.median(fin):.2f}", median_max_drop=f"{100*np.median(dd):.0f}%"))
print(pd.DataFrame(rows).to_string(index=False))
