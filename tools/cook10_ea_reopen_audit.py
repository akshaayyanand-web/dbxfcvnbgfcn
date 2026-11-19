import numpy as np, pandas as pd
exec(open("wport.py").read().split('if __name__ == "__main__":')[0])
def rr(et, xt, e, st, px, cost): return (px - e) / abs(e - st) * np.sign(e - st) - cost * e / abs(e - st)
rows = []
def audit(name, trs):
    df = pd.DataFrame(trs, columns=["et", "xt", "r"]); df["et"] = pd.to_datetime(df.et, utc=True)
    ny = df.et.dt.tz_convert("America/New_York"); m = ny.dt.hour * 60 + ny.dt.minute
    reopen = (m >= 18 * 60) & (m < 19 * 60)          # first hour after the 17:00-18:00 ET daily break
    sunday = ny.dt.weekday == 6
    rows.append(dict(ea=name, trades=len(df), R_total=round(df.r.sum(), 1), reopen_trades=int(reopen.sum()), reopen_R=round(df.r[reopen].sum(), 1),
                     reopen_share=f"{100 * df.r[reopen].sum() / df.r.sum():.0f}%" if df.r.sum() else "-", meanR_reopen=round(df.r[reopen].mean(), 3) if reopen.any() else None,
                     meanR_other=round(df.r[~reopen].mean(), 3)))
for k, v in TRL.items():
    tr, cost = v[0], v[1]
    audit(k, [(et, xt, rr(et, xt, e, st, px, cost)) for et, xt, e, st, px in tr])
for k in ("gold", "spx_fade"): audit("addon " + k, AT[k])
MT = pd.read_pickle("more_trades.pkl"); audit("nqfade", MT["nqfade"])
audit("nikkei", nk)
pd.set_option("display.width", 250); print(pd.DataFrame(rows).to_string())
