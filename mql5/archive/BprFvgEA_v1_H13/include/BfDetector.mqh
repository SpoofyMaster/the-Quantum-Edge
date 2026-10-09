//+------------------------------------------------------------------+
//| BfDetector.mqh                                                   |
//| BprFvgEA: turns LuxAlgo BPR / FVG zones into buy and sell setups |
//+------------------------------------------------------------------+
//
// © LuxAlgo (original Pine v5 logic of 'ICT Concepts [LuxAlgo]') for the zones this detector consumes.
// Licence: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)
//          https://creativecommons.org/licenses/by-nc-sa/4.0/
// BprFvgEA contains a port / derivative work of the FVG and Balance Price Range logic of the Pine v5 script
// "ICT Concepts [LuxAlgo]" (see BfEngine.mqh). The EA, including this file, is distributed under the same licence:
// NON-COMMERCIAL use only, attribution to LuxAlgo required, share-alike. Not affiliated with or endorsed by LuxAlgo.
// The setup rules below are this project's own (hypothesis H-13), not LuxAlgo's.
//
// What it is: the pure detector of research/indicators/BPR_FVG_EA_SPEC.md section 4 ("spec s.N" below).
// It gets closed bars, the engine state after ProcessBar(u) and an environment (BfEnv), and it emits
//   - intents  : PLACE_LIMIT, MARKET, CANCEL                      (IntentCount / GetIntent / ClearIntents)
//   - events   : ARMED, DONE, MSS, PLACE_LIMIT, MARKET, CANCEL     (EventCount / GetEvent / ClearEvents)
// The executor reports back with NotifyFilled / NotifyCancelled / NotifyClosed.
// STATUS of the trading rules: untested HYPOTHESIS (H-13). Paper / demo / tester use only.
//
// PURITY CONTRACT: no MT5 API (transliterated to C++ for the parity harness). Fixed-size arrays only; price arrays
// enter as 'const double &x[]' parameters; only MathMax / MathMin / MathAbs / MathRound are used.
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
   int               m_refFvgUp;        // id of the setup made from the newest bullish FVG (0 = none)
   int               m_refFvgDn;        // id of the setup made from the newest bearish FVG (0 = none)
   BfSetup           m_s[BF_MAX_SETUPS];   // tracked setups (ARMED / ORDERED / FILLED), in creation order
   int               m_n;
   BfIntent          m_in[BF_MAX_INTENTS];
   int               m_nIn;
   int               m_inLost;
   BfEvent           m_ev[BF_MAX_EVENTS];
   int               m_nEv;
   int               m_evLost;
   BfSetup           m_c;               // candidate under construction (step 4)

   //--- spec s.4 step 5: "All levels are rounded to the tick": MathRound(x / tick) * tick, then normalised to the
   //    symbol digits (NormalizeDouble), so a level equals the broker's price exactly (201734 * 0.01 is
   //    2017.3400000000001 in binary; normalised it is 2017.34, the same double as a 2017.34 bar high).
   double            RoundTick(const double x)
     {
      if(m_p.tickSize <= 0.0)
         return(x);
      return(NormalizeDouble(MathRound(x / m_p.tickSize) * m_p.tickSize, m_p.digits));
     }

   //--- spec s.9: one record per intent and per status change.
   void              AddEvent(const int n, const int evType, const BfSetup &s, const int reason)
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
      m_ev[m_nEv].src         = s.src;
      m_ev[m_nEv].reason      = reason;
      m_ev[m_nEv].P           = s.P;
      m_ev[m_nEv].SL          = s.SL;
      m_ev[m_nEv].TP1         = s.TP1;
      m_ev[m_nEv].TP2         = s.TP2;
      m_ev[m_nEv].status      = s.status;
      m_ev[m_nEv].ordKind     = s.ordKind;
      m_ev[m_nEv].created     = s.created;
      m_ev[m_nEv].B           = s.B;
      m_ev[m_nEv].T           = s.T;
      m_ev[m_nEv].h           = s.h;
      m_ev[m_nEv].sweepBar    = s.sweepBar;
      m_ev[m_nEv].M           = s.M;
      m_ev[m_nEv].mssDone     = s.mssDone;
      m_ev[m_nEv].mssBar      = s.mssBar;
      m_ev[m_nEv].X           = s.X;
      m_ev[m_nEv].O           = s.O;
      m_ev[m_nEv].decisionBar = s.decisionBar;
      m_nEv++;
     }

   void              AddIntent(const int type, const BfSetup &s, const int reason, const int bar)
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
      m_in[m_nIn].src    = s.src;
      m_in[m_nIn].reason = reason;
      m_in[m_nIn].bar    = bar;
      m_in[m_nIn].P      = s.P;
      m_in[m_nIn].SL     = s.SL;
      m_in[m_nIn].TP1    = s.TP1;
      m_in[m_nIn].TP2    = s.TP2;
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

   //--- drops CLOSED and DONE setups, keeps the creation order of the others.
   void              Compact(void)
     {
      int r;
      int w = 0;
      for(r = 0; r < m_n; r++)
        {
         if(m_s[r].status == BF_ST_DONE || m_s[r].status == BF_ST_CLOSED)
            continue;
         if(w != r)
            BfCopySetup(m_s[w], m_s[r]);
         w++;
        }
      m_n = w;
     }

   //--- status -> DONE(reason). A pending order is cancelled: DONE record first, then the CANCEL intent.
   void              SetDone(const int i, const int n, const int reason, const bool cancelOrder)
     {
      m_s[i].status = BF_ST_DONE;
      m_s[i].reason = reason;
      AddEvent(n, BF_EV_DONE, m_s[i], reason);
      if(cancelOrder)
        {
         AddEvent(n, BF_EV_CANCEL, m_s[i], reason);
         AddIntent(BF_EV_CANCEL, m_s[i], reason, n);
        }
     }

   bool              SourceAllowed(const int src)
     {
      return(m_p.source == BF_SOURCE_BOTH || m_p.source == src);
     }

   bool              DirAllowed(const int dir)
     {
      if(m_p.direction == BF_DIR_LONG_ONLY)
         return(dir > 0);
      if(m_p.direction == BF_DIR_SHORT_ONLY)
         return(dir < 0);
      return(true);
     }

   //+---------------------------------------------------------------+
   //| spec s.3: one candidate. Returns its id, or 0 when the source |
   //| / direction filters remove it (never logged).                 |
   //+---------------------------------------------------------------+
   int               NewCandidate(const int u, const int src, const int dir, const double bot, const double top,
                                  const double deep, const double brk, const bool brokenAtCreation,
                                  const double &h[], const double &l[], const double &c[])
     {
      int    k;
      int    lo_     = 0;
      int    s       = 0;
      int    reason  = BF_R_NONE;
      double ext     = 0.0;
      double rng     = 0.0;
      bool   sweepOK = false;

      if(!SourceAllowed(src) || !DirAllowed(dir))
         return(0);

      BfClearSetup(m_c);
      m_c.id      = m_nextId;
      m_nextId++;
      m_c.src     = src;
      m_c.dir     = dir;
      m_c.created = u;
      m_c.B       = bot;
      m_c.T       = top;
      m_c.h       = top - bot;
      m_c.deep    = deep;
      m_c.brk     = brk;

      //--- spec s.3.1 notes
      if(m_c.h <= 0.0)
         reason = BF_R_BAD_GEOMETRY;
      else
         if(brokenAtCreation)
            reason = BF_R_BROKEN_AT_CREATION;
         else
           {
            //--- spec s.3.2 sweep: extreme bar s in [u - sweep_window, u] (clipped at 0), ties -> the LATEST bar
            lo_ = BfIMax(0, u - m_p.sweepWindow);
            s   = lo_;
            ext = (dir > 0) ? l[lo_] : h[lo_];
            for(k = lo_; k <= u; k++)
              {
               if(dir > 0)
                 {
                  if(l[k] <= ext)
                    {
                     ext = l[k];
                     s   = k;
                    }
                 }
               else
                 {
                  if(h[k] >= ext)
                    {
                     ext = h[k];
                     s   = k;
                    }
                 }
              }
            m_c.sweepBar = s;
            if(s - m_p.rangeBars < 0)
               reason = BF_R_INSUFFICIENT_HISTORY;              // the range window must exist
            else
              {
               // R = min l (long) / max h (short) over [s - range_bars, s - 1]
               rng = (dir > 0) ? l[s - m_p.rangeBars] : h[s - m_p.rangeBars];
               for(k = s - m_p.rangeBars; k <= s - 1; k++)
                 {
                  if(dir > 0)
                     rng = MathMin(rng, l[k]);
                  else
                     rng = MathMax(rng, h[k]);
                 }
               m_c.R   = rng;
               sweepOK = (dir > 0) ? (l[s] < rng) : (h[s] > rng);
               if(m_p.useSweep && !sweepOK)
                  reason = BF_R_NO_SWEEP;
               else
                  if(s - m_p.mssBars < 0)
                     reason = BF_R_INSUFFICIENT_HISTORY;        // spec s.3.3: s - mss_bars >= 0
                  else
                    {
                     //--- spec s.3.3: M = max h (long) / min l (short) over [s - mss_bars, s - 1]
                     m_c.M = (dir > 0) ? h[s - m_p.mssBars] : l[s - m_p.mssBars];
                     for(k = s - m_p.mssBars; k <= s - 1; k++)
                       {
                        if(dir > 0)
                           m_c.M = MathMax(m_c.M, h[k]);
                        else
                           m_c.M = MathMin(m_c.M, l[k]);
                       }
                     //--- MSS at creation: first closed bar m in (s, u] with c[m] beyond M
                     if(m_p.useMss)
                       {
                        for(k = s + 1; k <= u; k++)
                          {
                           if((dir > 0 && c[k] > m_c.M) || (dir < 0 && c[k] < m_c.M))
                             {
                              m_c.mssDone = true;
                              m_c.mssBar  = k;
                              break;
                             }
                          }
                       }
                     else
                       {
                        m_c.mssDone = true;                    // treated as having happened at creation
                        m_c.mssBar  = u;
                       }
                     //--- spec s.3.4: rally extreme X over [s, u]; measured-move origin O over [u - rally_bars, u]
                     m_c.X = (dir > 0) ? h[s] : l[s];
                     for(k = s; k <= u; k++)
                       {
                        if(dir > 0)
                           m_c.X = MathMax(m_c.X, h[k]);
                        else
                           m_c.X = MathMin(m_c.X, l[k]);
                       }
                     lo_ = BfIMax(0, u - m_p.rallyBars);
                     m_c.O = (dir > 0) ? l[lo_] : h[lo_];
                     for(k = lo_; k <= u; k++)
                       {
                        if(dir > 0)
                           m_c.O = MathMin(m_c.O, l[k]);
                        else
                           m_c.O = MathMax(m_c.O, h[k]);
                       }
                     //--- spec s.4 step 4: capacity of tracked setups
                     if(m_n >= BF_MAX_SETUPS)
                        reason = BF_R_CAPACITY;
                    }
              }
           }

      if(reason != BF_R_NONE)
        {
         m_c.status = BF_ST_DONE;
         m_c.reason = reason;
         AddEvent(u, BF_EV_DONE, m_c, reason);
         return(m_c.id);
        }

      m_c.status = BF_ST_ARMED;
      BfCopySetup(m_s[m_n], m_c);
      m_n++;
      AddEvent(u, BF_EV_ARMED, m_c, BF_R_NONE);
      if(m_c.mssDone)
         AddEvent(u, BF_EV_MSS, m_c, BF_R_NONE);
      return(m_c.id);
     }

   //+---------------------------------------------------------------+
   //| spec s.4 step 2: consecutive-gap update of FVG_UP[0] / FVG_DN[0]|
   //+---------------------------------------------------------------+
   void              RefreshFvg(const StateS &eng, const BfEngineEvents &ev)
     {
      int i;
      if(ev.updFvgUp && m_refFvgUp > 0 && eng.nFu > 0 && eng.fu[0].box.exists)
        {
         i = FindIndex(m_refFvgUp);
         if(i >= 0 && m_s[i].status == BF_ST_ARMED && m_s[i].src == BF_SOURCE_FVG && m_s[i].dir > 0)
           {
            m_s[i].B    = eng.fu[0].box.bottom;
            m_s[i].T    = eng.fu[0].box.top;
            m_s[i].h    = m_s[i].T - m_s[i].B;
            m_s[i].deep = m_s[i].B;                             // Lo = B
            m_s[i].brk  = m_s[i].B;                             // break: l[k] < B
           }
        }
      if(ev.updFvgDn && m_refFvgDn > 0 && eng.nFd > 0 && eng.fd[0].box.exists)
        {
         i = FindIndex(m_refFvgDn);
         if(i >= 0 && m_s[i].status == BF_ST_ARMED && m_s[i].src == BF_SOURCE_FVG && m_s[i].dir < 0)
           {
            m_s[i].B    = eng.fd[0].box.bottom;
            m_s[i].T    = eng.fd[0].box.top;
            m_s[i].h    = m_s[i].T - m_s[i].B;
            m_s[i].deep = m_s[i].T;                             // Hi = T
            m_s[i].brk  = m_s[i].T;                             // break: h[k] > T
           }
        }
     }

   //+---------------------------------------------------------------+
   //| spec s.4 step 3: one existing setup (ARMED or ORDERED-pending)|
   //+---------------------------------------------------------------+
   void              StepExisting(const int i, const int u, const double &h[], const double &l[], const double &c[],
                                  const BfEnv &env)
     {
      bool pending = false;
      bool broken  = false;
      // ORDERED and not yet filled = pending (LIMIT order, or a MARKET decision the executor has not filled yet;
      // live, a MARKET order is filled or cancelled on the same tick, so only the parity harness sees it here).
      if(m_s[i].status == BF_ST_ARMED)
         pending = false;
      else
         if(m_s[i].status == BF_ST_ORDERED)
            pending = true;
         else
            return;

      //--- a. break (spec s.3.1 break rule, bar k > created)
      if(m_s[i].dir > 0)
         broken = (l[u] < m_s[i].brk);
      else
         broken = (h[u] > m_s[i].brk);
      if(broken)
        {
         SetDone(i, u, BF_R_BROKEN, pending);
         return;
        }
      //--- b. expiry
      if(u - m_s[i].created > m_p.expiryBars)
        {
         SetDone(i, u, BF_R_EXPIRED, pending);
         return;
        }
      if(pending)
        {
         //--- c. runaway (pending LIMIT only): long h[u] >= TP1; short l[u] <= TP1 - spread (TP1 is an ask level)
         if(m_s[i].ordKind == BF_ORD_LIMIT &&
            ((m_s[i].dir > 0 && h[u] >= m_s[i].TP1) || (m_s[i].dir < 0 && l[u] <= m_s[i].TP1 - env.sp)))
           {
            SetDone(i, u, BF_R_RUNAWAY, true);
            return;
           }
         //--- d. session cancel (pending only)
         if(m_p.useSession && env.sessionCancel)
           {
            SetDone(i, u, BF_R_SESSION_END, true);
            return;
           }
         return;
        }
      //--- e. ARMED: update the extreme X, check the MSS (spec s.3.3, s.3.4)
      if(m_s[i].dir > 0)
         m_s[i].X = MathMax(m_s[i].X, h[u]);
      else
         m_s[i].X = MathMin(m_s[i].X, l[u]);
      if(!m_s[i].mssDone)
        {
         if((m_s[i].dir > 0 && c[u] > m_s[i].M) || (m_s[i].dir < 0 && c[u] < m_s[i].M))
           {
            m_s[i].mssDone = true;
            m_s[i].mssBar  = u;
            AddEvent(u, BF_EV_MSS, m_s[i], BF_R_NONE);
           }
        }
     }

   //+---------------------------------------------------------------+
   //| spec s.4 step 4: candidates of bar u, in the spec order       |
   //+---------------------------------------------------------------+
   void              NewCandidates(const int u, const double &h[], const double &l[], const double &c[],
                                   const StateS &eng, const BfEngineEvents &ev)
     {
      int    pos  = 0;
      int    id   = 0;
      double bot  = 0.0;
      double top  = 0.0;
      double deep = 0.0;
      double brk  = 0.0;
      bool   pairOk = (eng.nFu > 0 && eng.nFd > 0 && eng.fu[0].box.exists && eng.fd[0].box.exists);

      //--- 1. the BPR from the UP array. Direction = pos (pos = 0 cannot occur, QUIRK 5).
      if(ev.newBprUp && pairOk && eng.nBu > 0 && eng.bu[0].box.exists && !eng.bu[0].posNa)
        {
         pos = eng.bu[0].pos;
         if(pos == 1 || pos == -1)
           {
            bot = eng.bu[0].box.bottom;
            top = MathMin(eng.fu[0].box.top, eng.fd[0].box.top);
            if(pos == 1)
              {
               deep = MathMin(eng.fu[0].box.bottom, eng.fd[0].box.bottom);   // Lo
               brk  = eng.bu[0].box.bottom;                                    // l[k] < Z.bottom
              }
            else
              {
               deep = MathMax(eng.fu[0].box.top, eng.fd[0].box.top);         // Hi
               brk  = eng.bu[0].box.top;                                       // h[k] > Z.top
              }
            NewCandidate(u, BF_SOURCE_BPR, pos, bot, top, deep, brk, !eng.bu[0].active, h, l, c);
           }
        }
      //--- 2. the BPR from the DN array
      if(ev.newBprDn && pairOk && eng.nBd > 0 && eng.bd[0].box.exists && !eng.bd[0].posNa)
        {
         pos = eng.bd[0].pos;
         if(pos == 1 || pos == -1)
           {
            bot = eng.bd[0].box.bottom;
            top = MathMin(eng.fu[0].box.top, eng.fd[0].box.top);
            if(pos == 1)
              {
               deep = MathMin(eng.fu[0].box.bottom, eng.fd[0].box.bottom);
               brk  = eng.bd[0].box.bottom;
              }
            else
              {
               deep = MathMax(eng.fu[0].box.top, eng.fd[0].box.top);
               brk  = eng.bd[0].box.top;
              }
            NewCandidate(u, BF_SOURCE_BPR, pos, bot, top, deep, brk, !eng.bd[0].active, h, l, c);
           }
        }
      //--- 3. the bullish FVG: B = Z.bottom (= high[u-2]), T = Z.top (= low[u]), Lo = B, break l[k] < B
      if(ev.newFvgUp && eng.nFu > 0 && eng.fu[0].box.exists)
        {
         id = NewCandidate(u, BF_SOURCE_FVG, 1, eng.fu[0].box.bottom, eng.fu[0].box.top, eng.fu[0].box.bottom,
                           eng.fu[0].box.bottom, false, h, l, c);
         m_refFvgUp = id;                                       // 0 when filtered: no setup refers to FVG_UP[0]
        }
      //--- 4. the bearish FVG: B = Z.bottom (= high[u]), T = Z.top (= low[u-2]), Hi = T, break h[k] > T
      if(ev.newFvgDn && eng.nFd > 0 && eng.fd[0].box.exists)
        {
         id = NewCandidate(u, BF_SOURCE_FVG, -1, eng.fd[0].box.bottom, eng.fd[0].box.top, eng.fd[0].box.top,
                           eng.fd[0].box.top, false, h, l, c);
         m_refFvgDn = id;
        }
     }

   //+---------------------------------------------------------------+
   //| spec s.4 step 5: one ARMED setup with the MSS done. Returns   |
   //| true when an order was decided.                               |
   //+---------------------------------------------------------------+
   bool              TryDecide(const int i, const int u, const double &o[], const double &h[], const double &l[],
                               const double &c[], const BfEnv &env)
     {
      int    dir = m_s[i].dir;
      int    evType = BF_EV_NONE;
      double sp  = env.sp;
      double tk  = m_p.tickSize;
      double bot = m_s[i].B;
      double top = m_s[i].T;
      double zh  = m_s[i].h;
      double P     = 0.0;
      double SL    = 0.0;
      double TP1   = 0.0;
      double TP2   = 0.0;
      double risk  = 0.0;
      double rr1   = 0.0;
      double costR = 0.0;

      if(m_p.entryMode == BF_ENTRY_CONFIRM)
        {
         //--- CONFIRM trigger on the same bar u (step 3a already ran)
         if(dir > 0)
           {
            if(!(l[u] <= bot + zh / 4.0 && c[u] >= bot + zh / 2.0 && c[u] > o[u]))
               return(false);
            P = c[u] + sp;                                      // expected ask
           }
         else
           {
            if(!(h[u] >= top - zh / 4.0 && c[u] <= top - zh / 2.0 && c[u] < o[u]))
               return(false);
            P = c[u];                                           // expected bid
           }
         evType = BF_EV_MARKET;
        }
      else
        {
         //--- LIMIT price
         if(dir > 0)
            P = bot + (double)m_p.entryOffsetTicks * tk + sp;   // ask buy-limit price
         else
            P = top - (double)m_p.entryOffsetTicks * tk;        // bid sell-limit price
         evType = BF_EV_PLACE_LIMIT;
        }

      //--- levels (same formulas for LIMIT and CONFIRM)
      if(dir > 0)
        {
         SL  = MathMin(bot - m_p.stopZoneMult * zh, m_s[i].deep - 2.0 * sp);      // bid level
         TP1 = m_s[i].X - 2.0 * sp;                                               // bid
         TP2 = P + (m_s[i].X - m_s[i].O);                                         // bid
        }
      else
        {
         SL  = MathMax(top + m_p.stopZoneMult * zh, m_s[i].deep + 2.0 * sp) + sp; // ask level
         TP1 = m_s[i].X + 2.0 * sp;                                               // ask
         TP2 = P - (m_s[i].O - m_s[i].X);                                         // ask
        }

      //--- marketability (LIMIT only): market already through P -> wait for the next bar
      if(evType == BF_EV_PLACE_LIMIT)
        {
         if(dir > 0 && c[u] + sp <= P)                          // decision ask = c[u] + sp
            return(false);
         if(dir < 0 && c[u] >= P)                               // decision bid = c[u]
            return(false);
        }

      //--- checks (on the unrounded levels); a failure keeps the setup ARMED for the next bar
      risk = MathAbs(P - SL);
      if(risk <= 0.0)
         return(false);
      if(dir > 0 && TP1 <= P)
         return(false);
      if(dir < 0 && TP1 >= P)
         return(false);
      rr1 = MathAbs(TP1 - P) / risk;
      if(rr1 < m_p.minRR)
         return(false);
      costR = (sp + m_p.commPrice + 2.0 * m_p.slippageTicks * tk) / risk;
      if(costR > m_p.maxCostR)
         return(false);

      //--- TP1_TP2 with TP2 not beyond TP1: the trade uses TP1 only (TP2 is set equal to TP1)
      if(m_p.tpMode == BF_TP_TP1_TP2 && ((dir > 0 && TP2 <= TP1) || (dir < 0 && TP2 >= TP1)))
         TP2 = TP1;

      //--- result: ORDERED, levels rounded to the tick, X frozen
      m_s[i].P           = RoundTick(P);
      m_s[i].SL          = RoundTick(SL);
      m_s[i].TP1         = RoundTick(TP1);
      m_s[i].TP2         = RoundTick(TP2);
      m_s[i].status      = BF_ST_ORDERED;
      m_s[i].ordKind     = (evType == BF_EV_MARKET) ? BF_ORD_MARKET : BF_ORD_LIMIT;
      m_s[i].decisionBar = u;
      AddEvent(u, evType, m_s[i], BF_R_NONE);
      AddIntent(evType, m_s[i], BF_R_NONE, u);
      return(true);
     }

   //+---------------------------------------------------------------+
   //| spec s.4 step 5: entry decisions, creation order, <= 1 per bar|
   //+---------------------------------------------------------------+
   void              Decide(const int u, const double &o[], const double &h[], const double &l[], const double &c[],
                            const BfEnv &env)
     {
      int i;
      if(!env.slotFree)
         return;
      if(m_p.useSession && !env.sessionEntryOk)
         return;
      if(!env.riskOk)
         return;
      if(!env.spreadOk)
         return;
      for(i = 0; i < m_n; i++)
        {
         if(m_s[i].status != BF_ST_ARMED || !m_s[i].mssDone)
            continue;
         if(m_s[i].created < m_tradeFrom)
            continue;                                           // warm-up setups never trade
         if(TryDecide(i, u, o, h, l, c, env))
            return;                                             // at most one order per bar
        }
     }

public:
                     CBfDetector(void)
     {
      BfDefaultParams(m_p);
      BfClearSetup(m_c);
      m_tradeFrom = 0;
      m_warmEnded = false;
      m_disabled  = false;
      m_nextId    = 1;
      m_lastBar   = -1;
      m_refFvgUp  = 0;
      m_refFvgDn  = 0;
      m_n         = 0;
      m_nIn       = 0;
      m_inLost    = 0;
      m_nEv       = 0;
      m_evLost    = 0;
     }

   //--- tradeFrom = index of the first bar whose setups may trade (the number of warm-up bars).
   void              Init(const BfParams &p, const int tradeFrom)
     {
      BfCopyParams(m_p, p);
      BfClearSetup(m_c);
      m_tradeFrom = tradeFrom;
      m_warmEnded = false;
      m_disabled  = (p.fvgMode != BF_FVGTYPE_FVG);           // spec s.1: setups need FVG
      m_nextId    = 1;
      m_lastBar   = -1;
      m_refFvgUp  = 0;
      m_refFvgDn  = 0;
      m_n         = 0;
      m_nIn       = 0;
      m_inLost    = 0;
      m_nEv       = 0;
      m_evLost    = 0;
     }

   //--- spec s.4 step 4: setups created during warm-up become DONE(WARMUP) when warm-up ends.
   //    The records carry n = the last bar processed (tradeFrom - 1). Idempotent.
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
         if(m_s[i].status == BF_ST_ARMED)
            SetDone(i, m_lastBar, BF_R_WARMUP, false);
         else
            if(m_s[i].status == BF_ST_ORDERED && m_s[i].ordKind == BF_ORD_LIMIT)
               SetDone(i, m_lastBar, BF_R_WARMUP, true);       // cannot happen: no decisions during warm-up
        }
      Compact();
     }

   //+---------------------------------------------------------------+
   //| spec s.4: one closed bar u. The engine has already processed  |
   //| bar u (step 1); eng / ev are its state and events.            |
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

      //--- step 2: FVG update refresh
      RefreshFvg(eng, ev);
      //--- step 3: existing setups in creation order
      for(i = 0; i < m_n; i++)
         StepExisting(i, u, h, l, c, env);
      Compact();
      //--- step 4: new candidates (they take part in step 5 on the same bar)
      NewCandidates(u, h, l, c, eng, ev);
      //--- step 5: entry decisions (never during warm-up)
      if(u >= m_tradeFrom)
         Decide(u, o, h, l, c, env);
      Compact();
     }

   //--- executor feedback (spec s.4 last paragraph)
   void              NotifyFilled(const int id)
     {
      int i = FindIndex(id);
      if(i < 0)
         return;
      if(m_s[i].status == BF_ST_ORDERED)
         m_s[i].status = BF_ST_FILLED;
     }

   void              NotifyCancelled(const int id, const int reason)
     {
      int i = FindIndex(id);
      if(i < 0)
         return;
      if(m_s[i].status == BF_ST_ORDERED || m_s[i].status == BF_ST_ARMED)
        {
         SetDone(i, m_lastBar, reason, false);                  // the executor already removed the order
         Compact();
        }
     }

   //--- EA executor only; the parity harness never calls it. A decided order could not be sent for a transient
   //    reason (limit inside the stops level, slot busy, no tick, daily budget; spec s.5 "Marketable LIMIT
   //    decisions"): ORDERED -> ARMED, no order kind, levels cleared, X unfrozen (StepExisting updates it again
   //    from the next bar). No event record.
   void              NotifyRetry(const int id)
     {
      int i = FindIndex(id);
      if(i < 0)
         return;
      if(m_s[i].status != BF_ST_ORDERED)
         return;
      m_s[i].status      = BF_ST_ARMED;
      m_s[i].ordKind     = BF_ORD_NONE;
      m_s[i].P           = 0.0;
      m_s[i].SL          = 0.0;
      m_s[i].TP1         = 0.0;
      m_s[i].TP2         = 0.0;
      m_s[i].decisionBar = -1;
     }

   void              NotifyClosed(const int id)
     {
      int i = FindIndex(id);
      if(i < 0)
         return;
      if(m_s[i].status == BF_ST_FILLED)
        {
         m_s[i].status = BF_ST_CLOSED;
         Compact();
        }
     }

   //--- harness environment: slot_free = no setup in ORDERED or FILLED (spec s.9)
   bool              HasOrderOrPosition(void)
     {
      int i;
      for(i = 0; i < m_n; i++)
         if(m_s[i].status == BF_ST_ORDERED || m_s[i].status == BF_ST_FILLED)
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

   //--- inspection (panel, logs)
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

   int               ArmedCount(void)
     {
      int i;
      int k = 0;
      for(i = 0; i < m_n; i++)
         if(m_s[i].status == BF_ST_ARMED)
            k++;
      return(k);
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
