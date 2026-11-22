//+------------------------------------------------------------------+
//| Account Equity Guard – safety EA for ANY other EA (grids, martingales, manual trading).
//| Attach to one chart of the account. It watches the whole account, every symbol and every magic number:
//|  - Daily: once equity is InpDailyLossPct % of the start balance below the server-midnight balance (FTMO's rule),
//|    it closes ALL positions, deletes ALL pending orders, and keeps closing anything new until the next server day.
//|  - Total: once equity is InpMaxLossPct % below the start balance, it does the same for good (until you reset it).
//|  - Optional floating-loss cap (FundedSquad's 1.5% max floating loss rule): closes everything at InpMaxFloatingPct and stops
//|    the generated EAs for the rest of the server day (sets their PP_DH_ day-halt flag).
//|  - Optional trailing max loss (TopOneTrader NOVA): the line follows the highest equity and stops at the start balance.
//|  - Optional profit lock: once equity reaches the target, it closes everything so a phase is not given back.
//| It does not stop other EAs from sending orders: it closes them as they appear. Remove other EAs after a halt.
//+------------------------------------------------------------------+
#property version "1.00"
input double InpStartBalance   = 50000;  // Evaluation starting balance
input double InpDailyLossPct   = 4.0;    // Close everything at this loss today (firm limit usually 5)
input double InpMaxLossPct     = 8.0;    // Close everything for good at this total loss (firm limit usually 10)
input double InpProfitLockPct  = 0;      // Close everything once equity is this % above the start (0 = off; e.g. 10 for phase 1)
input double InpMaxFloatingPct = 0;      // Close everything once ALL open trades together are this % of the start in loss, and stop the EAs for the day (0 = off; FundedSquad: 1.2)
input bool   InpFloatHaltDay   = true;   // After the floating cap: stop the EAs for the rest of the day (false = just close the trades and keep trading)
input double InpTrailLossPct   = 0;      // Trailing max loss: close everything for good once equity is this % (of the start) below its highest point; locks at the start balance (0 = off; TopOneTrader NOVA eval: 5.5)
#include <Trade/Trade.mqh>
CTrade trade;
int DayKey(datetime t) { MqlDateTime s; TimeToStruct(t, s); return s.year * 10000 + s.mon * 100 + s.day; }
string GV(string k) { return "AEG_" + k; }
double DayStartBalance()
  {
   string n = GV("DS_" + IntegerToString(DayKey(TimeTradeServer())));
   if(!GlobalVariableCheck(n)) GlobalVariableSet(n, AccountInfoDouble(ACCOUNT_BALANCE));
   return GlobalVariableGet(n);
  }
void CloseEverything(string why)
  {
   for(int i = OrdersTotal() - 1; i >= 0; i--) { ulong o = OrderGetTicket(i); if(o > 0) trade.OrderDelete(o); }
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong p = PositionGetTicket(i);
      if(p == 0) continue;
      trade.SetTypeFillingBySymbol(PositionGetString(POSITION_SYMBOL));
      if(!trade.PositionClose(p)) Print(why, ": close failed for ", p, " retcode ", trade.ResultRetcode());
     }
  }
int OnInit()
  {
   trade.SetDeviationInPoints(100); EventSetTimer(1);
   Print("Account Equity Guard: start ", InpStartBalance, ", daily stop ", InpDailyLossPct, "%, max stop ", InpMaxLossPct, "%, profit lock ", InpProfitLockPct, "%");
   return INIT_SUCCEEDED;
  }
void OnDeinit(const int r) { EventKillTimer(); }
void Check()
  {
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   string dayHalt = GV("DH_" + IntegerToString(DayKey(TimeTradeServer())));
   if(GlobalVariableCheck(GV("HALT"))) { CloseEverything("Max-loss halt"); return; }
   if(GlobalVariableCheck(dayHalt))   { CloseEverything("Daily halt"); return; }
   if(eq <= InpStartBalance * (1 - InpMaxLossPct / 100))
     { GlobalVariableSet(GV("HALT"), 1); GlobalVariableSet("PP_HALT", 1); Print("MAX LOSS reached (equity ", eq, "): everything closed, trading halted for good"); CloseEverything("Max-loss halt"); return; }
   if(DayStartBalance() - eq >= InpStartBalance * InpDailyLossPct / 100)
     { GlobalVariableSet(dayHalt, 1); GlobalVariableSet("PP_DH_" + IntegerToString(DayKey(TimeTradeServer())), 1); GlobalVariableSet("PP_DH_" + IntegerToString(DayKey(TimeGMT())), 1); Print("DAILY LOSS reached (equity ", eq, "): everything closed until the next server day"); CloseEverything("Daily halt"); return; }
   if(InpTrailLossPct > 0)
     {
      double pk = GlobalVariableCheck(GV("PEAK")) ? GlobalVariableGet(GV("PEAK")) : InpStartBalance;
      if(eq > pk) { pk = eq; GlobalVariableSet(GV("PEAK"), pk); }
      double fl = MathMin(InpStartBalance, pk - InpStartBalance * InpTrailLossPct / 100);
      if(eq <= fl) { GlobalVariableSet(GV("HALT"), 1); GlobalVariableSet("PP_HALT", 1); Print("TRAILING MAX LOSS reached (equity ", eq, ", peak ", pk, "): everything closed, trading halted for good"); CloseEverything("Trailing max-loss halt"); return; }
     }
   double flt = eq - AccountInfoDouble(ACCOUNT_BALANCE);
   if(InpMaxFloatingPct > 0 && flt <= -InpStartBalance * InpMaxFloatingPct / 100)
     {
      if(InpFloatHaltDay) { GlobalVariableSet(dayHalt, 1); GlobalVariableSet("PP_DH_" + IntegerToString(DayKey(TimeTradeServer())), 1); GlobalVariableSet("PP_DH_" + IntegerToString(DayKey(TimeGMT())), 1); }   // also halts the EAs today
      Print("FLOATING LOSS cap reached (open P&L ", DoubleToString(flt, 2), "): everything closed", InpFloatHaltDay ? ", EAs stopped until the next server day" : "");
      CloseEverything("Floating cap"); return;
     }
   if(InpProfitLockPct > 0 && eq >= InpStartBalance * (1 + InpProfitLockPct / 100))
     { GlobalVariableSet(GV("HALT"), 1); GlobalVariableSet("PP_HALT", 1); Print("PROFIT TARGET reached (equity ", eq, "): everything closed"); CloseEverything("Profit lock"); }
  }
void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_REQUEST) return;      // the guard's own requests (emergency closes) count too
   string k = "PP_REQ_" + IntegerToString(DayKey(TimeTradeServer())); if(!GlobalVariableCheck(k)) GlobalVariableSet(k, 0);
   for(int i = 0; i < 50; i++) { double v = GlobalVariableGet(k); if(GlobalVariableSetOnCondition(k, v + 1, v)) break; }
  }
void ReportActivity()   // hourly summary in the Experts log
  {
   static int lastHour = -1; MqlDateTime s; TimeToStruct(TimeTradeServer(), s);
   if(s.hour == lastHour) return; lastHour = s.hour;
   string d = IntegerToString(DayKey(TimeTradeServer()));
   int req = GlobalVariableCheck("PP_REQ_" + d) ? (int)GlobalVariableGet("PP_REQ_" + d) : 0, op = GlobalVariableCheck("PP_OPENS_" + d) ? (int)GlobalVariableGet("PP_OPENS_" + d) : 0;
   Print("Activity today: ", req, " server requests, ", op, " positions opened, ", PositionsTotal(), " open now, margin used ",
         DoubleToString(AccountInfoDouble(ACCOUNT_MARGIN) / MathMax(AccountInfoDouble(ACCOUNT_EQUITY), 1) * 100, 1), "% of equity");
  }
void OnTick()  { Check(); }
void OnTimer() { Check(); ReportActivity(); }
