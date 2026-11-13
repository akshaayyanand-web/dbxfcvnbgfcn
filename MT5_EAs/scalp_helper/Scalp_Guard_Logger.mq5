//+------------------------------------------------------------------+
//| Scalp Guard + Logger – helper EA for MANUAL scalping. Attach to the chart of the symbol you scalp (e.g. .USTECHCash).
//| 1) Every manual trade on this symbol gets a stop-loss and take-profit (in points) within a tick of opening.
//| 2) Daily loss limit: once today's closed + open loss reaches InpDailyLossUSD, open trades are closed and any new
//|    trade on this symbol is closed straight away until the next server day.
//| 3) Logs every closed trade to MQL5\Files\<InpLogFile>: times, prices, lots, spread at entry, max points for / against
//|    while open (MFE / MAE), seconds held, profit. Send that file back for analysis.
//| It does not open trades itself. Only manual trades (magic 0) on the chart's symbol are touched.
//+------------------------------------------------------------------+
#property version "1.00"
input double InpStopPts      = 20;     // Stop-loss distance in price points (0 = do not set one)
input double InpTargetPts    = 0;      // Take-profit distance in price points (0 = leave it to you)
input double InpDailyLossUSD = 1000;   // Daily loss limit in $ (0 = off)
input string InpLogFile      = "scalp_log.csv";
#include <Trade/Trade.mqh>
CTrade trade;
ulong  tk_[]; double mfe_[], mae_[], spr_[];
int Find(ulong t) { for(int i = 0; i < ArraySize(tk_); i++) if(tk_[i] == t) return i; return -1; }
int Track(ulong t, double spread)
  {
   int i = Find(t); if(i >= 0) return i;
   int n = ArraySize(tk_); ArrayResize(tk_, n + 1); ArrayResize(mfe_, n + 1); ArrayResize(mae_, n + 1); ArrayResize(spr_, n + 1);
   tk_[n] = t; mfe_[n] = 0; mae_[n] = 0; spr_[n] = spread; return n;
  }
int DayKey(datetime t) { MqlDateTime s; TimeToStruct(t, s); return s.year * 10000 + s.mon * 100 + s.day; }
double TodayPnL()
  {
   datetime now = TimeTradeServer(); MqlDateTime s; TimeToStruct(now, s); s.hour = 0; s.min = 0; s.sec = 0;
   double pnl = 0;
   if(HistorySelect(StructToTime(s), now + 60))
      for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
        {
         ulong d = HistoryDealGetTicket(i);
         if(HistoryDealGetString(d, DEAL_SYMBOL) != _Symbol || HistoryDealGetInteger(d, DEAL_MAGIC) != 0) continue;
         pnl += HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_COMMISSION) + HistoryDealGetDouble(d, DEAL_SWAP);
        }
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong p = PositionGetTicket(i);
      if(p == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != 0) continue;
      pnl += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
     }
   return pnl;
  }
int OnInit()
  {
   int f = FileOpen(InpLogFile, FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI, ',');
   if(f != INVALID_HANDLE)
     {
      if(FileSize(f) == 0) FileWrite(f, "position", "side", "lots", "open_time", "open_price", "close_time", "close_price", "seconds_held",
                                     "spread_at_entry_pts", "max_for_pts", "max_against_pts", "profit_usd", "stop_pts", "target_pts");
      FileClose(f);
     }
   Print("Scalp Guard + Logger on ", _Symbol, ": stop ", InpStopPts, " pts, target ", InpTargetPts, " pts, daily loss limit $", InpDailyLossUSD, ", log MQL5\\Files\\", InpLogFile);
   return INIT_SUCCEEDED;
  }
void OnTick()
  {
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   bool halted = InpDailyLossUSD > 0 && TodayPnL() <= -InpDailyLossUSD;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong p = PositionGetTicket(i);
      if(p == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != 0) continue;
      long type = PositionGetInteger(POSITION_TYPE); double op = PositionGetDouble(POSITION_PRICE_OPEN);
      int k = Track(PositionGetInteger(POSITION_IDENTIFIER), ask - bid);
      double fav = type == POSITION_TYPE_BUY ? bid - op : op - ask;
      mfe_[k] = MathMax(mfe_[k], fav); mae_[k] = MathMax(mae_[k], -fav);
      if(halted) { trade.PositionClose(p); Print("Daily loss limit reached: trade closed. No more trades today."); continue; }
      if(PositionGetDouble(POSITION_SL) == 0 && (InpStopPts > 0 || InpTargetPts > 0))
        {
         double sl = InpStopPts > 0 ? (type == POSITION_TYPE_BUY ? op - InpStopPts : op + InpStopPts) : 0;
         double tp = InpTargetPts > 0 ? (type == POSITION_TYPE_BUY ? op + InpTargetPts : op - InpTargetPts) : PositionGetDouble(POSITION_TP);
         if(!trade.PositionModify(p, NormalizeDouble(sl, _Digits), NormalizeDouble(tp, _Digits))) Print("Could not set SL/TP: ", trade.ResultRetcode());
        }
     }
  }
void OnTradeTransaction(const MqlTradeTransaction &tr, const MqlTradeRequest &rq, const MqlTradeResult &rs)
  {
   if(tr.type != TRADE_TRANSACTION_DEAL_ADD || !HistoryDealSelect(tr.deal)) return;
   if(HistoryDealGetString(tr.deal, DEAL_SYMBOL) != _Symbol || HistoryDealGetInteger(tr.deal, DEAL_MAGIC) != 0) return;
   if(HistoryDealGetInteger(tr.deal, DEAL_ENTRY) != DEAL_ENTRY_OUT) return;
   ulong pos = HistoryDealGetInteger(tr.deal, DEAL_POSITION_ID);
   if(!HistorySelectByPosition(pos)) return;
   datetime ot = 0; double opx = 0; long side = -1;
   for(int i = 0; i < HistoryDealsTotal(); i++)
     {
      ulong d = HistoryDealGetTicket(i);
      if(HistoryDealGetInteger(d, DEAL_ENTRY) == DEAL_ENTRY_IN) { ot = (datetime)HistoryDealGetInteger(d, DEAL_TIME); opx = HistoryDealGetDouble(d, DEAL_PRICE); side = HistoryDealGetInteger(d, DEAL_TYPE); }
     }
   HistoryDealSelect(tr.deal);
   datetime ct = (datetime)HistoryDealGetInteger(tr.deal, DEAL_TIME);
   double profit = HistoryDealGetDouble(tr.deal, DEAL_PROFIT) + HistoryDealGetDouble(tr.deal, DEAL_COMMISSION) + HistoryDealGetDouble(tr.deal, DEAL_SWAP);
   int k = Find(pos);
   int f = FileOpen(InpLogFile, FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI, ',');
   if(f == INVALID_HANDLE) { Print("Log file error ", GetLastError()); return; }
   FileSeek(f, 0, SEEK_END);
   FileWrite(f, (long)pos, side == DEAL_TYPE_BUY ? "buy" : "sell", DoubleToString(HistoryDealGetDouble(tr.deal, DEAL_VOLUME), 2),
             TimeToString(ot, TIME_DATE | TIME_SECONDS), DoubleToString(opx, _Digits), TimeToString(ct, TIME_DATE | TIME_SECONDS),
             DoubleToString(HistoryDealGetDouble(tr.deal, DEAL_PRICE), _Digits), (long)(ct - ot),
             k >= 0 ? DoubleToString(spr_[k], 2) : "", k >= 0 ? DoubleToString(mfe_[k], 2) : "", k >= 0 ? DoubleToString(mae_[k], 2) : "",
             DoubleToString(profit, 2), DoubleToString(InpStopPts, 1), DoubleToString(InpTargetPts, 1));
   FileClose(f);
  }
