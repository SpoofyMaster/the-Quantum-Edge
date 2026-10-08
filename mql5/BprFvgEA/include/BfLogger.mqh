//+------------------------------------------------------------------+
//| BfLogger.mqh                                                     |
//| BprFvgEA: Experts-log lines and CSV logs (spec s.7)              |
//+------------------------------------------------------------------+
//
// Part of BprFvgEA (distributed as a whole under CC BY-NC-SA 4.0 because it includes a port of LuxAlgo code; see
// BfEngine.mqh). This file contains no LuxAlgo logic. Adapted from mql5/VideoStrategyEA/include/DebugLogger.mqh.
//
// Files (Common Files folder, FILE_COMMON; symbol and timeframe in the name):
//   BFEA_setups_<sym>_<tf>.csv  one row per setup when it ends (DONE / CLOSED), plus the still-open ones at exit
//   BFEA_trades_<sym>_<tf>.csv  one row per closed trade
// In the Strategy Tester the files are rewritten at the start of each run; on a chart they are appended to.
// In optimisation runs no file is written (agents would write into the same file).
//+------------------------------------------------------------------+
#ifndef BF_LOGGER_MQH
#define BF_LOGGER_MQH

#include "BfDefines.mqh"

#define BF_SETUPS_HEADER "id,source,dir,created_time,B,T,h,sweep_bar_time,M,mss_time,status,reason,P,SL,TP1,TP2,decision_time"
#define BF_TRADES_HEADER "id,dir,entry_time,entry,lots,SL,TP1,TP2,exit_time,exit,exit_reason,pnl_usd,R,planned_risk_usd"

class CBfLogger
  {
private:
   bool              m_csv;
   bool              m_fresh;
   bool              m_quiet;
   string            m_fSetups;
   string            m_fTrades;
   int               m_hS;
   int               m_hT;
   int               m_rows;

   int               OpenCsv(const string name, const string header)
     {
      int flags;
      int fh;
      if(m_fresh)
         flags = FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_SHARE_READ | FILE_COMMON;
      else
         flags = FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_SHARE_READ | FILE_COMMON;
      fh = FileOpen(name, flags);
      if(fh == INVALID_HANDLE)
        {
         Print("[BFEA ERROR] cannot open ", name, " error ", GetLastError());
         return(INVALID_HANDLE);
        }
      if(FileSize(fh) == 0)
         FileWriteString(fh, header + "\r\n");
      FileSeek(fh, 0, SEEK_END);
      return(fh);
     }

public:
                     CBfLogger(void)
     {
      m_csv     = false;
      m_fresh   = false;
      m_quiet   = false;
      m_fSetups = "";
      m_fTrades = "";
      m_hS      = INVALID_HANDLE;
      m_hT      = INVALID_HANDLE;
      m_rows    = 0;
     }

   //--- csv: write the files; fresh: truncate them now (tester); quiet: no Experts-log lines (optimisation)
   void              Init(const bool csv, const bool fresh, const bool quiet, const string sym, const string tf)
     {
      string s = sym;
      StringReplace(s, "/", "_");
      StringReplace(s, "\\", "_");
      StringReplace(s, ":", "_");
      StringReplace(s, "*", "_");
      StringReplace(s, "?", "_");
      StringReplace(s, "\"", "_");
      StringReplace(s, "<", "_");
      StringReplace(s, ">", "_");
      StringReplace(s, "|", "_");
      m_csv     = csv;
      m_fresh   = fresh;
      m_quiet   = quiet;
      m_fSetups = "BFEA_setups_" + s + "_" + tf + ".csv";
      m_fTrades = "BFEA_trades_" + s + "_" + tf + ".csv";
      m_rows    = 0;
      if(m_csv)
        {
         m_hS = OpenCsv(m_fSetups, BF_SETUPS_HEADER);
         m_hT = OpenCsv(m_fTrades, BF_TRADES_HEADER);
        }
     }

   string            SetupsFile(void)
     {
      return(m_fSetups);
     }

   string            TradesFile(void)
     {
      return(m_fTrades);
     }

   static string     Ts(const datetime t)
     {
      if(t <= 0)
         return("");
      return(TimeToString(t, TIME_DATE | TIME_MINUTES));
     }

   void              Info(const string msg)
     {
      if(!m_quiet)
         Print("[BFEA] ", msg);
     }

   void              Error(const string msg)
     {
      Print("[BFEA ERROR] ", msg);
     }

   void              SetupRow(const string line)
     {
      if(!m_csv || m_hS == INVALID_HANDLE)
         return;
      FileWriteString(m_hS, line + "\r\n");
      m_rows++;
      if(m_rows % 200 == 0)
         FileFlush(m_hS);
     }

   void              TradeRow(const string line)
     {
      if(!m_csv || m_hT == INVALID_HANDLE)
         return;
      FileWriteString(m_hT, line + "\r\n");
      FileFlush(m_hT);
      if(m_hS != INVALID_HANDLE)
         FileFlush(m_hS);
     }

   void              Close(void)
     {
      if(m_hS != INVALID_HANDLE)
        {
         FileClose(m_hS);
         m_hS = INVALID_HANDLE;
        }
      if(m_hT != INVALID_HANDLE)
        {
         FileClose(m_hT);
         m_hT = INVALID_HANDLE;
        }
     }
  };

#endif
//+------------------------------------------------------------------+
