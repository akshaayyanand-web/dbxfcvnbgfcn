# Classic "grid" martingale EA (add a double-size position every G x ATR against you, close the whole basket at
# T x ATR past the average price), on every hourly market we have, judged on a 10% max / 5% daily prop account.
import sys, numpy as np, pandas as pd, itertools
from multiprocessing import Pool
from backtest_ema_macd import load
from futures_lab import load_csv
S = sys.argv[1]
MK = {"Gold": ("fut/XAUUSD.csv", 0.0001), "Silver": ("fut/XAGUSD.csv", 0.00025), "Nasdaq": ("fut/USATECHIDXUSD.csv", 0.00012),
      "S&P 500": ("fut/USA500IDXUSD.csv", 0.0001), "Dow": ("fut/USA30IDXUSD.csv", 0.00012), "Russell": ("fut/USSC2000IDXUSD.csv", 0.0002),
      "Oil": ("fut/LIGHTCMDUSD.csv", 0.0003), "BTC": ("kh/BTCUSDT.csv", 0.0012), "ETH": ("kh/ETHUSDT.csv", 0.0012),
      "SOL": ("kh/SOLUSDT.csv", 0.0012), "XRP": ("kh/XRPUSDT.csv", 0.0012), "DOGE": ("kh/DOGEUSDT.csv", 0.0012)}
idx = pd.date_range(pd.Timestamp("2020-04-01", tz="UTC"), pd.Timestamp("2026-10-30", tz="UTC"), freq="1h")

def data(m):
    f, c = MK[m]; d = load(S + "/" + f) if f.startswith("kh") else load_csv(S + "/" + f)
    d = d.reindex(idx); live = d.c.notna().to_numpy(); d = d.ffill()
    tr = np.maximum(d.h - d.l, np.maximum((d.h - d.c.shift()).abs(), (d.l - d.c.shift()).abs()))
    return d.o.to_numpy(), d.h.to_numpy(), d.l.to_numpy(), d.c.to_numpy(), tr.ewm(alpha=1/24).mean().shift().to_numpy(), \
        d.c.ewm(span=200).mean().shift().to_numpy(), live, c

def grid(D, G, N, T, risk, trend, stop=True):
    """Hourly account return r and worst-of-hour return lo (fractions of the start balance)."""
    o, h, l, c, atr, ema, live, cost = D
    r, lo = np.zeros(len(o)), np.zeros(len(o)); pos = None
    for i in range(201, len(o)):
        if not live[i]: continue
        if pos is None and (np.isnan(atr[i]) or np.isnan(ema[i]) or atr[i] <= 0): continue
        if pos is None:
            d = (1 if c[i-1] > ema[i] else -1) if trend else 1
            e0, a0 = o[i], atr[i]; lv = [e0 - d * k * G * a0 for k in range(N)]; sz = [2.0 ** k for k in range(N)]
            sp = e0 - d * N * G * a0
            unit = risk / sum(s * abs(sp - p) / p for s, p in zip(sz, lv))
            pos = dict(d=d, lv=lv, sz=[s * unit for s in sz], n=1, sp=sp, a0=a0, u=0.0); r[i] -= pos["sz"][0] * cost
        d, P = pos["d"], pos
        adv = l[i] if d == 1 else h[i]; fav = h[i] if d == 1 else l[i]
        filled = 0
        while P["n"] < N and (adv - P["lv"][P["n"]]) * d <= 0:      # add the next double-size level
            k = P["n"]; r[i] -= P["sz"][k] * cost; P["n"] += 1; filled += 1
        held = list(zip(P["sz"][:P["n"]], P["lv"][:P["n"]]))
        mtm = lambda px: sum(s * d * (px - p) / p for s, p in held)
        hit_stop = (adv - P["sp"]) * d <= 0
        u0 = P["u"]
        lo[i] = r[i] + mtm(P["sp"] if hit_stop else adv) - u0
        avg = sum(s * p for s, p in held) / sum(s for s, _ in held); tp = avg + d * T * P["a0"]
        if hit_stop:
            r[i] += mtm(P["sp"]) - u0; pos = None; continue
        if not filled and (fav - tp) * d >= 0:
            r[i] += mtm(tp) - u0; pos = None; continue
        P["u"] = mtm(c[i]); r[i] += P["u"] - u0
    return r, lo

def run(r, lo, h0, target, maxl=0.10, daily=0.05):
    days = idx.floor("D"); eq = 0.0; day = None; halt = None
    for i in range(h0, len(r)):
        if days[i] != day: day = days[i]; dopen = eq
        if halt == day: continue
        if eq + lo[i] <= -maxl or eq + lo[i] <= dopen - daily: return "fail", i - h0, eq
        eq += r[i]
        if target and eq >= target: return "pass", i - h0, eq
        if dopen - eq >= 0.8 * daily: halt = day
        if eq <= -0.8 * maxl: return "stopped", i - h0, eq
    return "open", len(r) - h0, eq

def job(a):
    m, G, N, T, risk, trend, stop = a
    D = data(m); r, lo = grid(D, G, N, T, risk, trend, stop)
    est = pd.date_range("2020-06-01", "2025-09-01", freq="7D", tz="UTC"); res = []; tm = []
    for s in est:
        h0 = idx.searchsorted(s); x, i1, _ = run(r, lo, h0, 0.10)
        if x != "pass": res.append(x); continue
        y, i2, _ = run(r, lo, h0 + i1 + 1, 0.05); res.append(y)
        if y == "pass": tm.append((i1 + i2) / 24)
    s = pd.Series(r, index=idx).resample("YS").sum() * 100
    return dict(market=m, G=G, N=N, T=T, risk=risk, trend=trend, stop=stop, pass2=100 * np.mean([x == "pass" for x in res]),
                breach=100 * np.mean([x == "fail" for x in res]), halted=100 * np.mean([x == "stopped" for x in res]),
                days=np.median(tm) if tm else np.nan, yr_med=s.iloc[:-1].median(), yr_worst=s.iloc[:-1].min())

if __name__ == "__main__":
    jobs = [(m, G, N, T, risk, tr, True) for m in MK for G, N in ((1.0, 4), (2.0, 4), (1.5, 5)) for T in (1.0,) for risk in (0.03,) for tr in (False, True)]
    jobs += [(m, 1.0, 6, 1.0, 0.12, False, True) for m in MK]   # "no real stop": the basket stop is beyond the 10% limit, so a full loss = breach
    with Pool(4) as p: out = p.map(job, jobs)
    df = pd.DataFrame(out); pd.set_option("display.width", 250)
    print(df.round(1).to_string(index=False))
    df.to_pickle(S + "/grid_mg.pkl")
