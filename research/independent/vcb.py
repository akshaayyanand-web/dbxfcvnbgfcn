"""INDEPENDENT re-implementation of STRAT-0053 (volatility-compression breakout, crypto) - written separately from engine.py/lib.py,
plain Python loops, own EWMA/percentile code, own data loaders (Binance spot, Coinbase USD, Bitstamp USD, Binance USD-M perps).
Rule (pre-registered in the catalogue run): for each coin, v_t = stdev of the last N daily returns; p_t = percentile of v_t within the trailing
252 days (>=126); squeeze if p_{t-1} < pct; enter long when close_t > max(close_{t-N..t-1}) during a squeeze, short when close_t < min(...);
hold H days (newest signal wins). Sizing: w = sign * min(0.15/vol_i, 3) / sqrt(#coins with data); portfolio scaled to 15% vol with a
120-day EWMA of realised P&L (lagged), max 5x, gross exposure <= 2x. Return = position_{t-1} x (r_t - cash_t); costs = |dw| x cost."""
import json, csv, math, os, glob, zipfile, io, sys
import numpy as np
SCR = "/tmp/claude-0/-home-user-dbxfcvnbgfcn/0ea82c59-9b45-5b6c-b663-efd40f90c87c/scratchpad"
COINS = ["BTC", "ETH", "ADA", "AVAX", "BCH", "DOGE", "DOT", "LINK", "LTC", "SOL", "XRP", "BNB", "TRX"]
def load_coinbase():
    out = {}
    for c in COINS:
        f = f"{SCR}/indep/cb/{c}.json"
        if not os.path.exists(f): continue
        rows = json.load(open(f)); d = {}
        for t, lo, hi, op, cl, v in rows: d[int(t) // 86400] = float(cl)
        out[c] = d
    return out
def load_bitstamp():
    out = {}
    for c in COINS:
        f = f"{SCR}/indep/bs/{c}USD.csv"
        if not os.path.exists(f): continue
        d = {}
        for row in csv.reader(open(f)):
            if not row or not row[0].isdigit(): continue
            ts = int(row[0]); ts = ts // 1000 if ts > 1e11 else ts; d[ts // 86400] = float(row[6])
        out[c] = d
    return out
def load_binance_spot():
    """daily close = last hourly close of each UTC day, read straight from the raw kline CSVs"""
    out = {}
    for c in COINS:
        f = f"{SCR}/kh/{c}USDT.csv"
        if not os.path.exists(f): continue
        d = {}
        for row in csv.reader(open(f)):
            t = int(row[0]); t = t // 1000 if t > 1e14 else t; d[t // 86_400_000] = float(row[4])
        out[c] = d
    return out
def load_binance_perp():
    out = {}
    for c in COINS:
        d = {}
        for f in sorted(glob.glob(f"{SCR}/cdata/um/{c}USDT-1d-*.zip")):
            with zipfile.ZipFile(f) as z: txt = z.read(z.namelist()[0]).decode()
            for row in csv.reader(io.StringIO(txt)):
                if not row or not row[0].isdigit(): continue
                t = int(row[0]); t = t // 1000 if t > 1e14 else t; d[t // 86_400_000] = float(row[4])
        if d: out[c] = d
    return out
def load_cash():
    """Fed funds effective rate (FRED DFF, % p.a.) -> per calendar day."""
    d = {}
    for row in csv.reader(open(f"{SCR}/rdata/fred/DFF.csv")):
        try: y, m, dd = map(int, row[0].split("-")); v = float(row[1])
        except Exception: continue
        import datetime as dt
        d[(dt.date(y, m, dd) - dt.date(1970, 1, 1)).days] = v / 100 / 365
    return d
def backtest(px, cash, N=20, H=5, pct=0.2, cost_bp=6.0, tv=0.15, start_day=None, end_day=None, long_only=False, extra_slip_bp=0.0, coins=None):
    coins = [c for c in (coins or list(px)) if c in px]
    days = sorted(set().union(*[px[c].keys() for c in coins]))
    if start_day: days = [d for d in days if d >= start_day - 400]
    if end_day: days = [d for d in days if d <= end_day]
    T = len(days); K = len(coins); P = np.full((T, K), np.nan)
    for j, c in enumerate(coins):
        for i, d in enumerate(days):
            if d in px[c]: P[i, j] = px[c][d]
    R = np.full((T, K), np.nan); R[1:] = P[1:] / P[:-1] - 1
    cash_d = np.array([cash.get(d, np.nan) for d in days]); last = 0.0
    for i in range(T):
        if math.isnan(cash_d[i]): cash_d[i] = last
        else: last = cash_d[i]
    sig = np.zeros((T, K)); vol = np.full((T, K), np.nan)
    for j in range(K):
        r = R[:, j]; v_hist = []; m = 0.0; var = 0.0; init = False; hold_left = 0; cur = 0.0
        for i in range(T):
            # EWMA vol (span 60) of daily returns, annualised with 365
            if not math.isnan(r[i]):
                a = 2 / 61
                if not init: m, var, init = r[i], 0.0, True
                else: dlt = r[i] - m; m += a * dlt; var = (1 - a) * (var + a * dlt * dlt)
                vol[i, j] = math.sqrt(var * 365) if var > 0 else np.nan
            # rolling N-day stdev of returns and its percentile in the trailing 252 values
            win = r[max(0, i - N + 1):i + 1]
            if i >= N and not np.isnan(win).any():
                v_hist.append(float(np.std(win, ddof=1)))
            else: v_hist.append(np.nan)
            prev_ok = i >= 1 and not math.isnan(v_hist[i - 1])
            squeeze = False
            if prev_ok:
                w = [x for x in v_hist[max(0, i - 252):i] if not math.isnan(x)]
                if len(w) >= 126:
                    x = v_hist[i - 1]; below = sum(1 for y in w if y < x); eq = sum(1 for y in w if y == x)
                    squeeze = (below + 0.5 * (eq + 1)) / len(w) < pct
            ev = 0
            if squeeze and i > N and not math.isnan(P[i, j]):
                past = P[i - N:i, j]
                if not np.isnan(past).any():
                    if P[i, j] > past.max(): ev = 1
                    elif P[i, j] < past.min(): ev = -1
            if ev != 0 and not (long_only and ev < 0): cur, hold_left = float(ev), H
            elif hold_left > 0: hold_left -= 1
            if hold_left == 0: cur = 0.0
            sig[i, j] = cur
    W = np.zeros((T, K))
    for i in range(T):
        n = sum(1 for j in range(K) if not math.isnan(P[i, j]))
        for j in range(K):
            if sig[i, j] != 0 and not math.isnan(vol[i, j]) and vol[i, j] > 0 and n > 0:
                W[i, j] = sig[i, j] * min(tv / vol[i, j], 3.0) / math.sqrt(n)
    # portfolio vol targeting on lagged realised P&L of the unscaled book
    raw = np.zeros(T)
    for i in range(1, T): raw[i] = sum(W[i - 1, j] * (R[i, j] - cash_d[i]) for j in range(K) if not math.isnan(R[i, j]))
    a = 2 / 121; m = 0.0; var = 0.0; scale = np.zeros(T)
    for i in range(1, T):
        rv = math.sqrt(var * 365) if i > 40 and var > 0 else float("nan")
        scale[i] = min(tv / rv, 5.0) if rv == rv and rv > 0 else 0.0     # uses P&L up to i-1
        dlt = raw[i] - m; m += a * dlt; var = (1 - a) * (var + a * dlt * dlt)
    Wf = W * scale[:, None]
    g = np.abs(Wf).sum(1); Wf = Wf * np.minimum(1, 2.0 / np.where(g > 0, g, 1))[:, None]
    pnl = np.zeros(T); turn = np.zeros(T)
    for i in range(1, T):
        pnl[i] = sum(Wf[i - 1, j] * (R[i, j] - cash_d[i]) for j in range(K) if not math.isnan(R[i, j]))
        dw = np.abs(Wf[i] - Wf[i - 1]).sum(); turn[i] = dw; pnl[i] -= dw * (cost_bp + extra_slip_bp) / 1e4
    if start_day:
        keep = [i for i, d in enumerate(days) if d >= start_day]; return [days[i] for i in keep], pnl[keep], Wf[keep], turn[keep], coins
    return days, pnl, Wf, turn, coins
def stats(pnl, ann=365):
    p = np.asarray(pnl); eq = np.cumprod(1 + p); yrs = len(p) / ann
    cagr = eq[-1] ** (1 / yrs) - 1 if eq[-1] > 0 else -1; dd = float((eq / np.maximum.accumulate(eq) - 1).min())
    sh = p.mean() / p.std() * math.sqrt(ann) if p.std() > 0 else 0
    return dict(cagr=round(cagr, 4), sharpe=round(sh, 3), maxdd=round(dd, 3), days=len(p))
