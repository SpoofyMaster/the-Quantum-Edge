//+------------------------------------------------------------------------------------------------+
//| QuantumEdgeImpulseReversion.mq5                                 PROJECT QUANTUM EDGE (research) |
//|                                                                                                 |
//| MQL5 port of pine/quantum_edge_impulse_reversion.pine (same signal, exits and risk engine),     |
//| implementing docs/deliverables/mql5_spec.md. Human approval for MQL5 implementation was given    |
//| by the project owner on 2026-09-26 for Strategy Tester / demo testing.                          |
//|                                                                                                 |
//| STATUS: NOT YET COMPILED (written without MetaEditor). Compile in MetaEditor, report errors.     |
//|                                                                                                 |
//| RESEARCH RESULT TO KEEP IN MIND: the underlying idea did NOT validate (FINAL_REPORT.md):         |
//|   dev 2020-2023 best net EV +0.021R (CI incl. 0); validation 2024-2025H1 -0.055R.                |
//| SAFETY: trades only in the Strategy Tester or on DEMO accounts. On a REAL account the EA runs    |
//| in log-only mode (no orders) - there is deliberately no input to override this.                  |
//|                                                                                                 |
//| Signal (bar-close decisions, M1 bid bars, fills at the next bar's open):                        |
//|   seasonal sigma : NY-local 5-min time-of-week buckets (2016), per-week mean |log r|,            |
//|                    median of previous <=20 weeks (>=4 required) x sqrt(pi/2); causal             |
//|   impulse        : ln(C_t / C_t-5) / sqrt(sum_{i=0..4} e_{t-i}^2)                                |
//|   event          : first bar with |impulse| > k                                                  |
//|     Active fade  : London 08:00-16:30 (Europe/London) or NY 08:00-17:00 (America/New_York)       |
//|     Quiet revert : neither session and not in the rollover blackout                             |
//|   direction      : -sign(impulse)                                                                |
//| Exits  : stop = StopMult x max(seasonal, realised sigma60) x sqrt(H) x price; target optional;   |
//|          time exit after H minutes (<=120); forced exit in the 16:45-17:30 NY rollover blackout  |
//| Risk   : 0.20% equity per trade incl. commission; 1.00% daily loss lockout (FX day 17:00 NY);    |
//|          portfolio ledger across instances (max positions, max open risk, correlation guard);    |
//|          execution-health breaker (order errors, spread spikes, disconnects). No martingale,     |
//|          grids, averaging or size-up after losses.                                              |
//+------------------------------------------------------------------------------------------------+
#property copyright "Project Quantum Edge (research)"
#property version   "1.00"
#property description "Research EA: de-seasonalised impulse reversion (parity with the Pine prototype)."
#property description "Tester/demo only. Real accounts run in log-only mode."

#include <Trade/Trade.mqh>

//------------------------------------------------------------------------------------------------
// Inputs
//------------------------------------------------------------------------------------------------
enum ENUM_QE_MODE
  {
   QE_ACTIVE_FADE  = 0,   // Active fade (H-11)
   QE_QUIET_REVERT = 1    // Quiet revert (H-02)
  };

enum ENUM_QE_SERVER_TIME
  {
   QE_SERVER_NY_PLUS_7 = 0,   // Server = New York + 7h (IC Markets, most NY-close brokers)
   QE_SERVER_EU_DST    = 1,   // Server = UTC+2 winter / UTC+3 summer, EU DST dates
   QE_SERVER_FIXED     = 2    // Server = UTC + fixed offset (no DST)
  };

input group "Signal (defaults = pre-registered EXP007 candidate)"
input ENUM_QE_MODE InpMode        = QE_ACTIVE_FADE; // Mode
input double       InpK           = 5.0;            // Impulse threshold k (de-seasonalised sigma)
input int          InpHoldMin     = 30;             // Holding horizon H (minutes, 5..120)
input double       InpStopMult    = 1.0;            // Stop multiple of expected move
input double       InpTargetMult  = 1.5;            // Target multiple (0 = time exit only)
input int          InpSeasonWeeks = 20;             // Seasonal window (weeks)
input int          InpSeasonMinWeeks = 4;           // Minimum weeks before trading

input group "Risk (never raise above research limits)"
input double InpRiskPct        = 0.20;   // Risk per trade % of equity (incl. commission), max 0.20
input double InpDayLossPct     = 1.00;   // Max planned daily loss % (FX day = 17:00 NY), max 1.00
input double InpMaxOpenRiskPct = 0.60;   // Max open planned risk across QE instances %
input int    InpMaxPositions   = 3;      // Max simultaneous QE positions (all symbols)
input double InpCommLotSide    = 3.50;   // Commission per lot per side, account ccy (UNVERIFIED)
input double InpCorrThreshold  = 0.60;   // Reject same-exposure trades with rho*dir*dir >= this
input string InpCorrTable      = "EURUSD/GBPUSD=0.80;XAUUSD/XAGUSD=0.80;EURUSD/USDJPY=-0.30;GBPUSD/USDJPY=-0.25;EURUSD/XAUUSD=0.30";

input group "Execution health"
input int    InpDeviationPts   = 30;     // Max deviation (points)
input int    InpMaxOrderErrors = 3;      // Consecutive order errors -> suspend for the FX day
input double InpSpreadSpikeMult = 3.0;   // Skip signal if spread > mult x median for this hour-of-week
input int    InpDisconnectSec  = 60;     // Disconnect watchdog threshold (seconds)

input group "Time"
input ENUM_QE_SERVER_TIME InpServerTime = QE_SERVER_NY_PLUS_7; // Broker server-time convention
input int    InpFixedUtcOffsetH = 0;     // Only for 'fixed offset' mode

input group "Housekeeping"
input long   InpMagic          = 26092601; // Magic number
input bool   InpAllowDemoOrders = true;    // Send orders on DEMO accounts (tester always trades)
input bool   InpLogCsv         = true;     // Write CSV logs (MQL5/Files/Common)
input bool   InpShowPanel      = true;     // Show chart panel

//------------------------------------------------------------------------------------------------
// Constants & state
//------------------------------------------------------------------------------------------------
#define NB        2016            // 5-minute buckets per week
#define WMAX      52              // max seasonal weeks supported
#define MISSING   -1.0
#define H_OF_WEEK 168
#define SPREAD_SAMPLES 20

#define SQRT_PI_2 1.2533141373155003   // sqrt(pi/2)
#define GV_PREFIX "QE."

CTrade   g_trade;
int      g_W;                                  // effective seasonal weeks
double   g_hist[];                             // NB * g_W ring of weekly bucket means
double   g_curSum[NB];
int      g_curCnt[NB];
long     g_curWeek = LONG_MIN;
int      g_weeksSeen = 0;

// rolling series (most recent last)
double   g_closeRing[6];                       // last 6 closes (t-5..t)
double   g_eRing[5];                           // last 5 seasonal sigmas
double   g_retRing[60];                        // last 60 log returns
int      g_nClose = 0, g_nE = 0, g_nRet = 0;
double   g_prevClose = 0.0;
bool     g_prevOver = false;

// last closed bar state
datetime g_lastProcessed = 0;                  // server time of last processed closed M1 bar
double   g_lastImpulse = 0.0, g_lastSeas = MISSING, g_lastRv60 = MISSING;
bool     g_lastSignal = false;
int      g_lastDir = 0;
double   g_lastClose = 0.0;
string   g_lastSession = "";

// risk state
long     g_fxDay = LONG_MIN;
double   g_dayStartEq = 0.0;
bool     g_lockout = false;
bool     g_breaker = false;
int      g_orderErrors = 0;
string   g_breakerReason = "";

// spread profile per hour-of-week (NY local), ring of samples in points
double   g_spreadSamples[H_OF_WEEK][SPREAD_SAMPLES];
int      g_spreadCount[H_OF_WEEK];
int      g_spreadPos[H_OF_WEEK];

// position bookkeeping
ulong    g_posTicket = 0;
datetime g_posEntryTime = 0;
double   g_posPlannedRisk = 0.0;
int      g_posDir = 0;

// watchdog
bool     g_wasDisconnected = false;
datetime g_lastTickTime = 0;

// correlation table
string   g_corrA[], g_corrB[];
double   g_corrV[];

bool     g_tradingAllowed = false;
bool     g_inWarmup = false;
datetime g_testStart = 0;
string   g_tradeModeNote = "";

//------------------------------------------------------------------------------------------------
// Time conversion (DST-correct). Mirrored in qe/mql5_parity.py and tested against zoneinfo.
//------------------------------------------------------------------------------------------------
datetime MakeDate(int y, int m, int d, int hh = 0, int mm = 0)
  {
   MqlDateTime t; ZeroMemory(t);
   t.year = y; t.mon = m; t.day = d; t.hour = hh; t.min = mm; t.sec = 0;
   return StructToTime(t);
  }

int DayOfWeek(datetime t) { MqlDateTime s; TimeToStruct(t, s); return s.day_of_week; } // 0 = Sunday

datetime NthSunday(int y, int m, int n)      // n >= 1
  {
   datetime first = MakeDate(y, m, 1);
   int dow = DayOfWeek(first);
   int add = (7 - dow) % 7;
   return first + (datetime)((add + 7 * (n - 1)) * 86400);
  }

datetime LastSunday(int y, int m)
  {
   int ny = (m == 12) ? y + 1 : y;
   int nm = (m == 12) ? 1 : m + 1;
   datetime last = MakeDate(ny, nm, 1) - 86400;
   int dow = DayOfWeek(last);
   return last - (datetime)(dow * 86400);
  }

int YearOf(datetime t) { MqlDateTime s; TimeToStruct(t, s); return s.year; }

// US DST: second Sunday of March 02:00 EST (07:00 UTC) .. first Sunday of November 02:00 EDT (06:00 UTC)
bool IsUSDST_UTC(datetime utc)
  {
   int y = YearOf(utc);
   datetime start = NthSunday(y, 3, 2) + 7 * 3600;
   datetime end   = NthSunday(y, 11, 1) + 6 * 3600;
   return utc >= start && utc < end;
  }

// UK/EU DST: last Sunday of March 01:00 UTC .. last Sunday of October 01:00 UTC
bool IsUKDST_UTC(datetime utc)
  {
   int y = YearOf(utc);
   datetime start = LastSunday(y, 3) + 3600;
   datetime end   = LastSunday(y, 10) + 3600;
   return utc >= start && utc < end;
  }

datetime ServerToUTC(datetime server)
  {
   if(InpServerTime == QE_SERVER_NY_PLUS_7)
     {
      datetime ny = server - 7 * 3600;
      datetime cand = ny + 5 * 3600;             // assume EST
      return IsUSDST_UTC(cand - 3600) ? ny + 4 * 3600 : cand;
     }
   if(InpServerTime == QE_SERVER_EU_DST)
     {
      datetime cand = server - 2 * 3600;         // assume winter UTC+2
      return IsUKDST_UTC(cand - 3600) ? server - 3 * 3600 : cand;
     }
   return server - InpFixedUtcOffsetH * 3600;
  }

datetime UTCToNY(datetime utc)     { return utc - (IsUSDST_UTC(utc) ? 4 : 5) * 3600; }
datetime UTCToLondon(datetime utc) { return utc + (IsUKDST_UTC(utc) ? 1 : 0) * 3600; }
int      MinuteOfDay(datetime t)   { MqlDateTime s; TimeToStruct(t, s); return s.hour * 60 + s.min; }

bool InWindow(int m, int startM, int endM)
  {
   if(startM <= endM) return m >= startM && m < endM;
   return m >= startM || m < endM;
  }

struct SessionInfo
  {
   bool     london;
   bool     newyork;
   bool     blackout;
   long     fxDay;
   int      bucket;
   long     weekId;
   int      hourOfWeek;
  };

SessionInfo Sessions(datetime serverBarOpen)
  {
   SessionInfo si;
   datetime utc = ServerToUTC(serverBarOpen);
   datetime ny  = UTCToNY(utc);
   datetime ldn = UTCToLondon(utc);
   int nyM  = MinuteOfDay(ny);
   int ldM  = MinuteOfDay(ldn);
   si.london   = InWindow(ldM, 8 * 60, 16 * 60 + 30);
   si.newyork  = InWindow(nyM, 8 * 60, 17 * 60);
   si.blackout = InWindow(nyM, 16 * 60 + 45, 17 * 60 + 30);
   si.fxDay    = (long)((ny + 7 * 3600) / 86400);            // 17:00 NY rolls to the next FX day
   int dow     = DayOfWeek(ny);                                // 0 = Sunday
   si.bucket   = dow * 288 + nyM / 5;
   long days   = (long)MathFloor((double)ny / 86400.0);
   si.weekId   = (long)MathFloor((days - 10958) / 7.0);        // weeks start Sunday; 10958 = 2000-01-02
   si.hourOfWeek = dow * 24 + nyM / 60;
   return si;
  }

//------------------------------------------------------------------------------------------------
// Seasonal model (identical algorithm to Pine and qe/pine_parity.py)
//------------------------------------------------------------------------------------------------
void SeasonalReset()
  {
   ArrayResize(g_hist, NB * g_W);
   ArrayInitialize(g_hist, MISSING);
   ArrayInitialize(g_curSum, 0.0);
   ArrayInitialize(g_curCnt, 0);
   g_curWeek = LONG_MIN;
   g_weeksSeen = 0;
  }

void SeasonalRollWeek(long newWeek)
  {
   int slot = (int)(((g_curWeek % g_W) + g_W) % g_W);
   for(int b = 0; b < NB; b++)
     {
      g_hist[b * g_W + slot] = (g_curCnt[b] > 0) ? g_curSum[b] / g_curCnt[b] : MISSING;
      g_curSum[b] = 0.0;
      g_curCnt[b] = 0;
     }
   if(newWeek - g_curWeek > 1)
     {
      long last = (newWeek - 1 < g_curWeek + g_W) ? newWeek - 1 : g_curWeek + g_W;
      for(long wk = g_curWeek + 1; wk <= last; wk++)
        {
         int s2 = (int)(((wk % g_W) + g_W) % g_W);
         for(int b = 0; b < NB; b++) g_hist[b * g_W + s2] = MISSING;
        }
     }
   g_weeksSeen++;
   g_curWeek = newWeek;
  }

double SeasonalExpectation(int bucket)
  {
   double vals[];
   ArrayResize(vals, 0, g_W);
   for(int j = 0; j < g_W; j++)
     {
      double v = g_hist[bucket * g_W + j];
      if(v >= 0.0)
        {
         int n = ArraySize(vals);
         ArrayResize(vals, n + 1, g_W);
         vals[n] = v;
        }
     }
   int n = ArraySize(vals);
   if(n < InpSeasonMinWeeks) return MISSING;
   ArraySort(vals);
   double med = (n % 2 == 1) ? vals[n / 2] : 0.5 * (vals[n / 2 - 1] + vals[n / 2]);
   return med * SQRT_PI_2;
  }

//------------------------------------------------------------------------------------------------
// Rolling helpers
//------------------------------------------------------------------------------------------------
void PushRing(double &ring[], int &count, double v)
  {
   int size = ArraySize(ring);
   if(count < size) { ring[count] = v; count++; return; }
   for(int i = 1; i < size; i++) ring[i - 1] = ring[i];
   ring[size - 1] = v;
  }

double StdevUnbiased(const double &x[], int n)
  {
   if(n < 2) return MISSING;
   double m = 0.0;
   for(int i = 0; i < n; i++) m += x[i];
   m /= n;
   double s = 0.0;
   for(int i = 0; i < n; i++) s += (x[i] - m) * (x[i] - m);
   return MathSqrt(s / (n - 1));
  }

//------------------------------------------------------------------------------------------------
// Process one CLOSED M1 bar (bid). Mirrors the Pine bar logic exactly, in the same order.
//------------------------------------------------------------------------------------------------
void ProcessClosedBar(const MqlRates &bar)
  {
   SessionInfo si = Sessions(bar.time);
   double c = bar.close;
   double absr = MISSING, r1 = 0.0;
   bool haveRet = (g_prevClose > 0.0 && c > 0.0);
   if(haveRet) { r1 = MathLog(c) - MathLog(g_prevClose); absr = MathAbs(r1); }

   // week roll
   if(g_curWeek == LONG_MIN) g_curWeek = si.weekId;
   else if(si.weekId != g_curWeek) SeasonalRollWeek(si.weekId);

   // expectation from previous weeks only
   double e = SeasonalExpectation(si.bucket);

   // accumulate current bar AFTER the expectation (causal)
   if(haveRet)
     {
      g_curSum[si.bucket] += absr;
      g_curCnt[si.bucket] += 1;
      PushRing(g_retRing, g_nRet, r1);
     }
   PushRing(g_closeRing, g_nClose, c);
   PushRing(g_eRing, g_nE, e);

   // impulse = ln(C_t/C_t-5) / sqrt(sum e^2 over last 5 bars)
   double impulse = 0.0;
   bool valid = false;
   if(g_nClose == 6 && g_nE == 5)
     {
      double s = 0.0;
      bool ok = true;
      for(int i = 0; i < 5; i++) { if(g_eRing[i] < 0.0) { ok = false; break; } s += g_eRing[i] * g_eRing[i]; }
      if(ok && s > 0.0)
        {
         impulse = (MathLog(g_closeRing[5]) - MathLog(g_closeRing[0])) / MathSqrt(s);
         valid = true;
        }
     }
   double rv60 = (g_nRet == 60) ? StdevUnbiased(g_retRing, 60) : MISSING;

   bool over = valid && MathAbs(impulse) > InpK;
   bool trigger = over && !g_prevOver;
   g_prevOver = over;

   bool active = si.london || si.newyork;
   bool sessOk = (InpMode == QE_ACTIVE_FADE) ? active : (!active && !si.blackout);

   g_lastImpulse = valid ? impulse : 0.0;
   g_lastSeas    = e;
   g_lastRv60    = rv60;
   g_lastClose   = c;
   g_lastSignal  = trigger && sessOk && !si.blackout;
   g_lastDir     = (impulse > 0.0) ? -1 : 1;                  // AGAINST the impulse
   g_lastSession = si.blackout ? "ROLLOVER BLACKOUT" : (active ? "active (LDN/NY)" : "quiet");
   g_prevClose   = c;
   g_lastProcessed = bar.time;

   if(trigger && !g_inWarmup)
      LogCsv("event", g_lastDir, impulse, e, rv60, 0, 0, 0,
             g_lastSignal ? "signal" : (si.blackout ? "blackout" : "session_filter"));
  }

//------------------------------------------------------------------------------------------------
// History warm-up / catch-up
//------------------------------------------------------------------------------------------------
bool CatchUp()
  {
   datetime lastClosedOpen = iTime(_Symbol, PERIOD_M1, 1);
   if(lastClosedOpen == 0) return false;
   if(g_lastProcessed >= lastClosedOpen) return true;
   datetime from = (g_lastProcessed == 0)
                   ? lastClosedOpen - (datetime)((g_W + 1) * 7 * 86400)
                   : g_lastProcessed + 60;
   MqlRates rates[];
   ArraySetAsSeries(rates, false);
   int n = CopyRates(_Symbol, PERIOD_M1, from, lastClosedOpen, rates);
   if(n <= 0) { PrintFormat("QE: CopyRates failed (%d), err %d", n, GetLastError()); return false; }
   for(int i = 0; i < n; i++)
      if(rates[i].time > g_lastProcessed && rates[i].time <= lastClosedOpen)
         ProcessClosedBar(rates[i]);
   return true;
  }

//------------------------------------------------------------------------------------------------
// Portfolio ledger (terminal global variables shared by all QE instances)
//------------------------------------------------------------------------------------------------
string GvRisk(string sym) { return GV_PREFIX + "risk." + sym + "." + IntegerToString(InpMagic); }
string GvDir(string sym)  { return GV_PREFIX + "dir."  + sym + "." + IntegerToString(InpMagic); }

void LedgerSet(double risk, int dir)
  {
   GlobalVariableSet(GvRisk(_Symbol), risk);
   GlobalVariableSet(GvDir(_Symbol), dir);
  }

void LedgerClear() { LedgerSet(0.0, 0); }

// sum of open planned risk and count of open QE positions across all instances (any magic)
void LedgerTotals(double &openRisk, int &positions, bool excludeSelf)
  {
   openRisk = 0.0; positions = 0;
   int total = GlobalVariablesTotal();
   for(int i = 0; i < total; i++)
     {
      string name = GlobalVariableName(i);
      if(StringFind(name, GV_PREFIX + "risk.") != 0) continue;
      if(excludeSelf && name == GvRisk(_Symbol)) continue;
      double v = GlobalVariableGet(name);
      if(v > 0.0) { openRisk += v; positions++; }
     }
  }

void ParseCorrTable()
  {
   ArrayResize(g_corrA, 0); ArrayResize(g_corrB, 0); ArrayResize(g_corrV, 0);
   string items[];
   int n = StringSplit(InpCorrTable, ';', items);
   for(int i = 0; i < n; i++)
     {
      string kv[];
      if(StringSplit(items[i], '=', kv) != 2) continue;
      string ab[];
      if(StringSplit(kv[0], '/', ab) != 2) continue;
      int k = ArraySize(g_corrV);
      ArrayResize(g_corrA, k + 1); ArrayResize(g_corrB, k + 1); ArrayResize(g_corrV, k + 1);
      g_corrA[k] = ab[0]; g_corrB[k] = ab[1]; g_corrV[k] = StringToDouble(kv[1]);
     }
  }

double Corr(string a, string b)
  {
   if(a == b) return 1.0;
   for(int i = 0; i < ArraySize(g_corrV); i++)
      if((g_corrA[i] == a && g_corrB[i] == b) || (g_corrA[i] == b && g_corrB[i] == a))
         return g_corrV[i];
   return 0.0;
  }

// symbol names on some brokers carry suffixes (e.g. EURUSD.a): compare on the first 6 characters
string BaseSym(string s) { return StringSubstr(s, 0, 6); }

bool CorrelationBlocked(int dir, string &blocker)
  {
   int total = GlobalVariablesTotal();
   for(int i = 0; i < total; i++)
     {
      string name = GlobalVariableName(i);
      if(StringFind(name, GV_PREFIX + "dir.") != 0) continue;
      if(name == GvDir(_Symbol)) continue;
      double d = GlobalVariableGet(name);
      if(d == 0.0) continue;
      string rest = StringSubstr(name, StringLen(GV_PREFIX + "dir."));
      string parts[];
      if(StringSplit(rest, '.', parts) < 2) continue;
      string other = parts[0];
      if(Corr(BaseSym(_Symbol), BaseSym(other)) * dir * d >= InpCorrThreshold)
        { blocker = other; return true; }
     }
   return false;
  }

//------------------------------------------------------------------------------------------------
// Spread profile (execution-health breaker)
//------------------------------------------------------------------------------------------------
void SpreadSample(int how, double pts)
  {
   g_spreadSamples[how][g_spreadPos[how]] = pts;
   g_spreadPos[how] = (g_spreadPos[how] + 1) % SPREAD_SAMPLES;
   if(g_spreadCount[how] < SPREAD_SAMPLES) g_spreadCount[how]++;
  }

double SpreadMedian(int how)
  {
   int n = g_spreadCount[how];
   if(n < 5) return MISSING;
   double v[];
   ArrayResize(v, n);
   for(int i = 0; i < n; i++) v[i] = g_spreadSamples[how][i];
   ArraySort(v);
   return (n % 2 == 1) ? v[n / 2] : 0.5 * (v[n / 2 - 1] + v[n / 2]);
  }

//------------------------------------------------------------------------------------------------
// Position helpers
//------------------------------------------------------------------------------------------------
bool FindOwnPosition()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      g_posTicket = t;
      g_posEntryTime = (datetime)PositionGetInteger(POSITION_TIME);
      g_posDir = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
      return true;
     }
   g_posTicket = 0;
   return false;
  }

bool ClosePosition(string reason)
  {
   if(!FindOwnPosition()) return true;
   if(!g_tradingAllowed)
     {
      LogCsv("paper_close", g_posDir, 0, 0, 0, 0, 0, 0, reason);
      g_posTicket = 0; LedgerClear();
      return true;
     }
   bool ok = g_trade.PositionClose(g_posTicket, InpDeviationPts);
   uint rc = g_trade.ResultRetcode();
   if(!ok || (rc != TRADE_RETCODE_DONE && rc != TRADE_RETCODE_DONE_PARTIAL && rc != TRADE_RETCODE_PLACED))
     {
      OnOrderError("close_failed rc=" + IntegerToString((int)rc));
      return false;
     }
   LogCsv("close", g_posDir, 0, 0, 0, 0, g_trade.ResultPrice(), 0, reason);
   g_orderErrors = 0;
   if(!FindOwnPosition()) LedgerClear();
   return true;
  }

void OnOrderError(string what)
  {
   g_orderErrors++;
   LogCsv("order_error", 0, 0, 0, 0, 0, 0, 0, what);
   if(g_orderErrors >= InpMaxOrderErrors)
     {
      g_breaker = true;
      g_breakerReason = "order errors";
      LogCsv("breaker", 0, 0, 0, 0, 0, 0, 0, "consecutive order errors");
     }
  }

//------------------------------------------------------------------------------------------------
// Risk: FX-day bookkeeping and sizing
//------------------------------------------------------------------------------------------------
void UpdateFxDay(const SessionInfo &si)
  {
   if(si.fxDay != g_fxDay)
     {
      g_fxDay = si.fxDay;
      g_dayStartEq = AccountInfoDouble(ACCOUNT_EQUITY);
      g_lockout = false;
      g_breaker = false;
      g_breakerReason = "";
      g_orderErrors = 0;
     }
   double dayLoss = MathMax(0.0, g_dayStartEq - AccountInfoDouble(ACCOUNT_EQUITY));
   if(!g_lockout && dayLoss >= g_dayStartEq * MathMin(InpDayLossPct, 1.0) / 100.0)
     {
      g_lockout = true;
      LogCsv("lockout", 0, 0, 0, 0, 0, 0, 0, "daily loss limit");
     }
  }

// Loss in account currency for 1.0 lot when price moves `dist` against the position
double LossPerLot(double dist)
  {
   double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
   if(tv <= 0.0) tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(ts <= 0.0 || tv <= 0.0) return 0.0;
   return dist / ts * tv;
  }

double SizeLots(double stopDist, double &plannedRisk)
  {
   plannedRisk = 0.0;
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   double budget = eq * MathMin(InpRiskPct, 0.20) / 100.0;
   double perLot = LossPerLot(stopDist) + 2.0 * InpCommLotSide;   // same as qe/risk.py (slippage 0 here)
   if(perLot <= 0.0) return 0.0;
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lots = MathFloor(budget / perLot / step + 1e-9) * step;
   lots = MathMin(lots, vmax);
   if(lots < vmin) return 0.0;
   plannedRisk = lots * perLot;
   return NormalizeDouble(lots, 8);
  }

//------------------------------------------------------------------------------------------------
// Entry
//------------------------------------------------------------------------------------------------
void TryEntry(datetime newBarOpen, const SessionInfo &siNow)
  {
   if(!g_lastSignal) return;
   // the signal bar must be the bar immediately before this one (no entries on stale signals,
   // e.g. a Friday-close signal carried over the weekend gap)
   if(newBarOpen - g_lastProcessed > 5 * 60)
     {
      LogCsv("reject", g_lastDir, g_lastImpulse, g_lastSeas, g_lastRv60, 0, 0, 0, "stale_signal_gap");
      g_lastSignal = false;
      return;
     }
   int dir = g_lastDir;
   string why = "";
   double sigmaUse = MathMax(g_lastSeas > 0 ? g_lastSeas : 0.0, g_lastRv60 > 0 ? g_lastRv60 : 0.0);
   double moveDist = sigmaUse * MathSqrt((double)InpHoldMin) * g_lastClose;
   double stopDist = InpStopMult * moveDist;
   double plannedRisk = 0.0;
   double lots = (moveDist > 0.0) ? SizeLots(stopDist, plannedRisk) : 0.0;
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   double nominal = eq * MathMin(InpRiskPct, 0.20) / 100.0;
   double dayLimit = g_dayStartEq * MathMin(InpDayLossPct, 1.0) / 100.0;
   double dayLoss = MathMax(0.0, g_dayStartEq - eq);
   double othersRisk; int othersPos;
   LedgerTotals(othersRisk, othersPos, true);

   MqlTick tk; SymbolInfoTick(_Symbol, tk);
   double spreadPts = (tk.ask - tk.bid) / _Point;
   double spreadMed = SpreadMedian(siNow.hourOfWeek);

   if(siNow.blackout)                                         why = "rollover_blackout";
   else if(g_breaker)                                         why = "execution_breaker:" + g_breakerReason;
   else if(g_lockout)                                         why = "daily_lockout";
   else if(FindOwnPosition())                                 why = "symbol_already_open";
   else if(moveDist <= 0.0)                                   why = "no_volatility_estimate";
   else if(lots <= 0.0)                                       why = "below_min_lot";
   else if(othersPos >= InpMaxPositions)                      why = "max_positions";
   else if(othersRisk + plannedRisk > eq * InpMaxOpenRiskPct / 100.0 + 1e-9) why = "max_open_risk";
   else if(dayLoss + othersRisk + MathMax(plannedRisk, nominal) > dayLimit + 1e-9) why = "daily_budget_insufficient";
   else if(spreadMed > 0.0 && spreadPts > InpSpreadSpikeMult * spreadMed) why = "spread_spike";
   else
     {
      string blocker;
      if(CorrelationBlocked(dir, blocker)) why = "correlated_with_" + blocker;
     }

   if(why != "")
     {
      LogCsv("reject", dir, g_lastImpulse, g_lastSeas, g_lastRv60, lots, 0, plannedRisk, why);
      return;
     }

   double stopsLevel = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   double entry = (dir > 0) ? tk.ask : tk.bid;
   double tgtDist = (InpTargetMult > 0.0) ? InpTargetMult * moveDist : 0.0;
   if(stopDist <= stopsLevel || (tgtDist > 0.0 && tgtDist <= stopsLevel))
     {
      LogCsv("reject", dir, g_lastImpulse, g_lastSeas, g_lastRv60, lots, entry, plannedRisk, "inside_stops_level");
      return;
     }
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double sl = NormalizeDouble(entry - dir * stopDist, digits);
   double tp = (tgtDist > 0.0) ? NormalizeDouble(entry + dir * tgtDist, digits) : 0.0;
   string comment = StringFormat("QE|R=%.2f|H=%d", plannedRisk, InpHoldMin);

   if(!g_tradingAllowed)
     {
      LogCsv("paper_entry", dir, g_lastImpulse, g_lastSeas, g_lastRv60, lots, entry, plannedRisk, g_tradeModeNote);
      return;
     }

   bool ok = (dir > 0) ? g_trade.Buy(lots, _Symbol, 0.0, sl, tp, comment)
                       : g_trade.Sell(lots, _Symbol, 0.0, sl, tp, comment);
   uint rc = g_trade.ResultRetcode();
   if(!ok || (rc != TRADE_RETCODE_DONE && rc != TRADE_RETCODE_DONE_PARTIAL && rc != TRADE_RETCODE_PLACED))
     {
      OnOrderError("entry_failed rc=" + IntegerToString((int)rc));
      return;
     }
   g_orderErrors = 0;
   double fill = g_trade.ResultPrice();
   if(FindOwnPosition())
     {
      // re-anchor SL/TP to the actual fill (parity with the research simulator)
      if(fill > 0.0 && MathAbs(fill - entry) >= _Point)
        {
         double sl2 = NormalizeDouble(fill - dir * stopDist, digits);
         double tp2 = (tgtDist > 0.0) ? NormalizeDouble(fill + dir * tgtDist, digits) : 0.0;
         g_trade.PositionModify(g_posTicket, sl2, tp2);
        }
      g_posPlannedRisk = plannedRisk;
      LedgerSet(plannedRisk, dir);
     }
   LogCsv("entry", dir, g_lastImpulse, g_lastSeas, g_lastRv60, lots, fill, plannedRisk, "ok");
  }

//------------------------------------------------------------------------------------------------
// Exits (time, rollover, max holding)
//------------------------------------------------------------------------------------------------
void ManageExits(datetime newBarOpen, const SessionInfo &siNow)
  {
   if(!FindOwnPosition())
     {
      if(GlobalVariableCheck(GvRisk(_Symbol)) && GlobalVariableGet(GvRisk(_Symbol)) > 0.0) LedgerClear();
      return;
     }
   long heldSec = (long)(newBarOpen - g_posEntryTime);
   if(siNow.blackout)                                   ClosePosition("rollover");
   else if(heldSec >= (long)InpHoldMin * 60)            ClosePosition("time");
   else if(heldSec >= 120 * 60)                         ClosePosition("max_hold_120");
  }

//------------------------------------------------------------------------------------------------
// Logging
//------------------------------------------------------------------------------------------------
void LogCsv(string ev, int dir, double impulse, double seas, double rv60, double lots, double price,
            double risk, string note)
  {
   if(!InpLogCsv) return;
   MqlDateTime s; TimeToStruct(TimeCurrent(), s);
   string fn = StringFormat("QE_%s_%d_%04d%02d%02d.csv", _Symbol, InpMagic, s.year, s.mon, s.day);
   int h = FileOpen(fn, FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_SHARE_READ | FILE_COMMON, ',');
   if(h == INVALID_HANDLE) return;
   if(FileSize(h) == 0)
      FileWrite(h, "server_time", "bar_time", "event", "dir", "impulse", "seasonal_sigma", "rv60",
                "lots", "price", "planned_risk", "equity", "spread_pts", "note");
   FileSeek(h, 0, SEEK_END);
   MqlTick tk; SymbolInfoTick(_Symbol, tk);
   FileWrite(h, TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS), TimeToString(g_lastProcessed, TIME_DATE | TIME_MINUTES),
             ev, dir, DoubleToString(impulse, 4), DoubleToString(seas, 10), DoubleToString(rv60, 10),
             DoubleToString(lots, 2), DoubleToString(price, _Digits), DoubleToString(risk, 2),
             DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2), DoubleToString((tk.ask - tk.bid) / _Point, 1), note);
   FileClose(h);
  }

//------------------------------------------------------------------------------------------------
// Panel
//------------------------------------------------------------------------------------------------
void DrawPanel()
  {
   if(!InpShowPanel) return;
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   double openRisk; int pos;
   LedgerTotals(openRisk, pos, false);
   string txt = StringFormat(
      "QUANTUM EDGE - research EA (%s)\n"
      "Mode %s | k=%.1f | H=%d min | stop %.2f | target %.2f\n"
      "Seasonal weeks loaded: %d%s\n"
      "Last bar %s | impulse %.2f | session %s\n"
      "Day P&L: %.3f%% | lockout: %s | breaker: %s\n"
      "QE open positions: %d | open planned risk: %.2f\n"
      "Research verdict: NOT validated (see FINAL_REPORT.md)",
      g_tradeModeNote,
      InpMode == QE_ACTIVE_FADE ? "Active fade" : "Quiet revert", InpK, InpHoldMin, InpStopMult, InpTargetMult,
      g_weeksSeen, g_weeksSeen < InpSeasonMinWeeks ? " (warming up: NO TRADES)" : "",
      TimeToString(g_lastProcessed, TIME_DATE | TIME_MINUTES), g_lastImpulse, g_lastSession,
      g_dayStartEq > 0 ? 100.0 * (eq - g_dayStartEq) / g_dayStartEq : 0.0,
      g_lockout ? "LOCKED" : "open", g_breaker ? g_breakerReason : "ok",
      pos, openRisk);
   Comment(txt);
  }

//------------------------------------------------------------------------------------------------
// Event handlers
//------------------------------------------------------------------------------------------------
int OnInit()
  {
   if(InpHoldMin < 5 || InpHoldMin > 120) { Print("QE: InpHoldMin must be 5..120"); return INIT_PARAMETERS_INCORRECT; }
   if(InpRiskPct <= 0.0 || InpRiskPct > 0.20) { Print("QE: InpRiskPct must be in (0, 0.20]"); return INIT_PARAMETERS_INCORRECT; }
   if(InpDayLossPct <= 0.0 || InpDayLossPct > 1.0) { Print("QE: InpDayLossPct must be in (0, 1.0]"); return INIT_PARAMETERS_INCORRECT; }
   if(InpSeasonWeeks < InpSeasonMinWeeks || InpSeasonWeeks > WMAX) { Print("QE: bad seasonal weeks"); return INIT_PARAMETERS_INCORRECT; }

   // trading permission: tester always; demo if allowed; REAL accounts are log-only (research phase)
   bool tester = (bool)MQLInfoInteger(MQL_TESTER) || (bool)MQLInfoInteger(MQL_OPTIMIZATION);
   ENUM_ACCOUNT_TRADE_MODE am = (ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE);
   if(tester)                                          { g_tradingAllowed = true;  g_tradeModeNote = "STRATEGY TESTER"; }
   else if(am == ACCOUNT_TRADE_MODE_DEMO && InpAllowDemoOrders) { g_tradingAllowed = true;  g_tradeModeNote = "DEMO"; }
   else if(am == ACCOUNT_TRADE_MODE_REAL)              { g_tradingAllowed = false; g_tradeModeNote = "REAL ACCOUNT: LOG-ONLY"; }
   else                                                { g_tradingAllowed = false; g_tradeModeNote = "LOG-ONLY"; }

   g_W = InpSeasonWeeks;
   SeasonalReset();
   ArrayInitialize(g_spreadCount, 0);
   ArrayInitialize(g_spreadPos, 0);
   ParseCorrTable();

   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(InpDeviationPts);
   g_trade.SetTypeFillingBySymbol(_Symbol);
   g_trade.SetAsyncMode(false);

   g_testStart = TimeCurrent();
   g_inWarmup = true;
   if(!CatchUp()) Print("QE: warm-up incomplete; will retry on the next bar");
   g_inWarmup = false;
   PrintFormat("QE: init %s | mode %s | weeks loaded %d | %s", _Symbol,
               InpMode == QE_ACTIVE_FADE ? "Active fade" : "Quiet revert", g_weeksSeen, g_tradeModeNote);
   EventSetTimer(5);
   DrawPanel();
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   if(!FindOwnPosition()) LedgerClear();
   Comment("");
  }

void OnTick()
  {
   g_lastTickTime = TimeCurrent();
   static datetime lastBar = 0;
   datetime barOpen = iTime(_Symbol, PERIOD_M1, 0);
   if(barOpen == 0 || barOpen == lastBar) return;
   lastBar = barOpen;

   // 1) process every newly CLOSED bar (decisions at bar close)
   if(!CatchUp()) return;

   SessionInfo siNow = Sessions(barOpen);
   UpdateFxDay(siNow);

   // 2) spread profile: one sample per 15 minutes -> the 20-sample ring per hour-of-week spans ~5 weeks
   MqlTick tk;
   if(MinuteOfDay(UTCToNY(ServerToUTC(barOpen))) % 15 == 0 && SymbolInfoTick(_Symbol, tk) && tk.ask > tk.bid)
      SpreadSample(siNow.hourOfWeek, (tk.ask - tk.bid) / _Point);

   // 3) exits first, then entries (fills at the open of the bar after the signal bar)
   ManageExits(barOpen, siNow);
   if(g_weeksSeen >= InpSeasonMinWeeks) TryEntry(barOpen, siNow);
   g_lastSignal = false;   // a signal is acted on (or rejected) exactly once
   DrawPanel();
  }

void OnTimer()
  {
   bool connected = (bool)TerminalInfoInteger(TERMINAL_CONNECTED);
   if(!connected) { g_wasDisconnected = true; return; }
   if(g_wasDisconnected)
     {
      g_wasDisconnected = false;
      LogCsv("reconnect", 0, 0, 0, 0, 0, 0, 0, "connection restored");
      if(FindOwnPosition())
        {
         datetime now = TimeCurrent();
         SessionInfo si = Sessions(now);
         if(si.blackout || (long)(now - g_posEntryTime) >= (long)InpHoldMin * 60)
            ClosePosition("reconnect_overdue");
        }
     }
   if(g_lastTickTime > 0 && TimeCurrent() - g_lastTickTime > InpDisconnectSec && FindOwnPosition()
      && !(bool)MQLInfoInteger(MQL_TESTER))
     {
      datetime now = TimeCurrent();
      if((long)(now - g_posEntryTime) >= (long)InpHoldMin * 60) ClosePosition("stale_feed_overdue");
     }
  }

void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   if(!HistoryDealSelect(trans.deal)) return;
   if(HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != InpMagic) return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol) return;
   long entry = HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
   if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
     {
      double pnl = HistoryDealGetDouble(trans.deal, DEAL_PROFIT) + HistoryDealGetDouble(trans.deal, DEAL_COMMISSION)
                   + HistoryDealGetDouble(trans.deal, DEAL_SWAP) + HistoryDealGetDouble(trans.deal, DEAL_FEE);
      long rsn = HistoryDealGetInteger(trans.deal, DEAL_REASON);
      string why = (rsn == DEAL_REASON_SL) ? "stop" : (rsn == DEAL_REASON_TP) ? "target" : "closed";
      LogCsv("exit_deal", 0, 0, 0, 0, HistoryDealGetDouble(trans.deal, DEAL_VOLUME),
             HistoryDealGetDouble(trans.deal, DEAL_PRICE), pnl, why);
      if(!FindOwnPosition()) LedgerClear();
     }
  }

//------------------------------------------------------------------------------------------------
// Strategy Tester: report per-trade R statistics comparable with the Python research (EXP006/007)
//------------------------------------------------------------------------------------------------
double OnTester()
  {
   if(!HistorySelect(0, TimeCurrent())) return 0.0;
   int nd = HistoryDealsTotal();
   // position id -> planned risk (from the IN deal comment) and accumulated P&L
   long   ids[];  double risk[]; double pnl[];
   for(int i = 0; i < nd; i++)
     {
      ulong d = HistoryDealGetTicket(i);
      if(HistoryDealGetInteger(d, DEAL_MAGIC) != InpMagic) continue;
      long pid = HistoryDealGetInteger(d, DEAL_POSITION_ID);
      int k = -1;
      for(int j = 0; j < ArraySize(ids); j++) if(ids[j] == pid) { k = j; break; }
      if(k < 0)
        {
         k = ArraySize(ids);
         ArrayResize(ids, k + 1); ArrayResize(risk, k + 1); ArrayResize(pnl, k + 1);
         ids[k] = pid; risk[k] = 0.0; pnl[k] = 0.0;
        }
      pnl[k] += HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_COMMISSION)
                + HistoryDealGetDouble(d, DEAL_SWAP) + HistoryDealGetDouble(d, DEAL_FEE);
      if(HistoryDealGetInteger(d, DEAL_ENTRY) == DEAL_ENTRY_IN)
        {
         string c = HistoryDealGetString(d, DEAL_COMMENT);
         int p = StringFind(c, "R=");
         if(p >= 0)
           {
            string rest = StringSubstr(c, p + 2);
            int bar = StringFind(rest, "|");
            risk[k] = StringToDouble(bar >= 0 ? StringSubstr(rest, 0, bar) : rest);
           }
        }
     }
   int n = 0; double sum = 0.0, sum2 = 0.0;
   for(int k = 0; k < ArraySize(ids); k++)
     {
      if(risk[k] <= 0.0) continue;
      double r = pnl[k] / risk[k];
      n++; sum += r; sum2 += r * r;
     }
   double mean = (n > 0) ? sum / n : 0.0;
   double sd = (n > 1) ? MathSqrt((sum2 - n * mean * mean) / (n - 1)) : 0.0;
   double t = (sd > 0.0) ? mean / (sd / MathSqrt(n)) : 0.0;
   int h = FileOpen("QE_tester_summary.csv", FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_COMMON, ',');
   if(h != INVALID_HANDLE)
     {
      if(FileSize(h) == 0) FileWrite(h, "symbol", "mode", "k", "H", "stop", "target", "trades", "mean_R", "sd_R", "t_stat",
                                     "net_profit", "from", "to");
      FileSeek(h, 0, SEEK_END);
      FileWrite(h, _Symbol, (int)InpMode, InpK, InpHoldMin, InpStopMult, InpTargetMult, n, DoubleToString(mean, 4),
                DoubleToString(sd, 4), DoubleToString(t, 2), DoubleToString(TesterStatistics(STAT_PROFIT), 2),
                TimeToString(g_testStart, TIME_DATE), TimeToString(TimeCurrent(), TIME_DATE));
      FileClose(h);
     }
   PrintFormat("QE tester: trades=%d mean R=%.4f sd=%.4f t=%.2f", n, mean, sd, t);
   return mean;   // custom optimisation criterion = mean net R per trade (do NOT optimise on it blindly)
  }
//+------------------------------------------------------------------------------------------------+
