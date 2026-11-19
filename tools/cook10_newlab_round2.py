# Round 2 of the new-mechanism lab. Pre-registered: R2-A month-end rebalancing (3 idx x 2 thresholds), R2-B pre-holiday (2 idx),
# R2-F oil Asia drift (1), R2-D gold-night neighbour windows (robustness only, not selection).
import pickle, numpy as np, pandas as pd
from dateutil.easter import easter
exec(open("newlab.py").read().split('if __name__ == "__main__":')[0])

def cash_days(m):
    """Trading days (NY dates) with a 15:00 ET bar."""
    H = m.ny.hour; D = pd.Index(m.ny.date)
    return sorted(set(D[H == 15]))

def h_month_end(m, thr):
    H = m.ny.hour; D = np.array(m.ny.date); days = cash_days(m); out = []
    bymonth = {}
    for d in days: bymonth.setdefault((d.year, d.month), []).append(d)
    keys = sorted(bymonth)
    for k0, k1 in zip(keys[:-1], keys[1:]):
        prev, cur = bymonth[k0], bymonth[k1]
        if len(cur) < 6: continue
        t3, last = cur[-3], cur[-1]
        i_ref = np.where((D == prev[-1]) & (H == 15))[0]; i_in = np.where((D == t3) & (H == 15))[0]; i_out = np.where((D == last) & (H == 15))[0]
        if not (len(i_ref) and len(i_in) and len(i_out)): continue
        i_ref, i_in, i_out = i_ref[0], i_in[0], i_out[0] + 1
        mtd = m.o[i_in] / m.o[i_ref] - 1
        if abs(mtd) <= thr or i_out >= len(m.o): continue
        tr = trade(m, i_in, i_out, -int(np.sign(mtd)))
        if tr: out.append(tr)
    return out

def us_holidays(y0=2016, y1=2027):
    from pandas.tseries.holiday import USFederalHolidayCalendar
    h = set(USFederalHolidayCalendar().holidays(f"{y0}-01-01", f"{y1}-12-31").date)
    h -= {d for d in h if (d.month == 10) or (d.month == 11 and d.day < 20)}   # Columbus / Veterans day: markets open
    h |= {easter(y) - pd.Timedelta(days=2) for y in range(y0, y1 + 1)}       # Good Friday
    return h

def h_pre_holiday(m):
    H = m.ny.hour; D = np.array(m.ny.date); hol = us_holidays(); out = []
    for d in sorted(set(D[H == 10])):
        nxt = d + pd.Timedelta(days=1)
        while nxt.weekday() >= 5: nxt += pd.Timedelta(days=1)
        if nxt not in hol: continue
        i = np.where((D == d) & (H == 10))[0]; j = np.where((D == d) & (H == 15))[0]
        if len(i) and len(j):
            tr = trade(m, i[0], j[0] + 1, +1)
            if tr: out.append(tr)
    return out

def h_asia_window(m, h_in, h_out):
    out = []; H = m.t.hour; WD = m.t.weekday
    for i in np.where((H == h_in) & np.isin(WD, [6, 0, 1, 2, 3] if h_in >= 20 else [0, 1, 2, 3, 4]))[0]:
        j = next_bar(m, i, lambda j: H[j] == h_out, 12)
        if j: out.append(trade(m, i, j, +1))
    return out

if __name__ == "__main__":
    M = {s: Mkt(s, load_duka(s), c) for s, c in (("XAUUSD", 0.00012), ("LIGHTCMDUSD", 0.0003), ("USA500IDXUSD", 0.00015), ("USATECHIDXUSD", 0.00015), ("USA30IDXUSD", 0.00015))}
    S16 = pd.Timestamp("2022-01-01", tz="UTC"); HYP = []
    for s in ("USA500IDXUSD", "USATECHIDXUSD", "USA30IDXUSD"):
        for thr in (0.0, 0.02):
            HYP.append(("R2-A month-end rebalancing (fade month-to-date)", s, f"T-3 15:00 -> last day 16:00 ET, |MTD|>{thr:.0%}", lambda s=s, thr=thr: h_month_end(M[s], thr)))
    for s in ("USA500IDXUSD", "USATECHIDXUSD"):
        HYP.append(("R2-B pre-holiday drift", s, "long 10:00 -> 16:00 ET day before US holiday", lambda s=s: h_pre_holiday(M[s])))
    HYP.append(("R2-F oil Asia-session drift", "LIGHTCMDUSD", "long 23->03 UTC", lambda: h_asia_window(M["LIGHTCMDUSD"], 23, 3)))
    for a, b in ((22, 2), (23, 2), (23, 4), (0, 4), (1, 5)):
        HYP.append(("R2-D gold-night robustness (not for selection)", "XAUUSD", f"long {a:02d}->{b:02d} UTC", lambda a=a, b=b: h_asia_window(M["XAUUSD"], a, b)))
    rows, TR = [], {}
    for hyp, mk, var, fn in HYP:
        trs = [x for x in fn() if x]; TR[(hyp, mk, var)] = trs
        rows.append(dict(hyp=hyp, market=mk, variant=var, **stats(trs, S16)))
    R = pd.DataFrame(rows); R.to_csv("newlab2_results.csv", index=False); pickle.dump(TR, open("newlab2_trades.pkl", "wb"))
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30); print(R.drop(columns=["hyp"]).to_string())
