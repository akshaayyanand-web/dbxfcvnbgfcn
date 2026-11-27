"""Build the 6 add-on EAs (MT5_EAs/addons/) from the pack's existing EAs, so they share the same guard, sizing,
news block, request counter, stagger and duplicate-entry protection. Rules = exactly the tested Python versions."""
import re, os
SRCD = "MT5_EAs"; OUT = "MT5_EAs/addons"; os.makedirs(OUT, exist_ok=True)
def header(text, lines, tf, magic, risk):
    a = text.index("//+"); b = text.index("#property")
    hdr = "//+------------------------------------------------------------------+\n" + "".join(f"//| {l}\n" for l in lines) + "//+------------------------------------------------------------------+\n"
    text = text[:a] + hdr + text[b:]
    text = re.sub(r"#define REQUIRED_TF PERIOD_\w+", f"#define REQUIRED_TF PERIOD_{tf}", text)
    text = re.sub(r"input double InpRiskPct = [0-9.]+;", f"input double InpRiskPct = {risk};", text)
    return re.sub(r"input long   InpMagic   = \d+;", f"input long   InpMagic   = {magic};", text)
sol = open(f"{SRCD}/optional/SOL_Dip_1h.mq5").read()
def dip(name, chart, tf, hold, magic, tag):
    t = header(sol, [f"{name} - MT5 EA. Chart: {chart}, {tf}. Add-on (Nov 2026), same rule as SOL Dip 1h on a new market/timeframe.",
                     f"Buy when RSI(2) < 15 and close > EMA(200), unless yesterday's daily close is >8% below the close 30 days earlier.",
                     f"Stop 2 x ATR(14) below the signal close (on the order). Exit after {hold} bars (96 hours). Long only.",
                     "Tested: beats 95-100% of random-entry runs with the same exits; survives double costs, a one-bar delay and nearby settings."], tf, magic, 0.15)
    assert t.count("144") >= 2
    t = t.replace("iBarShift(_Symbol, _Period, ot) >= 144", f"iBarShift(_Symbol, _Period, ot) >= {hold}").replace("Time exit (144 bars)", f"Time exit ({hold} bars)").replace('"SOL Dip 1h"', f'"{tag}"')
    open(f"{OUT}/{name.replace(' ', '_')}.mq5", "w").write(t)
dip("BTC Dip 1h", "BTCUSD", "H1", 96, 1131, "BTC Dip 1h")
dip("Gold Dip 4h", "XAUUSD", "H4", 24, 1132, "Gold Dip 4h")
dip("NQ Dip 1h", "US100 / NAS100", "H1", 96, 1133, "NQ Dip 1h")
orb = open(f"{SRCD}/NQ_Opening_Range.mq5").read()
t = header(orb, ["Nasdaq Opening-Range Breakout 30 - MT5 EA. Chart: US100 / NAS100 / USTEC, M5 (New York clock). Add-on (Nov 2026).",
                 "Range = 09:30-10:00 New York. First M5 close outside it until 12:00 New York -> buy / sell, stop at the other side",
                 "of the range, target 2 x risk (both on the order). One trade per day. Flat at 15:55 NY. Thin edge: demo first."], "M5", 1134, 0.15)
for a, b in (("if(m >= 570 && m < 585)", "if(m >= 570 && m < 600)"), ("if(m1 < 585 || m1 >= 690 || day == lastTradeDay) return;  // signal bars 09:45 .. 11:25", "if(m1 < 600 || m1 >= 720 || day == lastTradeDay) return;  // signal bars 10:00 .. 11:55"), ('"NQ ORB"', '"NQ ORB30"')):
    assert a in t, a; t = t.replace(a, b)
open(f"{OUT}/NQ_Opening_Range_30.mq5", "w").write(t)
base = orb[:orb.index("\nint lastTradeDay = 0;")]
NB = r'''
input double InpBandK        = 1.0;    // Noise band width (x the average move from the open at this minute)
input int    InpLookbackDays = 14;     // Sessions used for the average move
// Builds the session statistics from M1 bars: today's 09:30 open, the previous session's 15:59 close, the average
// |close/open - 1| at minute m over the previous InpLookbackDays sessions, and today's VWAP (tick volume).
bool SessionStats(int m, double &sigma, double &openT, double &prevC, double &vwap)
  {
   MqlRates r[]; ArraySetAsSeries(r, true);
   int got = CopyRates(_Symbol, PERIOD_M1, 1, 30000, r);
   if(got < 3000) return false;
   int keys[60]; double op[60], atm[60], lc[60]; int nd = 0; double pv = 0, vv = 0;
   for(int i = 0; i < 60; i++) { keys[i] = 0; op[i] = 0; atm[i] = 0; lc[i] = 0; }
   int today = DayKey(ToNY(r[0].time));
   for(int i = 0; i < got && nd < 60; i++)
     {
      datetime nt = ToNY(r[i].time); int dk = DayKey(nt), mm = MinuteOfDay(nt) - 570;
      if(mm < 0 || mm >= 390) continue;
      int ix = -1;
      for(int j = 0; j < nd; j++) if(keys[j] == dk) { ix = j; break; }
      if(ix < 0) { if(nd >= 60) break; ix = nd; keys[nd] = dk; nd++; }
      if(mm == 0) op[ix] = r[i].open;
      if(mm == m) atm[ix] = r[i].close;
      if(mm == 389) lc[ix] = r[i].close;
      if(dk == today) { double w = r[i].tick_volume > 0 ? (double)r[i].tick_volume : 1.0; pv += (r[i].high + r[i].low + r[i].close) / 3.0 * w; vv += w; }
     }
   if(nd < 2 || keys[0] != today || op[0] <= 0 || vv <= 0) return false;
   openT = op[0]; vwap = pv / vv; prevC = 0;
   for(int j = 1; j < nd; j++) if(lc[j] > 0) { prevC = lc[j]; break; }
   double s = 0; int n = 0, used = 0;
   for(int j = 1; j < nd && used < InpLookbackDays; j++)
     {
      if(op[j] <= 0) continue;
      used++;
      if(atm[j] > 0) { s += MathAbs(atm[j] / op[j] - 1); n++; }
     }
   if(used < InpLookbackDays || n == 0 || prevC <= 0) return false;
   sigma = s / n; return true;
  }
void OnNewBar()
  {
   ulong tk; long tp; datetime ot;
   datetime n1 = ToNY(iTime(_Symbol, _Period, 1));
   int m = MinuteOfDay(n1) - 570; bool check = (m >= 30 && m < 390 && m % 30 == 29);
   bool inPos = MyPosition(tk, tp, ot);
   if(inPos && m >= 385 && m < 390) { CloseMine("Flat before the 16:00 New York close"); return; }
   if(!check) return;
   double sigma, openT, prevC, vwap;
   if(!SessionStats(m, sigma, openT, prevC, vwap)) return;
   double ub = MathMax(openT, prevC) * (1 + InpBandK * sigma), lb = MathMin(openT, prevC) * (1 - InpBandK * sigma), c1 = iClose(_Symbol, _Period, 1);
   if(inPos)
     {
      if(tp == POSITION_TYPE_BUY && c1 < MathMax(ub, vwap)) CloseMine("Back inside the band / below VWAP");
      if(tp == POSITION_TYPE_SELL && c1 > MathMin(lb, vwap)) CloseMine("Back inside the band / above VWAP");
      return;
     }
   if(m >= 355) return;                                                  // no new trades in the last 35 minutes
   int dir = c1 > ub ? 1 : (c1 < lb ? -1 : 0);
   if(dir == 0) return;
   double price = dir == 1 ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double risk = InpBandK * sigma * openT;
   OpenTrade(dir, price - dir * risk, 0, "Noise Band NQ");
  }
'''
t = header(base, ["Noise Band NQ - MT5 EA. Chart: US100 / NAS100 / USTEC, M1 (New York clock). Add-on (Nov 2026).",
                  "Zarattini, Aziz & Barbon (2024) intraday momentum. Band = max/min(today's open, yesterday's close) x (1 +/- k x the average",
                  "move from the open at this minute over the last 14 sessions). Every 30 min from 10:00: close above the band -> buy, below -> sell.",
                  "Hard stop one band width away; at each check exit when price is back inside the band or past VWAP; flat 15:55 NY.",
                  "Beats random entries, but the edge is thin (double costs leave +0.02R): demo first and compare live spreads."], "M1", 1135, 0.2) + NB
open(f"{OUT}/Noise_Band_NQ_1m.mq5", "w").write(t)
JUMP = r'''
input double InpJumpSigma = 4.0;   // Bar move threshold (x the std of 15-minute moves over the last 200 bars)
input int    InpMaxBars   = 50;    // Close after this many bars
void OnNewBar()
  {
   ulong tk; long tp; datetime ot;
   double atr = AtrRma(14, 1);
   if(atr == EMPTY_VALUE) return;
   if(MyPosition(tk, tp, ot))
     {
      int held = iBarShift(_Symbol, _Period, ot);
      if(held >= InpMaxBars) { CloseMine("Time exit"); return; }
      double best = tp == POSITION_TYPE_BUY ? -DBL_MAX : DBL_MAX;
      for(int i = 1; i <= held; i++) { double c = iClose(_Symbol, _Period, i); best = tp == POSITION_TYPE_BUY ? MathMax(best, c) : MathMin(best, c); }
      if(held < 1 || !PositionSelectByTicket(tk)) return;
      double sl = PositionGetDouble(POSITION_SL), nsl = NormalizeDouble(tp == POSITION_TYPE_BUY ? best - 3 * atr : best + 3 * atr, _Digits);
      double px = tp == POSITION_TYPE_BUY ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double minDist = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
      bool better = tp == POSITION_TYPE_BUY ? (nsl > sl + _Point && nsl < px - minDist) : (nsl < sl - _Point && nsl > px + minDist);
      if(better && !trade.PositionModify(tk, nsl, PositionGetDouble(POSITION_TP))) Print("trail modify failed ", trade.ResultRetcode());
      return;
     }
   double c[]; ArraySetAsSeries(c, true);
   if(CopyClose(_Symbol, _Period, 1, 202, c) < 202) return;
   double mean = 0, ss = 0; int n = 200;
   for(int i = 1; i <= n; i++) mean += c[i - 1] - c[i];
   mean /= n;
   for(int i = 1; i <= n; i++) { double d = c[i - 1] - c[i] - mean; ss += d * d; }
   double sd = MathSqrt(ss / (n - 1)), mv = c[0] - c[1];
   if(sd <= 0 || MathAbs(mv) <= InpJumpSigma * sd) return;
   int dir = mv > 0 ? 1 : -1;
   double price = dir == 1 ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   OpenTrade(dir, price - dir * 2 * atr, 0, "BTC Jump");
  }
'''
t = header(base, ["BTC Jump 15m - MT5 EA. Chart: BTCUSD, M15. Add-on (Nov 2026), list-2 strategy #448 'jump direction persistence'.",
                  "A 15-minute close more than 4 standard deviations (last 200 bars) from the previous close -> trade in its direction.",
                  "Stop 2 x ATR(14); the stop then trails 3 x ATR behind the best close; close after 50 bars. One position at a time.",
                  "Needs tight fills: double costs or a one-bar delay remove most of the edge. Demo first and compare live spreads."], "M15", 1136, 0.1) + JUMP
open(f"{OUT}/BTC_Jump_15m.mq5", "w").write(t)
print(sorted(os.listdir(OUT)))
