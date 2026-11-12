//+------------------------------------------------------------------+
//| NQ ORB All-In – one-day-pass EA for evaluations WITHOUT a consistency rule (LucidPro / Apex / Tradeify Growth style).
//| Chart: Nasdaq 100 (US100 / NAS100 / USTEC / NQ / MNQ), M5. New York clock.
//| Strategy: range = 09:30-09:45 New York. First M5 close outside it until 11:30 -> buy / sell, stop at the other side
//| of the range. One trade per day, flat at 15:55 New York.
//| Sizing: each trade risks (InpRoomShare %) of the room left above the max-loss line (and the daily loss limit, if any),
//| minus a safety buffer. Take-profit = exactly what is still needed to reach the profit target. Stops for good once
//| the target is reached. Max-loss line: InpMaxLoss under the highest END-OF-DAY balance, never above the start balance.
//| Python 2020-2026, 50K ($3,000 target / $2,000 trailing): median 3.8 days to funded, 78% within 7 days,
//| 94% within 14 days, 2.2 accounts on average (42% pass on the first). tools/futures_allin_test.py
//| THIS SIZING BLOWS ACCOUNTS ON PURPOSE (~58% of attempts). Never run it on a funded account.
//+------------------------------------------------------------------+
#property version "1.00"
#property strict
input double InpStartBalance  = 50000;  // Evaluation starting balance
input double InpProfitTarget  = 3000;   // Profit target ($)
input double InpMaxLoss       = 2000;   // Max loss / trailing drawdown ($)
input bool   InpTrailingEOD   = true;   // true: max-loss line trails the highest end-of-day balance (locks at the start balance); false: static
input double InpDailyLoss     = 0;      // Daily loss limit ($), 0 = the account has none
input double InpRoomShare     = 100;    // % of the room left to risk on each trade (100 = all-in; 75 = slower, a bit fewer blown accounts)
input double InpSafety        = 75;     // $ kept back from the room for slippage and gaps
input double InpCommission    = 1.5;    // Round-turn commission per lot ($), counted in the size
input double InpMaxLots       = 0;      // Max lots / contracts per trade (0 = no cap). Set your firm's limit (e.g. 5 minis or 50 micros)
input int    InpEodHourNY     = 17;     // Hour (New York) at which the firm takes the end-of-day balance
input long   InpMagic         = 2201;   // Magic number
input bool   InpAutoServerOffset = true; // Live: detect the server's GMT offset automatically
input int    InpServerGMTOffset  = 2;    // Tester: server GMT offset in winter
input bool   InpServerUsesUSDST  = true; // Tester: server shifts +1h with US daylight saving
#include <Trade/Trade.mqh>
CTrade trade;
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


//--- evaluation state (kept in terminal global variables so a restart does not lose it) -------------------
string GV(string k) { return "ODP_" + IntegerToString(InpMagic) + "_" + k; }
double PeakEOD() { if(!GlobalVariableCheck(GV("peak"))) GlobalVariableSet(GV("peak"), InpStartBalance); return GlobalVariableGet(GV("peak")); }
double Floor()   { return InpTrailingEOD ? MathMin(PeakEOD() - InpMaxLoss, InpStartBalance) : InpStartBalance - InpMaxLoss; }
int    TradingDayNY(datetime serverT) { datetime n = ToNY(serverT); if(HourOf(n) >= InpEodHourNY) n += 86400; return DayKey(n); }
void UpdateEOD()      // when a new trading day starts, the last balance becomes the end-of-day balance
  {
   int d = TradingDayNY(TimeTradeServer());
   if(!GlobalVariableCheck(GV("day"))) { GlobalVariableSet(GV("day"), d); GlobalVariableSet(GV("dstart"), AccountInfoDouble(ACCOUNT_BALANCE)); return; }
   if((int)GlobalVariableGet(GV("day")) == d) return;
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   if(bal > PeakEOD()) GlobalVariableSet(GV("peak"), bal);
   GlobalVariableSet(GV("day"), d); GlobalVariableSet(GV("dstart"), bal);
   Print("New trading day: EOD balance ", DoubleToString(bal, 2), ", max-loss line now ", DoubleToString(Floor(), 2));
  }
bool TargetReached() { return AccountInfoDouble(ACCOUNT_BALANCE) >= InpStartBalance + InpProfitTarget; }
double RiskRoom()
  {
   double eq = AccountInfoDouble(ACCOUNT_EQUITY), room = eq - Floor();
   if(InpDailyLoss > 0) room = MathMin(room, InpDailyLoss - MathMax(0, GlobalVariableGet(GV("dstart")) - eq));
   return room;
  }
//--- sizing -----------------------------------------------------------------------
double ValuePerPointPerLot()
  {
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE), tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
   if(tv <= 0) tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   return ts > 0 ? tv / ts : 0;
  }
double LotsForRisk(double money, double dist, ENUM_ORDER_TYPE type, double price)
  {
   double vpp = ValuePerPointPerLot(); if(vpp <= 0 || dist <= 0 || money <= 0) return 0;
   double perLot = dist * vpp + InpCommission;
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP), vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN), vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lots = MathFloor(money / perLot / step) * step;
   if(InpMaxLots > 0) lots = MathMin(lots, InpMaxLots);
   lots = MathMin(lots, vmax);
   double margin;
   while(lots >= vmin && OrderCalcMargin(type, _Symbol, lots, price, margin) && margin > AccountInfoDouble(ACCOUNT_MARGIN_FREE) * 0.95) lots -= step;
   return lots >= vmin ? NormalizeDouble(lots, 8) : 0;
  }
//--- strategy ---------------------------------------------------------------------
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
   if(TargetReached()) return;
   int day = DayKey(n1), m1 = MinuteOfDay(n1);
   if(m1 < 585 || m1 >= 690 || day == lastTradeDay) return;          // signal bars 09:45 .. 11:25 New York
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
   double price = dir == 1 ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double stop = dir == 1 ? lo : hi, dist = MathAbs(price - stop);
   if(dir * (price - stop) <= 0) { Print("Price already beyond the stop, no trade today"); return; }
   double money = RiskRoom() * InpRoomShare / 100.0 - InpSafety;
   if(money <= 0) { Print("No room left above the max-loss line: this evaluation is over"); return; }
   double lots = LotsForRisk(money, dist, dir == 1 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL, price);
   if(lots <= 0) { Print("Stop too wide for the room left (", DoubleToString(money, 0), "$), no trade today"); return; }
   double need = InpStartBalance + InpProfitTarget - AccountInfoDouble(ACCOUNT_BALANCE) + InpCommission * lots + 10;
   double tpDist = need / (lots * ValuePerPointPerLot());
   double sl = NormalizeDouble(stop, _Digits), tpp = NormalizeDouble(price + dir * tpDist, _Digits);
   bool ok = dir == 1 ? trade.Buy(lots, _Symbol, 0, sl, tpp, "NQ ORB All-In") : trade.Sell(lots, _Symbol, 0, sl, tpp, "NQ ORB All-In");
   Print(ok ? "Opened " : "FAILED ", dir == 1 ? "BUY " : "SELL ", lots, " lots, risk $", DoubleToString(lots * (dist * ValuePerPointPerLot() + InpCommission), 0),
         ", target +$", DoubleToString(need, 0), " (", DoubleToString(tpDist / dist, 2), "R), SL ", sl, " TP ", tpp, ", retcode ", trade.ResultRetcode());
  }
//--- events -------------------------------------------------------------------------
int OnInit()
  {
   trade.SetExpertMagicNumber(InpMagic); trade.SetDeviationInPoints(50); trade.SetTypeFillingBySymbol(_Symbol);
   if(_Period != PERIOD_M5) Print("WARNING: attach this EA to an M5 chart");
   UpdateEOD();
   Print("NQ ORB All-In: balance ", AccountInfoDouble(ACCOUNT_BALANCE), ", max-loss line ", DoubleToString(Floor(), 2), ", target ", InpStartBalance + InpProfitTarget);
   return INIT_SUCCEEDED;
  }
void OnTick()
  {
   UpdateEOD();
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq <= Floor() + 5) { CloseMine("At the max-loss line"); return; }
   if(TargetReached()) { static bool said = false; if(!said) { Print("PROFIT TARGET REACHED – EA stopped. Remove it now."); said = true; } CloseMine("Target reached"); return; }
   static datetime lastBar = 0; datetime b0 = iTime(_Symbol, _Period, 0);
   if(b0 == lastBar || _Period != PERIOD_M5) return;
   lastBar = b0; OnNewBar();
  }
