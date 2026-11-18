"""Opening-range expansion (family 5) on 1-minute bars. Builds, per instrument and day, the first breakout of the opening range
and its outcome under each stop rule; formulations filter those trades. Output: daily per-instrument trade-return streams (net of costs)."""
import os, pickle, numpy as np, pandas as pd
from data import SCR, RDATA
INSTR = {  # name: (file, tz, open, end, cost bps round trip)
    "NQ": (f"{SCR}/fut1m/USATECHIDXUSD_1m.csv", "America/New_York", "09:30", "15:55", 3.0),
    "SPX": (f"{SCR}/fut1m/USA500IDXUSD_1m.csv", "America/New_York", "09:30", "15:55", 3.0),
    "GOLD": (f"{SCR}/fut1m/XAUUSD_1m.csv", "America/New_York", "08:20", "15:55", 4.0),
    "DAX": (f"{SCR}/eu1m/DEUIDXEUR_1m.csv", "Europe/Berlin", "09:00", "17:25", 3.0),
    "EURUSD": (f"{SCR}/fx1m/EURUSD_1m.csv", "Europe/London", "08:00", "16:00", 2.0),
}
def _bars(name):
    f, tz, *_ = INSTR[name]; d = pd.read_csv(f, parse_dates=["t"]).set_index("t"); d.index = d.index.tz_convert(tz); return d
def table(name, d=None):
    """one row per day and opening-range length M: range, breakout, outcomes (stop at far side / mid), overnight move, volume ratio"""
    f, tz, op, en, cost = INSTR.get(name, (None, "America/New_York", "09:30", "15:55", 4.0))
    d = _bars(name) if d is None else d
    m = d.index.hour * 60 + d.index.minute; o0 = int(op[:2]) * 60 + int(op[3:]); e0 = int(en[:2]) * 60 + int(en[3:])
    d = d[(m >= o0) & (m <= e0) & (d.index.dayofweek < 5)]; m = d.index.hour * 60 + d.index.minute
    closes = d.c.groupby(d.index.date).last()
    rows = []
    for day, g in d.groupby(d.index.date):
        mm = (g.index.hour * 60 + g.index.minute).values
        if len(g) < (e0 - o0) * 0.7: continue
        h, l, c, v = g.h.values, g.l.values, g.c.values, g.v.values
        for M in (15, 30):
            r = mm < o0 + M
            if r.sum() < M * 0.7: continue
            hi, lo = h[r].max(), l[r].min(); k0 = int(np.argmax(~r))
            ent = None
            for k in range(k0, len(c)):
                if c[k] > hi: ent = (k, 1); break
                if c[k] < lo: ent = (k, -1); break
            if ent is None: continue
            k, dr = ent; e = c[k]; out = {}
            for sname, st in (("far", lo if dr == 1 else hi), ("mid", (hi + lo) / 2)):
                res = None
                for j in range(k + 1, len(c)):
                    if (dr == 1 and l[j] <= st) or (dr == -1 and h[j] >= st): res = (st - e) * dr; break
                if res is None: res = (c[-1] - e) * dr
                out[sname] = res / e - cost / 1e4
            # execution-aware: limit order back at the range edge within 60 min of the signal, then same exits (far stop)
            edge = hi if dr == 1 else lo; fill = None
            for j in range(k + 1, min(len(c), k + 61)):
                if (dr == 1 and l[j] <= edge) or (dr == -1 and h[j] >= edge): fill = j; break
            lim = np.nan
            if fill is not None:
                st = lo if dr == 1 else hi; res = None
                for j in range(fill + 1, len(c)):
                    if (dr == 1 and l[j] <= st) or (dr == -1 and h[j] >= st): res = (st - edge) * dr; break
                if res is None: res = (c[-1] - edge) * dr
                lim = res / edge - cost * 0.6 / 1e4      # limit entry pays less spread
            vr = v[k] / max(1e-12, v[r].mean())
            rows.append(dict(day=pd.Timestamp(day), M=M, dir=dr, width=(hi - lo) / e, far=out["far"], mid=out["mid"], limit=lim, open=c[0], volratio=vr, minute=int(mm[k] - o0)))
    t = pd.DataFrame(rows)
    pc = closes.shift(1); pc.index = pd.to_datetime(pc.index); t["prevclose"] = t.day.map(pc)
    t["overnight"] = np.sign(t.open / t.prevclose - 1)
    dc = closes.copy(); dc.index = pd.to_datetime(dc.index)
    t["trend50"] = t.day.map(np.sign(dc - dc.rolling(50).mean()).shift(1))
    rng = (d.h.groupby(d.index.date).max() - d.l.groupby(d.index.date).min()) / dc.values
    rng.index = pd.to_datetime(rng.index); t["atr14"] = t.day.map(rng.rolling(14).mean().shift(1))
    return t
def spread_bars():
    a = _bars("NQ").c; b = _bars("SPX").c; j = pd.concat([a, b], axis=1, keys=["a", "b"]).dropna()
    s = np.exp(np.log(j.a) - np.log(j.b)) * 1000
    return pd.DataFrame({"o": s, "h": s, "l": s, "c": s, "v": 1.0})
def tables():
    p = f"{RDATA}/orb_tables.pkl"
    if os.path.exists(p): return pickle.load(open(p, "rb"))
    T = {n: table(n) for n in INSTR}
    T["NQ-SPX"] = table("NQ-SPX", spread_bars()); INSTR["NQ-SPX"] = (None, "America/New_York", "09:30", "15:55", 6.0)
    pickle.dump(T, open(p, "wb")); return T
if __name__ == "__main__":
    T = tables()
    for k, v in T.items(): print(k, len(v), v.day.min().date(), v.day.max().date(), "far mean bps", round(v[v.M == 15].far.mean() * 1e4, 2))
