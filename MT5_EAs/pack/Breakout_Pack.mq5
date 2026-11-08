//+------------------------------------------------------------------+
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
input double InpRisk_NQORB = 0.625;   // NQORB: risk per trade (% of balance, 0 = off)
input double InpRisk_NQBO15 = 0.2;   // NQBO15: risk per trade (% of balance, 0 = off)
input double InpRisk_NQBO5 = 0.05;   // NQBO5: risk per trade (% of balance, 0 = off)
input double InpRisk_SPXBO5 = 0.1;   // SPXBO5: risk per trade (% of balance, 0 = off)
input double InpRisk_DAXORB = 0.2;   // DAXORB: risk per trade (% of balance, 0 = off)
input double InpRisk_GOLDASIA = 0.3125;   // GOLDASIA: risk per trade (% of balance, 0 = off)
string gSym = ""; ENUM_TIMEFRAMES gTf = PERIOD_M5; long gMagic = 0; double gRisk = 0;

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
      if(PositionGetString(POSITION_SYMBOL) != gSym || PositionGetInteger(POSITION_MAGIC) != gMagic) continue;
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
      if(OrderGetString(ORDER_SYMBOL) != gSym || OrderGetInteger(ORDER_MAGIC) != gMagic) continue;
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
   double spread = SymbolInfoDouble(gSym, SYMBOL_ASK) - SymbolInfoDouble(gSym, SYMBOL_BID);
   if(spread <= InpMaxSpreadPct / 100.0 * stopDist) return false;
   static datetime lastWarn = 0;
   if(TimeCurrent() - lastWarn > 300)
     {
      Print(tag, ": spread ", DoubleToString(spread, (int)SymbolInfoInteger(gSym, SYMBOL_DIGITS)), " is over ", InpMaxSpreadPct, "% of the stop distance ",
            DoubleToString(stopDist, (int)SymbolInfoInteger(gSym, SYMBOL_DIGITS)), ", waiting up to 15 min for it to normalise");
      lastWarn = TimeCurrent();
     }
   gSpreadRetry = true;
   return true;
  }
double RiskMoney()
  {
   double bal = AccountInfoDouble(ACCOUNT_BALANCE), eq = AccountInfoDouble(ACCOUNT_EQUITY);
   double r = bal * gRisk * InpRiskMultiplier / 100;
   double dayRoom = InpAccountSize * InpDailyStopPct / 100 - MathMax(0, DayStartBalance() - eq);
   double maxRoom = eq - InpAccountSize * (1 - InpMaxStopPct / 100);
   r = MathMin(r, MathMin(dayRoom, maxRoom) * InpGuardShare / 100);
   if(InpRoomCapPct > 0)      // room cap: full size until the day starts 3% down, then shrink linearly to 0 at the firm limit
     {
      double room = DayStartBalance() - InpAccountSize * (1 - InpFirmMaxLossPct / 100);
      r *= MathMax(0, MathMin(1, room / (InpAccountSize * InpRoomCapPct / 100)));
     }
   if(InpHalfBelowPct > 0)    // half-size mode, shared by all EAs: on below -4% (day start), off again above -2%
     {
      double dsb = DayStartBalance();
      if(dsb <= InpAccountSize * (1 - InpHalfBelowPct / 100)) GlobalVariableSet("PP_HALF", 1);
      else if(dsb >= InpAccountSize * (1 - InpHalfUntilPct / 100) && GlobalVariableCheck("PP_HALF")) GlobalVariableDel("PP_HALF");
      if(GlobalVariableCheck("PP_HALF")) r *= 0.5;
     }
   return MathMax(r, 0);
  }
double LotsFor(double riskMoney, double stopDist, ENUM_ORDER_TYPE type, double price)
  {
   double tickSize = SymbolInfoDouble(gSym, SYMBOL_TRADE_TICK_SIZE);
   double tickVal  = SymbolInfoDouble(gSym, SYMBOL_TRADE_TICK_VALUE_LOSS);
   if(tickVal <= 0) tickVal = SymbolInfoDouble(gSym, SYMBOL_TRADE_TICK_VALUE);
   if(stopDist <= 0 || tickSize <= 0 || tickVal <= 0) return 0;
   double lossPerLot = stopDist / tickSize * tickVal;
   double step = SymbolInfoDouble(gSym, SYMBOL_VOLUME_STEP), vmin = SymbolInfoDouble(gSym, SYMBOL_VOLUME_MIN), vmax = SymbolInfoDouble(gSym, SYMBOL_VOLUME_MAX);
   double lots = MathFloor(riskMoney / lossPerLot / step) * step;
   if(lots < vmin) return 0;              // stop too wide for the allowed risk: skip the trade
   lots = MathMin(lots, vmax);
   double margin;
   while(lots >= vmin && OrderCalcMargin(type, gSym, lots, price, margin) && margin > AccountInfoDouble(ACCOUNT_MARGIN_FREE) * 0.9)
      lots -= step;
   return lots >= vmin ? NormalizeDouble(lots, 8) : 0;
  }
bool OpenTrade(int dir, double stopPrice, double tpPrice, string tag)
  {
   trade.SetExpertMagicNumber(gMagic); trade.SetTypeFillingBySymbol(gSym);
   if(NewsBlocked()) { Print(tag, ": high-impact news within ", InpNewsBlockMin, " min, skipped"); return false; }
   double price = dir == 1 ? SymbolInfoDouble(gSym, SYMBOL_ASK) : SymbolInfoDouble(gSym, SYMBOL_BID);
   double dist = MathAbs(price - stopPrice);
   if(dir * (price - stopPrice) <= 0) { Print(tag, ": price already beyond the stop, skipped"); return false; }
   if(SpreadTooWide(dist, tag)) return false;
   double lots = LotsFor(RiskMoney(), dist, dir == 1 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL, price);
   if(lots <= 0) { Print(tag, ": size below minimum for the allowed risk, skipped"); return false; }
   double sl = NormalizeDouble(stopPrice, (int)SymbolInfoInteger(gSym, SYMBOL_DIGITS)), tp = tpPrice > 0 ? NormalizeDouble(tpPrice, (int)SymbolInfoInteger(gSym, SYMBOL_DIGITS)) : 0;
   bool ok = dir == 1 ? trade.Buy(lots, gSym, 0, sl, tp, tag) : trade.Sell(lots, gSym, 0, sl, tp, tag);
   Print(tag, ok ? " opened " : " FAILED ", lots, " lots, SL ", sl, " TP ", tp, " retcode ", trade.ResultRetcode());
   return ok;
  }

//--- indicators -------------------------------------------------------------------
double Rsi(int len, int shift)
  {
   static int hs[40]; static string ks[40]; static int n = 0; string key = gSym + "|" + IntegerToString(gTf) + "|" + IntegerToString(len); int h = INVALID_HANDLE;
   for(int i = 0; i < n; i++) if(ks[i] == key) h = hs[i];
   if(h == INVALID_HANDLE && n < 40) { h = iRSI(gSym, gTf, len, PRICE_CLOSE); hs[n] = h; ks[n] = key; n++; }
   double b[]; ArraySetAsSeries(b, true);
   if(CopyBuffer(h, 0, shift, 1, b) < 1) return EMPTY_VALUE;
   return b[0];
  }
double Ema(int len, int shift)
  {
   static int hs[40]; static string ks[40]; static int n = 0; string key = gSym + "|" + IntegerToString(gTf) + "|" + IntegerToString(len); int h = INVALID_HANDLE;
   for(int i = 0; i < n; i++) if(ks[i] == key) h = hs[i];
   if(h == INVALID_HANDLE && n < 40) { h = iMA(gSym, gTf, len, 0, MODE_EMA, PRICE_CLOSE); hs[n] = h; ks[n] = key; n++; }
   double b[]; ArraySetAsSeries(b, true);
   if(CopyBuffer(h, 0, shift, 1, b) < 1) return EMPTY_VALUE;
   return b[0];
  }
double AtrRma(int len, int shift)   // Wilder ATR (same as TradingView ta.atr / the Python tests)
  {
   MqlRates r[]; ArraySetAsSeries(r, false);
   int got = CopyRates(gSym, gTf, shift, 500, r);
   if(got < len + 2) return EMPTY_VALUE;
   double a = r[1].high - r[1].low;
   for(int i = 1; i < got; i++)
     {
      double tr = MathMax(r[i].high - r[i].low, MathMax(MathAbs(r[i].high - r[i - 1].close), MathAbs(r[i].low - r[i - 1].close)));
      a = (i == 1) ? tr : a + (tr - a) / len;
     }
   return a;
  }

//=== module NQORB (from NQ_Opening_Range.mq5) ===
int lastTradeDay_NQORB = 0;
void OnNewBar_NQORB()
  {
   ulong tk; long tp; datetime ot;
   datetime n0 = ToNY(iTime(gSym, gTf, 0)), n1 = ToNY(iTime(gSym, gTf, 1));
   if(MyPosition(tk, tp, ot))
     {
      if(MinuteOfDay(n0) >= 955 || DayKey(n0) != DayKey(ToNY(ot))) CloseMine("Flat 15:55 New York");
      return;
     }
   int day = DayKey(n1), m1 = MinuteOfDay(n1);
   if(m1 < 585 || m1 >= 690 || day == lastTradeDay_NQORB) return;  // signal bars 09:45 .. 11:25
   double hi = -DBL_MAX, lo = DBL_MAX; int cnt = 0;
   for(int i = 1; i < 60; i++)
     {
      datetime nt = ToNY(iTime(gSym, gTf, i));
      if(DayKey(nt) != day) break;
      int m = MinuteOfDay(nt);
      if(m >= 570 && m < 585) { hi = MathMax(hi, iHigh(gSym, gTf, i)); lo = MathMin(lo, iLow(gSym, gTf, i)); cnt++; }
     }
   if(cnt < 2 || hi <= lo) return;
   double c1 = iClose(gSym, gTf, 1);
   int dir = c1 > hi ? 1 : (c1 < lo ? -1 : 0);
   if(dir == 0) return;
   double stop = dir == 1 ? lo : hi;
   double price = dir == 1 ? SymbolInfoDouble(gSym, SYMBOL_ASK) : SymbolInfoDouble(gSym, SYMBOL_BID);
   if(OpenTrade(dir, stop, price + dir * 2.0 * MathAbs(price - stop), "NQ ORB") || !gSpreadRetry) lastTradeDay_NQORB = day;
  }

//=== module NQBO15 (from NQ_Breakout_15m.mq5) ===
void OnNewBar_NQBO15()
  {
   ulong tk; long tp; datetime ot;
   datetime n0 = ToNY(iTime(gSym, gTf, 0)), n1 = ToNY(iTime(gSym, gTf, 1));
   if(MyPosition(tk, tp, ot))
     {
      if(MinuteOfDay(n0) >= 950 || DayKey(n0) != DayKey(ToNY(ot))) CloseMine("Flat 15:50 New York");
      return;
     }
   int m1 = MinuteOfDay(n1);
   if(m1 < 570 || m1 >= 720) return;                         // signal bar inside 09:30-12:00 New York
   double c1 = iClose(gSym, gTf, 1), ema = Ema(200, 1), atr = AtrRma(14, 1);
   if(ema == EMPTY_VALUE || atr == EMPTY_VALUE || atr <= 0) return;
   int hiIdx = iHighest(gSym, gTf, MODE_HIGH, 20, 2), loIdx = iLowest(gSym, gTf, MODE_LOW, 20, 2);
   if(hiIdx < 0 || loIdx < 0) return;
   double hi = iHigh(gSym, gTf, hiIdx), lo = iLow(gSym, gTf, loIdx);
   int dir = (c1 > hi && c1 > ema) ? 1 : ((c1 < lo && c1 < ema) ? -1 : 0);
   if(dir == 0) return;
   double price = dir == 1 ? SymbolInfoDouble(gSym, SYMBOL_ASK) : SymbolInfoDouble(gSym, SYMBOL_BID);
   OpenTrade(dir, price - dir * atr, 0, "NQ Breakout 15m");
  }

//=== module NQBO5 (from NQ_Breakout_5m) ===
void OnNewBar_NQBO5()
  {
   ulong tk; long tp; datetime ot;
   datetime n0 = ToNY(iTime(gSym, gTf, 0)), n1 = ToNY(iTime(gSym, gTf, 1));
   if(MyPosition(tk, tp, ot))
     {
      if(MinuteOfDay(n0) >= 950 || DayKey(n0) != DayKey(ToNY(ot))) CloseMine("Flat 15:50 New York");
      return;
     }
   int m1 = MinuteOfDay(n1);
   if(m1 < 570 || m1 >= 720) return;                         // signal bar inside 09:30-12:00 New York
   double c1 = iClose(gSym, gTf, 1), ema = Ema(800, 1), atr = AtrRma(14, 1);
   if(ema == EMPTY_VALUE || atr == EMPTY_VALUE || atr <= 0) return;
   int hiIdx = iHighest(gSym, gTf, MODE_HIGH, 50, 2), loIdx = iLowest(gSym, gTf, MODE_LOW, 50, 2);
   if(hiIdx < 0 || loIdx < 0) return;
   double hi = iHigh(gSym, gTf, hiIdx), lo = iLow(gSym, gTf, loIdx);
   int dir = (c1 > hi && c1 > ema) ? 1 : ((c1 < lo && c1 < ema) ? -1 : 0);
   if(dir == 0) return;
   double price = dir == 1 ? SymbolInfoDouble(gSym, SYMBOL_ASK) : SymbolInfoDouble(gSym, SYMBOL_BID);
   OpenTrade(dir, price - dir * 2 * atr, 0, "NQ Breakout 5m");
  }

//=== module SPXBO5 (from SPX_Breakout_5m.mq5) ===
void OnNewBar_SPXBO5()
  {
   ulong tk; long tp; datetime ot;
   datetime n0 = ToNY(iTime(gSym, gTf, 0)), n1 = ToNY(iTime(gSym, gTf, 1));
   if(MyPosition(tk, tp, ot))
     {
      if(MinuteOfDay(n0) >= 950 || DayKey(n0) != DayKey(ToNY(ot))) CloseMine("Flat 15:50 New York");
      return;
     }
   int m1 = MinuteOfDay(n1);
   if(m1 < 570 || m1 >= 720) return;                         // signal bar inside 09:30-12:00 New York
   double c1 = iClose(gSym, gTf, 1), ema = Ema(200, 1), atr = AtrRma(14, 1);
   if(ema == EMPTY_VALUE || atr == EMPTY_VALUE || atr <= 0) return;
   int hiIdx = iHighest(gSym, gTf, MODE_HIGH, 50, 2), loIdx = iLowest(gSym, gTf, MODE_LOW, 50, 2);
   if(hiIdx < 0 || loIdx < 0) return;
   double hi = iHigh(gSym, gTf, hiIdx), lo = iLow(gSym, gTf, loIdx);
   int dir = (c1 > hi && c1 > ema) ? 1 : ((c1 < lo && c1 < ema) ? -1 : 0);
   if(dir == 0) return;
   double price = dir == 1 ? SymbolInfoDouble(gSym, SYMBOL_ASK) : SymbolInfoDouble(gSym, SYMBOL_BID);
   OpenTrade(dir, price - dir * 2 * atr, 0, "SPX Breakout 5m");
  }

//=== module DAXORB (from DAX_Opening_Range.mq5) ===
datetime ToFrankfurt(datetime s) { datetime u = ToUTC(s); return u + (IsUKDST(u) ? 7200 : 3600); }   // EU and UK switch DST together
double EmaD1(int len)       // EMA(len) of daily closes up to yesterday
  {
   int n = MathMin(iBars(gSym, PERIOD_D1) - 1, 5 * len);
   if(n < 2 * len) return EMPTY_VALUE;
   double a = 2.0 / (len + 1), e = iClose(gSym, PERIOD_D1, n);
   for(int k = n - 1; k >= 1; k--) e = a * iClose(gSym, PERIOD_D1, k) + (1 - a) * e;
   return e;
  }
int lastTradeDay_DAXORB = 0;
void OnNewBar_DAXORB()
  {
   ulong tk; long tp; datetime ot;
   datetime f0 = ToFrankfurt(iTime(gSym, gTf, 0)), f1 = ToFrankfurt(iTime(gSym, gTf, 1));
   if(MyPosition(tk, tp, ot))
     {
      if(MinuteOfDay(f0) >= 1045 || DayKey(f0) != DayKey(ToFrankfurt(ot))) CloseMine("Flat 17:25 Frankfurt");
      return;
     }
   int m1 = MinuteOfDay(f1), day = DayKey(f1);
   if(m1 < 570 || m1 >= 720 || day == lastTradeDay_DAXORB || DayKey(f0) != day) return;   // signal bar 09:30-12:00 Frankfurt
   double hi = -1, lo = -1;
   for(int k = 1; k < 60; k++)
     {
      datetime fk = ToFrankfurt(iTime(gSym, gTf, k));
      if(DayKey(fk) != day) break;
      int mk = MinuteOfDay(fk);
      if(mk >= 540 && mk < 570)
        {
         double h = iHigh(gSym, gTf, k), l = iLow(gSym, gTf, k);
         hi = hi < 0 ? h : MathMax(hi, h); lo = lo < 0 ? l : MathMin(lo, l);
        }
     }
   if(hi <= 0 || lo <= 0 || hi <= lo) return;
   double c1 = iClose(gSym, gTf, 1), ema = EmaD1(50);
   if(ema == EMPTY_VALUE) return;
   int dir = 0;
   if(c1 > hi && c1 > ema) dir = 1;
   if(c1 < lo && c1 < ema) dir = -1;
   if(dir == 0) return;
   if(OpenTrade(dir, (hi + lo) / 2, 0, "DAX Opening Range") || !gSpreadRetry) lastTradeDay_DAXORB = day;
  }

//=== module GOLDASIA (from Gold_Asia_Breakout.mq5) ===
int lastTradeDay_GOLDASIA = 0;
void OnNewBar_GOLDASIA()
  {
   ulong tk; long tp; datetime ot;
   datetime l0 = ToLondon(iTime(gSym, gTf, 0)), l1 = ToLondon(iTime(gSym, gTf, 1));
   if(MyPosition(tk, tp, ot))
     {
      if(HourOf(l0) >= 20 || DayKey(l0) != DayKey(ToLondon(ot))) CloseMine("Flat 20:00 London");
      return;
     }
   int day = DayKey(l1), h1 = HourOf(l1);
   if(h1 < 7 || h1 >= 14 || day == lastTradeDay_GOLDASIA) return;
   double hi = -DBL_MAX, lo = DBL_MAX; int cnt = 0;
   for(int i = 1; i < 48; i++)
     {
      datetime lt = ToLondon(iTime(gSym, gTf, i));
      if(DayKey(lt) != day) break;
      if(HourOf(lt) < 7) { hi = MathMax(hi, iHigh(gSym, gTf, i)); lo = MathMin(lo, iLow(gSym, gTf, i)); cnt++; }
     }
   if(cnt < 4 || hi <= lo) return;
   double c1 = iClose(gSym, gTf, 1), mid = (hi + lo) / 2;
   int dir = c1 > hi ? 1 : (c1 < lo ? -1 : 0);
   if(dir == 0) return;
   if(OpenTrade(dir, mid, 0, "Gold Asia BO") || !gSpreadRetry) lastTradeDay_GOLDASIA = day;
  }

//--- pack plumbing -------------------------------------------------------------------
#define NMOD 6
datetime gLastBar[NMOD]; bool gRetry[NMOD];
void CallModule(int k);
void SetCtx(int k)
  {
   if(k == 0) { gSym = InpSymNQ; gTf = PERIOD_M5; gMagic = 1106; gRisk = InpRisk_NQORB; }
   if(k == 1) { gSym = InpSymNQ; gTf = PERIOD_M15; gMagic = 1112; gRisk = InpRisk_NQBO15; }
   if(k == 2) { gSym = InpSymNQ; gTf = PERIOD_M5; gMagic = 1116; gRisk = InpRisk_NQBO5; }
   if(k == 3) { gSym = InpSymSPX; gTf = PERIOD_M5; gMagic = 1113; gRisk = InpRisk_SPXBO5; }
   if(k == 4) { gSym = InpSymDAX; gTf = PERIOD_M15; gMagic = 1115; gRisk = InpRisk_DAXORB; }
   if(k == 5) { gSym = InpSymGold; gTf = PERIOD_H1; gMagic = 1103; gRisk = InpRisk_GOLDASIA; }
  }
void RunAll()
  {
   for(int k = 0; k < NMOD; k++)
     {
      SetCtx(k);
      if(gSym == "" || gRisk <= 0) continue;
      bool blocked = GuardBlocks();
      datetime b0 = iTime(gSym, gTf, 0);
      if(b0 == 0) continue;
      if(b0 == gLastBar[k])
        {
         if(gRetry[k] && !blocked && TimeCurrent() - b0 < 15 * 60) { gSpreadRetry = false; CallModule(k); gRetry[k] = gSpreadRetry; }
         continue;
        }
      gLastBar[k] = b0; gSpreadRetry = false;
      if(!blocked) CallModule(k);
      gRetry[k] = gSpreadRetry;
     }
  }
void CallModule(int k)
  {
   if(k == 0) OnNewBar_NQORB();
   if(k == 1) OnNewBar_NQBO15();
   if(k == 2) OnNewBar_NQBO5();
   if(k == 3) OnNewBar_SPXBO5();
   if(k == 4) OnNewBar_DAXORB();
   if(k == 5) OnNewBar_GOLDASIA();
  }
int OnInit()
  {
   trade.SetDeviationInPoints(50);
   string syms[4]; syms[0] = InpSymNQ; syms[1] = InpSymSPX; syms[2] = InpSymDAX; syms[3] = InpSymGold;
   for(int i = 0; i < 4; i++)
      if(syms[i] != "" && !SymbolSelect(syms[i], true)) Print("WARNING: symbol '", syms[i], "' not found - type your broker's exact name in the inputs");
   for(int k = 0; k < NMOD; k++) { gLastBar[k] = 0; gRetry[k] = false; }
   EventSetTimer(5);
   return INIT_SUCCEEDED;
  }
void OnDeinit(const int reason) { EventKillTimer(); }
void OnTick()  { RunAll(); }
void OnTimer() { RunAll(); }
