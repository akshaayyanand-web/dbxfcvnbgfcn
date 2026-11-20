# Peak margin used by the 21-EA book on FTMO Swing (FX 1:30, gold/indices/oil 1:10, crypto assumed 1:1) vs Standard (1:100 / 1:30 / crypto assumed 1:3).
exec(open("combo10.py").read().split('if __name__ == "__main__":')[0])
CRYPTO = {"btc", "btcgap", "sol", "solrev", "btcrev", "xrprev"}
POS = {}   # name -> list of (entry, exit, stop_fraction)
for c, k in MAP.items(): POS[c] = [(et, xt, abs(e - st) / e) for et, xt, e, st, px in TRL[k][0]]
POS["nqbo15"] = [(et, xt, abs(e - st) / e) for et, xt, e, st, px in simT(bq, wq & (Cq > bq.h.rolling(20).max().shift(1).to_numpy()) & (Cq > cq.ewm(span=200, adjust=False).mean().to_numpy()), wq & (Cq < bq.l.rolling(20).min().shift(1).to_numpy()) & (Cq < cq.ewm(span=200, adjust=False).mean().to_numpy()), aq, 10 ** 6, mq >= 950)]
POS["spxbo5"] = [(et, xt, abs(e - st) / e) for et, xt, e, st, px in simT(b5, w5 & (C5 > hi) & (C5 > e5), w5 & (C5 < lo5) & (C5 < e5), 2 * a5, 10 ** 6, m5 >= 950)]
POS["daxpm"] = [(et, xt, abs(e - st) / e) for et, xt, e, st, px in dtr]
EST = {"goldvwap": (AT["gold"], 0.004), "spxfade": (AT["spx_fade"], 0.003), "nikkei": (nk, 0.006), "nqfade": (MT["nqfade"], 0.004), "xrprev": (MT["xrprev"], 0.015),
       "solrev": (CT["solrev"], 0.015), "btcrev": (CT["btcrev"], 0.012)}
for c, (tr, sf) in EST.items(): POS[c] = [(et, xt, sf) for et, xt, r in tr]
src = open("altdip.py").read().split('\nif __name__')[0]; ns = {"__file__": "/tmp/claude-0/-home-user-dbxfcvnbgfcn/0ea82c59-9b45-5b6c-b663-efd40f90c87c/scratchpad/altdip.py"}; exec(src, ns)
b = ns["load_crypto"]("SOL"); atr = ns["atr14"](b)
POS["sol"] = [(et, xt, 2 * atr[b.index.searchsorted(et) - 1] / b.c.iloc[b.index.searchsorted(et) - 1]) for et, xt, r, path in ns["dip_trades"]("SOL")]
print({c: (len(v), round(float(np.median([x[2] for x in v])) * 100, 2)) for c, v in POS.items()}, flush=True)

ASSET = {"btc": "BTC", "btcgap": "BTC", "btcrev": "BTC", "sol": "SOL", "solrev": "SOL", "xrprev": "XRP", "gdip": "GOLD", "gasia": "GOLD", "gmom": "GOLD", "goldvwap": "GOLD",
         "nq2h": "NQ", "orb15": "NQ", "nqbo15": "NQ", "nqfade": "NQ", "spx1h": "SPX", "spxbo5": "SPX", "spxfade": "SPX", "daxorb": "DAX", "daxpm": "DAX", "oil1h": "OIL", "nikkei": "JPN"}

ents = []
LEAN = [c for c in NAMES if c not in {'btc','gdip','nq2h','spx1h','oil1h','sol'}]
for c in LEAN:
    for et, xt, sf in POS.get(c, []):
        t = pd.Timestamp(et)
        if t >= pd.Timestamp("2020-09-01", tz="UTC"): ents.append((t, pd.Timestamp(xt), c))
E = pd.DataFrame(ents, columns=["et", "xt", "ea"]).sort_values("et")
yrs = (E.et.max() - E.et.min()).days / 365.25
m = E.et.dt.floor("1min").value_counts()
print(f"trades/yr {len(E)/yrs:.0f} | per trading day {len(E)/yrs/260:.1f}")
print(f"entries sharing the same minute with another EA: {100*(E.et.dt.floor('1min').map(m) > 1).mean():.1f}% of trades; max EAs entering in one minute: {m.max()}")
same5 = E.et.dt.floor("5min").value_counts(); print(f"entries sharing the same 5 minutes: {100*(E.et.dt.floor('5min').map(same5) > 1).mean():.1f}%")
# concurrent open positions
ev = pd.concat([pd.Series(1, E.et), pd.Series(-1, E.xt)]).sort_index().cumsum()
print("open positions at once: median", int(ev.median()), "| 95th pct", int(ev.quantile(.95)), "| max", int(ev.max()))
# direction (EAs with entry/stop known)
L = S_ = 0
for c, k in MAP.items():
    if c not in LEAN: continue
    for et, xt, e, st, px in TRL[k][0]:
        if pd.Timestamp(et) < pd.Timestamp("2020-09-01", tz="UTC"): continue
        if e > st: L += 1
        else: S_ += 1
print(f"direction (10 core EAs): long {100*L/(L+S_):.0f}% / short {100*S_/(L+S_):.0f}%")
# correlated equity-index group risk
IDX = {"nq2h", "orb15", "nqbo15", "nqfade", "spx1h", "spxbo5", "spxfade", "daxorb", "daxpm", "nikkei"}
for sc in (3.0, 4.0, 5.0):
    g = np.zeros(len(idx)); tot = np.zeros(len(idx))
    for c in LEAN:
        risk = BASE[c] / 100 * min(PORT["21"][c] * sc, 1.0 / BASE[c])
        for et, xt, sf in POS.get(c, []):
            i0, i1 = idx.searchsorted(pd.Timestamp(et)), idx.searchsorted(pd.Timestamp(xt))
            if pd.Timestamp(et) >= idx[0] and i0 < len(idx):
                tot[i0:max(i1, i0 + 1)] += risk
                if c in IDX: g[i0:max(i1, i0 + 1)] += risk
    print(f"x{sc}: stock-index group open risk max {100*g.max():.1f}%, 99th pct {100*np.quantile(g, .99):.1f}% | all EAs open risk max {100*tot.max():.1f}%, 99th {100*np.quantile(tot, .99):.1f}%")
