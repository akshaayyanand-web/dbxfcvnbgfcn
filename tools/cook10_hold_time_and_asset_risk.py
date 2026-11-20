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
rows = []
for c in NAMES:
    v = POS.get(c, [])
    if not v: continue
    hold = np.array([(pd.Timestamp(xt) - pd.Timestamp(et)).total_seconds() / 60 for et, xt, sf in v])
    rows.append(dict(ea=c, trades=len(v), under_2min=f"{100*(hold < 2).mean():.1f}%", under_5min=f"{100*(hold < 5).mean():.1f}%", median_hold_min=round(float(np.median(hold)))))
pass
for sc in (3.0, 4.0, 5.0):
    A = {}
    for c in NAMES:
        risk = BASE[c] / 100 * min(PORT["21"][c] * sc, 1.0 / BASE[c]); a_ = A.setdefault(ASSET[c], np.zeros(len(idx)))
        for et, xt, sf in POS.get(c, []):
            i0, i1 = idx.searchsorted(pd.Timestamp(et)), idx.searchsorted(pd.Timestamp(xt))
            if pd.Timestamp(et) >= idx[0] and i0 < len(idx): a_[i0:max(i1, i0 + 1)] += risk
    print(f"risk x{sc}: max open risk per asset %:", {k: round(100 * v.max(), 2) for k, v in A.items()}, "| hours any asset > 3%:", f"{100*np.mean(np.max(np.vstack(list(A.values())), axis=0) > 0.03):.3f}%", "| > 2%:", f"{100*np.mean(np.max(np.vstack(list(A.values())), axis=0) > 0.02):.3f}%")
