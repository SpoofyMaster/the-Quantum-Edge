//+------------------------------------------------------------------+
//| BfDefines.mqh                                                    |
//| BprFvgEA v2: constants, input enums, codes and shared structures.|
//+------------------------------------------------------------------+
//
// Part of BprFvgEA. The EA as a whole contains a port of LuxAlgo code (see BfEngine.mqh) and is therefore
// distributed under Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0),
// https://creativecommons.org/licenses/by-nc-sa/4.0/ : non-commercial use only, attribution to LuxAlgo required,
// share-alike. This file itself contains no LuxAlgo logic.
//
// "spec s.N" = research/indicators/BPR_BREAKOUT_FIB_SPEC.md section N (the single source of truth for v2).
//
// PURITY CONTRACT. This file is transliterated to C++ for the parity harness. It uses NO MT5 API: only basic
// types, enums, #define, structs with fixed-size arrays and string literals.
//+------------------------------------------------------------------+
#ifndef BF_DEFINES_MQH
#define BF_DEFINES_MQH

#define BF_MAX_SETUPS     128     // spec s.3: tracked setups; above that the reason is CAPACITY
#define BF_MAX_EVENTS     512     // event records kept between two ClearEvents() calls (spec s.7)
#define BF_MAX_INTENTS    128     // intents kept between two ClearIntents() calls (v10: up to 10 setups x 3 cancels
                                  // + 3 orders on one bar, plus a touch entry)
#define BF_NLEV           3       // Fibonacci entry levels per setup (spec s.5)
#define BF_MAX_BUSY       16      // v10: setups listed in BfEnv.busyIds (the EA's busy execution contexts)

//+------------------------------------------------------------------+
//| Input enums (spec s.1). The comment after each value is the text |
//| MT5 shows in the inputs dialog.                                  |
//+------------------------------------------------------------------+
enum ENUM_BF_FVGTYPE
  {
   BF_FVGTYPE_FVG  = 0,           // FVG
   BF_FVGTYPE_IFVG = 1            // IFVG (display only, no trading)
  };

enum ENUM_BF_FIB
  {
   BF_FIB_NONE = 0,               // NONE
   BF_FIB_BPR  = 1                // BPR
  };

enum ENUM_BF_DIRECTION
  {
   BF_DIR_BOTH       = 0,         // BOTH
   BF_DIR_LONG_ONLY  = 1,         // LONG_ONLY
   BF_DIR_SHORT_ONLY = 2          // SHORT_ONLY
  };

enum ENUM_BF_FVGRULE
  {
   BF_FVGRULE_LUXALGO = 0,        // LUXALGO (the FVG boxes the indicator draws)
   BF_FVGRULE_ANY_GAP = 1,        // ANY_GAP (any 3-candle gap)
   BF_FVGRULE_NONE    = 2         // NONE (no FVG needed)
  };

// v6: which breakouts of a touched BPR are traded. v7: BOTH follows each BPR twice, as a continuation setup and as a
// reversal setup, each on its own (a reversal can follow a continuation that already traded).
enum ENUM_BF_SETUPTYPE
  {
   BF_SETUP_CONTINUATION = 0,     // CONTINUATION (breakout in the BPR's direction, v1-v5)
   BF_SETUP_REVERSAL     = 1,     // REVERSAL (breakout through the BPR, opposite direction)
   BF_SETUP_BOTH         = 2      // BOTH (a continuation setup and a reversal setup per BPR)
  };

// v7: the reversal level (bullish BPR: a close below it; bearish: above it)
enum ENUM_BF_REVLEVEL
  {
   BF_REVLVL_DEEPEST = 0,         // DEEPEST wick of the T1 / T2 candles
   BF_REVLVL_T1      = 1,         // T1 candle's wick
   BF_REVLVL_LAST    = 2          // LAST touch candle's wick (v6)
  };

enum ENUM_BF_SERVER_TIME
  {
   BF_SERVER_NY_PLUS_7 = 0,       // NY+7 (IC Markets and most NY-close brokers)
   BF_SERVER_EU_DST    = 1,       // UTC+2 winter / UTC+3 summer on EU DST dates
   BF_SERVER_FIXED     = 2        // UTC + fixed offset (InpServerOffsetH)
  };

//+------------------------------------------------------------------+
//| Codes (spec s.7). The exact names are the strings of Bf*Name().  |
//+------------------------------------------------------------------+
enum ENUM_BF_REASON
  {
   BF_R_NONE               = 0,
   BF_R_BAD_GEOMETRY       = 1,
   BF_R_BROKEN_AT_CREATION = 2,
   BF_R_CAPACITY           = 3,
   BF_R_WARMUP             = 4,
   BF_R_BROKEN             = 5,
   BF_R_EXPIRED            = 6,
   BF_R_TOUCH_LIMIT        = 7,
   BF_R_LEG_BROKEN         = 8,
   BF_R_NEW_EXTREME        = 9,
   BF_R_TARGET             = 10,
   BF_R_SESSION_END        = 11,
   BF_R_NO_LEVEL           = 12,
   BF_R_MISSED             = 13,
   BF_R_RR                 = 14,
   BF_R_COST               = 15,
   BF_R_BAD_LEVEL          = 16,
   BF_R_SIZE_BELOW_MIN     = 17,
   BF_R_ORDER_FAILED       = 18
  };
#define BF_NREASON        19

enum ENUM_BF_EVENT
  {
   BF_EV_NONE        = 0,
   BF_EV_ARMED       = 1,
   BF_EV_TOUCH       = 2,
   BF_EV_REJECT      = 3,
   BF_EV_BREAKOUT    = 4,
   BF_EV_BREAK_FAIL  = 5,
   BF_EV_CONFIRM     = 6,
   BF_EV_PLACE_LIMIT = 7,
   BF_EV_SKIP        = 8,
   BF_EV_CANCEL      = 9,
   BF_EV_DROP        = 10,
   BF_EV_CLOSED      = 11,
   BF_EV_DONE        = 12,
   BF_EV_TOUCH_ENTRY = 13         // v6: market entry decided on the close of the T1 candle (record + intent)
  };

// Setup phases (spec s.4)
#define BF_PH_NONE        0
#define BF_PH_WAIT        1       // armed, no touch yet
#define BF_PH_ZONE        2       // touched; waiting for the breakout
#define BF_PH_BREAK       3       // breakout candle seen; counting the closes beyond the level
#define BF_PH_LEG         4       // confirmed; tracking the leg extreme, waiting for the pullback
#define BF_PH_ORDERED     5       // limit orders pending, none filled
#define BF_PH_FILLED      6       // at least one level filled
#define BF_PH_CLOSED      7
#define BF_PH_DONE        8

// Level statuses (spec s.5-s.6)
#define BF_LV_NONE        0
#define BF_LV_PENDING     1
#define BF_LV_FILLED      2
#define BF_LV_CLOSED      3
#define BF_LV_SKIPPED     4
#define BF_LV_CANCELLED   5
#define BF_LV_DROPPED     6

// Diagnostic counters (panel, Experts log; the Python reference keeps the same counts in 'stats')
#define BF_STAT_DONE      0                       // + reason
#define BF_STAT_SKIP      19                      // + reason
#define BF_STAT_DROP      38                      // + reason
#define BF_STAT_BLK_SLOT  57
#define BF_STAT_BLK_SESS  58
#define BF_STAT_BLK_RISK  59
#define BF_STAT_BLK_SPRD  60
#define BF_STAT_NO_FVG    61
#define BF_STAT_REANCHOR  62
#define BF_STAT_RETRY     63
#define BF_STAT_BRK_FAIL  64
#define BF_STAT_CONFIRM   65
#define BF_STAT_PLACE     66
#define BF_STAT_ARMED     67
#define BF_STAT_CLOSED    68
#define BF_STAT_TOUCH     69
#define BF_STAT_BREAKOUT  70
#define BF_NSTAT          71

string BfReasonName(const int r)
  {
   if(r == BF_R_BAD_GEOMETRY)
      return("BAD_GEOMETRY");
   if(r == BF_R_BROKEN_AT_CREATION)
      return("BROKEN_AT_CREATION");
   if(r == BF_R_CAPACITY)
      return("CAPACITY");
   if(r == BF_R_WARMUP)
      return("WARMUP");
   if(r == BF_R_BROKEN)
      return("BROKEN");
   if(r == BF_R_EXPIRED)
      return("EXPIRED");
   if(r == BF_R_TOUCH_LIMIT)
      return("TOUCH_LIMIT");
   if(r == BF_R_LEG_BROKEN)
      return("LEG_BROKEN");
   if(r == BF_R_NEW_EXTREME)
      return("NEW_EXTREME");
   if(r == BF_R_TARGET)
      return("TARGET");
   if(r == BF_R_SESSION_END)
      return("SESSION_END");
   if(r == BF_R_NO_LEVEL)
      return("NO_LEVEL");
   if(r == BF_R_MISSED)
      return("MISSED");
   if(r == BF_R_RR)
      return("RR");
   if(r == BF_R_COST)
      return("COST");
   if(r == BF_R_BAD_LEVEL)
      return("BAD_LEVEL");
   if(r == BF_R_SIZE_BELOW_MIN)
      return("SIZE_BELOW_MIN");
   if(r == BF_R_ORDER_FAILED)
      return("ORDER_FAILED");
   return("");
  }

string BfEventName(const int e)
  {
   if(e == BF_EV_ARMED)
      return("ARMED");
   if(e == BF_EV_TOUCH)
      return("TOUCH");
   if(e == BF_EV_REJECT)
      return("REJECT");
   if(e == BF_EV_BREAKOUT)
      return("BREAKOUT");
   if(e == BF_EV_BREAK_FAIL)
      return("BREAK_FAIL");
   if(e == BF_EV_CONFIRM)
      return("CONFIRM");
   if(e == BF_EV_PLACE_LIMIT)
      return("PLACE_LIMIT");
   if(e == BF_EV_SKIP)
      return("SKIP");
   if(e == BF_EV_CANCEL)
      return("CANCEL");
   if(e == BF_EV_DROP)
      return("DROP");
   if(e == BF_EV_CLOSED)
      return("CLOSED");
   if(e == BF_EV_DONE)
      return("DONE");
   if(e == BF_EV_TOUCH_ENTRY)
      return("TOUCH_ENTRY");
   return("");
  }

string BfPhaseName(const int ph)
  {
   if(ph == BF_PH_WAIT)
      return("WAIT");
   if(ph == BF_PH_ZONE)
      return("ZONE");
   if(ph == BF_PH_BREAK)
      return("BREAK");
   if(ph == BF_PH_LEG)
      return("LEG");
   if(ph == BF_PH_ORDERED)
      return("ORDERED");
   if(ph == BF_PH_FILLED)
      return("FILLED");
   if(ph == BF_PH_CLOSED)
      return("CLOSED");
   if(ph == BF_PH_DONE)
      return("DONE");
   return("");
  }

string BfLevelStatusName(const int s)
  {
   if(s == BF_LV_PENDING)
      return("PENDING");
   if(s == BF_LV_FILLED)
      return("FILLED");
   if(s == BF_LV_CLOSED)
      return("CLOSED");
   if(s == BF_LV_SKIPPED)
      return("SKIPPED");
   if(s == BF_LV_CANCELLED)
      return("CANCELLED");
   if(s == BF_LV_DROPPED)
      return("DROPPED");
   return("NONE");
  }

//+------------------------------------------------------------------+
//| Strategy parameters (spec s.1) plus the symbol values the        |
//| detector needs.                                                  |
//+------------------------------------------------------------------+
struct BfParams
  {
   // engine (LuxAlgo, unchanged from v1)
   int               length;              // InpLength 3..10
   int               visBoxes;            // InpVisibleBoxes 1..20
   int               fvgMode;             // ENUM_BF_FVGTYPE; setups need BF_FVGTYPE_FVG
   // setup rules (spec s.1)
   int               direction;           // ENUM_BF_DIRECTION
   int               maxTouches;          // 1..5
   int               confirmCloses;       // 1..5 (breakout candle included)
   bool              rejectBeforeBreak;   // the breakout candle must come after a rejection candle (stricter reading)
   int               fvgRule;             // ENUM_BF_FVGRULE
   int               setupExpiryBars;     // bars after the BPR's creation to reach the confirmation
   int               legExpiryBars;       // bars after the confirmation for orders / fills
   double            fib1;                // entry retracements, % of the leg (0 = off)
   double            fib2;
   double            fib3;
   double            stopFib;             // stop retracement, % (100 = leg origin)
   int               stopBufferTicks;
   double            targetFib;           // target retracement, % (0 = leg extreme, < 0 = extension)
   double            minRR;               // 0 = off
   double            maxCostR;            // 0 = off
   int               maxHoldMin;          // executor only (<= 120)
   // v5 (EA only; the Python reference has no counterpart, both false = v4)
   bool              anticipate;          // decide without a pullback candle: on the confirmation bar and on every leg
                                          // bar (FVG condition still required); a new extreme re-anchors and re-decides
                                          // on the same bar
   bool              legBreakOnClose;     // LEG_BROKEN only when a candle CLOSES beyond the leg origin (false = any
                                          // low / high beyond it)
   // v6 (EA only; the Python reference has no counterpart; CONTINUATION + false = v5)
   int               setupType;           // ENUM_BF_SETUPTYPE
   bool              touchEntry;          // market entry at the next open after the T1 candle, BPR direction
   double            touchTargetRR;       // its take-profit in R (risk = entry -> stop beyond the BPR)
   // v7 (EA only): the reversal setup
   int               revLevel;            // ENUM_BF_REVLEVEL
   bool              revNeedReject;       // a rejection after T1 before the reversal breakout ("price comes back")
   // v8 (EA only; -1 / true = v7)
   int               t1WaitBars;          // bars from the BPR's creation to T1 (0 = no limit). >= 0 also: the
                                          // breakout window counts only while price is at the zone (a visit, a
                                          // breakout), the setup idle the longest makes room at capacity, warm-up
                                          // setups not yet confirmed go on, and a reversal setup takes a candle that
                                          // closes beyond the zone inside a visit as the rejection. -1 = v4-v7 rules
   bool              revNeedFvg;          // the reversal waits for an FVG of its trade direction (false = its limits
                                          // can go in at the confirmation)
   // v9 (EA only; 0 = v8)
   int               revRejCandles;       // the reversal breakout needs at least this many candles in the BPR's
                                          // direction (bullish candles for a bullish BPR) that do not close beyond the
                                          // reversal level, after the T1 candle and after the last close beyond that
                                          // level that was not a breakout ("a rejection of at least 2 green candles,
                                          // successive or not, before price comes back for the breakout"). > 0 also:
                                          // such a close is no touch (no T2, the level stays)
   // v11 (EA only; false = v10)
   bool              revBodyInBox;        // reversal: the bodies of the T1 / T2 candles (every candle of the touch) and
                                          // of the rejection candles C1 .. C<revRejCandles> must stay in the BPR box or on
                                          // its side of it (a bullish BPR, tested from above: not below its bottom B;
                                          // a bearish one: not above its top T). Otherwise no trade: DONE(BROKEN).
                                          // A second tap that closes beyond the level too early (v9: no touch) is
                                          // checked as T2 while 2 touches are allowed
   // v10 (EA only; 1 / 0 = v9)
   int               maxSetups;           // setups with orders or positions at the same time (1 = one at a time, the
                                          // v2-v9 rule). > 1: every ready setup decides on its bar while a slot is
                                          // free (env.freeSlots); a setup that moves its own orders keeps its slot
   int               pendingMaxSec;       // a setup's limit orders live at most this long after its first placement
                                          // (seconds, env.now; 0 = off): then they are cancelled (EXPIRED)
   // session / execution
   bool              useSession;
   double            commissionPerLotSide; // account currency per lot per side (UNVERIFIED); informative
   double            slippageTicks;
   // symbol
   double            tickSize;
   int               digits;
   double            commPrice;           // round-trip commission per lot / value of a 1.0 price move per lot
  };

// Spec s.1 defaults (fixed from the owner's rule before any data was looked at). tickSize / commPrice are
// XAUUSD-like placeholders (UNVERIFIED); the EA overwrites them from the symbol.
void BfDefaultParams(BfParams &p)
  {
   p.length               = 5;
   p.visBoxes             = 2;
   p.fvgMode              = BF_FVGTYPE_FVG;
   p.direction            = BF_DIR_BOTH;
   p.maxTouches           = 2;
   p.confirmCloses        = 2;
   p.rejectBeforeBreak    = false;
   p.fvgRule              = BF_FVGRULE_LUXALGO;
   p.setupExpiryBars      = 240;
   p.legExpiryBars        = 60;
   p.fib1                 = 50.0;
   p.fib2                 = 61.8;
   p.fib3                 = 71.0;
   p.stopFib              = 100.0;
   p.stopBufferTicks      = 10;
   p.targetFib            = 0.0;
   p.minRR                = 0.0;
   p.maxCostR             = 0.30;
   p.maxHoldMin           = 120;
   p.anticipate           = false;
   p.legBreakOnClose      = false;
   p.setupType            = BF_SETUP_CONTINUATION;
   p.touchEntry           = false;
   p.touchTargetRR        = 1.5;
   p.revLevel             = BF_REVLVL_DEEPEST;
   p.revNeedReject        = true;
   p.t1WaitBars           = -1;
   p.revNeedFvg           = true;
   p.revRejCandles        = 0;
   p.revBodyInBox         = false;
   p.maxSetups            = 1;
   p.pendingMaxSec        = 0;
   p.useSession           = true;
   p.commissionPerLotSide = 3.50;
   p.slippageTicks        = 1.0;
   p.tickSize             = 0.01;
   p.digits               = 2;
   p.commPrice            = 0.07;
  }

void BfCopyParams(BfParams &dst, const BfParams &src)
  {
   dst.length               = src.length;
   dst.visBoxes             = src.visBoxes;
   dst.fvgMode              = src.fvgMode;
   dst.direction            = src.direction;
   dst.maxTouches           = src.maxTouches;
   dst.confirmCloses        = src.confirmCloses;
   dst.rejectBeforeBreak    = src.rejectBeforeBreak;
   dst.fvgRule              = src.fvgRule;
   dst.setupExpiryBars      = src.setupExpiryBars;
   dst.legExpiryBars        = src.legExpiryBars;
   dst.fib1                 = src.fib1;
   dst.fib2                 = src.fib2;
   dst.fib3                 = src.fib3;
   dst.stopFib              = src.stopFib;
   dst.stopBufferTicks      = src.stopBufferTicks;
   dst.targetFib            = src.targetFib;
   dst.minRR                = src.minRR;
   dst.maxCostR             = src.maxCostR;
   dst.maxHoldMin           = src.maxHoldMin;
   dst.anticipate           = src.anticipate;
   dst.legBreakOnClose      = src.legBreakOnClose;
   dst.setupType            = src.setupType;
   dst.touchEntry           = src.touchEntry;
   dst.touchTargetRR        = src.touchTargetRR;
   dst.revLevel             = src.revLevel;
   dst.revNeedReject        = src.revNeedReject;
   dst.t1WaitBars           = src.t1WaitBars;
   dst.revNeedFvg           = src.revNeedFvg;
   dst.revRejCandles        = src.revRejCandles;
   dst.revBodyInBox         = src.revBodyInBox;
   dst.maxSetups            = src.maxSetups;
   dst.pendingMaxSec        = src.pendingMaxSec;
   dst.useSession           = src.useSession;
   dst.commissionPerLotSide = src.commissionPerLotSide;
   dst.slippageTicks        = src.slippageTicks;
   dst.tickSize             = src.tickSize;
   dst.digits               = src.digits;
   dst.commPrice            = src.commPrice;
  }

// Fibonacci entry level k = 1..3 (% of the leg; 0 = off)
double BfFibOf(const BfParams &p, const int k)
  {
   if(k == 1)
      return(p.fib1);
   if(k == 2)
      return(p.fib2);
   if(k == 3)
      return(p.fib3);
   return(0.0);
  }

//+------------------------------------------------------------------+
//| Environment given to the detector at the close of each bar       |
//+------------------------------------------------------------------+
struct BfEnv
  {
   bool              slotFree;            // no pending order and no position of this EA
   bool              sessionEntryOk;      // the next bar's open is inside the entry window
   bool              sessionCancel;       // the next bar's open is at or after the last entry time
   bool              riskOk;              // no lockout, trade limit not reached
   bool              spreadOk;            // spread filter passed
   double            sp;                  // spread at the decision moment (price units)
   int               slotOwner;           // v5: id of the setup whose own pending limits are all that holds the slot
                                          // (0 = none); with anticipate it may re-decide after its re-anchor
   bool              keepOrders;          // 9.01: the pending orders are kept (InpCancelAtSessionEnd = false) and no
                                          // order can be sent now: a new extreme does not move (cancel) them
   int               freeSlots;           // v10 (maxSetups > 1): how many more setups may take orders now
   long              now;                 // v10: the decision moment (the next bar's open, server time; 0 = unknown)
   int               nBusy;               // v10 (maxSetups > 1): the setups whose execution context in the EA still
   int               busyIds[BF_MAX_BUSY];// holds orders / positions (their own slot, already counted as used)
  };

void BfClearEnv(BfEnv &e)
  {
   e.slotFree       = false;
   e.sessionEntryOk = false;
   e.sessionCancel  = false;
   e.keepOrders     = false;
   e.freeSlots      = 0;
   e.now            = 0;
   e.nBusy          = 0;
   for(int k = 0; k < BF_MAX_BUSY; k++)
      e.busyIds[k] = 0;
   e.riskOk         = false;
   e.spreadOk       = false;
   e.sp             = 0.0;
   e.slotOwner      = 0;
  }

//+------------------------------------------------------------------+
//| A tracked setup (spec s.3-s.6).                                  |
//+------------------------------------------------------------------+
struct BfSetup
  {
   int               id;
   int               dir;                 // +1 long (bullish BPR), -1 short (bearish BPR)
   int               created;             // bar index of the BPR's creation
   double            B;                   // zone = the drawn BPR box [B, T]
   double            T;
   int               phase;               // BF_PH_*
   int               reason;              // ENUM_BF_REASON (DONE only)
   int               touches;
   bool              inEp;                // the previous bar touched the zone
   int               ref;                 // reference candle (last candle of the latest touch); -1 = none
   double            lvl;                 // breakout level: high (long) / low (short) of the reference candle
   double            O;                   // leg origin (fib 100 %)
   int               oBar;
   double            X;                   // leg extreme (fib 0 %)
   int               xBar;
   int               brkBar;              // breakout candle; -1 = none
   int               nClose;              // closes beyond the level so far
   int               confirmBar;          // -1 = none
   int               decisionBar;         // -1 = none
   bool              ready;               // pullback bar with an FVG: may decide on this bar (step 5)
   double            SL;                  // order levels, rounded (0 until decided)
   double            TP;
   double            tgt;                 // bid target (rounded), for 'target touched'
   double            decO;                // fib anchors of the decision
   double            decX;
   int               touchBar1;           // first bar of touch 1 / touch 2 (-1 = none; drawing)
   int               touchBar2;
   bool              everFilled;
   int               lvSt[BF_NLEV];       // BF_LV_*
   double            lvP[BF_NLEV];        // entry price (rounded) once decided
   int               lvRsn[BF_NLEV];      // reason of SKIPPED / CANCELLED / DROPPED
   // v6
   int               zdir;                // the BPR's direction (+1 bullish, -1 bearish); 'dir' is the trade direction
                                          // and becomes -zdir when a reversal breakout starts
   bool              rev;                 // the breakout in progress / confirmed is a reversal
   double            lvlR;                // reversal level: low (bullish BPR) / high (bearish) of a touch candle (v7:
                                          // per revLevel, the deepest of T1 / T2 by default)
   int               lvlRBar;             // the bar of that candle
   double            rO;                  // reversal leg origin: highest high (bullish BPR) / lowest low since T1 began,
   int               rOBar;               // or since the latest later visit of the zone that was rejected (v7)
   double            rX;                  // reversal leg extreme after rO
   int               rXBar;
   bool              touchReady;          // T1 on this bar with InpTouchEntry: may decide the touch entry (step 5)
   double            tP;                  // touch entry: estimated entry, stop, target (record)
   double            tSL;
   double            tTP;
   // v7
   int               kind;                // BF_SETUP_CONTINUATION or BF_SETUP_REVERSAL: the breakout this setup trades
   bool              rej;                 // a rejection came after T1 (REJECT record)
   bool              cAct;                // a visit of the zone is open: candidate origin cO / cX, adopted as rO / rX
   double            cO;                  // when that visit is rejected (v7.01: the bounce after the visit's low cL)
   int               cOBar;
   double            cX;
   int               cXBar;
   double            cL;                  // v7.01: the visit's lowest low (bullish BPR) / highest high (bearish)
   bool              cLvlOn;              // v7.01 DEEPEST: a later touch's wick waits for its visit's rejection
   double            cLvl;
   int               cLvlBar;
   int               lastRej;             // v7.01: bar of the last REJECT (a reversal setup's expiry counts from it)
   int               lastVisit;           // v8: first bar of the latest visit of the zone (T1, T2, a pullback visit)
   int               nRejC;               // v9: rejection candles (in the BPR's direction, not closing beyond the
                                          // reversal level) after the T1 candle and after the last close beyond it
                                          // that was not a breakout; a breakout in progress (BREAK) keeps it
   long              ordTime;             // v10: env.now of the setup's first placement (0 = no order yet)
   int               ordBar;              // v10: the bar of that first placement (-1 = none)
   int               dupOf;               // v10: ended because setup dupOf already trades the same leg (0 = no)
   bool              tVisit;              // v11: the current visit of the zone is a touch (T1 / T2), not a pullback
   int               tVisitK;             // v11: that touch's number n (Tn; an early second tap is T2)
   int               bodyOut;             // v11: ended because a body left the box: n = the Tn candle, 10 + n = Cn,
                                          // 1000 + n = a later candle of the Tn touch (C: n <= 100)
   bool              pendTimeUp;          // v10: the pending-order time limit (pendingMaxSec) ended its orders
   int               reAnchorBar;         // v10: the bar of its last re-anchor (it keeps its slot to decide again)
  };

void BfClearSetup(BfSetup &s)
  {
   int k;
   s.id          = 0;
   s.dir         = 0;
   s.created     = -1;
   s.B           = 0.0;
   s.T           = 0.0;
   s.phase       = BF_PH_NONE;
   s.reason      = BF_R_NONE;
   s.touches     = 0;
   s.inEp        = false;
   s.ref         = -1;
   s.lvl         = 0.0;
   s.O           = 0.0;
   s.oBar        = -1;
   s.X           = 0.0;
   s.xBar        = -1;
   s.brkBar      = -1;
   s.nClose      = 0;
   s.confirmBar  = -1;
   s.decisionBar = -1;
   s.ready       = false;
   s.SL          = 0.0;
   s.TP          = 0.0;
   s.tgt         = 0.0;
   s.decO        = 0.0;
   s.decX        = 0.0;
   s.touchBar1   = -1;
   s.touchBar2   = -1;
   s.everFilled  = false;
   for(k = 0; k < BF_NLEV; k++)
     {
      s.lvSt[k]  = BF_LV_NONE;
      s.lvP[k]   = 0.0;
      s.lvRsn[k] = BF_R_NONE;
     }
   s.zdir        = 0;
   s.rev         = false;
   s.lvlR        = 0.0;
   s.lvlRBar     = -1;
   s.rO          = 0.0;
   s.rOBar       = -1;
   s.rX          = 0.0;
   s.rXBar       = -1;
   s.touchReady  = false;
   s.tP          = 0.0;
   s.tSL         = 0.0;
   s.tTP         = 0.0;
   s.kind        = BF_SETUP_CONTINUATION;
   s.rej         = false;
   s.cAct        = false;
   s.cO          = 0.0;
   s.cOBar       = -1;
   s.cX          = 0.0;
   s.cXBar       = -1;
   s.cL          = 0.0;
   s.cLvlOn      = false;
   s.cLvl        = 0.0;
   s.cLvlBar     = -1;
   s.lastRej     = -1;
   s.lastVisit   = -1;
   s.nRejC       = 0;
   s.ordTime     = 0;
   s.ordBar      = -1;
   s.dupOf       = 0;
   s.tVisit      = false;
   s.tVisitK     = 0;
   s.bodyOut     = 0;
   s.pendTimeUp  = false;
   s.reAnchorBar = -1;
  }

void BfCopySetup(BfSetup &dst, const BfSetup &src)
  {
   int k;
   dst.id          = src.id;
   dst.dir         = src.dir;
   dst.created     = src.created;
   dst.B           = src.B;
   dst.T           = src.T;
   dst.phase       = src.phase;
   dst.reason      = src.reason;
   dst.touches     = src.touches;
   dst.inEp        = src.inEp;
   dst.ref         = src.ref;
   dst.lvl         = src.lvl;
   dst.O           = src.O;
   dst.oBar        = src.oBar;
   dst.X           = src.X;
   dst.xBar        = src.xBar;
   dst.brkBar      = src.brkBar;
   dst.nClose      = src.nClose;
   dst.confirmBar  = src.confirmBar;
   dst.decisionBar = src.decisionBar;
   dst.ready       = src.ready;
   dst.SL          = src.SL;
   dst.TP          = src.TP;
   dst.tgt         = src.tgt;
   dst.decO        = src.decO;
   dst.decX        = src.decX;
   dst.touchBar1   = src.touchBar1;
   dst.touchBar2   = src.touchBar2;
   dst.everFilled  = src.everFilled;
   for(k = 0; k < BF_NLEV; k++)
     {
      dst.lvSt[k]  = src.lvSt[k];
      dst.lvP[k]   = src.lvP[k];
      dst.lvRsn[k] = src.lvRsn[k];
     }
   dst.zdir        = src.zdir;
   dst.rev         = src.rev;
   dst.lvlR        = src.lvlR;
   dst.lvlRBar     = src.lvlRBar;
   dst.rO          = src.rO;
   dst.rOBar       = src.rOBar;
   dst.rX          = src.rX;
   dst.rXBar       = src.rXBar;
   dst.touchReady  = src.touchReady;
   dst.tP          = src.tP;
   dst.tSL         = src.tSL;
   dst.tTP         = src.tTP;
   dst.kind        = src.kind;
   dst.rej         = src.rej;
   dst.cAct        = src.cAct;
   dst.cO          = src.cO;
   dst.cOBar       = src.cOBar;
   dst.cX          = src.cX;
   dst.cXBar       = src.cXBar;
   dst.cL          = src.cL;
   dst.cLvlOn      = src.cLvlOn;
   dst.cLvl        = src.cLvl;
   dst.cLvlBar     = src.cLvlBar;
   dst.lastRej     = src.lastRej;
   dst.lastVisit   = src.lastVisit;
   dst.nRejC       = src.nRejC;
   dst.ordTime     = src.ordTime;
   dst.ordBar      = src.ordBar;
   dst.dupOf       = src.dupOf;
   dst.tVisit      = src.tVisit;
   dst.tVisitK     = src.tVisitK;
   dst.bodyOut     = src.bodyOut;
   dst.pendTimeUp  = src.pendTimeUp;
   dst.reAnchorBar = src.reAnchorBar;
  }

//+------------------------------------------------------------------+
//| Intent emitted by the detector: PLACE_LIMIT (level k) or CANCEL  |
//| (level k). 'type' uses the BF_EV_* codes of the same name.       |
//+------------------------------------------------------------------+
struct BfIntent
  {
   int               type;                // BF_EV_PLACE_LIMIT / BF_EV_CANCEL / BF_EV_TOUCH_ENTRY (v6)
   int               id;
   int               dir;
   int               k;                   // level 1..3 (0 = the touch entry)
   int               reason;              // CANCEL only
   int               bar;                 // bar index of the decision / cancel
   double            P;
   double            SL;
   double            TP;
   bool              pendTime;            // v10: a CANCEL of the pending-order time limit (pendingMaxSec)
  };

void BfClearIntent(BfIntent &x)
  {
   x.type   = BF_EV_NONE;
   x.id     = 0;
   x.dir    = 0;
   x.k      = 0;
   x.reason = BF_R_NONE;
   x.bar    = -1;
   x.P      = 0.0;
   x.SL     = 0.0;
   x.TP     = 0.0;
   x.pendTime = false;
  }

void BfCopyIntent(BfIntent &dst, const BfIntent &src)
  {
   dst.type   = src.type;
   dst.id     = src.id;
   dst.dir    = src.dir;
   dst.k      = src.k;
   dst.reason = src.reason;
   dst.bar    = src.bar;
   dst.P      = src.P;
   dst.SL     = src.SL;
   dst.TP     = src.TP;
   dst.pendTime = src.pendTime;
  }

//+------------------------------------------------------------------+
//| Event record (spec s.7). n, id, ev, dir, k, reason, P, SL, TP,   |
//| O, X are the parity fields (P/SL/TP: PLACE_LIMIT only; O/X:      |
//| CONFIRM and PLACE_LIMIT only); the rest is a snapshot for logs.  |
//+------------------------------------------------------------------+
struct BfEvent
  {
   int               n;
   int               id;
   int               ev;                  // ENUM_BF_EVENT
   int               dir;
   int               k;                   // touch number (TOUCH) or level 1..3 (level records); else 0
   int               reason;
   double            P;
   double            SL;
   double            TP;
   double            O;
   double            X;
   // snapshot
   int               phase;
   int               created;
   double            B;
   double            T;
   int               touches;
   double            lvl;
   int               ref;
   int               brkBar;
   int               confirmBar;
   int               decisionBar;
   double            tgt;
   int               oBar;                // bar of the leg origin / extreme (drawing)
   int               xBar;
   double            snO;                 // the setup's O / X / SL / TP and levels after the event (CSV logs)
   double            snX;
   double            snSL;
   double            snTP;
   int               snLvSt[BF_NLEV];
   double            snLvP[BF_NLEV];
   int               snLvRsn[BF_NLEV];
   int               zdir;                // v6: the BPR's direction (dir is the trade direction)
   bool              rev;                 // v6: reversal breakout (lvl is then the reversal level)
   int               lvlBar;              // v6: the bar lvl comes from (ref; the touch candle for a reversal)
   int               kind;                // v7: BF_SETUP_CONTINUATION / BF_SETUP_REVERSAL (the setup's kind)
   int               rejC;                // v9: the setup's rejection candles after this bar's candle (nRejC; on a
                                          // BREAKOUT: the count the breakout used, the breakout candle never counts)
   bool              pendTime;            // v10: the record comes from the pending-order time limit (EXPIRED)
   int               dupOf;               // v10: DONE(NO_LEVEL) because setup dupOf trades the same leg (0 = no)
   int               bodyOut;             // v11: DONE(BROKEN) because a body left the box: n = Tn, 10 + n = Cn,
                                          // 1000 + n = a later candle of the Tn touch (C: n <= 100)
  };

void BfClearEvent(BfEvent &e)
  {
   e.n           = -1;
   e.id          = 0;
   e.ev          = BF_EV_NONE;
   e.dir         = 0;
   e.k           = 0;
   e.reason      = BF_R_NONE;
   e.P           = 0.0;
   e.SL          = 0.0;
   e.TP          = 0.0;
   e.O           = 0.0;
   e.X           = 0.0;
   e.phase       = BF_PH_NONE;
   e.created     = -1;
   e.B           = 0.0;
   e.T           = 0.0;
   e.touches     = 0;
   e.lvl         = 0.0;
   e.ref         = -1;
   e.brkBar      = -1;
   e.confirmBar  = -1;
   e.decisionBar = -1;
   e.tgt         = 0.0;
   e.oBar        = -1;
   e.xBar        = -1;
   e.snO         = 0.0;
   e.snX         = 0.0;
   e.snSL        = 0.0;
   e.snTP        = 0.0;
   for(int k = 0; k < BF_NLEV; k++)
     {
      e.snLvSt[k]  = BF_LV_NONE;
      e.snLvP[k]   = 0.0;
      e.snLvRsn[k] = BF_R_NONE;
     }
   e.zdir        = 0;
   e.rev         = false;
   e.lvlBar      = -1;
   e.kind        = BF_SETUP_CONTINUATION;
   e.rejC        = 0;
   e.dupOf       = 0;
   e.bodyOut     = 0;
   e.pendTime    = false;
  }

void BfCopyEvent(BfEvent &dst, const BfEvent &src)
  {
   dst.n           = src.n;
   dst.id          = src.id;
   dst.ev          = src.ev;
   dst.dir         = src.dir;
   dst.k           = src.k;
   dst.reason      = src.reason;
   dst.P           = src.P;
   dst.SL          = src.SL;
   dst.TP          = src.TP;
   dst.O           = src.O;
   dst.X           = src.X;
   dst.phase       = src.phase;
   dst.created     = src.created;
   dst.B           = src.B;
   dst.T           = src.T;
   dst.touches     = src.touches;
   dst.lvl         = src.lvl;
   dst.ref         = src.ref;
   dst.brkBar      = src.brkBar;
   dst.confirmBar  = src.confirmBar;
   dst.decisionBar = src.decisionBar;
   dst.tgt         = src.tgt;
   dst.oBar        = src.oBar;
   dst.xBar        = src.xBar;
   dst.snO         = src.snO;
   dst.snX         = src.snX;
   dst.snSL        = src.snSL;
   dst.snTP        = src.snTP;
   for(int k = 0; k < BF_NLEV; k++)
     {
      dst.snLvSt[k]  = src.snLvSt[k];
      dst.snLvP[k]   = src.snLvP[k];
      dst.snLvRsn[k] = src.snLvRsn[k];
     }
   dst.zdir        = src.zdir;
   dst.rev         = src.rev;
   dst.lvlBar      = src.lvlBar;
   dst.kind        = src.kind;
   dst.rejC        = src.rejC;
   dst.dupOf       = src.dupOf;
   dst.bodyOut     = src.bodyOut;
   dst.pendTime    = src.pendTime;
  }

#endif
//+------------------------------------------------------------------+
