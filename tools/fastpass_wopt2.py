exec(open("wopt.py").read().split("w = {c: 1.0 for c in names}; best")[0])
vol_tr = TR.std(); sh_tr = TR.mean() / TR.std()
cands = {"current": {c: 1.0 for c in names}}
rp = (1 / vol_tr); rp = rp / rp.mean(); cands["equal risk (inverse vol)"] = rp.to_dict()
tilt = (sh_tr / sh_tr.mean()).clip(0.5, 2.0); cands["Sharpe tilt, 0.5-2x"] = tilt.to_dict()
rt = (rp * (sh_tr / sh_tr.mean()).clip(0.5, 2.0)); rt = rt / rt.mean(); cands["equal risk x Sharpe tilt"] = rt.clip(0.25, 3).to_dict()
w1 = dict(cands["current"]);
for lab, df in (("train 2020-22", TR), ("test 2023-26", TE)):
    for nm, ww in cands.items():
        ann, vol, dd, sh, cal = stats(df, ww)
        print(f"{lab:14s} {nm:26s}: return {100*ann:5.1f}%/yr  vol {100*vol:4.1f}%  max DD {100*dd:5.1f}%  Sharpe {sh:4.2f}  return/DD {cal:4.2f}")
print({k: {c: round(v[c], 2) for c in names} for k, v in cands.items() if k != "current"})
pd.to_pickle(cands, "wcands.pkl")
