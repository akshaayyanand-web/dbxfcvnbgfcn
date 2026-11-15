import os, numpy as np, pandas as pd
exec(open("onestep2.py").read().split("\nRULES = {")[0])
TL = pd.read_pickle("dir_trades.pkl")
def wk_share(c):   # share of a component's R that came from weekday entries
    v = TL[c]; tot = sum(x[3] for x in v); wd = sum(x[3] for x in v if pd.Timestamp(x[0]).weekday() < 5); return max(0.0, wd / tot) if tot else 1.0
WKD = {"btc": wk_share("btc"), "sol": wk_share("sol"), "btcgap": 0.0}
print("weekday share kept:", {k: round(v, 2) for k, v in WKD.items()}, flush=True)
def acct(h0, target=None, days=None, every=14, DL=0.03, ML=0.10, G=0.02, fguard=None, flimit=0.015, slip=0.003, Z=0.07):
    floor = 1 - ML; eq = 1.0; opn = 0.0; day = -1; hd = -1; halfmode = False; mm = 0.0; viol = 0; pays = []; ndays = 0; pdays = 0; dstart = 1.0
    end = len(EQ_R) if days is None else min(h0 + days * 24, len(EQ_R)); nextpay = h0 + every * 24
    for i in range(h0, end):
        if days is not None and i >= nextpay:
            nextpay += every * 24; bal = eq - opn
            if bal > 1.0 and eq > 1.0: w = min(bal, eq) - 1.0; pays.append(w); eq -= w
        if DAYN[i] != day:
            if day != -1 and target is not None and eq - opn >= 1 + target and pdays >= 3: return "pass", i, viol, pays
            pdays += (eq - opn) - dstart >= 0.005; dstart = eq - opn; day = DAYN[i]; ndays += 1; ref = max(eq - opn, eq)          # FundedSquad: higher of balance and equity at the reset
            g = eq; room = g - floor
            if room <= 0.3 * ML: halfmode = True
            elif room >= 0.9 * ML: halfmode = False
            mm = max(0.0, min(1.0, room / Z)) * (0.5 if halfmode else 1.0)
        if hd == day or (EQ_R[i] == 0 and EQ_L[i] == 0):
            if hd == day: opn = 0.0
            continue
        low = eq * (1 + mm * EQ_L[i]); after = eq * (1 + mm * EQ_R[i])
        if low <= ref - G:
            eq = min(after, max(low, ref - G - slip)); opn = 0.0; hd = day
            if eq <= floor: return "breach", i, viol, pays
            continue
        if low <= floor or low <= ref - DL: return "breach", i, viol, pays
        opn_new = opn + eq * mm * D_FLT[i]; fl = min(opn_new + (low - after), opn_new)
        if fguard is not None and fl <= -fguard:
            eq = (eq - opn) - fguard - slip; opn = 0.0; hd = day
            if eq <= floor: return "breach", i, viol, pays
            continue
        if days is not None and fl <= -flimit:
            viol += 1
            if viol >= 2: return "terminated (floating rule)", i, viol, pays
        opn = opn_new; eq = after
        if eq <= floor + 0.005: return "stopped", i, viol, pays
    return ("open" if target is not None else "kept"), end - 1, viol, pays
def weights(scale):
    w = PORT["21"]; return {c: min(w[c] * scale, 1.0 / BASE[c]) * WKD.get(c, 1.0) for c in NAMES}
def ev(args):
    es, fs, fg = args
    starts = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    out = []
    for h0 in starts:
        build(weights(es)); p, i, _, _ = acct(h0, target=0.09)
        if p != "pass": out.append((p, None, None, 0.0, 0)); continue
        build(weights(fs)); o, j, v, pays = acct(i + 48, days=365, fguard=fg)
        out.append(("pass", (i - h0) / 24, o, 200000 * sum(pays), v))
    d = pd.DataFrame(out, columns=["ev", "days", "funded", "paid", "viol"]); ok = d[d.ev == "pass"]
    you = 0.8 * ok.paid + np.where(ok.paid > 0, 0.2 * 0.09 * 200000, 0)
    return dict(eval_scale=es, funded_scale=fs, float_guard=fg, eval_pass=round(100 * len(ok) / len(d), 1), eval_med_days=round(ok.days.median()),
                funded_kept=round(100 * (ok.funded == "kept").mean(), 1), floating_terminated=round(100 * ok.funded.str.startswith("term").mean(), 1),
                one_violation=round(100 * (ok.viol == 1).mean(), 1), you_get_per_yr_median=round(float(np.median(you))), you_get_25pct=round(float(np.percentile(you, 25))))
if __name__ == "__main__":
    jobs = [(3.5, 1.5, 0.012)]
    with Pool(os.cpu_count()) as p: rows = p.map(ev, jobs)
    pd.set_option("display.width", 260); print(pd.DataFrame(rows).to_string(index=False))
