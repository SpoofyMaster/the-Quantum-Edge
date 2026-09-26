//+------------------------------------------------------------------+
//| ExportM1WithSpread.mq5 — DATA EXPORT SCRIPT (no trading).        |
//| Writes M1 bars incl. MT5 'spread' (points) for the chart symbol   |
//| to MQL5/Files/<SYMBOL>_M1_<from>_<to>.csv for broker-spread       |
//| research. NOT YET COMPILED in MetaEditor — verify before use.     |
//+------------------------------------------------------------------+
#property script_show_inputs
input datetime InpFrom = D'2020.01.01 00:00';
input datetime InpTo   = D'2026.09.26 00:00';

void OnStart()
{
   MqlRates rates[];
   ArraySetAsSeries(rates, false);
   int n = CopyRates(_Symbol, PERIOD_M1, InpFrom, InpTo, rates);
   if(n <= 0) { PrintFormat("CopyRates failed: %d", GetLastError()); return; }
   string name = StringFormat("%s_M1_%s_%s.csv", _Symbol,
                              TimeToString(InpFrom, TIME_DATE), TimeToString(InpTo, TIME_DATE));
   StringReplace(name, ".", "-"); StringReplace(name, "-csv", ".csv");
   int h = FileOpen(name, FILE_WRITE | FILE_CSV | FILE_ANSI, ',');
   if(h == INVALID_HANDLE) { PrintFormat("FileOpen failed: %d", GetLastError()); return; }
   FileWrite(h, "time_server", "open", "high", "low", "close", "tick_volume", "spread_points", "digits");
   for(int i = 0; i < n; i++)
      FileWrite(h, TimeToString(rates[i].time, TIME_DATE | TIME_MINUTES), rates[i].open, rates[i].high,
                rates[i].low, rates[i].close, rates[i].tick_volume, rates[i].spread, _Digits);
   FileClose(h);
   PrintFormat("Exported %d M1 bars to %s (server time; record the server UTC offset!)", n, name);
}
