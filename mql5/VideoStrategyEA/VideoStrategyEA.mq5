//+------------------------------------------------------------------------------------------------+
//| VideoStrategyEA.mq5                                              PROJECT QUANTUM EDGE (research) |
//|                                                                                                 |
//| Reconstruction of the method shown in "I Made $1.4M Trading Gold, Here's What Actually Works"   |
//| (tomtrades, https://www.youtube.com/watch?v=xSVlVpXLuV0): a gold reversal of an hourly          |
//| candle's overextension, confirmed by a 1-minute type-3 shift, taken only when DXY shows the     |
//| mirror image of the entry model at the same time ("entry model inversion").                     |
//|                                                                                                 |
//| Specification : research/STRATEGY_RULEBOOK.md, research/ALGORITHM_SPECIFICATION.md              |
//| Reference impl: qe/video_strategy (Python, unit-tested; same functions and reason codes)        |
//| Traceability  : reports/VIDEO_VS_EA_VALIDATION.md                                               |
//|                                                                                                 |
//| STATUS: NOT YET COMPILED — written without MetaEditor (none available in the build sandbox).    |
//|         Compile in MetaEditor and report any error/warning (reports/COMPILATION_REPORT.md).     |
//| SAFETY: trades only in the Strategy Tester or on DEMO accounts. REAL accounts are log-only;     |
//|         there is deliberately no input to change this (live trading needs separate approval).   |
//| Install: copy the VideoStrategyEA folder (this file + include/) to MQL5/Experts/.               |
//+------------------------------------------------------------------------------------------------+
#property copyright "Project Quantum Edge (research)"
#property version   "1.00"
#property description "Gold reversal + DXY entry-model inversion (video reconstruction). Tester/demo only."

#include "include/Defines.mqh"
#include "include/SessionManager.mqh"
#include "include/MarketData.mqh"
#include "include/MarketStructure.mqh"
#include "include/DebugLogger.mqh"
#include "include/EntryEngine.mqh"
#include "include/RiskManager.mqh"
#include "include/TradeManager.mqh"
#include "include/Visualization.mqh"

//==============================================================================================
input group "==== GENERAL ===="
input long                InpMagic             = 26100401;      // Magic number
input string              InpComment           = "VSEA";        // Order comment prefix

input group "==== RISK (project hard limits; never raise) ===="
input double              InpRiskPercent       = 0.20;          // Risk per trade, % equity incl. commission (max 0.20)
input double              InpMaxDailyLossPct   = 1.00;          // Planned daily loss, % (FX day 17:00 NY; max 1.00)
input int                 InpMaxTradesPerDay   = 0;             // Max trades per FX day (0 = off; safety layer)
input double              InpCommissionLotSide = 3.50;          // Commission per lot per side, account ccy (UNVERIFIED)

input group "==== SESSION ===="
input ENUM_VS_SESSION     InpSessionPreset     = VS_SES_ASIA2_TO_LONDON4; // Trading hours (MKT-5)
input ENUM_VS_SERVER_TIME InpServerTime        = VS_SERVER_NY_PLUS_7;     // Broker server-time convention
input int                 InpFixedUtcOffsetH   = 0;             // Only for 'fixed offset' mode

input group "==== EXECUTION ===="
input int                 InpMaxSpreadPoints   = 0;             // Max spread in points to open (0 = off; safety layer)
input int                 InpSlippagePoints    = 30;            // Max deviation for market orders (points)
input double              InpSizingSlipTicks   = 1.0;           // Adverse ticks added to the stop distance for sizing
input int                 InpMaxOrderErrors    = 3;             // Consecutive order errors -> suspend for the FX day

input group "==== STRATEGY (video defaults) ===="
input ENUM_VS_CANDLE_MODE InpCandleMode        = VS_CANDLE_H1;  // Candle timeframe(s) (MKT-4, A-07)
input int                 InpH1MinExtMinutes   = 18;            // H1: min overextension minutes (EXT-2)
input int                 InpH1ShiftStart      = 22;            // H1: shift window start minute (SHF-3)
input int                 InpH1ShiftEnd        = 52;            // H1: shift window end minute (SHF-3)
input int                 InpM15MinExtMinutes  = 5;             // M15: min overextension minutes (experimental)
input int                 InpM15ShiftStart     = 6;             // M15: shift window start minute (experimental)
input int                 InpM15ShiftEnd       = 13;            // M15: shift window end minute (experimental)
input double              InpMaxExtPullback    = 0.50;          // Max internal pullback of the extension (EXT-3)
input int                 InpMtfLookbackMin    = 300;           // Middle-timeframe lookback, minutes (CTX-1)
input double              InpZigZagAtrMult     = 2.0;           // MTF zig-zag threshold, x ATR(M5,14) (CTX-2)
input double              InpTrendMaxRatio     = 0.50;          // Median pullback ratio below this = TREND (CTX-3)
input double              InpRangeMinRatio     = 0.75;          // ... at/above this = RANGE (CTX-3)
input double              InpMinCoverage       = 0.80;          // Min share of MTF minutes present (CTX-5)
input ENUM_VS_LOCATION    InpLocationMode      = VS_LOC_HALF;   // Location rule (EXT-4)
input double              InpMinLocRetrace     = 0.50;          // HALF mode: fraction of the previous opposite leg
input int                 InpPivotStrength     = 2;             // M1 pivot strength N (SHF-1)
input ENUM_VS_BREAK       InpBreakConfirm      = VS_BREAK_CLOSE;// Break confirmation (SHF-2)
input ENUM_VS_ENTRY       InpEntryMode         = VS_ENTRY_BREAK;// Entry (ENT-1 / ENT-2)
input ENUM_VS_TARGET      InpTargetMode        = VS_TARGET_EXT50;// Target (TP-1)
input double              InpFixedR            = 1.0;           // FIXED_R target multiple
input double              InpStopBufferAtr     = 0.10;          // Stop buffer, x ATR(M1,14) (SL-1)
input int                 InpStopBufferPoints  = 0;             // Stop buffer floor, points (SL-1)
input bool                InpAdjustSellTp      = true;          // Sell TP + spread (trigger at the bid-chart level)
input int                 InpMaxHoldMinutes    = 120;           // Time stop, minutes (project rule <= 120)

input group "==== CORRELATION (DXY) ===="
input ENUM_VS_DXY_MODE    InpDxyMode           = VS_DXY_FULL;   // DXY entry-model inversion (COR-1..3)
input ENUM_VS_DXY_SOURCE  InpDxySource         = VS_DXYSRC_AUTO;// DXY source (COR-5)
input string              InpDxySymbol         = "";            // Broker dollar-index symbol, e.g. DXY / USDX (blank = none)
input string              InpSymbolSuffix      = "";            // Suffix of the six FX pairs for synthetic DXY (e.g. ".a")

input group "==== RESEARCH OPTIONS (off = video) ===="
input bool                InpRequirePrevCandleBreak = false;    // EXT-5: extreme beyond previous candle high/low
input double              InpMinExtAtrMult     = 0.0;           // EXT-6: min extension size, x ATR(M1,14)
input double              InpMinBreakAtr       = 0.0;           // SHF-2: min break distance, x ATR(M1,14)

input group "==== VISUALIZATION / LOGS ===="
input bool                InpShowStructure     = true;          // Candle box, MTF legs, extension, shift
input bool                InpShowLevels        = true;          // Location level, protected swing
input bool                InpShowEntries       = true;          // Entry / SL / TP lines
input bool                InpShowPanel         = true;          // State panel
input ENUM_VS_LOG_LEVEL   InpLogLevel          = VS_LOG_SETUPS; // Journal verbosity
input bool                InpLogCsv            = true;          // CSV logs (Common/Files)

//==============================================================================================
struct SPositionContext
  {
   bool     active;
   bool     pending;
   ulong    orderTicket;
   int      setupId;
   int      tf;
   int      tracker;
   int      dir;
   datetime signalTime;
   datetime entryTime;
   datetime candleEnd;
   double   E;
   double   O;
   double   B;
   double   tpLevel;
   double   sl;
   double   tp;
   double   spread;
   double   buf;
   double   plannedRisk;
   double   plannedRR;
  };

CSessionManager  g_ses;
CMarketData      g_md;
CSeries          g_gold;
CSeries          g_dxy;
CCandleTracker   g_trk[2];
int              g_nTrk = 0;
CRiskManager     g_risk;
CTradeManager    g_tm;
CLogger          g_log;
CVisual          g_vis;
SStrategyParams  g_p;
SPositionContext g_pos;
datetime         g_lastBar = 0;
long             g_lastFxDay = -1;
int              g_nextId = 1;
string           g_lastReason = "";
double           g_sumR = 0.0;
int              g_nR = 0;

//+------------------------------------------------------------------+
bool ValidateInputs(string &why)
  {
   if(InpRiskPercent <= 0 || InpRiskPercent > 0.20) { why = "RiskPercent must be in (0, 0.20]"; return false; }
   if(InpMaxDailyLossPct <= 0 || InpMaxDailyLossPct > 1.00) { why = "MaxDailyLossPct must be in (0, 1.00]"; return false; }
   if(InpMaxHoldMinutes < 1 || InpMaxHoldMinutes > 120) { why = "MaxHoldMinutes must be in [1, 120]"; return false; }
   if(!(0 < InpH1ShiftStart && InpH1ShiftStart <= InpH1ShiftEnd && InpH1ShiftEnd <= 60)) { why = "H1 shift window"; return false; }
   if(!(0 < InpM15ShiftStart && InpM15ShiftStart <= InpM15ShiftEnd && InpM15ShiftEnd <= 15)) { why = "M15 shift window"; return false; }
   if(InpPivotStrength < 1 || InpPivotStrength > 10) { why = "PivotStrength must be 1..10"; return false; }
   if(InpMtfLookbackMin < 60 || InpMtfLookbackMin > 720) { why = "MtfLookbackMin must be 60..720"; return false; }
   return true;
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   string why;
   if(!ValidateInputs(why)) { Print("VideoStrategyEA: invalid input: ", why); return INIT_PARAMETERS_INCORRECT; }
   g_p.sessionPreset = InpSessionPreset;
   g_p.mtfLookbackMin = InpMtfLookbackMin;
   g_p.minCoverage = InpMinCoverage;
   g_p.zzAtrMult = InpZigZagAtrMult;
   g_p.zzAtrPeriod = 14;
   g_p.trendMaxRatio = InpTrendMaxRatio;
   g_p.rangeMinRatio = InpRangeMinRatio;
   g_p.locationMode = InpLocationMode;
   g_p.minLocRetrace = InpMinLocRetrace;
   g_p.requirePrevCandleBreak = InpRequirePrevCandleBreak;
   g_p.minExtAtrMult = InpMinExtAtrMult;
   g_p.maxExtPullback = InpMaxExtPullback;
   g_p.pivotStrength = InpPivotStrength;
   g_p.breakConfirm = InpBreakConfirm;
   g_p.minBreakAtr = InpMinBreakAtr;
   g_p.dxyMode = InpDxyMode;
   g_p.entryMode = InpEntryMode;
   g_p.stopBufferAtr = InpStopBufferAtr;
   g_p.stopBufferPoints = InpStopBufferPoints;
   g_p.targetMode = InpTargetMode;
   g_p.fixedR = InpFixedR;
   g_p.adjustSellTp = InpAdjustSellTp;
   g_p.maxHoldMin = InpMaxHoldMinutes;
   g_p.atrPeriodM1 = 14;

   g_ses.Init(InpServerTime, InpFixedUtcOffsetH);
   g_log.Init(InpLogLevel, InpLogCsv, _Symbol, InpMagic);
   g_vis.Init(InpShowStructure, InpShowLevels, InpShowEntries, InpShowPanel);
   int bars = InpMtfLookbackMin + 60 + 2 * InpPivotStrength + 120;
   if(!g_md.Init(_Symbol, InpDxySource, InpDxySymbol, InpSymbolSuffix, bars))
     {
      if(InpDxyMode != VS_DXY_OFF) { Print("VideoStrategyEA: ", g_md.lastError); return INIT_FAILED; }
     }
   if(InpDxyMode == VS_DXY_OFF)
      Print("VideoStrategyEA: WARNING DxyMode=OFF is a research ablation, not the video strategy.");
   if(StringFind(_Symbol, "XAU") < 0 && StringFind(_Symbol, "GOLD") < 0)
      Print("VideoStrategyEA: WARNING the video applies this method to gold only; symbol is ", _Symbol);

   STiming h1, m15;
   h1.candleMin = 60; h1.minExtMin = InpH1MinExtMinutes; h1.shiftStart = InpH1ShiftStart; h1.shiftEnd = InpH1ShiftEnd;
   m15.candleMin = 15; m15.minExtMin = InpM15MinExtMinutes; m15.shiftStart = InpM15ShiftStart; m15.shiftEnd = InpM15ShiftEnd;
   g_nTrk = 0;
   if(InpCandleMode == VS_CANDLE_H1 || InpCandleMode == VS_CANDLE_H1_AND_M15) g_trk[g_nTrk++].Init(h1, g_p, GetPointer(g_ses), GetPointer(g_log));
   if(InpCandleMode == VS_CANDLE_M15 || InpCandleMode == VS_CANDLE_H1_AND_M15) g_trk[g_nTrk++].Init(m15, g_p, GetPointer(g_ses), GetPointer(g_log));

   g_risk.Init(_Symbol, InpRiskPercent, InpMaxDailyLossPct, InpCommissionLotSide, InpMaxTradesPerDay);
   g_tm.Init(_Symbol, InpMagic, InpSlippagePoints, InpMaxOrderErrors);
   ZeroMemory(g_pos);
   ulong tk;
   if(g_tm.SelectPosition(tk))
     {
      g_pos.active = true;
      g_pos.entryTime = (datetime)PositionGetInteger(POSITION_TIME);
      g_pos.dir = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
      Print("VideoStrategyEA: recovered an open position ", tk);
     }
   PrintFormat("VideoStrategyEA started: %s | DXY %s | candle mode %s | entry %s | DXY mode %s",
               g_tm.modeNote, (InpDxyMode == VS_DXY_OFF ? "not used" : g_md.DxyDescription()),
               EnumToString(InpCandleMode), EnumToString(InpEntryMode), EnumToString(InpDxyMode));
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   for(int i = 0; i < g_nTrk; i++) g_trk[i].Finish();
   if(reason == REASON_REMOVE || reason == REASON_CHARTCLOSE) g_vis.DeleteAll();
  }

//+------------------------------------------------------------------+
double CurrentSpread(void)
  {
   MqlTick tk;
   if(!SymbolInfoTick(_Symbol, tk)) return VSEA_NA;
   return tk.ask - tk.bid;
  }

//+------------------------------------------------------------------+
//| signal -> order (ENT-1/2, SL-1, TP-1, RSK, SAF)                  |
//+------------------------------------------------------------------+
void Reject(const int ti, const SSignal &sig, const string reason, const bool finishCandle)
  {
   g_trk[ti].SetOutcome(reason, finishCandle);
   g_lastReason = reason;
   g_log.Setup(sig.setupId, sig.tf, TimeCurrent(), "NO ORDER: " + reason);
  }

void HandleSignal(const int ti, const SSignal &sig)
  {
   ulong tk;
   if(g_pos.active || g_tm.SelectPosition(tk) || g_tm.SelectPendingOrder(tk)) { Reject(ti, sig, R_SAFE_POSITION_OPEN, false); return; }
   if(g_tm.Breaker()) { Reject(ti, sig, R_SAFE_ORDER_ERROR, false); return; }
   MqlTick q;
   if(!SymbolInfoTick(_Symbol, q)) { Reject(ti, sig, R_SAFE_ORDER_ERROR, false); return; }
   double pt = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double spread = q.ask - q.bid;
   if(InpMaxSpreadPoints > 0 && spread > InpMaxSpreadPoints * pt) { Reject(ti, sig, R_SAFE_SPREAD, false); return; }
   int dir = sig.dir;
   double E = sig.extE, O = sig.extO;
   double tpLevel = O + 0.5 * (E - O);
   double buf = MathMax(InpStopBufferPoints * pt, VsValid(sig.atr) ? InpStopBufferAtr * sig.atr : 0.0);
   double sl = (dir < 0) ? E + spread + buf : E - buf;
   double tp = (dir < 0) ? tpLevel + (InpAdjustSellTp ? spread : 0.0) : tpLevel;
   double tick = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tick <= 0) tick = pt;

   bool limitMode = (InpEntryMode == VS_ENTRY_PULLBACK_50);
   double limitPrice = 0.0;
   double entryRef = (dir < 0) ? q.bid : q.ask;
   double sizeRef = entryRef;
   if(limitMode)
     {
      double lvl = sig.breakLeg + 0.5 * (E - sig.breakLeg);
      limitPrice = (dir < 0) ? lvl : lvl + spread;
      double worst = tpLevel + 0.5 * (E - tpLevel);
      sizeRef = (dir < 0) ? worst : worst + spread;
      // price already beyond the limit: a limit would fill at once -> market (same as the reference's next-open fill)
      if((dir < 0 && q.bid >= limitPrice) || (dir > 0 && q.ask <= limitPrice)) limitMode = false;
      else entryRef = limitPrice;
     }
   if(InpTargetMode == VS_TARGET_FIXED_R) tp = entryRef + dir * InpFixedR * MathAbs(entryRef - sl);
   double reward = (tp - entryRef) * dir, risk = (entryRef - sl) * dir;
   if(reward <= 0 || risk <= 0) { Reject(ti, sig, R_INV_TARGET_REACHED, false); return; }
   double planned;
   double lots = g_risk.SizeLots(MathAbs(sizeRef - sl) + InpSizingSlipTicks * tick, planned);
   if(lots <= 0) { Reject(ti, sig, R_SAFE_SIZE, false); return; }
   string rr = g_risk.CheckNewTrade(planned);
   if(rr != "") { Reject(ti, sig, rr, false); return; }
   if(!g_tm.StopsOk(dir, entryRef, sl, tp)) { Reject(ti, sig, R_SAFE_STOPS_LEVEL, false); return; }
   if(!g_tm.MarginOk(dir, lots, entryRef)) { Reject(ti, sig, R_SAFE_MARGIN, false); return; }

   string cmt = StringFormat("%s#%dM%d", InpComment, sig.setupId, sig.tf);
   string desc = StringFormat("%s %.2f lots entry=%.2f SL=%.2f TP=%.2f (plan RR %.2f, risk %.2f)",
                              dir < 0 ? "SELL" : "BUY", lots, entryRef, sl, tp, reward / risk, planned);
   g_vis.Orders(sig.setupId, sig.tf, TimeCurrent(), TimeCurrent() + 30 * 60, entryRef, sl, tp);
   if(!g_tm.tradingAllowed)
     {
      g_log.Setup(sig.setupId, sig.tf, TimeCurrent(), "PAPER (real account, log-only): " + desc);
      g_trk[ti].SetOutcome(R_PAPER, true);
      g_lastReason = R_PAPER;
      return;
     }
   ZeroMemory(g_pos);
   g_pos.setupId = sig.setupId; g_pos.tf = sig.tf; g_pos.tracker = ti; g_pos.dir = dir;
   g_pos.signalTime = sig.signalBarTime; g_pos.candleEnd = g_trk[ti].CandleEnd();
   g_pos.E = E; g_pos.O = O; g_pos.B = sig.breakLeg; g_pos.tpLevel = tpLevel; g_pos.sl = sl; g_pos.tp = tp;
   g_pos.spread = spread; g_pos.buf = buf; g_pos.plannedRisk = planned; g_pos.plannedRR = reward / risk;
   if(!limitMode)
     {
      if(!g_tm.OpenMarket(dir, lots, sl, tp, cmt)) { Reject(ti, sig, R_SAFE_ORDER_ERROR, false); g_log.Error(g_tm.lastError); return; }
      g_pos.active = true;
      g_pos.entryTime = TimeCurrent();
      g_risk.OnTradeOpened();
      g_trk[ti].SetOutcome(R_TRADE, true);
      g_lastReason = R_TRADE;
      g_log.Setup(sig.setupId, sig.tf, TimeCurrent(), "MARKET " + desc);
      return;
     }
   ulong ticket;
   if(!g_tm.PlaceLimit(dir, lots, limitPrice, sl, tp, g_pos.candleEnd, cmt, ticket))
     { Reject(ti, sig, R_SAFE_ORDER_ERROR, false); g_log.Error(g_tm.lastError); return; }
   g_pos.active = true;
   g_pos.pending = true;
   g_pos.orderTicket = ticket;
   g_trk[ti].SetOutcome(R_TRADE, false);       // provisional; replaced if the limit is cancelled
   g_log.Setup(sig.setupId, sig.tf, TimeCurrent(), StringFormat("LIMIT @%.2f %s", limitPrice, desc));
  }

//+------------------------------------------------------------------+
//| ENT-2 pending order: re-anchor / cancel on each closed bar        |
//+------------------------------------------------------------------+
void ManagePending(const int t)
  {
   if(!g_pos.active || !g_pos.pending) return;
   ulong ptk;
   bool hasPos = g_tm.SelectPosition(ptk);
   if(!OrderSelect(g_pos.orderTicket))
     {
      if(hasPos)
        {
         g_pos.pending = false;
         g_pos.entryTime = (datetime)PositionGetInteger(POSITION_TIME);
         g_risk.OnTradeOpened();
         g_trk[g_pos.tracker].SetOutcome(R_TRADE, true);
         g_log.Setup(g_pos.setupId, g_pos.tf, TimeCurrent(), "limit FILLED");
        }
      else
        {
         g_trk[g_pos.tracker].SetOutcome(R_INV_NO_PULLBACK, true);
         g_log.Setup(g_pos.setupId, g_pos.tf, TimeCurrent(), "limit expired: " + R_INV_NO_PULLBACK);
         ZeroMemory(g_pos);
        }
      return;
     }
   int dir = g_pos.dir;
   string cancel = "";
   if((dir < 0 && g_gold.l[t] <= g_pos.tpLevel) || (dir > 0 && g_gold.h[t] >= g_pos.tpLevel)) cancel = R_INV_TARGET_REACHED;
   else if(g_gold.t[t] + 60 >= g_pos.candleEnd) cancel = R_INV_NO_PULLBACK;
   if(cancel != "")
     {
      g_tm.DeleteOrder(g_pos.orderTicket);
      g_trk[g_pos.tracker].SetOutcome(cancel, true);
      g_log.Setup(g_pos.setupId, g_pos.tf, TimeCurrent(), "limit cancelled: " + cancel);
      ZeroMemory(g_pos);
      return;
     }
   bool moved = false;
   if(dir < 0 && g_gold.l[t] < g_pos.B) { g_pos.B = g_gold.l[t]; moved = true; }
   if(dir > 0 && g_gold.h[t] > g_pos.B) { g_pos.B = g_gold.h[t]; moved = true; }
   if(moved)
     {
      double lvl = g_pos.B + 0.5 * (g_pos.E - g_pos.B);
      double price = (dir < 0) ? lvl : lvl + g_pos.spread;
      if(g_tm.ModifyLimit(g_pos.orderTicket, price, g_pos.sl, g_pos.tp, g_pos.candleEnd))
         g_log.Verbose(g_pos.setupId, g_pos.tf, TimeCurrent(), StringFormat("limit re-anchored @%.2f", price));
     }
  }

//+------------------------------------------------------------------+
//| MGT-2/3: time stop and rollover exit (no BE/partials/trailing)    |
//+------------------------------------------------------------------+
void ManagePosition(void)
  {
   if(!g_pos.active || g_pos.pending) return;
   ulong tk;
   if(!g_tm.SelectPosition(tk)) return;
   datetime opened = (datetime)PositionGetInteger(POSITION_TIME);
   datetime now = TimeCurrent();
   string why = "";
   if(now - opened >= InpMaxHoldMinutes * 60) why = "TIME";
   else if(g_ses.InRolloverBlackout(now)) why = "ROLLOVER";
   if(why != "" && g_tm.ClosePosition(tk))
      g_log.Setup(g_pos.setupId, g_pos.tf, now, "position closed: " + why);
  }

//+------------------------------------------------------------------+
//| closed trades -> CSV (OnTradeTransaction)                         |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   if(!HistoryDealSelect(trans.deal)) return;
   if(HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != InpMagic) return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol) return;
   ENUM_DEAL_ENTRY entry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(trans.deal, DEAL_ENTRY);
   if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_OUT_BY) return;
   ulong posId = (ulong)HistoryDealGetInteger(trans.deal, DEAL_POSITION_ID);
   ulong still;
   if(g_tm.SelectPosition(still) && (ulong)PositionGetInteger(POSITION_IDENTIFIER) == posId) return;   // partial close
   if(!HistorySelectByPosition((long)posId)) return;
   double profit = 0, comm = 0, swap = 0, entryPx = 0, exitPx = 0, lots = 0;
   datetime tIn = 0, tOut = 0;
   string exitReason = "OTHER";
   for(int i = 0; i < HistoryDealsTotal(); i++)
     {
      ulong d = HistoryDealGetTicket(i);
      if(d == 0) continue;
      profit += HistoryDealGetDouble(d, DEAL_PROFIT);
      comm += HistoryDealGetDouble(d, DEAL_COMMISSION);
      swap += HistoryDealGetDouble(d, DEAL_SWAP);
      ENUM_DEAL_ENTRY de = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(d, DEAL_ENTRY);
      if(de == DEAL_ENTRY_IN) { entryPx = HistoryDealGetDouble(d, DEAL_PRICE); tIn = (datetime)HistoryDealGetInteger(d, DEAL_TIME); lots += HistoryDealGetDouble(d, DEAL_VOLUME); }
      else
        {
         exitPx = HistoryDealGetDouble(d, DEAL_PRICE);
         tOut = (datetime)HistoryDealGetInteger(d, DEAL_TIME);
         ENUM_DEAL_REASON r = (ENUM_DEAL_REASON)HistoryDealGetInteger(d, DEAL_REASON);
         exitReason = (r == DEAL_REASON_SL) ? "SL" : (r == DEAL_REASON_TP) ? "TP" : (r == DEAL_REASON_EXPERT) ? "EA_CLOSE" : EnumToString(r);
        }
     }
   double net = profit + comm + swap;
   double R = (g_pos.plannedRisk > 0) ? net / g_pos.plannedRisk : 0.0;
   g_sumR += R; g_nR++;
   string line = StringFormat("%d;%d;%d;%s;%s;%s;%.3f;%.3f;%.3f;%.3f;%.2f;%.2f;%.2f;%.2f;%.2f;%.3f;%s;%s;%.3f",
                              g_pos.setupId, g_pos.tf, g_pos.dir, CLogger::Ts(g_pos.signalTime), CLogger::Ts(tIn), CLogger::Ts(tOut),
                              entryPx, g_pos.sl, g_pos.tp, exitPx, lots, profit, comm, swap, g_pos.plannedRisk, R, exitReason,
                              g_ses.SessionLabel(tIn), g_pos.plannedRR);
   g_log.Trade(line);
   g_log.Setup(g_pos.setupId, g_pos.tf, tOut, StringFormat("CLOSED %s net=%.2f R=%.2f", exitReason, net, R));
   ZeroMemory(g_pos);
  }

//+------------------------------------------------------------------+
//| main loop                                                         |
//+------------------------------------------------------------------+
void DrawTracker(const int i, const int t, const bool started)
  {
   CCandleTracker *tr = GetPointer(g_trk[i]);
   int id = tr.setupId, tf = tr.CandleMinutes();
   datetime open = tr.CandleOpen(), end = tr.CandleEnd();
   if(started && tr.Active())
     {
      g_vis.MtfLegs(id, tf, tr.ctxG, StringFormat("MTF %s %.2f", ConditionName(tr.ctxG.condition), tr.ctxG.ratioMedian));
      g_vis.Level(id, tf, "locS", open, end, tr.LocationSell(), clrOrangeRed, "sell location (EXT-4)");
      g_vis.Level(id, tf, "locB", open, end, tr.LocationBuy(), clrDodgerBlue, "buy location (EXT-4)");
     }
   if(!tr.Active()) return;
   int cs = g_gold.LowerBound(open);
   double hi = g_gold.h[cs], lo = g_gold.l[cs];
   for(int k = cs; k <= t; k++) { hi = MathMax(hi, g_gold.h[k]); lo = MathMin(lo, g_gold.l[k]); }
   g_vis.CandleBox(id, tf, open, end, hi, lo, StringFormat("#%d M%d", id, tf));
   if(tr.gBull.e >= 0 && tr.gBull.o >= 0)
      g_vis.Extension(id, tf, "extUp", g_gold.t[tr.gBull.o], tr.gBull.O, g_gold.t[tr.gBull.e], tr.gBull.E,
                      StringFormat("bullish extension PB=%.2f", tr.gBull.PB));
   if(tr.gBear.e >= 0 && tr.gBear.o >= 0)
      g_vis.Extension(id, tf, "extDn", g_gold.t[tr.gBear.o], tr.gBear.O, g_gold.t[tr.gBear.e], tr.gBear.E,
                      StringFormat("bearish extension PB=%.2f", tr.gBear.PB));
  }

void OnNewBar(void)
  {
   long fxDay = g_ses.FxDay(TimeCurrent());
   g_risk.UpdateDay(fxDay);
   if(fxDay != g_lastFxDay) { g_lastFxDay = fxDay; g_tm.ResetBreaker(); }   // SAF-5: breaker lasts one FX day
   ulong syncTk;
   if(g_pos.active && !g_pos.pending && !g_tm.SelectPosition(syncTk)) ZeroMemory(g_pos);   // missed close event
   if(!g_md.LoadGold(g_gold)) { g_log.Error(g_md.lastError); return; }
   g_gold.ComputePivots(InpPivotStrength);
   if(InpDxyMode != VS_DXY_OFF)
     {
      if(!g_md.LoadDxy(g_gold, g_dxy)) g_log.Error(g_md.lastError);
      g_dxy.ComputePivots(InpPivotStrength);
     }
   else
     {
      g_dxy.Resize(g_gold.n);
      for(int k = 0; k < g_gold.n; k++) { g_dxy.t[k] = g_gold.t[k]; g_dxy.o[k] = VSEA_NA; g_dxy.h[k] = VSEA_NA; g_dxy.l[k] = VSEA_NA; g_dxy.c[k] = VSEA_NA; g_dxy.phPrev[k] = -1; g_dxy.plPrev[k] = -1; }
     }
   int t = g_gold.n - 1;
   if(t < InpMtfLookbackMin) return;
   ManagePending(t);
   for(int i = 0; i < g_nTrk; i++)
     {
      SSignal sig;
      bool started = false;
      bool ok = g_trk[i].OnBar(g_gold, g_dxy, t, g_nextId, started, sig);
      if(started) g_nextId++;
      DrawTracker(i, t, started);
      if(ok)
        {
         g_vis.Shift(sig.setupId, sig.tf, sig.dir, sig.protTime, sig.protPrice, sig.signalBarTime,
                     sig.dir < 0 ? g_gold.h[t] : g_gold.l[t], StringFormat("type-3 shift, minute %d", sig.minute));
         HandleSignal(i, sig);
        }
      else if(!g_trk[i].Active() && g_trk[i].Reason() != "" && g_trk[i].Reason() != R_INV_SESSION && started)
         g_vis.Invalidation(g_trk[i].setupId, g_trk[i].CandleMinutes(), g_trk[i].CandleOpen(), g_gold.h[t], g_trk[i].Reason());
     }
  }

void UpdatePanel(void)
  {
   if(!InpShowPanel) return;
   double pt = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double sp = CurrentSpread();
   g_vis.PanelSet(0, "VideoStrategyEA  gold reversal + DXY entry-model inversion");
   g_vis.PanelSet(1, "MODE: " + g_tm.modeNote + " | DXY: " + (InpDxyMode == VS_DXY_OFF ? "OFF (ablation)" : g_md.DxyDescription()));
   for(int i = 0; i < 2; i++)
     {
      if(i >= g_nTrk) { g_vis.PanelSet(2 + i, ""); continue; }
      CCandleTracker *tr = GetPointer(g_trk[i]);
      g_vis.PanelSet(2 + i, StringFormat("M%d #%d STATE: %s | CONDITION: %s (%.2f) | %s", tr.CandleMinutes(), tr.setupId,
                                        tr.state, ConditionName(tr.ctxG.condition),
                                        VsValid(tr.ctxG.ratioMedian) ? tr.ctxG.ratioMedian : -1.0, tr.Reason()));
     }
   if(g_nTrk > 0)
     {
      CCandleTracker *t0 = GetPointer(g_trk[0]);
      string dx = "n/a";
      if(VsValid(t0.xOpen))
         dx = StringFormat("since open %+.3f | shift up %s / down %s", g_dxy.c[g_dxy.n - 1] - t0.xOpen,
                           t0.xShiftUp >= 0 ? "yes" : "no", t0.xShiftDn >= 0 ? "yes" : "no");
      g_vis.PanelSet(4, "DXY: " + dx);
     }
   g_vis.PanelSet(5, StringFormat("SPREAD: %.0f points | LOCKOUT: %s | TRADES TODAY: %d", VsValid(sp) ? sp / pt : -1.0,
                                  g_risk.Lockout() ? "YES" : "no", g_risk.TradesToday()));
   g_vis.PanelSet(6, "POSITION: " + (g_pos.active ? (g_pos.pending ? "pending limit" : (g_pos.dir < 0 ? "SHORT" : "LONG")) : "none")
                  + " | LAST: " + g_lastReason);
   g_vis.PanelDraw();
  }

void OnTick()
  {
   datetime cur = iTime(_Symbol, PERIOD_M1, 0);
   if(cur == 0) return;
   if(cur != g_lastBar)
     {
      g_lastBar = cur;
      OnNewBar();
      UpdatePanel();
     }
   ManagePosition();
  }

double OnTester()
  {
   return (g_nR > 0) ? g_sumR / g_nR : 0.0;      // average R per trade (net of costs)
  }
//+------------------------------------------------------------------+
