//+------------------------------------------------------------------+
//| DebugLogger.mqh — setup-tagged journal lines and CSV logs         |
//| Files (MQL5/Files, or Common/Files in the tester):                |
//|   VSEA_events_<symbol>_<magic>.csv   every setup / reason        |
//|   VSEA_trades_<symbol>_<magic>.csv   one row per closed trade    |
//| The reason codes are the same as qe/video_strategy/engine.py so   |
//| EA logs can be compared with the Python reference.                |
//+------------------------------------------------------------------+
#ifndef VSEA_LOGGER_MQH
#define VSEA_LOGGER_MQH

#include "Defines.mqh"

class CLogger
  {
private:
   int               m_level;
   bool              m_csv;
   string            m_events;
   string            m_trades;

   void              Append(const string file, const string header, const string line)
     {
      if(!m_csv) return;
      int flags = FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_SHARE_READ | FILE_COMMON;
      int h = FileOpen(file, flags, ';');
      if(h == INVALID_HANDLE) return;
      if(FileSize(h) == 0) FileWriteString(h, header + "\r\n");
      FileSeek(h, 0, SEEK_END);
      FileWriteString(h, line + "\r\n");
      FileClose(h);
     }

public:
                     CLogger(void) : m_level(VS_LOG_SETUPS), m_csv(true) {}

   void              Init(const int level, const bool csv, const string symbol, const long magic)
     {
      m_level = level;
      m_csv = csv;
      m_events = "VSEA_events_" + symbol + "_" + IntegerToString(magic) + ".csv";
      m_trades = "VSEA_trades_" + symbol + "_" + IntegerToString(magic) + ".csv";
     }

   static string     Ts(const datetime t) { return TimeToString(t, TIME_DATE | TIME_MINUTES); }

   void              Error(const string msg) { Print("[VSEA ERROR] ", msg); }

   void              Setup(const int setupId, const int tf, const datetime when, const string msg)
     {
      if(m_level >= VS_LOG_SETUPS)
         PrintFormat("[SETUP #%d M%d] %s %s", setupId, tf, Ts(when), msg);
     }

   void              Verbose(const int setupId, const int tf, const datetime when, const string msg)
     {
      if(m_level >= VS_LOG_VERBOSE)
         PrintFormat("[SETUP #%d M%d] %s %s", setupId, tf, Ts(when), msg);
     }

   //--- one row per finished setup (also rejections)
   void              Event(const int setupId, const int tf, const datetime candleOpen, const string condition,
                           const double ratio, const string reason, const int dir, const datetime signalTime,
                           const double extE, const double extO, const double protPrice, const string gate)
     {
      string line = StringFormat("%d;%d;%s;%s;%.4f;%s;%d;%s;%.5f;%.5f;%.5f;%s",
                                 setupId, tf, Ts(candleOpen), condition, ratio, reason, dir,
                                 (signalTime > 0 ? Ts(signalTime) : ""), extE, extO, protPrice, gate);
      Append(m_events, "setup_id;tf;candle_open_server;condition;ratio_median;reason;direction;signal_time_server;"
             "ext_E;ext_O;protected;gate", line);
     }

   void              Trade(const string line)
     {
      Append(m_trades, "setup_id;tf;direction;signal_time;entry_time;exit_time;entry;sl;tp;exit;lots;profit;"
             "commission;swap;planned_risk;R;exit_reason;session;planned_rr", line);
     }
  };

#endif
