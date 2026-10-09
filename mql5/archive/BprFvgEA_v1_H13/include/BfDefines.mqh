//+------------------------------------------------------------------+
//| BfDefines.mqh                                                    |
//| BprFvgEA: constants, input enums, codes and shared structures.   |
//+------------------------------------------------------------------+
//
// Part of BprFvgEA. The EA as a whole contains a port of LuxAlgo code (see BfEngine.mqh) and is therefore
// distributed under Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0),
// https://creativecommons.org/licenses/by-nc-sa/4.0/ : non-commercial use only, attribution to LuxAlgo required,
// share-alike. This file itself contains no LuxAlgo logic.
//
// "spec s.N" = research/indicators/BPR_FVG_EA_SPEC.md section N (the single source of truth for this EA).
//
// PURITY CONTRACT. This file is transliterated to C++ for the parity harness. It uses NO MT5 API: only basic
// types, enums, #define, structs with fixed-size arrays and string literals.
//+------------------------------------------------------------------+
#ifndef BF_DEFINES_MQH
#define BF_DEFINES_MQH

#define BF_MAX_SETUPS     128     // spec s.4 step 4: tracked setups; above that the reason is CAPACITY
#define BF_MAX_EVENTS     512     // event records kept between two ClearEvents() calls (spec s.9)
#define BF_MAX_INTENTS    16      // intents kept between two ClearIntents() calls

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

enum ENUM_BF_SOURCE
  {
   BF_SOURCE_BPR  = 0,            // BPR
   BF_SOURCE_FVG  = 1,            // FVG
   BF_SOURCE_BOTH = 2             // BOTH
  };

enum ENUM_BF_DIRECTION
  {
   BF_DIR_BOTH       = 0,         // BOTH
   BF_DIR_LONG_ONLY  = 1,         // LONG_ONLY
   BF_DIR_SHORT_ONLY = 2          // SHORT_ONLY
  };

enum ENUM_BF_ENTRY
  {
   BF_ENTRY_LIMIT   = 0,          // LIMIT (R1: front-run limit near the far edge)
   BF_ENTRY_CONFIRM = 1           // CONFIRM (R3: rejection candle, then a market order)
  };

enum ENUM_BF_TPMODE
  {
   BF_TP_TP1_TP2  = 0,            // TP1_TP2 (partial at TP1, rest at TP2)
   BF_TP_TP1_ONLY = 1,            // TP1_ONLY
   BF_TP_TP2_ONLY = 2             // TP2_ONLY
  };

enum ENUM_BF_SERVER_TIME
  {
   BF_SERVER_NY_PLUS_7 = 0,       // NY+7 (IC Markets and most NY-close brokers)
   BF_SERVER_EU_DST    = 1,       // UTC+2 winter / UTC+3 summer on EU DST dates
   BF_SERVER_FIXED     = 2        // UTC + fixed offset (InpServerOffsetH)
  };

//+------------------------------------------------------------------+
//| Codes. The prefixed identifiers avoid clashes between the lists; |
//| the exact names are the strings returned by Bf*Name() below.     |
//+------------------------------------------------------------------+
// Reasons of DONE (spec s.3-s.6, s.9).
enum ENUM_BF_REASON
  {
   BF_R_NONE                 = 0,
   BF_R_BAD_GEOMETRY         = 1,
   BF_R_BROKEN_AT_CREATION   = 2,
   BF_R_INSUFFICIENT_HISTORY = 3,
   BF_R_NO_SWEEP             = 4,
   BF_R_CAPACITY             = 5,
   BF_R_WARMUP               = 6,
   BF_R_BROKEN               = 7,
   BF_R_EXPIRED              = 8,
   BF_R_RUNAWAY              = 9,
   BF_R_SESSION_END          = 10,
   BF_R_SIZE_BELOW_MIN       = 11,
   BF_R_ORDER_FAILED         = 12,
   BF_R_RUNAWAY_SAME_BAR     = 13     // Python simulator only; the EA never produces it
  };

// Event records (spec s.9): one per intent and per status change.
enum ENUM_BF_EVENT
  {
   BF_EV_NONE        = 0,
   BF_EV_ARMED       = 1,
   BF_EV_DONE        = 2,
   BF_EV_MSS         = 3,
   BF_EV_PLACE_LIMIT = 4,
   BF_EV_MARKET      = 5,
   BF_EV_CANCEL      = 6
  };

// Setup status (spec s.4).
enum ENUM_BF_STATUS
  {
   BF_ST_NONE    = 0,
   BF_ST_ARMED   = 1,
   BF_ST_ORDERED = 2,
   BF_ST_FILLED  = 3,
   BF_ST_CLOSED  = 4,
   BF_ST_DONE    = 5
  };

// Kind of order decided for an ORDERED setup.
#define BF_ORD_NONE       0
#define BF_ORD_LIMIT      1
#define BF_ORD_MARKET     2

string BfReasonName(const int r)
  {
   if(r == BF_R_BAD_GEOMETRY)
      return("BAD_GEOMETRY");
   if(r == BF_R_BROKEN_AT_CREATION)
      return("BROKEN_AT_CREATION");
   if(r == BF_R_INSUFFICIENT_HISTORY)
      return("INSUFFICIENT_HISTORY");
   if(r == BF_R_NO_SWEEP)
      return("NO_SWEEP");
   if(r == BF_R_CAPACITY)
      return("CAPACITY");
   if(r == BF_R_WARMUP)
      return("WARMUP");
   if(r == BF_R_BROKEN)
      return("BROKEN");
   if(r == BF_R_EXPIRED)
      return("EXPIRED");
   if(r == BF_R_RUNAWAY)
      return("RUNAWAY");
   if(r == BF_R_SESSION_END)
      return("SESSION_END");
   if(r == BF_R_SIZE_BELOW_MIN)
      return("SIZE_BELOW_MIN");
   if(r == BF_R_ORDER_FAILED)
      return("ORDER_FAILED");
   if(r == BF_R_RUNAWAY_SAME_BAR)
      return("RUNAWAY_SAME_BAR");
   return("");
  }

string BfEventName(const int e)
  {
   if(e == BF_EV_ARMED)
      return("ARMED");
   if(e == BF_EV_DONE)
      return("DONE");
   if(e == BF_EV_MSS)
      return("MSS");
   if(e == BF_EV_PLACE_LIMIT)
      return("PLACE_LIMIT");
   if(e == BF_EV_MARKET)
      return("MARKET");
   if(e == BF_EV_CANCEL)
      return("CANCEL");
   return("");
  }

string BfStatusName(const int s)
  {
   if(s == BF_ST_ARMED)
      return("ARMED");
   if(s == BF_ST_ORDERED)
      return("ORDERED");
   if(s == BF_ST_FILLED)
      return("FILLED");
   if(s == BF_ST_CLOSED)
      return("CLOSED");
   if(s == BF_ST_DONE)
      return("DONE");
   return("");
  }

// Setup source names (spec s.9): "BPR" or "FVG".
string BfSourceName(const int src)
  {
   if(src == BF_SOURCE_BPR)
      return("BPR");
   if(src == BF_SOURCE_FVG)
      return("FVG");
   return("BOTH");
  }

//+------------------------------------------------------------------+
//| Strategy parameters (spec s.1). Every strategy input, plus the   |
//| symbol values the detector needs.                                |
//+------------------------------------------------------------------+
struct BfParams
  {
   // engine (spec s.2)
   int               length;              // InpLength 3..10
   int               visBoxes;            // InpVisibleBoxes 1..20
   int               fvgMode;             // ENUM_BF_FVGTYPE; setups need BF_FVGTYPE_FVG
   // setups (spec s.1 "Setups")
   int               source;              // ENUM_BF_SOURCE
   int               direction;           // ENUM_BF_DIRECTION
   int               entryMode;           // ENUM_BF_ENTRY
   int               entryOffsetTicks;    // delta of the LIMIT price, in ticks
   bool              useSweep;
   int               sweepWindow;
   int               rangeBars;
   bool              useMss;
   int               mssBars;
   int               rallyBars;
   int               expiryBars;
   double            stopZoneMult;
   double            minRR;
   double            maxCostR;
   int               tpMode;              // ENUM_BF_TPMODE
   double            tp1Fraction;         // executor only
   bool              breakEven;           // executor only
   int               maxHoldMin;          // executor only (<= 120)
   // session / execution
   bool              useSession;
   double            commissionPerLotSide; // account currency per lot per side (UNVERIFIED); informative
   double            slippageTicks;
   // symbol
   double            tickSize;            // price tick
   int               digits;              // symbol digits (levels are normalised to them)
   double            commPrice;           // round-trip commission per lot / value of a 1.0 price move per lot
  };

// Spec s.1 / s.10 defaults (fixed before any data was looked at). tickSize / commPrice are XAUUSD-like
// placeholders (UNVERIFIED); the EA overwrites them from the symbol.
void BfDefaultParams(BfParams &p)
  {
   p.length               = 5;
   p.visBoxes             = 2;
   p.fvgMode              = BF_FVGTYPE_FVG;
   p.source               = BF_SOURCE_BPR;
   p.direction            = BF_DIR_BOTH;
   p.entryMode            = BF_ENTRY_LIMIT;
   p.entryOffsetTicks     = 5;
   p.useSweep             = true;
   p.sweepWindow          = 30;
   p.rangeBars            = 30;
   p.useMss               = true;
   p.mssBars              = 20;
   p.rallyBars            = 10;
   p.expiryBars           = 60;
   p.stopZoneMult         = 1.2;
   p.minRR                = 1.0;
   p.maxCostR             = 0.15;
   p.tpMode               = BF_TP_TP1_TP2;
   p.tp1Fraction          = 0.5;
   p.breakEven            = true;
   p.maxHoldMin           = 120;
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
   dst.source               = src.source;
   dst.direction            = src.direction;
   dst.entryMode            = src.entryMode;
   dst.entryOffsetTicks     = src.entryOffsetTicks;
   dst.useSweep             = src.useSweep;
   dst.sweepWindow          = src.sweepWindow;
   dst.rangeBars            = src.rangeBars;
   dst.useMss               = src.useMss;
   dst.mssBars              = src.mssBars;
   dst.rallyBars            = src.rallyBars;
   dst.expiryBars           = src.expiryBars;
   dst.stopZoneMult         = src.stopZoneMult;
   dst.minRR                = src.minRR;
   dst.maxCostR             = src.maxCostR;
   dst.tpMode               = src.tpMode;
   dst.tp1Fraction          = src.tp1Fraction;
   dst.breakEven            = src.breakEven;
   dst.maxHoldMin           = src.maxHoldMin;
   dst.useSession           = src.useSession;
   dst.commissionPerLotSide = src.commissionPerLotSide;
   dst.slippageTicks        = src.slippageTicks;
   dst.tickSize             = src.tickSize;
   dst.digits               = src.digits;
   dst.commPrice            = src.commPrice;
  }

//+------------------------------------------------------------------+
//| Environment given to the detector at the close of each bar       |
//| (spec s.4 "The detector is pure").                               |
//+------------------------------------------------------------------+
struct BfEnv
  {
   bool              slotFree;            // no pending order and no position of this EA
   bool              sessionEntryOk;      // the next bar's open is inside the entry window
   bool              sessionCancel;       // the next bar's open is at or after the last entry time
   bool              riskOk;              // no lockout, trade limit not reached
   bool              spreadOk;            // spread filter passed
   double            sp;                  // spread at the decision moment (price units)
  };

void BfClearEnv(BfEnv &e)
  {
   e.slotFree       = false;
   e.sessionEntryOk = false;
   e.sessionCancel  = false;
   e.riskOk         = false;
   e.spreadOk       = false;
   e.sp             = 0.0;
  }

//+------------------------------------------------------------------+
//| A tracked setup (spec s.3-s.4).                                  |
//+------------------------------------------------------------------+
struct BfSetup
  {
   int               id;
   int               src;                 // BF_SOURCE_BPR / BF_SOURCE_FVG
   int               dir;                 // +1 long, -1 short
   int               status;              // ENUM_BF_STATUS
   int               reason;              // ENUM_BF_REASON (DONE only)
   int               ordKind;             // BF_ORD_*
   int               created;             // bar index u of creation
   double            B;                   // edge B (zone bottom)
   double            T;                   // true top T
   double            h;                   // T - B
   double            deep;                // Lo (long) or Hi (short)
   double            brk;                 // break level: Z.bottom (long, l < brk) or Z.top (short, h > brk)
   int               sweepBar;            // s (-1 = not computed)
   double            R;                   // range extreme before the sweep (logging only)
   double            M;                   // structure-shift level
   bool              mssDone;
   int               mssBar;              // -1 = none
   double            X;                   // rally extreme (frozen once ordered)
   double            O;                   // measured-move origin
   double            P;                   // order levels, rounded to the tick (0 until ordered)
   double            SL;
   double            TP1;
   double            TP2;
   int               decisionBar;         // -1 = none
  };

void BfClearSetup(BfSetup &s)
  {
   s.id          = 0;
   s.src         = BF_SOURCE_BPR;
   s.dir         = 0;
   s.status      = BF_ST_NONE;
   s.reason      = BF_R_NONE;
   s.ordKind     = BF_ORD_NONE;
   s.created     = -1;
   s.B           = 0.0;
   s.T           = 0.0;
   s.h           = 0.0;
   s.deep        = 0.0;
   s.brk         = 0.0;
   s.sweepBar    = -1;
   s.R           = 0.0;
   s.M           = 0.0;
   s.mssDone     = false;
   s.mssBar      = -1;
   s.X           = 0.0;
   s.O           = 0.0;
   s.P           = 0.0;
   s.SL          = 0.0;
   s.TP1         = 0.0;
   s.TP2         = 0.0;
   s.decisionBar = -1;
  }

void BfCopySetup(BfSetup &dst, const BfSetup &src)
  {
   dst.id          = src.id;
   dst.src         = src.src;
   dst.dir         = src.dir;
   dst.status      = src.status;
   dst.reason      = src.reason;
   dst.ordKind     = src.ordKind;
   dst.created     = src.created;
   dst.B           = src.B;
   dst.T           = src.T;
   dst.h           = src.h;
   dst.deep        = src.deep;
   dst.brk         = src.brk;
   dst.sweepBar    = src.sweepBar;
   dst.R           = src.R;
   dst.M           = src.M;
   dst.mssDone     = src.mssDone;
   dst.mssBar      = src.mssBar;
   dst.X           = src.X;
   dst.O           = src.O;
   dst.P           = src.P;
   dst.SL          = src.SL;
   dst.TP1         = src.TP1;
   dst.TP2         = src.TP2;
   dst.decisionBar = src.decisionBar;
  }

//+------------------------------------------------------------------+
//| Intent emitted by the detector (spec s.4): PLACE_LIMIT, MARKET,  |
//| CANCEL. 'type' uses the BF_EV_* codes of the same name.          |
//+------------------------------------------------------------------+
struct BfIntent
  {
   int               type;                // BF_EV_PLACE_LIMIT / BF_EV_MARKET / BF_EV_CANCEL
   int               id;
   int               dir;
   int               src;
   int               reason;              // CANCEL only
   int               bar;                 // bar index u of the decision
   double            P;
   double            SL;
   double            TP1;
   double            TP2;
  };

void BfClearIntent(BfIntent &x)
  {
   x.type   = BF_EV_NONE;
   x.id     = 0;
   x.dir    = 0;
   x.src    = BF_SOURCE_BPR;
   x.reason = BF_R_NONE;
   x.bar    = -1;
   x.P      = 0.0;
   x.SL     = 0.0;
   x.TP1    = 0.0;
   x.TP2    = 0.0;
  }

void BfCopyIntent(BfIntent &dst, const BfIntent &src)
  {
   dst.type   = src.type;
   dst.id     = src.id;
   dst.dir    = src.dir;
   dst.src    = src.src;
   dst.reason = src.reason;
   dst.bar    = src.bar;
   dst.P      = src.P;
   dst.SL     = src.SL;
   dst.TP1    = src.TP1;
   dst.TP2    = src.TP2;
  }

//+------------------------------------------------------------------+
//| Event record (spec s.9). The first ten fields are the JSON line  |
//| {"n","id","ev","dir","src","reason","P","SL","TP1","TP2"}; the   |
//| rest is a snapshot of the setup after the event (for the logs).  |
//| P/SL/TP1/TP2 are the setup's order levels at the time of the     |
//| event: 0 until an order is decided.                              |
//+------------------------------------------------------------------+
struct BfEvent
  {
   int               n;                   // bar index u being processed
   int               id;
   int               ev;                  // ENUM_BF_EVENT
   int               dir;
   int               src;
   int               reason;              // ENUM_BF_REASON (DONE / CANCEL)
   double            P;
   double            SL;
   double            TP1;
   double            TP2;
   // snapshot
   int               status;
   int               ordKind;
   int               created;
   double            B;
   double            T;
   double            h;
   int               sweepBar;
   double            M;
   bool              mssDone;
   int               mssBar;
   double            X;
   double            O;
   int               decisionBar;
  };

void BfClearEvent(BfEvent &e)
  {
   e.n           = -1;
   e.id          = 0;
   e.ev          = BF_EV_NONE;
   e.dir         = 0;
   e.src         = BF_SOURCE_BPR;
   e.reason      = BF_R_NONE;
   e.P           = 0.0;
   e.SL          = 0.0;
   e.TP1         = 0.0;
   e.TP2         = 0.0;
   e.status      = BF_ST_NONE;
   e.ordKind     = BF_ORD_NONE;
   e.created     = -1;
   e.B           = 0.0;
   e.T           = 0.0;
   e.h           = 0.0;
   e.sweepBar    = -1;
   e.M           = 0.0;
   e.mssDone     = false;
   e.mssBar      = -1;
   e.X           = 0.0;
   e.O           = 0.0;
   e.decisionBar = -1;
  }

void BfCopyEvent(BfEvent &dst, const BfEvent &src)
  {
   dst.n           = src.n;
   dst.id          = src.id;
   dst.ev          = src.ev;
   dst.dir         = src.dir;
   dst.src         = src.src;
   dst.reason      = src.reason;
   dst.P           = src.P;
   dst.SL          = src.SL;
   dst.TP1         = src.TP1;
   dst.TP2         = src.TP2;
   dst.status      = src.status;
   dst.ordKind     = src.ordKind;
   dst.created     = src.created;
   dst.B           = src.B;
   dst.T           = src.T;
   dst.h           = src.h;
   dst.sweepBar    = src.sweepBar;
   dst.M           = src.M;
   dst.mssDone     = src.mssDone;
   dst.mssBar      = src.mssBar;
   dst.X           = src.X;
   dst.O           = src.O;
   dst.decisionBar = src.decisionBar;
  }

#endif
//+------------------------------------------------------------------+
