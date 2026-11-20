# Calm-day, flat-by-close intraday mean reversion (no overnight financing). Pre-registered:
# C1 lunchtime range reversion (SPX, NQ, DAX, XAU), C2 lunchtime VWAP reversion (SPX, NQ, DAX). Calm = 20d realized vol < trailing 120d median.
# Judged pooled per rule; same rule on NON-calm days reported as a control.
import pickle, numpy as np, pandas as pd
exec(open("newlab3.py").read().split('\nif __name__ == "__main__":')[0])
CFG = {  # tz, session open, morning-range end, lunch window end, flat time (minutes after local midnight)
    "SPX": ("America/New_York", 570, 690, 870, 930), "NQ": ("America/New_York", 570, 690, 870, 930),
    "DAX": ("Europe/Berlin", 540, 660, 840, 925), "XAU": ("Europe/London", 480, 660, 780, 900)}
def load_v(path):
    d = pd.read_csv(path, index_col=0); d.index = pd.to_datetime(d.index, utc=True); d = d[~d.index.duplicated()].sort_index()
    return d.iloc[:, 4].to_numpy(float) if d.shape[1] >= 5 else np.ones(len(d))
def calm_flags(m, tz):
    c = pd.Series(m.c, m.t).resample("1D").last().dropna(); r = np.log(c).diff()
    v20 = r.rolling(20).std(); calm = (v20 < v20.rolling(120, min_periods=60).median()).shift(1)
    return {k.date(): bool(x) for k, x in calm.dropna().items()}
def run(m, rule, vol=None):
    tz, o, r1, w1, fl = CFG[m.name]; loc = m.t.tz_convert(tz); mins = loc.hour * 60 + loc.minute
    calm = calm_flags(m, tz); out = {"calm": [], "notcalm": []}
    day = np.array(loc.date); starts = np.r_[0, np.flatnonzero(day[1:] != day[:-1]) + 1, len(day)]
    for a, b in zip(starts[:-1], starts[1:]):
        dte = day[a]
        if pd.Timestamp(dte).weekday() >= 5 or dte not in calm: continue
        mm = mins[a:b]; ix = np.arange(a, b)
        morn = ix[(mm >= o) & (mm < r1)]; lunch = ix[(mm >= r1) & (mm < w1)]; flat = ix[mm >= fl]
        if len(morn) < 60 or not len(lunch) or not len(flat): continue
        hi, lo = m.h[morn].max(), m.l[morn].min(); rng = hi - lo; mid = (hi + lo) / 2
        if rng <= 0: continue
        if rule == "C2":
            sess = ix[(mm >= o) & (mm < w1)]; tp = (m.h[sess] + m.l[sess] + m.c[sess]) / 3; vv = np.maximum(vol[sess], 1e-9)
            vwap = np.cumsum(tp * vv) / np.cumsum(vv); vmap = dict(zip(sess, vwap))
        trade_ = None
        for k in lunch:
            if rule == "C1":
                if m.c[k] > hi + 0.25 * rng: d, tgt, st = -1, mid, m.c[k] + rng
                elif m.c[k] < lo - 0.25 * rng: d, tgt, st = 1, mid, m.c[k] - rng
                else: continue
            else:
                vw = vmap[k]; dev = m.c[k] - vw; lim = 1.5 * m.sig[k] * np.sqrt(max(k - morn[0], 1)) * m.c[k] if np.isfinite(m.sig[k]) else np.inf
                if abs(dev) <= lim: continue
                d = -int(np.sign(dev)); tgt = vw; st = m.c[k] + np.sign(dev) * 1.5 * abs(dev)
            j = k + 1
            if j >= flat[0]: break
            e = m.o[j]; risk = abs(e - st)
            if risk <= 0 or (tgt - e) * d <= 0: break
            x = None
            for q in range(j, flat[0]):
                if (d > 0 and m.l[q] <= st) or (d < 0 and m.h[q] >= st): x = st if (m.o[q] - st) * d > 0 else m.o[q]; break
                if (d > 0 and m.h[q] >= tgt) or (d < 0 and m.l[q] <= tgt): x = tgt; break
            if x is None: x, q = m.o[flat[0]], flat[0]
            trade_ = (m.t[j], m.t[q], d * (x - e) / risk - m.cost * e / risk); break
        if trade_: out["calm" if calm[dte] else "notcalm"].append(trade_)
    return out
if __name__ == "__main__":
    P = {"XAU": "fut1m/XAUUSD_1m.csv", "SPX": "fut1m/USA500IDXUSD_1m.csv", "NQ": "fut1m/USATECHIDXUSD_1m.csv", "DAX": "eu1m/DEUIDXEUR_1m.csv"}
    C = {"XAU": 0.00012, "SPX": 0.00015, "NQ": 0.00015, "DAX": 0.00015}
    M = {k: M1(k, p, C[k]) for k, p in P.items()}; V = {k: load_v(p) for k, p in P.items()}
    S = pd.Timestamp("2023-01-01", tz="UTC"); rows = []; TR = {}; pooled = {}
    for rule, mks in (("C1", ("SPX", "NQ", "DAX", "XAU")), ("C2", ("SPX", "NQ", "DAX"))):
        for mk in mks:
            o = run(M[mk], rule, V[mk] if len(V[mk]) == len(M[mk].t) else np.ones(len(M[mk].t)))
            for k in ("calm", "notcalm"):
                TR[(rule, mk, k)] = o[k]; rows.append(dict(rule=rule, market=mk, days=k, **stats(o[k], S))); pooled.setdefault((rule, k), []).extend(o[k])
            print(rows[-2], flush=True)
    R = pd.DataFrame(rows); pd.set_option("display.width", 250); print(R.to_string())
    PO = pd.DataFrame([dict(rule=r, days=k, **stats(sorted(v, key=lambda x: x[0]), S)) for (r, k), v in pooled.items()])
    print("\nPOOLED (the actual test is the 'calm' row):\n" + PO.to_string())
    R.to_csv("calmlab_results.csv", index=False); PO.to_csv("calmlab_pooled.csv", index=False); pickle.dump(TR, open("calmlab_trades.pkl", "wb"))
