"""Swing + intraday prop portfolio: BTC Dip v3, Gold Dip, Gold Asia breakout, NQ intraday momentum.

Weights are picked on 12-month windows started in 2020-2022 (fresh account, never touching 8% max / 4% daily),
then checked on 2024-2026, 67 rolling prop windows and an FTMO-style 2-step evaluation.
Usage: python3 portfolio_intraday.py DATA_DIR   (DATA_DIR holds kh/BTCUSDT.csv and fut/XAUUSD.csv, fut/USATECHIDXUSD.csv)
"""
import itertools, sys, numpy as np, pandas as pd
from backtest_ema_macd import load
from futures_lab import load_csv
import portfolio_prop as P, intraday_lab as I
S=sys.argv[1]
btc=load(S+"/kh/BTCUSDT.csv").loc["2019-06-01":]; gold=load_csv(S+"/fut/XAUUSD.csv"); nq=load_csv(S+"/fut/USATECHIDXUSD.csv")
idx=pd.date_range(pd.Timestamp("2020-04-01",tz="UTC"),pd.Timestamp("2026-10-30",tz="UTC"),freq="1h")
comps={}
t,c=P.dip_trades(btc,"2h",3,20,0.15,P.FEE_CRYPTO); comps["btc_dip"]=P.trade_series(t,c,btc,idx)
t,c=P.dip_trades(gold,"1h",2,10,0.08,P.COST["XAUUSD"]); comps["gold_dip"]=P.trade_series(t,c,gold,idx)
ga=I.range_breakout(gold,"Europe/London",0,7,7,14,20,"mid",None,True,I.COST["XAUUSD"]); comps["gold_asia"]=P.trade_series([x[:5] for x in ga],I.COST["XAUUSD"],gold,idx)
nm=I.intraday_momentum(nq,"America/New_York",16,11,15,0.006,True,True,I.COST["USATECHIDXUSD"]); comps["nq_imom"]=P.trade_series([x[:5] for x in nm],I.COST["USATECHIDXUSD"],nq,idx)
names=list(comps); R=np.array([comps[k][0] for k in names]); LO=np.array([comps[k][1] for k in names])
d=pd.DataFrame(R.T,index=idx,columns=names).resample("1D").sum(); print("daily correlations:"); print(d[d.abs().sum(axis=1)>0].corr().round(2).to_string())
grid=dict(btc_dip=[0.5,1.0,1.5],gold_dip=[0,0.25,0.5],gold_asia=[0,0.25,0.5,0.75,1.0],nq_imom=[0,0.25,0.5,0.75,1.0])
tr_starts=pd.date_range("2020-04-01","2022-12-01",freq="MS",tz="UTC"); tr1=pd.Timestamp("2024-01-01",tz="UTC")
rows=[]
for combo in itertools.product(*grid.values()):
    w=np.array(combo,float)
    wins=[P.evaluate(R,LO,idx,w,s,min(s+pd.DateOffset(years=1),tr1),max_loss=0.08,daily=0.04) for s in tr_starts]
    p=np.array([x["ret"] for x in wins])*100
    rows.append(dict(zip(names,combo),breaches=sum(x["breach"] for x in wins),med=np.median(p),worst=p.min()))
res=pd.DataFrame(rows); ok=res[res.breaches==0].sort_values("med",ascending=False)
print(f"\n{len(res)} weight sets, {len(ok)} safe on 2020-22 windows. Top 8:"); print(ok.head(8).round(1).to_string(index=False))
days=idx.floor("D")
def phase(w,h0,target):
    r=(R[:,h0:]*w[:,None]).sum(0); lo=(LO[:,h0:]*w[:,None]).sum(0); eq=1.0; day=None; halt=None
    for k in range(len(r)):
        dd=days[h0+k]
        if dd!=day: day=dd; dopen=eq
        if halt==dd: continue
        low=eq*(1+lo[k])
        if low<=0.90 or low<=dopen*0.95: return "fail",k
        eq*=1+r[k]
        if eq>=1+target: return "pass",k
        if 1-eq/dopen>=0.04: halt=dd
    return "open",len(r)
starts=pd.date_range("2020-04-01","2025-09-01",freq="7D",tz="UTC"); wstarts=pd.date_range("2020-04-01","2025-10-01",freq="MS",tz="UTC")
picks={"OLD: BTC 1% + gold dip 0.5%":np.array([1.0,0.5,0,0]),"NEW best (picked on 2020-22)":ok.iloc[0][names].to_numpy(float)}
if len(ok)>1: picks["NEW 2nd best"]=ok.iloc[1][names].to_numpy(float)
print("\nOut-of-sample + FTMO-style 2-step (10%/5%, guard ON):")
for name,w in picks.items():
    te=P.evaluate(R,LO,idx,w,tr1,None); yrs=(idx[-1]-tr1).days/365
    wins=[P.evaluate(R,LO,idx,w,s,s+pd.DateOffset(years=1),guard=True) for s in wstarts]; p=np.array([x["ret"] for x in wins])*100
    both=[]
    for s in starts:
        h0=idx.searchsorted(s); a,k1=phase(w,h0,0.10)
        if a!="pass": both.append((a,None)); continue
        b,k2=phase(w,h0+k1+1,0.05); both.append(("pass",(k1+k2)/24) if b=="pass" else (b,None))
    dd=np.array([x[1] for x in both if x[1] is not None]); n=len(both)
    yr={y:f"{100*P.evaluate(R,LO,idx,w,pd.Timestamp(f'{y}-01-01',tz='UTC'),pd.Timestamp(f'{y+1}-01-01',tz='UTC'))['ret']:+.0f}%" for y in range(2020,2027)}
    print(f"  {name:<30} {dict(zip(names,w))}")
    print(f"     2024-26 {100*((1+te['ret'])**(1/yrs)-1):+.1f}%/yr maxDD {100*te['dd']:.1f}% | prop windows median {np.median(p):+.1f}% avg {p.mean():+.1f}% breaches {sum(x['breach'] for x in wins)}/{len(wins)}"
          f" | 2-step pass {100*sum(x[0]=='pass' for x in both)/n:.0f}% fail {100*sum(x[0]=='fail' for x in both)/n:.0f}% median {np.median(dd):.0f}d <=60d {100*np.sum(dd<=60)/n:.0f}% <=90d {100*np.sum(dd<=90)/n:.0f}%")
    print("     years:",yr)
