"""BTCUSDT perpetual microstructure sample (one day every 14 days, 2023-01 .. 2026-10): minute features from aggregate trades
and order-book depth snapshots, plus a numba market-making simulator. Taker fee 4 bp + 0.5 bp slippage per side; maker fee 2 bp."""
import os, glob, zipfile, io, pickle, numpy as np, pandas as pd
from numba import njit
from data import SCR, RDATA
M = f"{SCR}/mdata"
def _csv(f):
    with zipfile.ZipFile(f) as z: return pd.read_csv(io.BytesIO(z.read(z.namelist()[0])))
def trades(day):
    d = _csv(f"{M}/agg/BTCUSDT-aggTrades-{day}.zip"); t = d.transact_time.values; t = np.where(t > 1e14, t // 1000, t)
    return pd.DataFrame({"t": t, "p": d.price.values.astype(float), "q": d.quantity.values.astype(float), "s": np.where(d.is_buyer_maker.astype(str).str.lower() == "true", -1, 1)})
def minute_table(day):
    tr = trades(day); tr["m"] = (tr.t // 60000).astype("int64"); tr["notional"] = tr.p * tr.q
    g = tr.groupby("m"); out = pd.DataFrame({"close": g.p.last(), "open": g.p.first(), "high": g.p.max(), "low": g.p.min(),
          "svol": g.apply(lambda x: (x.q * x.s).sum()), "vol": g.q.sum(), "n": g.p.size(), "maxnot": g.notional.max(),
          "sgn_ac": g.s.apply(lambda s: float(np.corrcoef(s.values[:-1], s.values[1:])[0, 1]) if len(s) > 20 and s.std() > 0 else 0.0)})
    # VPIN: 50 equal-volume buckets per day, rolling 50
    V = tr.q.sum() / 50; cum = tr.q.cumsum(); b = (cum // V).astype(int); bk = tr.groupby(b).apply(lambda x: abs((x.q * x.s).sum()) / max(x.q.sum(), 1e-9))
    bend = tr.groupby(b).m.last(); vp = pd.Series(bk.values, index=bend.values).groupby(level=0).last().rolling(10, min_periods=5).mean()
    out["vpin"] = vp.reindex(out.index, method="ffill")
    dp = _csv(f"{M}/depth/BTCUSDT-bookDepth-{day}.zip"); dp["m"] = (pd.to_datetime(dp.timestamp).astype("int64") // 60_000_000_000).astype("int64")
    pv = dp.pivot_table(index="m", columns="percentage", values="notional", aggfunc="last")
    imb1 = (pv[-1] - pv[1]) / (pv[-1] + pv[1]); imb5 = (pv[-5] - pv[5]) / (pv[-5] + pv[5]); depth1 = pv[-1] + pv[1]
    out["imb1"] = imb1.reindex(out.index, method="ffill"); out["imb5"] = imb5.reindex(out.index, method="ffill"); out["depth1"] = depth1.reindex(out.index, method="ffill")
    out["day"] = pd.Timestamp(day); return out
def days(): return sorted(os.path.basename(f).split("-aggTrades-")[1][:10] for f in glob.glob(f"{M}/agg/*.zip"))
def table():
    p = f"{RDATA}/micro_min.pkl"
    if os.path.exists(p): return pickle.load(open(p, "rb"))
    T = pd.concat([minute_table(d) for d in days()]); pickle.dump(T, open(p, "wb")); return T
@njit(cache=True)
def mm_sim(t, p, s, half_bp, gamma_bp, max_inv, maker_bp, tox, tox_th, refresh_ms):
    """quote bid/ask around a reference price (last trade at quote refresh), skewed by inventory; a quote fills only when an aggressive
    trade prints strictly through it. Returns P&L per unit notional (sum over fills + inventory mark at end) and fill count."""
    inv = 0.0; cash = 0.0; fills = 0; ref = p[0]; last_ref_t = t[0]; n = len(t); quote_on = True
    for i in range(n):
        if t[i] - last_ref_t >= refresh_ms:
            ref = p[i]; last_ref_t = t[i]; quote_on = tox[i] < tox_th
        if not quote_on: continue
        bid = ref * (1 - (half_bp + gamma_bp * inv) / 1e4); ask = ref * (1 + (half_bp - gamma_bp * inv) / 1e4)
        if s[i] < 0 and p[i] < bid and inv < max_inv:
            inv += 1.0; cash -= bid * (1 + maker_bp / 1e4); fills += 1
        elif s[i] > 0 and p[i] > ask and inv > -max_inv:
            inv -= 1.0; cash += ask * (1 - maker_bp / 1e4); fills += 1
    pnl = cash + inv * p[n - 1] * (1 - np.sign(inv) * 4.5 / 1e4)     # flatten leftover inventory with a taker order
    return pnl / p[0], fills
if __name__ == "__main__":
    T = table(); print(T.shape, T.day.min().date(), T.day.max().date(), T.day.nunique(), "days"); print(T.describe().T[["mean", "std"]].round(4))
