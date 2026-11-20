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
def margin_series(scale, lev):
    M = np.zeros(len(idx))
    for c in NAMES:
        risk = BASE[c] / 100 * min(PORT["21"][c] * scale, 1.0 / BASE[c])
        L = lev["crypto"] if c in CRYPTO else lev["cfd"]
        for et, xt, sf in POS.get(c, []):
            if not sf or sf <= 0: continue
            a, z = idx.searchsorted(pd.Timestamp(et)), idx.searchsorted(pd.Timestamp(xt))
            if a < len(idx): M[a:max(z, a + 1)] += risk / sf / L
    return M
for acct_, lev in (("1:30 indices+gold, 1:3 crypto", dict(cfd=30, crypto=3)), ("1:100 indices+gold, 1:10 crypto", dict(cfd=100, crypto=10))):
    for sc in (5.0, 6.0, 8.0):
        m = margin_series(sc, lev); m = m[idx >= pd.Timestamp("2020-09-01", tz="UTC")]
        print(dict(account=acct_, risk_x=sc, margin_median=f"{100*np.median(m[m>0]):.0f}%", margin_p99=f"{100*np.quantile(m, .99):.0f}%", margin_max=f"{100*m.max():.0f}%",
                   hours_over_80pct=f"{100*(m > 0.8).mean():.2f}%", hours_over_100pct=f"{100*(m > 1.0).mean():.2f}%"), flush=True)
