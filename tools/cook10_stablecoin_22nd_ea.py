# STRAT-0826 (stablecoin supply acceleration -> long crypto) as a 22nd EA on The5ers High Stakes: BTC+ETH CFDs, hourly mark-to-market,
# entry cost + daily crypto swap (0 / 10 / 25 %/yr). Same 3x risk in evaluation and funded.
import sys
exec(open("firms.py").read().split('\nif __name__ == "__main__":')[0])
sys.path.insert(0, "/home/user/dbxfcvnbgfcn/research"); import crypto2
exec(open("newlab.py").read().split('\nif __name__ == "__main__":')[0].split("class Mkt")[0])
ST = crypto2.load()["stable"]; ST.index = ST.index.normalize()
lst = np.log(ST); sig = ((lst.diff(7) / 7) > (lst.diff(90) / 90)).astype(float).shift(1)          # known the next day
px = {s: load_crypto(s).c for s in ("BTC", "ETH")}; cost = {"BTC": 0.0006, "ETH": 0.001}
hr = pd.DataFrame({s: v.reindex(idx).ffill() for s, v in px.items()}); r = hr.pct_change().fillna(0)
pos_day = sig.reindex(idx.normalize(), method="ffill").fillna(0).to_numpy()                        # held all day d if signal for d is 1
def comp(swap_yr, f=1.0):
    R = np.zeros(len(idx))
    for s in ("BTC", "ETH"):
        w = 0.5 * pos_day; held = np.r_[0, w[:-1]]                                                 # position during hour i decided at hour i-1
        R += f * held * r[s].to_numpy()
        ch = np.abs(np.diff(np.r_[0, w])); R -= f * ch * cost[s] / 2                               # half the round trip at each change
        R -= f * held * swap_yr / (365 * 24)
    return [R, np.minimum(R, 0) * 1.5, np.zeros(len(idx))]
d0 = pd.Series(comp(0.0)[0], idx).groupby(idx.normalize()).sum()
tgt = np.median([PORT["21"][c] * pd.Series(COMP[c][0], idx).groupby(idx.normalize()).sum().loc["2020-09-01":"2022-12-31"].std() for c in NAMES])
F1 = tgt / d0.loc["2020-09-01":"2022-12-31"].std()
print(f"in-market share {100*pos_day[idx >= pd.Timestamp('2020-09-01', tz='UTC')].mean():.0f}% | notional when on at 1x sizing: {100*F1:.1f}% of equity", flush=True)
BASEN = list(NAMES)
def sharpe(nm):
    build({c: (PORT["21"][c] if c in nm else 0.0) for c in NAMES}); dd = pd.Series(EQ_R, idx).groupby(idx.normalize()).sum().loc["2020-09-01":]
    a, b = dd[:"2022-12-31"], dd["2023-01-01":]; s_ = lambda x: x.mean() / x.std() * np.sqrt(365)
    return round(s_(a), 2), round(s_(b), 2), round(100 * dd.sum() / 6.2, 1)
if __name__ == "__main__":
    st = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    for sw in (0.0, 0.10, 0.25):
        for mult in (1.0, 2.0):
            COMP["stable"] = comp(sw, F1 * mult); PORT["21"]["stable"] = 1.0; BASE["stable"] = 0.1
            if "stable" not in NAMES: NAMES.append("stable")
            only = pd.Series(COMP["stable"][0], idx).groupby(idx.normalize()).sum().loc["2020-09-01":]
            s_ = lambda x: round(x.mean() / x.std() * np.sqrt(365), 2)
            book22 = BASEN + ["stable"]
            print(dict(swap=f"{sw:.0%}/yr", size=f"{mult:g}x", EA_alone_sharpe_2020_22=s_(only[:"2022-12-31"]), EA_alone_sharpe_2023_26=s_(only["2023-01-01":]),
                       book21=sharpe(BASEN), book22=sharpe(book22)), flush=True)
            with Pool(os.cpu_count()) as p: d = pd.DataFrame(p.map(uf, [(h, 3.0, "The5ers High Stakes 2-Step") for h in st]), columns=["days", "tries", "i"])
            with Pool(os.cpu_count()) as p: g = pd.DataFrame(p.map(fund, [(h, 3.0, 3.0, "The5ers High Stakes 2-Step") for h in st]), columns=["o", "pct"])
            ok = g[g.o.notna()]
            print(dict(book="21 EAs + stablecoin", swap=f"{sw:.0%}/yr", size=f"{mult:g}x", first_try=round(100 * (d.tries == 1).mean()), median_days=d.days.median(), p75=d.days.quantile(.75),
                       funded_kept=round(100 * (ok.o == "kept").mean()), yr_median=round(100 * ok.pct.median(), 1), yr_p10=round(100 * ok.pct.quantile(.1), 1)), flush=True)
            if sw == 0.0 and mult == 1.0:
                saved = COMP.pop("stable"); NAMES.remove("stable")
                with Pool(os.cpu_count()) as p: d = pd.DataFrame(p.map(uf, [(h, 3.0, "The5ers High Stakes 2-Step") for h in st]), columns=["days", "tries", "i"])
                with Pool(os.cpu_count()) as p: g = pd.DataFrame(p.map(fund, [(h, 3.0, 3.0, "The5ers High Stakes 2-Step") for h in st]), columns=["o", "pct"])
                ok = g[g.o.notna()]
                print(dict(book="21 EAs only (baseline)", first_try=round(100 * (d.tries == 1).mean()), median_days=d.days.median(), p75=d.days.quantile(.75),
                           funded_kept=round(100 * (ok.o == "kept").mean()), yr_median=round(100 * ok.pct.median(), 1), yr_p10=round(100 * ok.pct.quantile(.1), 1)), flush=True)
                COMP["stable"] = saved; NAMES.append("stable")
