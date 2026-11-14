# Improving the friend's gold EA: 144 versions (1m/5m/15m, ATR-vs-spread filter, London+NY hours, trailing, SL/TP), picked on 2020-22, confirmed 2023-24 and 2025-26.
import sys, itertools, numpy as np, pandas as pd
sys.path.insert(0, "/home/user/dbxfcvnbgfcn/tools")
from portfolio_prop import load_csv, rsi, rma
from multiprocessing import Pool
raw = load_csv("fut1m/XAUUSD_1m.csv").loc["2020-01-01":]
DATA = {}
def prep(tf):
    m = raw if tf == "1min" else raw.resample(tf).agg(dict(o="first", h="max", l="min", c="last", v="sum")).dropna()
    O, H, L, C, V = m.o.to_numpy(), m.h.to_numpy(), m.l.to_numpy(), m.c.to_numpy(), m.v.to_numpy(); T = m.index
    srv = (T + pd.Timedelta(hours=2)).normalize(); tp = (H + L + C) / 3
    g = pd.DataFrame({"pv": tp * V, "v": V, "d": srv})
    vwap = (g.groupby("d").pv.cumsum() / g.groupby("d").v.cumsum()).to_numpy()
    R7 = rsi(m.c, 7).to_numpy()
    atr = rma(pd.concat([m.h - m.l, (m.h - m.c.shift()).abs(), (m.l - m.c.shift()).abs()], axis=1).max(axis=1), 14).to_numpy()
    hr = T.hour.to_numpy()
    return O, H, L, C, T, vwap, R7, atr, hr
for tf in ("1min", "5min", "15min"): DATA[tf] = prep(tf)
def run(tf, spread, atr_mult_spread, session, trail, sl_m, tp_m, pend_bars=10):
    O, H, L, C, T, vwap, R7, atr, hr = DATA[tf]
    n = len(C); pend = 0; pend_t = 0; pend_until = 0; out = []; i = 20
    while i < n - 1:
        if pend == 0 or i > pend_until:
            pend = 0
            ok = np.isfinite(vwap[i]) and np.isfinite(atr[i]) and atr[i] >= atr_mult_spread * spread and (not session or 8 <= hr[i] < 21)
            if ok:
                buy = C[i] > vwap[i] and (R7[i] < 35 or (R7[i-1] < 35 and R7[i] > R7[i-1])) and C[i] > O[i]
                sell = C[i] < vwap[i] and (R7[i] > 65 or (R7[i-1] > 65 and R7[i] < R7[i-1])) and C[i] < O[i]
                if buy or sell: pend = 1 if buy else -1; pend_t = C[i] - pend * 2 * atr[i] * 0.9; pend_until = i + pend_bars
            i += 1; continue
        d = pend
        if ((L[i] <= pend_t) if d == 1 else (H[i] >= pend_t)) and ((C[i] > O[i]) if d == 1 else (C[i] < O[i])):
            e = O[i + 1] + d * spread / 2; a = atr[i]; sl = e - d * sl_m * a; tp = e + d * tp_m * a; R = sl_m * a; j = i + 1; px = None
            while j < n:
                if (L[j] <= sl) if d == 1 else (H[j] >= sl): px = sl; break
                if (H[j] >= tp) if d == 1 else (L[j] <= tp): px = tp; break
                if trail:
                    best = H[j] if d == 1 else L[j]
                    if (best - e) * d >= 0.8 * a:
                        nsl = best - d * 0.5 * a
                        if (nsl - sl) * d > 0: sl = nsl
                j += 1
            if px is None: break
            out.append((T[i + 1].year, ((px - e) * d - spread / 2) / R)); pend = 0; i = j + 1; continue
        i += 1
    return out
def ev(cfg):
    tf, am, sess, trail, (slm, tpm) = cfg
    res = {}
    for sp in (0.15, 0.30):
        r = pd.DataFrame(run(tf, sp, am, sess, trail, slm, tpm), columns=["yr", "R"])
        for lab, yrs in (("A", (2020, 2021, 2022)), ("B", (2023, 2024)), ("C", (2025, 2026))):
            x = r[r.yr.isin(yrs)].R
            res[f"{lab}_R_yr_{sp}"] = round(x.sum() / (len(yrs) if lab != "C" else 1.83), 1); res[f"{lab}_n_{sp}"] = len(x)
        res[f"by_year_{sp}"] = r.groupby("yr").R.sum().round(1).to_dict()
    return dict(tf=tf, atr_vs_spread=am, london_ny=sess, trailing=trail, sl_tp=f"{slm}/{tpm}", **res)
cfgs = list(itertools.product(("1min", "5min", "15min"), (0, 4, 8, 12), (False, True), (True, False), ((2.0, 3.0), (1.5, 3.0), (2.0, 4.0))))
if __name__ == "__main__":
    with Pool(4) as p: rows = p.map(ev, cfgs)
    df = pd.DataFrame(rows); df.to_pickle("xau_better.pkl")
    pd.set_option("display.width", 320); pd.set_option("display.max_colwidth", 140); pd.set_option("display.max_rows", 200)
    A = df.sort_values("A_R_yr_0.15", ascending=False)
    print(f"{len(df)} versions. Positive in 2020-22 (picked there): {(df['A_R_yr_0.15'] > 0).sum()}; also 2023-24: {((df['A_R_yr_0.15'] > 0) & (df['B_R_yr_0.15'] > 0)).sum()}; also 2025-26: {((df['A_R_yr_0.15'] > 0) & (df['B_R_yr_0.15'] > 0) & (df['C_R_yr_0.15'] > 0)).sum()}; and all three at double spread: {((df['A_R_yr_0.3'] > 0) & (df['B_R_yr_0.3'] > 0) & (df['C_R_yr_0.3'] > 0)).sum()}")
    cols = ["tf", "atr_vs_spread", "london_ny", "trailing", "sl_tp", "A_n_0.15", "A_R_yr_0.15", "B_R_yr_0.15", "C_R_yr_0.15", "A_R_yr_0.3", "B_R_yr_0.3", "C_R_yr_0.3"]
    print("\nbest 12 picked on 2020-22 only:"); print(A[cols].head(12).to_string(index=False))
    print("\noriginal settings (1min, no filter, all hours, trailing, 2/3):"); print(df[(df.tf == "1min") & (df.atr_vs_spread == 0) & (~df.london_ny) & (df.trailing) & (df.sl_tp == "2.0/3.0")][cols].to_string(index=False))
