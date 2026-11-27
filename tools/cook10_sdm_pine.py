# "Order Flow: Structural Delta Map + HMA + EMAs" (TradingView) turned into trade rules with its default inputs. Long logic; shorts = negated series.
#  AGR (structural buy): last confirmed pivot (48/48) was a LOW -> price dips to the VWAP anchored at that pivot (low <= AVWAP +0.1%), closes above it,
#                        green candle, volume > 1.5 x 20-bar average.
#  ABS (absorption buy): low < previous low, green candle, lower wick > body, volume > 1.5 x average.
#  Each also with the script's trend lines as a filter: HMA(100) rising, or close > EMA200.
#  Stop 0.1 ATR beyond the signal bar's extreme; exits: 2R target, or time exit 10 bars (the shared harness). Costs + swap per market. Train < 2023.
import sys
exec(open("joat.py").read().split("def S_joat")[0])
EX = [("2R target", 0, 2.0), ("time exit 10 bars", 5, 0.0)]
def wma(x, n):
    w = np.arange(n, 0, -1, dtype=float) / (n * (n + 1) / 2); y = np.convolve(np.nan_to_num(x), w, mode="full")[:len(x)]; y[:n - 1] = np.nan; return y
def hma(x, n): return wma(2 * wma(x, n // 2) - wma(x, n), int(np.sqrt(n)))
def S_sdm(X):
    O, H, L, C, V = X.O, X.H, X.L, X.C, X.V; N = X.N; A = X.atr(); out = {}
    if not X.hasvol: return {k: (np.zeros(N, bool), L - .1 * A) for k in ("AGR", "AGR + HMA rising", "AGR + above EMA200", "ABS", "ABS + HMA rising", "ABS + above EMA200")}
    p = 48; lmin = pd.Series(L).rolling(2 * p + 1, center=True).min().to_numpy(); hmax = pd.Series(H).rolling(2 * p + 1, center=True).max().to_numpy()
    is_pl = L == lmin; is_ph = H == hmax                                   # pivot at bar j, known at bar j+48
    tp = (H + L + C) / 3; cs = np.r_[0, np.cumsum(tp * V)]; cv = np.r_[0, np.cumsum(V)]
    up = np.zeros(N, bool); av = np.full(N, np.nan); anchor = -1; trend = False
    for k in range(p, N):
        j = k - p
        if is_ph[j]: anchor = j; trend = False
        if is_pl[j]: anchor = j; trend = True
        if anchor >= 0:
            vv = cv[k + 1] - cv[anchor]
            if vv > 0: av[k] = (cs[k + 1] - cs[anchor]) / vv
        up[k] = trend
    hv = V > 1.5 * sma(V, 20); bull = C > O
    agr = up & (L <= av + 0.001 * np.abs(av)) & (C > av) & bull & hv
    absb = (L < shift(L)) & bull & ((O - L) > (C - O)) & hv
    hm = hma(C, 100); hup = hm > shift(hm); e200 = pd.Series(C).ewm(span=200, adjust=False).mean().to_numpy(); st = L - 0.1 * A
    for nm, s in (("AGR", agr), ("ABS", absb)):
        out[nm] = (s, st); out[nm + " + HMA rising"] = (s & hup, st); out[nm + " + above EMA200"] = (s & (C > e200), st)
    return out
src = open("joat.py").read(); fn = src[src.index("def run(job):"):src.index('\nif __name__ == "__main__":')]
fn = fn.replace("S_joat", "S_sdm").replace('(0.25 if tf == "M15" else 1.0)', '({"M5": 5 / 60, "M15": 0.25}.get(tf, 1.0))').replace('if nm.startswith("3"):', 'if False:')
exec(fn)
if __name__ == "__main__":
    mk = ("NQ", "SPX", "DAX", "XAU", "BTC", "ETH", "EURUSD")
    for s in mk:
        try: K._cache[(s, "M5")] = K.rs(K.MK[s][0](), "5min").pipe(lambda b: b[(b.h >= b.l) & (b.c > 0)])
        except Exception as ex: print(s, "no M5", ex)
    jobs = [(s, tf) for s in mk for tf in ("M5", "M15", "H1")]
    with Pool(3) as p: res = p.map(run, jobs, chunksize=1)
    D = pd.DataFrame([r for o in res for r in o]); D.to_csv("sdm.csv", index=False); D = D[D.n > 0]
    pd.set_option("display.width", 230); pd.set_option("display.max_rows", 300)
    g = D.groupby(["rule", "exit"]).agg(cells=("n", "size"), trades=("n", "sum"), win=("win", "median"), med_train=("avgR_train", "median"), med_hold=("avgR_hold", "median"))
    print("\nBY RULE (median over 7 markets x 3 timeframes):"); print(g.round(3).to_string())
    D["ok"] = (D.t_train >= 2) & (D.t_hold >= 1.5) & (D.n_train >= 50) & (D.n_hold >= 30)
    print(f"\ncells passing train t>=2 and holdout t>=1.5: {int(D.ok.sum())} of {len(D)} (luck ~{len(D)*0.023*0.067:.1f})"); print(D[D.ok].round(3).to_string(index=False) if D.ok.any() else "none")
    print("\nbest 8 cells by holdout t:"); print(D.sort_values("t_hold", ascending=False).head(8).round(3).to_string(index=False))
