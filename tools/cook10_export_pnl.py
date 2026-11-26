# Daily P&L of the 21-EA The5ers pack (3x preset risks, $10K), simulated from the backtested trades. Server day = UTC+2.
exec(open("firms.py").read().split('\nif __name__ == "__main__":')[0])
W = {c: min(PORT["21"][c] * 3.0, 1.0 / BASE[c]) for c in NAMES}
NICE = {"btc": "BTC_Dip_v3", "btcgap": "BTC_Weekend_Gap", "btcrev": "BTC_Revert_5m", "sol": "SOL_Dip_1h", "solrev": "SOL_Revert_5m", "xrprev": "XRP_Revert_5m",
        "gdip": "Gold_Dip", "gasia": "Gold_Asia_Breakout", "gmom": "Gold_Intraday_Momentum", "goldvwap": "Gold_VWAP_Pullback_5m", "nq2h": "NQ_Dip_2h", "orb15": "NQ_Opening_Range",
        "nqbo15": "NQ_Breakout_15m", "nqfade": "NQ_Open_Fade_1m", "spx1h": "SPX_Dip_1h", "spxbo5": "SPX_Breakout_5m", "spxfade": "Open_Fade_1m_SPX", "daxorb": "DAX_Opening_Range",
        "daxpm": "DAX_Premarket_15m", "oil1h": "Oil_Dip_1h", "nikkei": "Nikkei_Breakout_5m"}
day = (idx + pd.Timedelta(hours=2)).tz_convert(None).normalize()
cols = {}
for c in NAMES: cols[NICE[c]] = pd.Series(W[c] * COMP[c][0], idx).groupby(day).sum()
D = pd.DataFrame(cols); D = D.loc["2016-01-04":]
book_h = pd.Series(sum(W[c] * COMP[c][0] for c in NAMES), idx); low_h = pd.Series(sum(W[c] * COMP[c][1] for c in NAMES), idx)
cum_prev = book_h.groupby(day).cumsum() - book_h; worst = (cum_prev + low_h).groupby(day).min()
D["BOOK_total"] = D[[NICE[c] for c in NAMES]].sum(axis=1); D["BOOK_worst_intraday"] = worst.reindex(D.index)
D = D[(D.index.dayofweek < 5) | (D.abs().sum(axis=1) > 0)]
D = (100 * D).round(4); D.index.name = "server_date"
D.to_csv("pack21_daily_pnl.csv")
risk = pd.DataFrame({"EA": [NICE[c] for c in NAMES], "risk_per_trade_pct_of_balance": [round(100 * W[c] * BASE[c], 3) for c in NAMES],
                     "first_trade_day": [D[NICE[c]].ne(0).idxmax().date() for c in NAMES]})
risk.to_csv("pack21_risk_table.csv", index=False)
b = D.BOOK_total / 100; S = "2023-01-01"
print(len(D), "days", D.index[0].date(), "->", D.index[-1].date())
print("annual % (sum of daily):", (b.groupby(b.index.year).sum() * 100).round(1).to_dict())
print(f"worst closed day {D.BOOK_total.min():.2f}% on {D.BOOK_total.idxmin().date()} | worst intraday {D.BOOK_worst_intraday.min():.2f}% on {D.BOOK_worst_intraday.idxmin().date()}")
print("Sharpe 2016-22 / 2023-26:", round(b[:S].mean() / b[:S].std() * np.sqrt(252), 2), round(b[S:].mean() / b[S:].std() * np.sqrt(252), 2))
