import os, numpy as np, pandas as pd
exec(open("onestep.py").read().split("RULES = {")[0])
def core2(h0, target, DL, ML, trailing, bestday, scaleZ=0.7, slip=0.003):
    floor = 1 - ML; eq = 1.0; opn = 0.0; day = -1; hd = -1; halfmode = False; mm = 0.0; G = DL - 0.01
    peak_eod = 1.0; day_start_bal = 1.0; best = 0.0
    for i in range(h0, len(EQ_R)):
        if DAYN[i] != day:
            if day != -1:
                bal = eq - opn; best = max(best, bal - day_start_bal)
                if trailing: peak_eod = max(peak_eod, bal); floor = min(max(floor, peak_eod - ML), 1.0)   # trails the best EOD balance
                if bal >= 1 + target and (not bestday or best <= 0.5 * (bal - 1)): return "pass", i
            day = DAYN[i]; ref = eq - opn; day_start_bal = ref; g = eq
            room = g - floor
            if room <= 0.3 * ML: halfmode = True
            elif room >= 0.9 * ML: halfmode = False
            mm = max(0.0, min(1.0, room / (scaleZ * ML))) * (0.5 if halfmode else 1.0)
        if hd == day or (EQ_R[i] == 0 and EQ_L[i] == 0):
            if hd == day: opn = 0.0
            continue
        low = eq * (1 + mm * EQ_L[i]); after = eq * (1 + mm * EQ_R[i])
        if low <= ref - G:
            eq = min(after, max(low, ref - G - slip)); opn = 0.0; hd = day
            if eq <= floor: return "breach", i
            if eq <= floor + 0.005: return "stopped", i
            continue
        if low <= floor or low <= ref - DL: return "breach", i
        opn += eq * mm * D_FLT[i]; eq = after
        if eq <= floor + 0.005: return "stopped", i
    return "open", len(EQ_R) - 1
RULES = {"FTMO 1-Step: +10%, 3% daily, 10% trailing EOD, best-day 50%": (0.10, 0.03, 0.10, True, True),
         "1-step: +10%, 4% daily, 8% static": (0.10, 0.04, 0.08, False, False),
         "1-step: +10%, 4% daily, 8% trailing EOD": (0.10, 0.04, 0.08, True, False),
         "1-step: +10%, 5% daily, 10% static (ideal)": (0.10, 0.05, 0.10, False, False)}
def ev(args):
    rule, scale = args; w = PORT["21"]; build({c: min(w[c] * scale, 1.0 / BASE[c]) for c in NAMES})
    res = []
    for s in pd.date_range("2020-09-01", "2026-05-01", freq="3D", tz="UTC"):
        if s.weekday() >= 5: continue
        h0 = idx.searchsorted(s); p, i = core2(h0, *RULES[rule]); res.append((p, (i - h0) / 24 if p == "pass" else None))
    d = pd.DataFrame(res, columns=["o", "d"]); d = d[d.o != "open"]; t = d.d.dropna()
    return dict(rules=rule, scale=scale, pass_pct=round(100 * (d.o == "pass").mean(), 1), breach=round(100 * (d.o == "breach").mean(), 1),
                med=round(t.median()), p25=round(t.quantile(.25)), p75=round(t.quantile(.75)), within30=round(100 * (d.d <= 30).mean()))
if __name__ == "__main__":
    jobs = [(r, sc) for r in RULES for sc in (1.5, 2.5, 3.5, 4.5)]
    with Pool(os.cpu_count()) as p: rows = p.map(ev, jobs)
    pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 70); print(pd.DataFrame(rows).to_string(index=False))
