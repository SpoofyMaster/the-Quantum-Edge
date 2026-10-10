//+------------------------------------------------------------------+
//| BprFvgEA.mq5  (version 4)                                        |
//| LuxAlgo FVG / BPR zones on the chart + the owner's BPR setup:    |
//| rejection -> breakout -> Fibonacci pullback entries              |
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
// The setup rules are the project owner's (2026-10-09), not LuxAlgo's.
//
// Specification (single source of truth): research/indicators/BPR_BREAKOUT_FIB_SPEC.md ("spec s.N" below).
// Python reference with the same detector records: qe/strategies/bpr_breakout.py.
// Version 1 (H-13 sweep / MSS / far-edge limit rules, REJECTED by EXP010) is frozen in mql5/archive/BprFvgEA_v1_H13.
// Version 3 = version 2 + four EA-only switches (owner request 2026-10-10): InpUseCostFilter, InpUseRRFilter,
// InpCancelAtSessionEnd and InpEntriesAfterSessionEnd. The executor maps them onto the detector's existing settings
// and environment (max cost 0 = off, min RR 0 = off, the session signals of BfEnv), so the pure detector and its Python
// reference are unchanged; with the switches at their defaults v3 behaves exactly as v2.
// Version 4 = version 3 + two EA-only exit switches (owner request 2026-10-10): InpUseTimeStop and
// InpFlatBeforeRollover. Switched off, a position is no longer closed at market after InpMaxHoldMin ("close at market:
// TIME") or at 16:44 New York ("ROLLOVER"); it runs to its server stop-loss / take-profit. Both default to ON, so the
// defaults behave exactly as v3. Turning either OFF departs from the project's hard rule "every position closed
// <= 120 minutes after entry": that is the owner's decision for the Strategy Tester / demo, and such runs are not
// research trials of H-14 (see the README).
//
// STATUS: NOT YET COMPILED in MetaEditor (written without a compiler). Send the compiler messages.
// TRADING RULES: hypothesis H-14, UNTESTED. No claim of profitability.
// SAFETY: orders are sent only in the Strategy Tester and on DEMO accounts. On a REAL account the EA is log-only
//         (draws, detects, logs; sends no order). The account is checked again before every send and fails closed:
//         while the terminal is not connected or the account is not known yet, the EA is log-only as well.
//         There is deliberately no input to change this.
//         Do not tune on the locked final-test period (>= 2025-07-01, config/research.toml).
// INSTALL: copy the whole BprFvgEA folder (this file + include/) to MQL5/Experts/ and compile BprFvgEA.mq5.
//+------------------------------------------------------------------+
#property copyright   "(c) LuxAlgo - FVG/BPR Pine v5 logic; port + setups under CC BY-NC-SA 4.0"
#property link        "https://creativecommons.org/licenses/by-nc-sa/4.0/"
#property version     "4.00"
#property description "LuxAlgo FVG/BPR zones + BPR rejection -> breakout -> Fibonacci 50/61.8/71 limit entries (H-14)."
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
input bool                InpShowFVGinBPRmode     = false;              // Also draw the FVG boxes when BPRs are shown
input int                 InpVisibleBoxes         = 2;                  // # Visible FVG's (1..20): engine array length
input int                 InpLength               = 5;                  // Length (3..10): period of the body SMA
input ENUM_BF_FVGTYPE     InpFvgType              = BF_FVGTYPE_FVG;     // Options: FVG / IFVG (setups need FVG)
input bool                InpShowDisplacement     = false;              // Show displacement markers
input int                 InpDisplacementBars     = 300;                // Displacement markers on the last N bars
input ENUM_BF_FIB         InpFib                  = BF_FIB_NONE;        // LuxAlgo 'Fibonacci between last: BPR' (display)
input bool                InpFibExtend            = false;              // Extend the LuxAlgo Fibonacci lines
input bool                InpLiveBar              = true;               // Display the forming bar (decisions never use it)
input color               InpBullColor            = C'0,230,118';       // Bullish FVG / BPR colour
input color               InpBullBreakColor       = C'128,128,0';       // Bullish break colour
input color               InpBearColor            = C'255,82,82';       // Bearish FVG / BPR colour
input color               InpBearBreakColor       = C'255,0,0';         // Bearish break colour
input int                 InpFillTransp           = 90;                 // Fill transparency 0..100
input int                 InpBorderTransp         = 65;                 // Border / text transparency 0..100
input int                 InpBreakTransp          = 95;                 // Broken fill transparency 0..100
input bool                InpShowSetups           = true;               // Setup drawings: T1/T2, breakout, B1/B2, Fibonacci, orders
input bool                InpShowPanel            = true;               // Status and diagnostics panel

input group "==== SETUP: BPR rejection -> breakout -> Fibonacci (hypothesis H-14, untested) ===="
input ENUM_BF_DIRECTION   InpDirection            = BF_DIR_BOTH;        // Direction
input int                 InpMaxTouches           = 2;                  // Touches of the BPR allowed (a further touch ends it)
input int                 InpConfirmCloses        = 2;                  // Closes beyond the breakout level (breakout candle included)
input bool                InpRejectBeforeBreak    = false;              // Strict: a rejection candle must come before the breakout candle
input ENUM_BF_FVGRULE     InpFvgRule              = BF_FVGRULE_LUXALGO; // FVG needed in the breakout leg
input int                 InpSetupExpiryBars      = 240;                // Bars after the BPR's creation to confirm a breakout
input int                 InpLegExpiryBars        = 60;                 // Bars after the confirmation to place / fill entries
input double              InpFib1                 = 50.0;               // Entry 1: retracement % of the leg (0 = off)
input double              InpFib2                 = 61.8;               // Entry 2: retracement % (0 = off)
input double              InpFib3                 = 71.0;               // Entry 3: retracement % (0 = off)
input double              InpStopFib              = 100.0;              // Stop-loss: retracement % (100 = the leg origin)
input int                 InpStopBufferTicks      = 10;                 // Stop-loss: extra ticks beyond that level
input double              InpTargetFib            = 0.0;                // Take-profit: retracement % (0 = the leg high/low; <0 = extension)
input bool                InpUseRRFilter          = true;               // Reward:risk filter ON (false = entries placed whatever their RR)
input double              InpMinRR                = 0.0;                // Minimum reward:risk per entry (0 = off)
input bool                InpUseCostFilter        = true;               // Cost filter ON (false = entries placed whatever their cost)
input double              InpMaxCostR             = 0.30;               // Maximum round-trip cost per entry, fraction of its risk (0 = off)
input bool                InpUseTimeStop          = true;               // Time stop ON (false = no "close at market: TIME"; the position runs to its SL / TP)
input int                 InpMaxHoldMin           = 120;                // Time stop per position, minutes (max 120)

input group "==== SESSION, RISK, EXECUTION ===="
input ENUM_BF_SERVER_TIME InpServerMode           = BF_SERVER_NY_PLUS_7;// Server time convention
input int                 InpServerOffsetH        = 0;                  // Fixed-offset mode only: server = UTC + hours
input bool                InpUseSession           = true;               // Entries 08:00 London .. 14:45 New York, Mon-Fri
input bool                InpCancelAtSessionEnd   = true;               // Cancel pending orders at 14:45 New York (false = keep them until filled / expired)
input bool                InpEntriesAfterSessionEnd = false;            // Allow NEW orders after 14:45 New York, until 16:44 New York (Mon-Fri)
input bool                InpFlatBeforeRollover   = true;               // Close positions at 16:44 New York (false = held over the rollover / weekend: swap, gaps)
input double              InpRiskPct              = 0.20;               // Risk per SETUP, % equity incl. commission (max 0.20), split over the entries
input double              InpDailyLossPct         = 1.00;               // Planned daily loss, % (FX day 17:00 NY; max 1.00)
input int                 InpMaxTradesDay         = 0;                  // Max positions per FX day (0 = no limit)
input double              InpCommissionPerLotSide = 3.50;               // Commission per lot per side, account ccy (UNVERIFIED)
input int                 InpSlippageTicks        = 1;                  // Slippage ticks (sizing, cost check)
input int                 InpMaxSpreadPts         = 0;                  // Max spread in points (0 = off)
input long                InpMagic                = 2610091;            // Magic number (v2 / v3 / v4)
input int                 InpDeviationPts         = 30;                 // Max deviation for market orders, points
input int                 InpWarmupBars           = 5000;               // Closed bars processed at start (never traded)
input bool                InpLogCsv               = true;               // CSV logs in the Common Files folder

//+------------------------------------------------------------------+
//| Execution context: one setup, up to BF_NLEV orders / positions   |
//| (spec s.8)                                                       |
//+------------------------------------------------------------------+
#define BF_XS_NONE        0       // level not sent
#define BF_XS_PENDING     1       // limit order in the book
#define BF_XS_OPEN        2       // filled: a position (or part of the netting position)
#define BF_XS_DONE        3       // finished (closed, cancelled, refused)

struct BfLevelCtx
  {
   int               state;             // BF_XS_*
   bool              cancelled;         // the detector cancelled this level: it is never reported to the detector again
   bool              cancelWanted;      // a delete failed: retried on the next ticks
   bool              partialDel;        // the rest of a partly filled limit was deleted
   bool              market;            // sent as a market order (its live price was already at / through P)
   bool              fillCheck;         // market fill: its actual risk has not been checked yet
   bool              riskLogged;
   bool              posSeen;           // entry / lots / fill time read from the open position
   ulong             orderTicket;
   ulong             posId;             // POSITION_IDENTIFIER once filled
   double            P;
   double            lots;
   double            planned;           // planned risk, account currency
   double            budget;            // equity * risk% / levels at sizing time
   double            entry;
   datetime          fillTime;
   int               tries;
   int               closeFails;
   string            closeReason;
   datetime          lastTry;           // last delete / close attempt (retries throttled, RetryDue)
  };

struct BfTradeCtx
  {
   bool              active;
   int               id;
   int               dir;
   double            SL;
   double            TP;
   datetime          decisionTime;
   BfLevelCtx        lv[BF_NLEV];
  };

// A position with this EA's symbol and magic that no level owns (restart, or a fill that raced a cancel): managed
// with its server SL/TP, the time stop and the 16:44 New York flat (each only while its v4 switch is ON).
struct BfOrphan
  {
   ulong             posId;
   datetime          fillTime;
   int               closeFails;
   datetime          lastTry;
  };

void ResetLevel(BfLevelCtx &x)
  {
   x.state        = BF_XS_NONE;
   x.cancelled    = false;
   x.cancelWanted = false;
   x.partialDel   = false;
   x.market       = false;
   x.fillCheck    = false;
   x.riskLogged   = false;
   x.posSeen      = false;
   x.orderTicket  = 0;
   x.posId        = 0;
   x.P            = 0.0;
   x.lots         = 0.0;
   x.planned      = 0.0;
   x.budget       = 0.0;
   x.entry        = 0.0;
   x.fillTime     = 0;
   x.tries        = 0;
   x.closeFails   = 0;
   x.closeReason  = "";
   x.lastTry      = 0;
  }

void ResetCtx(BfTradeCtx &x)
  {
   int k;
   x.active       = false;
   x.id           = 0;
   x.dir          = 0;
   x.SL           = 0.0;
   x.TP           = 0.0;
   x.decisionTime = 0;
   for(k = 0; k < BF_NLEV; k++)
      ResetLevel(x.lv[k]);
  }

//+------------------------------------------------------------------+
//| Globals                                                          |
//+------------------------------------------------------------------+
double         g_o[];                   // the EA's own closed-bar arrays, absolute index 0 = first warm-up bar
double         g_h[];
double         g_l[];
double         g_c[];
datetime       g_t[];
int            g_n            = 0;

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
BfOrphan       g_orph[];
int            g_nOrph        = 0;

bool           g_ready        = false;  // warm-up done
bool           g_tradeLogic   = true;   // false in IFVG mode: display only
bool           g_renderOn     = true;   // false in non-visual Strategy Tester runs
datetime       g_lastFormTime = 0;
int            g_emptyFetch   = 0;
long           g_fxDay        = -1;
string         g_lastEvent    = "";
double         g_sumR         = 0.0;
int            g_nR           = 0;
int            g_warmArmed    = 0;
int            g_warmDone     = 0;
bool           g_recoveryLive = false;  // the restart recovery has run while trading was permitted
long           g_lastStrayDel = 0;
string         g_runText      = "";
int            g_nRetry       = 0;      // decisions put back because of a transient condition
string         g_lastWait     = "";     // last transient condition
string         g_permWhy      = "";     // why trading is not permitted (algo trading switches), "" = OK
int            g_nLogOnly     = 0;      // decisions not sent because the account is log-only
string         g_mgmtBlock    = "";     // management sends paused (algo trading off): logged when it changes
int            g_nExpPre      = 0;      // setups expired before the breakout confirmation
int            g_nExpLeg      = 0;      // setups expired after the confirmation (no pullback / FVG / fill in time)
int            g_nRollDel     = 0;      // pending orders deleted by the 16:44 New York rollover rule

//--- validated copies of the inputs
int            g_len          = 5;
int            g_vis          = 2;
int            g_displBars    = 300;
int            g_fillT        = 90;
int            g_borderT      = 65;
int            g_breakT       = 95;
int            g_maxTouches   = 2;
int            g_confirm      = 2;
int            g_setupExp     = 240;
int            g_legExp       = 60;
int            g_stopBuf      = 10;
int            g_maxHold      = 120;
int            g_maxTradesDay = 0;
int            g_slipTicks    = 1;
int            g_maxSpreadPts = 0;
int            g_devPts       = 30;
int            g_warmBars     = 5000;
int            g_serverOffH   = 0;
double         g_fib[BF_NLEV];
double         g_stopFib      = 100.0;
double         g_tgtFib       = 0.0;
double         g_minRR        = 0.0;
double         g_maxCostR     = 0.30;
double         g_riskPct      = 0.20;
double         g_dayLossPct   = 1.00;
double         g_commSide     = 3.50;
int            g_nLevels      = 3;      // enabled Fibonacci entries (the risk is split over them)

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

string FibText(const double f)
  {
   return(DoubleToString(f, 1) + "%");
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

string FvgRuleText(void)
  {
   if((int)InpFvgRule == BF_FVGRULE_ANY_GAP)
      return("ANY_GAP");
   if((int)InpFvgRule == BF_FVGRULE_NONE)
      return("NONE");
   return("LUXALGO");
  }

string DirectionText(void)
  {
   if((int)InpDirection == BF_DIR_LONG_ONLY)
      return("LONG_ONLY");
   if((int)InpDirection == BF_DIR_SHORT_ONLY)
      return("SHORT_ONLY");
   return("BOTH");
  }

//+------------------------------------------------------------------+
//| OnInit: validate / clamp (hard caps: 0.20 %, 1.00 %, 120 min)    |
//+------------------------------------------------------------------+
bool ClampInputs(string &why)
  {
   int    k;
   double fmax = 0.0;
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
   g_fib[0] = InpFib1;
   g_fib[1] = InpFib2;
   g_fib[2] = InpFib3;
   g_nLevels = 0;
   for(k = 0; k < BF_NLEV; k++)
     {
      if(g_fib[k] < 0.0 || g_fib[k] >= 100.0)
        {
         why = "InpFib" + IntegerToString(k + 1) + " must be in [0, 100)";
         return(false);
        }
      if(g_fib[k] > 0.0)
        {
         g_nLevels++;
         fmax = MathMax(fmax, g_fib[k]);
        }
     }
   if(g_nLevels == 0)
     {
      why = "at least one of InpFib1..3 must be > 0";
      return(false);
     }
   if(InpStopFib <= 0.0 || InpStopFib > 200.0)
     {
      why = "InpStopFib must be in (0, 200]";
      return(false);
     }
   if(InpTargetFib < -200.0 || InpTargetFib >= 100.0)
     {
      why = "InpTargetFib must be in [-200, 100)";
      return(false);
     }
   if(InpMinRR < 0.0 || InpMaxCostR < 0.0)
     {
      why = "InpMinRR and InpMaxCostR must be >= 0";
      return(false);
     }
   if(InpStopFib <= fmax)
      Print("BprFvgEA: WARNING InpStopFib (", DoubleToString(InpStopFib, 1), ") is not beyond the deepest entry (",
            DoubleToString(fmax, 1), "): those entries get BAD_LEVEL");
   g_len          = ClampWarn("InpLength", InpLength, 3, 10);
   g_vis          = ClampWarn("InpVisibleBoxes", InpVisibleBoxes, 1, BF_MAXB);
   g_displBars    = ClampWarn("InpDisplacementBars", InpDisplacementBars, 1, 5000);
   g_fillT        = ClampWarn("InpFillTransp", InpFillTransp, 0, 100);
   g_borderT      = ClampWarn("InpBorderTransp", InpBorderTransp, 0, 100);
   g_breakT       = ClampWarn("InpBreakTransp", InpBreakTransp, 0, 100);
   g_maxTouches   = ClampWarn("InpMaxTouches", InpMaxTouches, 1, 5);
   g_confirm      = ClampWarn("InpConfirmCloses", InpConfirmCloses, 1, 5);
   g_setupExp     = ClampWarn("InpSetupExpiryBars", InpSetupExpiryBars, 1, 100000);
   g_legExp       = ClampWarn("InpLegExpiryBars", InpLegExpiryBars, 1, 100000);
   g_stopBuf      = ClampWarn("InpStopBufferTicks", InpStopBufferTicks, 0, 100000);
   g_maxHold      = ClampWarn("InpMaxHoldMin", InpMaxHoldMin, 1, 120);              // hard cap 120 min
   g_maxTradesDay = ClampWarn("InpMaxTradesDay", InpMaxTradesDay, 0, 1000);
   g_slipTicks    = ClampWarn("InpSlippageTicks", InpSlippageTicks, 0, 100000);
   g_maxSpreadPts = ClampWarn("InpMaxSpreadPts", InpMaxSpreadPts, 0, 1000000);
   g_devPts       = ClampWarn("InpDeviationPts", InpDeviationPts, 0, 100000);
   g_warmBars     = ClampWarn("InpWarmupBars", InpWarmupBars, 100, 500000);
   g_serverOffH   = ClampWarn("InpServerOffsetH", InpServerOffsetH, -12, 14);
   g_stopFib      = InpStopFib;
   g_tgtFib       = InpTargetFib;
   g_minRR        = InpMinRR;
   g_maxCostR     = InpMaxCostR;
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

//--- engine and detector parameters from the validated inputs (spec s.1)
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
   g_bp.direction            = (int)InpDirection;
   g_bp.maxTouches           = g_maxTouches;
   g_bp.confirmCloses        = g_confirm;
   g_bp.rejectBeforeBreak    = InpRejectBeforeBreak;
   g_bp.fvgRule              = (int)InpFvgRule;
   g_bp.setupExpiryBars      = g_setupExp;
   g_bp.legExpiryBars        = g_legExp;
   g_bp.fib1                 = g_fib[0];
   g_bp.fib2                 = g_fib[1];
   g_bp.fib3                 = g_fib[2];
   g_bp.stopFib              = g_stopFib;
   g_bp.stopBufferTicks      = g_stopBuf;
   g_bp.targetFib            = g_tgtFib;
   // v3 switches (EA only): a filter that is switched off is passed to the detector as 0 = off
   g_bp.minRR                = InpUseRRFilter ? g_minRR : 0.0;
   g_bp.maxCostR             = InpUseCostFilter ? g_maxCostR : 0.0;
   g_bp.maxHoldMin           = g_maxHold;
   g_bp.useSession           = InpUseSession;
   g_bp.commissionPerLotSide = g_commSide;
   g_bp.slippageTicks        = (double)g_slipTicks;
   g_bp.tickSize             = 0.0;          // set from the symbol by SetupSymbolParams()
   g_bp.commPrice            = 0.0;
  }

//--- tick size, digits and comm_price from the symbol; false while the symbol data is not ready
bool SetupSymbolParams(void)
  {
   double tick = g_trade.TickSize();
   if(tick <= 0.0)
      return(false);
   if(g_risk.ValuePerPriceUnit() <= 0.0)
      return(false);
   g_bp.tickSize  = tick;
   g_bp.digits    = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   g_bp.commPrice = g_risk.CommPrice();
   return(true);
  }

//+------------------------------------------------------------------+
//| Bar arrays                                                       |
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
//| Logs (spec s.8)                                                  |
//+------------------------------------------------------------------+
string LevelCsv(const BfEvent &e, const int k)
  {
   int st = e.snLvSt[k];
   if(g_fib[k] <= 0.0)
      return("off");
   if(st == BF_LV_NONE)
      return("");
   if(st == BF_LV_SKIPPED || st == BF_LV_CANCELLED || st == BF_LV_DROPPED)
      return(BfLevelStatusName(st) + ":" + BfReasonName(e.snLvRsn[k]));
   return(BfLevelStatusName(st) + "@" + Px(e.snLvP[k]));
  }

// BFEA2_setups row (run added by the logger):
// id,dir,created_time,B,T,touches,ref_time,level,breakout_time,confirm_time,O,X,decision_time,SL,TP,L1,L2,L3,phase,reason
string SetupCsv(const BfEvent &e)
  {
   bool conf = (e.confirmBar >= 0);
   bool dec  = (e.snSL != 0.0);
   string line = IntegerToString(e.id) + "," + IntegerToString(e.dir) + "," + CBfLogger::Ts(BarTime(e.created)) + "," +
                 Px(e.B) + "," + Px(e.T) + "," + IntegerToString(e.touches) + "," +
                 ((e.ref >= 0) ? CBfLogger::Ts(BarTime(e.ref)) : "") + "," + ((e.ref >= 0) ? Px(e.lvl) : "") + "," +
                 ((e.brkBar >= 0) ? CBfLogger::Ts(BarTime(e.brkBar)) : "") + "," +
                 (conf ? CBfLogger::Ts(BarTime(e.confirmBar)) : "") + "," + (conf ? Px(e.snO) : "") + "," +
                 (conf ? Px(e.snX) : "") + "," + ((e.decisionBar >= 0) ? CBfLogger::Ts(BarTime(e.decisionBar)) : "") +
                 "," + (dec ? Px(e.snSL) : "") + "," + (dec ? Px(e.snTP) : "") + "," + LevelCsv(e, 0) + "," +
                 LevelCsv(e, 1) + "," + LevelCsv(e, 2) + "," + BfPhaseName(e.phase) + "," + BfReasonName(e.reason);
   return(line);
  }

// One Experts-log line per detector record
string EventText(const BfEvent &e)
  {
   string s = "#" + IntegerToString(e.id) + " " + DirText(e.dir) + " " + BfEventName(e.ev);
   int    k = e.k;
   if(e.ev == BF_EV_TOUCH)
      s = s + " " + IntegerToString(k) + " of max " + IntegerToString(g_maxTouches) + " (zone " + Px(e.B) + " - " +
          Px(e.T) + ")";
   else
      if(e.ev == BF_EV_BREAKOUT || e.ev == BF_EV_BREAK_FAIL)
         s = s + " level " + Px(e.lvl) + " (" + ((e.dir > 0) ? "high" : "low") + " of the candle at " +
             CBfLogger::Ts(BarTime(e.ref)) + ")";
      else
         if(e.ev == BF_EV_CONFIRM)
            s = s + ": leg " + Px(e.O) + " -> " + Px(e.X) + ", tracking the " + ((e.dir > 0) ? "high" : "low");
         else
            if(e.ev == BF_EV_PLACE_LIMIT)
               s = s + " (decided) L" + IntegerToString(k) + " (" + FibText(g_fib[k - 1]) + ") P=" + Px(e.P) + " SL=" +
                   Px(e.SL) + " TP=" + Px(e.TP) + " | fib " + Px(e.O) + " -> " + Px(e.X);
            else
               if(e.ev == BF_EV_SKIP || e.ev == BF_EV_CANCEL || e.ev == BF_EV_DROP)
                  s = s + " L" + IntegerToString(k) + " (" + FibText(g_fib[k - 1]) + ")";
   if(e.reason != BF_R_NONE)
      s = s + " (" + BfReasonName(e.reason) + ")";
   if(e.ev == BF_EV_DONE)
      s = s + " in phase " + BfPhaseName(e.phase);
   s = s + " | bar " + CBfLogger::Ts(BarTime(e.n));
   return(s);
  }

//+------------------------------------------------------------------+
//| Setup drawings (spec s.8)                                        |
//+------------------------------------------------------------------+
color DirColor(const int dir)
  {
   return((dir > 0) ? InpBullColor : InpBearColor);
  }

void DrawEvent(const BfEvent &e)
  {
   string   tip;
   datetime t;
   double   lo;
   double   hi;
   if(!g_renderOn || !InpShowSetups || e.n < 0 || e.n >= g_n)
      return;
   t  = g_t[e.n];
   lo = g_l[e.n];
   hi = g_h[e.n];
   tip = "#" + IntegerToString(e.id) + " " + DirText(e.dir) + " " + BfEventName(e.ev);
   if(e.ev == BF_EV_TOUCH)
     {
      // the setup's own zone (the LuxAlgo box may leave the engine arrays, and its colour is not the direction)
      if(e.k == 1)
         g_render.SetupRect(e.id, "ZONE", BarTime(e.created), e.B, g_render.IdxToTime(e.n + BF_SK_BARS, g_n, g_t,
                            g_lastFormTime), e.T, DirColor(e.dir), "#" + IntegerToString(e.id) + " " +
                            DirText(e.dir) + " zone " + Px(e.B) + " - " + Px(e.T));
      g_render.SetupText(e.id, "T" + IntegerToString(e.k), t, (e.dir > 0) ? lo : hi, "T" + IntegerToString(e.k),
                         DirColor(e.dir), (e.dir > 0) ? ANCHOR_UPPER : ANCHOR_LOWER, tip);
     }
   else
      if(e.ev == BF_EV_DROP && e.k >= 1 && e.k <= BF_NLEV)
         g_render.SetupLabel(e.id, "L" + IntegerToString(e.k), FibText(g_fib[e.k - 1]) + " L" + IntegerToString(e.k) +
                             " DROPPED " + BfReasonName(e.reason) + (g_trade.tradingAllowed ? "" : " (log-only)"));
   else
      if(e.ev == BF_EV_BREAKOUT)
        {
         g_render.SetupHLine(e.id, "BRK", BarTime(e.ref), t, e.lvl, DirColor(e.dir), STYLE_DOT, "",
                             tip + " level " + Px(e.lvl));
         g_render.SetupText(e.id, "B1", t, (e.dir > 0) ? hi : lo, "B1", DirColor(e.dir),
                            (e.dir > 0) ? ANCHOR_LOWER : ANCHOR_UPPER, tip);
        }
      else
         if(e.ev == BF_EV_BREAK_FAIL)
            g_render.SetupText(e.id, "BF" + IntegerToString(e.n), t, (e.dir > 0) ? hi : lo, "x", C'128,128,128',
                               (e.dir > 0) ? ANCHOR_LOWER : ANCHOR_UPPER, tip);
         else
            if(e.ev == BF_EV_CONFIRM)
               g_render.SetupText(e.id, "B2", t, (e.dir > 0) ? hi : lo, "B2", DirColor(e.dir),
                                  (e.dir > 0) ? ANCHOR_LOWER : ANCHOR_UPPER, tip + ": leg " + Px(e.O) + " -> " +
                                  Px(e.X));
            else
               if(e.ev == BF_EV_DONE || e.ev == BF_EV_CLOSED)
                  g_render.SetupGrey(e.id);
  }

// The setup Fibonacci (spec s.8): dashed while the leg is tracked (phase LEG), solid with the order lines once
// decided. 0 % = the leg extreme X, 100 % = the leg origin O.
void DrawFib(const BfSetup &s)
  {
   int             k;
   int             endIdx;
   bool            ordered = (s.phase == BF_PH_ORDERED || s.phase == BF_PH_FILLED);
   double          O = ordered ? s.decO : s.O;
   double          X = ordered ? s.decX : s.X;
   double          f;
   double          p;
   datetime        t1;
   datetime        t2;
   color           cl  = DirColor(s.dir);
   color           fibC = C'255,193,7';
   ENUM_LINE_STYLE st = ordered ? STYLE_SOLID : STYLE_DASH;
   string          lbl;
   string          tip = "#" + IntegerToString(s.id) + " " + DirText(s.dir) + " fib " + Px(O) + " -> " + Px(X);
   if(!g_renderOn || !InpShowSetups || s.oBar < 0 || s.xBar < 0)
      return;
   endIdx = BfIMax(s.xBar, (s.decisionBar >= 0) ? s.decisionBar : g_n - 1) + BF_SK_BARS;
   t1 = BarTime(s.oBar);
   t2 = g_render.IdxToTime(endIdx, g_n, g_t, g_lastFormTime);
   g_render.SetupSegment(s.id, "LEG", t1, O, BarTime(s.xBar), X, cl, STYLE_DOT);
   g_render.SetupHLine(s.id, "F0", t1, t2, X, fibC, st, "0% " + Px(X) + (ordered ? "" : " (tracking)"), tip);
   g_render.SetupHLine(s.id, "F100", t1, t2, O, fibC, st, "100% " + Px(O), tip);
   for(k = 0; k < BF_NLEV; k++)
     {
      f = g_fib[k];
      if(f <= 0.0)
        {
         g_render.SetupDelete(s.id, "L" + IntegerToString(k + 1));
         continue;
        }
      p   = X - (f / 100.0) * (X - O);
      lbl = FibText(f);
      if(ordered)
        {
         if(s.lvSt[k] == BF_LV_PENDING || s.lvSt[k] == BF_LV_FILLED || s.lvSt[k] == BF_LV_CLOSED)
            lbl = lbl + " L" + IntegerToString(k + 1) + " " + ((s.dir > 0) ? "BUY" : "SELL") + " LIMIT " +
                  Px(s.lvP[k]) + " " + BfLevelStatusName(s.lvSt[k]);
         else
            lbl = lbl + " L" + IntegerToString(k + 1) + " " + BfLevelStatusName(s.lvSt[k]) + " " +
                  BfReasonName(s.lvRsn[k]);
        }
      g_render.SetupHLine(s.id, "L" + IntegerToString(k + 1), t1, t2, p, ordered ? C'33,150,243' : fibC, st, lbl, tip);
     }
   if(ordered)
     {
      g_render.SetupHLine(s.id, "SL", t1, t2, s.SL, C'255,82,82', STYLE_SOLID, "SL " + Px(s.SL), tip);
      g_render.SetupHLine(s.id, "TP", t1, t2, s.TP, C'0,200,83', STYLE_SOLID, "TP " + Px(s.TP), tip);
     }
   else
     {
      g_render.SetupDelete(s.id, "SL");
      g_render.SetupDelete(s.id, "TP");
     }
  }

void DrawSetups(void)
  {
   int     i;
   int     n;
   BfSetup s;
   if(!g_renderOn || !InpShowSetups || !g_tradeLogic)
      return;
   n = g_det.TrackedCount();
   for(i = 0; i < n; i++)
     {
      if(!g_det.GetTracked(i, s))
         continue;
      if(s.touches >= 1)
         g_render.SetupRect(s.id, "ZONE", BarTime(s.created), s.B, g_render.IdxToTime(g_n - 1 + BF_SK_BARS, g_n, g_t,
                            g_lastFormTime), s.T, DirColor(s.dir), "#" + IntegerToString(s.id) + " " + DirText(s.dir) +
                            " zone " + Px(s.B) + " - " + Px(s.T) + " (" + BfPhaseName(s.phase) + ", touches " +
                            IntegerToString(s.touches) + ")");
      if(s.phase == BF_PH_LEG || s.phase == BF_PH_ORDERED || s.phase == BF_PH_FILLED)
         DrawFib(s);
     }
  }

//+------------------------------------------------------------------+
//| Detector records -> logs and drawings                            |
//+------------------------------------------------------------------+
void HandleEvents(void)
  {
   int     i;
   int     n = g_det.EventCount();
   BfEvent e;
   for(i = 0; i < n; i++)
     {
      if(!g_det.GetEvent(i, e))
         continue;
      g_log.Info(EventText(e));
      g_lastEvent = "#" + IntegerToString(e.id) + " " + BfEventName(e.ev) +
                    ((e.k > 0 && e.ev != BF_EV_TOUCH) ? " L" + IntegerToString(e.k) : "") +
                    ((e.reason != BF_R_NONE) ? "(" + BfReasonName(e.reason) + ")" : "") + " " +
                    CBfLogger::Ts(BarTime(e.n));
      DrawEvent(e);
      if(e.ev == BF_EV_DONE && e.reason == BF_R_EXPIRED)
        {
         if(e.phase == BF_PH_WAIT || e.phase == BF_PH_ZONE || e.phase == BF_PH_BREAK)
            g_nExpPre++;
         else
            g_nExpLeg++;
        }
      if(e.ev == BF_EV_DONE || e.ev == BF_EV_CLOSED)
         g_log.SetupRow(SetupCsv(e));
     }
   if(g_det.LostEvents() > 0 && n >= BF_MAX_EVENTS)
      g_log.Error("event buffer full: " + IntegerToString(g_det.LostEvents()) + " records lost so far");
   g_det.ClearEvents();
  }

// warm-up: records are counted, not logged (no warm-up setup is ever traded)
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
//| Execution helpers                                                |
//+------------------------------------------------------------------+
bool CtxBusy(void)
  {
   int k;
   if(!g_ctx.active)
      return(false);
   for(k = 0; k < BF_NLEV; k++)
      if(g_ctx.lv[k].state == BF_XS_PENDING || g_ctx.lv[k].state == BF_XS_OPEN)
         return(true);
   return(false);
  }

// a position identifier owned by a level of the context (an open level, or a pending order that just filled)
bool IsTracked(const ulong id)
  {
   int k;
   if(!g_ctx.active || id == 0)
      return(false);
   for(k = 0; k < BF_NLEV; k++)
     {
      if(g_ctx.lv[k].state == BF_XS_OPEN && g_ctx.lv[k].posId == id)
         return(true);
      if(g_ctx.lv[k].state == BF_XS_PENDING && g_ctx.lv[k].orderTicket == id)
         return(true);
     }
   return(false);
  }

bool IsTrackedOrder(const ulong ticket)
  {
   int k;
   if(!g_ctx.active)
      return(false);
   for(k = 0; k < BF_NLEV; k++)
      if(g_ctx.lv[k].state == BF_XS_PENDING && g_ctx.lv[k].orderTicket == ticket)
         return(true);
   return(false);
  }

int FindOrphan(const ulong posId)
  {
   int i;
   for(i = 0; i < g_nOrph; i++)
      if(g_orph[i].posId == posId)
         return(i);
   return(-1);
  }

void AddOrphan(const ulong posId, const datetime fillTime, const string why)
  {
   if(posId == 0 || FindOrphan(posId) >= 0)
      return;
   if(ArrayResize(g_orph, g_nOrph + 1, 8) < g_nOrph + 1)
      return;
   g_orph[g_nOrph].posId      = posId;
   g_orph[g_nOrph].fillTime   = fillTime;
   g_orph[g_nOrph].closeFails = 0;
   g_orph[g_nOrph].lastTry    = 0;
   g_nOrph++;
   g_log.Error("position " + IntegerToString((long)posId) + " (opened " + CBfLogger::Ts(fillTime) + ") is managed " +
               "without a setup (" + why + "): " + ExitsListText());
  }

void RemoveOrphan(const int i)
  {
   int j;
   if(i < 0 || i >= g_nOrph)
      return;
   for(j = i + 1; j < g_nOrph; j++)
     {
      g_orph[j - 1].posId      = g_orph[j].posId;
      g_orph[j - 1].fillTime   = g_orph[j].fillTime;
      g_orph[j - 1].closeFails = g_orph[j].closeFails;
      g_orph[j - 1].lastTry    = g_orph[j].lastTry;
     }
   g_nOrph--;
  }

// the order just selected by OrderGetTicket(): a pending order of this EA (symbol + magic, pending order type)
bool IsOwnPendingOrder(void)
  {
   long ot;
   if(OrderGetString(ORDER_SYMBOL) != _Symbol || OrderGetInteger(ORDER_MAGIC) != InpMagic)
      return(false);
   ot = OrderGetInteger(ORDER_TYPE);
   return(ot == (long)ORDER_TYPE_BUY_LIMIT || ot == (long)ORDER_TYPE_SELL_LIMIT ||
          ot == (long)ORDER_TYPE_BUY_STOP || ot == (long)ORDER_TYPE_SELL_STOP ||
          ot == (long)ORDER_TYPE_BUY_STOP_LIMIT || ot == (long)ORDER_TYPE_SELL_STOP_LIMIT);
  }

// spec s.8 "one setup at a time": no context, no orphan, no own position or pending order
bool SlotFree(void)
  {
   return(!CtxBusy() && g_nOrph == 0 && g_trade.OwnPositions() == 0 && g_trade.OwnPendingOrders() == 0);
  }

string LevelTag(const int k)
  {
   return("#" + IntegerToString(g_ctx.id) + " L" + IntegerToString(k + 1) + " ");
  }

// position identifier of a market deal (DEAL_POSITION_ID); the order ticket when the deal is not in the history yet
ulong PosIdOfMarketFill(void)
  {
   ulong deal = g_trade.LastDeal();
   if(deal > 0 && HistoryDealSelect(deal))
      return((ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID));
   return(0);
  }

// v4 exit switches: the two market closes that are not server orders (InpUseTimeStop, InpFlatBeforeRollover)
bool TimeStopDue(const datetime fillTime, const datetime now)
  {
   return(InpUseTimeStop && (long)now >= (long)fillTime + (long)g_maxHold * 60);
  }

bool RolloverFlatDue(const datetime fillTime, const datetime now)
  {
   return(InpFlatBeforeRollover && g_ses.FlatDue(fillTime, now));
  }

// the EA's market exits that are ON: "the 120-min time stop and the 16:44 New York flat" ("" when both are OFF)
string MarketExitsText(void)
  {
   string ts = "the " + IntegerToString(g_maxHold) + "-min time stop";
   if(InpUseTimeStop && InpFlatBeforeRollover)
      return(ts + " and the 16:44 New York flat");
   if(InpUseTimeStop)
      return(ts);
   if(InpFlatBeforeRollover)
      return("the 16:44 New York flat");
   return("");
  }

// every exit of a position: "server SL/TP, the 120-min time stop and the 16:44 New York flat apply"
string ExitsListText(void)
  {
   if(InpUseTimeStop && InpFlatBeforeRollover)
      return("server SL/TP, " + MarketExitsText() + " apply");
   if(InpUseTimeStop || InpFlatBeforeRollover)
      return("server SL/TP and " + MarketExitsText() + " apply");
   return("only server SL/TP apply (time stop and 16:44 flat OFF)");
  }

// which market exit is due for a position filled at fillTime ("" = none)
string DueExitText(const datetime fillTime, const datetime now)
  {
   if(TimeStopDue(fillTime, now))
      return("time stop");
   if(RolloverFlatDue(fillTime, now))
      return("16:44 New York flat");
   return("");
  }

// 16:44-17:00 New York: no new order, no pending order over the rollover (any session setting; also with
// InpFlatBeforeRollover = false, which only lets POSITIONS cross it)
bool InRolloverWindow(void)
  {
   int m = CBfSession::MinuteOfDay(g_ses.ServerToNY(TimeCurrent()));
   return(m >= BF_NY_FLAT_MIN && m < BF_NY_ROLL_MIN);
  }

// seconds from now to the next 16:44 New York (the rollover cut)
long SecondsToRolloverCut(void)
  {
   long nyNow = (long)g_ses.ServerToNY(TimeCurrent());
   long nyCut = (nyNow / 86400) * 86400 + (long)BF_NY_FLAT_MIN * 60;
   if(nyCut <= nyNow)
      nyCut += 86400;
   return(nyCut - nyNow);
  }

// the effective entry window of the EA (v3: InpEntriesAfterSessionEnd extends it to 16:44 New York)
bool SessionOkAt(const datetime server)
  {
   return(g_ses.EntryOk(server) || (InpEntriesAfterSessionEnd && LateEntryOk(server)));
  }

// retries of failed management sends (delete / close) at most every 3 seconds per level / position
bool RetryDue(datetime &last)
  {
   long now = (long)TimeCurrent();
   if(last > 0 && now >= (long)last && now - (long)last < 3)
      return(false);
   last = (datetime)now;
   return(true);
  }

// management sends (delete / close) need the algo-trading switches on; a change of that state is logged once
bool MgmtAllowed(void)
  {
   string why = "";
   if(!g_trade.tradingAllowed)
      return(false);
   g_trade.TradePermission(why);
   if(why != g_mgmtBlock)
     {
      if(why != "")
         g_log.Error("order management paused: " + why + " (positions keep their server SL/TP until it is back)");
      else
         g_log.Info("order management resumed");
      g_mgmtBlock = why;
     }
   return(why == "");
  }

//+------------------------------------------------------------------+
//| Execution: detector intents (spec s.8)                           |
//+------------------------------------------------------------------+
void ExecCancel(const BfIntent &it)
  {
   int k = it.k - 1;
   if(!g_ctx.active || g_ctx.id != it.id || k < 0 || k >= BF_NLEV)
      return;
   if(g_ctx.lv[k].state != BF_XS_PENDING)
      return;
   g_ctx.lv[k].cancelled = true;                 // the detector forgets this level: never reported again
   if(g_trade.DeleteOrder(g_ctx.lv[k].orderTicket))
     {
      g_log.Info(LevelTag(k) + "pending order deleted (" + BfReasonName(it.reason) + ")");
      // a part filled just before the delete becomes a position no level owns: Reconcile() adopts it
      g_ctx.lv[k].state = BF_XS_DONE;
      return;
     }
   if(!OrderSelect(g_ctx.lv[k].orderTicket))
     {
      // the order already left the book (filled or expired): SyncTrade reads its outcome from the history and,
      // if it was filled, manages the position (time stop, rollover, SL/TP) without telling the detector
      g_log.Info(LevelTag(k) + "cancel (" + BfReasonName(it.reason) + "): the order already left the book");
      return;
     }
   g_ctx.lv[k].cancelWanted = true;
   g_log.Error(LevelTag(k) + "could not delete the pending order: " + g_trade.lastError + " (retried on the next ticks)");
  }

// One decision: the PLACE_LIMIT intents of one setup (spec s.8 "Placement of one decision")
void ExecBatch(const BfIntent &its[], const int n)
  {
   int      j;
   int      k;
   int      sent     = 0;
   int      id       = its[0].id;
   int      dir      = its[0].dir;
   double   SL       = g_trade.NormalizePrice(its[0].SL);
   double   TP       = g_trade.NormalizePrice(its[0].TP);
   double   tick     = (g_bp.tickSize > 0.0) ? g_bp.tickSize : g_trade.TickSize();
   double   budget   = 0.0;
   double   sumPlan  = 0.0;
   double   P[BF_NLEV];
   double   lots[BF_NLEV];
   double   plan[BF_NLEV];
   double   ref[BF_NLEV];
   bool     mkt[BF_NLEV];
   bool     ok;
   ulong    ticket;
   string   wait     = "";
   string   why      = "";
   string   cmt;
   string   tag      = "#" + IntegerToString(id) + " ";
   MqlTick  q;
   datetime expiry;

   ZeroMemory(q);
   //--- account not confirmed yet (terminal reconnecting, login unknown): transient -> decide again later
   if(g_trade.AccountPending())
     {
      g_nRetry++;
      g_lastWait = "account not confirmed (" + g_trade.modeNote + ")";
      g_log.Info(tag + "orders not sent now: " + g_lastWait + "; the setup decides again on a later bar");
      g_det.NotifyRetry(id);
      return;
     }
   //--- REAL account: log-only. The levels end DROP(ORDER_FAILED).
   if(!g_trade.tradingAllowed)
     {
      g_nLogOnly++;
      for(j = 0; j < n; j++)
        {
         g_log.Info(tag + "LOG-ONLY (" + g_trade.modeNote + "): " + ((dir > 0) ? "BUY" : "SELL") + " LIMIT L" +
                    IntegerToString(its[j].k) + " P=" + Px(its[j].P) + " SL=" + Px(its[j].SL) + " TP=" + Px(its[j].TP) +
                    " not sent");
         g_det.NotifyCancelled(id, its[j].k, BF_R_ORDER_FAILED);
        }
      return;
     }
   //--- global checks: any failure -> nothing is sent, the setup decides again on a later bar (NotifyRetry)
   if(!g_trade.TradePermission(why))
      wait = "trading not permitted: " + why;
   else
      if(!SlotFree())
         wait = "slot busy (an order or position of this EA exists)";
      else
         if(g_trade.Breaker())
            wait = "order-error breaker (3 refused decisions; resets after 30 min) - last error: " + g_trade.lastError;
         else
            if(InRolloverWindow())
               wait = "16:44-17:00 New York (no new order over the rollover)";
            else
               if(SecondsToRolloverCut() < 120)
                  wait = "less than 2 minutes before the 16:44 New York rollover";
               else
               if(!g_risk.Ready())
                  wait = "daily-risk baseline not ready (account or equity not available yet)";
               else
                  if(!SymbolInfoTick(_Symbol, q) || q.ask <= 0.0 || q.bid <= 0.0)
                     wait = "no tick";
   if(wait == "" && !g_trade.DirectionAllowed(dir))
     {
      for(j = 0; j < n; j++)
         g_det.NotifyCancelled(id, its[j].k, BF_R_ORDER_FAILED);
      g_log.Error(tag + "the symbol's trade mode does not allow " + DirText(dir) + " orders");
      return;
     }
   //--- sizing: equity * risk% split over the enabled levels; lots from |entry - SL| + slippage (spec s.8)
   if(wait == "")
     {
      g_risk.OnTradeEvent(g_ses);
      budget = g_risk.LevelBudget(g_nLevels);
      for(j = 0; j < n; j++)
        {
         P[j]    = g_trade.NormalizePrice(its[j].P);
         mkt[j]  = (dir > 0) ? (q.ask <= P[j]) : (q.bid >= P[j]);
         ref[j]  = mkt[j] ? ((dir > 0) ? q.ask : q.bid) : P[j];
         lots[j] = g_risk.SizeLotsBudget(MathAbs(ref[j] - SL) + (double)g_slipTicks * tick +
                                         (mkt[j] ? (double)g_devPts * _Point : 0.0), budget, plan[j]);
         sumPlan += plan[j];
        }
      if(!g_risk.CheckNewTrade(sumPlan))
         wait = "daily-loss budget (realised loss today + planned risk " + DoubleToString(sumPlan, 2) + " > limit)";
     }
   if(wait != "")
     {
      g_nRetry++;
      g_lastWait = wait;
      g_log.Info(tag + "orders not sent now: " + wait + "; the setup decides again on a later bar");
      g_det.NotifyRetry(id);
      return;
     }
   //--- send, level by level
   ResetCtx(g_ctx);
   g_ctx.active       = true;
   g_ctx.id           = id;
   g_ctx.dir          = dir;
   g_ctx.SL           = SL;
   g_ctx.TP           = TP;
   g_ctx.decisionTime = TimeCurrent();
   g_trade.BeginBatch();                         // at most one breaker strike for the whole decision
   for(j = 0; j < n; j++)
     {
      k = its[j].k - 1;
      if(k < 0 || k >= BF_NLEV)
         continue;
      why = "";
      if(lots[j] <= 0.0)
        {
         g_log.Info(LevelTag(k) + "size below the minimum volume (budget " + DoubleToString(budget, 2) + " " +
                    AccountInfoString(ACCOUNT_CURRENCY) + " for a stop of " + Px(MathAbs(ref[j] - SL)) + "): no order");
         g_det.NotifyCancelled(id, k + 1, BF_R_SIZE_BELOW_MIN);
         continue;
        }
      if(mkt[j])
        {
         if(!g_trade.StopsOk(dir, (dir > 0) ? q.bid : q.ask, SL, TP))
            why = "SL/TP versus the market (stops level, or the price is already beyond a level)";
        }
      else
         if(!g_trade.PendingPriceOk(dir, P[j]))
            why = "limit price inside the stops level of the market";
         else
            if(!g_trade.StopsOk(dir, P[j], SL, TP))
               why = "SL/TP versus the limit price (stops level)";
      if(why == "" && !g_trade.MarginOk(dir, lots[j], ref[j]))
         why = "not enough free margin";
      if(why != "")
        {
         g_log.Info(LevelTag(k) + "order not sent: " + why);
         g_det.NotifyCancelled(id, k + 1, BF_R_ORDER_FAILED);
         continue;
        }
      cmt    = "BF2|" + IntegerToString(id) + "|" + IntegerToString(k + 1);
      ticket = 0;
      if(mkt[j])
        {
         g_log.Info(LevelTag(k) + "limit " + Px(P[j]) + " is already marketable (" +
                    ((dir > 0) ? "ask " + Px(q.ask) : "bid " + Px(q.bid)) + "): sent as a MARKET order");
         ok = g_trade.OpenMarket(dir, lots[j], SL, TP, cmt);
        }
      else
        {
         // safety net only: the detector cancels the order through its own intents
         // server-side expiry, never later than the next 16:44 New York: the broker removes the order even when no
         // tick arrives in 16:44-17:00 (the EA's own deletes need a tick)
         expiry = (datetime)((long)TimeCurrent() + (long)(g_legExp + 3) * (long)PeriodSeconds());
         if((long)expiry > (long)TimeCurrent() + SecondsToRolloverCut())
            expiry = (datetime)((long)TimeCurrent() + SecondsToRolloverCut());
         ok = g_trade.PlaceLimit(dir, lots[j], P[j], SL, TP, expiry, cmt, ticket);
        }
      if(!ok)
        {
         g_log.Error(LevelTag(k) + "order failed: " + g_trade.lastError);
         g_det.NotifyCancelled(id, k + 1, BF_R_ORDER_FAILED);
         continue;
        }
      sent++;
      g_ctx.lv[k].orderTicket = ticket;
      g_ctx.lv[k].P           = P[j];
      g_ctx.lv[k].lots        = lots[j];
      g_ctx.lv[k].planned     = plan[j];
      g_ctx.lv[k].budget      = budget;
      g_ctx.lv[k].entry       = ref[j];
      g_ctx.lv[k].market      = mkt[j];
      g_log.Info(LevelTag(k) + (mkt[j] ? "MARKET " : "LIMIT ") + DirText(dir) + " sent: " + DoubleToString(lots[j], 2) +
                 " lots P=" + Px(ref[j]) + " SL=" + Px(SL) + " TP=" + Px(TP) + " planned risk " +
                 DoubleToString(plan[j], 2) + " " + AccountInfoString(ACCOUNT_CURRENCY));
      if(mkt[j])
        {
         g_ctx.lv[k].state     = BF_XS_OPEN;
         g_ctx.lv[k].fillCheck = true;
         g_ctx.lv[k].posId     = PosIdOfMarketFill();
         g_ctx.lv[k].fillTime  = TimeCurrent();
         g_det.NotifyFilled(id, k + 1);
        }
      else
        {
         g_ctx.lv[k].state = BF_XS_PENDING;
         if(ticket == 0)
            g_log.Error(LevelTag(k) + "the server returned no order ticket: the order will be deleted as untracked");
        }
     }
   g_trade.EndBatch();
   if(sent == 0)
      ResetCtx(g_ctx);
   g_risk.OnTradeEvent(g_ses);
  }

void ExecuteIntents(void)
  {
   int      i;
   int      n  = g_det.IntentCount();
   int      nb = 0;
   BfIntent it;
   BfIntent batch[BF_NLEV];
   BfSetup  ds;
   for(i = 0; i < n; i++)
     {
      if(!g_det.GetIntent(i, it))
         continue;
      if(it.type == BF_EV_CANCEL)
         ExecCancel(it);
      else
         if(it.type == BF_EV_PLACE_LIMIT && nb < BF_NLEV && (nb == 0 || batch[0].id == it.id))
           {
            BfCopyIntent(batch[nb], it);
            nb++;
           }
     }
   g_det.ClearIntents();
   if(nb > 0)
     {
      // draw the decided Fibonacci and order lines first: execution may end the setup (log-only, size, refusal)
      if(g_det.GetSetup(batch[0].id, ds))
         DrawFib(ds);
      ExecBatch(batch, nb);
     }
   HandleEvents();                               // DROP / DONE records produced by the Notify calls
  }

//+------------------------------------------------------------------+
//| Closed positions -> trades CSV, detector, risk                   |
//+------------------------------------------------------------------+
string DealReasonText(const long r, const string closeReason)
  {
   if(r == (long)DEAL_REASON_SL)
      return("SL");
   if(r == (long)DEAL_REASON_TP)
      return("TP");
   if(r == (long)DEAL_REASON_EXPERT)
      return((closeReason != "") ? closeReason : "EA");
   if(r == (long)DEAL_REASON_SO)
      return("STOP_OUT");
   if(r == (long)DEAL_REASON_CLIENT || r == (long)DEAL_REASON_MOBILE || r == (long)DEAL_REASON_WEB)
      return("MANUAL");
   return("OTHER");
  }

// The position posId is closed: one trades-CSV row (all levels that share it), detector told. false = the closing
// deals are not in the history yet (retried on the next ticks).
bool FinishPosition(const ulong posId)
  {
   int      i;
   int      k;
   int      total;
   ulong    d;
   long     ent;
   long     lastReason = -1;
   double   pnl    = 0.0;
   double   vIn    = 0.0;
   double   vOut   = 0.0;
   double   pxIn   = 0.0;
   double   pxOut  = 0.0;
   double   vol;
   double   px;
   double   plan   = 0.0;
   double   R      = 0.0;
   datetime tIn    = 0;
   datetime tOut   = 0;
   bool     anyOut = false;
   string   levels = "";
   string   cr     = "";
   string   reason;
   string   line;
   double   step   = g_trade.VolumeStep();
   if(posId == 0 || !HistorySelectByPosition((long)posId))
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
            anyOut     = true;
            vOut      += vol;
            pxOut     += px * vol;
            tOut       = (datetime)HistoryDealGetInteger(d, DEAL_TIME);
            lastReason = HistoryDealGetInteger(d, DEAL_REASON);
           }
     }
   if(!anyOut || vOut < vIn - 0.5 * step)
      return(false);
   for(k = 0; k < BF_NLEV; k++)
     {
      if(g_ctx.lv[k].state != BF_XS_OPEN || g_ctx.lv[k].posId != posId)
         continue;
      levels = levels + ((levels == "") ? "" : "+") + IntegerToString(k + 1);
      plan  += g_ctx.lv[k].planned;
      if(cr == "")
         cr = g_ctx.lv[k].closeReason;
     }
   reason = DealReasonText(lastReason, cr);
   if(plan > 0.0)
      R = pnl / plan;
   // BFEA2_trades row: id,levels,dir,entry_time,entry,lots,SL,TP,exit_time,exit,exit_reason,pnl,R,planned_risk
   line = IntegerToString(g_ctx.id) + "," + levels + "," + IntegerToString(g_ctx.dir) + "," + CBfLogger::Ts(tIn) + "," +
          ((vIn > 0.0) ? DoubleToString(pxIn / vIn, _Digits + 2) : "") + "," + DoubleToString(vIn, 2) + "," +
          Px(g_ctx.SL) + "," + Px(g_ctx.TP) + "," + CBfLogger::Ts(tOut) + "," +
          ((vOut > 0.0) ? DoubleToString(pxOut / vOut, _Digits + 2) : "") + "," + reason + "," +
          DoubleToString(pnl, 2) + "," + ((plan > 0.0) ? DoubleToString(R, 3) : "") + "," +
          ((plan > 0.0) ? DoubleToString(plan, 2) : "");
   g_log.TradeRow(line);
   g_log.Info("#" + IntegerToString(g_ctx.id) + " L" + levels + " " + DirText(g_ctx.dir) + " CLOSED " + reason + " pnl " +
              DoubleToString(pnl, 2) + " " + AccountInfoString(ACCOUNT_CURRENCY) +
              ((plan > 0.0) ? " R=" + DoubleToString(R, 2) : "") + " | " + CBfLogger::Ts(tOut));
   g_lastEvent = "#" + IntegerToString(g_ctx.id) + " L" + levels + " CLOSED " + reason + " " + CBfLogger::Ts(tOut);
   if(plan > 0.0)
     {
      g_sumR += R;
      g_nR++;
     }
   for(k = 0; k < BF_NLEV; k++)
     {
      if(g_ctx.lv[k].state != BF_XS_OPEN || g_ctx.lv[k].posId != posId)
         continue;
      g_ctx.lv[k].state = BF_XS_DONE;
      if(!g_ctx.lv[k].cancelled)
         g_det.NotifyClosed(g_ctx.id, k + 1);
     }
   g_risk.OnTradeEvent(g_ses);
   return(true);
  }

//+------------------------------------------------------------------+
//| Every tick: fills, closures, cancel retries (spec s.8)           |
//+------------------------------------------------------------------+
void SyncTrade(void)
  {
   int    k;
   int    reason;
   long   state;
   ulong  tk;
   ulong  pid;
   double vi;
   double vc;
   bool   found;
   if(!g_ctx.active)
      return;
   for(k = 0; k < BF_NLEV; k++)
     {
      if(g_ctx.lv[k].state == BF_XS_PENDING)
        {
         if(g_ctx.lv[k].orderTicket == 0)
           {
            g_ctx.lv[k].tries++;
            if(g_ctx.lv[k].tries > 20)
              {
               g_ctx.lv[k].state = BF_XS_DONE;    // untracked: Reconcile deletes the order / adopts a fill
               if(!g_ctx.lv[k].cancelled)
                  g_det.NotifyCancelled(g_ctx.id, k + 1, BF_R_ORDER_FAILED);
              }
            continue;
           }
         if(OrderSelect(g_ctx.lv[k].orderTicket))
           {
            if(g_ctx.lv[k].cancelWanted || (InRolloverWindow() && !g_ctx.lv[k].partialDel))
              {
               if(!MgmtAllowed() || !RetryDue(g_ctx.lv[k].lastTry))
                  continue;
               if(!g_ctx.lv[k].cancelWanted)
                 {
                  // 16:44-17:00 New York (whatever InpUseSession / InpCancelAtSessionEnd / InpFlatBeforeRollover are):
                  // no pending order over the rollover (a fill there would be closed at once by the 16:44 flat, or
                  // with the flat OFF would open in the rollover spread)
                  g_ctx.lv[k].cancelWanted = true;
                  g_nRollDel++;
                  g_log.Info(LevelTag(k) + "16:44-17:00 New York ROLLOVER: the pending order is deleted (this is the " +
                             "rollover rule, not the 14:45 session end; recorded with reason SESSION_END)");
                  if(!g_ctx.lv[k].cancelled)
                    {
                     g_ctx.lv[k].cancelled = true;
                     g_det.NotifyCancelled(g_ctx.id, k + 1, BF_R_SESSION_END);
                    }
                 }
               if(g_trade.DeleteOrder(g_ctx.lv[k].orderTicket))
                 {
                  g_log.Info(LevelTag(k) + "pending order deleted (retry)");
                  g_ctx.lv[k].cancelWanted = false;
                  g_ctx.lv[k].state        = BF_XS_DONE;
                 }
               continue;
              }
            // a partly filled limit: the rest is deleted, the filled part is read from the history below
            vi = OrderGetDouble(ORDER_VOLUME_INITIAL);
            vc = OrderGetDouble(ORDER_VOLUME_CURRENT);
            if(vc < vi - 1e-9 && !g_ctx.lv[k].partialDel && MgmtAllowed() && RetryDue(g_ctx.lv[k].lastTry))
              {
               // retried (throttled) until the rest is deleted; ManagePositions applies the time stop meanwhile
               if(g_trade.DeleteOrder(g_ctx.lv[k].orderTicket))
                 {
                  g_ctx.lv[k].partialDel = true;
                  g_log.Info(LevelTag(k) + "partly filled (" + DoubleToString(vi - vc, 2) + " of " +
                             DoubleToString(vi, 2) + " lots): the rest was deleted");
                 }
              }
            continue;                            // still in the book
           }
         //--- the order left the book: filled (fully or partly), expired, cancelled or rejected
         found = (HistorySelect((datetime)((long)g_ctx.decisionTime - 86400), (datetime)((long)TimeCurrent() + 3600)) &&
                  HistoryOrderSelect(g_ctx.lv[k].orderTicket));
         if(!found)
           {
            g_ctx.lv[k].tries++;
            if(g_ctx.lv[k].tries < 20)
               continue;                         // history not ready yet
            state = -1;
            vi    = 0.0;
            vc    = 0.0;
            pid   = 0;
           }
         else
           {
            state = HistoryOrderGetInteger(g_ctx.lv[k].orderTicket, ORDER_STATE);
            vi    = HistoryOrderGetDouble(g_ctx.lv[k].orderTicket, ORDER_VOLUME_INITIAL);
            vc    = HistoryOrderGetDouble(g_ctx.lv[k].orderTicket, ORDER_VOLUME_CURRENT);
            pid   = (ulong)HistoryOrderGetInteger(g_ctx.lv[k].orderTicket, ORDER_POSITION_ID);
           }
         g_ctx.lv[k].tries = 0;
         if(found && (state == (long)ORDER_STATE_FILLED || vi - vc > 1e-9))
           {
            g_ctx.lv[k].state    = BF_XS_OPEN;
            g_ctx.lv[k].posId    = (pid > 0) ? pid : g_ctx.lv[k].orderTicket;
            g_ctx.lv[k].fillTime = TimeCurrent();
            if(g_trade.SelectPositionById(g_ctx.lv[k].posId, tk) && PositionSelectByTicket(tk))
              {
               g_ctx.lv[k].posSeen  = true;
               g_ctx.lv[k].fillTime = (datetime)PositionGetInteger(POSITION_TIME);
               g_ctx.lv[k].entry    = PositionGetDouble(POSITION_PRICE_OPEN);
              }
            g_ctx.lv[k].lots = vi - vc;
            if(!g_ctx.lv[k].cancelled)
               g_det.NotifyFilled(g_ctx.id, k + 1);
            g_log.Info(LevelTag(k) + DirText(g_ctx.dir) + " FILLED " + DoubleToString(vi - vc, 2) + " lots" +
                       (g_ctx.lv[k].posSeen ? " at " + Px(g_ctx.lv[k].entry) : "") + " SL=" + Px(g_ctx.SL) + " TP=" +
                       Px(g_ctx.TP) + (g_ctx.lv[k].cancelled ? " (after its cancel: managed without the setup)" : ""));
            g_lastEvent = LevelTag(k) + "FILLED " + CBfLogger::Ts(TimeCurrent());
            g_risk.OnTradeEvent(g_ses);
            continue;
           }
         reason = (state == (long)ORDER_STATE_EXPIRED) ? BF_R_EXPIRED : BF_R_ORDER_FAILED;
         g_ctx.lv[k].state = BF_XS_DONE;
         if(!g_ctx.lv[k].cancelled)
           {
            g_log.Info(LevelTag(k) + "pending order left the book without a fill (" + BfReasonName(reason) + ")");
            g_det.NotifyCancelled(g_ctx.id, k + 1, reason);
           }
         continue;
        }
      if(g_ctx.lv[k].state == BF_XS_OPEN)
        {
         if(g_ctx.lv[k].posId > 0 && g_trade.SelectPositionById(g_ctx.lv[k].posId, tk))
           {
            if(!g_ctx.lv[k].posSeen && PositionSelectByTicket(tk))
              {
               g_ctx.lv[k].posSeen  = true;
               g_ctx.lv[k].fillTime = (datetime)PositionGetInteger(POSITION_TIME);
               g_ctx.lv[k].entry    = PositionGetDouble(POSITION_PRICE_OPEN);
              }
            continue;                            // still open
           }
         if(g_ctx.lv[k].posId == 0)
           {
            // a market fill whose deal was not in the history: take the untracked position of this EA
            if(g_trade.SelectPosition(tk) && PositionSelectByTicket(tk) &&
               !IsTracked((ulong)PositionGetInteger(POSITION_IDENTIFIER)))
               g_ctx.lv[k].posId = (ulong)PositionGetInteger(POSITION_IDENTIFIER);
            g_ctx.lv[k].tries++;
            if(g_ctx.lv[k].tries <= 50)
               continue;
           }
         if(FinishPosition(g_ctx.lv[k].posId))
            continue;
         g_ctx.lv[k].tries++;
         if(g_ctx.lv[k].tries > 50)
           {
            g_log.Error(LevelTag(k) + "closed position not found in the history; the level is reset");
            g_ctx.lv[k].state = BF_XS_DONE;
            if(!g_ctx.lv[k].cancelled)
               g_det.NotifyClosed(g_ctx.id, k + 1);
           }
        }
     }
   HandleEvents();
   if(!CtxBusy())
      ResetCtx(g_ctx);
  }

//+------------------------------------------------------------------+
//| Every tick: positions / orders of this EA that no level owns     |
//+------------------------------------------------------------------+
void Reconcile(void)
  {
   int   i;
   ulong tk;
   ulong id;
   long  now;
   for(i = PositionsTotal() - 1; i >= 0; i--)
     {
      tk = PositionGetTicket(i);
      if(tk == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagic)
         continue;
      id = (ulong)PositionGetInteger(POSITION_IDENTIFIER);
      if(IsTracked(id) || FindOrphan(id) >= 0)
         continue;
      AddOrphan(id, (datetime)PositionGetInteger(POSITION_TIME), "not owned by a level: restart or a fill that raced a cancel");
     }
   if(!g_trade.tradingAllowed)
      return;
   now = (long)TimeCurrent();
   if(g_lastStrayDel > 0 && now >= g_lastStrayDel && now - g_lastStrayDel < 5)
      return;
   for(i = OrdersTotal() - 1; i >= 0; i--)
     {
      tk = OrderGetTicket(i);
      if(tk == 0 || !IsOwnPendingOrder())
         continue;
      if(IsTrackedOrder(tk))
         continue;
      g_lastStrayDel = now;
      if(g_trade.DeleteOrder(tk))
         g_log.Info("stray pending order " + IntegerToString((long)tk) + " deleted");
      else
         g_log.Error("stray pending order " + IntegerToString((long)tk) + " not deleted: " + g_trade.lastError +
                     " (retried in 5 s)");
     }
  }

//+------------------------------------------------------------------+
//| Every tick: position management (spec s.8)                       |
//+------------------------------------------------------------------+
bool CloseLevel(const int k, const ulong tk, const string why)
  {
   int j;
   if(!MgmtAllowed() || !RetryDue(g_ctx.lv[k].lastTry))
      return(false);
   if(g_trade.ClosePosition(tk))
     {
      for(j = 0; j < BF_NLEV; j++)
         if(g_ctx.lv[j].state == BF_XS_OPEN && g_ctx.lv[j].posId == g_ctx.lv[k].posId)
            g_ctx.lv[j].closeReason = why;
      g_log.Info(LevelTag(k) + "close at market: " + why);
      return(true);
     }
   g_ctx.lv[k].closeFails++;
   if(g_ctx.lv[k].closeFails <= 3)
      g_log.Error(LevelTag(k) + "close (" + why + ") failed: " + g_trade.lastError + " (retried)");
   return(false);
  }

// market fills only: if lots * (LossPerLot(|fill - SL| + slippage) + 2 * commission) exceeds the level's budget, the
// excess is closed (hedging), or the whole position (netting, or the rest below the minimum volume). true = done.
bool CheckFillRisk(const int k, const ulong ptk)
  {
   double vol;
   double fill;
   double perLot;
   double risk;
   double cut;
   double rest;
   bool   whole;
   if(g_ctx.lv[k].budget <= 0.0 || g_ctx.SL <= 0.0)
      return(true);
   if(!PositionSelectByTicket(ptk))
      return(false);
   vol    = PositionGetDouble(POSITION_VOLUME);
   fill   = PositionGetDouble(POSITION_PRICE_OPEN);
   perLot = g_risk.PerLotRisk(MathAbs(fill - g_ctx.SL) + (double)g_slipTicks * g_trade.TickSize());
   if(perLot <= 0.0 || vol <= 0.0)
      return(true);
   risk = vol * perLot;
   if(!g_trade.IsHedging())
     {
      // netting: the levels share one position; its risk is compared with the budgets of all levels in it, and the
      // whole position is closed when it is above them (no per-level trim, as in v1)
      double sumBudget = 0.0;
      for(int j = 0; j < BF_NLEV; j++)
         if(g_ctx.lv[j].state == BF_XS_OPEN && g_ctx.lv[j].posId == g_ctx.lv[k].posId)
            sumBudget += g_ctx.lv[j].budget;
      if(risk <= sumBudget + 1e-9)
         return(true);
      if(!g_ctx.lv[k].riskLogged)
        {
         g_ctx.lv[k].riskLogged = true;
         g_log.Error(LevelTag(k) + "netting position risk " + DoubleToString(risk, 2) + " > budget " +
                     DoubleToString(sumBudget, 2) + " after a market fill: closing the position");
        }
      return(CloseLevel(k, ptk, "RISK"));
     }
   if(risk <= g_ctx.lv[k].budget + 1e-9)
      return(true);
   cut   = g_trade.CeilVolume(vol - g_ctx.lv[k].budget / perLot);
   rest  = vol - cut;
   whole = (rest < g_trade.MinVolume() - 1e-12);
   if(!g_ctx.lv[k].riskLogged)
     {
      g_ctx.lv[k].riskLogged = true;
      g_log.Error(LevelTag(k) + "market fill at " + Px(fill) + ": risk " + DoubleToString(risk, 2) + " > budget " +
                  DoubleToString(g_ctx.lv[k].budget, 2) + ": " + (whole ? "closing the position" :
                  "closing " + DoubleToString(cut, 2) + " of " + DoubleToString(vol, 2) + " lots"));
     }
   if(whole)
      return(CloseLevel(k, ptk, "RISK"));
   if(!MgmtAllowed() || !RetryDue(g_ctx.lv[k].lastTry))
      return(false);
   if(g_trade.ClosePartial(ptk, cut))
     {
      g_ctx.lv[k].lots    = rest;
      g_ctx.lv[k].planned = rest * perLot;
      return(true);
     }
   return(false);
  }

void ManagePositions(void)
  {
   int      k;
   ulong    tk;
   datetime now = TimeCurrent();
   if(!g_ctx.active || !g_trade.tradingAllowed)
      return;
   for(k = 0; k < BF_NLEV; k++)
     {
      //--- a pending level that is partly filled (the rest is still being deleted): its position, whose identifier is
      //    the order ticket, gets the time stop and the 16:44 flat from POSITION_TIME (each while its switch is ON)
      if(g_ctx.lv[k].state == BF_XS_PENDING && g_ctx.lv[k].orderTicket > 0 &&
         g_trade.SelectPositionById(g_ctx.lv[k].orderTicket, tk) && PositionSelectByTicket(tk))
        {
         datetime pt = (datetime)PositionGetInteger(POSITION_TIME);
         if((TimeStopDue(pt, now) || RolloverFlatDue(pt, now)) && MgmtAllowed() && RetryDue(g_ctx.lv[k].lastTry))
           {
            if(g_trade.ClosePosition(tk))
               g_log.Info(LevelTag(k) + "partly filled position closed at market (" + DueExitText(pt, now) + ")");
           }
         continue;
        }
      if(g_ctx.lv[k].state != BF_XS_OPEN || g_ctx.lv[k].posId == 0)
         continue;
      if(!g_trade.SelectPositionById(g_ctx.lv[k].posId, tk))
         continue;
      //--- time stop: now >= fill_time + max_hold (<= 120 min); v4: only while InpUseTimeStop is ON
      if(TimeStopDue(g_ctx.lv[k].fillTime, now))
        {
         CloseLevel(k, tk, "TIME");
         continue;
        }
      //--- before the rollover: flat at 16:44 New York; v4: only while InpFlatBeforeRollover is ON
      if(RolloverFlatDue(g_ctx.lv[k].fillTime, now))
        {
         CloseLevel(k, tk, "ROLLOVER");
         continue;
        }
      if(g_ctx.lv[k].fillCheck && CheckFillRisk(k, tk))
         g_ctx.lv[k].fillCheck = false;
     }
  }

void ManageOrphans(void)
  {
   int      i;
   ulong    tk;
   datetime now = TimeCurrent();
   for(i = g_nOrph - 1; i >= 0; i--)
     {
      if(!g_trade.SelectPositionById(g_orph[i].posId, tk))
        {
         g_log.Info("unowned position " + IntegerToString((long)g_orph[i].posId) + " is closed");
         RemoveOrphan(i);
         continue;
        }
      if(!g_trade.tradingAllowed)
         continue;
      if(TimeStopDue(g_orph[i].fillTime, now) || RolloverFlatDue(g_orph[i].fillTime, now))
        {
         if(!MgmtAllowed() || !RetryDue(g_orph[i].lastTry))
            continue;
         if(g_trade.ClosePosition(tk))
            g_log.Info("unowned position " + IntegerToString((long)g_orph[i].posId) + " closed at market (" +
                       DueExitText(g_orph[i].fillTime, now) + ")");
         else
           {
            g_orph[i].closeFails++;
            if(g_orph[i].closeFails <= 3)
               g_log.Error("unowned position " + IntegerToString((long)g_orph[i].posId) + " could not be closed: " +
                           g_trade.lastError + " (retried)");
           }
        }
     }
  }

//+------------------------------------------------------------------+
//| Environment of the detector                                      |
//+------------------------------------------------------------------+
// v3: the late entry window 14:45-16:44 New York, Monday-Friday (InpEntriesAfterSessionEnd)
bool LateEntryOk(const datetime server)
  {
   datetime ny  = g_ses.ServerToNY(server);
   int      dow = CBfSession::DowOf(ny);
   int      m   = CBfSession::MinuteOfDay(ny);
   return(dow >= 1 && dow <= 5 && m >= BF_NY_LAST_MIN && m < BF_NY_FLAT_MIN);
  }

// v3: the cut that keeps pending orders out of the rollover even without a tick in 16:44-17:00 New York: the next
// bar opens at or after 16:44 NY, on a weekend, or in another FX day than the bar that just closed (a data gap)
bool RolloverCut(const datetime nextOpen, const datetime barTime)
  {
   datetime ny  = g_ses.ServerToNY(nextOpen);
   int      dow = CBfSession::DowOf(ny);
   int      m   = CBfSession::MinuteOfDay(ny);
   return(m >= BF_NY_FLAT_MIN || dow == 0 || dow == 6 || g_ses.FxDay(nextOpen) != g_ses.FxDay(barTime));
  }

void BuildEnv(BfEnv &env, const bool warm, const datetime nextOpen, const bool stale, const datetime barTime)
  {
   MqlTick q;
   BfClearEnv(env);
   if(warm)
      return;                                    // warm-up: no decision is possible (all flags false)
   if(SymbolInfoTick(_Symbol, q) && q.ask > 0.0 && q.bid > 0.0)
      env.sp = q.ask - q.bid;                    // spread at the decision moment (first tick of bar u+1)
   env.slotFree       = SlotFree();
   // v3 switches (the detector uses both signals only with InpUseSession = true):
   // - InpEntriesAfterSessionEnd: new orders also from 14:45 to 16:44 New York (the entry window ends at 16:44)
   // - InpCancelAtSessionEnd = false: no cancel when the entry window ends; pending orders stay until they fill, the leg
   //   expires (InpLegExpiryBars), a new extreme re-anchors the setup, or the rollover cut (16:44 New York, weekend,
   //   or a new FX day after a data gap) is reached
   env.sessionEntryOk = g_ses.EntryOk(nextOpen) || (InpEntriesAfterSessionEnd && LateEntryOk(nextOpen));
   if(InpCancelAtSessionEnd)
      // = SessionCancel(nextOpen) with the defaults (v2); with the extended window also a new FX day after a data gap
      env.sessionCancel = !env.sessionEntryOk ||
                          (InpEntriesAfterSessionEnd && g_ses.FxDay(nextOpen) != g_ses.FxDay(barTime));
   else
      env.sessionCancel = RolloverCut(nextOpen, barTime);
   env.riskOk         = g_risk.RiskOk();         // the order-error breaker is checked (and reported) by ExecBatch
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
   ProcessBar(g_ep, g_state, u, g_o, g_h, g_l, g_c, ev);
   if(!warm)
     {
      DrawDisplBar(u);
      if(g_renderOn && InpShowDisplacement && u - g_displBars >= 0)
         g_render.DisplDelete(IntegerToString((long)g_t[u - g_displBars]));
     }
   if(!g_tradeLogic)
      return;                                    // IFVG: display only
   BuildEnv(env, warm, nextOpen, stale, g_t[u]);
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
//| Rendering                                                        |
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
   int    k;
   string s = "";
   string one;
   if(!g_ctx.active)
      return((g_nOrph > 0) ? "none (" + IntegerToString(g_nOrph) + " unowned position(s) managed)" : "none");
   for(k = 0; k < BF_NLEV; k++)
     {
      one = "";
      if(g_ctx.lv[k].state == BF_XS_PENDING)
         one = "L" + IntegerToString(k + 1) + " limit " + Px(g_ctx.lv[k].P);
      else
         if(g_ctx.lv[k].state == BF_XS_OPEN)
            one = "L" + IntegerToString(k + 1) + " open " + DoubleToString(g_ctx.lv[k].lots, 2) + " @ " +
                  Px(g_ctx.lv[k].entry);
      if(one != "")
         s = s + ((s == "") ? "" : " | ") + one;
     }
   return("#" + IntegerToString(g_ctx.id) + " " + DirText(g_ctx.dir) + " SL " + Px(g_ctx.SL) + " TP " + Px(g_ctx.TP) +
          ": " + s + ((g_nOrph > 0) ? " | +" + IntegerToString(g_nOrph) + " unowned" : ""));
  }

int St(const int code)
  {
   return(g_det.StatValue(code));
  }

// diagnostics rows (panel and Experts log): why setups do or do not become orders
string DiagFunnel(void)
  {
   return("funnel: BPRs " + IntegerToString(St(BF_STAT_ARMED)) + " | touches " + IntegerToString(St(BF_STAT_TOUCH)) +
          " | breakouts " + IntegerToString(St(BF_STAT_BREAKOUT)) + " (failed " + IntegerToString(St(BF_STAT_BRK_FAIL)) +
          ") | confirmed " + IntegerToString(St(BF_STAT_CONFIRM)) + " | entry decisions " +
          IntegerToString(St(BF_STAT_PLACE)) + " (orders accepted " + IntegerToString(g_trade.nSent) + ") | closed " +
          IntegerToString(St(BF_STAT_CLOSED)));
  }

string DiagSkips(void)
  {
   return("entries skipped: missed " + IntegerToString(St(BF_STAT_SKIP + BF_R_MISSED)) + " cost " +
          IntegerToString(St(BF_STAT_SKIP + BF_R_COST)) + " rr " + IntegerToString(St(BF_STAT_SKIP + BF_R_RR)) +
          " bad " + IntegerToString(St(BF_STAT_SKIP + BF_R_BAD_LEVEL)) + " | dropped: size " +
          IntegerToString(St(BF_STAT_DROP + BF_R_SIZE_BELOW_MIN)) + " refused " +
          IntegerToString(St(BF_STAT_DROP + BF_R_ORDER_FAILED)) + " expired " +
          IntegerToString(St(BF_STAT_DROP + BF_R_EXPIRED)));
  }

string DiagWaits(void)
  {
   return("waiting: no FVG " + IntegerToString(St(BF_STAT_NO_FVG)) + " bars | blocked: session " +
          IntegerToString(St(BF_STAT_BLK_SESS)) + " slot " + IntegerToString(St(BF_STAT_BLK_SLOT)) + " daily-risk " +
          IntegerToString(St(BF_STAT_BLK_RISK)) + " spread/catch-up " + IntegerToString(St(BF_STAT_BLK_SPRD)) +
          (g_trade.Breaker() ? " | BREAKER TRIPPED" : "") + " | retried " +
          IntegerToString(g_nRetry) + " | re-anchored " + IntegerToString(St(BF_STAT_REANCHOR)));
  }

string DiagEnded(void)
  {
   return("ended: broken " + IntegerToString(St(BF_STAT_DONE + BF_R_BROKEN)) + " broken-at-start " +
          IntegerToString(St(BF_STAT_DONE + BF_R_BROKEN_AT_CREATION)) + " expired " + IntegerToString(g_nExpPre) +
          " before / " + IntegerToString(g_nExpLeg) + " after the breakout | touch limit " +
          IntegerToString(St(BF_STAT_DONE + BF_R_TOUCH_LIMIT)) + " leg broken " +
          IntegerToString(St(BF_STAT_DONE + BF_R_LEG_BROKEN)) + " no level " +
          IntegerToString(St(BF_STAT_DONE + BF_R_NO_LEVEL)) + " session " +
          IntegerToString(St(BF_STAT_DONE + BF_R_SESSION_END)) + " (rollover order deletes " +
          IntegerToString(g_nRollDel) + ") refused " +
          IntegerToString(St(BF_STAT_DONE + BF_R_ORDER_FAILED)) + " size " +
          IntegerToString(St(BF_STAT_DONE + BF_R_SIZE_BELOW_MIN)) + " geometry " +
          IntegerToString(St(BF_STAT_DONE + BF_R_BAD_GEOMETRY)) + " capacity " +
          IntegerToString(St(BF_STAT_DONE + BF_R_CAPACITY)));
  }

string DiagOrders(void)
  {
   return("orders: accepted " + IntegerToString(g_trade.nSent) + " refused " + IntegerToString(g_trade.nFailed) +
          ((g_trade.lastFilling != "") ? " | filling " + g_trade.lastFilling : "") +
          ((g_nLogOnly > 0) ? " | log-only decisions " + IntegerToString(g_nLogOnly) : "") +
          ((g_trade.lastError != "") ? " | last error: " + g_trade.lastError : "") +
          ((g_lastWait != "") ? " | last wait: " + g_lastWait : ""));
  }

void LogDiagnostics(const string when)
  {
   if(!g_tradeLogic)
      return;
   g_log.Info("DIAG " + when + " | " + DiagFunnel());
   g_log.Info("DIAG " + when + " | " + DiagSkips());
   g_log.Info("DIAG " + when + " | " + DiagWaits());
   g_log.Info("DIAG " + when + " | " + DiagEnded());
   g_log.Info("DIAG " + when + " | " + DiagOrders());
  }

// v3 switches as one line (panel, start log, self-check)
string FiltersText(void)
  {
   string cost = !InpUseCostFilter ? "OFF (switch)" : ((g_maxCostR > 0.0) ? "<= " + DoubleToString(g_maxCostR, 2) + " R" :
                                                       "off (InpMaxCostR = 0)");
   string rr   = !InpUseRRFilter ? "OFF (switch)" : ((g_minRR > 0.0) ? ">= " + DoubleToString(g_minRR, 2) :
                                                   "off (InpMinRR = 0)");
   string win  = !InpUseSession ? "OFF (any time)" :
                 (InpEntriesAfterSessionEnd ? "08:00 LDN-16:44 NY" : "08:00 LDN-14:45 NY");
   string canc = !InpUseSession ? "off (InpUseSession = false)" :
                 (InpCancelAtSessionEnd ? "ON (at the end of the entry window)" : "OFF (switch)");
   return("switches: cost filter " + cost + " | RR filter " + rr + " | entry window " + win +
          " | cancel at window end " + canc + " | rollover order deletes " + IntegerToString(g_nRollDel));
  }

// v4 exit switches as one line (panel, start log, self-check)
string ExitsText(void)
  {
   return("exits: server SL/TP | time stop " + (InpUseTimeStop ? IntegerToString(g_maxHold) + " min" : "OFF (switch)") +
          " | 16:44 New York flat " + (InpFlatBeforeRollover ? "ON" : "OFF (switch)") +
          ((InpUseTimeStop && InpFlatBeforeRollover) ? "" : " | NOT a research trial (H-14 exits changed)"));
  }

void UpdatePanel(void)
  {
   string perm = "";
   if(!g_renderOn || !InpShowPanel)
      return;
   g_trade.TradePermission(perm);
   g_permWhy = perm;
   g_render.PanelSet(0, "BprFvgEA v4 " + _Symbol + " " + TfName() + " | mode: " + g_trade.modeNote + " | algo trading: " +
                     ((perm == "") ? "ON" : "OFF - " + perm));
   g_render.PanelSet(1, "rules: touches <= " + IntegerToString(g_maxTouches) + ", " + IntegerToString(g_confirm) +
                     " closes" + (InpRejectBeforeBreak ? " after a rejection" : "") + ", FVG " + FvgRuleText() + " | entries " + FibText(g_fib[0]) + " " + FibText(g_fib[1]) + " " +
                     FibText(g_fib[2]) + " | SL " + FibText(g_stopFib) + "+" + IntegerToString(g_stopBuf) + "t TP " +
                     FibText(g_tgtFib) + " | " + DirectionText() + (g_tradeLogic ? "" : " | IFVG: display only"));
   g_render.PanelSet(2, FiltersText());
   g_render.PanelSet(3, ExitsText());
   g_render.PanelSet(4, "tracking: wait " + IntegerToString(g_det.PhaseCount(BF_PH_WAIT)) + " zone " +
                     IntegerToString(g_det.PhaseCount(BF_PH_ZONE)) + " breakout " +
                     IntegerToString(g_det.PhaseCount(BF_PH_BREAK)) + " leg " +
                     IntegerToString(g_det.PhaseCount(BF_PH_LEG)) + " ordered " +
                     IntegerToString(g_det.PhaseCount(BF_PH_ORDERED)) + " filled " +
                     IntegerToString(g_det.PhaseCount(BF_PH_FILLED)));
   g_render.PanelSet(5, DiagFunnel());
   g_render.PanelSet(6, DiagSkips());
   g_render.PanelSet(7, DiagWaits());
   g_render.PanelSet(8, DiagEnded());
   g_render.PanelSet(9, DiagOrders());
   g_render.PanelSet(10, "orders/positions: " + CtxText());
   g_render.PanelSet(11, "today: " + DoubleToString(g_risk.RealisedToday(), 2) + " " + AccountInfoString(ACCOUNT_CURRENCY) +
                     " | lockout: " + (g_risk.Lockout() ? "YES" : "no") + " | positions " +
                     IntegerToString(g_risk.TradesToday()) + " | last: " + g_lastEvent);
   g_render.PanelDraw();
  }

//+------------------------------------------------------------------+
//| FX day (17:00 New York): risk day, breaker reset                 |
//+------------------------------------------------------------------+
void DayCheck(void)
  {
   long fx     = g_ses.FxDay(TimeCurrent());
   bool tester = ((bool)MQLInfoInteger(MQL_TESTER) || (bool)MQLInfoInteger(MQL_OPTIMIZATION));
   bool first  = (g_fxDay < 0);
   if(fx == g_fxDay)
      return;
   if(!tester && (!(bool)TerminalInfoInteger(TERMINAL_CONNECTED) || AccountInfoInteger(ACCOUNT_LOGIN) <= 0))
      return;
   if(AccountInfoDouble(ACCOUNT_EQUITY) <= 0.0)
      return;
   if(!g_risk.UpdateDay(fx, g_ses))
      return;
   g_fxDay = fx;
   g_trade.ResetBreaker();
   if(!first && g_ready)
      LogDiagnostics("new FX day");
  }

//+------------------------------------------------------------------+
//| Start-up self-check (Experts log): everything that can stop an   |
//| order from being placed                                          |
//+------------------------------------------------------------------+
void SelfCheck(void)
  {
   string   perm      = "";
   int      fill      = (int)SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   int      expm      = (int)SymbolInfoInteger(_Symbol, SYMBOL_EXPIRATION_MODE);
   double   tick      = g_trade.TickSize();
   double   eq        = AccountInfoDouble(ACCOUNT_EQUITY);
   double   budget    = g_risk.LevelBudget(g_nLevels);
   double   vmin      = g_trade.MinVolume();
   double   vpp       = g_risk.ValuePerPriceUnit();
   double   maxStop   = 0.0;
   datetime dayStart  = (datetime)(((long)TimeCurrent() / 86400) * 86400);
   int      m;
   int      first     = -1;
   int      last      = -1;
   bool     okPrev;
   bool     okNow;
   g_trade.TradePermission(perm);
   g_log.Info("SELF-CHECK account: " + g_trade.modeNote + " | login " + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)) +
              " " + AccountInfoString(ACCOUNT_SERVER) + " | " + (g_trade.IsHedging() ? "hedging" : "NETTING") +
              " | equity " + DoubleToString(eq, 2) + " " + AccountInfoString(ACCOUNT_CURRENCY) + " | leverage 1:" +
              IntegerToString(AccountInfoInteger(ACCOUNT_LEVERAGE)));
   g_log.Info("SELF-CHECK permissions: " + ((perm == "") ? "OK" : "NOT PERMITTED - " + perm) +
              (g_trade.tradingAllowed ? "" : " | account guard: " + g_trade.modeNote + " (no order is sent)"));
   g_log.Info("SELF-CHECK symbol: digits " + IntegerToString(_Digits) + " tick " + DoubleToString(tick, _Digits) +
              " value/1.0 move/lot " + DoubleToString(vpp, 2) + " | stops level " +
              IntegerToString(SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL)) + " pts, freeze level " +
              IntegerToString(SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL)) + " pts | spread now " +
              IntegerToString(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD)) + " pts | filling FOK " +
              (((fill & SYMBOL_FILLING_FOK) != 0) ? "yes" : "no") + " IOC " + (((fill & SYMBOL_FILLING_IOC) != 0) ? "yes" : "no") +
              " (limit orders: CTrade's symbol mode, RETURN if refused) | expiration GTC " + (((expm & SYMBOL_EXPIRATION_GTC) != 0) ? "yes" : "no") +
              " SPECIFIED " + (((expm & SYMBOL_EXPIRATION_SPECIFIED) != 0) ? "yes" : "no"));
   if(vpp > 0.0 && vmin > 0.0 && budget > 0.0)
      maxStop = (budget / vmin - 2.0 * g_commSide) / vpp;
   g_log.Info("SELF-CHECK " + FiltersText());
   g_log.Info("SELF-CHECK " + ExitsText());
   if(!InpUseTimeStop && !InpFlatBeforeRollover)
      g_log.Info("SELF-CHECK note: no time stop and no 16:44 New York flat - a position runs to its SL / TP and may be " +
                 "held over the rollover and the weekend (swap; a gap can fill the stop worse than planned, so a loss " +
                 "can exceed the 0.20 % budget); one setup at a time, so no new setup trades while it is open");
   else
      if(!InpUseTimeStop)
         g_log.Info("SELF-CHECK note: no time stop - a position runs to its SL / TP or is closed at 16:44 New York; " +
                    "one setup at a time, so no new setup trades while it is open");
      else
         if(!InpFlatBeforeRollover)
            g_log.Info("SELF-CHECK note: no 16:44 New York flat - a position is closed by its SL / TP or the " +
                       IntegerToString(g_maxHold) + "-min time stop, which can fall after 16:44 New York: the position " +
                       "may then be held over the 17:00 New York rollover (swap, triple on Wednesday; rollover " +
                       "spread) and, while the market is closed (daily break, Friday close), until it reopens " +
                       "(weekend, gap risk beyond the 0.20 % budget)");
   if(!InpUseCostFilter || (g_maxCostR <= 0.0))
      g_log.Info("SELF-CHECK note: the cost filter is off - an entry may be placed even when spread + commission + " +
                 "slippage are a large part of its risk (small Fibonacci legs)");
   g_log.Info("SELF-CHECK risk: " + DoubleToString(g_riskPct, 2) + "% per setup = " + DoubleToString(budget, 2) + " " +
              AccountInfoString(ACCOUNT_CURRENCY) + " per entry (" + IntegerToString(g_nLevels) + " entries) | volume min " +
              DoubleToString(vmin, 2) + " step " + DoubleToString(g_trade.VolumeStep(), 2) +
              ((maxStop > 0.0) ? " | the minimum volume fits a stop of at most " + DoubleToString(maxStop, _Digits) +
               " price units (wider stops -> SIZE_BELOW_MIN)" : " | the minimum volume does not fit the budget: " +
               "every entry gets SIZE_BELOW_MIN (raise the deposit)"));
   if(InpUseSession)
     {
      // the first window that STARTS on this server date; its end may be on the next date (it can cross midnight)
      okPrev = SessionOkAt((datetime)((long)dayStart - 60));
      for(m = 0; m < 1440 && first < 0; m++)
        {
         okNow = SessionOkAt((datetime)((long)dayStart + (long)m * 60));
         if(okNow && !okPrev)
            first = m;
         okPrev = okNow;
        }
      if(first >= 0)
        {
         last = first;
         while(last + 1 < 2880 && SessionOkAt((datetime)((long)dayStart + (long)(last + 1) * 60)))
            last++;
         g_log.Info("SELF-CHECK session (" + EnumToString(InpServerMode) + "): entries on " +
                    TimeToString(dayStart, TIME_DATE) + " from " + StringFormat("%02d:%02d", first / 60, first % 60) +
                    " to " + StringFormat("%02d:%02d", (last % 1440) / 60, (last % 1440) % 60) +
                    ((last >= 1440) ? " (+1 day)" : "") + " server time; check that this is 08:00 London .. " +
                    (InpEntriesAfterSessionEnd ? "16:44" : "14:45") + " New York for your broker (InpServerMode)");
        }
      else
         g_log.Info("SELF-CHECK session: no entry window starts on " + TimeToString(dayStart, TIME_DATE) + " (weekend)");
     }
   else
      g_log.Info("SELF-CHECK session: off (entries at any time)");
  }

//+------------------------------------------------------------------+
//| Warm-up                                                          |
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
                 " requested bars were available (this does not block trading)");
   SelfCheck();
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
//| skipped                                                          |
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
      ProcessClosed(g_n - 1, false, nextOpen, nextOpen != formTime);
     }
   return(true);
  }

//+------------------------------------------------------------------+
//| Restart recovery                                                 |
//+------------------------------------------------------------------+
// fromInit: called from OnInit (the context starts empty). Otherwise it runs again on the first tick on which trading
// is permitted (the account was not known at OnInit).
void RecoverState(const bool fromInit)
  {
   int   i;
   ulong tk;
   if(fromInit)
     {
      ResetCtx(g_ctx);
      g_nOrph = 0;
      ArrayResize(g_orph, 0, 8);
     }
   //--- pending orders left from before the restart belong to setups the new detector does not know: deleted
   for(i = OrdersTotal() - 1; i >= 0; i--)
     {
      tk = OrderGetTicket(i);
      if(tk == 0 || !IsOwnPendingOrder())
         continue;
      if(IsTrackedOrder(tk))
         continue;
      if(g_trade.tradingAllowed)
        {
         if(g_trade.DeleteOrder(tk))
            g_log.Info("restart: deleted the pending order " + IntegerToString((long)tk) + " left from before");
         else
            g_log.Error("restart: could not delete the pending order " + IntegerToString((long)tk) + ": " +
                        g_trade.lastError + " (Reconcile retries it)");
        }
      else
         g_log.Info("restart: pending order " + IntegerToString((long)tk) + " found; " + g_trade.modeNote +
                    " leaves it alone");
     }
   //--- positions with this EA's magic number: managed as unowned positions (Reconcile)
   Reconcile();
  }

string RunStamp(void)
  {
   return(TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS));
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

   g_ses.Init((int)InpServerMode, g_serverOffH);
   g_trade.Init(_Symbol, InpMagic, g_devPts, 3);  // account guard evaluated (fail closed), re-checked on every tick
   BuildParams();
   g_risk.Init(_Symbol, InpMagic, g_riskPct, g_dayLossPct, g_commSide, g_maxTradesDay);
   g_runText = RunStamp();
   g_log.Init(InpLogCsv && !optim, tester, optim, _Symbol, TfName(), InpMagic, g_runText);
   g_render.Init(InpShowZones, InpShowBPR, InpShowFVGinBPRmode, ((int)InpFib == BF_FIB_BPR), InpFibExtend,
                 InpShowDisplacement, InpShowSetups, InpShowPanel, InpBullColor, InpBullBreakColor, InpBearColor,
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
   g_lastStrayDel = 0;
   g_nRetry       = 0;
   g_lastWait     = "";
   g_nLogOnly     = 0;
   g_nRollDel     = 0;
   g_nExpPre      = 0;
   g_nExpLeg      = 0;
   g_recoveryLive = g_trade.tradingAllowed;
   ResetState(g_state, g_ep);
   ResetState(g_tmp, g_ep);

   if(!g_tradeLogic)
      g_log.Error("InpFvgType = IFVG: setups need FVG. The EA draws the zones only; trading is disabled.");
   g_log.Info("start v4: " + _Symbol + " " + TfName() + " | mode " + g_trade.modeNote + " | BPR rejection -> breakout -> " +
              "fib entries " + FibText(g_fib[0]) + "/" + FibText(g_fib[1]) + "/" + FibText(g_fib[2]) + ", touches <= " +
              IntegerToString(g_maxTouches) + ", " + IntegerToString(g_confirm) + " closes, FVG " + FvgRuleText() +
              ", direction " + DirectionText() + " | risk " + DoubleToString(g_riskPct, 2) + "% per setup, daily " +
              DoubleToString(g_dayLossPct, 2) + "% | hypothesis H-14 (untested)");
   g_log.Info("start v4: " + FiltersText());
   g_log.Info("start v4: " + ExitsText());
   if(InpLogCsv && !optim)
      g_log.Info("CSV logs (Common Files folder): " + g_log.SetupsFile() + ", " + g_log.TradesFile() + " | run " +
                 g_runText);

   RecoverState(true);
   DoWarmup();                                   // retried on the next ticks while the history is not ready
   return(INIT_SUCCEEDED);
  }

// A raw market close of position ticket tk (CTrade refuses to trade once the program is stopping)
void ClosePositionRaw(const ulong tk)
  {
   MqlTradeRequest rq;
   MqlTradeResult  rs;
   MqlTick         q;
   int             fill = (int)SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   bool            buy;
   if(!PositionSelectByTicket(tk) || !SymbolInfoTick(_Symbol, q))
      return;
   buy = (PositionGetInteger(POSITION_TYPE) == (long)POSITION_TYPE_BUY);
   ZeroMemory(rq);
   ZeroMemory(rs);
   rq.action    = TRADE_ACTION_DEAL;
   rq.position  = tk;
   rq.symbol    = _Symbol;
   rq.volume    = PositionGetDouble(POSITION_VOLUME);
   rq.type      = buy ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
   rq.price     = buy ? q.bid : q.ask;
   rq.deviation = (ulong)g_devPts;
   rq.magic     = (ulong)InpMagic;
   rq.comment   = "BF2 stop";
   if((fill & SYMBOL_FILLING_FOK) != 0)
      rq.type_filling = ORDER_FILLING_FOK;
   else
      if((fill & SYMBOL_FILLING_IOC) != 0)
         rq.type_filling = ORDER_FILLING_IOC;
      else
         rq.type_filling = ORDER_FILLING_RETURN;
   if(OrderSend(rq, rs) && (rs.retcode == TRADE_RETCODE_DONE || rs.retcode == TRADE_RETCODE_DONE_PARTIAL))
      g_log.Info("stop: closed position " + IntegerToString((long)tk) + " (EA removed: " + MarketExitsText() +
                 " would no longer run)");
   else
      g_log.Error("stop: could not close position " + IntegerToString((long)tk) + " (retcode " +
                  IntegerToString((long)rs.retcode) + " " + rs.comment + ") - CLOSE IT MANUALLY");
  }

void OnDeinit(const int reason)
  {
   int             i;
   int             n;
   ulong           tk      = 0;
   bool            tester  = ((bool)MQLInfoInteger(MQL_TESTER) || (bool)MQLInfoInteger(MQL_OPTIMIZATION));
   bool            canSend = false;
   string          note    = "";
   MqlTradeRequest rq;
   MqlTradeResult  rs;
   BfSetup         s;
   BfEvent         e;
   //--- setups still open at exit get a row with their current state
   if(g_ready && g_tradeLogic)
     {
      LogDiagnostics("end");
      n = g_det.TrackedCount();
      for(i = 0; i < n; i++)
        {
         if(!g_det.GetTracked(i, s))
            continue;
         BfClearEvent(e);
         e.id = s.id;
         e.dir = s.dir;
         e.created = s.created;
         e.B = s.B;
         e.T = s.T;
         e.touches = s.touches;
         e.lvl = s.lvl;
         e.ref = s.ref;
         e.brkBar = s.brkBar;
         e.confirmBar = s.confirmBar;
         e.decisionBar = s.decisionBar;
         e.phase = s.phase;
         e.snO = s.O;
         e.snX = s.X;
         e.snSL = s.SL;
         e.snTP = s.TP;
         for(int k = 0; k < BF_NLEV; k++)
           {
            e.snLvSt[k]  = s.lvSt[k];
            e.snLvP[k]   = s.lvP[k];
            e.snLvRsn[k] = s.lvRsn[k];
           }
         g_log.SetupRow(SetupCsv(e));
        }
     }
   if(!tester)
     {
      //--- every pending order of this EA is deleted. A raw request: CTrade refuses to trade once the program stops.
      canSend = g_trade.Permitted();
      note    = canSend ? ": pending orders deleted, positions kept" : ": trading not permitted, nothing sent";
      for(i = OrdersTotal() - 1; i >= 0; i--)
        {
         tk = OrderGetTicket(i);
         if(tk == 0 || !IsOwnPendingOrder())
            continue;
         if(!canSend)
           {
            g_log.Error("stop: pending order " + IntegerToString((long)tk) + " stays in the book (trading not " +
                        "permitted now) - DELETE IT MANUALLY");
            continue;
           }
         ZeroMemory(rq);
         ZeroMemory(rs);
         rq.action = TRADE_ACTION_REMOVE;
         rq.order  = tk;
         rq.magic  = (ulong)InpMagic;
         if(OrderSend(rq, rs) && (rs.retcode == TRADE_RETCODE_DONE || rs.retcode == TRADE_RETCODE_PLACED))
            g_log.Info("stop: deleted the pending order " + IntegerToString((long)tk));
         else
            g_log.Error("stop: could not delete the pending order " + IntegerToString((long)tk) + " (retcode " +
                        IntegerToString((long)rs.retcode) + " " + rs.comment + ") - DELETE IT MANUALLY");
        }
      //--- removal / chart or terminal close / template / program stop: nothing would run the time stop and the
      //    16:44 flat any more, so this EA's positions are closed (raw requests). Recompile, input change and chart
      //    change keep them: the restarted EA adopts them at once (Reconcile). v4: with both exit switches OFF the
      //    EA has no market exit to run, so the positions are kept with their server SL/TP.
      if(canSend && (InpUseTimeStop || InpFlatBeforeRollover) &&
         (reason == REASON_REMOVE || reason == REASON_CHARTCLOSE || reason == REASON_CLOSE ||
          reason == REASON_TEMPLATE || reason == REASON_PROGRAM))
        {
         for(i = PositionsTotal() - 1; i >= 0; i--)
           {
            tk = PositionGetTicket(i);
            if(tk == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagic)
               continue;
            ClosePositionRaw(tk);
           }
        }
      if(reason != REASON_RECOMPILE && g_trade.SelectPosition(tk))
         g_log.Error("stop (reason " + IntegerToString(reason) + "): position " + IntegerToString((long)tk) +
                     " stays open with its server SL/TP only" + ((InpUseTimeStop || InpFlatBeforeRollover) ?
                     " - " + MarketExitsText() + " will NO LONGER RUN unless the EA runs again on " + _Symbol + " with magic " +
                     IntegerToString(InpMagic) + ". Otherwise close it manually." :
                     " (time stop and 16:44 flat are OFF by the v4 switches)"));
     }
   g_log.Info("stop (reason " + IntegerToString(reason) + ")" + note);
   g_log.Close();
   g_render.DeleteAll();
  }

void OnTick()
  {
   datetime formTime;
   bool     newBar = false;
   //--- account guard (fail closed), re-evaluated on every tick: never latched
   g_trade.Refresh();
   if(g_trade.tradingAllowed && !g_recoveryLive)
     {
      g_recoveryLive = true;
      g_log.Info("account confirmed (" + g_trade.modeNote + "): the restart recovery runs again");
      RecoverState(false);
     }
   //--- fills / closures, unowned positions / orders, position management: also while the warm-up is pending
   SyncTrade();
   Reconcile();
   ManagePositions();
   ManageOrphans();
   if(!g_ready)
     {
      if(!DoWarmup())
         return;
     }
   if(!g_risk.Ready())
      DayCheck();
   //--- new closed bar(s): engine + detector + intents
   formTime = iTime(_Symbol, _Period, 0);
   if(formTime > 0 && formTime != g_lastFormTime)
     {
      DayCheck();
      g_risk.OnTradeEvent(g_ses);
      if(ProcessNewBars(formTime))
        {
         g_lastFormTime = formTime;
         newBar = true;
         DrawSetups();
        }
     }
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

// Strategy Tester criterion: average R per closed position (net of costs)
double OnTester()
  {
   if(g_nR <= 0)
      return(0.0);
   return(g_sumR / (double)g_nR);
  }
//+------------------------------------------------------------------+
