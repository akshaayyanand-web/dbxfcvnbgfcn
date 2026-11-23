//+------------------------------------------------------------------+
//| Gold Asia-Range Breakout – MT5 EA. Chart: XAUUSD, H1 (London clock)
//| Range = 00:00-07:00 London. First H1 close above / below it between 07:00 and 14:00 London -> buy /
//| sell, stop at the range middle (on the order). One trade per day. Flat at 20:00 London.
//| Portfolio risk: 0.3125% per trade.
//+------------------------------------------------------------------+
#property version "1.00"
#define REQUIRED_TF PERIOD_H1
input double InpRiskPct = 0.2;    // Risk per trade (% of balance)
input long   InpMagic   = 1103;   // Magic number (unique per EA)

#include <Trade/Trade.mqh>
CTrade trade;

//--- common inputs
input double InpAccountSize      = 10000; // Starting balance of the prop account
input double InpDailyStopPct     = 4.0;    // ACCOUNT guard: stop for the day at this loss (% of start; firm limit 5)
input double InpMaxStopPct       = 9.5;    // ACCOUNT guard: stop everything at this loss from start (firm limit 10)
input double InpRoomCapPct       = 8.0;    // Room cap: size shrinks to 0 as the day-start balance nears the firm limit (full size above -3%; 0 = off)
input double InpHalfBelowPct     = 0;    // Half size for all EAs once a day starts this % below the start balance (0 = off)
input double InpHalfUntilPct     = 0;    // ...and stay at half size until a day starts no more than this % below it
input double InpFirmMaxLossPct   = 10.0;   // The firm's max-loss limit (% of start) used by the room cap
input double InpGuardShare       = 60;     // A trade may risk at most this % of the remaining daily / max room
input double InpRiskMultiplier   = 1.0;    // Keep 1.0: the default risks are already the tested fast preset (see README)
input bool   InpAutoServerOffset = true;   // Live: detect the server's GMT offset automatically
input int    InpServerGMTOffset  = 2;      // Tester: server GMT offset in winter (FTMO-style servers: 2)
input bool   InpServerUsesUSDST  = true;   // Tester: server shifts +1h with US daylight saving (FTMO-style)
input int    InpNewsBlockMin     = 5;      // No NEW trades this many minutes before/after high-impact USD news (0 = off)
input double InpMaxSpreadPct     = 15;     // Skip a trade if the current spread is more than this % of its stop distance (0 = off)
input int    InpMaxPosPerSymbol  = 0;      // Skip a trade if this many positions (any EA) are already open on the symbol (0 = off; FundedSquad: 2)
input bool   InpNoOpposite       = false;  // Skip a trade if any EA has the opposite direction open on the symbol (FundedSquad: true, no hedging)
input bool   InpNoWeekendEntries = false;  // No new trades on Saturday/Sunday (UTC) (FundedSquad: true)
input bool   InpDailyResetUTC    = false;  // Daily loss day starts at 00:00 UTC instead of server midnight (FundedSquad: true)
input bool   InpDailyRefHigher   = true;  // Daily loss measured from the HIGHER of day-start balance and equity (FundedSquad: true)
input int    InpMinHoldSec       = 0;      // Minimum hold: no trade closes by its SL/TP before this many seconds (0 = off; FundedSquad: 130)
input bool   InpTrailingMaxLoss  = false;  // Max-loss levels trail the highest equity and lock at the starting balance (TopOneTrader NOVA: true)
input double InpHoldStopMult     = 1.5;    // During the minimum hold the server stop sits this many x the normal stop distance away (emergency only)
input int    InpMaxOpenTotal     = 6;      // Skip a new trade if the ACCOUNT already has this many open positions (0 = off; The5ers pack: 5)
input int    InpStaggerSec       = 90;      // Wait this many seconds after ANY EA's entry before entering (0 = off; The5ers pack: 90)
input int    InpReqWarn          = 500;    // Warn when ALL EAs together have sent this many server requests today (0 = off)
input int    InpReqBlock         = 1000;   // No NEW entries once today's account-wide requests reach this (closes always allowed; 0 = off)
input int    InpDupMax           = 5;      // Malfunction guard: this many entries by THIS EA within 10 minutes blocks it until the next server day (0 = off)

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
int GuardDay() { return InpDailyResetUTC ? DayKey(TimeGMT()) : DayKey(TimeTradeServer()); }
double DayStartBalance()
  {
   string n = "PP_DS_" + IntegerToString(GuardDay());
   if(!GlobalVariableCheck(n)) GlobalVariableSet(n, AccountInfoDouble(ACCOUNT_BALANCE));
   return GlobalVariableGet(n);
  }
double DayStartEquity()      // equity (open trades included) at the first check of the server day; used by the drawdown brake
  {
   string n = "PP_DE_" + IntegerToString(GuardDay());
   if(!GlobalVariableCheck(n)) GlobalVariableSet(n, AccountInfoDouble(ACCOUNT_EQUITY));
   return GlobalVariableGet(n);
  }
double DailyRef() { return InpDailyRefHigher ? MathMax(DayStartBalance(), DayStartEquity()) : DayStartBalance(); }   // reference for the daily loss
double PeakEquity()   // highest equity seen on this account (shared by all EAs in this terminal)
  {
   double eq = AccountInfoDouble(ACCOUNT_EQUITY), pk = GlobalVariableCheck("PP_PEAK") ? GlobalVariableGet("PP_PEAK") : InpAccountSize;
   if(eq > pk) { pk = eq; GlobalVariableSet("PP_PEAK", pk); }
   return pk;
  }
double LossFloor(double pct)   // equity level of a max-loss line: static from the start, or trailing the peak (locks at the start balance)
  {
   double f = InpAccountSize * (1 - pct / 100);
   if(InpTrailingMaxLoss) f = MathMax(f, MathMin(InpAccountSize, PeakEquity() - InpAccountSize * pct / 100));
   return f;
  }
bool GuardBlocks()
  {
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   string dayHalt = "PP_DH_" + IntegerToString(GuardDay());
   if(GlobalVariableCheck("PP_HALT")) { CloseMine("Guard (max loss)"); return true; }
   if(GlobalVariableCheck(dayHalt))   { CloseMine("Guard (daily)");    return true; }
   if(eq <= LossFloor(InpMaxStopPct))
     { GlobalVariableSet("PP_HALT", 1); CloseMine("Guard (max loss)"); return true; }
   if(DailyRef() - eq >= InpAccountSize * InpDailyStopPct / 100)
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
   double dayRoom = InpAccountSize * InpDailyStopPct / 100 - MathMax(0, DailyRef() - eq);
   double maxRoom = eq - LossFloor(InpMaxStopPct);
   r = MathMin(r, MathMin(dayRoom, maxRoom) * InpGuardShare / 100);
   if(InpRoomCapPct > 0)      // room cap: full size until the day starts 3% down (equity), then shrink linearly to 0 at the firm limit
     {
      double room = DayStartEquity() - LossFloor(InpFirmMaxLossPct);
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
   if(stopDist <= 0) return 0;
   // Loss per lot at the stop, in the ACCOUNT currency: MT5's own profit calculator converts JPY/EUR quotes correctly.
   // (Some brokers report the tick value of e.g. JPN225 in yen, which made the old tick-value method size ~150x too small.)
   double lossPerLot = 0, pf = 0;
   double exitPx = (type == ORDER_TYPE_BUY) ? price - stopDist : price + stopDist;
   if(OrderCalcProfit(type, _Symbol, 1.0, price, exitPx, pf) && pf < 0) lossPerLot = -pf;
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickVal  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
   if(tickVal <= 0) tickVal = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickLoss = (tickSize > 0 && tickVal > 0) ? stopDist / tickSize * tickVal : 0;
   static bool warned = false;
   if(!warned && lossPerLot > 0 && tickLoss > 0 && (tickLoss > 2 * lossPerLot || lossPerLot > 2 * tickLoss))
     { warned = true; Print("NOTE: broker tick value for ", _Symbol, " disagrees with the profit calculator (", DoubleToString(tickLoss, 2), " vs ", DoubleToString(lossPerLot, 2), " per lot at the stop); using the profit calculator"); }
   if(lossPerLot <= 0) lossPerLot = tickLoss;
   if(lossPerLot <= 0) return 0;
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP), vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN), vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lots = MathFloor(riskMoney / lossPerLot / step) * step;
   if(lots < vmin) return 0;              // stop too wide for the allowed risk: skip the trade
   lots = MathMin(lots, vmax);
   double margin;
   while(lots >= vmin && OrderCalcMargin(type, _Symbol, lots, price, margin) && margin > AccountInfoDouble(ACCOUNT_MARGIN_FREE) * 0.9)
      lots -= step;
   return lots >= vmin ? NormalizeDouble(lots, 8) : 0;
  }
bool SymbolSlotOK(int dir, string tag)   // firm rules on the symbol across ALL EAs: max open positions and no opposite directions
  {
   if(InpMaxOpenTotal > 0 && PositionsTotal() >= InpMaxOpenTotal) { Print(tag, ": ", PositionsTotal(), " positions open on the account (cap ", InpMaxOpenTotal, "), skipped"); return false; }
   if(InpNoWeekendEntries) { MqlDateTime w; TimeToStruct(TimeGMT(), w); if(w.day_of_week == 0 || w.day_of_week == 6) { Print(tag, ": weekend, no new trades"); return false; } }
   if(InpMaxPosPerSymbol <= 0 && !InpNoOpposite) return true;
   int n = 0; bool opposite = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(PositionGetTicket(i) == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      n++;
      long t = PositionGetInteger(POSITION_TYPE);
      if((dir == 1 && t == POSITION_TYPE_SELL) || (dir == -1 && t == POSITION_TYPE_BUY)) opposite = true;
     }
   if(InpNoOpposite && opposite) { Print(tag, ": opposite position open on ", _Symbol, " (no-hedging rule), skipped"); return false; }
   if(InpMaxPosPerSymbol > 0 && n >= InpMaxPosPerSymbol) { Print(tag, ": ", n, " positions already open on ", _Symbol, ", skipped"); return false; }
   return true;
  }
string HoldKey(ulong tk) { return "PP_HOLD_" + IntegerToString((long)tk); }
bool InHold(ulong tk) { return GlobalVariableCheck(HoldKey(tk) + "S"); }
// Minimum hold: while a position is younger than InpMinHoldSec only the wide emergency stop is on the server.
// After that the real stop/target go on, or the trade is closed if price is already past one of them.
void ManageHold()
  {
   if(InpMinHoldSec <= 0) return;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagic || !InHold(tk)) continue;
      if(TimeCurrent() - (datetime)PositionGetInteger(POSITION_TIME) < InpMinHoldSec) continue;
      double sl = GlobalVariableGet(HoldKey(tk) + "S"), tp = GlobalVariableGet(HoldKey(tk) + "T"), cur = PositionGetDouble(POSITION_SL);
      bool buy = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY;
      double px = buy ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      if(cur > 0 && (buy ? cur > sl : cur < sl)) sl = cur;                                  // keep a tighter (trailed) stop
      bool hit = (sl > 0 && (buy ? px <= sl : px >= sl)) || (tp > 0 && (buy ? px >= tp : px <= tp));
      bool ok = hit ? trade.PositionClose(tk) : trade.PositionModify(tk, NormalizeDouble(sl, _Digits), NormalizeDouble(tp, _Digits));
      if(ok) { GlobalVariableDel(HoldKey(tk) + "S"); GlobalVariableDel(HoldKey(tk) + "T"); Print(hit ? "Hold over: past SL/TP, closed" : "Hold over: SL/TP set"); }
     }
  }
// --- server-request budget (account-wide, per server day, kept in terminal global variables so it survives restarts) ---
string ReqKey()   { return "PP_REQ_" + IntegerToString(DayKey(TimeTradeServer())); }
string OpensKey() { return "PP_OPENS_" + IntegerToString(DayKey(TimeTradeServer())); }
void GVInc(string k)
  {
   if(!GlobalVariableCheck(k)) GlobalVariableSet(k, 0);
   for(int i = 0; i < 50; i++) { double v = GlobalVariableGet(k); if(GlobalVariableSetOnCondition(k, v + 1, v)) return; }
  }
int ReqCount() { string k = ReqKey(); return GlobalVariableCheck(k) ? (int)GlobalVariableGet(k) : 0; }
bool ReqBudgetOK(string tag)
  {
   if(InpReqBlock <= 0) return true;
   int c = ReqCount();
   if(c < InpReqBlock) return true;
   static datetime lastMsg = 0;
   if(TimeCurrent() - lastMsg >= 300) { lastMsg = TimeCurrent(); Print(tag, ": ", c, " server requests today (limit ", InpReqBlock, "), no new entries until the next server day"); }
   return false;
  }
bool DupOK(string tag)   // the same EA trying to enter again and again in a short time = probably a malfunction
  {
   if(InpDupMax <= 0) return true;
   string hk = "PP_DUPHALT_" + IntegerToString(InpMagic) + "_" + IntegerToString(DayKey(TimeTradeServer()));
   if(GlobalVariableCheck(hk)) { Print(tag, ": blocked until the next server day (too many entries in 10 minutes)"); return false; }
   static datetime t[32]; static int n = 0; datetime now = TimeCurrent(); int c = 0;
   for(int i = 0; i < 32; i++) if(t[i] > 0 && now - t[i] < 600) c++;
   if(c >= InpDupMax) { GlobalVariableSet(hk, 1); Print("WARNING ", tag, ": ", c, " entries in 10 minutes - possible malfunction, this EA is blocked until the next server day"); return false; }
   t[n % 32] = now; n++;
   return true;
  }
void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_REQUEST) return;      // one event per request this EA sent (open, close, modify, delete)
   GVInc(ReqKey()); int c = ReqCount();
   if(InpReqWarn > 0 && (c == InpReqWarn || c == InpReqWarn * 3 / 2)) Print("WARNING: ", c, " server requests today across all EAs (new entries stop at ", InpReqBlock, ")");
  }
// Stagger: if another EA opened a trade less than InpStaggerSec ago, wait and retry on later ticks of the same bar (max 15 min).
// The slot is claimed atomically (GlobalVariableSetOnCondition), so two EAs cannot enter in the same moment.
bool StaggerSlotOK(string tag)
  {
   if(InpStaggerSec <= 0 || MQLInfoInteger(MQL_TESTER)) return true;
   if(!GlobalVariableCheck("PP_LASTENTRY")) GlobalVariableSet("PP_LASTENTRY", 0);
   double last = GlobalVariableGet("PP_LASTENTRY"); double now = (double)TimeCurrent();
   if(now - last < InpStaggerSec || !GlobalVariableSetOnCondition("PP_LASTENTRY", now, last))
     { gSpreadRetry = true; static datetime lastMsg = 0; if(TimeCurrent() - lastMsg >= 30) { lastMsg = TimeCurrent(); Print(tag, ": another EA entered ", (int)(now - last), " s ago, waiting (stagger ", InpStaggerSec, " s)"); } return false; }
   return true;
  }
bool OpenTrade(int dir, double stopPrice, double tpPrice, string tag)
  {
   if(!SymbolSlotOK(dir, tag)) return false;
   if(!ReqBudgetOK(tag)) return false;
   if(!StaggerSlotOK(tag)) return false;
   if(NewsBlocked()) { Print(tag, ": high-impact news within ", InpNewsBlockMin, " min, skipped"); return false; }
   double price = dir == 1 ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double dist = MathAbs(price - stopPrice);
   if(dir * (price - stopPrice) <= 0) { Print(tag, ": price already beyond the stop, skipped"); return false; }
   if(SpreadTooWide(dist, tag)) return false;
   double lots = LotsFor(RiskMoney(), dist, dir == 1 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL, price);
   if(lots <= 0) { Print(tag, ": size below minimum for the allowed risk, skipped"); return false; }
   double sl = NormalizeDouble(stopPrice, _Digits), tp = tpPrice > 0 ? NormalizeDouble(tpPrice, _Digits) : 0;
   double ssl = sl, stp = tp;
   if(InpMinHoldSec > 0) { ssl = NormalizeDouble(price - dir * InpHoldStopMult * dist, _Digits); stp = 0; }   // real SL/TP applied after the hold
   if(!DupOK(tag)) return false;
   bool ok = dir == 1 ? trade.Buy(lots, _Symbol, 0, ssl, stp, tag) : trade.Sell(lots, _Symbol, 0, ssl, stp, tag);
   if(ok && InpStaggerSec > 0) GlobalVariableSet("PP_LASTENTRY", (double)TimeCurrent());
   if(ok) GVInc(OpensKey());
   Print(tag, ok ? " opened " : " FAILED ", lots, " lots, SL ", sl, " TP ", tp, " retcode ", trade.ResultRetcode());
   if(ok && InpMinHoldSec > 0) { ulong pt = trade.ResultOrder(); GlobalVariableSet(HoldKey(pt) + "S", sl); GlobalVariableSet(HoldKey(pt) + "T", tp); }
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
   ManageHold();
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
