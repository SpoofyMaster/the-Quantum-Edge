//+------------------------------------------------------------------+
//| BfDetector.mqh                                                   |
//| BprFvgEA v2: BPR rejection -> breakout -> Fibonacci pullback      |
//+------------------------------------------------------------------+
//
// © LuxAlgo (original Pine v5 logic of 'ICT Concepts [LuxAlgo]') for the zones this detector consumes.
// Licence: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)
//          https://creativecommons.org/licenses/by-nc-sa/4.0/
// BprFvgEA contains a port / derivative work of the FVG and Balance Price Range logic of the Pine v5 script
// "ICT Concepts [LuxAlgo]" (see BfEngine.mqh). The EA, including this file, is distributed under the same licence:
// NON-COMMERCIAL use only, attribution to LuxAlgo required, share-alike. Not affiliated with or endorsed by LuxAlgo.
// The setup rules below are the project owner's (hypothesis H-14), not LuxAlgo's.
//
// What it is: the pure detector of research/indicators/BPR_BREAKOUT_FIB_SPEC.md ("spec s.N" below). It gets closed
// bars, the engine state after ProcessBar(u) and an environment (BfEnv), and it emits
//   - intents : PLACE_LIMIT (level k), CANCEL (level k)            (IntentCount / GetIntent / ClearIntents)
//   - events  : one record per state change (spec s.7)            (EventCount / GetEvent / ClearEvents)
// The executor reports back with NotifyFilled / NotifyClosed / NotifyCancelled / NotifyRetry (spec s.6).
// Python reference with the same records: qe/strategies/bpr_breakout.py (tests/test_bpr_breakout_ea_harness.py).
// STATUS of the trading rules: untested HYPOTHESIS (H-14). Paper / demo / tester use only.
//
// PURITY CONTRACT: no MT5 API (transliterated to C++ for the parity harness). Fixed-size arrays only; price arrays
// enter as 'const double &x[]' parameters; only MathMax / MathMin / MathAbs / MathRound / NormalizeDouble are used.
//+------------------------------------------------------------------+
#ifndef BF_DETECTOR_MQH
#define BF_DETECTOR_MQH

#include "BfDefines.mqh"
#include "BfEngine.mqh"

class CBfDetector
  {
private:
   BfParams          m_p;
   int               m_tradeFrom;       // first bar index that may trade; earlier bars are warm-up
   bool              m_warmEnded;
   bool              m_disabled;        // IFVG mode: setups need FVG, so the detector does nothing
   int               m_nextId;
   int               m_lastBar;         // last bar index given to OnBarClosed
   int               m_fvgUp;           // last bar with a bullish FVG (spec s.2 fvgBar[+1]); -1 = none
   int               m_fvgDn;           // last bar with a bearish FVG
   BfSetup           m_s[BF_MAX_SETUPS];   // tracked setups, in creation order
   int               m_n;
   BfIntent          m_in[BF_MAX_INTENTS];
   int               m_nIn;
   int               m_inLost;
   BfEvent           m_ev[BF_MAX_EVENTS];
   int               m_nEv;
   int               m_evLost;
   BfSetup           m_c;               // setup under construction (spec s.3)
   int               m_stat[BF_NSTAT];

   //--- spec s.2: RoundTick(x) = NormalizeDouble(MathRound(x / tick) * tick, digits)
   double            RoundTick(const double x)
     {
      if(m_p.tickSize <= 0.0)
         return(x);
      return(NormalizeDouble(MathRound(x / m_p.tickSize) * m_p.tickSize, m_p.digits));
     }

   void              Stat(const int code)
     {
      if(code >= 0 && code < BF_NSTAT)
         m_stat[code]++;
     }

   //--- spec s.7: one record per state change. P/SL/TP: PLACE_LIMIT only; O/X: CONFIRM and PLACE_LIMIT only.
   void              AddEvent(const int n, const int evType, const BfSetup &s, const int k, const int reason)
     {
      if(m_nEv >= BF_MAX_EVENTS)
        {
         m_evLost++;
         return;
        }
      BfClearEvent(m_ev[m_nEv]);
      m_ev[m_nEv].n           = n;
      m_ev[m_nEv].id          = s.id;
      m_ev[m_nEv].ev          = evType;
      m_ev[m_nEv].dir         = s.dir;
      m_ev[m_nEv].k           = k;
      m_ev[m_nEv].reason      = reason;
      if(evType == BF_EV_PLACE_LIMIT && k >= 1 && k <= BF_NLEV)
        {
         m_ev[m_nEv].P  = s.lvP[k - 1];
         m_ev[m_nEv].SL = s.SL;
         m_ev[m_nEv].TP = s.TP;
        }
      if(evType == BF_EV_CONFIRM || evType == BF_EV_PLACE_LIMIT)
        {
         m_ev[m_nEv].O = s.O;
         m_ev[m_nEv].X = s.X;
        }
      m_ev[m_nEv].phase       = s.phase;
      m_ev[m_nEv].created     = s.created;
      m_ev[m_nEv].B           = s.B;
      m_ev[m_nEv].T           = s.T;
      m_ev[m_nEv].touches     = s.touches;
      m_ev[m_nEv].lvl         = s.lvl;
      m_ev[m_nEv].ref         = s.ref;
      m_ev[m_nEv].brkBar      = s.brkBar;
      m_ev[m_nEv].confirmBar  = s.confirmBar;
      m_ev[m_nEv].decisionBar = s.decisionBar;
      m_ev[m_nEv].tgt         = s.tgt;
      m_ev[m_nEv].oBar        = s.oBar;
      m_ev[m_nEv].xBar        = s.xBar;
      m_ev[m_nEv].snO         = s.O;
      m_ev[m_nEv].snX         = s.X;
      m_ev[m_nEv].snSL        = s.SL;
      m_ev[m_nEv].snTP        = s.TP;
      for(int j = 0; j < BF_NLEV; j++)
        {
         m_ev[m_nEv].snLvSt[j]  = s.lvSt[j];
         m_ev[m_nEv].snLvP[j]   = s.lvP[j];
         m_ev[m_nEv].snLvRsn[j] = s.lvRsn[j];
        }
      m_nEv++;
     }

   void              AddIntent(const int type, const BfSetup &s, const int k, const int reason, const int bar)
     {
      if(m_nIn >= BF_MAX_INTENTS)
        {
         m_inLost++;
         return;
        }
      BfClearIntent(m_in[m_nIn]);
      m_in[m_nIn].type   = type;
      m_in[m_nIn].id     = s.id;
      m_in[m_nIn].dir    = s.dir;
      m_in[m_nIn].k      = k;
      m_in[m_nIn].reason = reason;
      m_in[m_nIn].bar    = bar;
      if(type == BF_EV_PLACE_LIMIT && k >= 1 && k <= BF_NLEV)
        {
         m_in[m_nIn].P  = s.lvP[k - 1];
         m_in[m_nIn].SL = s.SL;
         m_in[m_nIn].TP = s.TP;
        }
      m_nIn++;
     }

   int               FindIndex(const int id)
     {
      int i;
      if(id <= 0)
         return(-1);
      for(i = 0; i < m_n; i++)
         if(m_s[i].id == id)
            return(i);
      return(-1);
     }

   //--- drops CLOSED and DONE setups, keeps the creation order of the others
   void              Compact(void)
     {
      int r;
      int w = 0;
      for(r = 0; r < m_n; r++)
        {
         if(m_s[r].phase == BF_PH_DONE || m_s[r].phase == BF_PH_CLOSED)
            continue;
         if(w != r)
            BfCopySetup(m_s[w], m_s[r]);
         w++;
        }
      m_n = w;
     }

   //--- the DONE record keeps the phase the setup ended in (logs / CSV); the phase changes after the record
   void              SetDone(const int i, const int n, const int reason)
     {
      m_s[i].reason = reason;
      AddEvent(n, BF_EV_DONE, m_s[i], 0, reason);
      m_s[i].phase  = BF_PH_DONE;
      Stat(BF_STAT_DONE + reason);
     }

   void              SetClosed(const int i, const int n)
     {
      m_s[i].phase = BF_PH_CLOSED;
      AddEvent(n, BF_EV_CLOSED, m_s[i], 0, BF_R_NONE);
      Stat(BF_STAT_CLOSED);
     }

   //--- every PENDING level -> CANCELLED: CANCEL record + cancel intent (level order)
   void              CancelPending(const int i, const int n, const int reason)
     {
      int k;
      for(k = 0; k < BF_NLEV; k++)
        {
         if(m_s[i].lvSt[k] != BF_LV_PENDING)
            continue;
         m_s[i].lvSt[k]  = BF_LV_CANCELLED;
         m_s[i].lvRsn[k] = reason;
         AddEvent(n, BF_EV_CANCEL, m_s[i], k + 1, reason);
         AddIntent(BF_EV_CANCEL, m_s[i], k + 1, reason, n);
        }
     }

   bool              AnyLevel(const int i, const int st)
     {
      int k;
      for(k = 0; k < BF_NLEV; k++)
         if(m_s[i].lvSt[k] == st)
            return(true);
      return(false);
     }

   //--- nothing pending and nothing open: CLOSED if a level ever filled, otherwise DONE(reason)
   void              MaybeClosed(const int i, const int n, const int reason)
     {
      if(AnyLevel(i, BF_LV_PENDING) || AnyLevel(i, BF_LV_FILLED))
         return;
      if(m_s[i].everFilled)
         SetClosed(i, n);
      else
         SetDone(i, n, reason);
     }

   //--- all levels back to NONE (re-anchor, retry)
   void              ResetLevels(const int i)
     {
      int k;
      for(k = 0; k < BF_NLEV; k++)
        {
         m_s[i].lvSt[k]  = BF_LV_NONE;
         m_s[i].lvP[k]   = 0.0;
         m_s[i].lvRsn[k] = BF_R_NONE;
        }
      m_s[i].decisionBar = -1;
      m_s[i].SL          = 0.0;
      m_s[i].TP          = 0.0;
      m_s[i].tgt         = 0.0;
     }

   bool              DirAllowed(const int dir)
     {
      if(m_p.direction == BF_DIR_LONG_ONLY)
         return(dir > 0);
      if(m_p.direction == BF_DIR_SHORT_ONLY)
         return(dir < 0);
      return(true);
     }

   //--- spec s.2 helpers
   bool              Beyond(const int i, const double cu)
     {
      if(m_s[i].dir > 0)
         return(cu > m_s[i].lvl);
      return(cu < m_s[i].lvl);
     }

   void              Track(const int i, const int u, const double hu, const double lu)
     {
      if(m_s[i].dir > 0)
        {
         if(lu < m_s[i].O)
           {
            m_s[i].O    = lu;
            m_s[i].oBar = u;
            m_s[i].X    = hu;
            m_s[i].xBar = u;
           }
         else
            if(hu > m_s[i].X)
              {
               m_s[i].X    = hu;
               m_s[i].xBar = u;
              }
        }
      else
        {
         if(hu > m_s[i].O)
           {
            m_s[i].O    = hu;
            m_s[i].oBar = u;
            m_s[i].X    = lu;
            m_s[i].xBar = u;
           }
         else
            if(lu < m_s[i].X)
              {
               m_s[i].X    = lu;
               m_s[i].xBar = u;
              }
        }
     }

   bool              NewExt(const int i, const double hu, const double lu)
     {
      if(m_s[i].dir > 0)
         return(hu > m_s[i].X);
      return(lu < m_s[i].X);
     }

   bool              OriginBroken(const int i, const double hu, const double lu)
     {
      if(m_s[i].dir > 0)
         return(lu < m_s[i].O);
      return(hu > m_s[i].O);
     }

   void              Confirm(const int i, const int u)
     {
      m_s[i].phase      = BF_PH_LEG;
      m_s[i].confirmBar = u;
      AddEvent(u, BF_EV_CONFIRM, m_s[i], 0, BF_R_NONE);
      Stat(BF_STAT_CONFIRM);
     }

   //+---------------------------------------------------------------+
   //| spec s.4.1-s.4.4: one existing setup on closed bar u          |
   //+---------------------------------------------------------------+
   void              StepExisting(const int i, const int u, const double &h[], const double &l[], const double &c[],
                                  const BfEnv &env)
     {
      int  d = m_s[i].dir;
      int  ph = m_s[i].phase;
      bool tn;
      bool touched;
      m_s[i].ready = false;
      if(ph == BF_PH_WAIT || ph == BF_PH_ZONE || ph == BF_PH_BREAK)
        {
         //--- 4.1 steps 1-2
         if((d > 0 && l[u] < m_s[i].B) || (d < 0 && h[u] > m_s[i].T))
           {
            SetDone(i, u, BF_R_BROKEN);
            return;
           }
         if(u - m_s[i].created > m_p.setupExpiryBars)
           {
            SetDone(i, u, BF_R_EXPIRED);
            return;
           }
         tn = (d > 0) ? (l[u] <= m_s[i].T) : (h[u] >= m_s[i].B);
         //--- step 4: BREAK
         if(ph == BF_PH_BREAK)
           {
            if(Beyond(i, c[u]))
              {
               m_s[i].nClose++;
               Track(i, u, h[u], l[u]);
               if(m_s[i].nClose >= m_p.confirmCloses)
                  Confirm(i, u);
               m_s[i].inEp = tn;
               return;
              }
            AddEvent(u, BF_EV_BREAK_FAIL, m_s[i], 0, BF_R_NONE);
            Stat(BF_STAT_BRK_FAIL);
            m_s[i].phase  = BF_PH_ZONE;
            m_s[i].nClose = 0;
           }
         else
           {
            //--- step 5: ZONE + a candle that does NOT touch the zone closes beyond the level = breakout candle (a
            //    touching candle belongs to the touch: it becomes the reference candle in step 6). Stricter reading
            //    (rejectBeforeBreak): the previous candle must not have touched either (a rejection came first).
            if(ph == BF_PH_ZONE && !tn && (!m_p.rejectBeforeBreak || !m_s[i].inEp) && Beyond(i, c[u]))
              {
               m_s[i].phase  = BF_PH_BREAK;
               m_s[i].brkBar = u;
               m_s[i].nClose = 1;
               Track(i, u, h[u], l[u]);
               AddEvent(u, BF_EV_BREAKOUT, m_s[i], 0, BF_R_NONE);
               Stat(BF_STAT_BREAKOUT);
               if(m_s[i].nClose >= m_p.confirmCloses)
                  Confirm(i, u);
               m_s[i].inEp = tn;
               return;
              }
           }
         //--- step 6: touch logic
         if(tn)
           {
            if(!m_s[i].inEp)
              {
               m_s[i].touches++;
               if(m_s[i].touches > m_p.maxTouches)
                 {
                  SetDone(i, u, BF_R_TOUCH_LIMIT);
                  return;
                 }
               AddEvent(u, BF_EV_TOUCH, m_s[i], m_s[i].touches, BF_R_NONE);
               Stat(BF_STAT_TOUCH);
               if(m_s[i].touches == 1)
                  m_s[i].touchBar1 = u;
               else
                  m_s[i].touchBar2 = u;
               if(d > 0)
                 {
                  m_s[i].O = l[u];
                  m_s[i].X = h[u];
                 }
               else
                 {
                  m_s[i].O = h[u];
                  m_s[i].X = l[u];
                 }
               m_s[i].oBar = u;
               m_s[i].xBar = u;
              }
            else
               Track(i, u, h[u], l[u]);
            m_s[i].ref   = u;
            m_s[i].lvl   = (d > 0) ? h[u] : l[u];
            m_s[i].phase = BF_PH_ZONE;
            m_s[i].inEp  = true;
           }
         else
           {
            if(m_s[i].inEp)
              {
               AddEvent(u, BF_EV_REJECT, m_s[i], 0, BF_R_NONE);
               m_s[i].inEp = false;
              }
            if(m_s[i].phase == BF_PH_ZONE)
               Track(i, u, h[u], l[u]);
           }
         return;
        }
      if(ph == BF_PH_LEG)
        {
         //--- 4.2
         if(OriginBroken(i, h[u], l[u]))
           {
            SetDone(i, u, BF_R_LEG_BROKEN);
            return;
           }
         if(u - m_s[i].confirmBar > m_p.legExpiryBars)
           {
            SetDone(i, u, BF_R_EXPIRED);
            return;
           }
         if(NewExt(i, h[u], l[u]))
           {
            m_s[i].X    = (d > 0) ? h[u] : l[u];
            m_s[i].xBar = u;
            return;
           }
         if(m_p.fvgRule == BF_FVGRULE_NONE || ((d > 0) ? m_fvgUp : m_fvgDn) > m_s[i].ref)
            m_s[i].ready = true;
         else
            Stat(BF_STAT_NO_FVG);
         return;
        }
      if(ph == BF_PH_ORDERED)
        {
         //--- 4.3
         if(NewExt(i, h[u], l[u]))
           {
            CancelPending(i, u, BF_R_NEW_EXTREME);
            ResetLevels(i);
            m_s[i].X     = (d > 0) ? h[u] : l[u];
            m_s[i].xBar  = u;
            m_s[i].phase = BF_PH_LEG;
            Stat(BF_STAT_REANCHOR);
            return;
           }
         if(OriginBroken(i, h[u], l[u]))
           {
            CancelPending(i, u, BF_R_LEG_BROKEN);
            SetDone(i, u, BF_R_LEG_BROKEN);
            return;
           }
         if(u - m_s[i].confirmBar > m_p.legExpiryBars)
           {
            CancelPending(i, u, BF_R_EXPIRED);
            SetDone(i, u, BF_R_EXPIRED);
            return;
           }
         if(m_p.useSession && env.sessionCancel)
           {
            CancelPending(i, u, BF_R_SESSION_END);
            SetDone(i, u, BF_R_SESSION_END);
           }
         return;
        }
      if(ph == BF_PH_FILLED)
        {
         //--- 4.4
         if(AnyLevel(i, BF_LV_PENDING))
           {
            touched = (d > 0) ? (h[u] >= m_s[i].tgt) : (l[u] <= m_s[i].tgt);
            if(touched || NewExt(i, h[u], l[u]))
               CancelPending(i, u, BF_R_TARGET);
            else
               if(u - m_s[i].confirmBar > m_p.legExpiryBars)
                  CancelPending(i, u, BF_R_EXPIRED);
               else
                  if(m_p.useSession && env.sessionCancel)
                     CancelPending(i, u, BF_R_SESSION_END);
           }
         MaybeClosed(i, u, BF_R_TARGET);
        }
     }

   //+---------------------------------------------------------------+
   //| spec s.3: one new BPR                                         |
   //+---------------------------------------------------------------+
   void              NewSetup(const int u, const ZoneS &z)
     {
      int reason = BF_R_NONE;
      int dir    = z.pos;
      if(!DirAllowed(dir))
         return;
      BfClearSetup(m_c);
      m_c.id      = m_nextId;
      m_nextId++;
      m_c.dir     = dir;
      m_c.created = u;
      m_c.B       = z.box.bottom;
      m_c.T       = z.box.top;
      if(m_c.T <= m_c.B)
         reason = BF_R_BAD_GEOMETRY;
      else
         if(!z.active)
            reason = BF_R_BROKEN_AT_CREATION;
         else
            if(m_n >= BF_MAX_SETUPS)
               reason = BF_R_CAPACITY;
      if(reason != BF_R_NONE)
        {
         m_c.phase  = BF_PH_DONE;
         m_c.reason = reason;
         AddEvent(u, BF_EV_DONE, m_c, 0, reason);
         Stat(BF_STAT_DONE + reason);
         return;
        }
      m_c.phase = BF_PH_WAIT;
      BfCopySetup(m_s[m_n], m_c);
      m_n++;
      AddEvent(u, BF_EV_ARMED, m_c, 0, BF_R_NONE);
      Stat(BF_STAT_ARMED);
     }

   void              NewSetups(const int u, const StateS &eng, const BfEngineEvents &ev)
     {
      bool pairOk = (eng.nFu > 0 && eng.nFd > 0 && eng.fu[0].box.exists && eng.fd[0].box.exists);
      if(ev.newBprUp && pairOk && eng.nBu > 0 && eng.bu[0].box.exists && !eng.bu[0].posNa &&
         (eng.bu[0].pos == 1 || eng.bu[0].pos == -1))
         NewSetup(u, eng.bu[0]);
      if(ev.newBprDn && pairOk && eng.nBd > 0 && eng.bd[0].box.exists && !eng.bd[0].posNa &&
         (eng.bd[0].pos == 1 || eng.bd[0].pos == -1))
         NewSetup(u, eng.bd[0]);
     }

   //+---------------------------------------------------------------+
   //| spec s.5: one ready setup. true = at least one level placed.  |
   //+---------------------------------------------------------------+
   bool              TryDecide(const int i, const int u, const double &c[], const BfEnv &env)
     {
      int    k;
      int    d     = m_s[i].dir;
      int    nPl   = 0;
      int    why[BF_NLEV];
      double Pk[BF_NLEV];
      double sp    = env.sp;
      double tk    = m_p.tickSize;
      double L     = (double)d * (m_s[i].X - m_s[i].O);
      double SL;
      double tgt;
      double TP;
      double P;
      double f;
      double risk;
      double cost;
      if(L <= 0.0)
        {
         SetDone(i, u, BF_R_BAD_GEOMETRY);
         return(false);
        }
      SL   = m_s[i].X - (double)d * (m_p.stopFib / 100.0) * L - (double)d * (double)m_p.stopBufferTicks * tk;
      if(d < 0)
         SL += sp;
      tgt  = m_s[i].X - (double)d * (m_p.targetFib / 100.0) * L;
      TP   = tgt;
      if(d < 0)
         TP += sp;
      cost = sp + m_p.commPrice + 2.0 * m_p.slippageTicks * tk;
      for(k = 0; k < BF_NLEV; k++)
        {
         why[k] = -1;                                           // -1 = level off
         Pk[k]  = 0.0;
         f      = BfFibOf(m_p, k + 1);
         if(f <= 0.0)
            continue;
         P = m_s[i].X - (double)d * (f / 100.0) * L;
         if(d > 0)
            P += sp;
         risk  = MathAbs(P - SL);
         Pk[k] = P;
         if((double)d * (P - SL) <= 0.0 || (double)d * (TP - P) <= 0.0)
            why[k] = BF_R_BAD_LEVEL;
         else
            if((d > 0 && c[u] + sp <= P) || (d < 0 && c[u] >= P))
               why[k] = BF_R_MISSED;
            else
               if(m_p.minRR > 0.0 && MathAbs(TP - P) / risk < m_p.minRR)
                  why[k] = BF_R_RR;
               else
                  if(m_p.maxCostR > 0.0 && cost / risk > m_p.maxCostR)
                     why[k] = BF_R_COST;
                  else
                    {
                     why[k] = BF_R_NONE;
                     nPl++;
                    }
        }
      if(nPl > 0)
        {
         m_s[i].SL   = RoundTick(SL);
         m_s[i].TP   = RoundTick(TP);
         m_s[i].tgt  = RoundTick(tgt);
         m_s[i].decO = m_s[i].O;
         m_s[i].decX = m_s[i].X;
        }
      //--- records in level order
      for(k = 0; k < BF_NLEV; k++)
        {
         if(why[k] < 0)
            continue;
         if(why[k] != BF_R_NONE)
           {
            m_s[i].lvSt[k]  = BF_LV_SKIPPED;
            m_s[i].lvRsn[k] = why[k];
            AddEvent(u, BF_EV_SKIP, m_s[i], k + 1, why[k]);
            Stat(BF_STAT_SKIP + why[k]);
           }
         else
           {
            m_s[i].lvSt[k] = BF_LV_PENDING;
            m_s[i].lvP[k]  = RoundTick(Pk[k]);
            AddEvent(u, BF_EV_PLACE_LIMIT, m_s[i], k + 1, BF_R_NONE);
            AddIntent(BF_EV_PLACE_LIMIT, m_s[i], k + 1, BF_R_NONE, u);
            Stat(BF_STAT_PLACE);
           }
        }
      if(nPl == 0)
        {
         SetDone(i, u, BF_R_NO_LEVEL);
         return(false);
        }
      m_s[i].phase       = BF_PH_ORDERED;
      m_s[i].decisionBar = u;
      return(true);
     }

   //+---------------------------------------------------------------+
   //| spec s.5: decisions, creation order, one setup per bar        |
   //+---------------------------------------------------------------+
   void              Decide(const int u, const double &c[], const BfEnv &env)
     {
      int i;
      int nReady  = 0;
      int blocked = -1;
      for(i = 0; i < m_n; i++)
         if(m_s[i].phase == BF_PH_LEG && m_s[i].ready)
            nReady++;
      if(nReady == 0)
         return;
      if(!env.slotFree)
         blocked = BF_STAT_BLK_SLOT;
      else
         if(m_p.useSession && !env.sessionEntryOk)
            blocked = BF_STAT_BLK_SESS;
         else
            if(!env.riskOk)
               blocked = BF_STAT_BLK_RISK;
            else
               if(!env.spreadOk)
                  blocked = BF_STAT_BLK_SPRD;
      if(blocked >= 0)
        {
         for(i = 0; i < nReady; i++)
            Stat(blocked);
         return;
        }
      for(i = 0; i < m_n; i++)
        {
         if(m_s[i].phase != BF_PH_LEG || !m_s[i].ready)
            continue;
         if(TryDecide(i, u, c, env))
            return;
        }
     }

public:
                     CBfDetector(void)
     {
      int k;
      BfDefaultParams(m_p);
      BfClearSetup(m_c);
      m_tradeFrom = 0;
      m_warmEnded = false;
      m_disabled  = false;
      m_nextId    = 1;
      m_lastBar   = -1;
      m_fvgUp     = -1;
      m_fvgDn     = -1;
      m_n         = 0;
      m_nIn       = 0;
      m_inLost    = 0;
      m_nEv       = 0;
      m_evLost    = 0;
      for(k = 0; k < BF_NSTAT; k++)
         m_stat[k] = 0;
     }

   //--- tradeFrom = index of the first bar whose setups may trade (the number of warm-up bars)
   void              Init(const BfParams &p, const int tradeFrom)
     {
      int k;
      BfCopyParams(m_p, p);
      BfClearSetup(m_c);
      m_tradeFrom = tradeFrom;
      m_warmEnded = false;
      m_disabled  = (p.fvgMode != BF_FVGTYPE_FVG);           // setups need FVG
      m_nextId    = 1;
      m_lastBar   = -1;
      m_fvgUp     = -1;
      m_fvgDn     = -1;
      m_n         = 0;
      m_nIn       = 0;
      m_inLost    = 0;
      m_nEv       = 0;
      m_evLost    = 0;
      for(k = 0; k < BF_NSTAT; k++)
         m_stat[k] = 0;
     }

   //--- spec s.7 warm-up: setups created during warm-up become DONE(WARMUP); n = the last warm-up bar. Idempotent.
   void              EndWarmup(void)
     {
      int i;
      if(m_warmEnded)
         return;
      m_warmEnded = true;
      for(i = 0; i < m_n; i++)
        {
         if(m_s[i].created >= m_tradeFrom)
            continue;
         if(m_s[i].phase == BF_PH_ORDERED || m_s[i].phase == BF_PH_FILLED)
            CancelPending(i, m_lastBar, BF_R_WARMUP);            // cannot happen: no decisions during warm-up
         SetDone(i, m_lastBar, BF_R_WARMUP);
        }
      Compact();
     }

   //+---------------------------------------------------------------+
   //| spec s.4: one closed bar u. The engine has already processed  |
   //| bar u; eng / ev are its state and events.                     |
   //+---------------------------------------------------------------+
   void              OnBarClosed(const int u, const double &o[], const double &h[], const double &l[],
                                 const double &c[], const StateS &eng, const BfEngineEvents &ev, const BfEnv &env)
     {
      int i;
      if(m_disabled)
        {
         m_lastBar = u;
         return;
        }
      if(!m_warmEnded && u >= m_tradeFrom)
         EndWarmup();
      m_lastBar = u;
      //--- step 2: FVG bars (spec s.2)
      if(m_p.fvgRule == BF_FVGRULE_LUXALGO)
        {
         if(ev.newFvgUp || ev.updFvgUp)
            m_fvgUp = u;
         if(ev.newFvgDn || ev.updFvgDn)
            m_fvgDn = u;
        }
      else
         if(m_p.fvgRule == BF_FVGRULE_ANY_GAP && u >= 2)
           {
            if(l[u] > h[u - 2])
               m_fvgUp = u;
            if(h[u] < l[u - 2])
               m_fvgDn = u;
           }
      //--- step 3: existing setups in creation order
      for(i = 0; i < m_n; i++)
         StepExisting(i, u, h, l, c, env);
      Compact();
      //--- step 4: new setups
      NewSetups(u, eng, ev);
      //--- step 5: decisions (never during warm-up)
      if(u >= m_tradeFrom)
         Decide(u, c, env);
      Compact();
     }

   //--- executor feedback (spec s.6)
   void              NotifyFilled(const int id, const int k)
     {
      int i = FindIndex(id);
      if(i < 0 || k < 1 || k > BF_NLEV)
         return;
      if(m_s[i].lvSt[k - 1] != BF_LV_PENDING)
         return;                                                // cancelled by the detector: executor-managed only
      if(m_s[i].phase != BF_PH_ORDERED && m_s[i].phase != BF_PH_FILLED)
         return;
      m_s[i].lvSt[k - 1] = BF_LV_FILLED;
      m_s[i].everFilled  = true;
      m_s[i].phase       = BF_PH_FILLED;
     }

   void              NotifyClosed(const int id, const int k)
     {
      int i = FindIndex(id);
      if(i < 0 || k < 1 || k > BF_NLEV)
         return;
      if(m_s[i].lvSt[k - 1] != BF_LV_FILLED)
         return;
      m_s[i].lvSt[k - 1] = BF_LV_CLOSED;
      if(m_s[i].phase == BF_PH_FILLED)
        {
         MaybeClosed(i, m_lastBar, BF_R_ORDER_FAILED);
         Compact();
        }
     }

   void              NotifyCancelled(const int id, const int k, const int reason)
     {
      int i = FindIndex(id);
      if(i < 0 || k < 1 || k > BF_NLEV)
         return;
      if(m_s[i].lvSt[k - 1] != BF_LV_PENDING)
         return;
      if(m_s[i].phase != BF_PH_ORDERED && m_s[i].phase != BF_PH_FILLED)
         return;
      m_s[i].lvSt[k - 1]  = BF_LV_DROPPED;
      m_s[i].lvRsn[k - 1] = reason;
      AddEvent(m_lastBar, BF_EV_DROP, m_s[i], k, reason);
      Stat(BF_STAT_DROP + reason);
      MaybeClosed(i, m_lastBar, reason);
      Compact();
     }

   //--- EA executor only: no order of the decision was sent (transient reason). ORDERED -> LEG, levels cleared.
   void              NotifyRetry(const int id)
     {
      int i = FindIndex(id);
      if(i < 0)
         return;
      if(m_s[i].phase != BF_PH_ORDERED || m_s[i].everFilled)
         return;
      ResetLevels(i);
      m_s[i].phase = BF_PH_LEG;
      Stat(BF_STAT_RETRY);
     }

   //--- harness environment: slot_free = no setup ORDERED or FILLED
   bool              HasOrderOrPosition(void)
     {
      int i;
      for(i = 0; i < m_n; i++)
         if(m_s[i].phase == BF_PH_ORDERED || m_s[i].phase == BF_PH_FILLED)
            return(true);
      return(false);
     }

   //--- intents
   int               IntentCount(void)
     {
      return(m_nIn);
     }

   bool              GetIntent(const int i, BfIntent &out)
     {
      if(i < 0 || i >= m_nIn)
         return(false);
      BfCopyIntent(out, m_in[i]);
      return(true);
     }

   void              ClearIntents(void)
     {
      m_nIn = 0;
     }

   //--- event records
   int               EventCount(void)
     {
      return(m_nEv);
     }

   bool              GetEvent(const int i, BfEvent &out)
     {
      if(i < 0 || i >= m_nEv)
         return(false);
      BfCopyEvent(out, m_ev[i]);
      return(true);
     }

   void              ClearEvents(void)
     {
      m_nEv = 0;
     }

   //--- inspection (panel, logs, drawing)
   int               TrackedCount(void)
     {
      return(m_n);
     }

   bool              GetTracked(const int i, BfSetup &out)
     {
      if(i < 0 || i >= m_n)
         return(false);
      BfCopySetup(out, m_s[i]);
      return(true);
     }

   bool              GetSetup(const int id, BfSetup &out)
     {
      int i = FindIndex(id);
      if(i < 0)
         return(false);
      BfCopySetup(out, m_s[i]);
      return(true);
     }

   int               PhaseCount(const int ph)
     {
      int i;
      int k = 0;
      for(i = 0; i < m_n; i++)
         if(m_s[i].phase == ph)
            k++;
      return(k);
     }

   int               StatValue(const int code)
     {
      if(code < 0 || code >= BF_NSTAT)
         return(0);
      return(m_stat[code]);
     }

   bool              Disabled(void)
     {
      return(m_disabled);
     }

   int               TradeFrom(void)
     {
      return(m_tradeFrom);
     }

   int               LastBar(void)
     {
      return(m_lastBar);
     }

   int               LostEvents(void)
     {
      return(m_evLost);
     }

   int               LostIntents(void)
     {
      return(m_inLost);
     }
  };

#endif
//+------------------------------------------------------------------+
