//+------------------------------------------------------------------+
//| BfLogger.mqh                                                     |
//| BprFvgEA: Experts-log lines and CSV logs (spec s.7)              |
//+------------------------------------------------------------------+
//
// Part of BprFvgEA (distributed as a whole under CC BY-NC-SA 4.0 because it includes a port of LuxAlgo code; see
// BfEngine.mqh). This file contains no LuxAlgo logic. Adapted from mql5/VideoStrategyEA/include/DebugLogger.mqh.
//
// Files (Common Files folder, FILE_COMMON; symbol, timeframe, magic number and run mode in the name):
//   BFEA_setups_<sym>_<tf>_<magic>_<TESTER|LIVE>.csv  one row per setup when it ends (DONE / CLOSED), plus the
//                                                     still-open ones at exit
//   BFEA_trades_<sym>_<tf>_<magic>_<TESTER|LIVE>.csv  one row per closed trade
// TESTER files are rewritten at the start of each tester run; LIVE files (a chart, demo or log-only) are appended to
// and never touched by the tester. The first column 'run' is the server time of OnInit, so (run, id) is unique even
// though setup ids restart at 1 on every start. LIVE rows are flushed at once (nothing is lost on a crash).
// Files are opened with FILE_SHARE_READ (readable while the EA runs) but not FILE_SHARE_WRITE: a second writer
// (another terminal or instance with the same name) gets a loud open error instead of overwriting rows.
// In optimisation runs no file is written (agents would write into the same file).
//+------------------------------------------------------------------+
#ifndef BF_LOGGER_MQH
#define BF_LOGGER_MQH

#include "BfDefines.mqh"

#define BF_SETUPS_HEADER "run,id,source,dir,created_time,B,T,h,sweep_bar_time,M,mss_time,status,reason,P,SL,TP1,TP2,decision_time"
#define BF_TRADES_HEADER "run,id,dir,entry_time,entry,lots,SL,TP1,TP2,exit_time,exit,exit_reason,pnl_usd,R,planned_risk_usd"

class CBfLogger
  {
private:
   bool              m_csv;
   bool              m_fresh;
   bool              m_quiet;
   string            m_fSetups;
   string            m_fTrades;
   string            m_run;
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
      m_run     = "";
      m_hS      = INVALID_HANDLE;
      m_hT      = INVALID_HANDLE;
      m_rows    = 0;
     }

   //--- csv: write the files; tester: TESTER files, truncated now (otherwise LIVE files, appended to);
   //    quiet: no Experts-log lines (optimisation); run: the 'run' column (server time of OnInit)
   void              Init(const bool csv, const bool tester, const bool quiet, const string sym, const string tf,
                          const long magic, const string run)
     {
      string mode = tester ? "TESTER" : "LIVE";
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
      m_fresh   = tester;
      m_quiet   = quiet;
      m_run     = run;
      m_fSetups = "BFEA_setups_" + s + "_" + tf + "_" + IntegerToString(magic) + "_" + mode + ".csv";
      m_fTrades = "BFEA_trades_" + s + "_" + tf + "_" + IntegerToString(magic) + "_" + mode + ".csv";
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

   //--- a new run stamp (the warm-up was repeated, so setup ids restart at 1)
   void              SetRun(const string run)
     {
      m_run = run;
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
      FileWriteString(m_hS, m_run + "," + line + "\r\n");
      m_rows++;
      if(!m_fresh || m_rows % 200 == 0)
         FileFlush(m_hS);                                   // LIVE: every row; TESTER: every 200 rows
     }

   void              TradeRow(const string line)
     {
      if(!m_csv || m_hT == INVALID_HANDLE)
         return;
      FileWriteString(m_hT, m_run + "," + line + "\r\n");
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
