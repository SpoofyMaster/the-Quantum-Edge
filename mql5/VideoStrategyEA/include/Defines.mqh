//+------------------------------------------------------------------+
//| Defines.mqh — enums, parameter and result structures             |
//| Rule IDs refer to research/STRATEGY_RULEBOOK.md                  |
//+------------------------------------------------------------------+
#ifndef VSEA_DEFINES_MQH
#define VSEA_DEFINES_MQH

#define VSEA_PREFIX      "VSEA_"
#define VSEA_MAX_PIVOTS  64
#define VSEA_NA          EMPTY_VALUE

enum ENUM_VS_CANDLE_MODE
  {
   VS_CANDLE_H1         = 0,   // H1 candle (video slide; default)
   VS_CANDLE_M15        = 1,   // M15 candle (experimental timings)
   VS_CANDLE_H1_AND_M15 = 2    // H1 and M15 trackers (closest to what the video shows)
  };

enum ENUM_VS_SESSION
  {
   VS_SES_ASIA2_TO_LONDON4 = 0, // 10:00 Tokyo .. 11:00 London candle opens
   VS_SES_STRICT           = 1, // 10:00 Tokyo candle and 08:00 London candle only
   VS_SES_ALL              = 2  // any hour except the NY rollover (research only)
  };

enum ENUM_VS_LOCATION
  {
   VS_LOC_HALF            = 0,  // beyond 50% of the previous opposite MTF leg (video)
   VS_LOC_CONDITION_AWARE = 1   // author's extended rule (range 75%, counter-trend 100%)
  };

enum ENUM_VS_BREAK
  {
   VS_BREAK_CLOSE = 0,          // M1 close beyond the protected swing
   VS_BREAK_WICK  = 1           // M1 wick beyond the protected swing
  };

enum ENUM_VS_DXY_MODE
  {
   VS_DXY_FULL             = 0, // opposite drive + opposite half + opposite type-3 shift
   VS_DXY_MIRROR_DIRECTION = 1, // opposite drive + opposite half
   VS_DXY_OFF              = 2  // research ablation only (NOT the video strategy)
  };

enum ENUM_VS_DXY_SOURCE
  {
   VS_DXYSRC_AUTO      = 0,     // broker symbol if present, else synthetic
   VS_DXYSRC_BROKER    = 1,     // broker dollar-index symbol only
   VS_DXYSRC_SYNTHETIC = 2      // ICE formula from six FX pairs (close-only)
  };

enum ENUM_VS_ENTRY
  {
   VS_ENTRY_BREAK       = 0,    // market order after the shift bar closes (video)
   VS_ENTRY_PULLBACK_50 = 1     // limit at 50% of the breaking leg (author's other videos)
  };

enum ENUM_VS_TARGET
  {
   VS_TARGET_EXT50   = 0,       // 50% of the overextension (video)
   VS_TARGET_FIXED_R = 1        // fixed reward:risk (research option)
  };

enum ENUM_VS_SERVER_TIME
  {
   VS_SERVER_NY_PLUS_7 = 0,     // server = New York + 7h (IC Markets and most NY-close brokers)
   VS_SERVER_EU_DST    = 1,     // server = UTC+2 winter / UTC+3 summer on EU DST dates
   VS_SERVER_FIXED     = 2      // server = UTC + fixed offset
  };

enum ENUM_VS_LOG_LEVEL
  {
   VS_LOG_ERRORS  = 0,
   VS_LOG_SETUPS  = 1,          // setup lifecycle (recommended)
   VS_LOG_VERBOSE = 2           // every evaluation
  };

enum ENUM_VS_COND { VS_COND_UNDEFINED = 0, VS_COND_TREND = 1, VS_COND_TRENDING_RANGE = 2, VS_COND_RANGE = 3 };

//--- reason codes (STRATEGY_RULEBOOK.md section J)
#define R_TRADE                 "TRADE"
#define R_INV_SESSION           "INV_SESSION"
#define R_INV_CONTEXT_TREND     "INV_CONTEXT_TREND"
#define R_INV_CONTEXT_UNDEFINED "INV_CONTEXT_UNDEFINED"
#define R_INV_NO_EXTENSION      "INV_NO_EXTENSION"
#define R_INV_LOCATION          "INV_LOCATION"
#define R_INV_NO_SHIFT          "INV_NO_SHIFT"
#define R_INV_DXY_SAME_DIR      "INV_DXY_SAME_DIRECTION"
#define R_INV_DXY_NO_INVERSION  "INV_DXY_NO_INVERSION"
#define R_INV_DXY_NO_DATA       "INV_DXY_NO_DATA"
#define R_INV_TARGET_REACHED    "INV_TARGET_REACHED"
#define R_INV_NO_PULLBACK       "INV_NO_PULLBACK"
#define R_INV_STRUCTURE_BROKEN  "INV_STRUCTURE_BROKEN"
#define R_SAFE_POSITION_OPEN    "SAFE_POSITION_OPEN"
#define R_SAFE_SPREAD           "SAFE_SPREAD"
#define R_SAFE_DAILY_LOSS       "SAFE_DAILY_LOSS"
#define R_SAFE_MAX_TRADES       "SAFE_MAX_TRADES"
#define R_SAFE_SIZE             "SAFE_SIZE"
#define R_SAFE_MARGIN           "SAFE_MARGIN"
#define R_SAFE_STOPS_LEVEL      "SAFE_STOPS_LEVEL"
#define R_SAFE_ORDER_ERROR      "SAFE_ORDER_ERROR"
#define R_PAPER                 "PAPER_SIGNAL"

//--- strategy parameters shared by all trackers (ALGORITHM_SPECIFICATION.md section 9)
struct SStrategyParams
  {
   int      sessionPreset;
   int      mtfLookbackMin;
   double   minCoverage;
   double   zzAtrMult;
   int      zzAtrPeriod;
   double   trendMaxRatio;
   double   rangeMinRatio;
   int      locationMode;
   double   minLocRetrace;
   bool     requirePrevCandleBreak;
   double   minExtAtrMult;
   double   maxExtPullback;
   int      pivotStrength;
   int      breakConfirm;
   double   minBreakAtr;
   int      dxyMode;
   int      entryMode;
   double   stopBufferAtr;
   double   stopBufferPoints;
   int      targetMode;
   double   fixedR;
   bool     adjustSellTp;
   int      maxHoldMin;
   int      atrPeriodM1;
  };

//--- per-tracker timing (MKT-4, EXT-2, SHF-3)
struct STiming
  {
   int      candleMin;
   int      minExtMin;
   int      shiftStart;
   int      shiftEnd;
  };

//--- middle-timeframe context (spec section 2)
struct SMtfContext
  {
   int      condition;      // ENUM_VS_COND
   int      direction;      // +1 bull, -1 bear, 0 neutral
   double   ratioMedian;
   int      nCompleted;
   double   coverage;
   double   theta;
   bool     hasDown;        // most recent down leg (start high Hs, end low Le)
   double   downHs;
   double   downLe;
   bool     hasUp;          // most recent up leg (start low Ls, end high He)
   double   upLs;
   double   upHe;
   int      nPivots;        // for drawing
   datetime pvTime[VSEA_MAX_PIVOTS];
   double   pvPrice[VSEA_MAX_PIVOTS];
  };

//--- a signal produced by a candle tracker at the close of a bar
struct SSignal
  {
   bool     valid;
   int      setupId;
   int      tf;             // candle minutes
   int      dir;            // +1 buy, -1 sell
   datetime candleOpen;
   datetime signalBarTime;  // open time of the shift bar (decision at its close)
   int      minute;         // close-minute of the shift bar inside the candle
   double   extE;           // extension extreme
   double   extO;           // extension origin
   datetime extETime;
   datetime extOTime;
   double   extPB;
   double   protPrice;      // protected swing broken by the shift
   datetime protTime;
   double   breakLeg;       // B: extreme of the breaking leg (for PULLBACK_50)
   double   atr;
   string   gate;
  };

#endif
