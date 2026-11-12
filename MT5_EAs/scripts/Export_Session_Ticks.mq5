//+------------------------------------------------------------------+
//| Export_Session_Ticks – MT5 SCRIPT (not an EA). Saves only the ticks inside a daily time window, with just
//| time (ms), bid and ask, so the file stays small. Default: 16:25-19:00 server time = 09:25-12:00 New York
//| on RoboForex / FTMO-style servers (GMT+2 winter, +3 summer).
//| Use: MetaEditor -> File -> New -> Script, paste this, Compile. In MT5 drag it from Navigator -> Scripts onto
//| any chart, set the inputs, OK. The file is written to MQL5\Files (File -> Open Data Folder -> MQL5 -> Files).
//+------------------------------------------------------------------+
#property script_show_inputs
#property version "1.00"
input string   InpSymbol   = ".USTECHCash";        // Symbol
input datetime InpFrom     = D'2026.10.20 00:00';  // First day (server time)
input datetime InpTo       = D'2026.11.12 00:00';  // Last day (server time, not included)
input int      InpStartMin = 16 * 60 + 25;         // Window start, minutes after midnight server time (16:25)
input int      InpEndMin   = 19 * 60;              // Window end (19:00)
void OnStart()
  {
   string fn = InpSymbol + "_session_ticks.csv";
   int f = FileOpen(fn, FILE_WRITE | FILE_ANSI | FILE_TXT);
   if(f == INVALID_HANDLE) { Print("Cannot open ", fn, " error ", GetLastError()); return; }
   FileWriteString(f, "time_msc,bid,ask\n");
   long total = 0;
   for(datetime d = InpFrom; d < InpTo; d += 86400)
     {
      MqlDateTime s; TimeToStruct(d, s);
      if(s.day_of_week == 0 || s.day_of_week == 6) continue;
      ulong a = (ulong)(d + InpStartMin * 60) * 1000, b = (ulong)(d + InpEndMin * 60) * 1000;
      MqlTick t[];
      int n = CopyTicksRange(InpSymbol, t, COPY_TICKS_INFO, a, b);
      if(n <= 0) { Print(TimeToString(d, TIME_DATE), ": no ticks (", GetLastError(), ")"); continue; }
      int digits = (int)SymbolInfoInteger(InpSymbol, SYMBOL_DIGITS);
      string buf = "";
      for(int i = 0; i < n; i++)
        {
         buf += IntegerToString(t[i].time_msc) + "," + DoubleToString(t[i].bid, digits) + "," + DoubleToString(t[i].ask, digits) + "\n";
         if(StringLen(buf) > 1000000) { FileWriteString(f, buf); buf = ""; }
        }
      FileWriteString(f, buf); total += n;
      Print(TimeToString(d, TIME_DATE), ": ", n, " ticks");
     }
   FileClose(f);
   Print("Done: ", total, " ticks written to MQL5\\Files\\", fn);
  }
