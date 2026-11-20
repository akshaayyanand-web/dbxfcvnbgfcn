# Trade-level rebuild of the 21-EA book to test execution limits for The5ers:
# total open-position cap, max 1 position per symbol, 60-120 s stagger after another EA's entry (charged as slippage), direction guardrail.
# Book P&L is booked at each trade's exit hour (same approximation for every variant, so comparisons are like-for-like).
import sys
exec(open("firms.py").read().split('\nif __name__ == "__main__":')[0])
exec(open("margin_check.py").read().split("def margin_series")[0].split('exec(open("combo10.py")')[1].split("\n", 1)[1])
def rr(e, st, px, cost): return (px - e) / abs(e - st) * np.sign(e - st) - cost * e / abs(e - st)
SYMB = {"btc": "BTC", "btcgap": "BTC", "btcrev": "BTC", "sol": "SOL", "solrev": "SOL", "xrprev": "XRP", "gdip": "XAU", "gasia": "XAU", "gmom": "XAU", "goldvwap": "XAU",
        "nq2h": "NQ", "orb15": "NQ", "nqbo15": "NQ", "nqfade": "NQ", "spx1h": "SPX", "spxbo5": "SPX", "spxfade": "SPX", "daxorb": "DAX", "daxpm": "DAX", "oil1h": "OIL", "nikkei": "JPN"}
LONGONLY = {"btc", "gdip", "nq2h", "spx1h", "oil1h", "sol"}
T = []   # (entry, exit, ea, r, w, direction)
for c, k in MAP.items():
    tr, cost = TRL[k][0], TRL[k][1]
    T += [(pd.Timestamp(et), pd.Timestamp(xt), c, rr(e, st, px, cost), BASE[c] / 100, 1 if e > st else -1) for et, xt, e, st, px in tr]
T += [(pd.Timestamp(et), pd.Timestamp(xt), "nqbo15", rr(e, st, px, 0.00012), BASE["nqbo15"] / 100, 1 if e > st else -1) for et, xt, e, st, px in simT(bq, wq & (Cq > bq.h.rolling(20).max().shift(1).to_numpy()) & (Cq > cq.ewm(span=200, adjust=False).mean().to_numpy()), wq & (Cq < bq.l.rolling(20).min().shift(1).to_numpy()) & (Cq < cq.ewm(span=200, adjust=False).mean().to_numpy()), aq, 10 ** 6, mq >= 950)]
T += [(pd.Timestamp(et), pd.Timestamp(xt), "spxbo5", rr(e, st, px, 0.0001), BASE["spxbo5"] / 100, 1 if e > st else -1) for et, xt, e, st, px in simT(b5, w5 & (C5 > hi) & (C5 > e5), w5 & (C5 < lo5) & (C5 < e5), 2 * a5, 10 ** 6, m5 >= 950)]
T += [(pd.Timestamp(et), pd.Timestamp(xt), "daxpm", rr(e, st, px, 0.0001), BASE["daxpm"] / 100, 1 if e > st else -1) for et, xt, e, st, px in dtr]
for c, (tr, w) in {"goldvwap": (AT["gold"], .002), "spxfade": (AT["spx_fade"], .0025), "nikkei": (nk, .001), "nqfade": (MT["nqfade"], .0025), "xrprev": (MT["xrprev"], .002),
                   "solrev": (CT["solrev"], .002), "btcrev": (CT["btcrev"], .002)}.items():
    T += [(pd.Timestamp(et), pd.Timestamp(xt), c, r, w, 0) for et, xt, r in tr]
T += [(et, xt, "sol", r, 0.003, 1) for et, xt, r, path in ns["dip_trades"]("SOL")]
T = sorted([x for x in T if x[0] >= idx[0]], key=lambda x: x[0])
def select(cap=None, per_symbol=None, stagger=0, slip=0.03, dirguard=False):
    kept, open_, last_entry, recent = [], [], None, []
    for et, xt, c, r, w, d in T:
        open_ = [o for o in open_ if o[1] > et]
        if cap and len(open_) >= cap: continue
        if per_symbol and sum(1 for o in open_ if o[2] == SYMB[c]) >= per_symbol: continue
        if dirguard and c in LONGONLY and len(recent) >= 30 and np.mean([x > 0 for x in recent[-50:]]) > 0.70: continue
        rr_ = r
        if stagger and last_entry is not None and (et - last_entry).total_seconds() < stagger: rr_ = r - slip; et = last_entry + pd.Timedelta(seconds=stagger)
        kept.append((et, xt, c, rr_, w)); open_.append((et, xt, SYMB[c])); last_entry = et
        if d: recent.append(d)
    return kept
def install(kept):
    for c in NAMES: COMP[c] = [np.zeros(len(idx)), np.zeros(len(idx)), np.zeros(len(idx))]
    for et, xt, c, r, w in kept:
        h = idx.searchsorted(xt)
        if h < len(idx): COMP[c][0][h] += w * r; COMP[c][1][h] += w * min(r, 0.0)
def stats_of(kept):
    E = pd.DataFrame(kept, columns=["et", "xt", "ea", "r", "w"]); E = E[E.et >= pd.Timestamp("2020-09-01", tz="UTC")]
    ev = pd.concat([pd.Series(1, E.et), pd.Series(-1, E.xt)]).sort_index().cumsum(); m = E.et.dt.floor("1min").value_counts()
    return dict(trades_per_yr=round(len(E) / 6.2), same_minute=f"{100*(E.et.dt.floor('1min').map(m) > 1).mean():.1f}%", open_typ=int(ev.median()), open_max=int(ev.max()))
VAR = {"A baseline (exit-hour booking)": dict(), "B max 1 per symbol": dict(per_symbol=1), "C cap 5 total + 1/symbol": dict(cap=5, per_symbol=1),
       "D cap 4 total + 1/symbol": dict(cap=4, per_symbol=1), "E cap 3 total + 1/symbol": dict(cap=3, per_symbol=1),
       "F = C + 90 s stagger (0.03R slip)": dict(cap=5, per_symbol=1, stagger=90), "G = F + direction guard 70%": dict(cap=5, per_symbol=1, stagger=90, dirguard=True)}
if __name__ == "__main__":
    st = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    for lab, kw in VAR.items():
        kept = select(**kw); install(kept); s = stats_of(kept)
        for x in (3.0, 4.0):
            with Pool(os.cpu_count()) as p: d = pd.DataFrame(p.map(uf, [(h, x, "The5ers High Stakes 2-Step") for h in st]), columns=["days", "tries", "i"])
            with Pool(os.cpu_count()) as p: g = pd.DataFrame(p.map(fund, [(h, x, x, "The5ers High Stakes 2-Step") for h in st]), columns=["o", "pct"])
            ok = g[g.o.notna()]
            print(dict(variant=lab, risk_x=x, **s, first_try=round(100 * (d.tries == 1).mean()), median_days=d.days.median(), funded_kept=round(100 * (ok.o == "kept").mean()),
                       yr_median=round(100 * ok.pct.median(), 1), yr_p10=round(100 * ok.pct.quantile(.1), 1)), flush=True)
