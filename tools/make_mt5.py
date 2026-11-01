"""Generate the six MT5 Expert Advisors in strategies/mt5/ from one shared code block.

Each EA is self-contained (no include files): common time-zone, sizing and account-guard code plus the
strategy's own OnNewBar() logic. Run: python3 tools/make_mt5.py
"""
import os

COMMON = r'''
#include <Trade/Trade.mqh>
CTrade trade;

//--- common inputs
input double InpAccountSize      = 200000; // Starting balance of the prop account
input double InpDailyStopPct     = 4.0;    // ACCOUNT guard: stop for the day at this loss (% of start; firm limit 5)
input double InpMaxStopPct       = 8.0;    // ACCOUNT guard: stop everything at this loss from start (firm limit 10)
input double InpGuardShare       = 60;     // A trade may risk at most this % of the remaining daily / max room
input bool   InpAutoServerOffset = true;   // Live: detect the server's GMT offset automatically
input int    InpServerGMTOffset  = 2;      // Tester: server GMT offset in winter (FTMO-style servers: 2)
input bool   InpServerUsesUSDST  = true;   // Tester: server shifts +1h with US daylight saving (FTMO-style)

//--- time helpers -------------------------------------------------------------
datetime MakeDate(int y, int m, int d) { MqlDateTime s; ZeroMemory(s); s.year = y; s.mon = m; s.day = d; return StructToTime(s); }
datetime NthSunday(int y, int m, int n)
  {
   datetime first = MakeDate(y, m, 1); MqlDateTime s; TimeToStruct(first, s);
   int add = (7 - s.day_of_week) % 7;
   return first + (add + 7 * (n - 1)) * 86400;
  }
datetime LastSunday(int y, int m)
  {
   datetime nxt = (m == 12) ? MakeDate(y + 1, 1, 1) : MakeDate(y, m + 1, 1);
   datetime last = nxt - 86400; MqlDateTime s; TimeToStruct(last, s);
   return last - s.day_of_week * 86400;
  }
int YearOf(datetime t) { MqlDateTime s; TimeToStruct(t, s); return s.year; }
bool IsUSDST(datetime utc) { int y = YearOf(utc); return utc >= NthSunday(y, 3, 2) + 7 * 3600 && utc < NthSunday(y, 11, 1) + 6 * 3600; }
bool IsUKDST(datetime utc) { int y = YearOf(utc); return utc >= LastSunday(y, 3) + 3600 && utc < LastSunday(y, 10) + 3600; }
int ServerOffset(datetime serverT)
  {
   if(InpAutoServerOffset && !MQLInfoInteger(MQL_TESTER))
      return (int)MathRound((double)(TimeTradeServer() - TimeGMT()) / 3600.0);
   int off = InpServerGMTOffset;
   if(InpServerUsesUSDST && IsUSDST(serverT - off * 3600)) off += 1;
   return off;
  }
datetime ToUTC(datetime s)    { return s - ServerOffset(s) * 3600; }
datetime ToNY(datetime s)     { datetime u = ToUTC(s); return u - (IsUSDST(u) ? 4 : 5) * 3600; }
datetime ToLondon(datetime s) { datetime u = ToUTC(s); return u + (IsUKDST(u) ? 3600 : 0); }
int HourOf(datetime t)   { MqlDateTime s; TimeToStruct(t, s); return s.hour; }
int MinuteOfDay(datetime t) { MqlDateTime s; TimeToStruct(t, s); return s.hour * 60 + s.min; }
int DayKey(datetime t)   { MqlDateTime s; TimeToStruct(t, s); return s.year * 10000 + s.mon * 100 + s.day; }

//--- positions ------------------------------------------------------------------
bool MyPosition(ulong &ticket, long &type, datetime &openTime)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      ticket = tk; type = PositionGetInteger(POSITION_TYPE); openTime = (datetime)PositionGetInteger(POSITION_TIME);
      return true;
     }
   return false;
  }
void CloseMine(string why)
  {
   ulong tk; long tp; datetime ot;
   while(MyPosition(tk, tp, ot))
     {
      if(!trade.PositionClose(tk)) { Print(why, ": close failed ", trade.ResultRetcode()); break; }
      Print(why, ": position closed");
     }
  }

//--- account-level prop guard ------------------------------------------------------
double DayStartBalance()
  {
   string n = "PP_DS_" + IntegerToString(DayKey(TimeTradeServer()));
   if(!GlobalVariableCheck(n)) GlobalVariableSet(n, AccountInfoDouble(ACCOUNT_BALANCE));
   return GlobalVariableGet(n);
  }
bool GuardBlocks()
  {
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   string dayHalt = "PP_DH_" + IntegerToString(DayKey(TimeTradeServer()));
   if(GlobalVariableCheck("PP_HALT")) { CloseMine("Guard (max loss)"); return true; }
   if(GlobalVariableCheck(dayHalt))   { CloseMine("Guard (daily)");    return true; }
   if(eq <= InpAccountSize * (1 - InpMaxStopPct / 100))
     { GlobalVariableSet("PP_HALT", 1); CloseMine("Guard (max loss)"); return true; }
   if(DayStartBalance() - eq >= InpAccountSize * InpDailyStopPct / 100)
     { GlobalVariableSet(dayHalt, 1); CloseMine("Guard (daily)"); return true; }
   return false;
  }
double RiskMoney()
  {
   double bal = AccountInfoDouble(ACCOUNT_BALANCE), eq = AccountInfoDouble(ACCOUNT_EQUITY);
   double r = bal * InpRiskPct / 100;
   double dayRoom = InpAccountSize * InpDailyStopPct / 100 - MathMax(0, DayStartBalance() - eq);
   double maxRoom = eq - InpAccountSize * (1 - InpMaxStopPct / 100);
   r = MathMin(r, MathMin(dayRoom, maxRoom) * InpGuardShare / 100);
   return MathMax(r, 0);
  }
double LotsFor(double riskMoney, double stopDist, ENUM_ORDER_TYPE type, double price)
  {
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickVal  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
   if(tickVal <= 0) tickVal = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   if(stopDist <= 0 || tickSize <= 0 || tickVal <= 0) return 0;
   double lossPerLot = stopDist / tickSize * tickVal;
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP), vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN), vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lots = MathFloor(riskMoney / lossPerLot / step) * step;
   if(lots < vmin) return 0;              // stop too wide for the allowed risk: skip the trade
   lots = MathMin(lots, vmax);
   double margin;
   while(lots >= vmin && OrderCalcMargin(type, _Symbol, lots, price, margin) && margin > AccountInfoDouble(ACCOUNT_MARGIN_FREE) * 0.9)
      lots -= step;
   return lots >= vmin ? NormalizeDouble(lots, 8) : 0;
  }
bool OpenTrade(int dir, double stopPrice, double tpPrice, string tag)
  {
   double price = dir == 1 ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double dist = MathAbs(price - stopPrice);
   if(dir * (price - stopPrice) <= 0) { Print(tag, ": price already beyond the stop, skipped"); return false; }
   double lots = LotsFor(RiskMoney(), dist, dir == 1 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL, price);
   if(lots <= 0) { Print(tag, ": size below minimum for the allowed risk, skipped"); return false; }
   double sl = NormalizeDouble(stopPrice, _Digits), tp = tpPrice > 0 ? NormalizeDouble(tpPrice, _Digits) : 0;
   bool ok = dir == 1 ? trade.Buy(lots, _Symbol, 0, sl, tp, tag) : trade.Sell(lots, _Symbol, 0, sl, tp, tag);
   Print(tag, ok ? " opened " : " FAILED ", lots, " lots, SL ", sl, " TP ", tp, " retcode ", trade.ResultRetcode());
   return ok;
  }

//--- indicators -------------------------------------------------------------------
double Rsi(int len, int shift)
  {
   static int handles[10]; static int lens[10]; static int n = 0;
   int h = INVALID_HANDLE;
   for(int i = 0; i < n; i++) if(lens[i] == len) h = handles[i];
   if(h == INVALID_HANDLE && n < 10) { h = iRSI(_Symbol, _Period, len, PRICE_CLOSE); handles[n] = h; lens[n] = len; n++; }
   double b[]; ArraySetAsSeries(b, true);
   if(CopyBuffer(h, 0, shift, 1, b) < 1) return EMPTY_VALUE;
   return b[0];
  }
double Ema(int len, int shift)
  {
   static int h = INVALID_HANDLE; static int hl = 0;
   if(h == INVALID_HANDLE || hl != len) { h = iMA(_Symbol, _Period, len, 0, MODE_EMA, PRICE_CLOSE); hl = len; }
   double b[]; ArraySetAsSeries(b, true);
   if(CopyBuffer(h, 0, shift, 1, b) < 1) return EMPTY_VALUE;
   return b[0];
  }
double AtrRma(int len, int shift)   // Wilder ATR (same as TradingView ta.atr / the Python tests)
  {
   MqlRates r[]; ArraySetAsSeries(r, false);
   int got = CopyRates(_Symbol, _Period, shift, 500, r);
   if(got < len + 2) return EMPTY_VALUE;
   double a = r[1].high - r[1].low;
   for(int i = 1; i < got; i++)
     {
      double tr = MathMax(r[i].high - r[i].low, MathMax(MathAbs(r[i].high - r[i - 1].close), MathAbs(r[i].low - r[i - 1].close)));
      a = (i == 1) ? tr : a + (tr - a) / len;
     }
   return a;
  }

//--- event plumbing -----------------------------------------------------------------
void OnNewBar();
int OnInit()
  {
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(50);
   trade.SetTypeFillingBySymbol(_Symbol);
   if(_Period != REQUIRED_TF) Print("WARNING: attach this EA to a ", EnumToString(REQUIRED_TF), " chart");
   return INIT_SUCCEEDED;
  }
void OnTick()
  {
   bool blocked = GuardBlocks();
   static datetime lastBar = 0;
   datetime b0 = iTime(_Symbol, _Period, 0);
   if(b0 == lastBar) return;
   lastBar = b0;
   if(blocked || _Period != REQUIRED_TF) return;
   OnNewBar();
  }
'''

EAS = {
"BTC_Dip_v3.mq5": dict(tf="PERIOD_H2", magic=1101, risk=1.0, header='''//+------------------------------------------------------------------+
//| BTC Dip v3 – MT5 EA. Chart: BTCUSD (or your broker's BTC symbol), H2
//| Buy when RSI(3) < 20 and close > EMA(50), unless the daily close is >15% below the close 30 days
//| earlier. Stop 2 x ATR(14) below the signal close (on the order). Exit after 48 H2 bars (4 days).
//| Portfolio risk: 1.0% per trade.  Python test 2020-2026: ~+20%/yr at 1% risk on its own.
//+------------------------------------------------------------------+''', body='''
void OnNewBar()
  {
   ulong tk; long tp; datetime ot;
   if(MyPosition(tk, tp, ot))
     {
      if(iBarShift(_Symbol, _Period, ot) >= 48) CloseMine("Time exit (4 days)");
      return;
     }
   double c1 = iClose(_Symbol, _Period, 1), rsi = Rsi(3, 1), ema = Ema(50, 1), atr = AtrRma(14, 1);
   if(rsi == EMPTY_VALUE || ema == EMPTY_VALUE || atr == EMPTY_VALUE) return;
   double d30 = iClose(_Symbol, PERIOD_D1, 1) / iClose(_Symbol, PERIOD_D1, 31) - 1;
   if(d30 < -0.15) return;                                  // crash filter
   if(rsi < 20 && c1 > ema) OpenTrade(1, c1 - 2 * atr, 0, "BTC Dip v3");
  }
'''),
"Gold_Dip.mq5": dict(tf="PERIOD_H1", magic=1102, risk=0.5, header='''//+------------------------------------------------------------------+
//| Gold Dip – MT5 EA. Chart: XAUUSD, H1
//| Buy when RSI(2) < 10 and close > EMA(50), unless the daily close is >8% below the close 30 days
//| earlier. Stop 2 x ATR(14) below the signal close (on the order). Exit after 96 H1 bars.
//| Portfolio risk: 0.5% per trade.
//+------------------------------------------------------------------+''', body='''
void OnNewBar()
  {
   ulong tk; long tp; datetime ot;
   if(MyPosition(tk, tp, ot))
     {
      if(iBarShift(_Symbol, _Period, ot) >= 96) CloseMine("Time exit (96 bars)");
      return;
     }
   double c1 = iClose(_Symbol, _Period, 1), rsi = Rsi(2, 1), ema = Ema(50, 1), atr = AtrRma(14, 1);
   if(rsi == EMPTY_VALUE || ema == EMPTY_VALUE || atr == EMPTY_VALUE) return;
   double d30 = iClose(_Symbol, PERIOD_D1, 1) / iClose(_Symbol, PERIOD_D1, 31) - 1;
   if(d30 < -0.08) return;                                  // crash filter
   if(rsi < 10 && c1 > ema) OpenTrade(1, c1 - 2 * atr, 0, "Gold Dip");
  }
'''),
"Gold_Asia_Breakout.mq5": dict(tf="PERIOD_H1", magic=1103, risk=0.25, header='''//+------------------------------------------------------------------+
//| Gold Asia-Range Breakout – MT5 EA. Chart: XAUUSD, H1 (London clock)
//| Range = 00:00-07:00 London. First H1 close above / below it between 07:00 and 14:00 London -> buy /
//| sell, stop at the range middle (on the order). One trade per day. Flat at 20:00 London.
//| Portfolio risk: 0.25% per trade.
//+------------------------------------------------------------------+''', body='''
int lastTradeDay = 0;
void OnNewBar()
  {
   ulong tk; long tp; datetime ot;
   datetime l0 = ToLondon(iTime(_Symbol, _Period, 0)), l1 = ToLondon(iTime(_Symbol, _Period, 1));
   if(MyPosition(tk, tp, ot))
     {
      if(HourOf(l0) >= 20 || DayKey(l0) != DayKey(ToLondon(ot))) CloseMine("Flat 20:00 London");
      return;
     }
   int day = DayKey(l1), h1 = HourOf(l1);
   if(h1 < 7 || h1 >= 14 || day == lastTradeDay) return;
   double hi = -DBL_MAX, lo = DBL_MAX; int cnt = 0;
   for(int i = 1; i < 48; i++)
     {
      datetime lt = ToLondon(iTime(_Symbol, _Period, i));
      if(DayKey(lt) != day) break;
      if(HourOf(lt) < 7) { hi = MathMax(hi, iHigh(_Symbol, _Period, i)); lo = MathMin(lo, iLow(_Symbol, _Period, i)); cnt++; }
     }
   if(cnt < 4 || hi <= lo) return;
   double c1 = iClose(_Symbol, _Period, 1), mid = (hi + lo) / 2;
   int dir = c1 > hi ? 1 : (c1 < lo ? -1 : 0);
   if(dir == 0) return;
   lastTradeDay = day;
   OpenTrade(dir, mid, 0, "Gold Asia BO");
  }
'''),
"Gold_Intraday_Momentum.mq5": dict(tf="PERIOD_H1", magic=1104, risk=0.25, header='''//+------------------------------------------------------------------+
//| Gold Intraday Momentum – MT5 EA. Chart: XAUUSD, H1 (London clock)
//| Reference = close of the H1 bar ending 17:00 London (previous day). At 09:00 London, if gold moved
//| more than 0.6% from it, trade in that direction; stop 1.0 x ATR(24); exit 16:00 London.
//| Portfolio risk: 0.25% per trade.
//+------------------------------------------------------------------+''', body='''
void OnNewBar()
  {
   ulong tk; long tp; datetime ot;
   datetime l0 = ToLondon(iTime(_Symbol, _Period, 0)), l1 = ToLondon(iTime(_Symbol, _Period, 1));
   if(MyPosition(tk, tp, ot))
     {
      if(HourOf(l0) >= 16 || DayKey(l0) != DayKey(ToLondon(ot))) CloseMine("Exit 16:00 London");
      return;
     }
   if(HourOf(l1) != 8) return;                               // bar 08:00-09:00 London just closed
   double ref = 0;
   for(int i = 2; i < 120; i++)
      if(HourOf(ToLondon(iTime(_Symbol, _Period, i))) == 16) { ref = iClose(_Symbol, _Period, i); break; }
   double c1 = iClose(_Symbol, _Period, 1), atr = AtrRma(24, 1);
   if(ref <= 0 || atr == EMPTY_VALUE) return;
   double mv = c1 / ref - 1;
   int dir = mv > 0.006 ? 1 : (mv < -0.006 ? -1 : 0);
   if(dir != 0) OpenTrade(dir, c1 - dir * 1.0 * atr, 0, "Gold Intraday Mom");
  }
'''),
"NQ_Intraday_Momentum.mq5": dict(tf="PERIOD_H1", magic=1105, risk=0.25, header='''//+------------------------------------------------------------------+
//| Nasdaq Intraday Momentum – MT5 EA. Chart: US100 / NAS100 / USTEC, H1 (New York clock)
//| Reference = close of the H1 bar ending 16:00 New York (previous day). At 11:00 New York, if the index
//| moved more than 0.6% from it, trade in that direction; stop 1.5 x ATR(24); exit 15:00 New York.
//| Portfolio risk: 0.25% per trade. Flat every day before the US close.
//+------------------------------------------------------------------+''', body='''
void OnNewBar()
  {
   ulong tk; long tp; datetime ot;
   datetime n0 = ToNY(iTime(_Symbol, _Period, 0)), n1 = ToNY(iTime(_Symbol, _Period, 1));
   if(MyPosition(tk, tp, ot))
     {
      if(HourOf(n0) >= 15 || DayKey(n0) != DayKey(ToNY(ot))) CloseMine("Exit 15:00 New York");
      return;
     }
   if(HourOf(n1) != 10) return;                              // bar 10:00-11:00 New York just closed
   double ref = 0;
   for(int i = 2; i < 120; i++)
      if(HourOf(ToNY(iTime(_Symbol, _Period, i))) == 15) { ref = iClose(_Symbol, _Period, i); break; }
   double c1 = iClose(_Symbol, _Period, 1), atr = AtrRma(24, 1);
   if(ref <= 0 || atr == EMPTY_VALUE) return;
   double mv = c1 / ref - 1;
   int dir = mv > 0.006 ? 1 : (mv < -0.006 ? -1 : 0);
   if(dir != 0) OpenTrade(dir, c1 - dir * 1.5 * atr, 0, "NQ Intraday Mom");
  }
'''),
"NQ_Opening_Range.mq5": dict(tf="PERIOD_M5", magic=1106, risk=0.5, header='''//+------------------------------------------------------------------+
//| Nasdaq Opening-Range Breakout – MT5 EA. Chart: US100 / NAS100 / USTEC, M5 (New York clock)
//| Range = 09:30-09:45 New York. First M5 close outside it until 11:30 New York -> buy / sell, stop at the
//| other side of the range, target 2 x risk (both on the order). One trade per day. Flat at 15:55 NY.
//| Portfolio risk: 0.5% per trade.
//+------------------------------------------------------------------+''', body='''
int lastTradeDay = 0;
void OnNewBar()
  {
   ulong tk; long tp; datetime ot;
   datetime n0 = ToNY(iTime(_Symbol, _Period, 0)), n1 = ToNY(iTime(_Symbol, _Period, 1));
   if(MyPosition(tk, tp, ot))
     {
      if(MinuteOfDay(n0) >= 955 || DayKey(n0) != DayKey(ToNY(ot))) CloseMine("Flat 15:55 New York");
      return;
     }
   int day = DayKey(n1), m1 = MinuteOfDay(n1);
   if(m1 < 585 || m1 >= 690 || day == lastTradeDay) return;  // signal bars 09:45 .. 11:25
   double hi = -DBL_MAX, lo = DBL_MAX; int cnt = 0;
   for(int i = 1; i < 60; i++)
     {
      datetime nt = ToNY(iTime(_Symbol, _Period, i));
      if(DayKey(nt) != day) break;
      int m = MinuteOfDay(nt);
      if(m >= 570 && m < 585) { hi = MathMax(hi, iHigh(_Symbol, _Period, i)); lo = MathMin(lo, iLow(_Symbol, _Period, i)); cnt++; }
     }
   if(cnt < 2 || hi <= lo) return;
   double c1 = iClose(_Symbol, _Period, 1);
   int dir = c1 > hi ? 1 : (c1 < lo ? -1 : 0);
   if(dir == 0) return;
   lastTradeDay = day;
   double stop = dir == 1 ? lo : hi;
   double price = dir == 1 ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   OpenTrade(dir, stop, price + dir * 2.0 * MathAbs(price - stop), "NQ ORB");
  }
'''),
}

if __name__ == "__main__":
    out = os.path.join(os.path.dirname(__file__), "..", "strategies", "mt5")
    os.makedirs(out, exist_ok=True)
    for name, e in EAS.items():
        src = (e["header"] + "\n#property version \"1.00\"\n"
               f"#define REQUIRED_TF {e['tf']}\n"
               f"input double InpRiskPct = {e['risk']};    // Risk per trade (% of balance)\n"
               f"input long   InpMagic   = {e['magic']};   // Magic number (unique per EA)\n"
               + COMMON + e["body"])
        with open(os.path.join(out, name), "w") as f:
            f.write(src)
        print("wrote", name)
