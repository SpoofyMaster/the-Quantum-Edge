//+------------------------------------------------------------------+
//| BfSession.mqh                                                    |
//| BprFvgEA: server time -> UTC / New York / London (DST-correct),  |
//| entry window, FX day and the pre-rollover flat time.             |
//+------------------------------------------------------------------+
//
// Part of BprFvgEA (distributed as a whole under CC BY-NC-SA 4.0 because it includes a port of LuxAlgo code; see
// BfEngine.mqh). This file contains no LuxAlgo logic. Adapted from mql5/VideoStrategyEA/include/SessionManager.mqh;
// the DST rules are the ones checked against zoneinfo in qe/mql5_parity.py.
//
// "spec s.N" = research/indicators/BPR_FVG_EA_SPEC.md section N.
//+------------------------------------------------------------------+
#ifndef BF_SESSION_MQH
#define BF_SESSION_MQH

#include "BfDefines.mqh"

#define BF_LDN_OPEN_MIN    480     // 08:00 Europe/London: first entry (spec s.1 InpUseSession)
#define BF_NY_LAST_MIN     885     // 14:45 America/New_York: last entry time (spec s.1, s.4 step 3d)
#define BF_NY_FLAT_MIN     1004    // 16:44 America/New_York: be flat before the rollover (spec s.5)
#define BF_NY_ROLL_MIN     1020    // 17:00 America/New_York: rollover / FX-day start

class CBfSession
  {
private:
   int               m_mode;
   int               m_offH;

public:
                     CBfSession(void)
     {
      m_mode = BF_SERVER_NY_PLUS_7;
      m_offH = 0;
     }

   void              Init(const int mode, const int offH)
     {
      m_mode = mode;
      m_offH = offH;
     }

   static datetime   MakeDate(const int y, const int m, const int d, const int hh, const int mm)
     {
      MqlDateTime t;
      ZeroMemory(t);
      t.year = y;
      t.mon  = m;
      t.day  = d;
      t.hour = hh;
      t.min  = mm;
      t.sec  = 0;
      return(StructToTime(t));
     }

   static int        DowOf(const datetime t)          // 0 = Sunday
     {
      MqlDateTime s;
      TimeToStruct(t, s);
      return(s.day_of_week);
     }

   static int        YearOf(const datetime t)
     {
      MqlDateTime s;
      TimeToStruct(t, s);
      return(s.year);
     }

   static int        MinuteOfDay(const datetime t)
     {
      MqlDateTime s;
      TimeToStruct(t, s);
      return(s.hour * 60 + s.min);
     }

   static datetime   NthSunday(const int y, const int m, const int n)
     {
      datetime first = MakeDate(y, m, 1, 0, 0);
      int      add   = (7 - DowOf(first)) % 7;
      return((datetime)((long)first + (long)(add + 7 * (n - 1)) * 86400));
     }

   static datetime   LastSunday(const int y, const int m)
     {
      int      ny   = (m == 12) ? y + 1 : y;
      int      nm   = (m == 12) ? 1 : m + 1;
      datetime last = (datetime)((long)MakeDate(ny, nm, 1, 0, 0) - 86400);
      return((datetime)((long)last - (long)DowOf(last) * 86400));
     }

   // US DST: 2nd Sunday of March 07:00 UTC .. 1st Sunday of November 06:00 UTC
   static bool       IsUSDST_UTC(const datetime utc)
     {
      int y = YearOf(utc);
      return((long)utc >= (long)NthSunday(y, 3, 2) + 7 * 3600 && (long)utc < (long)NthSunday(y, 11, 1) + 6 * 3600);
     }

   // UK/EU DST: last Sunday of March 01:00 UTC .. last Sunday of October 01:00 UTC
   static bool       IsUKDST_UTC(const datetime utc)
     {
      int y = YearOf(utc);
      return((long)utc >= (long)LastSunday(y, 3) + 3600 && (long)utc < (long)LastSunday(y, 10) + 3600);
     }

   datetime          ServerToUTC(const datetime server)
     {
      if(m_mode == BF_SERVER_NY_PLUS_7)
        {
         long ny   = (long)server - 7 * 3600;
         long cand = ny + 5 * 3600;                            // assume EST
         if(IsUSDST_UTC((datetime)(cand - 3600)))
            return((datetime)(ny + 4 * 3600));
         return((datetime)cand);
        }
      if(m_mode == BF_SERVER_EU_DST)
        {
         long cand2 = (long)server - 2 * 3600;                 // assume UTC+2
         if(IsUKDST_UTC((datetime)(cand2 - 3600)))
            return((datetime)((long)server - 3 * 3600));
         return((datetime)cand2);
        }
      return((datetime)((long)server - (long)m_offH * 3600));
     }

   static datetime   UTCToNY(const datetime utc)
     {
      return((datetime)((long)utc - (IsUSDST_UTC(utc) ? 4 : 5) * 3600));
     }

   static datetime   UTCToLondon(const datetime utc)
     {
      return((datetime)((long)utc + (IsUKDST_UTC(utc) ? 3600 : 0)));
     }

   datetime          ServerToNY(const datetime server)
     {
      return(UTCToNY(ServerToUTC(server)));
     }

   //--- FX day (starts 17:00 New York) of a server time, as a day number
   long              FxDay(const datetime server)
     {
      datetime ny = ServerToNY(server);
      return(((long)ny + 7 * 3600) / 86400);
     }

   //--- spec s.1 InpUseSession: entries from 08:00 Europe/London to 14:45 America/New_York, Monday-Friday.
   //    'server' is the open time of the bar on which the order would be placed (the next bar's open).
   bool              EntryOk(const datetime server)
     {
      datetime utc = ServerToUTC(server);
      datetime ny  = UTCToNY(utc);
      datetime ldn = UTCToLondon(utc);
      int      dow = DowOf(ny);
      if(dow == 0 || dow == 6)
         return(false);
      return(MinuteOfDay(ldn) >= BF_LDN_OPEN_MIN && MinuteOfDay(ny) < BF_NY_LAST_MIN);
     }

   //--- spec s.4 step 3d: "the next bar's open is at or after the last entry time". Pending orders exist only
   //    inside the entry window, so leaving the window (14:45 New York, or a data gap that jumps past it) is
   //    "at or after the last entry time".
   bool              SessionCancel(const datetime server)
     {
      return(!EntryOk(server));
     }

   //--- spec s.5 "Before the rollover": close at 16:44 New York. True when the most recent 16:44 NY cut-off lies
   //    after the fill, or when now is inside [16:44, 17:00) NY (covers fills inside that window).
   bool              FlatDue(const datetime fillServer, const datetime nowServer)
     {
      long nyNow  = (long)ServerToNY(nowServer);
      long nyFill = (long)ServerToNY(fillServer);
      long cut    = (nyNow / 86400) * 86400 + (long)BF_NY_FLAT_MIN * 60;
      int  mNow   = MinuteOfDay((datetime)nyNow);
      if(mNow >= BF_NY_FLAT_MIN && mNow < BF_NY_ROLL_MIN)
         return(true);
      if(nyNow < cut)
         cut -= 86400;
      return(nyFill < cut);
     }

   //--- New York time as text (logs / panel)
   string            NyText(const datetime server)
     {
      return(TimeToString(ServerToNY(server), TIME_DATE | TIME_MINUTES));
     }
  };

#endif
//+------------------------------------------------------------------+
