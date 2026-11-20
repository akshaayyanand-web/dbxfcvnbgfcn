exec(open("combo10.py").read().split('\nif __name__ == "__main__":')[0])
def run(sc, cap, edge):
    build({c: (min(PORT["21"][c] * sc, cap / BASE[c])) for c in NAMES})
    d = pd.Series(EQ_R, idx).groupby(idx.normalize()).sum().loc["2020-09-01":]
    d = d - (1 - edge) * d.mean()                      # same swings, smaller average profit
    eq = (1 + d.clip(lower=-0.99)).cumprod(); dd = (eq / eq.cummax() - 1)
    yr = np.array([(eq.iloc[min(i + 365, len(eq) - 1)] / eq.iloc[i] - 1) for i in range(0, len(eq) - 365, 7)])
    return dict(risk=f"{sc:g}x", per_trade_cap=f"{cap:g}%", edge=f"{edge:.0%} of backtest", yr_median=f"{100*np.median(yr):.0f}%", yr_p10=f"{100*np.percentile(yr,10):.0f}%",
                yr_worst=f"{100*yr.min():.0f}%", losing_years=f"{100*(yr < 0).mean():.0f}%", max_drawdown=f"{100*dd.min():.0f}%", worst_day=f"{100*d.min():.1f}%",
                max_risk_per_trade=f"{max(BASE[c] * min(PORT['21'][c] * sc, cap / BASE[c]) for c in NAMES):.1f}%")
for sc, cap in ((1, 1.0), (3, 1.0), (10, 1.0), (10, 100.0)):
    for edge in (1.0, 0.5, 0.33):
        print(run(sc, cap, edge), flush=True)
