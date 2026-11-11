"""Generate the MT5 Expert Advisors (six core + two dip grids) in strategies/mt5/ from one shared code block.

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
input double InpMaxStopPct       = 9.5;    // ACCOUNT guard: stop everything at this loss from start (firm limit 10)
input double InpRoomCapPct       = 7.0;    // Room cap: size shrinks to 0 as the day-start balance nears the firm limit (full size above -3%; 0 = off)
input double InpHalfBelowPct     = 4.0;    // Half size for all EAs once a day starts this % below the start balance (0 = off)
input double InpHalfUntilPct     = 2.0;    // ...and stay at half size until a day starts no more than this % below it
input double InpFirmMaxLossPct   = 10.0;   // The firm's max-loss limit (% of start) used by the room cap
input double InpGuardShare       = 60;     // A trade may risk at most this % of the remaining daily / max room
input double InpRiskMultiplier   = 1.0;    // Keep 1.0: the default risks are already the tested fast preset (see README)
input bool   InpAutoServerOffset = true;   // Live: detect the server's GMT offset automatically
input int    InpServerGMTOffset  = 2;      // Tester: server GMT offset in winter (FTMO-style servers: 2)
input bool   InpServerUsesUSDST  = true;   // Tester: server shifts +1h with US daylight saving (FTMO-style)
input int    InpNewsBlockMin     = 2;      // No NEW trades this many minutes before/after high-impact USD news (0 = off)
input double InpMaxSpreadPct     = 15;     // Skip a trade if the current spread is more than this % of its stop distance (0 = off)

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
void DeleteMyOrders()
  {
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong tk = OrderGetTicket(i);
      if(tk == 0) continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol || OrderGetInteger(ORDER_MAGIC) != InpMagic) continue;
      if(!trade.OrderDelete(tk)) Print("pending order delete failed ", trade.ResultRetcode());
     }
  }
void CloseMine(string why)
  {
   DeleteMyOrders();
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
double DayStartEquity()      // equity (open trades included) at the first check of the server day; used by the drawdown brake
  {
   string n = "PP_DE_" + IntegerToString(DayKey(TimeTradeServer()));
   if(!GlobalVariableCheck(n)) GlobalVariableSet(n, AccountInfoDouble(ACCOUNT_EQUITY));
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
bool NewsBlocked()   // uses MT5's built-in economic calendar (live only; the Strategy Tester has no calendar)
  {
   if(InpNewsBlockMin <= 0 || MQLInfoInteger(MQL_TESTER)) return false;
   datetime now = TimeTradeServer();
   MqlCalendarValue vals[];
   if(CalendarValueHistory(vals, now - InpNewsBlockMin * 60, now + InpNewsBlockMin * 60, NULL, "USD") <= 0) return false;
   for(int i = 0; i < ArraySize(vals); i++)
     {
      MqlCalendarEvent e;
      if(CalendarEventById(vals[i].event_id, e) && e.importance == CALENDAR_IMPORTANCE_HIGH) return true;
     }
   return false;
  }
bool gSpreadRetry = false;   // set when an entry waits for the spread to normalise (retried on later ticks, up to 15 minutes)
bool SpreadTooWide(double stopDist, string tag)
  {
   if(InpMaxSpreadPct <= 0 || stopDist <= 0) return false;
   double spread = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(spread <= InpMaxSpreadPct / 100.0 * stopDist) return false;
   static datetime lastWarn = 0;
   if(TimeCurrent() - lastWarn > 300)
     {
      Print(tag, ": spread ", DoubleToString(spread, _Digits), " is over ", InpMaxSpreadPct, "% of the stop distance ",
            DoubleToString(stopDist, _Digits), ", waiting up to 15 min for it to normalise");
      lastWarn = TimeCurrent();
     }
   gSpreadRetry = true;
   return true;
  }
double RiskMoney()
  {
   double bal = AccountInfoDouble(ACCOUNT_BALANCE), eq = AccountInfoDouble(ACCOUNT_EQUITY);
   double r = bal * InpRiskPct * InpRiskMultiplier / 100;
   double dayRoom = InpAccountSize * InpDailyStopPct / 100 - MathMax(0, DayStartBalance() - eq);
   double maxRoom = eq - InpAccountSize * (1 - InpMaxStopPct / 100);
   r = MathMin(r, MathMin(dayRoom, maxRoom) * InpGuardShare / 100);
   if(InpRoomCapPct > 0)      // room cap: full size until the day starts 3% down (equity), then shrink linearly to 0 at the firm limit
     {
      double room = DayStartEquity() - InpAccountSize * (1 - InpFirmMaxLossPct / 100);
      r *= MathMax(0, MathMin(1, room / (InpAccountSize * InpRoomCapPct / 100)));
     }
   if(InpHalfBelowPct > 0)    // half-size mode, shared by all EAs: on below -4% (day-start equity), off again above -2%
     {
      double dsb = DayStartEquity();
      if(dsb <= InpAccountSize * (1 - InpHalfBelowPct / 100)) GlobalVariableSet("PP_HALF", 1);
      else if(dsb >= InpAccountSize * (1 - InpHalfUntilPct / 100) && GlobalVariableCheck("PP_HALF")) GlobalVariableDel("PP_HALF");
      if(GlobalVariableCheck("PP_HALF")) r *= 0.5;
     }
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
   if(NewsBlocked()) { Print(tag, ": high-impact news within ", InpNewsBlockMin, " min, skipped"); return false; }
   double price = dir == 1 ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double dist = MathAbs(price - stopPrice);
   if(dir * (price - stopPrice) <= 0) { Print(tag, ": price already beyond the stop, skipped"); return false; }
   if(SpreadTooWide(dist, tag)) return false;
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
   if(b0 == lastBar)
     {
      // an entry was held back by a wide spread: try again on later ticks of the same bar (max 15 minutes)
      if(gSpreadRetry && !blocked && _Period == REQUIRED_TF && TimeCurrent() - b0 < 15 * 60) { gSpreadRetry = false; OnNewBar(); }
      return;
     }
   lastBar = b0;
   gSpreadRetry = false;
   if(blocked || _Period != REQUIRED_TF) return;
   OnNewBar();
  }
'''

EAS = {
"BTC_Dip_v3.mq5": dict(tf="PERIOD_H2", magic=1101, risk=0.75, header='''//+------------------------------------------------------------------+
//| BTC Dip v3 – MT5 EA. Chart: BTCUSD (or your broker's BTC symbol), H2
//| Buy when RSI(3) < 20 and close > EMA(50), unless the daily close is >15% below the close 30 days
//| earlier. Stop 2 x ATR(14) below the signal close (on the order). Exit after 48 H2 bars (4 days).
//| Portfolio risk: 0.75% per trade.  Python test 2020-2026: ~+20%/yr at 1% risk on its own.
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
"Gold_Dip.mq5": dict(tf="PERIOD_H1", magic=1102, risk=0.625, header='''//+------------------------------------------------------------------+
//| Gold Dip – MT5 EA. Chart: XAUUSD, H1
//| Buy when RSI(2) < 10 and close > EMA(50), unless the daily close is >8% below the close 30 days
//| earlier. Stop 2 x ATR(14) below the signal close (on the order). Exit after 96 H1 bars.
//| Portfolio risk: 0.625% per trade.
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
"Gold_Asia_Breakout.mq5": dict(tf="PERIOD_H1", magic=1103, risk=0.3125, header='''//+------------------------------------------------------------------+
//| Gold Asia-Range Breakout – MT5 EA. Chart: XAUUSD, H1 (London clock)
//| Range = 00:00-07:00 London. First H1 close above / below it between 07:00 and 14:00 London -> buy /
//| sell, stop at the range middle (on the order). One trade per day. Flat at 20:00 London.
//| Portfolio risk: 0.3125% per trade.
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
   if(OpenTrade(dir, mid, 0, "Gold Asia BO") || !gSpreadRetry) lastTradeDay = day;
  }
'''),
"Gold_Intraday_Momentum.mq5": dict(tf="PERIOD_H1", magic=1104, risk=0.3125, header='''//+------------------------------------------------------------------+
//| Gold Intraday Momentum – MT5 EA. Chart: XAUUSD, H1 (London clock)
//| Reference = close of the H1 bar ending 17:00 London (previous day). At 09:00 London, if gold moved
//| more than 0.6% from it, trade in that direction; stop 1.0 x ATR(24); exit 16:00 London.
//| Portfolio risk: 0.3125% per trade.
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
"NQ_Opening_Range.mq5": dict(tf="PERIOD_M5", magic=1106, risk=0.625, header='''//+------------------------------------------------------------------+
//| Nasdaq Opening-Range Breakout – MT5 EA. Chart: US100 / NAS100 / USTEC, M5 (New York clock)
//| Range = 09:30-09:45 New York. First M5 close outside it until 11:30 New York -> buy / sell, stop at the
//| other side of the range, target 2 x risk (both on the order). One trade per day. Flat at 15:55 NY.
//| Portfolio risk: 0.625% per trade.
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
   double stop = dir == 1 ? lo : hi;
   double price = dir == 1 ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(OpenTrade(dir, stop, price + dir * 2.0 * MathAbs(price - stop), "NQ ORB") || !gSpreadRetry) lastTradeDay = day;
  }
'''),
}
GRID_BODY = r'''
input double InpZ        = 2.0;   // Buy when price is this many standard deviations below its 20-bar mean
input int    InpLevels   = 3;     // Grid levels (1 market entry + limit orders), equal size
input double InpSpacing  = 1.0;   // Level spacing (x ATR 14); hard stop one spacing below the last level
input double InpTrailATR = 1.5;   // Once back at the mean: trail the stop this many ATRs under the close
input int    InpHoldBars = 120;   // Time exit (bars)
int cooldown = 0;
string GV(string k) { return "DG_" + IntegerToString(InpMagic) + "_" + _Symbol + "_" + k; }
int MyPositions(double &avg)
  {
   int n = 0; double vol = 0; avg = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      double v = PositionGetDouble(POSITION_VOLUME); avg += v * PositionGetDouble(POSITION_PRICE_OPEN); vol += v; n++;
     }
   if(vol > 0) avg /= vol;
   return n;
  }
void RaiseStops(double sl)
  {
   sl = NormalizeDouble(sl, _Digits);
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      double cur = PositionGetDouble(POSITION_SL);
      if(cur > 0 && sl <= cur + _Point) continue;           // only ever tighten
      if(!trade.PositionModify(tk, sl, PositionGetDouble(POSITION_TP))) Print("trail modify failed ", trade.ResultRetcode());
     }
  }
double ZScore(int shift)
  {
   double c[]; ArraySetAsSeries(c, true);
   if(CopyClose(_Symbol, _Period, shift, 20, c) < 20) return EMPTY_VALUE;
   double m = 0, v = 0;
   for(int i = 0; i < 20; i++) m += c[i];
   m /= 20;
   for(int i = 0; i < 20; i++) v += (c[i] - m) * (c[i] - m);
   double sd = MathSqrt(v / 19);
   return sd > 0 ? (c[0] - m) / sd : EMPTY_VALUE;
  }
void ResetBasket() { GlobalVariableDel(GV("T0")); GlobalVariableDel(GV("A0")); GlobalVariableDel(GV("TR")); }
void OnNewBar()
  {
   double avg; int n = MyPositions(avg);
   if(n == 0)
     {
      if(GlobalVariableCheck(GV("T0"))) { DeleteMyOrders(); ResetBasket(); cooldown = 3; return; }   // basket just ended
      if(cooldown > 0) { cooldown--; return; }
      double c1 = iClose(_Symbol, _Period, 1), z = ZScore(1), ema = Ema(200, 1), a0 = AtrRma(14, 1);
      if(z == EMPTY_VALUE || ema == EMPTY_VALUE || a0 == EMPTY_VALUE || a0 <= 0) return;
      if(z > -InpZ || c1 <= ema) return;                    // only dips, only while above the 200 EMA
      if(NewsBlocked()) { Print("Dip grid: high-impact news within ", InpNewsBlockMin, " min, skipped"); return; }
      double e0 = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl = e0 - InpLevels * InpSpacing * a0, sumDist = 0;
      if(SpreadTooWide(InpSpacing * a0, "Dip grid")) return;                 // compared with one grid spacing
      for(int k = 0; k < InpLevels; k++) sumDist += (e0 - k * InpSpacing * a0) - sl;
      double lots = LotsFor(RiskMoney(), sumDist, ORDER_TYPE_BUY, e0);   // the whole basket loses RiskMoney at the stop
      if(lots <= 0) { Print("Dip grid: size below minimum for the allowed risk, skipped"); return; }
      if(!trade.Buy(lots, _Symbol, 0, NormalizeDouble(sl, _Digits), 0, "Dip grid L1")) { Print("Dip grid: entry failed ", trade.ResultRetcode()); return; }
      for(int k = 1; k < InpLevels; k++)
         if(!trade.BuyLimit(lots, NormalizeDouble(e0 - k * InpSpacing * a0, _Digits), _Symbol, NormalizeDouble(sl, _Digits), 0, ORDER_TIME_GTC, 0, "Dip grid L" + IntegerToString(k + 1)))
            Print("Dip grid: limit order failed ", trade.ResultRetcode());
      GlobalVariableSet(GV("T0"), (double)iTime(_Symbol, _Period, 0)); GlobalVariableSet(GV("A0"), a0); GlobalVariableSet(GV("TR"), 0);
      return;
     }
   if(!GlobalVariableCheck(GV("T0"))) { GlobalVariableSet(GV("T0"), (double)iTime(_Symbol, _Period, 1)); GlobalVariableSet(GV("A0"), AtrRma(14, 1)); GlobalVariableSet(GV("TR"), 0); }
   datetime t0 = (datetime)GlobalVariableGet(GV("T0")); double a = GlobalVariableGet(GV("A0"));
   if(iBarShift(_Symbol, _Period, t0) > InpHoldBars) { CloseMine("Dip grid time exit"); return; }
   bool trail = GlobalVariableGet(GV("TR")) > 0;
   double z1 = ZScore(1);
   if(!trail && z1 != EMPTY_VALUE && z1 >= 0) { trail = true; GlobalVariableSet(GV("TR"), 1); DeleteMyOrders(); }   // back at the mean: no more adds
   if(trail)
     {
      double sl = MathMax(iClose(_Symbol, _Period, 1) - InpTrailATR * a, avg);
      if(sl >= SymbolInfoDouble(_Symbol, SYMBOL_BID) - SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point) { CloseMine("Dip grid trail exit"); return; }
      RaiseStops(sl);
     }
  }
'''


def grid_ea(title, chart, magic, risk, note):
    return dict(tf="PERIOD_H1", magic=magic, risk=risk, header=f'''//+------------------------------------------------------------------+
//| {title} – MT5 EA. Chart: {chart}, H1
//| Long-only dip grid: when price closes 2 standard deviations below its 20-bar mean while above the
//| 200 EMA, buy at market and place 2 equal buy-limits 1 and 2 x ATR(14) lower. Every position has the
//| same hard stop 3 x ATR below the first entry, sized so the FULL basket loses InpRiskPct at the stop.
//| Once price is back at its mean: cancel the limits and trail the stop 1.5 x ATR under the close
//| (never below break-even). Time exit after 120 bars.
//| {note}
//+------------------------------------------------------------------+''', body=GRID_BODY)


EAS["NQ_Dip_Grid.mq5"] = grid_ea("Nasdaq Dip Grid", "US100 / NAS100 / USTEC", 1107, 0.5, "Portfolio risk: 0.5% per basket (worst case). Python 2016-2026: ~+1.9%/yr at 0.5% on its own (+7.7%/yr at 2% worst case).")
EAS["SPX_Dip_Grid.mq5"] = grid_ea("S&P 500 Dip Grid", "US500 / SPX500", 1108, 0.5, "Portfolio risk: 0.5% per basket (worst case). Python 2016-2026: ~+2.8%/yr at 0.5% on its own (+11%/yr at 2% worst case).")

def dip_ea(title, chart, tf, magic, risk, rsi_len, buy, ema_len, hold_bars, crash, note):
    return dict(tf=tf, magic=magic, risk=risk, header=f"""//+------------------------------------------------------------------+
//| {title} – MT5 EA. Chart: {chart}, {tf.replace('PERIOD_', '')}
//| Buy when RSI({rsi_len}) < {buy} and close > EMA({ema_len}), unless the daily close is >{int(crash * 100)}% below the close
//| 30 days earlier. Stop 2 x ATR(14) below the signal close (on the order). Exit after {hold_bars} bars.
//| {note}
//+------------------------------------------------------------------+""", body=f"""
void OnNewBar()
  {{
   ulong tk; long tp; datetime ot;
   if(MyPosition(tk, tp, ot))
     {{
      if(iBarShift(_Symbol, _Period, ot) >= {hold_bars}) CloseMine("Time exit ({hold_bars} bars)");
      return;
     }}
   double c1 = iClose(_Symbol, _Period, 1), rsi = Rsi({rsi_len}, 1), ema = Ema({ema_len}, 1), atr = AtrRma(14, 1);
   if(rsi == EMPTY_VALUE || ema == EMPTY_VALUE || atr == EMPTY_VALUE) return;
   double d30 = iClose(_Symbol, PERIOD_D1, 1) / iClose(_Symbol, PERIOD_D1, 31) - 1;
   if(d30 < -{crash}) return;                                  // crash filter
   if(rsi < {buy} && c1 > ema) OpenTrade(1, c1 - 2 * atr, 0, "{title}");
  }}
""")


RETIRED = {"NQ_Dip_Grid.mq5": EAS.pop("NQ_Dip_Grid.mq5"), "SPX_Dip_Grid.mq5": EAS.pop("SPX_Dip_Grid.mq5"),
           "NQ_Intraday_Momentum.mq5": EAS.pop("NQ_Intraday_Momentum.mq5")}
EAS["NQ_Dip_2h.mq5"] = dip_ea("NQ Dip 2h", "US100 / NAS100 / USTEC", "PERIOD_H2", 1109, 0.3125, 2, 25, 50, 48, 0.08,
                              "Portfolio risk: 0.3125% per trade. Python 2020-2026 at 1% risk: +12.3%/yr (2020-22), +14.4%/yr (2023-26).")
EAS["SPX_Dip_1h.mq5"] = dip_ea("S&P Dip 1h", "US500 / SPX500", "PERIOD_H1", 1110, 0.3125, 2, 15, 200, 48, 0.08,
                               "Portfolio risk: 0.3125% per trade. Python 2020-2026 at 1% risk: +10.5%/yr (2020-22), +12.6%/yr (2023-26).")
EAS["Oil_Dip_1h.mq5"] = dip_ea("Oil Dip 1h", "WTI / USOIL / XTIUSD", "PERIOD_H1", 1111, 0.1875, 2, 25, 50, 144, 0.15,
                               "Portfolio risk: 0.1875% per trade. Python 2020-2026 at 1% risk: +14.1%/yr (2020-22), +15.5%/yr (2023-26).")

EAS["BTC_Dip_EMA200_2h.mq5"] = dip_ea("BTC Dip EMA200 2h", "BTCUSD", "PERIOD_H2", 1117, 0.05, 2, 10, 200, 72, 0.08,
                                     "OPTIONAL variant of BTC_Dip_v3 (Nov 2026). Portfolio risk: 0.05% per trade, run at most ONE variant. With the 12 EAs: pass 100%, 0 breaches, ~3 days faster, funded +118% vs +116%.")
EAS["NQ_Breakout_15m.mq5"] = dict(tf="PERIOD_M15", magic=1112, risk=0.2, header="""//+------------------------------------------------------------------+
//| NQ Breakout 15m – MT5 EA. Chart: US100 / NAS100 / USTEC, M15 (New York clock)
//| Between 09:30 and 12:00 New York: a 15-minute close above the highest high of the previous 20 bars while
//| above EMA(200) -> buy; a close below the lowest low of the previous 20 bars while below EMA(200) -> sell.
//| Stop 1 x ATR(14) on the order, no target: flat at 15:50 New York. Several trades a day are possible.
//| Portfolio risk: 0.2% per trade, core EA since 7 Nov 2026 (fits at 0.2% with the drawdown brake). About 1 trade per weekday. Python 2019-2026 at 1% risk: about +44%/yr
//| (2019-22) and +48%/yr (2023-26); +27%/yr with double costs. Thin, cost-sensitive edge: low spreads only.
//+------------------------------------------------------------------+""", body="""
void OnNewBar()
  {
   ulong tk; long tp; datetime ot;
   datetime n0 = ToNY(iTime(_Symbol, _Period, 0)), n1 = ToNY(iTime(_Symbol, _Period, 1));
   if(MyPosition(tk, tp, ot))
     {
      if(MinuteOfDay(n0) >= 950 || DayKey(n0) != DayKey(ToNY(ot))) CloseMine("Flat 15:50 New York");
      return;
     }
   int m1 = MinuteOfDay(n1);
   if(m1 < 570 || m1 >= 720) return;                         // signal bar inside 09:30-12:00 New York
   double c1 = iClose(_Symbol, _Period, 1), ema = Ema(200, 1), atr = AtrRma(14, 1);
   if(ema == EMPTY_VALUE || atr == EMPTY_VALUE || atr <= 0) return;
   int hiIdx = iHighest(_Symbol, _Period, MODE_HIGH, 20, 2), loIdx = iLowest(_Symbol, _Period, MODE_LOW, 20, 2);
   if(hiIdx < 0 || loIdx < 0) return;
   double hi = iHigh(_Symbol, _Period, hiIdx), lo = iLow(_Symbol, _Period, loIdx);
   int dir = (c1 > hi && c1 > ema) ? 1 : ((c1 < lo && c1 < ema) ? -1 : 0);
   if(dir == 0) return;
   double price = dir == 1 ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   OpenTrade(dir, price - dir * atr, 0, "NQ Breakout 15m");
  }
""")

EAS["Nikkei_Breakout_5m.mq5"] = dict(tf="PERIOD_M5", magic=1118, risk=0.1, header="""//+------------------------------------------------------------------+
//| Nikkei Breakout 5m – MT5 EA. Chart: JP225 / .JP225Cash / JP225.cash (your broker's Nikkei 225), M5 (Tokyo clock)
//| Between 09:00 and 11:30 Tokyo: a 5-minute close above the highest high of the previous 20 bars while above
//| EMA(800) -> buy; a close below the lowest low of the previous 20 bars while below EMA(800) -> sell.
//| Stop 2 x ATR(14) on the order, no target: flat at 14:55 Tokyo. Several trades a day are possible.
//| OPTIONAL (Nov 2026). Portfolio risk: 0.1% per trade, ~1 trade per weekday, trades 00:00-05:55 UTC when the other EAs are quiet.
//| Python: +27/+36 R per year (2021-22 / 2023, Dukascopy) and +35 R per year on broker data Jun 2025-Nov 2026 (never seen
//| before the rules were fixed); +17 R per year with double costs. With the 12 EAs in Pass Mode: pass +1-2%, same speed.
//+------------------------------------------------------------------+""", body="""
datetime ToTokyo(datetime s) { return ToUTC(s) + 9 * 3600; }   // Japan has no daylight saving
void OnNewBar()
  {
   ulong tk; long tp; datetime ot;
   datetime t0 = ToTokyo(iTime(_Symbol, _Period, 0)), t1 = ToTokyo(iTime(_Symbol, _Period, 1));
   if(MyPosition(tk, tp, ot))
     {
      if(MinuteOfDay(t0) >= 895 || DayKey(t0) != DayKey(ToTokyo(ot))) CloseMine("Flat 14:55 Tokyo");
      return;
     }
   int m1 = MinuteOfDay(t1);
   if(m1 < 540 || m1 >= 690 || DayKey(t0) != DayKey(t1)) return;   // signal bar inside 09:00-11:30 Tokyo, entry the same day
   double c1 = iClose(_Symbol, _Period, 1), ema = Ema(800, 1), atr = AtrRma(14, 1);
   if(ema == EMPTY_VALUE || atr == EMPTY_VALUE || atr <= 0) return;
   int hiIdx = iHighest(_Symbol, _Period, MODE_HIGH, 20, 2), loIdx = iLowest(_Symbol, _Period, MODE_LOW, 20, 2);
   if(hiIdx < 0 || loIdx < 0) return;
   double hi = iHigh(_Symbol, _Period, hiIdx), lo = iLow(_Symbol, _Period, loIdx);
   int dir = (c1 > hi && c1 > ema) ? 1 : ((c1 < lo && c1 < ema) ? -1 : 0);
   if(dir == 0) return;
   double price = dir == 1 ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   OpenTrade(dir, price - dir * 2 * atr, 0, "Nikkei Breakout 5m");
  }
""")

EAS["DAX_Opening_Range.mq5"] = dict(tf="PERIOD_M15", magic=1115, risk=0.2, header="""//+------------------------------------------------------------------+
//| DAX Opening Range – MT5 EA. Chart: GER40 / DE40 / DAX40 (your broker's DAX symbol), M15 (Frankfurt clock)
//| Range = high/low of 09:00-09:30 Frankfurt. From 09:30 to 12:00, the first 15-minute close above the range
//| while above the EMA(50) of daily closes (up to yesterday) -> buy; below the range and below that EMA -> sell.
//| Stop at the middle of the range (on the order), no target, flat at 17:25 Frankfurt. One trade per day.
//| Portfolio risk: 0.2% per trade, ~11 trades a month. Python 2021-2026 at 1% risk: +42%/yr (2021-22),
//| +29%/yr (2023-26), +28%/yr with double costs. With the 9 core EAs: pass 95% / 97%, median 68 / 60 days. Trades 03:30-11:25 New York, when the other EAs are quiet.
//+------------------------------------------------------------------+""", body="""
datetime ToFrankfurt(datetime s) { datetime u = ToUTC(s); return u + (IsUKDST(u) ? 7200 : 3600); }   // EU and UK switch DST together
double EmaD1(int len)       // EMA(len) of daily closes up to yesterday
  {
   int n = MathMin(iBars(_Symbol, PERIOD_D1) - 1, 5 * len);
   if(n < 2 * len) return EMPTY_VALUE;
   double a = 2.0 / (len + 1), e = iClose(_Symbol, PERIOD_D1, n);
   for(int k = n - 1; k >= 1; k--) e = a * iClose(_Symbol, PERIOD_D1, k) + (1 - a) * e;
   return e;
  }
int lastTradeDay = 0;
void OnNewBar()
  {
   ulong tk; long tp; datetime ot;
   datetime f0 = ToFrankfurt(iTime(_Symbol, _Period, 0)), f1 = ToFrankfurt(iTime(_Symbol, _Period, 1));
   if(MyPosition(tk, tp, ot))
     {
      if(MinuteOfDay(f0) >= 1045 || DayKey(f0) != DayKey(ToFrankfurt(ot))) CloseMine("Flat 17:25 Frankfurt");
      return;
     }
   int m1 = MinuteOfDay(f1), day = DayKey(f1);
   if(m1 < 570 || m1 >= 720 || day == lastTradeDay || DayKey(f0) != day) return;   // signal bar 09:30-12:00 Frankfurt
   double hi = -1, lo = -1;
   for(int k = 1; k < 60; k++)
     {
      datetime fk = ToFrankfurt(iTime(_Symbol, _Period, k));
      if(DayKey(fk) != day) break;
      int mk = MinuteOfDay(fk);
      if(mk >= 540 && mk < 570)
        {
         double h = iHigh(_Symbol, _Period, k), l = iLow(_Symbol, _Period, k);
         hi = hi < 0 ? h : MathMax(hi, h); lo = lo < 0 ? l : MathMin(lo, l);
        }
     }
   if(hi <= 0 || lo <= 0 || hi <= lo) return;
   double c1 = iClose(_Symbol, _Period, 1), ema = EmaD1(50);
   if(ema == EMPTY_VALUE) return;
   int dir = 0;
   if(c1 > hi && c1 > ema) dir = 1;
   if(c1 < lo && c1 < ema) dir = -1;
   if(dir == 0) return;
   if(OpenTrade(dir, (hi + lo) / 2, 0, "DAX Opening Range") || !gSpreadRetry) lastTradeDay = day;
  }
""")

EAS["BTC_Weekend_Gap.mq5"] = dict(tf="PERIOD_H1", magic=1114, risk=0.25, header="""//+------------------------------------------------------------------+
//| BTC Weekend Gap – MT5 EA. Chart: BTCUSD (your broker's BTC symbol), H1. Needs BTC to trade at weekends.
//| CME bitcoin futures close Friday 16:00 Chicago (17:00 New York) and reopen Sunday 17:00 Chicago (18:00 NY)
//| while spot keeps trading. At the Sunday reopen, if BTC has moved more than 2% since Friday's close, trade
//| IN the direction of that weekend move (the popular "gap fill" fade loses money; the follow-through wins).
//| Stop 1.5 x ATR(14) on the order, exit after 48 H1 bars. About 1-2 trades a month.
//| Portfolio risk: 0.25% per trade (halved Nov 2026: the weekend-gap effect lost money on every coin in 2025 and 2026).
//| Python 2020-2026 at 1% risk: +19%/yr (2020-22), +8%/yr (2023-26), 34% winners,
//| average +0.87R. With the 8 EAs: 2-step pass 94% / 97%, 0 breaches, median 70 / 66 days, funded +84% / +95%.
//+------------------------------------------------------------------+""", body="""
int lastGapWeek = 0;
void OnNewBar()
  {
   ulong tk; long tp; datetime ot;
   if(MyPosition(tk, tp, ot))
     {
      if(iBarShift(_Symbol, _Period, ot) >= 48) CloseMine("Time exit (48h)");
      return;
     }
   datetime n0 = ToNY(iTime(_Symbol, _Period, 0)); MqlDateTime s0; TimeToStruct(n0, s0);
   if(s0.day_of_week != 0 || s0.hour < 18 || s0.hour > 19) return;      // Sunday 18:00-19:59 New York (CME reopen)
   int wk = DayKey(n0);
   if(wk == lastGapWeek) return;
   double friClose = 0;
   for(int k = 1; k < 120; k++)                                          // close of the Friday 16:00-17:00 NY bar
     {
      MqlDateTime s; TimeToStruct(ToNY(iTime(_Symbol, _Period, k)), s);
      if(s.day_of_week == 5 && s.hour == 16) { friClose = iClose(_Symbol, _Period, k); break; }
      if(s.day_of_week == 4) break;
     }
   if(friClose <= 0) { lastGapWeek = wk; return; }
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), gap = bid / friClose - 1, atr = AtrRma(14, 1);
   if(atr == EMPTY_VALUE || atr <= 0) return;
   if(MathAbs(gap) < 0.02) { lastGapWeek = wk; return; }
   int dir = gap > 0 ? 1 : -1;
   double price = dir == 1 ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : bid;
   if(OpenTrade(dir, price - dir * 1.5 * atr, 0, "BTC Weekend Gap") || !gSpreadRetry) lastGapWeek = wk;
  }
""")

EAS["SPX_Breakout_5m.mq5"] = dict(tf="PERIOD_M5", magic=1113, risk=0.1, header="""//+------------------------------------------------------------------+
//| SPX Breakout 5m – MT5 EA. Chart: US500 / SPX500, M5 (New York clock). Core EA #12 since 8 Nov 2026 (low spreads only).
//| Between 09:30 and 12:00 New York: a 5-minute close above the highest high of the previous 50 bars while
//| above EMA(200) -> buy; a close below the lowest low of the previous 50 bars while below EMA(200) -> sell.
//| Stop 2 x ATR(14) on the order, no target: flat at 15:50 New York. Several trades a day are possible.
//| Portfolio risk: 0.1% per trade (~26 trades a month). Python 2019-2026 at 1% risk: +47%/yr (2019-22),
//| +20%/yr (2023-26), +15%/yr with double costs. With the fast preset: funded year +71% / +98% instead of
//| +58% / +91%, 0 breaches; evaluation pass 93% instead of 95%, so it is meant for the funded account.
//+------------------------------------------------------------------+""", body="""
void OnNewBar()
  {
   ulong tk; long tp; datetime ot;
   datetime n0 = ToNY(iTime(_Symbol, _Period, 0)), n1 = ToNY(iTime(_Symbol, _Period, 1));
   if(MyPosition(tk, tp, ot))
     {
      if(MinuteOfDay(n0) >= 950 || DayKey(n0) != DayKey(ToNY(ot))) CloseMine("Flat 15:50 New York");
      return;
     }
   int m1 = MinuteOfDay(n1);
   if(m1 < 570 || m1 >= 720) return;                         // signal bar inside 09:30-12:00 New York
   double c1 = iClose(_Symbol, _Period, 1), ema = Ema(200, 1), atr = AtrRma(14, 1);
   if(ema == EMPTY_VALUE || atr == EMPTY_VALUE || atr <= 0) return;
   int hiIdx = iHighest(_Symbol, _Period, MODE_HIGH, 50, 2), loIdx = iLowest(_Symbol, _Period, MODE_LOW, 50, 2);
   if(hiIdx < 0 || loIdx < 0) return;
   double hi = iHigh(_Symbol, _Period, hiIdx), lo = iLow(_Symbol, _Period, loIdx);
   int dir = (c1 > hi && c1 > ema) ? 1 : ((c1 < lo && c1 < ema) ? -1 : 0);
   if(dir == 0) return;
   double price = dir == 1 ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   OpenTrade(dir, price - dir * 2 * atr, 0, "SPX Breakout 5m");
  }
""")


# ---------------------------------------------------------------------------------------------------------------
# Breakout Pack: one EA that runs six of the morning-breakout strategies on four markets from a single chart.
# The strategy bodies are the same code as the single EAs; only the symbol / timeframe / magic / risk are switched
# per module. Same magic numbers as the single EAs, so running both never doubles a trade.
EAS["NQ_Breakout_5m"] = dict(tf="PERIOD_M5", magic=1116, risk=0.05, header="", body=EAS["NQ_Breakout_15m.mq5"]["body"]
    .replace("MODE_HIGH, 20, 2", "MODE_HIGH, 50, 2").replace("MODE_LOW, 20, 2", "MODE_LOW, 50, 2")
    .replace("Ema(200, 1)", "Ema(800, 1)").replace("price - dir * atr", "price - dir * 2 * atr").replace('"NQ Breakout 15m"', '"NQ Breakout 5m"'))
PACK = [  # module key, single-EA source, symbol input default, timeframe, magic, risk
    ("NQORB", "NQ_Opening_Range.mq5", "InpSymNQ", "PERIOD_M5", 1106, 0.625),
    ("NQBO15", "NQ_Breakout_15m.mq5", "InpSymNQ", "PERIOD_M15", 1112, 0.2),
    ("NQBO5", "NQ_Breakout_5m", "InpSymNQ", "PERIOD_M5", 1116, 0.05),
    ("SPXBO5", "SPX_Breakout_5m.mq5", "InpSymSPX", "PERIOD_M5", 1113, 0.1),
    ("DAXORB", "DAX_Opening_Range.mq5", "InpSymDAX", "PERIOD_M15", 1115, 0.2),
    ("GOLDASIA", "Gold_Asia_Breakout.mq5", "InpSymGold", "PERIOD_H1", 1103, 0.3125)]
def make_pack():
    common = COMMON.split("//--- event plumbing")[0]
    import re
    sub = lambda t: (t.replace("_Symbol", "gSym").replace("_Period", "gTf").replace("_Digits", "(int)SymbolInfoInteger(gSym, SYMBOL_DIGITS)")
                     .replace("InpMagic", "gMagic").replace("InpRiskPct", "gRisk"))
    common = sub(common)
    # indicator handles cached per symbol + timeframe + length
    common = re.sub(r"double Rsi\(int len, int shift\)\n  \{.*?\n  \}\n", """double Rsi(int len, int shift)
  {
   static int hs[40]; static string ks[40]; static int n = 0; string key = gSym + "|" + IntegerToString(gTf) + "|" + IntegerToString(len); int h = INVALID_HANDLE;
   for(int i = 0; i < n; i++) if(ks[i] == key) h = hs[i];
   if(h == INVALID_HANDLE && n < 40) { h = iRSI(gSym, gTf, len, PRICE_CLOSE); hs[n] = h; ks[n] = key; n++; }
   double b[]; ArraySetAsSeries(b, true);
   if(CopyBuffer(h, 0, shift, 1, b) < 1) return EMPTY_VALUE;
   return b[0];
  }
""", common, flags=re.S)
    common = re.sub(r"double Ema\(int len, int shift\)\n  \{.*?\n  \}\n", """double Ema(int len, int shift)
  {
   static int hs[40]; static string ks[40]; static int n = 0; string key = gSym + "|" + IntegerToString(gTf) + "|" + IntegerToString(len); int h = INVALID_HANDLE;
   for(int i = 0; i < n; i++) if(ks[i] == key) h = hs[i];
   if(h == INVALID_HANDLE && n < 40) { h = iMA(gSym, gTf, len, 0, MODE_EMA, PRICE_CLOSE); hs[n] = h; ks[n] = key; n++; }
   double b[]; ArraySetAsSeries(b, true);
   if(CopyBuffer(h, 0, shift, 1, b) < 1) return EMPTY_VALUE;
   return b[0];
  }
""", common, flags=re.S)
    common = common.replace("bool OpenTrade(int dir, double stopPrice, double tpPrice, string tag)\n  {\n",
                            "bool OpenTrade(int dir, double stopPrice, double tpPrice, string tag)\n  {\n   trade.SetExpertMagicNumber(gMagic); trade.SetTypeFillingBySymbol(gSym);\n")
    bodies = []
    for k, src, symin, tf, magic, risk in PACK:
        b = sub(EAS[src]["body"]).replace("void OnNewBar()", f"void OnNewBar_{k}()").replace("lastTradeDay", f"lastTradeDay_{k}")
        b = b.replace("datetime ToFrankfurt(", "datetime ToFrankfurt(") if k == "DAXORB" else b
        bodies.append(f"//=== module {k} (from {src}) ===" + b)
    inputs = "\n".join(f"input double InpRisk_{k} = {risk};   // {k}: risk per trade (% of balance, 0 = off)" for k, *_r in [(m[0],) for m in PACK] for risk in [dict((x[0], x[5]) for x in PACK)[k]])
    n = len(PACK)
    ctx = "\n".join(f'   if(k == {i}) {{ gSym = {sym}; gTf = {tf}; gMagic = {mg}; gRisk = InpRisk_{key}; }}' for i, (key, src, sym, tf, mg, rk) in enumerate(PACK))
    calls = "\n".join(f"   if(k == {i}) OnNewBar_{key}();" for i, (key, *_r) in enumerate(PACK))
    header = """//+------------------------------------------------------------------+
//| Breakout Pack – ONE MT5 EA that runs six morning-breakout strategies on four markets (about 5.3 trades a weekday):
//|   NQ opening range (M5) 0.625%, NQ 15m breakout 0.2%, NQ 5m breakout 0.05%, S&P 5m breakout 0.1%,
//|   DAX opening range (M15) 0.2%, Gold Asia breakout (H1) 0.3125%.
//| Attach it to ANY one chart (e.g. US100 M5). Type your broker's symbol names in the inputs. It checks all markets every 5 seconds.
//| It replaces the single EAs NQ_Opening_Range, NQ_Breakout_15m, SPX_Breakout_5m, DAX_Opening_Range and Gold_Asia_Breakout:
//| remove those, keep the other 7 (BTC_Dip_v3, Gold_Dip, Gold_Intraday_Momentum, NQ_Dip_2h, SPX_Dip_1h, Oil_Dip_1h, BTC_Weekend_Gap).
//| It uses the same magic numbers as the single EAs, so it never doubles their trades.
//+------------------------------------------------------------------+
#property version "1.00"
input string InpSymNQ   = ".USTECHCash";  // Your broker's Nasdaq symbol (FTMO: US100.cash)
input string InpSymSPX  = ".US500Cash";   // Your broker's S&P 500 symbol (FTMO: US500.cash)
input string InpSymDAX  = ".DE40Cash";    // Your broker's DAX symbol (FTMO: GER40.cash)
input string InpSymGold = "XAUUSD";       // Your broker's gold symbol
""" + inputs + "\nstring gSym = \"\"; ENUM_TIMEFRAMES gTf = PERIOD_M5; long gMagic = 0; double gRisk = 0;\n"
    plumbing = f"""
//--- pack plumbing -------------------------------------------------------------------
#define NMOD {n}
datetime gLastBar[NMOD]; bool gRetry[NMOD];
void CallModule(int k);
void SetCtx(int k)
  {{
{ctx}
  }}
void RunAll()
  {{
   for(int k = 0; k < NMOD; k++)
     {{
      SetCtx(k);
      if(gSym == "" || gRisk <= 0) continue;
      bool blocked = GuardBlocks();
      datetime b0 = iTime(gSym, gTf, 0);
      if(b0 == 0) continue;
      if(b0 == gLastBar[k])
        {{
         if(gRetry[k] && !blocked && TimeCurrent() - b0 < 15 * 60) {{ gSpreadRetry = false; CallModule(k); gRetry[k] = gSpreadRetry; }}
         continue;
        }}
      gLastBar[k] = b0; gSpreadRetry = false;
      if(!blocked) CallModule(k);
      gRetry[k] = gSpreadRetry;
     }}
  }}
void CallModule(int k)
  {{
{calls}
  }}
int OnInit()
  {{
   trade.SetDeviationInPoints(50);
   string syms[4]; syms[0] = InpSymNQ; syms[1] = InpSymSPX; syms[2] = InpSymDAX; syms[3] = InpSymGold;
   for(int i = 0; i < 4; i++)
      if(syms[i] != "" && !SymbolSelect(syms[i], true)) Print("WARNING: symbol '", syms[i], "' not found - type your broker's exact name in the inputs");
   for(int k = 0; k < NMOD; k++) {{ gLastBar[k] = 0; gRetry[k] = false; }}
   EventSetTimer(5);
   return INIT_SUCCEEDED;
  }}
void OnDeinit(const int reason) {{ EventKillTimer(); }}
void OnTick()  {{ RunAll(); }}
void OnTimer() {{ RunAll(); }}
"""
    return header + common.replace("input double InpAccountSize", "input double InpAccountSize") + "\n".join(bodies) + plumbing

if __name__ == "__main__":
    out = os.path.join(os.path.dirname(__file__), "..", "strategies", "mt5")
    os.makedirs(out, exist_ok=True)
    os.makedirs(os.path.join(out, "retired"), exist_ok=True)
    for name, e in [(k, v) for k, v in EAS.items() if k.endswith(".mq5")] + [("retired/" + k, v) for k, v in RETIRED.items()]:
        src = (e["header"] + "\n#property version \"1.00\"\n"
               f"#define REQUIRED_TF {e['tf']}\n"
               f"input double InpRiskPct = {e['risk']};    // Risk per trade (% of balance)\n"
               f"input long   InpMagic   = {e['magic']};   // Magic number (unique per EA)\n"
               + COMMON + e["body"])
        with open(os.path.join(out, name), "w") as f:
            f.write(src)
        print("wrote", name)
    # One clean download folder at the repo root: the 10 core EAs, the optional ones, and a zip of the core 10
    import shutil, zipfile
    CORE = ["BTC_Dip_v3", "Gold_Dip", "Gold_Asia_Breakout", "Gold_Intraday_Momentum", "NQ_Opening_Range", "NQ_Dip_2h",
            "SPX_Dip_1h", "Oil_Dip_1h", "BTC_Weekend_Gap", "DAX_Opening_Range", "NQ_Breakout_15m", "SPX_Breakout_5m"]
    OPTIONAL = ["BTC_Dip_EMA200_2h", "Nikkei_Breakout_5m"]
    dl = os.path.join(os.path.dirname(__file__), "..", "MT5_EAs")
    os.makedirs(os.path.join(dl, "optional"), exist_ok=True)
    for n in CORE: shutil.copy(os.path.join(out, n + ".mq5"), os.path.join(dl, n + ".mq5"))
    for n in OPTIONAL: shutil.copy(os.path.join(out, n + ".mq5"), os.path.join(dl, "optional", n + ".mq5"))
    for old in ("MT5_10_EAs.zip", "MT5_11_EAs.zip", os.path.join("optional", "NQ_Breakout_15m.mq5"), os.path.join("optional", "SPX_Breakout_5m.mq5")):
        if os.path.exists(os.path.join(dl, old)): os.remove(os.path.join(dl, old))
    with zipfile.ZipFile(os.path.join(dl, "MT5_12_EAs.zip"), "w", zipfile.ZIP_DEFLATED) as z:
        for n in CORE:
            zi = zipfile.ZipInfo(n + ".mq5", date_time=(2026, 1, 1, 0, 0, 0)); zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, open(os.path.join(out, n + ".mq5"), "rb").read())
    print("wrote MT5_EAs/ (12 core + zip)")
    os.makedirs(os.path.join(dl, "pack"), exist_ok=True)
    with open(os.path.join(dl, "pack", "Breakout_Pack.mq5"), "w") as f:
        f.write(make_pack())
    print("wrote MT5_EAs/pack/Breakout_Pack.mq5")
