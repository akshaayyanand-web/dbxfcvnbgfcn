//+------------------------------------------------------------------+
//| Account Equity Guard – safety EA for ANY other EA (grids, martingales, manual trading).
//| Attach to one chart of the account. It watches the whole account, every symbol and every magic number:
//|  - Daily: once equity is InpDailyLossPct % of the start balance below the server-midnight balance (FTMO's rule),
//|    it closes ALL positions, deletes ALL pending orders, and keeps closing anything new until the next server day.
//|  - Total: once equity is InpMaxLossPct % below the start balance, it does the same for good (until you reset it).
//|  - Optional profit lock: once equity reaches the target, it closes everything so a phase is not given back.
//| It does not stop other EAs from sending orders: it closes them as they appear. Remove other EAs after a halt.
//+------------------------------------------------------------------+
#property version "1.00"
input double InpStartBalance   = 50000;  // Evaluation starting balance
input double InpDailyLossPct   = 4.0;    // Close everything at this loss today (firm limit usually 5)
input double InpMaxLossPct     = 8.0;    // Close everything for good at this total loss (firm limit usually 10)
input double InpProfitLockPct  = 0;      // Close everything once equity is this % above the start (0 = off; e.g. 10 for phase 1)
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
     { GlobalVariableSet(GV("HALT"), 1); Print("MAX LOSS reached (equity ", eq, "): everything closed, trading halted for good"); CloseEverything("Max-loss halt"); return; }
   if(DayStartBalance() - eq >= InpStartBalance * InpDailyLossPct / 100)
     { GlobalVariableSet(dayHalt, 1); Print("DAILY LOSS reached (equity ", eq, "): everything closed until the next server day"); CloseEverything("Daily halt"); return; }
   if(InpProfitLockPct > 0 && eq >= InpStartBalance * (1 + InpProfitLockPct / 100))
     { GlobalVariableSet(GV("HALT"), 1); Print("PROFIT TARGET reached (equity ", eq, "): everything closed"); CloseEverything("Profit lock"); }
  }
void OnTick()  { Check(); }
void OnTimer() { Check(); }
