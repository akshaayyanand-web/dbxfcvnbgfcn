# Pairs / spread mean reversion, pre-registered (rules fixed before running):
#   spread = logA - beta*logB - alpha, beta/alpha/sd from a rolling OLS window W ending at the signal bar; z = resid / sd.
#   Enter at the NEXT bar's close when |z| > E (short the spread if z > E, long if z < -E). Beta, alpha, sd frozen at entry.
#   Exit at the first close where the frozen z crosses 0 (target), or moves 2 sd further against (stop), or after W/2 bars (time).
#   1R = 2 sd of the spread. Costs: spreadA + |beta|*spreadB per round trip, plus swap on (1+|beta|) notional per day held.
#   Grid: hourly W 240 / 720, daily W 60; E 2.0 / 2.5. 16 pairs across metals, indices, FX, oil, crypto.
import sys, numpy as np, pandas as pd
from multiprocessing import Pool
exec(open("smc.py").read().split("def run_symbol(")[0])
def duka(sym): d = pd.read_csv(f"fut/{sym}.csv", index_col=0); d.index = pd.to_datetime(d.index, utc=True); return d.c
LOAD = {"XAU": (lambda: duka("XAUUSD"), 0.00012, 0.04), "XAG": (lambda: duka("XAGUSD"), 0.0008, 0.04), "WTI": (lambda: duka("LIGHTCMDUSD"), 0.0003, 0.05),
        "SPX": (lambda: duka("USA500IDXUSD"), 0.00015, 0.05), "NQ": (lambda: duka("USATECHIDXUSD"), 0.00015, 0.05), "DOW": (lambda: duka("USA30IDXUSD"), 0.00015, 0.05),
        "RUT": (lambda: duka("USSC2000IDXUSD"), 0.0003, 0.05), "DAX": (lambda: m1_csv("eu1m/DEUIDXEUR_1m.csv").c, 0.00015, 0.05),
        "BTC": (lambda: crypto("BTC").c, 0.0006, 0.15), "ETH": (lambda: crypto("ETH").c, 0.001, 0.15), "SOL": (lambda: crypto("SOL").c, 0.0015, 0.15)}
for s in ("EURUSD",): LOAD[s] = (lambda s=s: m1_csv(f"fx1m/{s}_1m.csv").c, SRC[s][1], 0.02)
for s in ("GBPUSD", "AUDUSD", "NZDUSD", "USDCHF", "USDCAD", "EURJPY", "GBPJPY", "EURGBP"): LOAD[s] = (lambda s=s: hd(s).c, SRC.get(s, (None, 0.0001))[1], 0.02)
PAIRS = [("XAU", "XAG", "metals"), ("NQ", "SPX", "index"), ("SPX", "DOW", "index"), ("SPX", "RUT", "index"), ("NQ", "RUT", "index"), ("DAX", "SPX", "index"),
         ("EURUSD", "GBPUSD", "fx"), ("AUDUSD", "NZDUSD", "fx"), ("EURUSD", "USDCHF", "fx"), ("EURJPY", "GBPJPY", "fx"), ("EURGBP", "EURUSD", "fx"),
         ("USDCAD", "WTI", "fx/oil"), ("BTC", "ETH", "crypto"), ("ETH", "SOL", "crypto"), ("BTC", "SOL", "crypto"), ("XAU", "SPX", "cross")]
def hourly(sym): return LOAD[sym][0]().resample("1h").last().dropna()
def backtest(a, b, W, E, ca, cb, sa, sb, bar_days):
    la, lb = np.log(a), np.log(b)
    va, vb = la.rolling(W).var(), lb.rolling(W).var(); cov = la.rolling(W).cov(lb)
    beta = (cov / vb).to_numpy(); alpha = (la.rolling(W).mean() - beta * lb.rolling(W).mean()).to_numpy()
    sd = np.sqrt(np.maximum(va.to_numpy() - cov.to_numpy() ** 2 / vb.to_numpy(), 0)); LA, LB, T = la.to_numpy(), lb.to_numpy(), la.index
    out = []; k = W; n = len(LA)
    while k < n - 2:
        if not (np.isfinite(beta[k]) and sd[k] > 0): k += 1; continue
        z = (LA[k] - beta[k] * LB[k] - alpha[k]) / sd[k]
        if abs(z) <= E: k += 1; continue
        d = -np.sign(z); bt, al, s0 = beta[k], alpha[k], sd[k]; e = k + 1; se = LA[e] - bt * LB[e] - al
        x = None
        for j in range(e + 1, min(e + 1 + W // 2, n)):
            zj = (LA[j] - bt * LB[j] - al) / s0
            if d * zj >= 0 or d * zj <= -(E + 2): x = j; break
        x = x if x is not None else min(e + W // 2, n - 1)
        sx = LA[x] - bt * LB[x] - al; days = (x - e) * bar_days
        cost = ca + abs(bt) * cb + (sa + abs(bt) * sb) * days / 365
        out.append((T[e], d * (sx - se) / (2 * s0) - cost / (2 * s0), days, cost / (2 * s0))); k = x + 1
    return out
def run(p):
    A, B, cls = p
    try: a, b = hourly(A), hourly(B)
    except Exception as ex: print(A, B, "load fail", ex, flush=True); return []
    j = pd.concat([a, b], axis=1, join="inner").dropna(); j = j[(j > 0).all(axis=1)]; j.columns = ["a", "b"]
    dj = pd.concat([a.resample("1D").last(), b.resample("1D").last()], axis=1, sort=True).dropna(); dj = dj[(dj > 0).all(axis=1)]; dj.columns = ["a", "b"]
    (_, ca, sa), (_, cb, sb) = LOAD[A], LOAD[B]; res = []
    for tf, df, W, bd in (("1h", j, 240, 1 / 24), ("1h", j, 720, 1 / 24), ("1D", dj, 60, 1.4)):
        for E in (2.0, 2.5):
            for t, R, days, c in backtest(df.a, df.b, W, E, ca, cb, sa, sb, bd): res.append((f"{A}/{B}", cls, f"{tf} W{W} E{E}", t, R, days, c))
    print(f"{A}/{B}: {len(res)} trades, {j.index[0].date()} -> {j.index[-1].date()}", flush=True); return res
if __name__ == "__main__":
    with Pool(8) as pool: res = pool.map(run, PAIRS)
    D = pd.DataFrame([r for o in res for r in o], columns=["pair", "cls", "cfg", "t", "R", "days", "cR"]); D.to_pickle("pairs_trades.pkl")
    if "--mirror" in sys.argv: D["R"] = -D.R - 2 * D.cR; print("\nMIRROR = follow the spread breakout (stop at z=0, target 2 sd further), costs paid")
    S = pd.Timestamp("2023-01-01", tz="UTC")
    def summ(g):
        a, b = g[g.t < S].R, g[g.t >= S].R; tt = lambda v: round(v.mean() / v.std(ddof=1) * np.sqrt(len(v)), 2) if len(v) > 2 else np.nan
        yrs = g.groupby(g.t.dt.year).R.sum()
        return pd.Series(dict(trades=len(g), win=round(100 * (g.R > 0).mean()), avgR=round(g.R.mean(), 3), hold_d=round(g.days.mean(), 1), t_pre2023=tt(a), t_2023on=tt(b), pos_years=f"{(yrs > 0).sum()}/{len(yrs)}"))
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 400)
    print("\nBY CONFIG (all 16 pairs pooled):"); print(D.groupby("cfg").apply(summ).to_string())
    print("\nBY CLASS x CONFIG:"); print(D.groupby(["cls", "cfg"]).apply(summ).to_string())
    P = D.groupby(["pair", "cfg"]).apply(summ); print("\nBY PAIR x CONFIG:"); print(P.to_string())
    print("\npair/config with t>2 in BOTH periods:"); q = P[(P.t_pre2023 > 2) & (P.t_2023on > 2)]; print(q.to_string() if len(q) else "none")
