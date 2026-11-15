import os, numpy as np, pandas as pd
exec(open("onestep2.py").read().split("\nRULES = {")[0])
RULES = {"1-Step Lite: 8%, 3% daily, 7% static": [(0.08, 0.03, 0.07)],
         "1-Step Flex: 9%, 3% daily, 10% static": [(0.09, 0.03, 0.10)],
         "2-Step Lite: 6%+6%, 4% daily, 8% static": [(0.06, 0.04, 0.08), (0.06, 0.04, 0.08)],
         "2-Step Flex: 8%+6%, 4% daily, 12% static": [(0.08, 0.04, 0.12), (0.06, 0.04, 0.12)]}
def ev(args):
    rule, scale = args; w = PORT["21"]; build({c: min(w[c] * scale, 1.0 / BASE[c]) for c in NAMES})
    res = []
    for s in pd.date_range("2020-09-01", "2026-05-01", freq="3D", tz="UTC"):
        if s.weekday() >= 5: continue
        h0 = idx.searchsorted(s); h = h0; out = "pass"
        for tg, DL, ML in RULES[rule]:
            p, i = core2(h, tg, DL, ML, False, False)
            if p != "pass": out = p; break
            h = i + 24
        res.append((out, (h - 24 - h0) / 24 if out == "pass" else None))
    d = pd.DataFrame(res, columns=["o", "d"]); d = d[d.o != "open"]; t = d.d.dropna()
    return dict(rules=rule, scale=scale, pass_pct=round(100 * (d.o == "pass").mean(), 1), breach=round(100 * (d.o == "breach").mean(), 1),
                med=round(t.median()), p25=round(t.quantile(.25)), p75=round(t.quantile(.75)), within30=round(100 * (d.d <= 30).mean()))
if __name__ == "__main__":
    jobs = [(r, sc) for r in RULES for sc in (1.5, 2.0, 2.5, 3.0, 3.5)]
    with Pool(os.cpu_count()) as p: rows = p.map(ev, jobs)
    pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 60); print(pd.DataFrame(rows).to_string(index=False))
