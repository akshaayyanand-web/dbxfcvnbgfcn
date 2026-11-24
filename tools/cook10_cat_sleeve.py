# Add the best catalogue survivor (CFD-0262, ETH M15 multi-day consolidation breakout, 2ATR stop / 3ATR trail) to the 21-EA book.
# Trade R booked 6h after entry (median hold inside the 50-bar cap), loss side also booked as intraday drawdown. Sized like the crypto sleeve test.
import sys
exec(open("firms.py").read().split('\nif __name__ == "__main__":')[0])
T = pd.read_pickle("cat1000/trades_ETH_M15.pkl"); key = [k for k in T if k[0] == "CFD-0262" and k[3] == "2ATR stop, 3ATR trail"][0]; et, rr = T[key]
et = pd.DatetimeIndex(et).tz_localize("UTC") if pd.DatetimeIndex(et).tz is None else pd.DatetimeIndex(et)
st = [idx.searchsorted(s) for s in pd.date_range("2023-01-01", "2025-06-30", freq="7D", tz="UTC")]
def sim(tag):
    with Pool(os.cpu_count()) as p: d = pd.DataFrame(p.map(uf, [(h, 3.0, "The5ers High Stakes 2-Step") for h in st]), columns=["days", "tries", "i"])
    with Pool(os.cpu_count()) as p: g = pd.DataFrame(p.map(fund, [(h, 3.0, 3.0, "The5ers High Stakes 2-Step") for h in st]), columns=["o", "pct"])
    ok = g[g.o.notna()]; print(dict(book=tag, median_days=d.days.median(), first_try=round(100 * (d.tries == 1).mean()), kept=round(100 * (ok.o == "kept").mean()),
                                    yr_median=round(100 * ok.pct.median(), 1), yr_p10=round(100 * ok.pct.quantile(.1), 1)), flush=True)
if __name__ == "__main__":
    print("trades", len(rr), "avg R", round(float(rr.mean()), 3))
    sim("21 EAs")
    for risk in (0.001, 0.002):
        R = np.zeros(len(idx)); Lw = np.zeros(len(idx)); h = idx.searchsorted(et + pd.Timedelta(hours=6)); ok = h < len(idx)
        np.add.at(R, h[ok], risk * rr[ok]); np.add.at(Lw, h[ok], risk * np.minimum(rr[ok], 0))
        COMP["cat0262"] = [R, Lw, np.zeros(len(idx))]; PORT["21"]["cat0262"] = 1.0; BASE["cat0262"] = 0.1
        if "cat0262" not in NAMES: NAMES.append("cat0262")
        sim(f"21 EAs + CFD-0262 at {risk*100:.1f}% (x3 in sim)")
        NAMES.remove("cat0262"); COMP.pop("cat0262")
    d0 = pd.Series(np.zeros(len(idx)), idx)
    build({c: PORT["21"][c] for c in NAMES}); book = pd.Series(EQ_R, idx).groupby(idx.normalize()).sum()
    h = idx.searchsorted(et + pd.Timedelta(hours=6)); ok = h < len(idx); s = pd.Series(0.0, idx); np.add.at(s.values, h[ok], rr[ok]); sd = s.groupby(idx.normalize()).sum()
    crypto_eas = [c for c in ("btc", "sol", "btcrev", "solrev", "xrprev", "btcgap") if c in NAMES]
    cr = sum(pd.Series(COMP[c][0], idx) for c in crypto_eas).groupby(idx.normalize()).sum()
    print("daily corr with 21-EA book:", round(book.corr(sd), 2), "| with the 6 crypto EAs:", round(cr.corr(sd), 2))
    yr = pd.Series(rr, et).groupby(et.year).agg(["count", "mean", "sum"]).round(3); print(yr.to_string())
