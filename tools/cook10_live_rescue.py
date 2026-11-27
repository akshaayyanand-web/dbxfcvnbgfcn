# From the user's live state (equity $9,443.28, static floor $9,000, target $11,000 shown on the dashboard), what happens next?
# Replays the 21-EA pack's daily P&L (3x presets, % of $10K) from every historical start day, with the EA guard approximated:
# daily stop -4% (day capped at -4.3%), room cap (size x min(1, (day-start equity - 9000) / 800)), max-loss check on the intraday low.
import numpy as np, pandas as pd
P = pd.read_csv("/home/user/dbxfcvnbgfcn/research/results/cook10/export/pack21_daily_pnl.csv", parse_dates=["server_date"], index_col="server_date")
d = (P.BOOK_total * 100).to_numpy(); w = (P.BOOK_worst_intraday * 100).to_numpy()          # dollars on $10K
starts = np.where((P.index >= "2020-09-01") & (P.index <= "2025-10-31"))[0]
def go(i, mult, eq0=9443.28, target=11000.0, floor=9000.0, maxdays=250):
    eq = eq0
    for j in range(i, min(i + maxdays, len(d))):
        s = mult * max(0.0, min(1.0, (eq - floor) / 800.0))
        if eq + s * w[j] <= floor or s * w[j] <= -500: return "fail", j - i
        eq += max(s * d[j], -430.0)
        if eq <= floor: return "fail", j - i
        if eq >= target: return "pass", j - i
    return "open", maxdays
rows = []
for tgt, lab in ((11000, "$1,000 goal (shown)"), (10800, "8% goal")):
    for m in (0.5, 0.75, 1.0, 1.25, 1.5):
        r = [go(i, m, target=tgt) for i in starts]; o = np.array([x[0] for x in r]); dd = np.array([x[1] for x in r])
        rows.append(dict(goal=lab, risk=f"{m:.2f} x preset", passes=f"{100*np.mean(o=='pass'):.0f}%", fails=f"{100*np.mean(o=='fail'):.0f}%", still_open_after_1yr=f"{100*np.mean(o=='open'):.0f}%",
                         median_trading_days_to_pass=np.median(dd[o == "pass"]) if (o == "pass").any() else np.nan, pass_within_40_trading_days=f"{100*np.mean((o=='pass') & (dd <= 40)):.0f}%"))
R = pd.DataFrame(rows); pd.set_option("display.width", 220); print(R.to_string(index=False))
# how unusual is being -5.6% this early? lowest point within the first 10 trading days of a fresh start at 3x
lows = [np.min(np.cumsum(d[i:i + 10]) + np.r_[0, np.cumsum(d[i:i + 9])] * 0 + np.minimum(0, w[i:i + 10])) for i in starts]
print(f"\nfresh starts whose equity dipped to -$557 or worse within 10 trading days: {100*np.mean(np.array(lows) <= -557):.0f}%")
