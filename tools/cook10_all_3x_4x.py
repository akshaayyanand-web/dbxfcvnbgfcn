# Everything at 3x vs 4x (same risk both stages): 21 EAs, + 4 sisters (0.15% each), + Noise Band NQ (0.2%), + BTC #448 (0.1%, real costs).
import sys
exec(open("csleeve_sim.py").read().split('\nif __name__ == "__main__":')[0])
rs_src = open("rules_speed.py").read(); exec(rs_src[rs_src.index("def phase("):rs_src.index('\nif __name__ == "__main__":')])
src = open("y2026_scale.py").read(); exec(src[src.index("LEVELS = "):src.index("def scale_run")]); exec(src[src.index("def scale_run"):src.index('\nif __name__ == "__main__":')])
def at_exit(D, rf, tcol="tx"):
    R = np.zeros(len(idx)); Lw = np.zeros(len(idx)); h = idx.searchsorted(pd.DatetimeIndex(D[tcol])); ok = h < len(idx)
    np.add.at(R, h[ok], rf * D.R.to_numpy()[ok]); np.add.at(Lw, h[ok], rf * np.minimum(D.R.to_numpy()[ok], 0)); return [R, Lw, np.zeros(len(idx))]
nb = pd.read_pickle("ql_trades.pkl")[("NoiseBand", "NQ", "k=1.0")].copy()
nb["tx"] = (pd.DatetimeIndex(nb.day).tz_localize("America/New_York") + pd.Timedelta(hours=15, minutes=30)).tz_convert("UTC")
EXTRA = {"sis_orb30": (lambda rf: at_exit(pd.read_pickle("sister_ORB_NQ_30.pkl"), rf), 0.0015), "sis_btc1h": (lambda rf: at_exit(pd.read_pickle("sister_DIP_BTC_1h.pkl"), rf), 0.0015),
         "sis_xau4h": (lambda rf: at_exit(pd.read_pickle("sister_DIP_XAU_4h.pkl"), rf), 0.0015), "sis_nq1h": (lambda rf: at_exit(pd.read_pickle("sister_DIP_NQ_1h.pkl"), rf), 0.0015),
         "noiseband": (lambda rf: at_exit(nb, rf), 0.002), "btc448": (lambda rf: comp(TR[("B", "real")], rf), 0.001)}
BASE_N = list(NAMES)
def book(names):
    for nm in [n for n in NAMES if n not in BASE_N]: NAMES.remove(nm); COMP.pop(nm, None)
    for nm in names: f, rf = EXTRA[nm]; COMP[nm] = f(rf); PORT["21"][nm] = 1.0; BASE[nm] = 0.1; NAMES.append(nm)
BOOKS = {"21 EAs": [], "21 + 4 sisters": ["sis_orb30", "sis_btc1h", "sis_xau4h", "sis_nq1h"], "21 + 4 sisters + Noise Band + BTC #448": list(EXTRA)}
if __name__ == "__main__":
    ALL = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]; HS = RULES["The5ers High Stakes (8%+5%, 5% daily, 10% static)"]
    h26 = idx.searchsorted(pd.Timestamp("2026-01-02", tz="UTC")); rows = []
    for bk, ex in BOOKS.items():
        book(ex)
        for X_ in (3.0, 4.0):
            build({c: min(PORT["21"].get(c, 1.0) * X_, 1.0 / BASE[c]) for c in NAMES}); arr = (EQ_R.copy(), EQ_L.copy(), D_FLT.copy())
            d = pd.Series(EQ_R, idx).groupby((idx + pd.Timedelta(hours=2)).normalize()).sum().loc["2020-09-01":]
            res = [attempt(arr, h, HS) for h in ALL]; tr = np.array([r[0] for r in res]); dys = np.array([r[1] for r in res])
            with Pool(os.cpu_count()) as p: g = pd.DataFrame(p.map(fund, [(h, X_, X_, "The5ers High Stakes 2-Step") for h in ALL]), columns=["o", "pct"])
            ok = g[g.o.notna()]

            # 2026 replay: when funded (recompute end index of the pass), then scaling plan at the same X
            t0 = h26; tries = 0; jj = None
            while tries < 12:
                tries += 1; a, i = phase(*arr, t0, 0.08, 0.05, 0.10, False, len(idx))
                if a == "pass":
                    b2, j = phase(*arr, i + 24, 0.05, 0.05, 0.10, False, len(idx))
                    if b2 == "pass": jj = j; break
                    if b2 == "open": break
                    t0 = j + 24; continue
                if a == "open": break
                t0 = i + 24
            if jj is not None:
                globals()["X"] = X_; st, log, paid, lv, eq = scale_run(jj + 48, len(idx) - 1); y26 = f"funded {idx[jj].date()} ({(jj-h26)/24:.0f} d), {st}, ${LEVELS[lv]:,} level, paid ${paid:,.0f} ({100*paid/10000:.0f}%)"
            else: y26 = "not funded by 31 Oct"
            rows.append(dict(book=bk, risk=f"{X_:.0f}x", first_try=round(100 * np.mean(tr == 1)), median_days=np.nanmedian(dys), within_30d=round(100 * np.mean(dys <= 30)),
                             funded_kept=round(100 * (ok.o == "kept").mean()), yr_median=round(100 * ok.pct.median(), 1), yr_bad10=round(100 * ok.pct.quantile(.1), 1),
                             worst_day_raw=round(100 * d.min(), 2), replay_2026=y26)); print(rows[-1], flush=True)
    R = pd.DataFrame(rows); R.to_csv("all4x.csv", index=False); pd.set_option("display.width", 260); pd.set_option("display.max_colwidth", 90); print(R.to_string(index=False))
