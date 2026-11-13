# "Hold until green" 50-lot NQ scalps (no stop; close at +3/6/10 pts; give up at -50..-400 pts or the 15:55 close), 8,000 random NY entries 2020-2026, 2.1-pt spread.
import sys, numpy as np, pandas as pd
sys.path.insert(0, "/home/user/dbxfcvnbgfcn/tools")
from portfolio_prop import load_csv
m1 = load_csv("fut1m/USATECHIDXUSD_1m.csv").loc["2020-01-01":]
O, H, L, T = m1.o.to_numpy(), m1.h.to_numpy(), m1.l.to_numpy(), m1.index
ny = T.tz_convert("America/New_York"); mins = (ny.hour * 60 + ny.minute).to_numpy(); dk = (ny.year * 10000 + ny.month * 100 + ny.day).to_numpy(); wd = ny.weekday.to_numpy(); n = len(O)
rng = np.random.default_rng(11); cand = np.where((mins >= 575) & (mins < 900) & (wd < 5))[0]
ent = np.sort(rng.choice(cand, 8000, replace=False)); side = rng.choice([-1, 1], len(ent))
SPREAD, LOTS = 2.1, 50
rows = []
for tp in (3, 6, 10):
    for sl in (50, 100, 200, 400, None):
        res, worst = [], 0
        for i, d in zip(ent, side):
            e = O[i] + d * SPREAD / 2; r = None
            for j in range(i, n):
                if dk[j] != dk[i] or mins[j] >= 955: r = (O[j] - e) * d - SPREAD / 2; break          # still open at 15:55: closed at market
                adverse = (e - L[j]) if d == 1 else (H[j] - e)
                if sl is not None and adverse >= sl: r = -sl - SPREAD / 2; break
                fav = (H[j] - e) if d == 1 else (e - L[j])
                if fav >= tp + SPREAD / 2: r = tp; break
            res.append(r)
        r = np.array(res); losses = r[r < 0]
        # streak of wins before the first loss, from many random starting points
        idx_loss = np.where(r < 0)[0]
        streaks = np.diff(np.concatenate([[-1], idx_loss])) - 1
        rows.append(dict(take_profit=f"+{tp} pts (+${tp*LOTS})", give_up_at="close 15:55 only" if sl is None else f"-{sl} pts (-${sl*LOTS:,})",
                         win_pct=round(100 * (r > 0).mean(), 1), median_wins_before_a_loss=int(np.median(streaks)) if len(streaks) else len(r),
                         avg_loss_usd=round(LOTS * losses.mean()) if len(losses) else 0, worst_loss_usd=round(LOTS * r.min()),
                         avg_per_trade_usd=round(LOTS * r.mean()), total_8000_trades_usd=round(LOTS * r.sum())))
pd.set_option("display.width", 250); print(pd.DataFrame(rows).to_string(index=False))
