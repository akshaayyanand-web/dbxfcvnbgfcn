import os, numpy as np, pandas as pd
exec(open("frontier3.py").read().split("def ev(args)")[0].split("for k, w in PORT.items()")[0])
def core1(h0, Z, target, DL, ML, G, half, sl_off=0.005, slip=0.003):
    floor = 1 - ML; sl = floor + sl_off; eq = 1.0; opn = 0.0; day = -1; hd = -1; halfmode = False; mm = 0.0
    for i in range(h0, len(EQ_R)):
        if DAYN[i] != day:
            day = DAYN[i]; ref = eq - opn; g = eq
            if g <= 1 - half[0]: halfmode = True
            elif g >= 1 - half[1]: halfmode = False
            mm = max(0.0, min(1.0, (g - floor) / Z)) * (0.5 if halfmode else 1.0)
        if hd == day or (EQ_R[i] == 0 and EQ_L[i] == 0):
            if hd == day: opn = 0.0
            continue
        low = eq * (1 + mm * EQ_L[i]); after = eq * (1 + mm * EQ_R[i])
        if low <= ref - G:
            eq = min(after, max(low, ref - G - slip)); opn = 0.0; hd = day
            if eq <= floor: return "breach", i
            if eq <= sl: return "stopped", i
            continue
        if low <= floor or low <= ref - DL: return "breach", i
        opn += eq * mm * D_FLT[i]; eq = after
        if eq >= 1 + target: return "pass", i
        if eq <= sl: return "stopped", i
    return "open", len(EQ_R) - 1
RULES = {"FTMO-style 2-step (ref)": None, "1-step: +10%, daily 5%, max 10%": (0.10, 0.05, 0.10), "1-step: +10%, daily 4%, max 8%": (0.10, 0.04, 0.08),
         "1-step: +10%, daily 3%, max 6%": (0.10, 0.03, 0.06), "1-step: +8%, daily 4%, max 6%": (0.08, 0.04, 0.06)}
def ev(args):
    rule, scale = args; w = PORT["21"]; build({c: min(w[c] * scale, 1.0 / BASE[c]) for c in NAMES})
    res = []
    for s in pd.date_range("2020-09-01", "2026-05-01", freq="3D", tz="UTC"):
        if s.weekday() >= 5: continue
        h0 = idx.searchsorted(s)
        if RULES[rule] is None:
            p1, i1, _ = core(h0, 1.0, 0.07, target=0.10, half=(0.03, 0.01))
            if p1 != "pass": res.append((p1, None)); continue
            p2, i2, _ = core(i1 + 1, 1.0, 0.07, target=0.05, half=(0.03, 0.01)); res.append((p2, (i2 - h0) / 24 if p2 == "pass" else None)); continue
        tg, DL, ML = RULES[rule]; G = DL - 0.01; Z = ML * 0.7; half = (ML * 0.3, ML * 0.1)
        p, i = core1(h0, Z, tg, DL, ML, G, half); res.append((p, (i - h0) / 24 if p == "pass" else None))
    d = pd.DataFrame(res, columns=["o", "d"]); d = d[d.o != "open"]; t = d.d.dropna()
    return dict(rules=rule, scale=scale, pass_pct=round(100 * (d.o == "pass").mean(), 1), breach=round(100 * (d.o == "breach").mean(), 1),
                med=round(t.median()), p25=round(t.quantile(.25)), p75=round(t.quantile(.75)), within30=round(100 * (d.d <= 30).mean()))
if __name__ == "__main__":
    jobs = [("FTMO-style 2-step (ref)", 4.5)] + [(r, sc) for r in list(RULES)[1:] for sc in (2.5, 3.5, 4.5)]
    with Pool(os.cpu_count()) as p: rows = p.map(ev, jobs)
    pd.set_option("display.width", 250); print(pd.DataFrame(rows).to_string(index=False))
