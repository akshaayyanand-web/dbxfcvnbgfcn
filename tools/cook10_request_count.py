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


E = []
for c in NAMES:
    for et, xt, sf in POS.get(c, []):
        if pd.Timestamp(et) >= pd.Timestamp("2020-09-01", tz="UTC"): E.append((pd.Timestamp(et).normalize(), c))
E = pd.DataFrame(E, columns=["day", "ea"])
per = E.groupby(["day", "ea"]).size().unstack(fill_value=0)
alld = pd.date_range(E.day.min(), E.day.max(), freq="D"); per = per.reindex(alld, fill_value=0)
tot = per.sum(axis=1); wk = tot[tot.index.weekday < 5]
print(f"trades per day, ALL 21 EAs: average {wk.mean():.1f}, 99th pct {wk.quantile(.99):.0f}, max {tot.max()}")
print(f"server requests per day (open + close, no modifications): average {2*wk.mean():.0f}, max {2*tot.max()}")
m = per.max().sort_values(ascending=False)
print("max trades in one day by a single EA:", m.head(6).to_dict(), "| average per EA per trading day:", round(per.loc[per.index.weekday < 5].mean().mean(), 2))
