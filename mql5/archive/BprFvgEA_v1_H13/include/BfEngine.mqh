//+------------------------------------------------------------------+
//| BfEngine.mqh                                                     |
//| BprFvgEA: the LuxAlgo Fair Value Gap / Balance Price Range engine |
//+------------------------------------------------------------------+
//
// © LuxAlgo (original Pine v5 logic of 'ICT Concepts [LuxAlgo]')
// Licence: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)
//          https://creativecommons.org/licenses/by-nc-sa/4.0/
//
// This file is a PORT / DERIVATIVE WORK of the FVG, Balance Price Range and displacement logic of the Pine v5
// script "ICT Concepts [LuxAlgo]". It is distributed under the same licence (CC BY-NC-SA 4.0): NON-COMMERCIAL use
// only, attribution to LuxAlgo required, and any redistributed derivative must keep this licence.
// It is not affiliated with or endorsed by LuxAlgo.
// The changes made on purpose versus the original are listed in research/indicators/LUXALGO_BPR_SPEC.md, section 10.
//
// The code is copied from mql5/Indicators/LuxAlgo_BPR/LuxAlgo_BPR.mq5 (verified bar for bar against the Python
// reference qe/indicators/luxalgo_bpr.py) with three mechanical changes only:
//   1. the input globals are replaced by a BfEngineParams argument (length, visBoxes, fvgMode, showFVG, bpr);
//   2. Historical mode only: Pine 'per' is always true (spec s.2 of BPR_FVG_EA_SPEC.md; Present mode looks ahead);
//   3. ProcessBar() also reports a BfEngineEvents record (new / updated FVG, new BPR).
// One display-only field is added: 'fvgStyled' replaces Pine's 'not i_BPR' test in the FVG break loops (dashed /
// dotted border and break fill of FVG boxes). The EA computes BPRs always (bpr = true) but shows FVG boxes styled
// as the indicator does with BPR off when the user hides the BPRs. border / brokenFill are never read by any
// logic (BPR block, break loops, detector); they only feed the renderer.
//
// "Pine Lnnn" = line nnn of research/indicators/luxalgo_ict_concepts.pine (unmodified source).
// "spec s.N" / "QUIRK k" = research/indicators/LUXALGO_BPR_SPEC.md.
//
// PURITY CONTRACT: no MT5 API (transliterated to C++ for the parity harness). Arrays enter only as parameters.
//+------------------------------------------------------------------+
#ifndef BF_ENGINE_MQH
#define BF_ENGINE_MQH

#include "BfDefines.mqh"

#define BF_MAXB           20      // max of '# Visible FVG's' (Pine L74 maxval = 20)
#define BF_PERC_BODY      0.36    // Pine L38 perc_Body
#define BF_BX_BACK        10      // Pine L39 bxBack
#define BF_EXT            8       // Pine L609 / L703: right = bar_index + 8
#define BF_FIB_LEN        50      // Pine L126 plus = 50 (xloc.bar_index)

#define BF_KIND_FU        0       // bFVG_UP (Pine L238)
#define BF_KIND_FD        1       // bFVG_DN (Pine L239)
#define BF_KIND_BU        2       // bBPR_UP (Pine L241)
#define BF_KIND_BD        3       // bBPR_DN (Pine L242)

#define BF_BORDER_SOLID   0
#define BF_BORDER_DASHED  1
#define BF_BORDER_DOTTED  2

//+------------------------------------------------------------------+
//| Parameters and per-bar events                                    |
//+------------------------------------------------------------------+
struct BfEngineParams
  {
   int               length;        // Pine len (3..10): period of the body SMA
   int               visBoxes;      // Pine visBxs (1..20): length of the four arrays
   int               fvgMode;       // BF_FVGTYPE_FVG / BF_FVGTYPE_IFVG (Pine i_FVG)
   bool              showFVG;       // Pine shwFVG; always true in the EA
   bool              bpr;           // Pine i_BPR; always true in the EA (setups need BPRs)
   bool              fvgStyled;     // display only: FVG borders/fills styled as with i_BPR off (see header)
  };

// What ProcessBar(n) did on bar n (spec s.2 of BPR_FVG_EA_SPEC.md).
struct BfEngineEvents
  {
   bool              newBprUp;      // a new BPR at index 0 of BPR_UP
   bool              newBprDn;      // a new BPR at index 0 of BPR_DN
   bool              newFvgUp;      // a new bullish FVG at index 0 of FVG_UP
   bool              newFvgDn;      // a new bearish FVG at index 0 of FVG_DN
   bool              updFvgUp;      // consecutive-gap update applied to the existing FVG_UP[0]
   bool              updFvgDn;      // consecutive-gap update applied to the existing FVG_DN[0]
  };

//+------------------------------------------------------------------+
//| State structures (simple structs only; copied field by field)    |
//+------------------------------------------------------------------+
// A Pine box. exists == false is Pine 'box(na)'.
struct BoxS
  {
   bool              exists;
   int               left;          // absolute bar index (Pine bar_index)
   int               right;         // absolute bar index, may be > last bar (future)
   double            top;           // stored as given, never normalised (QUIRK 1)
   double            bottom;
   int               border;        // BF_BORDER_SOLID / _DASHED / _DOTTED
   bool              brokenFill;    // fill switched to the break colour (Pine set_bgcolor(..BR, 95))
  };

// Pine 'type FVG' (Pine L197-200): box, active, pos.
struct ZoneS
  {
   BoxS              box;
   bool              active;
   int               pos;           // 1 / -1 / 0 (BPR only)
   bool              posNa;         // true = Pine pos is na (all FVG entries)
  };

// The four Pine arrays. Each holds exactly n* entries (visBxs, or 0 for BPR when it is off).
struct StateS
  {
   ZoneS             fu[BF_MAXB];   // bFVG_UP
   ZoneS             fd[BF_MAXB];   // bFVG_DN
   ZoneS             bu[BF_MAXB];   // bBPR_UP
   ZoneS             bd[BF_MAXB];   // bBPR_DN
   int               nFu;
   int               nFd;
   int               nBu;
   int               nBd;
  };

//+------------------------------------------------------------------+
//| Small helpers                                                    |
//+------------------------------------------------------------------+
int BfIMin(const int a, const int b)
  {
   return((a < b) ? a : b);
  }

int BfIMax(const int a, const int b)
  {
   return((a > b) ? a : b);
  }

int BfIClamp(const int v, const int lo_, const int hi_)
  {
   if(v < lo_)
      return(lo_);
   if(v > hi_)
      return(hi_);
   return(v);
  }

void BfClearEngineEvents(BfEngineEvents &ev)
  {
   ev.newBprUp = false;
   ev.newBprDn = false;
   ev.newFvgUp = false;
   ev.newFvgDn = false;
   ev.updFvgUp = false;
   ev.updFvgDn = false;
  }

void BfCopyEngineParams(BfEngineParams &dst, const BfEngineParams &src)
  {
   dst.length    = src.length;
   dst.visBoxes  = src.visBoxes;
   dst.fvgMode   = src.fvgMode;
   dst.showFVG   = src.showFVG;
   dst.bpr       = src.bpr;
   dst.fvgStyled = src.fvgStyled;
  }

//+------------------------------------------------------------------+
//| State helpers                                                    |
//+------------------------------------------------------------------+
// Pine FVG.new(box(na), false) : box na, active false, pos na.
void ClearZone(ZoneS &z)
  {
   z.box.exists     = false;
   z.box.left       = 0;
   z.box.right      = 0;
   z.box.top        = 0.0;
   z.box.bottom     = 0.0;
   z.box.border     = BF_BORDER_SOLID;
   z.box.brokenFill = false;
   z.active         = false;
   z.pos            = 0;
   z.posNa          = true;
  }

void CopyZone(ZoneS &dst, const ZoneS &src)
  {
   dst.box.exists     = src.box.exists;
   dst.box.left       = src.box.left;
   dst.box.right      = src.box.right;
   dst.box.top        = src.box.top;
   dst.box.bottom     = src.box.bottom;
   dst.box.border     = src.box.border;
   dst.box.brokenFill = src.box.brokenFill;
   dst.active         = src.active;
   dst.pos            = src.pos;
   dst.posNa          = src.posNa;
  }

void CopyState(StateS &dst, const StateS &src)
  {
   int i;
   for(i = 0; i < BF_MAXB; i++)
     {
      CopyZone(dst.fu[i], src.fu[i]);
      CopyZone(dst.fd[i], src.fd[i]);
      CopyZone(dst.bu[i], src.bu[i]);
      CopyZone(dst.bd[i], src.bd[i]);
     }
   dst.nFu = src.nFu;
   dst.nFd = src.nFd;
   dst.nBu = src.nBu;
   dst.nBd = src.nBd;
  }

// Pine L598-604 (barstate.isfirst): visBxs empty entries in FVG_UP / FVG_DN, and in BPR_UP / BPR_DN
// only when i_BPR is on. Every later unshift is paired with a pop, so the sizes never change.
void ResetState(StateS &s, const BfEngineParams &p)
  {
   int i;
   int vis = BfIClamp(p.visBoxes, 1, BF_MAXB);
   for(i = 0; i < BF_MAXB; i++)
     {
      ClearZone(s.fu[i]);
      ClearZone(s.fd[i]);
      ClearZone(s.bu[i]);
      ClearZone(s.bd[i]);
     }
   s.nFu = vis;
   s.nFd = vis;
   s.nBu = p.bpr ? vis : 0;
   s.nBd = p.bpr ? vis : 0;
  }

// Pine array.unshift(new) followed by array.pop().box.delete(): every element moves one slot towards
// the end, the last one is dropped, the new one goes to slot 0. The size is unchanged.
void UnshiftZone(StateS &s, const int kind, const ZoneS &nz)
  {
   int i;
   if(kind == BF_KIND_FU)
     {
      if(s.nFu <= 0)
         return;
      for(i = s.nFu - 1; i > 0; i--)
         CopyZone(s.fu[i], s.fu[i - 1]);
      CopyZone(s.fu[0], nz);
     }
   else
      if(kind == BF_KIND_FD)
        {
         if(s.nFd <= 0)
            return;
         for(i = s.nFd - 1; i > 0; i--)
            CopyZone(s.fd[i], s.fd[i - 1]);
         CopyZone(s.fd[0], nz);
        }
      else
         if(kind == BF_KIND_BU)
           {
            if(s.nBu <= 0)
               return;
            for(i = s.nBu - 1; i > 0; i--)
               CopyZone(s.bu[i], s.bu[i - 1]);
            CopyZone(s.bu[0], nz);
           }
         else
           {
            if(s.nBd <= 0)
               return;
            for(i = s.nBd - 1; i > 0; i--)
               CopyZone(s.bd[i], s.bd[i - 1]);
            CopyZone(s.bd[0], nz);
           }
  }

//+------------------------------------------------------------------+
//| Series computed directly from the price arrays (no state)        |
//| Bar index n is absolute and non-series: 0 = oldest = Pine bar 0. |
//| Any index < 0 is Pine 'na'; every comparison with na is false.   |
//+------------------------------------------------------------------+
// Pine L130 meanBody = ta.sma(body, len): sum of the last len bodies, oldest first, / len.
// na (returns false) while n - len + 1 < 0.
bool MeanBodyAt(const BfEngineParams &p, const int n, const double &op[], const double &cl[], double &mb)
  {
   int k;
   int len = p.length;
   if(len < 1)
      return(false);
   if(n < 0 || n - len + 1 < 0)
      return(false);
   double sum = 0.0;
   for(k = len - 1; k >= 0; k--)
      sum += MathAbs(cl[n - k] - op[n - k]);            // Pine L129 body = |close - open|
   mb = sum / (double)len;
   return(true);
  }

// Pine L548-550: both wicks strictly smaller than 36 % of the body.
bool LBodyAt(const int n, const double &op[], const double &hi[], const double &lo[], const double &cl[])
  {
   double body = MathAbs(cl[n] - op[n]);                // Pine L129
   double mx   = MathMax(cl[n], op[n]);                 // Pine L127
   double mn   = MathMin(cl[n], op[n]);                 // Pine L128
   return((hi[n] - mx < body * BF_PERC_BODY) && (mn - lo[n] < body * BF_PERC_BODY));
  }

// Pine L552 L_bodyUP = body > meanBody and L_body and close > open
bool DispUpAt(const BfEngineParams &p, const int n, const double &op[], const double &hi[], const double &lo[],
              const double &cl[])
  {
   double mb = 0.0;
   if(n < 0)
      return(false);
   if(!MeanBodyAt(p, n, op, cl, mb))
      return(false);                                    // na comparison -> false
   double body = MathAbs(cl[n] - op[n]);
   return((body > mb) && LBodyAt(n, op, hi, lo, cl) && (cl[n] > op[n]));
  }

// Pine L553 L_bodyDN = body > meanBody and L_body and close < open
bool DispDnAt(const BfEngineParams &p, const int n, const double &op[], const double &hi[], const double &lo[],
              const double &cl[])
  {
   double mb = 0.0;
   if(n < 0)
      return(false);
   if(!MeanBodyAt(p, n, op, cl, mb))
      return(false);
   double body = MathAbs(cl[n] - op[n]);
   return((body > mb) && LBodyAt(n, op, hi, lo, cl) && (cl[n] < op[n]));
  }

// Pine L565 imbalanceUP = L_bodyUP[1] and (FVG ? low > high[2] : low < high[2])   (strict)
bool ImbUpAt(const BfEngineParams &p, const int n, const double &op[], const double &hi[], const double &lo[],
             const double &cl[])
  {
   if(n < 2)
      return(false);                                    // high[2] / L_bodyUP[1] na
   if(!DispUpAt(p, n - 1, op, hi, lo, cl))
      return(false);
   if(p.fvgMode == BF_FVGTYPE_FVG)
      return(lo[n] > hi[n - 2]);
   return(lo[n] < hi[n - 2]);
  }

// Pine L566 imbalanceDN = L_bodyDN[1] and (FVG ? high < low[2] : high > low[2])   (strict)
bool ImbDnAt(const BfEngineParams &p, const int n, const double &op[], const double &hi[], const double &lo[],
             const double &cl[])
  {
   if(n < 2)
      return(false);
   if(!DispDnAt(p, n - 1, op, hi, lo, cl))
      return(false);
   if(p.fvgMode == BF_FVGTYPE_FVG)
      return(hi[n] < lo[n - 2]);
   return(hi[n] > lo[n - 2]);
  }

//+------------------------------------------------------------------+
//| Break loops (Pine L700-769)                                      |
//+------------------------------------------------------------------+
// Pine L700-711: one bullish FVG entry. 'p.fvgStyled' stands for Pine's 'not i_BPR' (display only).
void FvgBreakUp(const BfEngineParams &p, ZoneS &z, const int n, const double lowN)
  {
   if(!z.active)
      return;
   z.box.right = n + BF_EXT;                                    // L703
   if(lowN < z.box.top && p.fvgStyled)                          // L704-705
      z.box.border = BF_BORDER_DASHED;
   if(lowN < z.box.bottom)                                      // L706
     {
      if(p.fvgStyled)                                           // L707-709
        {
         z.box.brokenFill = true;
         z.box.border     = BF_BORDER_DOTTED;
        }
      z.box.right = n;                                          // L710
      z.active    = false;                                      // L711
     }
  }

// Pine L713-724: one bearish FVG entry.
void FvgBreakDn(const BfEngineParams &p, ZoneS &z, const int n, const double highN)
  {
   if(!z.active)
      return;
   z.box.right = n + BF_EXT;                                    // L716
   if(highN > z.box.bottom && p.fvgStyled)                      // L717-718
      z.box.border = BF_BORDER_DASHED;
   if(highN > z.box.top)                                        // L719
     {
      if(p.fvgStyled)                                           // L720-722
        {
         z.box.brokenFill = true;
         z.box.border     = BF_BORDER_DOTTED;
        }
      z.box.right = n;                                          // L723
      z.active    = false;                                      // L724
     }
  }

// Pine L727-747 (BPR_UP) and L749-769 (BPR_DN) are identical apart from the break colour,
// which is a rendering matter here.
void BprBreak(ZoneS &z, const int n, const double highN, const double lowN)
  {
   if(!z.active)
      return;
   z.box.right = n + BF_EXT;                                    // L730 / L752
   if(z.posNa)
      return;                                                   // switch on na: no branch
   if(z.pos == -1)                                              // L732-739 / L754-761
     {
      if(highN > z.box.bottom)
         z.box.border = BF_BORDER_DASHED;
      if(highN > z.box.top)
        {
         z.box.brokenFill = true;
         z.box.border     = BF_BORDER_DOTTED;
         z.box.right      = n;
         z.active         = false;
        }
     }
   else
      if(z.pos == 1)                                            // L740-747 / L762-769
        {
         if(lowN < z.box.top)
            z.box.border = BF_BORDER_DASHED;
         if(lowN < z.box.bottom)
           {
            z.box.brokenFill = true;
            z.box.border     = BF_BORDER_DOTTED;
            z.box.right      = n;
            z.active         = false;
           }
        }
   // pos == 0 matches no switch case (cannot happen, QUIRK 5): only right = n + 8 above.
  }

//+------------------------------------------------------------------+
//| One Pine bar (spec s.4 order), Historical mode (per == true).    |
//| Mutates s and reports what happened in ev.                       |
//+------------------------------------------------------------------+
void ProcessBar(const BfEngineParams &p, StateS &s, const int n, const double &o[], const double &h[],
                const double &l[], const double &c[], BfEngineEvents &ev)
  {
   int    i;
   int    last;
   bool   fvgMode = (p.fvgMode == BF_FVGTYPE_FVG);
   bool   imbUp   = ImbUpAt(p, n, o, h, l, c);
   bool   imbDn   = ImbDnAt(p, n, o, h, l, c);
   ZoneS  nz;

   BfClearEngineEvents(ev);

   //--- step 1 (Pine L598-604, barstate.isfirst) is done once by ResetState().

   //--- step 2: bullish FVG (Pine L606-624). Historical mode: per == true.
   if(imbUp && p.showFVG)
     {
      if(ImbUpAt(p, n - 1, o, h, l, c))                         // L607 imbalanceUP[1]
        {
         // L608-609: update the newest entry in place; 'active' untouched.
         // QUIRK 1: FVG geometry even in IFVG mode. QUIRK 2: a broken entry is updated but stays
         // inactive. QUIRK 3: an na entry is a no-op.
         if(s.nFu > 0 && s.fu[0].box.exists)
           {
            s.fu[0].box.left   = n - 2;
            s.fu[0].box.top    = l[n];
            s.fu[0].box.right  = n + BF_EXT;
            s.fu[0].box.bottom = h[n - 2];
            ev.updFvgUp = true;
           }
        }
      else
        {
         // L611-624: new box(left = n-2, top, right = n, bottom), active = true, pos = na; pop oldest.
         ClearZone(nz);
         nz.box.exists = true;
         nz.box.left   = n - 2;
         nz.box.right  = n;
         nz.box.top    = fvgMode ? l[n] : h[n - 2];
         nz.box.bottom = fvgMode ? h[n - 2] : l[n];
         nz.active     = true;
         nz.posNa      = true;
         UnshiftZone(s, BF_KIND_FU, nz);
         if(s.nFu > 0)
            ev.newFvgUp = true;
        }
     }

   //--- step 3: bearish FVG (Pine L626-644)
   if(imbDn && p.showFVG)
     {
      if(ImbDnAt(p, n - 1, o, h, l, c))                         // L627 imbalanceDN[1]
        {
         // L628-629 (QUIRK 1-3 mirrored)
         if(s.nFd > 0 && s.fd[0].box.exists)
           {
            s.fd[0].box.left   = n - 2;
            s.fd[0].box.top    = l[n - 2];
            s.fd[0].box.right  = n + BF_EXT;
            s.fd[0].box.bottom = h[n];
            ev.updFvgDn = true;
           }
        }
      else
        {
         // L631-644
         ClearZone(nz);
         nz.box.exists = true;
         nz.box.left   = n - 2;
         nz.box.right  = n;
         nz.box.top    = fvgMode ? l[n - 2] : h[n];
         nz.box.bottom = fvgMode ? h[n] : l[n - 2];
         nz.active     = true;
         nz.posNa      = true;
         UnshiftZone(s, BF_KIND_FD, nz);
         if(s.nFd > 0)
            ev.newFvgDn = true;
        }
     }

   //--- step 4: Balance Price Range (Pine L647-697). Runs on EVERY bar, BEFORE this bar's FVG break loop
   //    (QUIRK 10). Uses FVG_UP[0] / FVG_DN[0] whether active or broken (QUIRK 9). An na box makes every
   //    comparison false, so both must exist.
   if(p.bpr && s.nFu > 0 && s.nFd > 0 && s.fu[0].box.exists && s.fd[0].box.exists)
     {
      double upBtm = s.fu[0].box.bottom;                        // L650 bxUPbtm
      double dnBtm = s.fd[0].box.bottom;                        // L651 bxDNbtm
      double upTop = s.fu[0].box.top;                           // L652 bxUPtop
      double dnTop = s.fd[0].box.top;                           // L653 bxDNtop
      int    left  = BfIMin(s.fu[0].box.left, s.fd[0].box.left);   // L654
      int    right = BfIMax(s.fu[0].box.right, s.fd[0].box.right); // L655

      // L657-675: BPR_UP (green)
      if(upBtm < dnTop && dnBtm < upBtm)
        {
         if(s.nBu > 0 && s.bu[0].box.exists && left == s.bu[0].box.left)
           {
            // L659-661: same BPR (identity = left edge, QUIRK 6). Geometry kept.
            // The extension is overwritten by the break loop below (QUIRK 8).
            if(s.bu[0].active)
               s.bu[0].box.right = right;
           }
         else
           {
            // L662-675: new BPR box(left, top = dnTop, right, bottom = upBtm) (QUIRK 4)
            ClearZone(nz);
            nz.box.exists = true;
            nz.box.left   = left;
            nz.box.top    = dnTop;
            nz.box.right  = right;
            nz.box.bottom = upBtm;
            nz.active     = true;
            nz.pos        = (c[n] > upBtm) ? 1 : ((c[n] < dnTop) ? -1 : 0);   // L673 (QUIRK 5)
            nz.posNa      = false;
            UnshiftZone(s, BF_KIND_BU, nz);
            if(s.nBu > 0)
               ev.newBprUp = true;
           }
        }

      // L677-697: BPR_DN (red)
      if(dnBtm < upTop && upBtm < dnBtm)
        {
         if(s.nBd > 0 && s.bd[0].box.exists && left == s.bd[0].box.left)
           {
            if(s.bd[0].active)
               s.bd[0].box.right = right;
           }
         else
           {
            ClearZone(nz);
            nz.box.exists = true;
            nz.box.left   = left;
            nz.box.top    = upTop;
            nz.box.right  = right;
            nz.box.bottom = dnBtm;
            nz.active     = true;
            nz.pos        = (c[n] > dnBtm) ? 1 : ((c[n] < upTop) ? -1 : 0);   // L695
            nz.posNa      = false;
            UnshiftZone(s, BF_KIND_BD, nz);
            if(s.nBd > 0)
               ev.newBprDn = true;
           }
        }
     }

   //--- step 5: FVG break loops (Pine L700-724), indices 0 .. min(bxBack, size - 1), active only.
   last = BfIMin(BF_BX_BACK, s.nFu - 1);
   for(i = 0; i <= last; i++)
      FvgBreakUp(p, s.fu[i], n, l[n]);
   last = BfIMin(BF_BX_BACK, s.nFd - 1);
   for(i = 0; i <= last; i++)
      FvgBreakDn(p, s.fd[i], n, h[n]);

   //--- step 6: BPR break loops (Pine L726-769), only when i_BPR.
   if(p.bpr)
     {
      last = BfIMin(BF_BX_BACK, s.nBu - 1);
      for(i = 0; i <= last; i++)
         BprBreak(s.bu[i], n, h[n], l[n]);
      last = BfIMin(BF_BX_BACK, s.nBd - 1);
      for(i = 0; i <= last; i++)
         BprBreak(s.bd[i], n, h[n], l[n]);
     }

   //--- step 7: Fibonacci (Pine L959-1118, barstate.islast) is drawn by the renderer from the shown state.
  }

#endif
//+------------------------------------------------------------------+
