//+------------------------------------------------------------------+
//| BTC Dip v3 – MT5 EA. Chart: BTCUSD (or your broker's BTC symbol), H2
//| Buy when RSI(3) < 20 and close > EMA(50), unless the daily close is >15% below the close 30 days
//| earlier. Stop 2 x ATR(14) below the signal close (on the order). Exit after 48 H2 bars (4 days).
//| Portfolio risk: 0.75% per trade.  Python test 2020-2026: ~+20%/yr at 1% risk on its own.
//+------------------------------------------------------------------+
#property version "1.00"
#define REQUIRED_TF PERIOD_H2
input double InpRiskPct = 0.75;    // Risk per trade (% of balance)
input long   InpMagic   = 1101;   // Magic number (unique per EA)

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
