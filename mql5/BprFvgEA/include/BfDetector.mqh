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
      if(evType == BF_EV_TOUCH_ENTRY)
        {
         m_ev[m_nEv].P  = s.tP;
         m_ev[m_nEv].SL = s.tSL;
         m_ev[m_nEv].TP = s.tTP;
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
      m_ev[m_nEv].lvl         = (s.rev || s.kind == BF_SETUP_REVERSAL) ? s.lvlR : s.lvl;
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
      m_ev[m_nEv].zdir        = s.zdir;
      m_ev[m_nEv].rev         = s.rev;
      m_ev[m_nEv].lvlBar      = (s.rev || s.kind == BF_SETUP_REVERSAL) ? s.lvlRBar : s.ref;
      m_ev[m_nEv].kind        = s.kind;
      m_ev[m_nEv].rejC        = s.nRejC;
      m_ev[m_nEv].pendTime    = s.pendTimeUp;
      m_ev[m_nEv].dupOf       = s.dupOf;
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
      m_in[m_nIn].pendTime = s.pendTimeUp;                       // v10
      if(type == BF_EV_PLACE_LIMIT && k >= 1 && k <= BF_NLEV)
        {
         m_in[m_nIn].P  = s.lvP[k - 1];
         m_in[m_nIn].SL = s.SL;
         m_in[m_nIn].TP = s.TP;
        }
      if(type == BF_EV_TOUCH_ENTRY)
        {
         m_in[m_nIn].P  = s.tP;
         m_in[m_nIn].SL = s.tSL;
         m_in[m_nIn].TP = s.tTP;
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

   //--- v6 setup types; v7: per setup. BOTH follows each BPR as two setups, a continuation and a reversal one.
   bool              HasCont(const int i)
     {
      return(m_s[i].kind == BF_SETUP_CONTINUATION);
     }

   bool              HasRev(const int i)
     {
      return(m_s[i].kind == BF_SETUP_REVERSAL);
     }

   //--- v7: the setup that sends the touch entry: the continuation one (CONTINUATION / BOTH), or the reversal one
   //    (REVERSAL, which has no continuation setup)
   bool              TouchOwner(const int i)
     {
      return(m_s[i].kind == BF_SETUP_CONTINUATION || m_p.setupType == BF_SETUP_REVERSAL);
     }

   //--- v7 reversal level at a touch (T1 / T2): DEEPEST = the deepest wick of the touch candles (the lowest low for a
   //    bullish BPR), T1 = the T1 candle's, LAST = the latest touch candle's (v6). v7.01: with DEEPEST a later touch's
   //    wick counts once its visit is rejected (ApplyLevelCand); a visit that turns into the breakout keeps the level.
   void              SetRevLevel(const int i, const int u, const double hu, const double lu)
     {
      double w = (m_s[i].zdir > 0) ? lu : hu;
      if(m_s[i].touches <= 1 || m_p.revLevel == BF_REVLVL_LAST)
        {
         m_s[i].lvlR    = w;
         m_s[i].lvlRBar = u;
         return;
        }
      if(m_p.revLevel == BF_REVLVL_T1)
         return;
      m_s[i].cLvlOn  = true;
      m_s[i].cLvl    = w;
      m_s[i].cLvlBar = u;
     }

   //--- v7.01 DEEPEST: the rejected visit's touch wick becomes the level if it is strictly deeper
   void              ApplyLevelCand(const int i)
     {
      if(!m_s[i].cLvlOn)
         return;
      m_s[i].cLvlOn = false;
      if((m_s[i].zdir > 0) ? (m_s[i].cLvl < m_s[i].lvlR) : (m_s[i].cLvl > m_s[i].lvlR))
        {
         m_s[i].lvlR    = m_s[i].cLvl;
         m_s[i].lvlRBar = m_s[i].cLvlBar;
        }
     }

   //--- spec s.2 helpers. Before the confirmation they use the BPR's direction (zdir); v1-v5 had dir == zdir there.
   bool              Beyond(const int i, const double cu)
     {
      if(m_s[i].zdir > 0)
         return(cu > m_s[i].lvl);
      return(cu < m_s[i].lvl);
     }

   //--- v6 reversal breakout: a close beyond the opposite extreme of the candle that made the latest touch (below
   //    its low for a bullish BPR, above its high for a bearish one)
   bool              BeyondRev(const int i, const double cu)
     {
      if(m_s[i].zdir > 0)
         return(cu < m_s[i].lvlR);
      return(cu > m_s[i].lvlR);
     }

   //--- v7 candidate origin of a visit of the zone (T1, T2, a pullback visit after the last touch, or a visit opened by
   //    a reversal breakout candle): v7.01 the bounce after the visit's lowest low cL (bullish BPR) - the highest high
   //    of the bars after it and the lowest low after that high. It becomes the reversal leg (rO / rX) when the visit is
   //    rejected; a visit that turns into the breakout keeps the earlier leg. A new visit low restarts the bounce.
   void              TrackCand(const int i, const int u, const double hu, const double lu)
     {
      if(m_s[i].zdir > 0)
        {
         if(lu < m_s[i].cL)
           {
            m_s[i].cL    = lu;
            m_s[i].cO    = lu;
            m_s[i].cOBar = u;
            m_s[i].cX    = lu;
            m_s[i].cXBar = u;
           }
         else
            if(hu > m_s[i].cO)
           {
            m_s[i].cO    = hu;
            m_s[i].cOBar = u;
            m_s[i].cX    = lu;
            m_s[i].cXBar = u;
           }
         else
            if(lu < m_s[i].cX)
              {
               m_s[i].cX    = lu;
               m_s[i].cXBar = u;
              }
        }
      else
        {
         if(hu > m_s[i].cL)
           {
            m_s[i].cL    = hu;
            m_s[i].cO    = hu;
            m_s[i].cOBar = u;
            m_s[i].cX    = hu;
            m_s[i].cXBar = u;
           }
         else
            if(lu < m_s[i].cO)
           {
            m_s[i].cO    = lu;
            m_s[i].cOBar = u;
            m_s[i].cX    = hu;
            m_s[i].cXBar = u;
           }
         else
            if(hu > m_s[i].cX)
              {
               m_s[i].cX    = hu;
               m_s[i].cXBar = u;
              }
        }
     }

   //--- v7: a visit of the zone begins on bar u (its first candle): a new candidate. v7.01: the bounce is measured
   //    from the visit's low, so cO starts AT that low (the entering candle's high belongs to the descent)
   void              StartCand(const int i, const int u, const double hu, const double lu)
     {
      m_s[i].cAct      = true;
      m_s[i].lastVisit = u;
      m_s[i].cL    = (m_s[i].zdir > 0) ? lu : hu;
      m_s[i].cO    = m_s[i].cL;
      m_s[i].cX    = m_s[i].cL;
      m_s[i].cOBar = u;
      m_s[i].cXBar = u;
     }

   //--- v6 reversal leg: origin = highest high (bullish BPR) since T1 began, extreme = lowest low after it. v7: a later
   //    visit of the zone that is rejected moves the origin to its own candidate (the top of the last bounce).
   void              TrackRev(const int i, const int u, const double hu, const double lu)
     {
      if(m_s[i].cAct)
         TrackCand(i, u, hu, lu);
      if(m_s[i].zdir > 0)
        {
         if(hu > m_s[i].rO)
           {
            m_s[i].rO    = hu;
            m_s[i].rOBar = u;
            m_s[i].rX    = lu;
            m_s[i].rXBar = u;
           }
         else
            if(lu < m_s[i].rX)
              {
               m_s[i].rX    = lu;
               m_s[i].rXBar = u;
              }
        }
      else
        {
         if(lu < m_s[i].rO)
           {
            m_s[i].rO    = lu;
            m_s[i].rOBar = u;
            m_s[i].rX    = hu;
            m_s[i].rXBar = u;
           }
         else
            if(hu > m_s[i].rX)
              {
               m_s[i].rX    = hu;
               m_s[i].rXBar = u;
              }
        }
     }

   void              Track(const int i, const int u, const double hu, const double lu)
     {
      if(m_s[i].zdir > 0)
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

   //--- v10: a setup with orders or positions (ORDERED / FILLED) that trades the same leg as setup i: the same trade
   //    direction and the same leg origin O (so the same stop; the leg origin no longer moves after the confirmation).
   //    -1 = none
   int               SameLegTraded(const int i)
     {
      int    j;
      double tol = (m_p.tickSize > 0.0) ? 0.5 * m_p.tickSize : 1e-9;
      for(j = 0; j < m_n; j++)
        {
         if(j == i || (m_s[j].phase != BF_PH_ORDERED && m_s[j].phase != BF_PH_FILLED))
            continue;
         if(m_s[j].dir == m_s[i].dir && MathAbs(m_s[j].O - m_s[i].O) < tol)
            return(j);
        }
      return(-1);
     }

   //--- v10: the EA's execution context of setup id still holds orders / positions (env.busyIds)
   bool              EnvBusy(const BfEnv &env, const int id)
     {
      int k;
      for(k = 0; k < env.nBusy && k < BF_MAX_BUSY; k++)
         if(env.busyIds[k] == id)
            return(true);
      return(false);
     }

   //--- v10: the pending-order time limit is reached: pendingMaxSec after the setup's first placement (env.now)
   bool              PendTimeUp(const int i, const BfEnv &env)
     {
      return(m_p.pendingMaxSec > 0 && m_s[i].ordTime > 0 && env.now > 0 &&
             env.now - m_s[i].ordTime >= (long)m_p.pendingMaxSec);
     }

   //--- v5 legBreakOnClose: only the close counts (a wick beyond the origin does not break the leg)
   bool              OriginBroken(const int i, const double hu, const double lu, const double cu)
     {
      if(m_p.legBreakOnClose)
        {
         if(m_s[i].dir > 0)
            return(cu < m_s[i].O);
         return(cu > m_s[i].O);
        }
      if(m_s[i].dir > 0)
         return(lu < m_s[i].O);
      return(hu > m_s[i].O);
     }

   //--- spec s.4.2 FVG condition: an FVG of the setup's direction after the reference candle (always met with NONE)
   bool              FvgOk(const int i)
     {
      int after = m_s[i].ref;
      if(m_p.fvgRule == BF_FVGRULE_NONE)
         return(true);
      //--- v8: a reversal without the FVG condition (revNeedFvg false): its limits can go in at the confirmation
      if(m_s[i].rev && !m_p.revNeedFvg)
         return(true);
      //--- v7.01 reversal: the FVG must belong to the reversal leg, after its 100 % bar too (not a gap of the move up)
      if(m_s[i].rev && m_s[i].oBar > after)
         after = m_s[i].oBar;
      return(((m_s[i].dir > 0) ? m_fvgUp : m_fvgDn) > after);
     }

   //--- a decision bar: ready with the FVG condition, otherwise counted as a bar without an FVG
   void              MarkReady(const int i)
     {
      if(FvgOk(i))
         m_s[i].ready = true;
      else
         Stat(BF_STAT_NO_FVG);
     }

   void              Confirm(const int i, const int u)
     {
      m_s[i].phase      = BF_PH_LEG;
      m_s[i].confirmBar = u;
      AddEvent(u, BF_EV_CONFIRM, m_s[i], 0, BF_R_NONE);
      Stat(BF_STAT_CONFIRM);
      //--- v5 anticipate: the orders may be decided on the confirmation bar itself, without a pullback candle
      if(m_p.anticipate)
         MarkReady(i);
     }

   //--- v6 reversal confirmation: the leg becomes the reversal leg (trade direction -zdir, set at the breakout)
   void              ConfirmRev(const int i, const int u)
     {
      m_s[i].O    = m_s[i].rO;
      m_s[i].oBar = m_s[i].rOBar;
      m_s[i].X    = m_s[i].rX;
      m_s[i].xBar = m_s[i].rXBar;
      Confirm(i, u);
     }

   //--- the expiry before the confirmation. v4-v7 (t1WaitBars < 0): setupExpiryBars from the BPR's creation (v7.01:
   //    a reversal setup from its last rejection when that is later). v8 (t1WaitBars >= 0): only while price is in
   //    play. Before T1 only t1WaitBars counts (0 = no limit). After a rejection, while price is away from the zone
   //    (ZONE, not in a visit), there is no limit either: the setup waits for price to come back (a late T2, a late
   //    break of the T1 wick). In a visit, setupExpiryBars counts from the visit's first bar; in a breakout, from the
   //    breakout candle (a rejection always comes before the next visit or breakout, so it is never later).
   bool              Expired(const int i, const int u)
     {
      int from = m_s[i].created;
      if(m_p.t1WaitBars < 0)
        {
         if(HasRev(i) && m_s[i].lastRej > from)
            from = m_s[i].lastRej;
         return(u - from > m_p.setupExpiryBars);
        }
      if(m_s[i].touches == 0)
         return(m_p.t1WaitBars > 0 && u - m_s[i].created > m_p.t1WaitBars);
      if(m_s[i].phase == BF_PH_ZONE && !m_s[i].inEp)
         return(false);
      from = m_s[i].touchBar1;
      if(m_s[i].lastVisit > from)
         from = m_s[i].lastVisit;
      if(m_s[i].phase == BF_PH_BREAK && m_s[i].brkBar > from)
         from = m_s[i].brkBar;
      return(u - from > m_p.setupExpiryBars);
     }

   //--- v8: a setup waiting for price (never touched, or away from its zone after a rejection) and the bar of its last
   //    zone event; -1 = busy (in a visit, a breakout, confirmed)
   int               IdleSince(const int i)
     {
      int a = m_s[i].created;
      if(m_s[i].phase == BF_PH_WAIT)
         return(a);
      if(m_s[i].phase != BF_PH_ZONE || m_s[i].inEp)
         return(-1);
      if(m_s[i].lastVisit > a)
         a = m_s[i].lastVisit;
      if(m_s[i].lastRej > a)
         a = m_s[i].lastRej;
      return(a);
     }

   //+---------------------------------------------------------------+
   //| spec s.4.1-s.4.4: one existing setup on closed bar u          |
   //+---------------------------------------------------------------+
   void              StepExisting(const int i, const int u, const double &o[], const double &h[], const double &l[],
                                  const double &c[], const BfEnv &env)
     {
      int  d  = m_s[i].dir;
      int  zd = m_s[i].zdir;
      int  ph = m_s[i].phase;
      bool tn;
      bool touched;
      bool brokeNow;
      bool rj;
      bool early;
      m_s[i].ready      = false;
      m_s[i].touchReady = false;
      if(ph == BF_PH_WAIT || ph == BF_PH_ZONE || ph == BF_PH_BREAK)
        {
         //--- 4.1 steps 1-2. v6: a broken BPR ends a continuation setup only; a reversal setup goes on (it trades the
         //    break), unless its direction is not allowed (a REVERSAL setup kept for its touch entry only).
         brokeNow = ((zd > 0 && l[u] < m_s[i].B) || (zd < 0 && h[u] > m_s[i].T));
         if(brokeNow && (!HasRev(i) || !DirAllowed(-zd)))
           {
            SetDone(i, u, BF_R_BROKEN);
            return;
           }
         if(Expired(i, u))
           {
            SetDone(i, u, BF_R_EXPIRED);
            return;
           }
         tn = (zd > 0) ? (l[u] <= m_s[i].T) : (h[u] >= m_s[i].B);
         //--- v9 reversal: the rejection candles ("a minimum 2 green candles, successive or not, before price comes
         //    back for the breakout"). After the T1 candle and outside a breakout in progress (BREAK), a candle in the
         //    BPR's direction (bullish for a bullish BPR) that does not close beyond the reversal level counts. A close
         //    beyond the level that is not the breakout restarts the count (below, after step 5b).
         if(HasRev(i) && ph != BF_PH_BREAK && m_s[i].touches > 0 && u > m_s[i].touchBar1 && !BeyondRev(i, c[u]) &&
            ((zd > 0) ? (c[u] > o[u]) : (c[u] < o[u])))
            m_s[i].nRejC++;
         //--- step 4: BREAK (continuation, or v6 reversal)
         if(ph == BF_PH_BREAK)
           {
            if(m_s[i].rev ? BeyondRev(i, c[u]) : Beyond(i, c[u]))
              {
               m_s[i].nClose++;
               Track(i, u, h[u], l[u]);
               TrackRev(i, u, h[u], l[u]);
               if(m_s[i].nClose >= m_p.confirmCloses)
                 {
                  if(m_s[i].rev)
                     ConfirmRev(i, u);
                  else
                     Confirm(i, u);
                 }
               m_s[i].inEp = tn;
               return;
              }
            AddEvent(u, BF_EV_BREAK_FAIL, m_s[i], 0, BF_R_NONE);
            Stat(BF_STAT_BRK_FAIL);
            m_s[i].phase  = BF_PH_ZONE;
            m_s[i].nClose = 0;
            if(m_s[i].rev)
              {
               m_s[i].rev = false;
               m_s[i].dir = zd;
              }
           }
         //--- steps 5 / 5b: ZONE, not on the bar of a BREAK_FAIL (that candle closed back on the other side of the level)
           {
            //--- step 5: ZONE + a candle that does NOT touch the zone closes beyond the level = breakout candle (a
            //    touching candle belongs to the touch: it becomes the reference candle in step 6). Stricter reading
            //    (rejectBeforeBreak): the previous candle must not have touched either (a rejection came first).
            if(m_s[i].phase == BF_PH_ZONE && ph != BF_PH_BREAK && HasCont(i) && DirAllowed(zd) && !tn &&
               (!m_p.rejectBeforeBreak || !m_s[i].inEp) && Beyond(i, c[u]))
              {
               m_s[i].phase  = BF_PH_BREAK;
               m_s[i].brkBar = u;
               m_s[i].nClose = 1;
               Track(i, u, h[u], l[u]);
               TrackRev(i, u, h[u], l[u]);
               AddEvent(u, BF_EV_BREAKOUT, m_s[i], 0, BF_R_NONE);
               Stat(BF_STAT_BREAKOUT);
               if(m_s[i].nClose >= m_p.confirmCloses)
                  Confirm(i, u);
               m_s[i].inEp = tn;
               return;
              }
            //--- v6 step 5b: reversal breakout candle: ZONE + a close beyond the reversal level lvlR (v7: the deepest
            //    wick of the T1 / T2 candles by default). It may touch the zone (it goes through it). v7: by default a
            //    rejection must have come after T1 ("T1, rejection, pullback, breakout"); v9: with at least
            //    revRejCandles rejection candles before this one. The trade direction becomes -zdir from here.
            if(m_s[i].phase == BF_PH_ZONE && ph != BF_PH_BREAK && HasRev(i) && DirAllowed(-zd) &&
               (!m_p.revNeedReject || m_s[i].rej) && m_s[i].nRejC >= m_p.revRejCandles && BeyondRev(i, c[u]))
              {
               m_s[i].phase  = BF_PH_BREAK;
               m_s[i].rev    = true;
               m_s[i].dir    = -zd;
               m_s[i].brkBar = u;
               m_s[i].nClose = 1;
               Track(i, u, h[u], l[u]);
               TrackRev(i, u, h[u], l[u]);
               //--- v7.01: a breakout candle that enters the zone opens a visit (not a touch): if the breakout fails
               //    and the visit is rejected, its bounce becomes the 100 % like any rejected visit
               if(!m_s[i].inEp)
                  StartCand(i, u, h[u], l[u]);
               AddEvent(u, BF_EV_BREAKOUT, m_s[i], 0, BF_R_NONE);
               Stat(BF_STAT_BREAKOUT);
               if(m_s[i].nClose >= m_p.confirmCloses)
                  ConfirmRev(i, u);
               m_s[i].inEp = tn;
               return;
              }
           }
         //--- v9: a close beyond the reversal level that is not the reversal breakout (price came back before enough
         //    rejection candles): the count restarts, and the candle is no touch. If it opens a new visit, step 6
         //    treats it like a pullback visit: it does not take the T2 slot and its wick does not become the level.
         early = (m_p.revRejCandles > 0 && HasRev(i) && ph == BF_PH_ZONE && m_s[i].touches > 0 &&
                  BeyondRev(i, c[u]));
         if(early)
            m_s[i].nRejC = 0;
         //--- v8 reversal (t1WaitBars >= 0): inside a visit, a candle that closes beyond the zone's far edge (above
         //    it for a bullish BPR) is the rejection (a bullish reaction off the BPR), even if its wick is in the zone
         if(m_p.t1WaitBars >= 0 && tn && m_s[i].inEp && HasRev(i) &&
            ((zd > 0) ? (c[u] > m_s[i].T) : (c[u] < m_s[i].B)))
            tn = false;
         //--- step 6: touch logic
         if(tn)
           {
            if(!m_s[i].inEp && HasRev(i) && (m_s[i].touches >= m_p.maxTouches || early))
              {
               //--- v7 reversal setup: a visit of the zone after the last touch is the pullback, not a touch. It does
               //    not end the setup and does not move the level; if it is rejected, its bounce is the new origin.
               //    v9: so is a visit opened by a close beyond the level that is not the breakout.
               TrackRev(i, u, h[u], l[u]);
               StartCand(i, u, h[u], l[u]);
              }
            else
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
                  m_s[i].O    = (zd > 0) ? l[u] : h[u];
                  m_s[i].X    = (zd > 0) ? h[u] : l[u];
                  m_s[i].oBar = u;
                  m_s[i].xBar = u;
                  SetRevLevel(i, u, h[u], l[u]);
                  //--- v7 reversal origin: T1 starts it (v6: from the T1 candle); every visit, T1 included (v7.01), is a
                  //    candidate until it is rejected
                  if(m_s[i].touches == 1)
                    {
                     m_s[i].rO    = (zd > 0) ? h[u] : l[u];
                     m_s[i].rX    = (zd > 0) ? l[u] : h[u];
                     m_s[i].rOBar = u;
                     m_s[i].rXBar = u;
                    }
                  else
                     TrackRev(i, u, h[u], l[u]);
                  StartCand(i, u, h[u], l[u]);
                  //--- v6 touch entry: on the close of the T1 candle, if that candle did not break the BPR
                  if(m_p.touchEntry && m_s[i].touches == 1 && !brokeNow && DirAllowed(zd) && TouchOwner(i))
                     m_s[i].touchReady = true;
                 }
               else
                 {
                  Track(i, u, h[u], l[u]);
                  TrackRev(i, u, h[u], l[u]);
                 }
            m_s[i].ref   = u;
            m_s[i].lvl   = (zd > 0) ? h[u] : l[u];
            m_s[i].phase = BF_PH_ZONE;
            m_s[i].inEp  = true;
           }
         else
           {
            rj = m_s[i].inEp;
            if(rj)
              {
               AddEvent(u, BF_EV_REJECT, m_s[i], 0, BF_R_NONE);
               m_s[i].inEp = false;
              }
            if(m_s[i].phase == BF_PH_ZONE)
              {
               Track(i, u, h[u], l[u]);
               TrackRev(i, u, h[u], l[u]);
              }
            //--- v7: the rejection; a rejected visit gives the reversal leg its origin (and, DEEPEST, its touch wick)
            if(rj)
              {
               m_s[i].rej     = true;
               m_s[i].lastRej = u;
               ApplyLevelCand(i);
               if(m_s[i].cAct)
                 {
                  m_s[i].rO    = m_s[i].cO;
                  m_s[i].rOBar = m_s[i].cOBar;
                  m_s[i].rX    = m_s[i].cX;
                  m_s[i].rXBar = m_s[i].cXBar;
                  m_s[i].cAct  = false;
                 }
              }
           }
         return;
        }
      if(ph == BF_PH_LEG)
        {
         //--- 4.2
         if(OriginBroken(i, h[u], l[u], c[u]))
           {
            SetDone(i, u, BF_R_LEG_BROKEN);
            return;
           }
         if(u - m_s[i].confirmBar > m_p.legExpiryBars)
           {
            SetDone(i, u, BF_R_EXPIRED);
            return;
           }
         //--- v10: the time limit runs from the first placement, also while a re-anchored setup waits to send again
         if(PendTimeUp(i, env))
           {
            m_s[i].pendTimeUp = true;
            SetDone(i, u, BF_R_EXPIRED);
            return;
           }
         if(NewExt(i, h[u], l[u]))
           {
            m_s[i].X    = (d > 0) ? h[u] : l[u];
            m_s[i].xBar = u;
            //--- v5 anticipate: a new-extreme bar is a decision bar too (the orders wait at the updated Fibonacci)
            if(!m_p.anticipate)
               return;
           }
         MarkReady(i);
         return;
        }
      if(ph == BF_PH_ORDERED)
        {
         //--- v10: the pending-order time limit (pendingMaxSec after the first placement) ends the orders and the setup
         if(PendTimeUp(i, env))
           {
            m_s[i].pendTimeUp = true;
            CancelPending(i, u, BF_R_EXPIRED);
            SetDone(i, u, BF_R_EXPIRED);
            return;
           }
         //--- 4.3. 9.01: with env.keepOrders (pending orders kept, and no order can be sent now) a new extreme does
         //    not re-anchor: moving the orders would cancel them with no way to send them again
         if(!env.keepOrders && NewExt(i, h[u], l[u]))
           {
            CancelPending(i, u, BF_R_NEW_EXTREME);
            ResetLevels(i);
            m_s[i].reAnchorBar = u;                             // v10: it keeps its slot to decide again
            m_s[i].X     = (d > 0) ? h[u] : l[u];
            m_s[i].xBar  = u;
            m_s[i].phase = BF_PH_LEG;
            Stat(BF_STAT_REANCHOR);
            //--- v5 anticipate: decided again on this bar at the new extreme; the slot its own cancelled orders held
            //    is given to it through env.slotOwner (Decide). Not after the leg's expiry and not on a session-cancel
            //    bar, where the orders would have been cancelled anyway (steps 3-4): after the expiry the next LEG bar
            //    ends the setup (EXPIRED); after a session-cancel bar it stays in LEG and decides again on a later bar
            //    inside the entry window, as v4 does after a re-anchor.
            if(m_p.anticipate && u - m_s[i].confirmBar <= m_p.legExpiryBars && !(m_p.useSession && env.sessionCancel))
               MarkReady(i);
            return;
           }
         if(OriginBroken(i, h[u], l[u], c[u]))
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
                  if(PendTimeUp(i, env))
                    {
                     m_s[i].pendTimeUp = true;                  // v10: the filled part runs on, the rest is cancelled
                     CancelPending(i, u, BF_R_EXPIRED);
                    }
                  else
                     if(m_p.useSession && env.sessionCancel)
                        CancelPending(i, u, BF_R_SESSION_END);
           }
         MaybeClosed(i, u, BF_R_TARGET);
        }
     }

   //--- v8: drop the setup idle for the longest time (never touched, or away from its zone since its last rejection),
   //    created before bar u
   void              EvictMostIdle(const int u)
     {
      int i;
      int a;
      int best  = -1;
      int bestA = 0;
      for(i = 0; i < m_n; i++)
        {
         if(m_s[i].created >= u)
            continue;
         a = IdleSince(i);
         if(a < 0)
            continue;
         if(best < 0 || a < bestA)
           {
            best  = i;
            bestA = a;
           }
        }
      if(best < 0)
         return;
      SetDone(best, u, BF_R_CAPACITY);
      Compact();
     }

   //+---------------------------------------------------------------+
   //| spec s.3: one new BPR                                         |
   //+---------------------------------------------------------------+
   void              AddSetup(const int u, const ZoneS &z, const int kind)
     {
      int reason = BF_R_NONE;
      int dir    = z.pos;
      BfClearSetup(m_c);
      m_c.id      = m_nextId;
      m_nextId++;
      m_c.kind    = kind;
      m_c.dir     = dir;
      m_c.zdir    = dir;
      m_c.created = u;
      m_c.B       = z.box.bottom;
      m_c.T       = z.box.top;
      //--- v8 (t1WaitBars >= 0, setups may wait long for T1): at capacity the oldest setup that was never touched makes
      //    room (DONE(CAPACITY)), so the newest BPRs are always tracked
      if(m_p.t1WaitBars >= 0 && m_n >= BF_MAX_SETUPS && m_c.T > m_c.B && z.active)
         EvictMostIdle(u);
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

   void              NewSetup(const int u, const ZoneS &z)
     {
      int dir = z.pos;
      //--- v7: CONTINUATION -> one continuation setup, REVERSAL -> one reversal setup, BOTH -> both (continuation
      //    first), each on its own. A setup is tracked if its trade direction is allowed (the reversal trades -dir);
      //    with REVERSAL also for its touch entry, which is in the BPR's direction.
      if(m_p.setupType != BF_SETUP_REVERSAL && DirAllowed(dir))
         AddSetup(u, z, BF_SETUP_CONTINUATION);
      if(m_p.setupType != BF_SETUP_CONTINUATION &&
         (DirAllowed(-dir) || (m_p.setupType == BF_SETUP_REVERSAL && m_p.touchEntry && DirAllowed(dir))))
         AddSetup(u, z, BF_SETUP_REVERSAL);
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
      //--- v5 anticipate: the confirmation bar and new-extreme bars are decision bars only because of anticipation.
      //    A decision there that cannot place any level (every entry beyond a spike's close, or COST / RR / BAD_LEVEL
      //    on a leg that is still short) does not end the setup: nothing is recorded, it stays in LEG and decides
      //    again on a later bar - a new extreme re-sizes the leg, an ordinary pullback candle applies the v4 rule.
      if(nPl == 0 && m_p.anticipate && (u == m_s[i].confirmBar || u == m_s[i].xBar))
         return(false);
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
      if(m_s[i].ordTime == 0)
        {
         m_s[i].ordTime = env.now;                              // v10: the pending-order time limit starts here
         m_s[i].ordBar  = u;
        }
      return(true);
     }

   //+---------------------------------------------------------------+
   //| v6: the touch entry of a setup whose T1 candle just closed:   |
   //| a market order in the BPR's direction at the next open. Stop  |
   //| beyond the BPR's far edge + the stop buffer, target           |
   //| touchTargetRR x the risk. true = decided (record + intent).   |
   //+---------------------------------------------------------------+
   bool              TryTouch(const int i, const int u, const double &c[], const BfEnv &env)
     {
      int    zd   = m_s[i].zdir;
      int    why  = BF_R_NONE;
      double sp   = env.sp;
      double tk   = m_p.tickSize;
      double P;
      double SL;
      double risk;
      double cost = sp + m_p.commPrice + 2.0 * m_p.slippageTicks * tk;
      if(zd > 0)
        {
         P  = c[u] + sp;                                        // a buy fills at the ask
         SL = m_s[i].B - (double)m_p.stopBufferTicks * tk;
        }
      else
        {
         P  = c[u];                                             // a sell fills at the bid
         SL = m_s[i].T + (double)m_p.stopBufferTicks * tk + sp; // the stop of a sell is an ask level
        }
      risk = (double)zd * (P - SL);
      if(risk <= 0.0 || m_p.touchTargetRR <= 0.0)
         why = BF_R_BAD_LEVEL;
      else
         if(m_p.minRR > 0.0 && m_p.touchTargetRR < m_p.minRR)
            why = BF_R_RR;
         else
            if(m_p.maxCostR > 0.0 && cost / risk > m_p.maxCostR)
               why = BF_R_COST;
      if(why != BF_R_NONE)
        {
         AddEvent(u, BF_EV_SKIP, m_s[i], 0, why);               // level 0 = the touch entry
         Stat(BF_STAT_SKIP + why);
         return(false);
        }
      m_s[i].tP  = RoundTick(P);
      m_s[i].tSL = RoundTick(SL);
      m_s[i].tTP = RoundTick(P + (double)zd * m_p.touchTargetRR * risk);
      AddEvent(u, BF_EV_TOUCH_ENTRY, m_s[i], 0, BF_R_NONE);
      AddIntent(BF_EV_TOUCH_ENTRY, m_s[i], 0, BF_R_NONE, u);
      return(true);
     }

   //+---------------------------------------------------------------+
   //| v10 (maxSetups > 1): every ready setup decides on its bar, in |
   //| creation order, while a slot is free (env.freeSlots). A setup |
   //| that moved its own orders on this bar (re-anchor), or whose   |
   //| own touch position holds a slot (env.slotOwner), keeps it. A  |
   //| setup whose EA context still holds its earlier orders waits   |
   //| (env.busyIds); one whose leg another setup already trades     |
   //| ends: one trade per leg.                                      |
   //+---------------------------------------------------------------+
   void              DecideMulti(const int u, const double &c[], const BfEnv &env)
     {
      int  i;
      int  nReady  = 0;
      int  blocked = -1;
      int  free_   = env.freeSlots;
      int  j;
      bool own;
      bool touched = (env.slotOwner > 0);                       // the EA holds one touch position at a time
      for(i = 0; i < m_n; i++)
         if((m_s[i].phase == BF_PH_LEG && m_s[i].ready) || m_s[i].touchReady)
            nReady++;
      if(nReady == 0)
         return;
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
         if(m_s[i].touchReady)
           {
            //--- one touch entry at a time (env.slotOwner = the setup of the open one), so one per bar at most
            if(free_ <= 0 || touched)
               Stat(BF_STAT_BLK_SLOT);
            else
               if(TryTouch(i, u, c, env))
                 {
                  free_--;
                  touched = true;
                 }
            continue;
           }
         if(m_s[i].phase != BF_PH_LEG || !m_s[i].ready)
            continue;
         //--- its earlier orders / position are still in its EA context (a delete that failed, a fill that raced its
         //    cancel): that context already counts as used, and the EA cannot send anyway. Not on its re-anchor bar,
         //    where the context still holds the orders being moved
         if(m_s[i].reAnchorBar != u && EnvBusy(env, m_s[i].id))
            continue;
         //--- the same leg (direction and origin, so the same stop) is already traded by another setup: copies of its
         //    orders would put several times the risk on one trade. One trade per leg: this setup ends
         j = SameLegTraded(i);
         if(j >= 0)
           {
            m_s[i].dupOf = m_s[j].id;
            SetDone(i, u, BF_R_NO_LEVEL);
            continue;
           }
         own = (m_s[i].reAnchorBar == u || (env.slotOwner > 0 && env.slotOwner == m_s[i].id));
         if(!own && free_ <= 0)
           {
            Stat(BF_STAT_BLK_SLOT);
            continue;
           }
         if(TryDecide(i, u, c, env) && !own)
            free_--;
        }
     }

   //+---------------------------------------------------------------+
   //| spec s.5: decisions, creation order, one setup per bar        |
   //+---------------------------------------------------------------+
   void              Decide(const int u, const double &c[], const BfEnv &env)
     {
      int i;
      int nReady  = 0;
      int blocked = -1;
      int own     = -1;                                         // v5: ready setup that owns the busy slot
      if(m_p.maxSetups > 1)
        {
         DecideMulti(u, c, env);                                // v10
         return;
        }
      for(i = 0; i < m_n; i++)
        {
         if(m_s[i].phase == BF_PH_LEG && m_s[i].ready)
           {
            nReady++;
            // v5 anticipate: its own pending limits hold the slot; v6 touch entry: its own touch position does
            if((m_p.anticipate || m_p.touchEntry) && env.slotOwner > 0 && m_s[i].id == env.slotOwner)
               own = i;
           }
         else
            if(m_s[i].touchReady)
               nReady++;                                        // v6: a touch entry on its T1 bar
        }
      if(nReady == 0)
         return;
      if(!env.slotFree && own < 0)
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
      //--- v5 anticipate: the slot is held only by the owner's own pending limits, which it cancelled on this bar
      //    (re-anchor): the owner decides again; every other ready setup waits for the slot
      if(!env.slotFree)
        {
         for(i = 0; i < nReady - 1; i++)
            Stat(BF_STAT_BLK_SLOT);
         TryDecide(own, u, c, env);
         return;
        }
      for(i = 0; i < m_n; i++)
        {
         if(m_s[i].touchReady)
           {
            if(TryTouch(i, u, c, env))
               return;
            continue;
           }
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
         //--- v8 (t1WaitBars >= 0): a warm-up setup that has not confirmed a breakout yet goes on (every BPR is
         //    tracked from its creation, also before the EA started); only confirmed ones end here
         if(m_p.t1WaitBars >= 0 &&
            (m_s[i].phase == BF_PH_WAIT || m_s[i].phase == BF_PH_ZONE || m_s[i].phase == BF_PH_BREAK))
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
         StepExisting(i, u, o, h, l, c, env);
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
      if(m_s[i].ordBar == m_s[i].decisionBar)
        {
         m_s[i].ordTime = 0;                                    // v10: no order was ever placed: no time limit yet
         m_s[i].ordBar  = -1;
        }
      ResetLevels(i);
      m_s[i].phase = BF_PH_LEG;
      Stat(BF_STAT_RETRY);
     }

   //--- harness environment (v6): 0 = no setup ORDERED or FILLED, the id when exactly one is, -1 when more
   int               OccupyingId(void)
     {
      int i;
      int id = 0;
      for(i = 0; i < m_n; i++)
        {
         if(m_s[i].phase != BF_PH_ORDERED && m_s[i].phase != BF_PH_FILLED)
            continue;
         if(id != 0)
            return(-1);
         id = m_s[i].id;
        }
      return(id);
     }

   //--- the phase of setup id (BF_PH_NONE when it is no longer tracked)
   int               PhaseOf(const int id)
     {
      int i = FindIndex(id);
      if(i < 0)
         return(BF_PH_NONE);
      return(m_s[i].phase);
     }

   //--- v10 harness environment: the setups ORDERED or FILLED
   int               BusyCount(void)
     {
      int i;
      int n = 0;
      for(i = 0; i < m_n; i++)
         if(m_s[i].phase == BF_PH_ORDERED || m_s[i].phase == BF_PH_FILLED)
            n++;
      return(n);
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
