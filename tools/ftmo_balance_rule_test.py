# FTMO daily floor = midnight balance - 5% of start; compares brake on balance vs equity. Run from the scratchpad (needs breach_anatomy.py chain, ea_trades.pkl).
# Daily-loss floor from the midnight BALANCE (closed trades) vs from EQUITY, for the 12 EAs at 1.0x-1.5x risk.
import sys, numpy as np, pandas as pd
exec(open('breach_anatomy.py').read().split("exec(\"def attempt2\"")[0])
TRL = pd.read_pickle("ea_trades.pkl")
W = {"BTC_Dip_v3": 0.75, "Gold_Dip": 0.625, "Gold_Asia_Breakout": 0.3125, "Gold_Intraday_Momentum": 0.3125, "NQ_Opening_Range": 0.625, "NQ_Dip_2h": 0.3125,
     "SPX_Dip_1h": 0.3125, "Oil_Dip_1h": 0.1875, "BTC_Weekend_Gap": 0.25, "DAX_Opening_Range": 0.2}
real = np.zeros(len(idx))
def book(tr, cost, w):
    for et, xt, e, st, px in tr:
        h = idx.searchsorted(xt)
        if h < len(idx) and xt >= idx[0]: real[min(h, len(idx) - 1)] += w / 100 * ((px - e) / abs(e - st) * np.sign(e - st) - cost * e / abs(e - st))
for k, w in W.items(): book(TRL[k][0], TRL[k][1], w)
bq = bars1("fut1m/USATECHIDXUSD_1m.csv", "15min"); cq = bq.c; Cq = cq.to_numpy()
aq = rma(pd.concat([bq.h - bq.l, (bq.h - cq.shift()).abs(), (bq.l - cq.shift()).abs()], axis=1).max(axis=1), 14).to_numpy()
nyq = bq.index.tz_convert("America/New_York"); mq = nyq.hour * 60 + nyq.minute; wq = (mq >= 570) & (mq < 720)
book(simT(bq, wq & (Cq > bq.h.rolling(20).max().shift(1).to_numpy()) & (Cq > cq.ewm(span=200, adjust=False).mean().to_numpy()), wq & (Cq < bq.l.rolling(20).min().shift(1).to_numpy()) & (Cq < cq.ewm(span=200, adjust=False).mean().to_numpy()), aq, 10 ** 6, mq >= 950), 0.00012, 0.2)
book(simT(b5, w5 & (C5 > hi) & (C5 > e5), w5 & (C5 < lo5) & (C5 < e5), 2 * a5, 10 ** 6, m5 >= 950), 0.0001, 0.1)
EQ_R, EQ_L = R, Lw
print(f"check: total of booked trades {100 * real.sum():.1f}% vs hourly mark-to-market total {100 * EQ_R.sum():.1f}%", flush=True)
CFG = (0.07, 0.905, (0.04, 0.02))
FLT = np.cumsum(EQ_R) - np.cumsum(real)          # open (floating) P&L of all positions, 1x units
def attempt(h0, target, m, base, tickguard=False, G=0.04, slip=0.003, brake="balance"):
    """FTMO 2-step. base='equity': daily floor from the day-start equity (old, stricter model).
    base='balance': floor = midnight closed balance - 5% (FTMO's rule); open profit carried past midnight does not raise it."""
    Z, sl, half = CFG; eq = 1.0; day = -1; hd = -1; halfmode = False
    for i in range(h0, len(EQ_R)):
        if DAYN[i] != day:
            day = DAYN[i]
            bal = eq - m * (FLT[i] - FLT[h0])                      # equity minus open P&L built since the start
            ref = eq if base == "equity" else bal
            g = eq if (base == "equity" or brake == "equity") else bal   # what the drawdown brake (room cap / half size) looks at
            if g <= 1 - half[0]: halfmode = True
            elif g >= 1 - half[1]: halfmode = False
            mm = m * max(0.0, min(1.0, (g - 0.90) / Z)) * (0.5 if halfmode else 1.0)
        if hd == day or (EQ_R[i] == 0 and EQ_L[i] == 0): continue
        x = eq * (1 + mm * EQ_L[i])
        if tickguard and x <= ref - G and not hd == day:
            # the EA guard checks every tick: it closes everything at the -4% line (0.3% slippage) and stops for the day
            eq = ref - G - slip; hd = day                      # closed at the guard line the moment it is touched
            if eq <= 0.90: return "breach", i
            if eq <= sl: return "stopped", i
            continue
        if x <= 0.90 or x <= ref - 0.05: return "breach", i
        eq *= 1 + mm * EQ_R[i]
        if eq >= 1 + target: return "pass", i
        if ref - eq >= G: hd = day
        if eq <= sl: return "stopped", i
    return "open", len(EQ_R) - 1
def ev(args):
    m, base, tg, G, br = args; out = {"risk": f"x{m}", "guard at": f"-{G:.1%}", "brake uses": br}
    for lab, a, z in (("2020-22", "2020-04-01", "2022-12-31"), ("2023-25", "2023-01-01", "2025-09-01"), ("2026", "2026-01-01", "2026-08-15")):
        res = []
        for s in pd.date_range(a, z, freq="1D", tz="UTC"):
            if s.weekday() >= 5: continue
            h0 = idx.searchsorted(s); p1, i1 = attempt(h0, 0.10, m, base, tg, G, brake=br)
            if p1 != "pass": res.append((p1, None)); continue
            p2, i2 = attempt(i1 + 1, 0.05, m, base, tg, G, brake=br); res.append((p2, (i2 - h0) / 24 if p2 == "pass" else None))
        n = len([x for x in res if x[0] != "open"]); t = [x[1] for x in res if x[1] is not None]
        out[f"{lab} pass%"] = 100 * sum(x[0] == "pass" for x in res) / n; out[f"{lab} breach%"] = 100 * sum(x[0] == "breach" for x in res) / n
        out[f"{lab} stopped%"] = 100 * sum(x[0] == "stopped" for x in res) / n; out[f"{lab} days"] = np.median(t)
    return out
with Pool(4) as p: rows = p.map(ev, [(m, "balance", True, 0.04, br) for m in (1.0, 0.9, 0.75) for br in ("balance", "equity")])
pd.set_option("display.width", 300); print(pd.DataFrame(rows).round(1).to_string(index=False))
