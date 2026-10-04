//+------------------------------------------------------------------+
//| SessionManager.mqh — server time -> UTC, DST, trading hours      |
//| MKT-5/6/7. The DST helpers are the ones already verified against |
//| zoneinfo in qe/mql5_parity.py (QuantumEdgeImpulseReversion.mq5). |
//+------------------------------------------------------------------+
#ifndef VSEA_SESSION_MQH
#define VSEA_SESSION_MQH

#include "Defines.mqh"

class CSessionManager
  {
private:
   int               m_serverMode;
   int               m_fixedOffsetH;

public:
                     CSessionManager(void) : m_serverMode(VS_SERVER_NY_PLUS_7), m_fixedOffsetH(0) {}
   void              Init(const int serverMode, const int fixedOffsetH) { m_serverMode = serverMode; m_fixedOffsetH = fixedOffsetH; }

   static datetime   MakeDate(const int y, const int m, const int d, const int hh = 0, const int mm = 0)
     {
      MqlDateTime t;
      ZeroMemory(t);
      t.year = y; t.mon = m; t.day = d; t.hour = hh; t.min = mm; t.sec = 0;
      return StructToTime(t);
     }
   static int        DayOfWeek(const datetime t) { MqlDateTime s; TimeToStruct(t, s); return s.day_of_week; } // 0 = Sunday
   static int        YearOf(const datetime t)    { MqlDateTime s; TimeToStruct(t, s); return s.year; }
   static int        MinuteOfDay(const datetime t) { MqlDateTime s; TimeToStruct(t, s); return s.hour * 60 + s.min; }

   static datetime   NthSunday(const int y, const int m, const int n)
     {
      datetime first = MakeDate(y, m, 1);
      int add = (7 - DayOfWeek(first)) % 7;
      return first + (datetime)((add + 7 * (n - 1)) * 86400);
     }
   static datetime   LastSunday(const int y, const int m)
     {
      int ny = (m == 12) ? y + 1 : y;
      int nm = (m == 12) ? 1 : m + 1;
      datetime last = MakeDate(ny, nm, 1) - 86400;
      return last - (datetime)(DayOfWeek(last) * 86400);
     }
   // US DST: 2nd Sunday of March 07:00 UTC .. 1st Sunday of November 06:00 UTC
   static bool       IsUSDST_UTC(const datetime utc)
     {
      int y = YearOf(utc);
      return utc >= NthSunday(y, 3, 2) + 7 * 3600 && utc < NthSunday(y, 11, 1) + 6 * 3600;
     }
   // UK/EU DST: last Sunday of March 01:00 UTC .. last Sunday of October 01:00 UTC
   static bool       IsUKDST_UTC(const datetime utc)
     {
      int y = YearOf(utc);
      return utc >= LastSunday(y, 3) + 3600 && utc < LastSunday(y, 10) + 3600;
     }

   datetime          ServerToUTC(const datetime server) const
     {
      if(m_serverMode == VS_SERVER_NY_PLUS_7)
        {
         datetime ny = server - 7 * 3600;
         datetime cand = ny + 5 * 3600;                 // assume EST
         return IsUSDST_UTC(cand - 3600) ? ny + 4 * 3600 : cand;
        }
      if(m_serverMode == VS_SERVER_EU_DST)
        {
         datetime cand = server - 2 * 3600;             // assume UTC+2
         return IsUKDST_UTC(cand - 3600) ? server - 3 * 3600 : cand;
        }
      return server - m_fixedOffsetH * 3600;
     }
   static datetime   UTCToNY(const datetime utc) { return utc - (IsUSDST_UTC(utc) ? 4 : 5) * 3600; }

   //--- FX day (17:00 New York) of a server time, as a day number
   long              FxDay(const datetime server) const
     {
      datetime ny = UTCToNY(ServerToUTC(server));
      return (long)((ny + 7 * 3600) / 86400);
     }

   //--- rollover blackout 16:45-17:30 New York (MGT-3)
   bool              InRolloverBlackout(const datetime server) const
     {
      int m = MinuteOfDay(UTCToNY(ServerToUTC(server)));
      return m >= 16 * 60 + 45 && m < 17 * 60 + 30;
     }

   //--- spec section 1: may a candle opening at this server time be traded?
   bool              IsTradingCandle(const datetime serverCandleOpen, const int preset) const
     {
      datetime utc = ServerToUTC(serverCandleOpen);
      if(preset == VS_SES_ALL)
         return !InRolloverBlackout(serverCandleOpen);
      MqlDateTime d;
      TimeToStruct(utc, d);
      if(d.day_of_week == 0 || d.day_of_week == 6)
         return false;
      datetime start = MakeDate(d.year, d.mon, d.day, 1, 0);                          // 10:00 Tokyo (UTC+9, no DST)
      datetime ldn8  = MakeDate(d.year, d.mon, d.day, 8, 0);
      datetime ldn11 = MakeDate(d.year, d.mon, d.day, 11, 0);
      if(IsUKDST_UTC(MakeDate(d.year, d.mon, d.day, 6, 0)))
        {
         ldn8  -= 3600;                                                                 // BST
         ldn11 -= 3600;
        }
      if(preset == VS_SES_STRICT)
         return utc == start || utc == ldn8;
      return utc >= start && utc <= ldn11;
     }

   //--- label for reports
   string            SessionLabel(const datetime serverTime) const
     {
      datetime utc = ServerToUTC(serverTime);
      int m = MinuteOfDay(utc);
      MqlDateTime d;
      TimeToStruct(utc, d);
      datetime ldn8 = MakeDate(d.year, d.mon, d.day, 8, 0);
      if(IsUKDST_UTC(MakeDate(d.year, d.mon, d.day, 6, 0)))
         ldn8 -= 3600;
      if(utc >= ldn8 && m < 16 * 60)
         return "LONDON";
      if(m < 9 * 60)
         return "ASIA";
      return "OTHER";
     }
  };

#endif
