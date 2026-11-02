# Replica of the "Kavach Grid" description (source is paid / not public), M15:
#  entry  : fade |Z| >= zth (Z = (close - SMA n) / stdev n), basket opens at the next bar's open
#  gate   : no new basket if ANY of: variance ratio(4) > vr_th, ADX14 > adx_th, price outside the prior 20-day range
#  basket : plan frozen at start: levels every S x ATR14 against, size x mult per level, max N levels,
#           hard stop one spacing past the last level; size so the stop loses `risk` of the account;
#           take-profit = average + T x ATR / (levels filled)  (tightens toward break-even); cooldown after exit
#  account: 10% max / 5% daily (from the day's opening balance), daily halt at 80% of the daily limit,
#           monthly halt at -mhalt, conservative fills (adverse side of the bar first)
import sys, numpy as np, pandas as pd, itertools, os
from multiprocessing import Pool
S = sys.argv[1]
SRC = {"Gold": ("fut1m/XAUUSD_1m.csv", 0.0001), "Nasdaq": ("fut1m/USATECHIDXUSD_1m.csv", 0.00012),
       "BTC": ("k5old/BTCUSDT_all.csv", 0.0012), "EURUSD": ("fx1m/EURUSD_1m.csv", 0.00008), "AUDCAD": ("fx1m/AUDCAD_1m.csv", 0.0002)}

def m15(m):
    f, cost = SRC[m]; p = S + "/" + f
    if f.startswith("k5old"):
        d = pd.read_csv(p, header=None, usecols=[0, 1, 2, 3, 4], names=["t", "o", "h", "l", "c"])
        d["t"] = pd.to_datetime(d.t, unit="ms", utc=True); d = d.set_index("t")
    else:
        d = pd.read_csv(p, usecols=[0, 1, 2, 3, 4], index_col=0); d.index = pd.to_datetime(d.index, utc=True)
    d = d.resample("15min").agg(dict(o="first", h="max", l="min", c="last")).dropna()
    return d.loc["2019-02-01":], cost

def indicators(d, n):
    c, h, l = d.c, d.h, d.l
    z = (c - c.rolling(n).mean()) / c.rolling(n).std()
    tr = np.maximum(h - l, np.maximum((h - c.shift()).abs(), (l - c.shift()).abs()))
    atr = tr.ewm(alpha=1 / 14).mean()
    up, dn = h.diff(), -l.diff()
    pdm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), d.index).ewm(alpha=1 / 14).mean()
    ndm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), d.index).ewm(alpha=1 / 14).mean()
    pdi, ndi = 100 * pdm / atr, 100 * ndm / atr
    adx = (100 * (pdi - ndi).abs() / (pdi + ndi)).ewm(alpha=1 / 14).mean()
    r1 = np.log(c).diff(); r4 = np.log(c).diff(4)
    vr = r4.rolling(400).var() / (4 * r1.rolling(400).var())
    day = d.index.floor("D"); dh = d.h.groupby(day).max(); dl = d.l.groupby(day).min()
    hi20 = dh.rolling(20).max().shift(1).reindex(day).to_numpy(); lo20 = dl.rolling(20).min().shift(1).reindex(day).to_numpy()
    don = (c.to_numpy() > hi20) | (c.to_numpy() < lo20)
    return z.to_numpy(), atr.to_numpy(), adx.to_numpy(), vr.to_numpy(), don

def basket_series(d, cost, ind, zth, Sp, N, mult, T, risk, gate, cool, vr_th=1.1, adx_th=25):
    o, h, l, c = (d[k].to_numpy() for k in "ohlc"); z, atr, adx, vr, don = ind
    n = len(o); r, lo = np.zeros(n), np.zeros(n); pos = None; wait = 0; nb = 0; wins = 0
    for i in range(500, n):
        if pos is None:
            if wait > 0: wait -= 1; continue
            zz = z[i - 1]
            if np.isnan(zz) or abs(zz) < zth or np.isnan(atr[i - 1]): continue
            if gate and (vr[i - 1] > vr_th or adx[i - 1] > adx_th or don[i - 1] or np.isnan(vr[i - 1])): continue
            dr = -1 if zz > 0 else 1; e0, a0 = o[i], atr[i - 1]
            lv = [e0 - dr * k * Sp * a0 for k in range(N)]; sz = [mult ** k for k in range(N)]; sp = e0 - dr * N * Sp * a0
            unit = risk / sum(s * abs(sp - p) / p for s, p in zip(sz, lv))
            pos = dict(d=dr, lv=lv, sz=[s * unit for s in sz], k=1, sp=sp, a0=a0, u=0.0); r[i] -= pos["sz"][0] * cost; nb += 1
        P = pos; dr = P["d"]; adv = l[i] if dr == 1 else h[i]; fav = h[i] if dr == 1 else l[i]; filled = 0
        while P["k"] < N and (adv - P["lv"][P["k"]]) * dr <= 0:
            r[i] -= P["sz"][P["k"]] * cost; P["k"] += 1; filled += 1
        held = list(zip(P["sz"][:P["k"]], P["lv"][:P["k"]]))
        mtm = lambda px: sum(s * dr * (px - p) / p for s, p in held)
        hit = (adv - P["sp"]) * dr <= 0; u0 = P["u"]
        lo[i] = r[i] + mtm(P["sp"] if hit else adv) - u0
        avg = sum(s * p for s, p in held) / sum(s for s, _ in held); tp = avg + dr * T * P["a0"] / P["k"]
        if hit:
            r[i] += mtm(P["sp"]) - u0; pos = None; wait = cool; continue
        if not filled and (fav - tp) * dr >= 0:
            r[i] += mtm(tp) - u0; pos = None; wait = cool; wins += 1; continue
        P["u"] = mtm(c[i]); r[i] += P["u"] - u0
    return r, lo, nb, wins

def run(r, lo, days, months, h0, h1, target=None, maxl=0.10, daily=0.05, mhalt=0.06):
    eq = 0.0; day = mon = None; halt = mh = None
    for i in range(h0, h1):
        if days[i] != day: day = days[i]; dopen = eq
        if months[i] != mon: mon = months[i]; mopen = eq
        if halt == day or mh == mon: continue
        if eq + lo[i] <= -maxl or eq + lo[i] <= dopen - daily: return "fail", i - h0, eq
        eq += r[i]
        if target and eq >= target: return "pass", i - h0, eq
        if dopen - eq >= 0.8 * daily: halt = day
        if mopen - eq >= mhalt: mh = mon
        if eq <= -0.8 * maxl: return "stopped", i - h0, eq
    return "open", h1 - h0, eq

PARAMS = list(itertools.product([20, 50], [2.0], [1.0, 2.0], [3, 5], [1.5, 2.0], [1.0, 2.0], [True, False]))

def market_job(m):
    d, cost = m15(m); idx = d.index; days = idx.floor("D").to_numpy(); months = idx.to_period("M").astype(str).to_numpy()
    yrs = (idx[-1] - idx[0]).days / 365.25; cut = idx.searchsorted(pd.Timestamp("2023-01-01", tz="UTC"))
    inds = {n: indicators(d, n) for n in (20, 50)}; out = []
    starts = idx.searchsorted(pd.date_range(idx[600], idx[-1] - pd.Timedelta(days=120), freq="28D"))
    for n, zth, Sp, N, mult, T, gate in PARAMS:
        r, lo, nb, wins = basket_series(d, cost, inds[n], zth, Sp, N, mult, T, 0.02, gate, cool=4)
        eqc = np.cumsum(r); dd = np.max(np.maximum.accumulate(eqc) - eqc)
        nz = np.flatnonzero((r != 0) | (lo != 0)); rr, ll, dd_, mm_ = r[nz], lo[nz], days[nz], months[nz]   # flat bars change nothing
        res = []; tm = []
        for h0 in np.searchsorted(nz, starts):
            a, i1, _ = run(rr, ll, dd_, mm_, h0, len(rr), 0.10)
            if a != "pass": res.append(a); continue
            b, i2, _ = run(rr, ll, dd_, mm_, h0 + i1 + 1, len(rr), 0.05); res.append(b)
            if b == "pass": tm.append((idx[nz[min(h0 + i1 + 1 + i2, len(nz) - 1)]] - idx[nz[min(h0, len(nz) - 1)]]).days)
        out.append(dict(market=m, zlen=n, spacing=Sp, levels=N, mult=mult, tp=T, gate=gate, baskets_mo=nb / yrs / 12, win=100 * wins / max(nb, 1),
                        yr_train=100 * r[:cut].sum() / (cut / len(r) * yrs), yr_test=100 * r[cut:].sum() / ((1 - cut / len(r)) * yrs),
                        maxdd=100 * dd, pass2=100 * np.mean([x == "pass" for x in res]), breach=100 * np.mean([x == "fail" for x in res]),
                        days=np.median(tm) if tm else np.nan)); print(m, len(out), "/", len(PARAMS), flush=True)
    return out

if __name__ == "__main__":
    mk = [m for m in SRC if os.path.exists(S + "/" + SRC[m][0])]
    with Pool(min(4, len(mk))) as p: res = p.map(market_job, mk)
    df = pd.DataFrame([x for o in res for x in o]); df.to_pickle(S + f"/kavach_{'_'.join(mk)}.pkl")
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)
    for m, g in df.groupby("market"):
        print(f"\n=== {m}: gate on vs off (averages over all settings)"); print(g.groupby("gate")[["yr_train", "yr_test", "pass2", "breach", "win"]].mean().round(1).to_string())
        best = g.sort_values("yr_train", ascending=False).head(5)
        print(f"top 5 settings chosen on 2019-2022 (risk 2% of the account per basket worst case), then 2023-2026:"); print(best.round(1).to_string(index=False))
        print(f"settings with a profitable test period: {100*(g.yr_test>0).mean():.0f}% | median test year {g.yr_test.median():+.1f}%")
