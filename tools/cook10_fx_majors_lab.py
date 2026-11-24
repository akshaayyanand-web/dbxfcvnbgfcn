# FX majors lab (HistData 1-minute, EST no-DST -> UTC). Pre-registered 8 variants:
# F1 gotobi (3), F6 Asian quiet fade (2), F8 London 4pm fix reversal on GBPUSD/USDJPY (2), F13 cross-pair 24h reversal (1).
import glob, io, zipfile, pickle, numpy as np, pandas as pd
exec(open("newlab3.py").read().split('if __name__ == "__main__":')[0])
COST = {"USDJPY": 0.00007, "GBPUSD": 0.00009, "AUDUSD": 0.0001, "USDCAD": 0.0001, "USDCHF": 0.00012, "NZDUSD": 0.00014, "EURJPY": 0.0001, "GBPJPY": 0.00015, "EURGBP": 0.00012}
def load_hd(pair):
    parts = []
    for f in sorted(glob.glob(f"hd/raw/{pair}_*.zip")):
        try: z = zipfile.ZipFile(f)
        except zipfile.BadZipFile: continue
        nm = [n for n in z.namelist() if n.lower().endswith(".csv")]
        if not nm: continue
        d = pd.read_csv(io.BytesIO(z.read(nm[0])), sep=";", header=None, names=["t", "o", "h", "l", "c", "v"])
        parts.append(d)
    d = pd.concat(parts); d.index = pd.DatetimeIndex(pd.to_datetime(d.t, format="%Y%m%d %H%M%S")).tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT").tz_convert("UTC"); d = d[d.index.notna()]
    return d[["o", "h", "l", "c"]].astype(float).loc[lambda x: ~x.index.duplicated()].sort_index()
class FX(M1):
    def __init__(s, pair):
        s.name, s.cost = pair, COST[pair]; d = load_hd(pair); s.t = d.index; s.o, s.h, s.l, s.c = (d[k].to_numpy(float) for k in "ohlc")
        lr = np.diff(np.log(s.c), prepend=np.log(s.c[0])); lr[np.abs(lr) > 0.03] = 0
        s.sig = pd.Series(lr).rolling(20 * 1400, min_periods=5000).std().shift(1).to_numpy()
def gotobi_days(y0=2016, y1=2026):
    out = set()
    for y in range(y0, y1 + 1):
        for m in range(1, 13):
            last = (pd.Timestamp(y, m, 1) + pd.offsets.MonthEnd(0)).day
            for dd in (5, 10, 15, 20, 25, last):
                t = pd.Timestamp(y, m, min(dd, last))
                while t.weekday() >= 5: t -= pd.Timedelta(days=1)
                out.add(t.date())
    return out
def h_gotobi(m, mode):
    G = gotobi_days(); out = []
    for dte in sorted(set(m.t.tz_convert("Asia/Tokyo").date)):
        if pd.Timestamp(dte).weekday() >= 5: continue
        isg = dte in G
        if (mode in ("pre", "post")) != isg: continue
        t8 = pd.Timestamp(f"{dte} 08:00", tz="Asia/Tokyo").tz_convert("UTC"); tfix = pd.Timestamp(f"{dte} 09:55", tz="Asia/Tokyo").tz_convert("UTC")
        tr = trade(m, t8, tfix, +1) if mode in ("pre", "control") else trade(m, tfix, tfix + pd.Timedelta(hours=2), -1)
        if tr: out.append(tr)
    return out
def h_asia_fade(m, z=2.0):
    out = []
    for dte in sorted(set(m.t.date)):
        t0 = pd.Timestamp(f"{dte} 23:00", tz="UTC")
        if t0.weekday() not in (6, 0, 1, 2, 3): continue
        a = m.at(t0)
        if a is None or not np.isfinite(m.sig[a]): continue
        b = m.at(t0 + pd.Timedelta(minutes=90)); e = m.at(t0 + pd.Timedelta(hours=6, minutes=30))
        if b is None or e is None: continue
        p0 = m.o[a]; sg = m.sig[a]
        for k in range(b, e):
            zz = (m.c[k] - p0) / (p0 * sg * np.sqrt(k - a))
            if abs(zz) > z:
                d = -int(np.sign(zz)); ent = k + 1; ep = m.o[ent]; sd = 2.5 * sg * np.sqrt(e - ent) * ep; stop = ep - d * sd; x = None
                for q in range(ent, e):
                    if (d > 0 and m.l[q] <= stop) or (d < 0 and m.h[q] >= stop): x = stop; break
                    if (d > 0 and m.h[q] >= p0) or (d < 0 and m.l[q] <= p0): x = p0; break
                x = m.o[e] if x is None else x
                out.append((m.t[ent], m.t[min(q, e)], d * (x - ep) / sd - m.cost * ep / sd)); break
    return out
def h_xsec(M):
    inv = {"USDJPY": -1, "USDCAD": -1, "USDCHF": -1, "GBPUSD": 1, "AUDUSD": 1, "NZDUSD": 1}
    cl = pd.DataFrame({p: pd.Series(M[p].c, M[p].t).resample("1h").last() for p in inv}).ffill()
    out = []
    for t in cl.index[(cl.index.hour == 20) & (cl.index.weekday < 4)]:
        if t - pd.Timedelta(hours=24) not in cl.index: continue
        r = {p: inv[p] * np.log(cl.at[t, p] / cl.at[t - pd.Timedelta(hours=24), p]) for p in inv}
        if any(not np.isfinite(v) for v in r.values()): continue
        srt = sorted(r, key=r.get)
        for p, side in ((srt[0], 1), (srt[1], 1), (srt[-1], -1), (srt[-2], -1)):
            tr = trade(M[p], t, t + pd.Timedelta(hours=24), side * inv[p])
            if tr: out.append((tr[0], tr[1], tr[2] - 0.00002 * 0))
    out.sort(key=lambda x: x[0]); return out
if __name__ == "__main__":
    M = {p: FX(p) for p in ("USDJPY", "GBPUSD", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURGBP")}
    print("loaded", {p: (str(m.t[0].date()), str(m.t[-1].date()), len(m.t)) for p, m in M.items()}, flush=True)
    S = pd.Timestamp("2023-01-01", tz="UTC"); HYP = [
        ("F1 gotobi", "USDJPY", "long 08:00->09:55 JST on gotobi days", lambda: h_gotobi(M["USDJPY"], "pre")),
        ("F1 gotobi", "USDJPY", "short 09:55->11:55 JST on gotobi days (post-fix reversal)", lambda: h_gotobi(M["USDJPY"], "post")),
        ("F1 gotobi control", "USDJPY", "long 08:00->09:55 JST on NON-gotobi days", lambda: h_gotobi(M["USDJPY"], "control")),
        ("F6 Asian quiet fade", "EURGBP", "fade |z|>2 drift from 23:00 UTC, target session open, out 05:30", lambda: h_asia_fade(M["EURGBP"])),
        ("F6 Asian quiet fade", "USDCHF", "fade |z|>2 drift from 23:00 UTC, target session open, out 05:30", lambda: h_asia_fade(M["USDCHF"])),
        ("F8 4pm fix reversal", "GBPUSD", "fade 15:30->16:00 London move for 30m", lambda: h_fix_reversal(M["GBPUSD"], "Europe/London", 16, 0, 30, 30, False)),
        ("F8 4pm fix reversal", "USDJPY", "fade 15:30->16:00 London move for 30m", lambda: h_fix_reversal(M["USDJPY"], "Europe/London", 16, 0, 30, 30, False)),
        ("F13 cross-pair reversal", "6 USD pairs", "buy 2 weakest / sell 2 strongest vs USD over 24h, hold 24h", lambda: h_xsec(M))]
    rows, TR = [], {}
    for hyp, mk, var, fn in HYP:
        trs = [x for x in fn() if x]; TR[(hyp, mk, var)] = trs; rows.append(dict(hyp=hyp, market=mk, variant=var, **stats(trs, S))); print(rows[-1], flush=True)
    R = pd.DataFrame(rows); R.to_csv("fxlab_results.csv", index=False); pickle.dump(TR, open("fxlab_trades.pkl", "wb"))
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30); print(R.drop(columns=["hyp"]).to_string())
