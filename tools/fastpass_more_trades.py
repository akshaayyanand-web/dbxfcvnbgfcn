import numpy as np, pandas as pd
exec(open("crypto_revert.py").read().split("CASES = [")[0])
out = {}
for hold in (12, 60):
    for mult in (1, 2):
        r = run("XRPUSDT", "ema", 0, 0.995, hold, "with", 0.0015 * mult, None)
        by = r.groupby("yr").R.sum().round(1)
        print(f"XRP stretch fade hold {hold*5}m cost x{mult}: {len(r)} trades ({len(r)/6.8:.0f}/yr), win {100*(r.R>0).mean():.0f}%, avg {r.R.mean():+.3f}R, {r.R.sum()/6.8:+.1f}R/yr, years+ {(by>0).sum()}/{len(by)} {by.to_dict()}")
        if hold == 12 and mult == 1: out["xrprev"] = [(t, t + pd.Timedelta(minutes=65), x) for t, x in zip(r.t, r.R)]
exec(open("open_fade_risk.py").read().split("a = detail")[0])
b = detail("fut1m/USATECHIDXUSD_1m.csv", 2.1, 10, 0.98, 30, True)
out["nqfade"] = [(t, t + pd.Timedelta(minutes=31), x) for t, x in zip(b.t, b.R)]
pd.to_pickle(out, "more_trades.pkl"); print({k: (len(v), round(sum(x[2] for x in v), 1)) for k, v in out.items()})
