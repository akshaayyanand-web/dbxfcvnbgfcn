# FTSE 100 (HistData UKXGBP 1-minute, 2016-2026). Pre-registered rules; London cash session 08:00-16:30; costs 0.015% round trip, swap 5%/yr.
#  QuantLab-style UK100 ideas:
#   MON  : Monday 09:00 London, price <= Friday 16:30 close * (1 - 0.3%) -> buy; stop 1 daily ATR(14); exit 16:25.
#   DROP3: after 3 down sessions in a row, buy the next 08:00 open; stop 1 daily ATR; exit that day's 16:25 (variant: hold 2 sessions).
#   PULL : session close > SMA200 and RSI(2) < 10 -> buy next 08:00 open; exit at the first close > SMA5 or after 5 sessions; stop 2 daily ATR.
#  Pack rule families on FTSE (functions from transfer.py / ql.py): ORB, BO15, DIP (H1), FADE, Noise Band k=1, Session Open Momentum.
#  Day-of-week: session returns by weekday, 2016-22 vs 2023-26.
import sys, numpy as np, pandas as pd
exec(open("transfer.py").read().split("JOBS = ")[0])
COST["UKX"] = 0.00015; SWAP["UKX"] = 0.05
_M = {}
def ukx1m():
    if "m" not in _M: _M["m"] = K.hd("UKXGBP")
    return _M["m"]
_old_m5 = m5
def m5(sym): return K.rs(ukx1m(), "5min") if sym == "UKX" else _old_m5(sym)
_old_h1 = h1
def h1(sym): return K.rs(ukx1m(), "1h") if sym == "UKX" else _old_h1(sym)
def sess_daily():
    d = ukx1m().copy(); d.index = d.index.tz_convert("Europe/London"); mn = d.index.hour * 60 + d.index.minute; d = d[(mn >= 480) & (mn < 990) & (d.index.dayofweek < 5)]
    g = d.groupby(d.index.normalize()); S = pd.DataFrame({"o": g.o.first(), "h": g.h.max(), "l": g.l.min(), "c": g.c.last()})
    pc = S.c.shift(1); tr = np.maximum(S.h - S.l, np.maximum(abs(S.h - pc), abs(S.l - pc))); S["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean().shift(1)
    return d, S
def walk_px(x, i0, d, e, stop, end_min):
    m = (x.index.hour * 60 + x.index.minute).to_numpy(); h, l, c, o = x.h.to_numpy(), x.l.to_numpy(), x.c.to_numpy(), x.o.to_numpy()
    for q in range(i0, len(c)):
        if (d > 0 and l[q] <= stop) or (d < 0 and h[q] >= stop): return min(o[q], stop) if d > 0 else max(o[q], stop)
        if m[q] >= end_min: return c[q]
    return c[-1]
def quantlab_ideas():
    d, S = sess_daily(); days = {k: v for k, v in d.groupby(d.index.normalize())}; keys = list(S.index); out = {"MON": [], "DROP3 1-day": [], "DROP3 2-day": [], "PULL": []}
    dn = (S.c < S.c.shift(1)); sma200, sma5 = S.c.rolling(200).mean(), S.c.rolling(5).mean()
    dl = S.c.diff(); up = dl.clip(lower=0).ewm(alpha=.5, adjust=False).mean(); dw = (-dl.clip(upper=0)).ewm(alpha=.5, adjust=False).mean(); rsi2 = 100 - 100 / (1 + up / dw.replace(0, np.nan))
    for i in range(201, len(keys) - 6):
        k = keys[i]; x = days[k]; a = S.atr.iloc[i]
        if not np.isfinite(a): continue
        if k.dayofweek == 0:
            m = x.index.hour * 60 + x.index.minute; j = np.where(m >= 540)[0]
            if len(j) and x.c.iloc[j[0]] <= S.c.iloc[i - 1] * (1 - 0.003):
                e = x.o.iloc[j[0] + 1] if j[0] + 1 < len(x) else None
                if e: xp = walk_px(x, j[0] + 1, 1, e, e - a, 985); out["MON"].append((k, (xp - e - COST["UKX"] * e) / a))
        if dn.iloc[i - 1] and dn.iloc[i - 2] and dn.iloc[i - 3]:
            e = x.o.iloc[0]; xp = walk_px(x, 0, 1, e, e - a, 985); out["DROP3 1-day"].append((k, (xp - e - COST["UKX"] * e) / a))
            x2 = pd.concat([x, days[keys[i + 1]]]); m2 = np.r_[(x.index.hour * 60 + x.index.minute).to_numpy(), 10000 + (days[keys[i + 1]].index.hour * 60 + days[keys[i + 1]].index.minute).to_numpy()]
            hh, ll, cc, oo = x2.h.to_numpy(), x2.l.to_numpy(), x2.c.to_numpy(), x2.o.to_numpy(); stop = e - a; xp = cc[-1]
            for q in range(len(cc)):
                if ll[q] <= stop: xp = min(oo[q], stop); break
                if m2[q] >= 10985: xp = cc[q]; break
            out["DROP3 2-day"].append((k, (xp - e - COST["UKX"] * e - SWAP["UKX"] / 365 * e) / a))
        if S.c.iloc[i - 1] > sma200.iloc[i - 1] and rsi2.iloc[i - 1] < 10:
            e = x.o.iloc[0]; stop = e - 2 * a; xp = None; held = 0
            for q in range(i, min(i + 5, len(keys))):
                y = days[keys[q]]
                if y.l.min() <= stop: xp = stop; held = q - i; break
                if y.c.iloc[-1] > sma5.iloc[q]: xp = y.c.iloc[-1]; held = q - i; break
            if xp is None: xp = days[keys[min(i + 4, len(keys) - 1)]].c.iloc[-1]; held = 4
            out["PULL"].append((k, (xp - e - COST["UKX"] * e - SWAP["UKX"] / 365 * 1.4 * held * e) / (2 * a)))
    return out
def tbl(name, tr):
    D = pd.DataFrame(tr, columns=["t", "R"])
    if len(D) < 20: return dict(system=name, trades=len(D))
    D["t"] = pd.to_datetime(D.t); D["t"] = D.t.dt.tz_localize(None) if D.t.dt.tz is not None else D.t
    A, B = D[D.t < "2023-01-01"].R, D[D.t >= "2023-01-01"].R; tt = lambda v: round(v.mean() / v.std(ddof=1) * np.sqrt(len(v)), 2) if len(v) > 2 else np.nan
    yrs = D.groupby(D.t.dt.year).R.sum(); span = max((D.t.max() - D.t.min()).days / 365, 1)
    r = dict(system=name, trades=len(D), per_yr=round(len(D) / span, 1), win=round(100 * (D.R > 0).mean()), pf=round(D.R[D.R > 0].sum() / max(-D.R[D.R < 0].sum(), 1e-9), 2),
             R_yr=round(D.R.sum() / span, 1), avgR_train=round(A.mean(), 3), t_train=tt(A), avgR_hold=round(B.mean(), 3), t_hold=tt(B), pos_years=f"{(yrs > 0).sum()}/{len(yrs)}")
    r["PASS"] = bool(r["t_train"] >= 2 and r["t_hold"] >= 1.5 and r["avgR_hold"] >= 0.05); return r
if __name__ == "__main__":
    rows = []; keep = {}
    for k, v in quantlab_ideas().items(): rows.append(tbl("QuantLab " + k, v)); keep[k] = v; print(rows[-1], flush=True)
    for nm, f in (("ORB 08:00", lambda: ORB("UKX", "LDN")), ("BO15 08:00", lambda: BO15("UKX", "LDN")), ("DIP H1", lambda: DIP("UKX")), ("FADE 08:00", lambda: FADE("UKX", "LDN"))):
        tr = f(); rows.append(tbl("Pack " + nm, tr)); keep[nm] = tr; print(rows[-1], flush=True)
    src = open("ql.py").read(); exec(src.split("def noise_band")[0].split("SRC = ")[0]); exec("def noise_band" + src.split("def noise_band")[1].split("if __name__")[0], globals())
    global SRC
    SRC = {"UKX": (None, "Europe/London", 480, 990)}
    def sessions(sym):
        d = ukx1m().copy(); d.index = d.index.tz_convert("Europe/London"); d = d[d.index.dayofweek < 5]; mn = d.index.hour * 60 + d.index.minute; d = d[(mn >= 480) & (mn < 990)]
        d["m"] = (d.index.hour * 60 + d.index.minute) - 480; d["v"] = 1.0; out = {}
        for day, x in d.groupby(d.index.normalize()):
            if len(x) > 0.8 * 510 and x.m.iloc[0] <= 2: out[day] = x
        return out, 510
    globals()["sessions"] = sessions; globals()["COST"] = 0.00015
    for nm, f in (("Noise Band k=1", lambda: noise_band(("UKX", 1.0))[3]), ("Noise Band k=2", lambda: noise_band(("UKX", 2.0))[3]),
                  ("Session Open Momentum 2x/6h", lambda: som(("UKX", 2.0, "6h"))[3]), ("Session Open Momentum 1x/close", lambda: som(("UKX", 1.0, "close"))[3])):
        tr = f(); rows.append(tbl(nm, tr)); keep[nm] = tr; print(rows[-1], flush=True)
    R = pd.DataFrame(rows); pd.set_option("display.width", 220); print(R.to_string(index=False)); R.to_csv("ftse.csv", index=False); pd.to_pickle(keep, "ftse_trades.pkl")
    d, S = sess_daily(); r = np.log(S.c / S.c.shift(1)).dropna(); dow = r.index.dayofweek
    print("\nFTSE session close-to-close return by weekday (bp):")
    for per, m in (("2016-22", r.index < "2023-01-01"), ("2023-26", r.index >= "2023-01-01")):
        g = r[m].groupby(dow[m]); print(per, {["Mon", "Tue", "Wed", "Thu", "Fri"][k]: f"{1e4*v.mean():+.1f} (t {v.mean()/v.std()*np.sqrt(len(v)):.1f})" for k, v in g})
