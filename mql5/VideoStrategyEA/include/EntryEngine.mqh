//+------------------------------------------------------------------+
//| EntryEngine.mqh — per-candle state machine (rulebook section M)   |
//| and the DXY correlation gate (COR-1..4).                          |
//| Mirrors qe/video_strategy/engine.py::CandleTracker.               |
//|                                                                    |
//| On every closed M1 bar the current candle is REPLAYED from its     |
//| open (<= 60 bars). The state is therefore a pure function of the   |
//| closed bars: restart-safe and identical to the Python reference.   |
//+------------------------------------------------------------------+
#ifndef VSEA_ENTRY_MQH
#define VSEA_ENTRY_MQH

#include "Defines.mqh"
#include "MarketData.mqh"
#include "MarketStructure.mqh"
#include "SessionManager.mqh"
#include "DebugLogger.mqh"

class CCandleTracker
  {
private:
   STiming           m_tm;
   SStrategyParams   m_p;
   CSessionManager  *m_ses;
   CLogger          *m_log;
   bool              m_useDxy;

   //--- candle state
   datetime          m_candle;
   bool              m_active;
   string            m_reason;
   string            m_gateReason;
   bool              m_flagValidExt;
   bool              m_flagExtNoLoc;
   bool              m_doneSell;
   bool              m_doneBuy;
   datetime          m_evalSell;     // time of the extreme already evaluated (SHF-5)
   datetime          m_evalBuy;
   double            m_locSell, m_locBuy, m_xLocBuy, m_xLocSell;
   bool              m_hasLocSell, m_hasLocBuy, m_hasXLocBuy, m_hasXLocSell;
   double            m_prevHigh, m_prevLow;
   int               m_lastDir;
   datetime          m_lastSignal;
   double            m_lastE, m_lastO, m_lastProt;

public:
   int               setupId;
   SMtfContext       ctxG;
   SMtfContext       ctxX;
   //--- replayed state of the last processed bar (for drawing / panel)
   CExtTracker       gBull, gBear, xBull, xBear;
   int               xShiftUp, xShiftDn;
   double            xOpen, xHi, xLo;
   string            state;

                     CCandleTracker(void) : m_ses(NULL), m_log(NULL), m_useDxy(true), m_candle(0), m_active(false), setupId(0)
     {
      gBull.sign = 1; gBear.sign = -1; xBull.sign = 1; xBear.sign = -1;
      state = "IDLE";
     }

   void              Init(const STiming &tm, const SStrategyParams &p, CSessionManager *ses, CLogger *log)
     {
      m_tm = tm; m_p = p; m_ses = ses; m_log = log;
      m_useDxy = (p.dxyMode != VS_DXY_OFF);
     }

   int               CandleMinutes(void) const { return m_tm.candleMin; }
   datetime          CandleOpen(void) const    { return m_candle; }
   datetime          CandleEnd(void) const     { return m_candle + m_tm.candleMin * 60; }
   bool              Active(void) const        { return m_active; }
   string            Reason(void) const        { return m_reason; }

   //--- the main EA reports what happened to a signal
   void              SetOutcome(const string reason, const bool finishCandle)
     {
      m_reason = reason;
      if(finishCandle) { m_active = false; state = "DONE"; }
     }

   //+---------------------------------------------------------------+
   //| candle lifecycle                                               |
   //+---------------------------------------------------------------+
   void              Finish(void)
     {
      if(m_candle == 0 || setupId == 0) return;
      if(m_reason == "")
        {
         if(m_gateReason != "") m_reason = m_gateReason;
         else if(m_flagValidExt) m_reason = R_INV_NO_SHIFT;
         else if(m_flagExtNoLoc) m_reason = R_INV_LOCATION;
         else m_reason = R_INV_NO_EXTENSION;
        }
      if(m_reason != R_INV_SESSION)
        {
         m_log.Event(setupId, m_tm.candleMin, m_candle, ConditionName(ctxG.condition),
                     VsValid(ctxG.ratioMedian) ? ctxG.ratioMedian : -1.0, m_reason, m_lastDir, m_lastSignal,
                     m_lastE, m_lastO, m_lastProt, m_gateReason);
         if(m_reason != R_TRADE)
            m_log.Setup(setupId, m_tm.candleMin, m_candle, "REJECTED reason=" + m_reason);
        }
      m_active = false;
      state = "IDLE";
     }

   void              Start(const CSeries &g, const CSeries &x, const datetime candle, const int newId)
     {
      m_candle = candle;
      setupId = newId;
      m_reason = ""; m_gateReason = "";
      m_flagValidExt = false; m_flagExtNoLoc = false;
      m_doneSell = false; m_doneBuy = false; m_evalSell = 0; m_evalBuy = 0;
      m_lastDir = 0; m_lastSignal = 0; m_lastE = 0; m_lastO = 0; m_lastProt = 0;
      m_hasLocSell = m_hasLocBuy = m_hasXLocBuy = m_hasXLocSell = false;
      ZeroMemory(ctxG); ZeroMemory(ctxX);
      ctxG.condition = VS_COND_UNDEFINED;
      int i0 = g.LowerBound(candle - m_tm.candleMin * 60), i1 = g.LowerBound(candle);
      m_prevHigh = VSEA_NA; m_prevLow = VSEA_NA;
      for(int k = i0; k < i1; k++)
        {
         m_prevHigh = VsValid(m_prevHigh) ? MathMax(m_prevHigh, g.h[k]) : g.h[k];
         m_prevLow  = VsValid(m_prevLow)  ? MathMin(m_prevLow, g.l[k])  : g.l[k];
        }
      m_active = m_ses.IsTradingCandle(candle, m_p.sessionPreset);
      if(!m_active) { m_reason = R_INV_SESSION; state = "OFF-SESSION"; return; }
      ComputeMtfContext(g, candle, m_p, ctxG);
      if(ctxG.condition == VS_COND_TREND) { m_active = false; m_reason = R_INV_CONTEXT_TREND; state = "DONE"; }
      else if(!ContextTradable(ctxG)) { m_active = false; m_reason = R_INV_CONTEXT_UNDEFINED; state = "DONE"; }
      m_log.Setup(setupId, m_tm.candleMin, candle, StringFormat("candle open; MTF condition=%s ratio=%.2f coverage=%.2f",
                  ConditionName(ctxG.condition), VsValid(ctxG.ratioMedian) ? ctxG.ratioMedian : -1.0, ctxG.coverage));
      if(!m_active) return;
      m_hasLocSell = LocationLevel(ctxG, -1, m_p, m_locSell);
      m_hasLocBuy  = LocationLevel(ctxG, 1, m_p, m_locBuy);
      if(m_useDxy)
        {
         ComputeMtfContext(x, candle, m_p, ctxX);
         m_hasXLocBuy  = LocationLevel(ctxX, 1, m_p, m_xLocBuy);
         m_hasXLocSell = LocationLevel(ctxX, -1, m_p, m_xLocSell);
        }
      state = "TRACK_EXTENSION";
     }

   //+---------------------------------------------------------------+
   //| EXT-1..6 validity of an extension at its extreme                |
   //+---------------------------------------------------------------+
   bool              ExtValid(const CSeries &g, const CExtTracker &ext)
     {
      if(ext.e < 0 || ext.Size() <= 0) return false;
      long dur = (long)(g.t[ext.e] - g.t[ext.o]) / 60 + 1;
      if(dur < m_tm.minExtMin || ext.PB >= m_p.maxExtPullback) return false;
      if(m_p.minExtAtrMult > 0)
        {
         double a = g.AtrAt(ext.e, m_p.atrPeriodM1);
         if(!VsValid(a) || ext.Size() < m_p.minExtAtrMult * a) return false;
        }
      if(m_p.requirePrevCandleBreak)
        {
         double ref = (ext.sign > 0) ? m_prevHigh : m_prevLow;
         if(!VsValid(ref) || (ext.E - ref) * ext.sign <= 0) return false;
        }
      bool has = (ext.sign > 0) ? m_hasLocSell : m_hasLocBuy;
      double lvl = (ext.sign > 0) ? m_locSell : m_locBuy;
      if(!has || (ext.E - lvl) * ext.sign < 0) { m_flagExtNoLoc = true; return false; }
      return true;
     }

   //+---------------------------------------------------------------+
   //| COR-1..3 (spec section 7). "" = pass                            |
   //+---------------------------------------------------------------+
   string            Gate(const CSeries &g, const CSeries &x, const int dir, const CExtTracker &ext, const int t)
     {
      if(!m_useDxy) return "";
      if(!VsValid(xOpen)) return R_INV_DXY_NO_DATA;
      int cs = g.LowerBound(m_candle);
      double xe = VSEA_NA;
      for(int j = ext.e; j >= cs; j--) if(VsValid(x.c[j])) { xe = x.c[j]; break; }
      if(!VsValid(xe)) return R_INV_DXY_NO_DATA;
      if(dir < 0)
        {
         if(!((xOpen - xLo) > (xHi - xOpen) && xe < xOpen)) return R_INV_DXY_SAME_DIR;
         if(!m_hasXLocBuy || xLo > m_xLocBuy) return R_INV_DXY_NO_INVERSION;
         if(m_p.dxyMode == VS_DXY_FULL && !(xShiftUp > xBear.e && xShiftUp <= t)) return R_INV_DXY_NO_INVERSION;
        }
      else
        {
         if(!((xHi - xOpen) > (xOpen - xLo) && xe > xOpen)) return R_INV_DXY_SAME_DIR;
         if(!m_hasXLocSell || xHi < m_xLocSell) return R_INV_DXY_NO_INVERSION;
         if(m_p.dxyMode == VS_DXY_FULL && !(xShiftDn > xBull.e && xShiftDn <= t)) return R_INV_DXY_NO_INVERSION;
        }
      return "";
     }

   //+---------------------------------------------------------------+
   //| process the closed bar t; returns true with a signal           |
   //+---------------------------------------------------------------+
   bool              OnBar(const CSeries &g, const CSeries &x, const int t, const int newIdIfNeeded, bool &startedNew, SSignal &sig)
     {
      ZeroMemory(sig);
      sig.valid = false;
      startedNew = false;
      datetime barTime = g.t[t];
      datetime candle = barTime - (datetime)(barTime % (m_tm.candleMin * 60));
      if(candle != m_candle)
        {
         Finish();
         Start(g, x, candle, newIdIfNeeded);
         startedNew = true;
        }
      if(!m_active) return false;
      //--- replay the candle up to bar t
      gBull.Reset(); gBear.Reset(); xBull.Reset(); xBear.Reset();
      xShiftUp = -1; xShiftDn = -1;
      xOpen = VSEA_NA; xHi = VSEA_NA; xLo = VSEA_NA;
      int cs = g.LowerBound(m_candle);
      bool wick = (m_p.breakConfirm == VS_BREAK_WICK);
      int pi; double pp;
      for(int k = cs; k <= t; k++)
        {
         gBull.Update(k, g.h[k], g.l[k]);
         gBear.Update(k, g.h[k], g.l[k]);
         if(!m_useDxy || !x.ValidBar(k)) continue;
         if(!VsValid(xOpen)) { xOpen = x.o[k]; xHi = x.h[k]; xLo = x.l[k]; }
         else { xHi = MathMax(xHi, x.h[k]); xLo = MathMin(xLo, x.l[k]); }
         xBull.Update(k, x.h[k], x.l[k]);
         xBear.Update(k, x.h[k], x.l[k]);
         if(FindShift(x, xBear, k, m_p.pivotStrength, wick, 0.0, pi, pp)) xShiftUp = k;
         if(FindShift(x, xBull, k, m_p.pivotStrength, wick, 0.0, pi, pp)) xShiftDn = k;
        }
      int minute = (int)((barTime - m_candle) / 60) + 1;
      for(int pass = 0; pass < 2; pass++)
        {
         int dir = (pass == 0) ? -1 : 1;
         if((dir < 0 && m_doneSell) || (dir > 0 && m_doneBuy)) continue;
         if(dir < 0) { if(!ExtValid(g, gBull)) continue; }
         else        { if(!ExtValid(g, gBear)) continue; }
         m_flagValidExt = true;
         state = "WAIT_SHIFT";
         if(minute < m_tm.shiftStart || minute > m_tm.shiftEnd) continue;
         double a = g.AtrAt(t, m_p.atrPeriodM1);
         double minBreak = (m_p.minBreakAtr > 0 && VsValid(a)) ? m_p.minBreakAtr * a : 0.0;
         int protIdx; double protPrice;
         bool shifted = (dir < 0) ? FindShift(g, gBull, t, m_p.pivotStrength, wick, minBreak, protIdx, protPrice)
                                  : FindShift(g, gBear, t, m_p.pivotStrength, wick, minBreak, protIdx, protPrice);
         if(!shifted) continue;
         datetime eTime = (dir < 0) ? g.t[gBull.e] : g.t[gBear.e];
         if((dir < 0 && m_evalSell == eTime) || (dir > 0 && m_evalBuy == eTime)) continue;
         if(dir < 0) m_evalSell = eTime; else m_evalBuy = eTime;
         string reason = (dir < 0) ? Gate(g, x, dir, gBull, t) : Gate(g, x, dir, gBear, t);
         double E = (dir < 0) ? gBull.E : gBear.E;
         double O = (dir < 0) ? gBull.O : gBear.O;
         m_lastDir = dir; m_lastSignal = barTime; m_lastE = E; m_lastO = O; m_lastProt = protPrice;
         m_log.Setup(setupId, m_tm.candleMin, barTime,
                     StringFormat("%s type-3 shift at minute %d: extreme=%.2f origin=%.2f protected=%.2f -> DXY gate %s",
                                  dir < 0 ? "bearish" : "bullish", minute, E, O, protPrice, reason == "" ? "PASS" : reason));
         if(reason != "") { m_gateReason = reason; continue; }
         if(dir < 0) m_doneSell = true; else m_doneBuy = true;
         sig.valid = true;
         sig.setupId = setupId;
         sig.tf = m_tm.candleMin;
         sig.dir = dir;
         sig.candleOpen = m_candle;
         sig.signalBarTime = barTime;
         sig.minute = minute;
         sig.extE = E;
         sig.extO = O;
         sig.extETime = eTime;
         sig.extOTime = (dir < 0) ? g.t[gBull.o] : g.t[gBear.o];
         sig.extPB = (dir < 0) ? gBull.PB : gBear.PB;
         sig.protPrice = protPrice;
         sig.protTime = g.t[protIdx];
         int e = (dir < 0) ? gBull.e : gBear.e;
         double B = (dir < 0) ? g.l[e + 1] : g.h[e + 1];
         for(int j = e + 1; j <= t; j++) B = (dir < 0) ? MathMin(B, g.l[j]) : MathMax(B, g.h[j]);
         sig.breakLeg = B;
         sig.atr = a;
         sig.gate = (m_useDxy ? "pass" : "off");
         state = "SIGNAL";
         return true;
        }
      return false;
     }

   double            LocationSell(void) const { return m_hasLocSell ? m_locSell : VSEA_NA; }
   double            LocationBuy(void) const  { return m_hasLocBuy ? m_locBuy : VSEA_NA; }
  };

#endif
