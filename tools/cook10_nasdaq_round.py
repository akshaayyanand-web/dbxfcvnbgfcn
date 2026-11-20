# Nasdaq round. Pre-registered: Q1 opening-gap fade (1m), Q2 opex-week long (1h), Q3 turnaround Tuesday (1h), Q4 VIX-spike reversal (1h),
# Q11 overnight-high/low sweep reversal (1m). Costs 0.015% round trip; multi-day holds pay 6%/yr financing.
import numpy as np, pandas as pd
exec(open("newlab.py").read().split('\nif __name__ == "__main__":')[0])
trade_h = trade
exec(open("newlab3.py").read().split('\nif __name__ == "__main__":')[0])
H1 = Mkt("NQ", load_duka("USATECHIDXUSD"), 0.00015); NYH = H1.ny; HH = NYH.hour; DH = np.array(NYH.date)
Q = M1("NQ", "fut1m/USATECHIDXUSD_1m.csv", 0.00015); NYM = Q.t.tz_convert("America/New_York"); MM = NYM.hour * 60 + NYM.minute; DM = np.array(NYM.date)
def bar_at(dte, hour):
    k = np.flatnonzero((DH == dte) & (HH == hour)); return k[0] if len(k) else None
def hold_fin(i, j, tr, nights):
    sd = 2.5 * H1.sig[i] * np.sqrt(j - i); return (tr[0], tr[1], tr[2] - 0.06 / 365 * nights / sd)
def q2():
    out = []
    for y in range(2016, 2027):
        for m in range(1, 13):
            fri = pd.Timestamp(y, m, 1) + pd.offsets.WeekOfMonth(week=2, weekday=4); mon = fri - pd.Timedelta(days=4)
            i, j = bar_at(mon.date(), 10), bar_at(fri.date(), 16) or bar_at(fri.date(), 15)
            if i is None or j is None or not np.isfinite(H1.sig[i]): continue
            tr = trade_h(H1, i, j, +1)
            if tr: out.append(hold_fin(i, j, tr, 4)[:3])
    return out
def q3():
    out = []
    for dte in sorted(set(DH)):
        if pd.Timestamp(dte).weekday() != 0: continue
        a, b = bar_at(dte, 10), bar_at(dte, 15)
        tue = (pd.Timestamp(dte) + pd.Timedelta(days=1)).date(); j = bar_at(tue, 15)
        if None in (a, b, j) or H1.o[b] / H1.o[a] - 1 > -0.01: continue
        tr = trade_h(H1, b, j, +1)
        if tr: out.append(hold_fin(b, j, tr, 1)[:3])
    return out
def q4():
    v = pd.read_csv("rdata/cboe/VIX.csv"); v.index = pd.to_datetime(v.DATE, format="%m/%d/%Y"); c = v.CLOSE
    sig = (c / c.shift(1) - 1 > 0.20) & (c > 20); out = []; busy = None
    for d0 in c.index[sig]:
        d1 = d0 + pd.offsets.BDay(1); d6 = d0 + pd.offsets.BDay(6)
        if busy is not None and d1 <= busy: continue
        i, j = bar_at(d1.date(), 10), bar_at(d6.date(), 15)
        if i is None or j is None or not np.isfinite(H1.sig[i]): continue
        tr = trade_h(H1, i, j, +1)
        if tr: out.append(hold_fin(i, j, tr, 7)[:3]); busy = d6
    return out
def day_slices():
    st = np.r_[0, np.flatnonzero(DM[1:] != DM[:-1]) + 1, len(DM)]; return list(zip(st[:-1], st[1:]))
def q1():
    out = []; prev_close = None
    for a, b in day_slices():
        dte = DM[a]; mm = MM[a:b]; ix = np.arange(a, b)
        if pd.Timestamp(dte).weekday() >= 5: continue
        op = ix[mm == 570]; cl = ix[(mm >= 955) & (mm < 960)]
        if prev_close is not None and len(op) and pd.Timestamp(dte).weekday() < 5:
            o = Q.o[op[0]]; gap = o / prev_close - 1; e_i = ix[mm == 575]; fl = ix[mm == 955]
            if abs(gap) > 0.005 and len(e_i) and len(fl):
                i = e_i[0]; e = Q.o[i]; d = -int(np.sign(gap)); tgt = prev_close; st = e - d * abs(gap) * prev_close
                if (tgt - e) * d > 0:
                    x = None
                    for q in range(i, fl[0]):
                        if (d > 0 and Q.l[q] <= st) or (d < 0 and Q.h[q] >= st): x = st; break
                        if (d > 0 and Q.h[q] >= tgt) or (d < 0 and Q.l[q] <= tgt): x = tgt; break
                    x = Q.o[fl[0]] if x is None else x; risk = abs(e - st)
                    out.append((Q.t[i], Q.t[min(q, fl[0])], d * (x - e) / risk - Q.cost * e / risk))
        pre = ix[mm < 960]
        prev_close = Q.c[pre[-1]] if len(pre) and mm[mm < 960].max() >= 955 else None
    return out
def q11():
    out = []; sl = day_slices()
    for k in range(1, len(sl)):
        a, b = sl[k]; pa, pb = sl[k - 1]; dte = DM[a]
        if pd.Timestamp(dte).weekday() >= 5: continue
        mm = MM[a:b]; ix = np.arange(a, b); pm = MM[pa:pb]; pix = np.arange(pa, pb)
        on = np.r_[pix[pm >= 1080], ix[mm < 570]]
        if len(on) < 300: continue
        onh, onl = Q.h[on].max(), Q.l[on].min(); mid = (onh + onl) / 2
        win = ix[(mm >= 570) & (mm < 630)]; fl = ix[mm == 955]
        if not len(win) or not len(fl): continue
        swept_hi = swept_lo = False; hi_run, lo_run = -np.inf, np.inf
        for q in win:
            hi_run, lo_run = max(hi_run, Q.h[q]), min(lo_run, Q.l[q])
            if Q.h[q] > onh * 1.001: swept_hi = True
            if Q.l[q] < onl * 0.999: swept_lo = True
            if MM[q] % 5 != 4: continue
            d = -1 if (swept_hi and Q.c[q] < onh) else (1 if (swept_lo and Q.c[q] > onl) else 0)
            if not d: continue
            i = q + 1; e = Q.o[i]; st = hi_run * 1.0002 if d < 0 else lo_run * 0.9998; tgt = mid
            if (tgt - e) * d <= 0 or (e - st) * d <= 0: break
            x = None
            for r in range(i, fl[0]):
                if (d > 0 and Q.l[r] <= st) or (d < 0 and Q.h[r] >= st): x = st; break
                if (d > 0 and Q.h[r] >= tgt) or (d < 0 and Q.l[r] <= tgt): x = tgt; break
            x = Q.o[fl[0]] if x is None else x; risk = abs(e - st)
            out.append((Q.t[i], Q.t[min(r, fl[0])], d * (x - e) / risk - Q.cost * e / risk)); break
    return out
if __name__ == "__main__":
    rows = []
    for nm, fn, sp in (("Q1 opening-gap fade >0.5% (1m)", q1, "2023-01-01"), ("Q2 opex-week long (1h)", q2, "2022-01-01"), ("Q3 turnaround Tuesday (1h)", q3, "2022-01-01"),
                       ("Q4 VIX-spike reversal, 5 days (1h)", q4, "2022-01-01"), ("Q11 overnight high/low sweep reversal (1m)", q11, "2023-01-01")):
        rows.append(dict(test=nm, split=sp, **stats(fn(), pd.Timestamp(sp, tz="UTC")))); print(rows[-1], flush=True)
    pd.set_option("display.width", 250); R = pd.DataFrame(rows); print(R.to_string()); R.to_csv("nqlab_results.csv", index=False)
