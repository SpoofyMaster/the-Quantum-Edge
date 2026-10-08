//+------------------------------------------------------------------+
//| BprFvgEA.mq5                                                     |
//| LuxAlgo FVG / BPR zones on the chart + BPR / FVG retest setups   |
//+------------------------------------------------------------------+
//
// © LuxAlgo (original Pine v5 logic of 'ICT Concepts [LuxAlgo]')
// Licence: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)
//          https://creativecommons.org/licenses/by-nc-sa/4.0/
//
// This Expert Advisor contains a PORT / DERIVATIVE WORK of the FVG, Balance Price Range, displacement and
// "Fibonacci between last: BPR" logic of the Pine v5 script "ICT Concepts [LuxAlgo]" (include/BfEngine.mqh,
// include/BfRender.mqh, adapted from mql5/Indicators/LuxAlgo_BPR/LuxAlgo_BPR.mq5). The EA as a whole is distributed
// under the same licence (CC BY-NC-SA 4.0): NON-COMMERCIAL use only, attribution to LuxAlgo required, and any
// redistributed derivative must keep this licence. It is not affiliated with or endorsed by LuxAlgo.
// The setup rules (sweep, structure shift, entries, stops, targets) are this project's own.
//
// Specification (single source of truth): research/indicators/BPR_FVG_EA_SPEC.md ("spec s.N" below).
// Engine specification: research/indicators/LUXALGO_BPR_SPEC.md. Rules' origin: BPR_RETEST_PLAYBOOK.md.
// Python reference: qe/strategies/bpr_fvg.py (same detector decisions).
//
// STATUS: NOT YET COMPILED in MetaEditor (written without a compiler). Send the compiler messages.
// TRADING RULES: untested HYPOTHESIS H-13. No claim of profitability.
// SAFETY: orders are sent only in the Strategy Tester and on DEMO accounts. On a REAL account the EA is log-only
//         (draws, detects, logs; sends no order). There is deliberately no input to change this.
//         Do not tune on the locked final-test period (>= 2025-07-01, config/research.toml).
// INSTALL: copy the whole BprFvgEA folder (this file + include/) to MQL5/Experts/ and compile BprFvgEA.mq5.
//+------------------------------------------------------------------+
#property copyright   "(c) LuxAlgo - FVG/BPR Pine v5 logic; port + setups under CC BY-NC-SA 4.0"
#property link        "https://creativecommons.org/licenses/by-nc-sa/4.0/"
#property version     "1.00"
#property description "LuxAlgo FVG/BPR zones + BPR/FVG retest setups (hypothesis H-13, untested)."
#property description "Tester/demo only; real accounts are log-only. Licence CC BY-NC-SA 4.0 (non-commercial)."

#include "include/BfDefines.mqh"
#include "include/BfEngine.mqh"
#include "include/BfDetector.mqh"
#include "include/BfSession.mqh"
#include "include/BfRisk.mqh"
#include "include/BfTrade.mqh"
#include "include/BfRender.mqh"
#include "include/BfLogger.mqh"

//+------------------------------------------------------------------+
//| Inputs (spec s.1). Enums are declared in include/BfDefines.mqh.  |
//+------------------------------------------------------------------+
input group "==== DISPLAY (LuxAlgo look) ===="
input bool                InpShowZones            = true;               // Draw the LuxAlgo boxes
input bool                InpShowBPR              = true;               // Show BPR boxes (false = FVG boxes); BPRs are always computed
input bool                InpShowFVGinBPRmode     = false;              // Debug: also draw the FVG boxes when BPRs are shown
input int                 InpVisibleBoxes         = 2;                  // # Visible FVG's (1..20): engine array length
input int                 InpLength               = 5;                  // Length (3..10): period of the body SMA
input ENUM_BF_FVGTYPE     InpFvgType              = BF_FVGTYPE_FVG;     // Options: FVG / IFVG (setups need FVG)
input bool                InpShowDisplacement     = false;              // Show displacement markers
input int                 InpDisplacementBars     = 300;                // Displacement markers on the last N bars
input ENUM_BF_FIB         InpFib                  = BF_FIB_NONE;        // Fibonacci between last: NONE / BPR
input bool                InpFibExtend            = false;              // Extend the Fibonacci lines
input bool                InpLiveBar              = true;               // Display the forming bar (decisions never use it)
input color               InpBullColor            = C'0,230,118';       // Bullish FVG / BPR colour
input color               InpBullBreakColor       = C'128,128,0';       // Bullish break colour
input color               InpBearColor            = C'255,82,82';       // Bearish FVG / BPR colour
input color               InpBearBreakColor       = C'255,0,0';         // Bearish break colour
input int                 InpFillTransp           = 90;                 // Fill transparency 0..100
input int                 InpBorderTransp         = 65;                 // Border / text transparency 0..100
input int                 InpBreakTransp          = 95;                 // Broken fill transparency 0..100
input bool                InpShowTradeBoxes       = true;               // Position-tool overlay for each order
input bool                InpShowPanel            = true;               // Status panel

input group "==== SETUPS (hypothesis H-13, untested) ===="
input ENUM_BF_SOURCE      InpSetupSource          = BF_SOURCE_BPR;      // Setup source: BPR / FVG / BOTH
input ENUM_BF_DIRECTION   InpDirection            = BF_DIR_BOTH;        // Direction
input ENUM_BF_ENTRY       InpEntryMode            = BF_ENTRY_LIMIT;     // Entry mode
input int                 InpEntryOffsetTicks     = 5;                  // LIMIT: offset delta from the far edge, ticks
input bool                InpUseSweep             = true;               // Require a liquidity sweep
input int                 InpSweepWindow          = 30;                 // Sweep window, bars
input int                 InpRangeBars            = 30;                 // Range before the sweep, bars
input bool                InpUseMss               = true;               // Require a structure shift (MSS)
input int                 InpMssBars              = 20;                 // Structure-shift window, bars
input int                 InpRallyBars            = 10;                 // Measured-move origin window, bars
input int                 InpExpiryBars           = 60;                 // Setup expiry, bars after creation
input double              InpStopZoneMult         = 1.2;                // Stop = zone heights beyond the far edge
input double              InpMinRR                = 1.0;                // Minimum reward:risk at TP1
input double              InpMaxCostR             = 0.15;               // Maximum round-trip cost, fraction of R
input ENUM_BF_TPMODE      InpTpMode               = BF_TP_TP1_TP2;      // Take-profit mode
input double              InpTp1Fraction          = 0.5;                // Fraction closed at TP1 (TP1_TP2)
input bool                InpBreakEven            = true;               // Stop to entry + commission after TP1
input int                 InpMaxHoldMin           = 120;                // Time stop, minutes (max 120)

input group "==== SESSION, RISK, EXECUTION ===="
input ENUM_BF_SERVER_TIME InpServerMode           = BF_SERVER_NY_PLUS_7;// Server time convention
input int                 InpServerOffsetH        = 0;                  // Fixed-offset mode only: server = UTC + hours
input bool                InpUseSession           = true;               // Entries 08:00 London .. 14:45 New York, Mon-Fri
input double              InpRiskPct              = 0.20;               // Risk per trade, % equity incl. commission (max 0.20)
input double              InpDailyLossPct         = 1.00;               // Planned daily loss, % (FX day 17:00 NY; max 1.00)
input int                 InpMaxTradesDay         = 0;                  // Max trades per FX day (0 = no limit)
input double              InpCommissionPerLotSide = 3.50;               // Commission per lot per side, account ccy (UNVERIFIED)
input int                 InpSlippageTicks        = 1;                  // Slippage ticks (planned risk, cost check)
input int                 InpMaxSpreadPts         = 0;                  // Max spread in points (0 = off)
input long                InpMagic                = 2610081;            // Magic number
input int                 InpDeviationPts         = 30;                 // Max deviation for market orders, points
input int                 InpWarmupBars           = 5000;               // Closed bars processed at start (never traded)
input bool                InpLogCsv               = true;               // CSV logs in the Common Files folder

//+------------------------------------------------------------------+
//| Trade context: the single pending order or position (spec s.5)   |
//+------------------------------------------------------------------+
struct BfTradeCtx
  {
   bool              active;
   bool              pending;           // a limit order is in the book
   bool              recovered;         // position found at start-up (no detector setup)
   bool              orphan;            // the detector already finished the setup (a fill raced a cancel)
   bool              cancelWanted;      // a delete failed: retried on the next ticks
   ulong             orderTicket;
   ulong             posId;
   int               id;
   int               dir;
   int               src;
   int               tpMode;            // effective take-profit mode of this trade
   double            P;
   double            SL;
   double            TP1;
   double            TP2;
   double            lots;
   double            planned;           // planned risk, account currency (0 = unknown)
   double            entry;
   datetime          decisionTime;
   datetime          fillTime;
   bool              tp1Done;
   bool              beDone;
   int               tries;
   int               closeFails;
   string            closeReason;
  };

void ResetCtx(BfTradeCtx &x)
  {
   x.active       = false;
   x.pending      = false;
   x.recovered    = false;
   x.orphan       = false;
   x.cancelWanted = false;
   x.orderTicket  = 0;
   x.posId        = 0;
   x.id           = 0;
   x.dir          = 0;
   x.src          = BF_SOURCE_BPR;
   x.tpMode       = BF_TP_TP1_ONLY;
   x.P            = 0.0;
   x.SL           = 0.0;
   x.TP1          = 0.0;
   x.TP2          = 0.0;
   x.lots         = 0.0;
   x.planned      = 0.0;
   x.entry        = 0.0;
   x.decisionTime = 0;
   x.fillTime     = 0;
   x.tp1Done      = false;
   x.beDone       = false;
   x.tries        = 0;
   x.closeFails   = 0;
   x.closeReason  = "";
  }

//+------------------------------------------------------------------+
//| Globals                                                          |
//+------------------------------------------------------------------+
double         g_o[];                   // spec s.2: the EA's own closed-bar arrays, absolute index 0 = first warm-up bar
double         g_h[];
double         g_l[];
double         g_c[];
datetime       g_t[];
int            g_n            = 0;      // number of closed bars stored (indices 0 .. g_n-1)

StateS         g_state;                 // committed engine state (closed bars only)
StateS         g_tmp;                   // throw-away copy for the forming bar (display only)
BfEngineParams g_ep;
BfParams       g_bp;

CBfDetector    g_det;
CBfSession     g_ses;
CBfRisk        g_risk;
CBfTrade       g_trade;
CBfRender      g_render;
CBfLogger      g_log;
BfTradeCtx     g_ctx;

bool           g_ready        = false;  // warm-up done
bool           g_tradeLogic   = true;   // false in IFVG mode: display only (spec s.1)
bool           g_renderOn     = true;   // false in non-visual Strategy Tester runs
datetime       g_lastFormTime = 0;      // forming bar seen at the last processed new bar
int            g_emptyFetch   = 0;
long           g_fxDay        = -1;
string         g_lastEvent    = "";
double         g_sumR         = 0.0;
int            g_nR           = 0;
int            g_warmArmed    = 0;
int            g_warmDone     = 0;

//--- validated copies of the inputs
int            g_len          = 5;
int            g_vis          = 2;
int            g_displBars    = 300;
int            g_fillT        = 90;
int            g_borderT      = 65;
int            g_breakT       = 95;
int            g_offTicks     = 5;
int            g_sweepWin     = 30;
int            g_rangeBars    = 30;
int            g_mssBars      = 20;
int            g_rallyBars    = 10;
int            g_expiryBars   = 60;
int            g_maxHold      = 120;
int            g_maxTradesDay = 0;
int            g_slipTicks    = 1;
int            g_maxSpreadPts = 0;
int            g_devPts       = 30;
int            g_warmBars     = 5000;
int            g_serverOffH   = 0;
double         g_stopMult     = 1.2;
double         g_minRR        = 1.0;
double         g_maxCostR     = 0.15;
double         g_tp1Frac      = 0.5;
double         g_riskPct      = 0.20;
double         g_dayLossPct   = 1.00;
double         g_commSide     = 3.50;

//+------------------------------------------------------------------+
//| Small helpers                                                    |
//+------------------------------------------------------------------+
string TfName(void)
  {
   string tf = EnumToString(_Period);
   if(StringFind(tf, "PERIOD_") == 0)
      tf = StringSubstr(tf, 7);
   return(tf);
  }

string Px(const double v)
  {
   return(DoubleToString(v, _Digits));
  }

string DirText(const int dir)
  {
   return((dir > 0) ? "LONG" : "SHORT");
  }

datetime BarTime(const int idx)
  {
   if(idx >= 0 && idx < g_n)
      return(g_t[idx]);
   return(0);
  }

int ClampWarn(const string name, const int v, const int lo_, const int hi_)
  {
   int r = BfIClamp(v, lo_, hi_);
   if(r != v)
      Print("BprFvgEA: ", name, " = ", v, " clamped to ", r);
   return(r);
  }

//+------------------------------------------------------------------+
//| OnInit: validate / clamp (hard caps: 0.20 %, 1.00 %, 120 min)    |
//+------------------------------------------------------------------+
bool ClampInputs(string &why)
  {
   why = "";
   if(InpRiskPct <= 0.0)
     {
      why = "InpRiskPct must be > 0";
      return(false);
     }
   if(InpDailyLossPct <= 0.0)
     {
      why = "InpDailyLossPct must be > 0";
      return(false);
     }
   if(InpStopZoneMult <= 0.0)
     {
      why = "InpStopZoneMult must be > 0";
      return(false);
     }
   if(InpMaxCostR <= 0.0)
     {
      why = "InpMaxCostR must be > 0";
      return(false);
     }
   g_len          = ClampWarn("InpLength", InpLength, 3, 10);
   g_vis          = ClampWarn("InpVisibleBoxes", InpVisibleBoxes, 1, BF_MAXB);
   g_displBars    = ClampWarn("InpDisplacementBars", InpDisplacementBars, 1, 5000);
   g_fillT        = ClampWarn("InpFillTransp", InpFillTransp, 0, 100);
   g_borderT      = ClampWarn("InpBorderTransp", InpBorderTransp, 0, 100);
   g_breakT       = ClampWarn("InpBreakTransp", InpBreakTransp, 0, 100);
   g_offTicks     = ClampWarn("InpEntryOffsetTicks", InpEntryOffsetTicks, 0, 100000);
   g_sweepWin     = ClampWarn("InpSweepWindow", InpSweepWindow, 1, 100000);
   g_rangeBars    = ClampWarn("InpRangeBars", InpRangeBars, 1, 100000);
   g_mssBars      = ClampWarn("InpMssBars", InpMssBars, 1, 100000);
   g_rallyBars    = ClampWarn("InpRallyBars", InpRallyBars, 0, 100000);
   g_expiryBars   = ClampWarn("InpExpiryBars", InpExpiryBars, 1, 100000);
   g_maxHold      = ClampWarn("InpMaxHoldMin", InpMaxHoldMin, 1, 120);              // hard cap 120 min
   g_maxTradesDay = ClampWarn("InpMaxTradesDay", InpMaxTradesDay, 0, 1000);
   g_slipTicks    = ClampWarn("InpSlippageTicks", InpSlippageTicks, 0, 100000);
   g_maxSpreadPts = ClampWarn("InpMaxSpreadPts", InpMaxSpreadPts, 0, 1000000);
   g_devPts       = ClampWarn("InpDeviationPts", InpDeviationPts, 0, 100000);
   g_warmBars     = ClampWarn("InpWarmupBars", InpWarmupBars, 100, 500000);
   g_serverOffH   = ClampWarn("InpServerOffsetH", InpServerOffsetH, -12, 14);
   g_stopMult     = InpStopZoneMult;
   g_minRR        = MathMax(0.0, InpMinRR);
   g_maxCostR     = InpMaxCostR;
   g_tp1Frac      = InpTp1Fraction;
   if(g_tp1Frac <= 0.0 || g_tp1Frac > 1.0)
     {
      g_tp1Frac = MathMin(1.0, MathMax(0.01, g_tp1Frac));
      Print("BprFvgEA: InpTp1Fraction clamped to ", DoubleToString(g_tp1Frac, 2));
     }
   g_riskPct = MathMin(InpRiskPct, 0.20);                                          // hard cap 0.20 %
   if(g_riskPct != InpRiskPct)
      Print("BprFvgEA: InpRiskPct capped at 0.20 (project hard limit)");
   g_dayLossPct = MathMin(InpDailyLossPct, 1.00);                                  // hard cap 1.00 %
   if(g_dayLossPct != InpDailyLossPct)
      Print("BprFvgEA: InpDailyLossPct capped at 1.00 (project hard limit)");
   g_commSide = MathMax(0.0, InpCommissionPerLotSide);
   if(g_vis >= 12)
      Print("BprFvgEA: WARNING InpVisibleBoxes >= 12: entries at index 11+ are never broken (LuxAlgo QUIRK 11)");
   return(true);
  }

//--- engine and detector parameters from the validated inputs (spec s.1, s.2)
void BuildParams(void)
  {
   g_ep.length    = g_len;
   g_ep.visBoxes  = g_vis;
   g_ep.fvgMode   = (int)InpFvgType;
   g_ep.showFVG   = true;                    // the engine always computes FVGs ...
   g_ep.bpr       = true;                    // ... and BPRs (setups need them); InpShowBPR is display only
   g_ep.fvgStyled = !InpShowBPR;             // FVG boxes styled like the indicator with BPR off (display only)

   BfDefaultParams(g_bp);
   g_bp.length               = g_len;
   g_bp.visBoxes             = g_vis;
   g_bp.fvgMode              = (int)InpFvgType;
   g_bp.source               = (int)InpSetupSource;
   g_bp.direction            = (int)InpDirection;
   g_bp.entryMode            = (int)InpEntryMode;
   g_bp.entryOffsetTicks     = g_offTicks;
   g_bp.useSweep             = InpUseSweep;
   g_bp.sweepWindow          = g_sweepWin;
   g_bp.rangeBars            = g_rangeBars;
   g_bp.useMss               = InpUseMss;
   g_bp.mssBars              = g_mssBars;
   g_bp.rallyBars            = g_rallyBars;
   g_bp.expiryBars           = g_expiryBars;
   g_bp.stopZoneMult         = g_stopMult;
   g_bp.minRR                = g_minRR;
   g_bp.maxCostR             = g_maxCostR;
   g_bp.tpMode               = (int)InpTpMode;
   g_bp.tp1Fraction          = g_tp1Frac;
   g_bp.breakEven            = InpBreakEven;
   g_bp.maxHoldMin           = g_maxHold;
   g_bp.useSession           = InpUseSession;
   g_bp.commissionPerLotSide = g_commSide;
   g_bp.slippageTicks        = (double)g_slipTicks;
   g_bp.tickSize             = 0.0;          // set from the symbol by SetupSymbolParams()
   g_bp.commPrice            = 0.0;
  }

//--- tick size and comm_price from the symbol; false while the symbol data is not ready
bool SetupSymbolParams(void)
  {
   double tick = g_trade.TickSize();
   if(tick <= 0.0)
      return(false);
   if(g_risk.ValuePerPriceUnit() <= 0.0)
      return(false);
   g_bp.tickSize  = tick;
   g_bp.digits    = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   g_bp.commPrice = g_risk.CommPrice();       // round-trip commission per lot / value of 1.0 price move per lot
   return(true);
  }

//+------------------------------------------------------------------+
//| Bar arrays (spec s.2)                                            |
//+------------------------------------------------------------------+
bool EnsureCapacity(const int need)
  {
   int cur = ArraySize(g_t);
   int ns;
   if(cur >= need)
      return(true);
   ns = BfIMax(need, cur + cur / 2 + 1024);
   if(ArrayResize(g_o, ns) < ns || ArrayResize(g_h, ns) < ns || ArrayResize(g_l, ns) < ns ||
      ArrayResize(g_c, ns) < ns || ArrayResize(g_t, ns) < ns)
     {
      Print("[BFEA ERROR] cannot resize the bar arrays to ", ns);
      return(false);
     }
   return(true);
  }

bool AppendBar(const MqlRates &r)
  {
   if(!EnsureCapacity(g_n + 2))
      return(false);
   g_o[g_n] = r.open;
   g_h[g_n] = r.high;
   g_l[g_n] = r.low;
   g_c[g_n] = r.close;
   g_t[g_n] = r.time;
   g_n++;
   return(true);
  }

//+------------------------------------------------------------------+
//| Logging helpers (spec s.7)                                       |
//+------------------------------------------------------------------+
void EventToSetup(const BfEvent &e, BfSetup &s)
  {
   BfClearSetup(s);
   s.id          = e.id;
   s.src         = e.src;
   s.dir         = e.dir;
   s.status      = e.status;
   s.reason      = e.reason;
   s.ordKind     = e.ordKind;
   s.created     = e.created;
   s.B           = e.B;
   s.T           = e.T;
   s.h           = e.h;
   s.sweepBar    = e.sweepBar;
   s.M           = e.M;
   s.mssDone     = e.mssDone;
   s.mssBar      = e.mssBar;
   s.X           = e.X;
   s.O           = e.O;
   s.P           = e.P;
   s.SL          = e.SL;
   s.TP1         = e.TP1;
   s.TP2         = e.TP2;
   s.decisionBar = e.decisionBar;
  }

// BFEA_setups row: id,source,dir,created_time,B,T,h,sweep_bar_time,M,mss_time,status,reason,P,SL,TP1,TP2,decision_time
// Times are server time, bar-open labelled.
string SetupCsv(const BfSetup &s)
  {
   bool   ord  = (s.ordKind != BF_ORD_NONE);
   string line = IntegerToString(s.id) + "," + BfSourceName(s.src) + "," + IntegerToString(s.dir) + "," +
                 CBfLogger::Ts(BarTime(s.created)) + "," + Px(s.B) + "," + Px(s.T) + "," +
                 DoubleToString(s.h, _Digits + 3) + "," + CBfLogger::Ts(BarTime(s.sweepBar)) + "," +
                 ((s.M != 0.0) ? Px(s.M) : "") + "," + (s.mssDone ? CBfLogger::Ts(BarTime(s.mssBar)) : "") + "," +
                 BfStatusName(s.status) + "," + BfReasonName(s.reason) + "," +
                 (ord ? Px(s.P) : "") + "," + (ord ? Px(s.SL) : "") + "," + (ord ? Px(s.TP1) : "") + "," +
                 (ord ? Px(s.TP2) : "") + "," + (ord ? CBfLogger::Ts(BarTime(s.decisionBar)) : "");
   return(line);
  }

// One Experts-log line per setup state change (spec s.7)
string EventText(const BfEvent &e)
  {
   string s = "#" + IntegerToString(e.id) + " " + BfSourceName(e.src) + " " + DirText(e.dir) + " " + BfEventName(e.ev);
   if(e.reason != BF_R_NONE)
      s = s + "(" + BfReasonName(e.reason) + ")";
   if(e.ev == BF_EV_ARMED)
      s = s + " B=" + Px(e.B) + " T=" + Px(e.T) + " h=" + DoubleToString(e.h, _Digits + 2) + " sweep=" +
          CBfLogger::Ts(BarTime(e.sweepBar)) + " M=" + Px(e.M) + " X=" + Px(e.X) + " O=" + Px(e.O);
   else
      if(e.ev == BF_EV_MSS)
         s = s + " M=" + Px(e.M) + " shift close at " + CBfLogger::Ts(BarTime(e.mssBar));
      else
         if(e.ordKind != BF_ORD_NONE)
            s = s + " P=" + Px(e.P) + " SL=" + Px(e.SL) + " TP1=" + Px(e.TP1) + " TP2=" + Px(e.TP2);
   s = s + " | bar " + CBfLogger::Ts(BarTime(e.n));
   return(s);
  }

//+------------------------------------------------------------------+
//| Trade overlays (spec s.8)                                        |
//+------------------------------------------------------------------+
void DrawTradeBox(const BfEvent &e)
  {
   double   finalTp;
   bool     tp1Line;
   datetime t1;
   datetime t2;
   string   note = "";
   if(!g_renderOn || !InpShowTradeBoxes)
      return;
   finalTp = e.TP2;
   if((int)InpTpMode == BF_TP_TP1_ONLY || e.TP2 == e.TP1)
      finalTp = e.TP1;
   tp1Line = ((int)InpTpMode == BF_TP_TP1_TP2 && e.TP2 != e.TP1);
   t1 = BarTime(e.n);
   t2 = g_render.IdxToTime(e.n + BF_TB_BARS, g_n, g_t, g_lastFormTime);
   if(!g_trade.tradingAllowed)
      note = " (log-only)";
   g_render.TradeBox(e.id, e.dir, t1, t2, e.P, e.SL, e.TP1, finalTp, tp1Line, note);
  }

//+------------------------------------------------------------------+
//| Detector events -> logs and overlays                             |
//+------------------------------------------------------------------+
void HandleEvents(void)
  {
   int     i;
   int     n = g_det.EventCount();
   BfEvent e;
   BfSetup s;
   for(i = 0; i < n; i++)
     {
      if(!g_det.GetEvent(i, e))
         continue;
      g_log.Info(EventText(e));
      g_lastEvent = "#" + IntegerToString(e.id) + " " + BfEventName(e.ev) +
                    ((e.reason != BF_R_NONE) ? "(" + BfReasonName(e.reason) + ")" : "") + " " +
                    CBfLogger::Ts(BarTime(e.n));
      if(e.ev == BF_EV_PLACE_LIMIT || e.ev == BF_EV_MARKET)
         DrawTradeBox(e);
      else
         if(e.ev == BF_EV_CANCEL)
           {
            if(g_renderOn)
               g_render.TradeBoxGrey(e.id);
           }
         else
            if(e.ev == BF_EV_DONE)
              {
               // a log-only (real account) signal keeps its colours; anything else that was ordered turns grey
               if(g_renderOn && e.ordKind != BF_ORD_NONE && !(e.reason == BF_R_ORDER_FAILED && !g_trade.tradingAllowed))
                  g_render.TradeBoxGrey(e.id);
               EventToSetup(e, s);
               g_log.SetupRow(SetupCsv(s));
              }
     }
   if(g_det.LostEvents() > 0 && n >= BF_MAX_EVENTS)
      g_log.Error("event buffer full: " + IntegerToString(g_det.LostEvents()) + " records lost so far");
   g_det.ClearEvents();
  }

// warm-up: events are counted, not logged (no warm-up setup is ever traded)
void CountWarmEvents(void)
  {
   int     i;
   int     n = g_det.EventCount();
   BfEvent e;
   for(i = 0; i < n; i++)
     {
      if(!g_det.GetEvent(i, e))
         continue;
      if(e.ev == BF_EV_ARMED)
         g_warmArmed++;
      if(e.ev == BF_EV_DONE)
         g_warmDone++;
     }
   g_det.ClearEvents();
  }

//+------------------------------------------------------------------+
//| Execution (spec s.5)                                             |
//+------------------------------------------------------------------+
// A limit (or market) order became a position: record it and tell the detector.
void OnFilled(const ulong ptk)
  {
   if(!PositionSelectByTicket(ptk))
      return;
   g_ctx.pending    = false;
   g_ctx.posId      = (ulong)PositionGetInteger(POSITION_IDENTIFIER);
   g_ctx.fillTime   = (datetime)PositionGetInteger(POSITION_TIME);
   g_ctx.entry      = PositionGetDouble(POSITION_PRICE_OPEN);
   g_ctx.lots       = PositionGetDouble(POSITION_VOLUME);
   g_ctx.tries      = 0;
   if(!g_ctx.orphan && !g_ctx.recovered)
      g_det.NotifyFilled(g_ctx.id);
   g_risk.OnTradeEvent(g_ses);
   g_lastEvent = "#" + IntegerToString(g_ctx.id) + " FILLED " + CBfLogger::Ts(g_ctx.fillTime);
   g_log.Info("#" + IntegerToString(g_ctx.id) + " " + DirText(g_ctx.dir) + " FILLED " + DoubleToString(g_ctx.lots, 2) +
              " lots at " + Px(g_ctx.entry) + " SL=" + Px(g_ctx.SL) + " TP1=" + Px(g_ctx.TP1) + " TP2=" + Px(g_ctx.TP2) +
              " | " + CBfLogger::Ts(g_ctx.fillTime));
  }

void ExecCancel(const BfIntent &it)
  {
   ulong ptk;
   if(!g_ctx.active || !g_ctx.pending || g_ctx.id != it.id)
      return;
   if(g_trade.DeleteOrder(g_ctx.orderTicket))
     {
      g_log.Info("#" + IntegerToString(it.id) + " pending order deleted (" + BfReasonName(it.reason) + ")");
      ResetCtx(g_ctx);
      return;
     }
   // the delete failed: the limit may have just been filled
   if(g_trade.SelectPosition(ptk))
     {
      g_ctx.orphan = true;                       // the detector has already finished this setup
      OnFilled(ptk);
      g_log.Error("#" + IntegerToString(it.id) + " cancel (" + BfReasonName(it.reason) +
                  ") came too late: the limit was filled; the position is managed (time stop, rollover, SL/TP)");
      return;
     }
   if(!OrderSelect(g_ctx.orderTicket))
     {
      ResetCtx(g_ctx);                           // the order is already gone
      return;
     }
   g_ctx.orphan       = true;
   g_ctx.cancelWanted = true;
   g_log.Error("#" + IntegerToString(it.id) + " could not delete the pending order: " + g_trade.lastError +
               " (retried on the next ticks)");
  }

void ExecOrder(const BfIntent &it, const bool market)
  {
   ulong    tk;
   ulong    ticket  = 0;
   MqlTick  q;
   double   planned = 0.0;
   double   lots    = 0.0;
   double   P        = 0.0;
   double   SL       = 0.0;
   double   TP1      = 0.0;
   double   TP2      = 0.0;
   double   serverTp = 0.0;
   double   entryRef = 0.0;
   double   tick    = g_bp.tickSize;
   int      effMode = (int)InpTpMode;
   string   why     = "";
   string   cmt;
   string   tag     = "#" + IntegerToString(it.id) + " ";
   bool     ok      = false;
   datetime expiry  = 0;

   ZeroMemory(q);
   if(!g_trade.tradingAllowed)
     {
      // REAL account: log-only (spec "Hard rules"). The setup ends DONE(ORDER_FAILED); the overlay keeps its colours.
      g_log.Info(tag + "LOG-ONLY (" + g_trade.modeNote + "): " + (market ? "MARKET" : "PLACE_LIMIT") + " " +
                 DirText(it.dir) + " P=" + Px(it.P) + " SL=" + Px(it.SL) + " TP1=" + Px(it.TP1) + " TP2=" + Px(it.TP2) +
                 " not sent");
      g_det.NotifyCancelled(it.id, BF_R_ORDER_FAILED);
      return;
     }

   P   = g_trade.NormalizePrice(it.P);
   SL  = g_trade.NormalizePrice(it.SL);
   TP1 = g_trade.NormalizePrice(it.TP1);
   TP2 = g_trade.NormalizePrice(it.TP2);
   if(effMode == BF_TP_TP1_TP2 && MathAbs(TP2 - TP1) < tick * 0.5)
      effMode = BF_TP_TP1_ONLY;                  // TP2 not beyond TP1: TP1 only (spec s.4 step 5)
   serverTp = (effMode == BF_TP_TP1_ONLY) ? TP1 : TP2;   // TP1_TP2: TP2 on the server, TP1 virtual (spec s.5)

   if(g_ctx.active || g_trade.SelectPosition(tk) || g_trade.SelectPendingOrder(tk))
      why = "slot busy";
   else
      if(g_trade.Breaker())
         why = "order-error breaker (resets at the next FX day)";
      else
         if(!SymbolInfoTick(_Symbol, q))
            why = "no tick";
   if(why == "")
     {
      entryRef = market ? ((it.dir > 0) ? q.ask : q.bid) : P;
      // spec s.6: lots from |P - SL| + slippage, never rounded up to the minimum volume
      lots = g_risk.SizeLots(MathAbs(entryRef - SL) + (double)g_slipTicks * tick, planned);
      if(lots <= 0.0)
        {
         g_log.Info(tag + "size below the minimum volume: no order");
         g_det.NotifyCancelled(it.id, BF_R_SIZE_BELOW_MIN);
         return;
        }
      if(!g_risk.CheckNewTrade(planned))
         why = "daily-loss budget (realised loss today + planned risk > limit)";
      else
         if(market)
           {
            // a buy's SL / TP are checked against the bid, a sell's against the ask
            if(!g_trade.StopsOk(it.dir, (it.dir > 0) ? q.bid : q.ask, SL, serverTp))
               why = "SL/TP versus the market (stops level, or price already beyond a level)";
           }
         else
           {
            if(!g_trade.PendingPriceOk(it.dir, P))
               why = "limit price versus the market (wrong side or inside the stops level)";
            else
               if(!g_trade.StopsOk(it.dir, P, SL, serverTp))
                  why = "SL/TP versus the limit price (stops level)";
           }
      if(why == "" && !g_trade.MarginOk(it.dir, lots, entryRef))
         why = "not enough free margin";
     }
   if(why != "")
     {
      g_log.Info(tag + "order not sent: " + why);
      g_det.NotifyCancelled(it.id, BF_R_ORDER_FAILED);
      return;
     }

   cmt = "BF|" + IntegerToString(it.id) + "|" + DoubleToString(TP1, _Digits);   // read back after a restart
   if(market)
      ok = g_trade.OpenMarket(it.dir, lots, SL, serverTp, cmt);
   else
     {
      // safety net only: the detector cancels the order through its own intents (spec s.5)
      expiry = (datetime)((long)TimeCurrent() + (long)(g_expiryBars + 3) * (long)PeriodSeconds());
      ok = g_trade.PlaceLimit(it.dir, lots, P, SL, serverTp, expiry, cmt, ticket);
     }
   if(!ok)
     {
      g_log.Error(tag + "order failed: " + g_trade.lastError);
      g_det.NotifyCancelled(it.id, BF_R_ORDER_FAILED);
      return;
     }

   ResetCtx(g_ctx);
   g_ctx.active       = true;
   g_ctx.pending      = !market;
   g_ctx.orderTicket  = ticket;
   g_ctx.id           = it.id;
   g_ctx.dir          = it.dir;
   g_ctx.src          = it.src;
   g_ctx.tpMode       = effMode;
   g_ctx.P            = P;
   g_ctx.SL           = SL;
   g_ctx.TP1          = TP1;
   g_ctx.TP2          = TP2;
   g_ctx.lots         = lots;
   g_ctx.planned      = planned;
   g_ctx.entry        = entryRef;
   g_ctx.decisionTime = TimeCurrent();
   g_log.Info(tag + (market ? "MARKET " : "LIMIT ") + DirText(it.dir) + " sent: " + DoubleToString(lots, 2) +
              " lots P=" + Px(market ? entryRef : P) + " SL=" + Px(SL) + " server TP=" + Px(serverTp) +
              ((effMode == BF_TP_TP1_TP2) ? " virtual TP1=" + Px(TP1) : "") + " planned risk " +
              DoubleToString(planned, 2) + " " + AccountInfoString(ACCOUNT_CURRENCY));
   if(market)
     {
      if(g_trade.SelectPosition(tk))
         OnFilled(tk);
      else
        {
         // position not visible yet: identify it through the deal
         ulong deal = g_trade.LastDeal();
         g_ctx.pending  = false;
         g_ctx.fillTime = TimeCurrent();
         if(deal > 0 && HistoryDealSelect(deal))
            g_ctx.posId = (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID);
         g_det.NotifyFilled(it.id);
         g_risk.OnTradeEvent(g_ses);
        }
     }
  }

void ExecuteIntents(void)
  {
   int      i;
   int      n = g_det.IntentCount();
   BfIntent it;
   for(i = 0; i < n; i++)
     {
      if(!g_det.GetIntent(i, it))
         continue;
      if(it.type == BF_EV_CANCEL)
         ExecCancel(it);
      else
         if(it.type == BF_EV_PLACE_LIMIT)
            ExecOrder(it, false);
         else
            if(it.type == BF_EV_MARKET)
               ExecOrder(it, true);
     }
   g_det.ClearIntents();
   HandleEvents();                               // DONE records produced by NotifyCancelled
  }

//+------------------------------------------------------------------+
//| Closed trade -> trades CSV, detector, risk (spec s.5, s.7)       |
//+------------------------------------------------------------------+
string DealReasonText(const long r)
  {
   if(r == (long)DEAL_REASON_SL)
      return(g_ctx.beDone ? "BE_SL" : "SL");
   if(r == (long)DEAL_REASON_TP)
      return("TP");
   if(r == (long)DEAL_REASON_EXPERT)
      return((g_ctx.closeReason != "") ? g_ctx.closeReason : "EA");
   if(r == (long)DEAL_REASON_SO)
      return("STOP_OUT");
   if(r == (long)DEAL_REASON_CLIENT || r == (long)DEAL_REASON_MOBILE || r == (long)DEAL_REASON_WEB)
      return("MANUAL");
   return("OTHER");
  }

// true when the closed position was found in the history and logged
bool FinishClosedTrade(void)
  {
   int      i;
   int      total;
   ulong    d;
   long     ent;
   double   pnl      = 0.0;
   double   vIn      = 0.0;
   double   vOut     = 0.0;
   double   pxIn     = 0.0;
   double   pxOut    = 0.0;
   double   vol      = 0.0;
   double   px       = 0.0;
   double   R        = 0.0;
   datetime tIn      = 0;
   datetime tOut     = 0;
   bool     anyOut   = false;
   string   reasonTx = "";
   string   line;
   BfSetup  s;

   if(g_ctx.posId == 0)
      return(false);
   if(!HistorySelectByPosition((long)g_ctx.posId))
      return(false);
   total = HistoryDealsTotal();
   for(i = 0; i < total; i++)
     {
      d = HistoryDealGetTicket(i);
      if(d == 0)
         continue;
      pnl += HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_COMMISSION) +
             HistoryDealGetDouble(d, DEAL_SWAP) + HistoryDealGetDouble(d, DEAL_FEE);
      ent = HistoryDealGetInteger(d, DEAL_ENTRY);
      vol = HistoryDealGetDouble(d, DEAL_VOLUME);
      px  = HistoryDealGetDouble(d, DEAL_PRICE);
      if(ent == (long)DEAL_ENTRY_IN)
        {
         vIn  += vol;
         pxIn += px * vol;
         if(tIn == 0)
            tIn = (datetime)HistoryDealGetInteger(d, DEAL_TIME);
        }
      else
         if(ent == (long)DEAL_ENTRY_OUT || ent == (long)DEAL_ENTRY_OUT_BY || ent == (long)DEAL_ENTRY_INOUT)
           {
            anyOut   = true;
            vOut    += vol;
            pxOut   += px * vol;
            tOut     = (datetime)HistoryDealGetInteger(d, DEAL_TIME);
            reasonTx = DealReasonText(HistoryDealGetInteger(d, DEAL_REASON));
           }
     }
   if(!anyOut)
      return(false);
   if(g_ctx.tp1Done && g_ctx.tpMode == BF_TP_TP1_TP2 && reasonTx != "TP1")
      reasonTx = "TP1+" + reasonTx;
   if(g_ctx.planned > 0.0)
      R = pnl / g_ctx.planned;

   // BFEA_trades row: id,dir,entry_time,entry,lots,SL,TP1,TP2,exit_time,exit,exit_reason,pnl_usd,R,planned_risk_usd
   line = IntegerToString(g_ctx.id) + "," + IntegerToString(g_ctx.dir) + "," + CBfLogger::Ts(tIn) + "," +
          ((vIn > 0.0) ? DoubleToString(pxIn / vIn, _Digits + 2) : "") + "," + DoubleToString(vIn, 2) + "," +
          Px(g_ctx.SL) + "," + Px(g_ctx.TP1) + "," + Px(g_ctx.TP2) + "," + CBfLogger::Ts(tOut) + "," +
          ((vOut > 0.0) ? DoubleToString(pxOut / vOut, _Digits + 2) : "") + "," + reasonTx + "," +
          DoubleToString(pnl, 2) + "," + ((g_ctx.planned > 0.0) ? DoubleToString(R, 3) : "") + "," +
          ((g_ctx.planned > 0.0) ? DoubleToString(g_ctx.planned, 2) : "");
   g_log.TradeRow(line);
   g_log.Info("#" + IntegerToString(g_ctx.id) + " " + DirText(g_ctx.dir) + " CLOSED " + reasonTx + " pnl " +
              DoubleToString(pnl, 2) + " " + AccountInfoString(ACCOUNT_CURRENCY) +
              ((g_ctx.planned > 0.0) ? " R=" + DoubleToString(R, 2) : "") + " | " + CBfLogger::Ts(tOut));
   g_lastEvent = "#" + IntegerToString(g_ctx.id) + " CLOSED " + reasonTx + " " + CBfLogger::Ts(tOut);
   if(g_ctx.planned > 0.0 && !g_ctx.recovered)
     {
      g_sumR += R;
      g_nR++;
     }
   if(!g_ctx.recovered && !g_ctx.orphan)
     {
      if(g_det.GetSetup(g_ctx.id, s))
        {
         s.status = BF_ST_CLOSED;
         g_log.SetupRow(SetupCsv(s));
        }
      g_det.NotifyClosed(g_ctx.id);
     }
   g_risk.OnTradeEvent(g_ses);
   ResetCtx(g_ctx);
   return(true);
  }

//+------------------------------------------------------------------+
//| Every tick: fills and closures -> detector (spec s.4, s.5)       |
//+------------------------------------------------------------------+
void SyncTrade(void)
  {
   ulong ptk;
   long  state = -1;
   long  posId = 0;
   int   reason;
   if(!g_ctx.active)
      return;
   if(g_ctx.pending)
     {
      if(g_trade.SelectPosition(ptk))
        {
         OnFilled(ptk);
         // a partly filled limit may still be in the book: remove the rest (one position per EA)
         if(OrderSelect(g_ctx.orderTicket))
            g_trade.DeleteOrder(g_ctx.orderTicket);
         return;
        }
      if(OrderSelect(g_ctx.orderTicket))
        {
         if(g_ctx.cancelWanted && g_trade.DeleteOrder(g_ctx.orderTicket))
           {
            g_log.Info("#" + IntegerToString(g_ctx.id) + " pending order deleted (retry)");
            ResetCtx(g_ctx);
           }
         return;                                 // still pending
        }
      // the order left the book and no position is open: filled and already closed, expired, or cancelled
      if(HistorySelect((datetime)((long)g_ctx.decisionTime - 86400), (datetime)((long)TimeCurrent() + 3600)) &&
         HistoryOrderSelect(g_ctx.orderTicket))
        {
         state = HistoryOrderGetInteger(g_ctx.orderTicket, ORDER_STATE);
         posId = HistoryOrderGetInteger(g_ctx.orderTicket, ORDER_POSITION_ID);
        }
      if(state == (long)ORDER_STATE_FILLED || state == (long)ORDER_STATE_PARTIAL)
        {
         g_ctx.pending  = false;
         g_ctx.posId    = (ulong)posId;
         g_ctx.fillTime = TimeCurrent();
         g_ctx.tries    = 0;
         if(!g_ctx.orphan)
            g_det.NotifyFilled(g_ctx.id);
         g_log.Info("#" + IntegerToString(g_ctx.id) + " FILLED and already closed between two ticks");
         FinishClosedTrade();                    // retried below on the next ticks if the deals are not there yet
         return;
        }
      if(state < 0)
        {
         g_ctx.tries++;
         if(g_ctx.tries < 20)
            return;                              // history not ready yet
        }
      reason = (state == (long)ORDER_STATE_EXPIRED) ? BF_R_EXPIRED : BF_R_ORDER_FAILED;
      g_log.Info("#" + IntegerToString(g_ctx.id) + " pending order left the book without a fill (" +
                 BfReasonName(reason) + ")");
      if(!g_ctx.orphan)
        {
         g_det.NotifyCancelled(g_ctx.id, reason);
         HandleEvents();
        }
      ResetCtx(g_ctx);
      return;
     }
   if(g_trade.SelectPosition(ptk))
      return;                                    // still open
   if(FinishClosedTrade())
      return;
   g_ctx.tries++;
   if(g_ctx.tries > 50)
     {
      g_log.Error("#" + IntegerToString(g_ctx.id) + " closed position not found in the history; context reset");
      if(!g_ctx.recovered && !g_ctx.orphan)
         g_det.NotifyClosed(g_ctx.id);
      g_risk.OnTradeEvent(g_ses);
      ResetCtx(g_ctx);
     }
  }

//+------------------------------------------------------------------+
//| Every tick: position management (spec s.5)                       |
//+------------------------------------------------------------------+
void CloseAll(const ulong tk, const string why)
  {
   g_ctx.closeReason = why;
   if(g_trade.ClosePosition(tk))
     {
      g_log.Info("#" + IntegerToString(g_ctx.id) + " close at market: " + why);
      return;
     }
   g_ctx.closeFails++;
   if(g_ctx.closeFails <= 3)
      g_log.Error("#" + IntegerToString(g_ctx.id) + " close (" + why + ") failed: " + g_trade.lastError + " (retried)");
  }

void ManagePosition(void)
  {
   ulong    tk;
   MqlTick  q;
   datetime now;
   double   vol   = 0.0;
   double   part  = 0.0;
   double   rest  = 0.0;
   double   vmin  = 0.0;
   double   be    = 0.0;
   double   curSL = 0.0;
   double   curTP = 0.0;
   bool     hit   = false;
   if(!g_ctx.active || g_ctx.pending)
      return;
   if(!g_trade.tradingAllowed)
      return;                                    // log-only: never touch anything
   if(!g_trade.SelectPosition(tk))
      return;
   if(!SymbolInfoTick(_Symbol, q))
      return;
   now = TimeCurrent();

   //--- time stop: close when now >= fill_time + max_hold_min (<= 120)
   if((long)now >= (long)g_ctx.fillTime + (long)g_maxHold * 60)
     {
      CloseAll(tk, "TIME");
      return;
     }
   //--- before the rollover: flat at 16:44 New York
   if(g_ses.FlatDue(g_ctx.fillTime, now))
     {
      CloseAll(tk, "ROLLOVER");
      return;
     }
   //--- TP1_TP2: virtual TP1. Long: bid >= TP1; short: ask <= TP1 (an ask level).
   if(g_ctx.tpMode == BF_TP_TP1_TP2 && !g_ctx.tp1Done && g_ctx.TP1 > 0.0)
     {
      hit = (g_ctx.dir > 0) ? (q.bid >= g_ctx.TP1) : (q.ask <= g_ctx.TP1);
      if(hit)
        {
         if(!PositionSelectByTicket(tk))
            return;
         vol  = PositionGetDouble(POSITION_VOLUME);
         part = g_trade.FloorVolume(vol * g_tp1Frac);       // rounded DOWN to the volume step
         rest = vol - part;
         vmin = g_trade.MinVolume();
         if(part < vmin - 1e-12 || rest < vmin - 1e-12)
           {
            g_ctx.tp1Done = true;
            CloseAll(tk, "TP1");                             // cannot split: close everything at TP1
            return;
           }
         if(g_trade.ClosePartial(tk, part))
           {
            g_ctx.tp1Done = true;
            g_log.Info("#" + IntegerToString(g_ctx.id) + " TP1 reached: closed " + DoubleToString(part, 2) + " of " +
                       DoubleToString(vol, 2) + " lots");
            g_lastEvent = "#" + IntegerToString(g_ctx.id) + " TP1 partial " + CBfLogger::Ts(now);
           }
         return;                                             // break-even from the next tick
        }
     }
   //--- break-even after TP1: stop to entry +/- comm_price in the profit direction
   if(g_ctx.tp1Done && InpBreakEven && !g_ctx.beDone)
     {
      if(!PositionSelectByTicket(tk))
         return;
      curSL = PositionGetDouble(POSITION_SL);
      curTP = PositionGetDouble(POSITION_TP);
      be    = g_trade.NormalizePrice((g_ctx.dir > 0) ? g_ctx.entry + g_bp.commPrice : g_ctx.entry - g_bp.commPrice);
      if(curSL > 0.0 && ((g_ctx.dir > 0 && curSL >= be) || (g_ctx.dir < 0 && curSL <= be)))
        {
         g_ctx.beDone = true;                                // already at or beyond break-even
         return;
        }
      if((g_ctx.dir > 0 && q.bid <= be) || (g_ctx.dir < 0 && q.ask >= be))
        {
         g_ctx.beDone = true;
         CloseAll(tk, "BE");                                 // the market is already through the break-even stop
         return;
        }
      if(g_trade.ModifySlOk(g_ctx.dir, be) && g_trade.ModifyStops(tk, be, curTP))
        {
         g_ctx.beDone = true;
         g_log.Info("#" + IntegerToString(g_ctx.id) + " stop moved to break-even " + Px(be));
        }
     }
  }

//+------------------------------------------------------------------+
//| Environment of the detector (spec s.4 step 5)                    |
//+------------------------------------------------------------------+
void BuildEnv(BfEnv &env, const bool warm, const datetime nextOpen, const bool stale)
  {
   MqlTick q;
   ulong   tk;
   BfClearEnv(env);
   if(warm)
      return;                                    // warm-up: no decision is possible (all flags false)
   if(SymbolInfoTick(_Symbol, q) && q.ask > 0.0 && q.bid > 0.0)
      env.sp = q.ask - q.bid;                    // spread at the decision moment (first tick of bar u+1)
   env.slotFree       = (!g_ctx.active && !g_trade.SelectPosition(tk) && !g_trade.SelectPendingOrder(tk));
   env.sessionEntryOk = g_ses.EntryOk(nextOpen);
   env.sessionCancel  = g_ses.SessionCancel(nextOpen);
   env.riskOk         = (g_risk.RiskOk() && !g_trade.Breaker());
   // a catch-up bar (not the last closed bar) has no decision tick: its spread is unknown -> no entry on it
   env.spreadOk       = (!stale && (g_maxSpreadPts <= 0 || env.sp <= (double)g_maxSpreadPts * _Point + 1e-12));
  }

//+------------------------------------------------------------------+
//| Displacement markers (display only)                              |
//+------------------------------------------------------------------+
void DrawDisplBar(const int k)
  {
   bool up;
   bool dn;
   if(!g_renderOn || !InpShowDisplacement || k < 0 || k >= g_n)
      return;
   up = DispUpAt(g_ep, k, g_o, g_h, g_l, g_c);
   dn = DispDnAt(g_ep, k, g_o, g_h, g_l, g_c);
   g_render.DisplMark(IntegerToString((long)g_t[k]), up, dn, g_t[k], g_l[k], g_h[k]);
  }

//+------------------------------------------------------------------+
//| One closed bar u: engine, detector, logs, intents (spec s.4)     |
//+------------------------------------------------------------------+
void ProcessClosed(const int u, const bool warm, const datetime nextOpen, const bool stale)
  {
   BfEngineEvents ev;
   BfEnv          env;
   //--- step 1: engine (Historical mode, closed bars only)
   ProcessBar(g_ep, g_state, u, g_o, g_h, g_l, g_c, ev);
   if(!warm)
     {
      DrawDisplBar(u);
      if(g_renderOn && InpShowDisplacement && u - g_displBars >= 0)
         g_render.DisplDelete(IntegerToString((long)g_t[u - g_displBars]));
     }
   if(!g_tradeLogic)
      return;                                    // IFVG: display only
   //--- steps 2-5: detector
   BuildEnv(env, warm, nextOpen, stale);
   g_det.OnBarClosed(u, g_o, g_h, g_l, g_c, g_state, ev, env);
   if(warm)
     {
      CountWarmEvents();
      g_det.ClearIntents();
      return;
     }
   HandleEvents();
   ExecuteIntents();
  }

//+------------------------------------------------------------------+
//| Rendering (spec s.8)                                             |
//+------------------------------------------------------------------+
void RenderNow(void)
  {
   MqlRates       fr[];
   datetime       ft;
   BfEngineEvents ev;
   bool           up;
   bool           dn;
   if(!g_renderOn || g_n <= 0)
      return;
   ft = iTime(_Symbol, _Period, 0);
   if(InpLiveBar && ft > g_t[g_n - 1])
     {
      // forming bar on a throw-away copy of the committed state (like the indicator); never used for decisions
      ArraySetAsSeries(fr, false);
      if(CopyRates(_Symbol, _Period, 0, 1, fr) == 1 && fr[0].time == ft && EnsureCapacity(g_n + 2))
        {
         g_o[g_n] = fr[0].open;
         g_h[g_n] = fr[0].high;
         g_l[g_n] = fr[0].low;
         g_c[g_n] = fr[0].close;
         g_t[g_n] = fr[0].time;
         CopyState(g_tmp, g_state);
         ProcessBar(g_ep, g_tmp, g_n, g_o, g_h, g_l, g_c, ev);
         g_render.RenderState(g_tmp, g_n, g_t, ft);
         if(InpShowDisplacement)
           {
            up = DispUpAt(g_ep, g_n, g_o, g_h, g_l, g_c);
            dn = DispDnAt(g_ep, g_n, g_o, g_h, g_l, g_c);
            g_render.DisplMark("F", up, dn, ft, fr[0].low, fr[0].high);
           }
         g_render.Redraw();
         return;
        }
     }
   g_render.RenderState(g_state, g_n, g_t, ft);
   if(InpShowDisplacement)
      g_render.DisplMark("F", false, false, ft, 0.0, 0.0);
   g_render.Redraw();
  }

string CtxText(void)
  {
   if(!g_ctx.active)
      return("none");
   if(g_ctx.pending)
      return("pending " + ((g_ctx.dir > 0) ? "BUY" : "SELL") + " LIMIT #" + IntegerToString(g_ctx.id) + " @" +
             Px(g_ctx.P) + " SL " + Px(g_ctx.SL));
   return(DirText(g_ctx.dir) + " #" + IntegerToString(g_ctx.id) + " " + DoubleToString(g_ctx.lots, 2) + " lots from " +
          Px(g_ctx.entry) + " SL " + Px(g_ctx.SL) + (g_ctx.tp1Done ? " (TP1 taken)" : "") +
          (g_ctx.recovered ? " [recovered]" : "") + (g_ctx.orphan ? " [orphan]" : ""));
  }

string EntryText(void)
  {
   return(((int)InpEntryMode == BF_ENTRY_CONFIRM) ? "CONFIRM" : "LIMIT");
  }

string DirectionText(void)
  {
   if((int)InpDirection == BF_DIR_LONG_ONLY)
      return("LONG_ONLY");
   if((int)InpDirection == BF_DIR_SHORT_ONLY)
      return("SHORT_ONLY");
   return("BOTH");
  }

void UpdatePanel(void)
  {
   if(!g_renderOn || !InpShowPanel)
      return;
   g_render.PanelSet(0, "BprFvgEA " + _Symbol + " " + TfName() + " | mode: " + g_trade.modeNote);
   g_render.PanelSet(1, "source " + BfSourceName((int)InpSetupSource) + " | entry " + EntryText() + " | direction " +
                     DirectionText() + (g_tradeLogic ? "" : " | IFVG: display only, no setups"));
   g_render.PanelSet(2, "setups armed: " + IntegerToString(g_det.ArmedCount()) + " (tracked " +
                     IntegerToString(g_det.TrackedCount()) + ")");
   g_render.PanelSet(3, "order/position: " + CtxText());
   g_render.PanelSet(4, "today: " + DoubleToString(g_risk.RealisedR(), 2) + " R (" +
                     DoubleToString(g_risk.RealisedToday(), 2) + " " + AccountInfoString(ACCOUNT_CURRENCY) +
                     ") | lockout: " + (g_risk.Lockout() ? "YES" : "no") + " | trades " +
                     IntegerToString(g_risk.TradesToday()));
   g_render.PanelSet(5, "last: " + g_lastEvent);
   g_render.PanelDraw();
  }

//+------------------------------------------------------------------+
//| FX day (17:00 New York): risk day, breaker reset                 |
//+------------------------------------------------------------------+
void DayCheck(void)
  {
   long fx = g_ses.FxDay(TimeCurrent());
   if(fx == g_fxDay)
      return;
   g_fxDay = fx;
   g_risk.UpdateDay(fx, g_ses);
   g_trade.ResetBreaker();
  }

//+------------------------------------------------------------------+
//| Warm-up (spec s.1 InpWarmupBars, s.4 step 4)                     |
//+------------------------------------------------------------------+
bool DoWarmup(void)
  {
   MqlRates rr[];
   int      got;
   int      k;
   int      w;
   datetime formTime;
   datetime lastT;
   formTime = iTime(_Symbol, _Period, 0);
   if(formTime <= 0)
      return(false);
   if(!SetupSymbolParams())
      return(false);
   ArraySetAsSeries(rr, false);
   got = CopyRates(_Symbol, _Period, 1, g_warmBars, rr);
   if(got <= 0)
      return(false);
   // count the usable closed bars (strictly increasing, before the forming bar), exactly as the loop below
   w     = 0;
   lastT = 0;
   for(k = 0; k < got; k++)
     {
      if(rr[k].time >= formTime)
         break;
      if(rr[k].time <= lastT)
         continue;
      lastT = rr[k].time;
      w++;
     }
   if(w < 3)
      return(false);
   if(!EnsureCapacity(w + 1024))
      return(false);
   g_n         = 0;
   g_warmArmed = 0;
   g_warmDone  = 0;
   ResetState(g_state, g_ep);
   ResetState(g_tmp, g_ep);
   g_det.Init(g_bp, w);                         // trade_from = w: bars 0 .. w-1 are warm-up
   for(k = 0; k < got; k++)
     {
      if(rr[k].time >= formTime)
         break;
      if(g_n > 0 && rr[k].time <= g_t[g_n - 1])
         continue;
      if(!AppendBar(rr[k]))
         return(false);
      ProcessClosed(g_n - 1, true, 0, true);
     }
   if(g_tradeLogic)
     {
      g_det.EndWarmup();                         // warm-up setups -> DONE(WARMUP)
      CountWarmEvents();
      g_det.ClearIntents();
     }
   g_lastFormTime = formTime;
   g_ready        = true;
   DayCheck();
   g_log.Info("warm-up: " + IntegerToString(g_n) + " closed bars " + CBfLogger::Ts(g_t[0]) + " .. " +
              CBfLogger::Ts(g_t[g_n - 1]) + "; setups armed during warm-up " + IntegerToString(g_warmArmed) +
              ", ended (incl. WARMUP) " + IntegerToString(g_warmDone) + " - none of them is traded");
   if(g_n < g_warmBars)
      g_log.Info("warm-up: only " + IntegerToString(g_n) + " of " + IntegerToString(g_warmBars) +
                 " requested bars were available");
   if(g_renderOn && InpShowDisplacement)
     {
      for(k = BfIMax(0, g_n - g_displBars); k < g_n; k++)
         DrawDisplBar(k);
     }
   RenderNow();
   UpdatePanel();
   g_render.Redraw();
   return(true);
  }

//+------------------------------------------------------------------+
//| New closed bars: fetched by time, processed in order, never      |
//| skipped (spec s.2)                                               |
//+------------------------------------------------------------------+
bool ProcessNewBars(const datetime formTime)
  {
   MqlRates rr[];
   int      got;
   int      k;
   datetime from;
   datetime to;
   datetime nextOpen;
   if(g_n <= 0)
      return(false);
   from = (datetime)((long)g_t[g_n - 1] + 1);
   to   = (datetime)((long)formTime - 1);
   if(to < from)
      return(true);
   ArraySetAsSeries(rr, false);
   got = CopyRates(_Symbol, _Period, from, to, rr);
   if(got < 0)
      return(false);                             // data not ready: retried on the next tick
   if(got == 0)
     {
      // the previous forming bar must arrive as a closed bar; wait a little for the history to catch up
      if(g_lastFormTime > g_t[g_n - 1])
        {
         g_emptyFetch++;
         if(g_emptyFetch < 20)
            return(false);
        }
      g_emptyFetch = 0;
      return(true);
     }
   g_emptyFetch = 0;
   for(k = 0; k < got; k++)
     {
      if(rr[k].time <= g_t[g_n - 1])
         continue;
      if(rr[k].time >= formTime)
         break;
      if(!AppendBar(rr[k]))
         return(false);
      nextOpen = formTime;
      if(k + 1 < got && rr[k + 1].time < formTime)
         nextOpen = rr[k + 1].time;
      // a bar whose next open is not the forming bar is a catch-up bar (stale = true)
      ProcessClosed(g_n - 1, false, nextOpen, nextOpen != formTime);
     }
   return(true);
  }

//+------------------------------------------------------------------+
//| Restart recovery (spec s.5)                                      |
//+------------------------------------------------------------------+
void RecoverState(void)
  {
   int    i;
   int    total;
   ulong  tk;
   ulong  d;
   string cmt;
   string parts[];
   double tick = g_trade.TickSize();
   ResetCtx(g_ctx);
   //--- a pending order left from before the restart is deleted
   for(i = OrdersTotal() - 1; i >= 0; i--)
     {
      tk = OrderGetTicket(i);
      if(tk == 0)
         continue;
      if(OrderGetString(ORDER_SYMBOL) != _Symbol || OrderGetInteger(ORDER_MAGIC) != InpMagic)
         continue;
      if(g_trade.tradingAllowed)
        {
         if(g_trade.DeleteOrder(tk))
            g_log.Info("restart: deleted the pending order " + IntegerToString((long)tk) + " left from before");
         else
            g_log.Error("restart: could not delete the pending order " + IntegerToString((long)tk) + ": " +
                        g_trade.lastError);
        }
      else
         g_log.Info("restart: pending order " + IntegerToString((long)tk) + " found; log-only mode leaves it alone");
     }
   //--- a position with this EA's magic number is managed again
   if(!g_trade.SelectPosition(tk))
      return;
   g_ctx.active    = true;
   g_ctx.recovered = true;
   g_ctx.posId     = (ulong)PositionGetInteger(POSITION_IDENTIFIER);
   g_ctx.dir       = (PositionGetInteger(POSITION_TYPE) == (long)POSITION_TYPE_BUY) ? 1 : -1;
   g_ctx.fillTime  = (datetime)PositionGetInteger(POSITION_TIME);      // the time stop comes from POSITION_TIME
   g_ctx.entry     = PositionGetDouble(POSITION_PRICE_OPEN);
   g_ctx.lots      = PositionGetDouble(POSITION_VOLUME);
   g_ctx.SL        = PositionGetDouble(POSITION_SL);
   g_ctx.TP2       = PositionGetDouble(POSITION_TP);
   cmt             = PositionGetString(POSITION_COMMENT);
   //--- TP1 from the comment BF|<id>|<TP1>
   if(StringSplit(cmt, '|', parts) >= 3 && parts[0] == "BF")
     {
      g_ctx.id  = (int)StringToInteger(parts[1]);
      g_ctx.TP1 = StringToDouble(parts[2]);
     }
   g_ctx.tpMode = BF_TP_TP1_ONLY;                // no virtual TP1 unless it is known and differs from the server TP
   if((int)InpTpMode == BF_TP_TP1_TP2 && g_ctx.TP1 > 0.0 && g_ctx.TP2 > 0.0 && MathAbs(g_ctx.TP1 - g_ctx.TP2) > tick * 0.5)
      g_ctx.tpMode = BF_TP_TP1_TP2;
   //--- TP1 already taken? (an earlier partial close of this position)
   if(HistorySelectByPosition((long)g_ctx.posId))
     {
      total = HistoryDealsTotal();
      for(i = 0; i < total; i++)
        {
         d = HistoryDealGetTicket(i);
         if(d == 0)
            continue;
         if(HistoryDealGetInteger(d, DEAL_ENTRY) == (long)DEAL_ENTRY_OUT)
            g_ctx.tp1Done = true;
        }
     }
   if(g_ctx.tp1Done && g_ctx.SL > 0.0 &&
      ((g_ctx.dir > 0 && g_ctx.SL >= g_ctx.entry) || (g_ctx.dir < 0 && g_ctx.SL <= g_ctx.entry)))
      g_ctx.beDone = true;
   g_log.Info("restart: managing position #" + IntegerToString(g_ctx.id) + " " + DirText(g_ctx.dir) + " " +
              DoubleToString(g_ctx.lots, 2) + " lots from " + Px(g_ctx.entry) + " opened " +
              CBfLogger::Ts(g_ctx.fillTime) + " (SL/TP on the server, time stop from POSITION_TIME" +
              ((g_ctx.tpMode == BF_TP_TP1_TP2) ? ", virtual TP1 " + Px(g_ctx.TP1) : "") + ")");
  }

//+------------------------------------------------------------------+
//| Event handlers                                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
   string why;
   bool   tester;
   bool   optim;
   bool   visual;
   if(!ClampInputs(why))
     {
      Print("BprFvgEA: invalid input: ", why);
      return(INIT_PARAMETERS_INCORRECT);
     }
   tester       = (bool)MQLInfoInteger(MQL_TESTER);
   optim        = (bool)MQLInfoInteger(MQL_OPTIMIZATION);
   visual       = (bool)MQLInfoInteger(MQL_VISUAL_MODE);
   g_renderOn   = !(tester && !visual);          // no chart objects in non-visual Strategy Tester runs
   g_tradeLogic = ((int)InpFvgType == BF_FVGTYPE_FVG);
   BuildParams();

   g_ses.Init((int)InpServerMode, g_serverOffH);
   g_trade.Init(_Symbol, InpMagic, g_devPts, 3);
   g_risk.Init(_Symbol, InpMagic, g_riskPct, g_dayLossPct, g_commSide, g_maxTradesDay);
   g_log.Init(InpLogCsv && !optim, tester, optim, _Symbol, TfName());
   g_render.Init(InpShowZones, InpShowBPR, InpShowFVGinBPRmode, ((int)InpFib == BF_FIB_BPR), InpFibExtend,
                 InpShowDisplacement, InpShowTradeBoxes, InpShowPanel, InpBullColor, InpBullBreakColor, InpBearColor,
                 InpBearBreakColor, g_fillT, g_borderT, g_breakT, ((int)InpFvgType == BF_FVGTYPE_IFVG), _Digits);
   ObjectsDeleteAll(0, BF_PREFIX);

   g_n            = 0;
   g_ready        = false;
   g_lastFormTime = 0;
   g_emptyFetch   = 0;
   g_fxDay        = -1;
   g_lastEvent    = "";
   g_sumR         = 0.0;
   g_nR           = 0;
   ResetState(g_state, g_ep);
   ResetState(g_tmp, g_ep);

   if(!g_tradeLogic)
      g_log.Error("InpFvgType = IFVG: setups need FVG. The EA draws the zones only; trading is disabled.");
   g_log.Info("start: " + _Symbol + " " + TfName() + " | mode " + g_trade.modeNote + " | source " +
              BfSourceName((int)InpSetupSource) + ", entry " + EntryText() + ", direction " + DirectionText() +
              " | risk " + DoubleToString(g_riskPct, 2) + "% per trade, daily " + DoubleToString(g_dayLossPct, 2) +
              "% | hypothesis H-13 (untested)");
   if(InpLogCsv && !optim)
      g_log.Info("CSV logs (Common Files folder): " + g_log.SetupsFile() + ", " + g_log.TradesFile());

   RecoverState();
   DoWarmup();                                   // retried on the next ticks while the history is not ready
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   int     i;
   int     n;
   BfSetup s;
   //--- setups still open at exit get a row with their current status
   if(g_ready && g_tradeLogic)
     {
      n = g_det.TrackedCount();
      for(i = 0; i < n; i++)
         if(g_det.GetTracked(i, s))
            g_log.SetupRow(SetupCsv(s));
     }
   g_log.Info("stop (reason " + IntegerToString(reason) + "): positions and orders are left untouched");
   g_log.Close();
   g_render.DeleteAll();                         // all BFEA_ objects
  }

void OnTick()
  {
   datetime formTime;
   bool     newBar = false;
   if(!g_ready)
     {
      if(!DoWarmup())
         return;
     }
   //--- fills / closures since the last tick -> detector
   SyncTrade();
   //--- new closed bar(s): engine + detector + intents
   formTime = iTime(_Symbol, _Period, 0);
   if(formTime > 0 && formTime != g_lastFormTime)
     {
      DayCheck();
      if(ProcessNewBars(formTime))
        {
         g_lastFormTime = formTime;
         newBar = true;
        }
     }
   //--- every tick: TP1 partial, break-even, time stop, 16:44 New York flat
   ManagePosition();
   //--- display
   if(newBar || InpLiveBar)
      RenderNow();
   UpdatePanel();
   g_render.Redraw();
  }

// The fills are blended with the chart background: re-render at once when the user changes it.
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
  {
   color bg;
   if(id != CHARTEVENT_CHART_CHANGE || !g_ready || !g_renderOn)
      return;
   bg = (color)ChartGetInteger(0, CHART_COLOR_BACKGROUND);
   if(bg == g_render.LastBg())
      return;
   RenderNow();
  }

// Strategy Tester criterion: average R per closed trade (net of costs)
double OnTester()
  {
   if(g_nR <= 0)
      return(0.0);
   return(g_sumR / (double)g_nR);
  }
//+------------------------------------------------------------------+
