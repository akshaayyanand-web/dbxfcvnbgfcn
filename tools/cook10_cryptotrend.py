# Crypto trend sleeve candidate: Supertrend(10,3) 4h and EMA9/21 4h (2 ATR stop) on BTC, ETH, SOL, XRP CFDs, with spread + crypto swap
# (10% or 20%/yr on the notional, both sides). Hourly mark-to-market components added to the 21-EA book; The5ers High Stakes at 3x.
import sys
exec(open("firms.py").read().split('\nif __name__ == "__main__":')[0])
exec(open("retail.py").read().split("\ndef run(")[0])
COSTC = {"BTC": 0.0006, "ETH": 0.001, "SOL": 0.0015, "XRP": 0.002}
def trades(sym, method):
    b5 = crypto(sym); hb = rs(b5, "4h"); O, H, L, C = (hb[c].to_numpy() for c in "ohlc"); T = hb.index; A10 = atr(H, L, C, 10); A14 = atr(H, L, C, 14)
    if method == "Supertrend":
        hl2 = (H + L) / 2; ub = hl2 + 3 * A10; lb = hl2 - 3 * A10; fub = ub.copy(); flb = lb.copy(); dirn = np.ones(len(C)); st = np.full(len(C), np.nan)
        for k in range(1, len(C)):
            if not np.isfinite(A10[k]): continue
            fub[k] = ub[k] if (not np.isfinite(fub[k - 1]) or ub[k] < fub[k - 1] or C[k - 1] > fub[k - 1]) else fub[k - 1]
            flb[k] = lb[k] if (not np.isfinite(flb[k - 1]) or lb[k] > flb[k - 1] or C[k - 1] < flb[k - 1]) else flb[k - 1]
            dirn[k] = 1 if C[k] > fub[k - 1] else (-1 if C[k] < flb[k - 1] else dirn[k - 1]); st[k] = flb[k] if dirn[k] > 0 else fub[k]
        fn = lambda k: ((int(dirn[k]) if dirn[k] != dirn[k - 1] else 0), st[k])
    else:
        e9 = pd.Series(C).ewm(span=9, adjust=False).mean().to_numpy(); e21 = pd.Series(C).ewm(span=21, adjust=False).mean().to_numpy()
        def fn(k):
            s = 1 if (e9[k] > e21[k] and e9[k - 1] <= e21[k - 1]) else (-1 if (e9[k] < e21[k] and e9[k - 1] >= e21[k - 1]) else 0)
            return s, (C[k] - s * 2 * A14[k]) if s else np.nan
    # re-run with exit times: same state machine, record (entry_time, exit_time, dir, entry, risk, exit)
    out = []; pos = 0
    for k in range(60, len(C) - 1):
        if pos and ((pos > 0 and L[k] <= stop) or (pos < 0 and H[k] >= stop)):
            out.append((T[ie], T[k], pos, e, r0, min(O[k], stop) if pos > 0 else max(O[k], stop))); pos = 0
        s, sl = fn(k)
        if s and s != pos:
            if pos: out.append((T[ie], T[k + 1], pos, e, r0, O[k + 1])); pos = 0
            e = O[k + 1]; stop = sl; r0 = abs(e - sl) if np.isfinite(sl) else 0
            if r0 > 3 * COSTC[sym] * e and (e - sl) * s > 0: pos = s; ie = k + 1
        elif pos and np.isfinite(sl): stop = max(stop, sl) if pos > 0 else min(stop, sl)
    return out, hb
def component(method, swap, risk=0.002):
    R = np.zeros(len(idx)); Lw = np.zeros(len(idx)); per_trade = []
    for sym in COSTC:
        tr, hb = trades(sym, method)
        px = crypto(sym).c.resample("1h").last().reindex(idx).ffill().to_numpy()
        for et, xt, d, e, r0, x in tr:
            a, b = idx.searchsorted(et), idx.searchsorted(xt)
            if a >= len(idx) or b <= a: continue
            days = (xt - et).total_seconds() / 86400; notional = e / r0
            costR = COSTC[sym] * notional + swap / 365 * days * notional
            prev = e
            for h in range(a, min(b, len(idx))):
                inc = d * (px[h] - prev) / r0; R[h] += risk * inc; Lw[h] += risk * min(inc, 0); prev = px[h]
            h = min(b, len(idx) - 1); last = d * (x - prev) / r0 - costR; R[h] += risk * last; Lw[h] += risk * min(last, 0)
            per_trade.append((et, d * (x - e) / r0 - costR))
    return [R, Lw, np.zeros(len(idx))], per_trade
if __name__ == "__main__":
    st = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]; base = list(NAMES)
    def sharpe(nm):
        build({c: (PORT["21"].get(c, 1.0) if c in nm else 0.0) for c in NAMES}); d = pd.Series(EQ_R, idx).groupby(idx.normalize()).sum().loc["2020-09-01":]
        s_ = lambda x: round(x.mean() / x.std() * np.sqrt(365), 2); return s_(d[:"2022-12-31"]), s_(d["2023-01-01":]), round(100 * d.sum() / 6.2, 1)
    print("21 EAs Sharpe 2020-22 / 2023-26 / %/yr x1:", sharpe(base), flush=True)
    with Pool(os.cpu_count()) as p: d = pd.DataFrame(p.map(uf, [(h, 3.0, "The5ers High Stakes 2-Step") for h in st]), columns=["days", "tries", "i"])
    with Pool(os.cpu_count()) as p: g = pd.DataFrame(p.map(fund, [(h, 3.0, 3.0, "The5ers High Stakes 2-Step") for h in st]), columns=["o", "pct"])
    ok = g[g.o.notna()]; print(dict(book="21 EAs", median_days=d.days.median(), first_try=round(100 * (d.tries == 1).mean()), yr_median=round(100 * ok.pct.median(), 1), yr_p10=round(100 * ok.pct.quantile(.1), 1)), flush=True)
    for method in ("Supertrend", "EMA"):
        for swap in (0.10, 0.20):
            comp, pt = component(method, swap); nm = f"ct_{method}"; COMP[nm] = comp; PORT["21"][nm] = 1.0; BASE[nm] = 0.1
            if nm not in NAMES: NAMES.append(nm)
            r = pd.Series([x[1] for x in pt], index=pd.DatetimeIndex([x[0] for x in pt])).sort_index()
            tt = lambda v: round(v.mean() / v.std(ddof=1) * np.sqrt(len(v)), 2)
            print(f"\n{method} 4h crypto, swap {swap:.0%}/yr: trades {len(r)}, avg R after swap {r.mean():.3f}, t 2020-22 {tt(r[:'2022-12-31'])}, t 2023-26 {tt(r['2023-01-01':])}", flush=True)
            book = base + [nm]; print("  book + sleeve Sharpe 2020-22 / 2023-26 / %/yr x1:", sharpe(book), flush=True)
            with Pool(os.cpu_count()) as p: d = pd.DataFrame(p.map(uf, [(h, 3.0, "The5ers High Stakes 2-Step") for h in st]), columns=["days", "tries", "i"])
            with Pool(os.cpu_count()) as p: g = pd.DataFrame(p.map(fund, [(h, 3.0, 3.0, "The5ers High Stakes 2-Step") for h in st]), columns=["o", "pct"])
            ok = g[g.o.notna()]
            print("  ", dict(book=f"21 EAs + crypto {method}", swap=f"{swap:.0%}", median_days=d.days.median(), first_try=round(100 * (d.tries == 1).mean()), kept=round(100 * (ok.o == "kept").mean()),
                             yr_median=round(100 * ok.pct.median(), 1), yr_p10=round(100 * ok.pct.quantile(.1), 1)), flush=True)
            NAMES.remove(nm); COMP.pop(nm)
