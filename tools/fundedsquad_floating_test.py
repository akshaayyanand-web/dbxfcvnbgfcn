import os, numpy as np, pandas as pd
exec(open("onestep2.py").read().split("\nRULES = {")[0])
def run(h0, target=0.09, DL=0.03, ML=0.10, fguard=None, flimit=0.015, slip=0.002, scaleZ=0.7):
    floor = 1 - ML; eq = 1.0; opn = 0.0; day = -1; hd = -1; halfmode = False; mm = 0.0; G = DL - 0.01; viol = 0; worst_float = 0.0
    for i in range(h0, len(EQ_R)):
        if DAYN[i] != day:
            if day != -1 and eq - opn >= 1 + target: return "pass", i, viol, worst_float
            day = DAYN[i]; ref = eq - opn; g = eq; room = g - floor
            if room <= 0.3 * ML: halfmode = True
            elif room >= 0.9 * ML: halfmode = False
            mm = max(0.0, min(1.0, room / (scaleZ * ML))) * (0.5 if halfmode else 1.0)
        if hd == day or (EQ_R[i] == 0 and EQ_L[i] == 0):
            if hd == day: opn = 0.0
            continue
        low = eq * (1 + mm * EQ_L[i]); after = eq * (1 + mm * EQ_R[i])
        if low <= ref - G:
            eq = min(after, max(low, ref - G - 0.003)); opn = 0.0; hd = day
            if eq <= floor: return "breach", i, viol, worst_float
            continue
        if low <= floor or low <= ref - DL: return "breach", i, viol, worst_float
        opn_new = opn + eq * mm * D_FLT[i]
        fl_worst = min(opn_new + (low - after), opn_new)          # worst floating P&L of open trades during the hour
        worst_float = min(worst_float, fl_worst)
        if fguard is not None and fl_worst <= -fguard:            # EA floating guard: close everything at -fguard, stop for the day
            eq = (eq - opn) - fguard - slip; opn = 0.0; hd = day
            if eq <= floor: return "breach", i, viol, worst_float
            continue
        if fl_worst <= -flimit:
            viol += 1
            if viol >= 2: return "disqualified (floating rule)", i, viol, worst_float
        opn = opn_new; eq = after
    return "open", len(EQ_R) - 1, viol, worst_float
def ev(args):
    scale, fg = args; w = PORT["21"]; build({c: min(w[c] * scale, 1.0 / BASE[c]) for c in NAMES})
    res = []
    for s in pd.date_range("2020-09-01", "2026-05-01", freq="3D", tz="UTC"):
        if s.weekday() >= 5: continue
        h0 = idx.searchsorted(s); p, i, v, wf = run(h0, fguard=fg); res.append((p, (i - h0) / 24 if p == "pass" else None, v, wf))
    d = pd.DataFrame(res, columns=["o", "d", "v", "wf"]); d = d[d.o != "open"]; t = d.d.dropna()
    return dict(scale=scale, float_guard=fg, pass_pct=round(100 * (d.o == "pass").mean(), 1), disq_floating=round(100 * (d.o.str.startswith("disq")).mean(), 1),
                passes_with_1_violation=round(100 * ((d.o == "pass") & (d.v == 1)).mean(), 1), breach=round(100 * (d.o == "breach").mean(), 1),
                med=round(t.median()) if len(t) else None, within30=round(100 * (d.d <= 30).mean()))
if __name__ == "__main__":
    jobs = [(sc, fg) for sc in (1.0, 1.5, 2.0, 2.5, 3.5) for fg in (None, 0.012)]
    with Pool(os.cpu_count()) as p: rows = p.map(ev, jobs)
    pd.set_option("display.width", 250); print(pd.DataFrame(rows).to_string(index=False))
