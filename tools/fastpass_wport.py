# Per-EA hourly components (12 core + 4 add-ons) with their own open-P&L, for re-weighting inside the corrected simulator.
import numpy as np, pandas as pd
exec(open("sol_addon.py").read().split("def ev(cfg)")[0])          # base 12 (comp_r/comp_l via breach_anatomy), SOL series, simT data
REALK = {}
def bookk(key, tr, cost, w):
    a = REALK.setdefault(key, np.zeros(len(idx)))
    for et, xt, e, st, px in tr:
        h = idx.searchsorted(xt)
        if h < len(idx) and xt >= idx[0]: a[min(h, len(idx) - 1)] += w / 100 * ((px - e) / abs(e - st) * np.sign(e - st) - cost * e / abs(e - st))
MAP = {"btc": "BTC_Dip_v3", "gdip": "Gold_Dip", "nq2h": "NQ_Dip_2h", "spx1h": "SPX_Dip_1h", "oil1h": "Oil_Dip_1h", "gasia": "Gold_Asia_Breakout",
       "gmom": "Gold_Intraday_Momentum", "orb15": "NQ_Opening_Range", "daxorb": "DAX_Opening_Range", "btcgap": "BTC_Weekend_Gap"}
for c, k in MAP.items(): bookk(c, TRL[k][0], TRL[k][1], W[k])
bookk("nqbo15", simT(bq, wq & (Cq > bq.h.rolling(20).max().shift(1).to_numpy()) & (Cq > cq.ewm(span=200, adjust=False).mean().to_numpy()), wq & (Cq < bq.l.rolling(20).min().shift(1).to_numpy()) & (Cq < cq.ewm(span=200, adjust=False).mean().to_numpy()), aq, 10 ** 6, mq >= 950), 0.00012, 0.2)
bookk("spxbo5", simT(b5, w5 & (C5 > hi) & (C5 > e5), w5 & (C5 < lo5) & (C5 < e5), 2 * a5, 10 ** 6, m5 >= 950), 0.0001, 0.1)
COMP = {}
for c in comp_r:
    r = np.asarray(comp_r[c], float); l = np.asarray(comp_l[c], float)
    COMP[c] = [r, l, np.diff(np.concatenate([[0.0], np.cumsum(r) - np.cumsum(REALK.get(c, np.zeros(len(idx))))]))]
Rs, Ls, rls, _ = SER["SOL 1h dip RSI2<15 EMA200 hold144"]
COMP["sol"] = [0.003 * Rs, 0.003 * Ls, 0.003 * np.diff(np.concatenate([[0.0], np.cumsum(Rs) - np.cumsum(rls)]))]
AT = pd.read_pickle("addon_trades.pkl"); NMJ = "breakout20 EMA800 stop2.0ATR"
nk = [(et, xt, (px - e) / abs(e - st) * np.sign(e - st) - 0.0002 * e / abs(e - st)) for et, xt, e, st, px in
      list(pd.read_pickle("world_JPNIDXJPY.pkl")[1]["JPN 5min " + NMJ]) + list(pd.read_pickle("jp_broker_trades.pkl")[NMJ])]
def intraday(tr, w):
    R = np.zeros(len(idx)); L = np.zeros(len(idx))
    for et, xt, r in tr:
        h = idx.searchsorted(pd.Timestamp(xt))
        if h < len(idx) and pd.Timestamp(xt) >= idx[0]: R[h] += w * r; L[h] += w * min(r, 0.0)
    return [R, L, np.zeros(len(idx))]
COMP["goldvwap"] = intraday(AT["gold"], 0.002); COMP["spxfade"] = intraday(AT["spx_fade"], 0.0025); COMP["nikkei"] = intraday(nk, 0.001)
def build(wts):
    """wts: multiplier per component (default 1 = the tested risk). Sets EQ_R, EQ_L, D_FLT for core()."""
    global EQ_R, EQ_L, D_FLT
    EQ_R = sum(wts.get(c, 1.0) * v[0] for c, v in COMP.items()); EQ_L = sum(wts.get(c, 1.0) * v[1] for c, v in COMP.items())
    D_FLT = sum(wts.get(c, 1.0) * v[2] for c, v in COMP.items())
exec(open("sim_fixed2.py").read().split("D_FLT = np.diff")[1].split("\n", 1)[1])   # core() (uses EQ_R, EQ_L, D_FLT, DAYN, idx)
build({})
if __name__ == "__main__":
    print("components:", list(COMP)); print("total R x1:", round(float(EQ_R.sum()), 3))
    flt_base = np.cumsum(sum(v[2] for c, v in COMP.items() if c not in ("sol", "goldvwap", "spxfade", "nikkei")))
    print("base open-P&L matches the old FLT:", np.allclose(flt_base, FLT, atol=1e-9))
