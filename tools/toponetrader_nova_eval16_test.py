NOVA = open("toponetrader_nova_test.py").read(); exec(NOVA[:NOVA.index("\nif __name__")])
OUT = {"sol", "solrev", "xrprev", "oil1h"}
code = NOVA[NOVA.index("def acct2("):NOVA.index("def job(")]
code = code.replace("build({c: min(PORT[\"21\"][c] * scale, 1.0 / BASE[c]) for c in NAMES})", "build({c: 0.0 if c in DROP else min(PORT[\"21\"][c] * scale, 1.0 / BASE[c]) for c in NAMES})")
code = code.replace("        else: opn += eq * mm * D_FLT[i]; eq = after\n",
"        else:\n            opn_new = opn + eq * mm * D_FLT[i]; fl = min(opn_new + (low - after), opn_new)\n            if FG and fl <= -FG: eq = (eq - opn) - FG - 0.002; opn = 0.0; hd = day; SOFT[0] += fl <= -0.02\n            else: opn = opn_new; eq = after\n")
DROP = set(); FG = None; SOFT = [0]; exec(code)
def ev(a):
    h0, es, drop, fg = a
    global DROP, FG; DROP = drop; FG = fg; SOFT[0] = 0
    p, i, _ = acct2(h0, es, target=0.05, TD=0.06)
    return p, (i - h0) / 24, SOFT[0]
if __name__ == "__main__":
    st = [idx.searchsorted(s) for s in pd.date_range("2020-09-01", "2025-06-30", freq="7D", tz="UTC")]
    for es, drop, fg, nm in ((2.0, set(), None, "21 EAs, no shield"), (2.0, OUT, None, "16 EAs, no shield"), (2.0, OUT, 0.018, "16 EAs, guard 1.8%"), (2.5, OUT, 0.018, "16 EAs x2.5, guard 1.8%"), (3.0, OUT, 0.018, "16 EAs x3, guard 1.8%")):
        with Pool(os.cpu_count()) as p: d = pd.DataFrame(p.map(ev, [(h, es, drop, fg) for h in st]), columns=["o", "days", "soft"])
        ok = d[d.o == "pass"]
        print(f"{nm:26s} | passed {100*len(ok)/len(d):.0f}% | median {ok.days.median():.0f}d | 75% {ok.days.quantile(.75):.0f}d | 90% {ok.days.quantile(.9):.0f}d | breached {int((d.o=='breached').sum())} | shield hits {int((d.soft>0).sum())}")
