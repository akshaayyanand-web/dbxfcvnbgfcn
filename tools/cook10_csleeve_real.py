# Real The5ers costs: BTC 0.090% round trip, ETH 0.227% (spread at current price + 0.03% commission per side). Margin check at 1:2 and 1:0.6.
import sys
exec(open("csleeve.py").read().split('\nif __name__ == "__main__":')[0])
if __name__ == "__main__":
    TR = pd.read_pickle("csleeve_trades.pkl"); S = pd.Timestamp("2023-01-01", tz="UTC")
    for w, cm in (("A", 0.00227 / 0.001), ("B", 0.0009 / 0.0006)):
        t = trades(w, cm); TR[(w, "real")] = t; tt = lambda v: round(v.mean() / v.std() * np.sqrt(len(v)), 2)
        print(f"{w} real cost: avg R {t.R.mean():+.3f} | train {t.R[t.t_in < S].mean():+.3f} (t {tt(t.R[t.t_in < S])}) | holdout {t.R[t.t_in >= S].mean():+.3f} (t {tt(t.R[t.t_in >= S])}) | win {100*(t.R>0).mean():.0f}% | positive years {(t.groupby(t.t_in.dt.year).R.sum()>0).sum()}/{t.t_in.dt.year.nunique()}", flush=True)
    pd.to_pickle(TR, "csleeve_trades.pkl")
    # margin: combined open notional of A+B at 0.3% risk per trade (0.1% x3), sampled every 15 minutes
    grid = pd.date_range("2020-09-01", "2026-10-31", freq="15min", tz="UTC"); notl = np.zeros(len(grid))
    for w in ("A", "B"):
        t = TR[(w, "real")]
        for r in t.itertuples():
            a, b = grid.searchsorted(r.t_in), grid.searchsorted(r.t_out); notl[a:b] += 0.003 * r.notional_x_risk
    op = notl[notl > 0]
    for lev in (2.0, 0.6):
        m = op / lev; print(f"leverage 1:{lev}: margin while a crypto trade is open - median {100*np.median(m):.0f}% of account, 95th pct {100*np.quantile(m,.95):.0f}%, max {100*m.max():.0f}%")
