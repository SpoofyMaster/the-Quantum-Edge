//+------------------------------------------------------------------+
//| LuxAlgo_BPR.mq5                                                  |
//| Fair Value Gaps + Balance Price Range (BPR) for MetaTrader 5     |
//+------------------------------------------------------------------+
//
// © LuxAlgo (original Pine v5 logic of 'ICT Concepts [LuxAlgo]')
// Licence: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)
//          https://creativecommons.org/licenses/by-nc-sa/4.0/
//
// This file is a PORT / DERIVATIVE WORK of the FVG, Balance Price Range, displacement and
// "Fibonacci between last: BPR" logic of the Pine v5 script "ICT Concepts [LuxAlgo]".
// It is distributed under the same licence (CC BY-NC-SA 4.0): NON-COMMERCIAL use only, attribution
// to LuxAlgo required, and any redistributed derivative must keep this licence.
// It is not affiliated with or endorsed by LuxAlgo.
// The changes made on purpose versus the original are listed in
// research/indicators/LUXALGO_BPR_SPEC.md, section 10.
//
// "Pine Lnnn" below = line nnn of research/indicators/luxalgo_ict_concepts.pine (unmodified source).
// "spec s.N" / "QUIRK k" = research/indicators/LUXALGO_BPR_SPEC.md.
//
// STATUS: NOT YET COMPILED in MetaEditor (written without a compiler). Send the compiler messages.
//+------------------------------------------------------------------+
#property copyright   "(c) LuxAlgo - original Pine v5 logic; port under CC BY-NC-SA 4.0"
#property link        "https://creativecommons.org/licenses/by-nc-sa/4.0/"
#property version     "1.00"
#property description "Fair Value Gaps + Balance Price Range, ported from 'ICT Concepts [LuxAlgo]' (Pine v5)."
#property description "Licence CC BY-NC-SA 4.0: non-commercial use only. Not affiliated with LuxAlgo."

#property indicator_chart_window
#property indicator_buffers 2
#property indicator_plots   2

//--- plot 0: displacement UP (Pine L1123-1128)
#property indicator_label1  "Displacement UP"
#property indicator_type1   DRAW_ARROW
#property indicator_color1  C'0,230,118'
#property indicator_width1  1
//--- plot 1: displacement DN (Pine L1129-1134)
#property indicator_label2  "Displacement DN"
#property indicator_type2   DRAW_ARROW
#property indicator_color2  C'255,82,82'
#property indicator_width2  1

//+------------------------------------------------------------------+
//| Constants                                                        |
//+------------------------------------------------------------------+
#define LXB_PREFIX        "LXBPR_"
#define LXB_MAXB          20      // max of '# Visible FVG's' (Pine L74 maxval = 20)
#define LXB_PERC_BODY     0.36    // Pine L38 perc_Body
#define LXB_BX_BACK       10      // Pine L39 bxBack
#define LXB_EXT           8       // Pine L609 / L703: right = bar_index + 8
#define LXB_FIB_LEN       50      // Pine L126 plus = 50 (xloc.bar_index)

#define LXB_KIND_FU       0       // bFVG_UP (Pine L238)
#define LXB_KIND_FD       1       // bFVG_DN (Pine L239)
#define LXB_KIND_BU       2       // bBPR_UP (Pine L241)
#define LXB_KIND_BD       3       // bBPR_DN (Pine L242)
#define LXB_NSLOTS        80      // 4 kinds x LXB_MAXB slots (draw cache)

#define LXB_BORDER_SOLID  0
#define LXB_BORDER_DASHED 1
#define LXB_BORDER_DOTTED 2

//+------------------------------------------------------------------+
//| Input enums (declared before use)                                |
//+------------------------------------------------------------------+
enum ENUM_LXB_MODE
  {
   MODE_PRESENT    = 0,   // Present
   MODE_HISTORICAL = 1    // Historical
  };

enum ENUM_LXB_FVGTYPE
  {
   FVG  = 0,              // FVG
   IFVG = 1               // IFVG
  };

enum ENUM_LXB_FIB
  {
   FIB_NONE = 0,          // NONE
   FIB_BPR  = 1           // BPR
  };

//+------------------------------------------------------------------+
//| Inputs                                                           |
//+------------------------------------------------------------------+
input group "Mode"
input ENUM_LXB_MODE    InpMode             = MODE_PRESENT;     // Mode (Pine i_mode)
input int              InpPresentBars      = 500;              // Present mode: bars back from the load-time last bar
input group "Market structure"
input int              InpLength           = 5;                // Length (3..10): period of the body SMA (Pine len)
input group "Displacement"
input bool             InpShowDisplacement = false;            // Show Displacement (Pine sDispl)
input group "Fair Value Gaps"
input bool             InpShowFVG          = true;             // Show FVGs (Pine shwFVG)
input bool             InpBPR              = true;             // Balance Price Range (Pine i_BPR; Pine default false)
input ENUM_LXB_FVGTYPE InpFvgType          = FVG;              // Options: FVG / IFVG (Pine i_FVG)
input int              InpVisibleBoxes     = 2;                // # Visible FVG's (1..20) (Pine visBxs)
input bool             InpShowFVGinBPRmode = false;            // Debug: draw the underlying FVG boxes when BPR is on
input group "Style"
input color            InpBullColor        = C'0,230,118';     // Bullish FVG / BPR colour (Pine cFVGbl)
input color            InpBullBreakColor   = C'128,128,0';     // Bullish break colour (Pine cFVGblBR)
input color            InpBearColor        = C'255,82,82';     // Bearish FVG / BPR colour (Pine cFVGbr)
input color            InpBearBreakColor   = C'255,0,0';       // Bearish break colour (Pine cFVGbrBR)
input int              InpFillTransp       = 90;               // Fill transparency 0..100 (Pine 90)
input int              InpBorderTransp     = 65;               // Border / text transparency 0..100 (Pine 65)
input int              InpBreakTransp      = 95;               // Broken fill transparency 0..100 (Pine 95)
input group "Fibonacci"
input ENUM_LXB_FIB     InpFib              = FIB_NONE;         // Fibonacci between last: (Pine iFib)
input bool             InpFibExtend        = false;            // Extend lines (Pine iExt)
input group "Live / alerts / export"
input bool             InpLiveBar          = true;             // Process forming bar like Pine realtime (repaints until close)
input bool             InpAlertNewBPR      = false;            // Alert on a NEW BPR created on a CLOSED bar (live bars only)
input bool             InpExportCSV        = false;            // Write the parity export file after each full calculation (path in Experts log)

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
   int               border;        // LXB_BORDER_SOLID / _DASHED / _DOTTED
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
   ZoneS             fu[LXB_MAXB];  // bFVG_UP
   ZoneS             fd[LXB_MAXB];  // bFVG_DN
   ZoneS             bu[LXB_MAXB];  // bBPR_UP
   ZoneS             bd[LXB_MAXB];  // bBPR_DN
   int               nFu;
   int               nFd;
   int               nBu;
   int               nBd;
  };

// What was last drawn for one zone slot (to skip unchanged object updates).
struct DrawCacheS
  {
   bool              drawn;
   datetime          t1;
   datetime          t2;
   double            p1;
   double            p2;
   color             fillClr;
   color             lineClr;
   int               style;
   bool              active;
   int               pos;
  };

// What was last drawn for the Fibonacci set.
struct FibCacheS
  {
   bool              drawn;
   datetime          tx1;
   datetime          tx2;
   datetime          trt;
   datetime          tend;
   double            y1;
   double            y2;
   double            f0;
   double            f1;
   color             bg;
  };

//+------------------------------------------------------------------+
//| Globals                                                          |
//+------------------------------------------------------------------+
double     g_bufUp[];                 // plot 0
double     g_bufDn[];                 // plot 1

StateS     g_state;                   // committed state (after the last CLOSED bar)
StateS     g_tmp;                     // throw-away copy used for the forming bar (Pine realtime rollback)

DrawCacheS g_zc[LXB_NSLOTS];
FibCacheS  g_fc;
bool       g_dirty      = false;

int        g_len        = 5;          // clamped InpLength
int        g_vis        = 2;          // clamped InpVisibleBoxes
int        g_presentBars = 500;       // clamped InpPresentBars
int        g_fillT      = 90;
int        g_borderT    = 65;
int        g_breakT     = 95;

int        g_perStart   = 0;          // Present: first bar with per == true (anchored at full recalculation)
int        g_procStart  = 0;          // first bar processed into the committed state
int        g_nextBar    = 0;          // next CLOSED bar to commit
int        g_lastTotal  = 0;          // rates_total at the previous call
datetime   g_firstTime  = 0;          // time of bar 0 at the previous call
bool       g_initDone   = false;      // a full calculation has completed
datetime   g_anchorTime = 0;          // Present: time of the forming bar at the first full calculation after OnInit
datetime   g_lastCommittedTime = 0;   // time of the last committed bar at the end of the previous call (alerts)
datetime   g_lastFormTime = 0;        // time of the forming bar at the previous call (background re-render)
bool       g_lastWasTmp = false;      // the last rendered state was the forming-bar copy
color      g_lastBg     = clrNONE;    // chart background used by the last render

//+------------------------------------------------------------------+
//| Small helpers                                                    |
//+------------------------------------------------------------------+
int IMin(const int a, const int b)
  {
   return((a < b) ? a : b);
  }

int IMax(const int a, const int b)
  {
   return((a > b) ? a : b);
  }

int IClamp(const int v, const int lo_, const int hi_)
  {
   if(v < lo_)
      return(lo_);
   if(v > hi_)
      return(hi_);
   return(v);
  }

//--- MQL5 colour layout is 0x00BBGGRR.
int ColorR(const color c)
  {
   return(((int)c) & 0xFF);
  }

int ColorG(const color c)
  {
   return((((int)c) >> 8) & 0xFF);
  }

int ColorB(const color c)
  {
   return((((int)c) >> 16) & 0xFF);
  }

color MakeColor(const int r, const int g, const int b)
  {
   int rr = IClamp(r, 0, 255);
   int gg = IClamp(g, 0, 255);
   int bb = IClamp(b, 0, 255);
   return((color)((bb << 16) | (gg << 8) | rr));
  }

// Emulates a Pine colour with transparency on an opaque MT5 object (spec s.9):
// shown = (1 - t) * colour + t * background, t = transp / 100.
color BlendColor(const color fg, const int transp, const color bg)
  {
   if(fg == clrNONE)
      return(clrNONE);
   color bgc = bg;
   if(bgc == clrNONE)
      bgc = clrWhite;
   double t  = (double)IClamp(transp, 0, 100) / 100.0;
   double u  = 1.0 - t;
   int    r  = (int)MathRound(u * (double)ColorR(fg) + t * (double)ColorR(bgc));
   int    g  = (int)MathRound(u * (double)ColorG(fg) + t * (double)ColorG(bgc));
   int    b  = (int)MathRound(u * (double)ColorB(fg) + t * (double)ColorB(bgc));
   return(MakeColor(r, g, b));
  }

ENUM_LINE_STYLE BorderToStyle(const int border)
  {
   if(border == LXB_BORDER_DASHED)
      return(STYLE_DASH);
   if(border == LXB_BORDER_DOTTED)
      return(STYLE_DOT);
   return(STYLE_SOLID);
  }

string BorderName(const int border)
  {
   if(border == LXB_BORDER_DASHED)
      return("dashed");
   if(border == LXB_BORDER_DOTTED)
      return("dotted");
   return("solid");
  }

string KindName(const int kind)
  {
   if(kind == LXB_KIND_FU)
      return("FVG_UP");
   if(kind == LXB_KIND_FD)
      return("FVG_DN");
   if(kind == LXB_KIND_BU)
      return("BPR_UP");
   return("BPR_DN");
  }

string FvgTypeName()
  {
   return((InpFvgType == FVG) ? "FVG" : "IFVG");
  }

string ModeName()
  {
   return((InpMode == MODE_PRESENT) ? "Present" : "Historical");
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
   z.box.border     = LXB_BORDER_SOLID;
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
   for(i = 0; i < LXB_MAXB; i++)
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
void ResetState(StateS &s)
  {
   int i;
   for(i = 0; i < LXB_MAXB; i++)
     {
      ClearZone(s.fu[i]);
      ClearZone(s.fd[i]);
      ClearZone(s.bu[i]);
      ClearZone(s.bd[i]);
     }
   s.nFu = g_vis;
   s.nFd = g_vis;
   s.nBu = InpBPR ? g_vis : 0;
   s.nBd = InpBPR ? g_vis : 0;
  }

// Pine array.unshift(new) followed by array.pop().box.delete(): every element moves one slot towards
// the end, the last one is dropped, the new one goes to slot 0. The size is unchanged.
void UnshiftZone(StateS &s, const int kind, const ZoneS &nz)
  {
   int i;
   if(kind == LXB_KIND_FU)
     {
      if(s.nFu <= 0)
         return;
      for(i = s.nFu - 1; i > 0; i--)
         CopyZone(s.fu[i], s.fu[i - 1]);
      CopyZone(s.fu[0], nz);
     }
   else
      if(kind == LXB_KIND_FD)
        {
         if(s.nFd <= 0)
            return;
         for(i = s.nFd - 1; i > 0; i--)
            CopyZone(s.fd[i], s.fd[i - 1]);
         CopyZone(s.fd[0], nz);
        }
      else
         if(kind == LXB_KIND_BU)
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
bool MeanBodyAt(const int n, const double &op[], const double &cl[], double &mb)
  {
   int k;
   if(n < 0 || n - g_len + 1 < 0)
      return(false);
   double sum = 0.0;
   for(k = g_len - 1; k >= 0; k--)
      sum += MathAbs(cl[n - k] - op[n - k]);           // Pine L129 body = |close - open|
   mb = sum / (double)g_len;
   return(true);
  }

// Pine L548-550: both wicks strictly smaller than 36 % of the body.
bool LBodyAt(const int n, const double &op[], const double &hi[], const double &lo[], const double &cl[])
  {
   double body = MathAbs(cl[n] - op[n]);                // Pine L129
   double mx   = MathMax(cl[n], op[n]);                 // Pine L127
   double mn   = MathMin(cl[n], op[n]);                 // Pine L128
   return((hi[n] - mx < body * LXB_PERC_BODY) && (mn - lo[n] < body * LXB_PERC_BODY));
  }

// Pine L552 L_bodyUP = body > meanBody and L_body and close > open
bool DispUpAt(const int n, const double &op[], const double &hi[], const double &lo[], const double &cl[])
  {
   double mb = 0.0;
   if(n < 0)
      return(false);
   if(!MeanBodyAt(n, op, cl, mb))
      return(false);                                    // na comparison -> false
   double body = MathAbs(cl[n] - op[n]);
   return((body > mb) && LBodyAt(n, op, hi, lo, cl) && (cl[n] > op[n]));
  }

// Pine L553 L_bodyDN = body > meanBody and L_body and close < open
bool DispDnAt(const int n, const double &op[], const double &hi[], const double &lo[], const double &cl[])
  {
   double mb = 0.0;
   if(n < 0)
      return(false);
   if(!MeanBodyAt(n, op, cl, mb))
      return(false);
   double body = MathAbs(cl[n] - op[n]);
   return((body > mb) && LBodyAt(n, op, hi, lo, cl) && (cl[n] < op[n]));
  }

// Pine L565 imbalanceUP = L_bodyUP[1] and (FVG ? low > high[2] : low < high[2])   (strict)
bool ImbUpAt(const int n, const double &op[], const double &hi[], const double &lo[], const double &cl[])
  {
   if(n < 2)
      return(false);                                    // high[2] / L_bodyUP[1] na
   if(!DispUpAt(n - 1, op, hi, lo, cl))
      return(false);
   if(InpFvgType == FVG)
      return(lo[n] > hi[n - 2]);
   return(lo[n] < hi[n - 2]);
  }

// Pine L566 imbalanceDN = L_bodyDN[1] and (FVG ? high < low[2] : high > low[2])   (strict)
bool ImbDnAt(const int n, const double &op[], const double &hi[], const double &lo[], const double &cl[])
  {
   if(n < 2)
      return(false);
   if(!DispDnAt(n - 1, op, hi, lo, cl))
      return(false);
   if(InpFvgType == FVG)
      return(hi[n] < lo[n - 2]);
   return(hi[n] > lo[n - 2]);
  }

// Pine L122 per = i_mode == 'Present' ? last_bar_index - bar_index <= 500 : true
// g_perStart = load-time last_bar_index - 500, fixed at each full recalculation (spec s.7).
bool IsPer(const int n)
  {
   if(InpMode == MODE_PRESENT)
      return(n >= g_perStart);
   return(true);
  }

//+------------------------------------------------------------------+
//| Break loops (Pine L700-769)                                      |
//+------------------------------------------------------------------+
// Pine L700-711: one bullish FVG entry.
void FvgBreakUp(ZoneS &z, const int n, const double lowN)
  {
   if(!z.active)
      return;
   z.box.right = n + LXB_EXT;                                   // L703
   if(lowN < z.box.top && !InpBPR)                              // L704-705
      z.box.border = LXB_BORDER_DASHED;
   if(lowN < z.box.bottom)                                      // L706
     {
      if(!InpBPR)                                               // L707-709
        {
         z.box.brokenFill = true;
         z.box.border     = LXB_BORDER_DOTTED;
        }
      z.box.right = n;                                          // L710
      z.active    = false;                                      // L711
     }
  }

// Pine L713-724: one bearish FVG entry.
void FvgBreakDn(ZoneS &z, const int n, const double highN)
  {
   if(!z.active)
      return;
   z.box.right = n + LXB_EXT;                                   // L716
   if(highN > z.box.bottom && !InpBPR)                          // L717-718
      z.box.border = LXB_BORDER_DASHED;
   if(highN > z.box.top)                                        // L719
     {
      if(!InpBPR)                                               // L720-722
        {
         z.box.brokenFill = true;
         z.box.border     = LXB_BORDER_DOTTED;
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
   z.box.right = n + LXB_EXT;                                   // L730 / L752
   if(z.posNa)
      return;                                                   // switch on na: no branch
   if(z.pos == -1)                                              // L732-739 / L754-761
     {
      if(highN > z.box.bottom)
         z.box.border = LXB_BORDER_DASHED;
      if(highN > z.box.top)
        {
         z.box.brokenFill = true;
         z.box.border     = LXB_BORDER_DOTTED;
         z.box.right      = n;
         z.active         = false;
        }
     }
   else
      if(z.pos == 1)                                            // L740-747 / L762-769
        {
         if(lowN < z.box.top)
            z.box.border = LXB_BORDER_DASHED;
         if(lowN < z.box.bottom)
           {
            z.box.brokenFill = true;
            z.box.border     = LXB_BORDER_DOTTED;
            z.box.right      = n;
            z.active         = false;
           }
        }
   // pos == 0 matches no switch case (cannot happen, QUIRK 5): only right = n + 8 above.
  }

//+------------------------------------------------------------------+
//| One Pine bar (spec s.4 order). Mutates s. Reports new BPRs.      |
//+------------------------------------------------------------------+
void ProcessBar(StateS &s, int n, const double &o[], const double &h[], const double &l[], const double &c[],
                bool &newBprUp, bool &newBprDn)
  {
   int    i;
   int    last;
   bool   fvgMode = (InpFvgType == FVG);
   bool   per     = IsPer(n);
   bool   imbUp   = ImbUpAt(n, o, h, l, c);
   bool   imbDn   = ImbDnAt(n, o, h, l, c);
   ZoneS  nz;

   newBprUp = false;
   newBprDn = false;

   //--- step 1 (Pine L598-604, barstate.isfirst) is done once by ResetState().

   //--- step 2: bullish FVG (Pine L606-624)
   if(imbUp && per && InpShowFVG)
     {
      if(ImbUpAt(n - 1, o, h, l, c))                            // L607 imbalanceUP[1]
        {
         // L608-609: update the newest entry in place; 'active' untouched.
         // QUIRK 1: FVG geometry even in IFVG mode. QUIRK 2: a broken entry is updated but stays
         // inactive. QUIRK 3: an na entry (previous gap outside 'per') is a no-op.
         if(s.nFu > 0 && s.fu[0].box.exists)
           {
            s.fu[0].box.left   = n - 2;
            s.fu[0].box.top    = l[n];
            s.fu[0].box.right  = n + LXB_EXT;
            s.fu[0].box.bottom = h[n - 2];
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
         UnshiftZone(s, LXB_KIND_FU, nz);
        }
     }

   //--- step 3: bearish FVG (Pine L626-644)
   if(imbDn && per && InpShowFVG)
     {
      if(ImbDnAt(n - 1, o, h, l, c))                            // L627 imbalanceDN[1]
        {
         // L628-629 (QUIRK 1-3 mirrored)
         if(s.nFd > 0 && s.fd[0].box.exists)
           {
            s.fd[0].box.left   = n - 2;
            s.fd[0].box.top    = l[n - 2];
            s.fd[0].box.right  = n + LXB_EXT;
            s.fd[0].box.bottom = h[n];
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
         UnshiftZone(s, LXB_KIND_FD, nz);
        }
     }

   //--- step 4: Balance Price Range (Pine L647-697). Runs on EVERY bar (not gated by 'per'),
   //    BEFORE this bar's FVG break loop (QUIRK 10). Uses FVG_UP[0] / FVG_DN[0] whether active or
   //    broken (QUIRK 9). An na box makes every comparison false, so both must exist.
   if(InpBPR && s.nFu > 0 && s.nFd > 0 && s.fu[0].box.exists && s.fd[0].box.exists)
     {
      double upBtm = s.fu[0].box.bottom;                        // L650 bxUPbtm
      double dnBtm = s.fd[0].box.bottom;                        // L651 bxDNbtm
      double upTop = s.fu[0].box.top;                           // L652 bxUPtop
      double dnTop = s.fd[0].box.top;                           // L653 bxDNtop
      int    left  = IMin(s.fu[0].box.left, s.fd[0].box.left);   // L654
      int    right = IMax(s.fu[0].box.right, s.fd[0].box.right); // L655

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
            UnshiftZone(s, LXB_KIND_BU, nz);
            if(s.nBu > 0)
               newBprUp = true;
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
            UnshiftZone(s, LXB_KIND_BD, nz);
            if(s.nBd > 0)
               newBprDn = true;
           }
        }
     }

   //--- step 5: FVG break loops (Pine L700-724), indices 0 .. min(bxBack, size - 1), active only.
   last = IMin(LXB_BX_BACK, s.nFu - 1);
   for(i = 0; i <= last; i++)
      FvgBreakUp(s.fu[i], n, l[n]);
   last = IMin(LXB_BX_BACK, s.nFd - 1);
   for(i = 0; i <= last; i++)
      FvgBreakDn(s.fd[i], n, h[n]);

   //--- step 6: BPR break loops (Pine L726-769), only when i_BPR.
   if(InpBPR)
     {
      last = IMin(LXB_BX_BACK, s.nBu - 1);
      for(i = 0; i <= last; i++)
         BprBreak(s.bu[i], n, h[n], l[n]);
      last = IMin(LXB_BX_BACK, s.nBd - 1);
      for(i = 0; i <= last; i++)
         BprBreak(s.bd[i], n, h[n], l[n]);
     }

   //--- step 7: Fibonacci (Pine L959-1118, barstate.islast) is drawn by RenderFib() from the rendered state.
  }

//+------------------------------------------------------------------+
//| Displacement plot value for bar n (Pine L1123-1134)              |
//+------------------------------------------------------------------+
void SetDispl(const int n, const double &o[], const double &h[], const double &l[], const double &c[])
  {
   g_bufUp[n] = EMPTY_VALUE;
   g_bufDn[n] = EMPTY_VALUE;
   if(!InpShowDisplacement || !IsPer(n))
      return;
   if(DispUpAt(n, o, h, l, c))
      g_bufUp[n] = l[n];                                        // plotted below the bar
   if(DispDnAt(n, o, h, l, c))
      g_bufDn[n] = h[n];                                        // plotted above the bar
  }

//+------------------------------------------------------------------+
//| Rendering                                                        |
//+------------------------------------------------------------------+
// Bar index -> time; indices to the right of the last bar are extrapolated with the bar period.
datetime IdxToTime(const int idx, const int rates_total, const datetime &tm[])
  {
   int lastIdx = rates_total - 1;
   if(idx < 0)
      return(tm[0]);
   if(idx <= lastIdx)
      return(tm[idx]);
   long secs = (long)PeriodSeconds();
   return((datetime)((long)tm[lastIdx] + (long)(idx - lastIdx) * secs));
  }

void DeleteZoneObjects(const string baseName)
  {
   ObjectDelete(0, baseName + "_F");
   ObjectDelete(0, baseName + "_B");
   ObjectDelete(0, baseName + "_T");
  }

void LxbDrawRect(const string name, const datetime t1, const double p1, const datetime t2, const double p2,
              const color clr, const bool fill, const bool back, const ENUM_LINE_STYLE style,
              const string tip)
  {
   if(ObjectFind(0, name) < 0)
     {
      if(!ObjectCreate(0, name, OBJ_RECTANGLE, 0, t1, p1, t2, p2))
         return;
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_SELECTED, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
     }
   else
     {
      ObjectMove(0, name, 0, t1, p1);
      ObjectMove(0, name, 1, t2, p2);
     }
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_FILL, fill);
   ObjectSetInteger(0, name, OBJPROP_BACK, back);
   ObjectSetInteger(0, name, OBJPROP_STYLE, style);
   ObjectSetString(0, name, OBJPROP_TOOLTIP, tip);
  }

void LxbDrawText(const string name, const datetime t, const double p, const string txt, const color clr,
              const string tip)
  {
   if(ObjectFind(0, name) < 0)
     {
      if(!ObjectCreate(0, name, OBJ_TEXT, 0, t, p))
         return;
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_SELECTED, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_BACK, false);
      ObjectSetInteger(0, name, OBJPROP_ANCHOR, ANCHOR_CENTER);
      ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 8);
      ObjectSetString(0, name, OBJPROP_FONT, "Arial");
     }
   else
     {
      ObjectMove(0, name, 0, t, p);
     }
   ObjectSetString(0, name, OBJPROP_TEXT, txt);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetString(0, name, OBJPROP_TOOLTIP, tip);
  }

void LxbDrawTrend(const string name, const datetime t1, const double p1, const datetime t2, const double p2,
               const color clr, const ENUM_LINE_STYLE style, const bool rayRight)
  {
   if(ObjectFind(0, name) < 0)
     {
      if(!ObjectCreate(0, name, OBJ_TREND, 0, t1, p1, t2, p2))
         return;
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_SELECTED, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_BACK, false);
      ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
      ObjectSetInteger(0, name, OBJPROP_RAY_LEFT, false);
     }
   else
     {
      ObjectMove(0, name, 0, t1, p1);
      ObjectMove(0, name, 1, t2, p2);
     }
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_STYLE, style);
   ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, rayRight);
  }

void ResetDrawCache()
  {
   int i;
   for(i = 0; i < LXB_NSLOTS; i++)
     {
      g_zc[i].drawn   = false;
      g_zc[i].t1      = 0;
      g_zc[i].t2      = 0;
      g_zc[i].p1      = 0.0;
      g_zc[i].p2      = 0.0;
      g_zc[i].fillClr = clrNONE;
      g_zc[i].lineClr = clrNONE;
      g_zc[i].style   = -1;
      g_zc[i].active  = false;
      g_zc[i].pos     = 0;
     }
   g_fc.drawn = false;
   g_fc.tx1   = 0;
   g_fc.tx2   = 0;
   g_fc.trt   = 0;
   g_fc.tend  = 0;
   g_fc.y1    = 0.0;
   g_fc.y2    = 0.0;
   g_fc.f0    = 0.0;
   g_fc.f1    = 0.0;
   g_fc.bg    = clrNONE;
  }

// One slot of one array: fill rectangle (_F), border rectangle (_B) and centred text (_T).
// Pine colours (L611-622, L662-672, L707-708, L734-736): fill = base @90 (break colour @95 once
// broken), border and text = base @65; border solid -> dashed (price entered) -> dotted (broken).
void RenderSlot(const int kind, const int slot, const bool visible, const ZoneS &z,
                const int rates_total, const datetime &tm[], const color bg)
  {
   int    ci       = kind * LXB_MAXB + slot;
   string baseName = LXB_PREFIX + KindName(kind) + IntegerToString(slot);

   if(!visible || !z.box.exists)
     {
      if(g_zc[ci].drawn)
        {
         DeleteZoneObjects(baseName);
         g_zc[ci].drawn = false;
         g_dirty = true;
        }
      return;
     }

   bool  bull     = (kind == LXB_KIND_FU || kind == LXB_KIND_BU);
   color baseClr  = bull ? InpBullColor : InpBearColor;
   color brkClr   = bull ? InpBullBreakColor : InpBearBreakColor;
   color fillClr  = z.box.brokenFill ? BlendColor(brkClr, g_breakT, bg) : BlendColor(baseClr, g_fillT, bg);
   color lineClr  = BlendColor(baseClr, g_borderT, bg);
   datetime t1    = IdxToTime(z.box.left, rates_total, tm);
   datetime t2    = IdxToTime(z.box.right, rates_total, tm);
   int    posVal  = z.posNa ? 0 : z.pos;

   if(g_zc[ci].drawn && g_zc[ci].t1 == t1 && g_zc[ci].t2 == t2 &&
      g_zc[ci].p1 == z.box.top && g_zc[ci].p2 == z.box.bottom &&
      g_zc[ci].fillClr == fillClr && g_zc[ci].lineClr == lineClr &&
      g_zc[ci].style == z.box.border && g_zc[ci].active == z.active && g_zc[ci].pos == posVal &&
      ObjectFind(0, baseName + "_F") >= 0 && ObjectFind(0, baseName + "_B") >= 0 &&
      ObjectFind(0, baseName + "_T") >= 0)
      return;                                                   // nothing changed and still on the chart

   bool   isBpr = (kind == LXB_KIND_BU || kind == LXB_KIND_BD);
   string txt   = isBpr ? "BPR" : FvgTypeName();
   string tip   = KindName(kind) + " #" + IntegerToString(slot) +
                  " top " + DoubleToString(z.box.top, _Digits) +
                  " bottom " + DoubleToString(z.box.bottom, _Digits) +
                  (z.active ? " active" : " inactive");
   if(!z.posNa)
      tip = tip + " pos " + IntegerToString(z.pos);

   LxbDrawRect(baseName + "_F", t1, z.box.top, t2, z.box.bottom, fillClr, true, true, STYLE_SOLID, tip);
   LxbDrawRect(baseName + "_B", t1, z.box.top, t2, z.box.bottom, lineClr, false, false,
            BorderToStyle(z.box.border), tip);
   // Pine centres box text in bar-index space (xloc.bar_index), so a weekend or session gap inside the box
   // does not pull the label off-centre.
   datetime tc = IdxToTime((z.box.left + z.box.right) / 2, rates_total, tm);
   if(((z.box.left + z.box.right) % 2) != 0)
      tc = (datetime)((long)tc + (long)(PeriodSeconds() / 2));
   LxbDrawText(baseName + "_T", tc, (z.box.top + z.box.bottom) / 2.0, txt, lineClr, tip);

   g_zc[ci].drawn   = true;
   g_zc[ci].t1      = t1;
   g_zc[ci].t2      = t2;
   g_zc[ci].p1      = z.box.top;
   g_zc[ci].p2      = z.box.bottom;
   g_zc[ci].fillClr = fillClr;
   g_zc[ci].lineClr = lineClr;
   g_zc[ci].style   = z.box.border;
   g_zc[ci].active  = z.active;
   g_zc[ci].pos     = posVal;
   g_dirty = true;
  }

void DeleteFibObjects()
  {
   ObjectDelete(0, LXB_PREFIX + "FIB_DIAG");
   ObjectDelete(0, LXB_PREFIX + "FIB_VERT");
   ObjectDelete(0, LXB_PREFIX + "FIB_0");
   ObjectDelete(0, LXB_PREFIX + "FIB_0236");
   ObjectDelete(0, LXB_PREFIX + "FIB_0382");
   ObjectDelete(0, LXB_PREFIX + "FIB_0500");
   ObjectDelete(0, LXB_PREFIX + "FIB_0618");
   ObjectDelete(0, LXB_PREFIX + "FIB_0786");
   ObjectDelete(0, LXB_PREFIX + "FIB_1");
   ObjectDelete(0, LXB_PREFIX + "FIB_1618");
  }

// Fibonacci between the last BPR up and the last BPR down (Pine L976-989, L1093-1118; spec s.8).
// Pine line definitions L251-260: diag silver@50 dashed, vert silver@50 dotted, levels solid,
// 0 / 1 silver@5, 0.236 / 0.786 orange@25, 0.382 / 0.618 / 1.618 yellow@25, 0.5 green@25.
// Only the 8 level lines take 'Extend lines' (extend=ext).
void RenderFib(const StateS &s, const int rates_total, const datetime &tm[], const color bg)
  {
   bool ok = (InpFib == FIB_BPR && InpBPR && s.nBu > 0 && s.nBd > 0 &&
              s.bu[0].box.exists && s.bd[0].box.exists);       // an na box makes every Pine line na
   if(!ok)
     {
      if(g_fc.drawn)
        {
         DeleteFibObjects();
         g_fc.drawn = false;
         g_dirty = true;
        }
      return;
     }

   bool   dnFirst = (s.bu[0].box.left > s.bd[0].box.left);          // L980
   bool   dnBottm = (s.bu[0].box.top > s.bd[0].box.top);            // L981
   int    x1      = dnFirst ? s.bd[0].box.left : s.bu[0].box.left;  // L982
   int    x2      = dnFirst ? s.bu[0].box.right : s.bd[0].box.right; // L983
   double y1;
   double y2;
   if(dnFirst)                                                     // L984-986
      y1 = dnBottm ? s.bd[0].box.bottom : s.bd[0].box.top;
   else
      y1 = dnBottm ? s.bu[0].box.top : s.bu[0].box.bottom;
   if(dnFirst)                                                     // L987-989
      y2 = dnBottm ? s.bu[0].box.top : s.bu[0].box.bottom;
   else
      y2 = dnBottm ? s.bd[0].box.bottom : s.bd[0].box.top;

   int    rt  = IMax(x1, x2);                                       // L1094
   double f0  = (rt == x1) ? y1 : y2;                               // L1098 _0
   double f1  = (rt == x1) ? y2 : y1;                               // L1099 _1
   double df  = f1 - f0;                                            // L1101

   datetime tx1  = IdxToTime(x1, rates_total, tm);
   datetime tx2  = IdxToTime(x2, rates_total, tm);
   datetime trt  = IdxToTime(rt, rates_total, tm);
   datetime tend = IdxToTime(rt + LXB_FIB_LEN, rates_total, tm);    // rt + plus

   if(g_fc.drawn && g_fc.tx1 == tx1 && g_fc.tx2 == tx2 && g_fc.trt == trt && g_fc.tend == tend &&
      g_fc.y1 == y1 && g_fc.y2 == y2 && g_fc.f0 == f0 && g_fc.f1 == f1 && g_fc.bg == bg &&
      ObjectFind(0, LXB_PREFIX + "FIB_0") >= 0 && ObjectFind(0, LXB_PREFIX + "FIB_DIAG") >= 0)
      return;

   color silver50 = BlendColor(C'178,181,190', 50, bg);
   color silver05 = BlendColor(C'178,181,190', 5, bg);
   color orange25 = BlendColor(C'255,152,0', 25, bg);
   color yellow25 = BlendColor(C'255,235,59', 25, bg);
   color green25  = BlendColor(C'76,175,80', 25, bg);
   bool  ext      = InpFibExtend;

   LxbDrawTrend(LXB_PREFIX + "FIB_DIAG", tx1, y1, tx2, y2, silver50, STYLE_DASH, false);                  // L1109
   LxbDrawTrend(LXB_PREFIX + "FIB_VERT", trt, f0, trt, f0 + df * 1.618, silver50, STYLE_DOT, false);      // L1110
   LxbDrawTrend(LXB_PREFIX + "FIB_0",    trt, f0, tend, f0, silver05, STYLE_SOLID, ext);                  // L1111
   LxbDrawTrend(LXB_PREFIX + "FIB_0236", trt, f0 + df * 0.236, tend, f0 + df * 0.236, orange25, STYLE_SOLID, ext); // L1112
   LxbDrawTrend(LXB_PREFIX + "FIB_0382", trt, f0 + df * 0.382, tend, f0 + df * 0.382, yellow25, STYLE_SOLID, ext); // L1113
   LxbDrawTrend(LXB_PREFIX + "FIB_0500", trt, f0 + df * 0.500, tend, f0 + df * 0.500, green25, STYLE_SOLID, ext);  // L1114
   LxbDrawTrend(LXB_PREFIX + "FIB_0618", trt, f0 + df * 0.618, tend, f0 + df * 0.618, yellow25, STYLE_SOLID, ext); // L1115
   LxbDrawTrend(LXB_PREFIX + "FIB_0786", trt, f0 + df * 0.786, tend, f0 + df * 0.786, orange25, STYLE_SOLID, ext); // L1116
   LxbDrawTrend(LXB_PREFIX + "FIB_1",    trt, f1, tend, f1, silver05, STYLE_SOLID, ext);                  // L1117
   LxbDrawTrend(LXB_PREFIX + "FIB_1618", trt, f0 + df * 1.618, tend, f0 + df * 1.618, yellow25, STYLE_SOLID, ext); // L1118

   g_fc.drawn = true;
   g_fc.tx1   = tx1;
   g_fc.tx2   = tx2;
   g_fc.trt   = trt;
   g_fc.tend  = tend;
   g_fc.y1    = y1;
   g_fc.y2    = y2;
   g_fc.f0    = f0;
   g_fc.f1    = f1;
   g_fc.bg    = bg;
   g_dirty = true;
  }

// Draws one state. Pine BPR mode: FVG boxes have na colours (invisible) but still drive the BPR;
// the debug input shows them anyway.
void RenderState(const StateS &s, const int rates_total, const datetime &tm[])
  {
   int   i;
   color bg       = (color)ChartGetInteger(0, CHART_COLOR_BACKGROUND);
   bool  showFvg  = (!InpBPR || InpShowFVGinBPRmode);
   g_lastBg       = bg;
   bool  showBpr  = InpBPR;

   for(i = 0; i < LXB_MAXB; i++)
     {
      RenderSlot(LXB_KIND_FU, i, showFvg && (i < s.nFu), s.fu[i], rates_total, tm, bg);
      RenderSlot(LXB_KIND_FD, i, showFvg && (i < s.nFd), s.fd[i], rates_total, tm, bg);
      RenderSlot(LXB_KIND_BU, i, showBpr && (i < s.nBu), s.bu[i], rates_total, tm, bg);
      RenderSlot(LXB_KIND_BD, i, showBpr && (i < s.nBd), s.bd[i], rates_total, tm, bg);
     }
   RenderFib(s, rates_total, tm, bg);

   if(g_dirty)
     {
      ChartRedraw(0);
      g_dirty = false;
     }
  }

//+------------------------------------------------------------------+
//| Parity export (format "# LuxAlgo_BPR export v1")                 |
//+------------------------------------------------------------------+
string Num17(const double v)
  {
   return(StringFormat("%.17g", v));
  }

string ExportFileName()
  {
   string sym = _Symbol;
   StringReplace(sym, "/", "_");
   StringReplace(sym, "\\", "_");
   StringReplace(sym, ":", "_");
   StringReplace(sym, "*", "_");
   StringReplace(sym, "?", "_");
   StringReplace(sym, "\"", "_");
   StringReplace(sym, "<", "_");
   StringReplace(sym, ">", "_");
   StringReplace(sym, "|", "_");
   string tf = EnumToString(_Period);                        // e.g. "PERIOD_M1"
   if(StringFind(tf, "PERIOD_") == 0)
      tf = StringSubstr(tf, 7);
   return("LuxAlgo_BPR_" + sym + "_" + tf + "_" + ModeName() + ".csv");
  }

string ZoneLine(const int kind, const int slot, const int count, const ZoneS &z)
  {
   string line = "ZONE," + KindName(kind) + "," + IntegerToString(slot) + ",";
   // Empty slot (Pine box(na)): geometry NA, active 0, pos NA, border solid, broken_fill 0.
   if(slot >= count || !z.box.exists)
      return(line + "0,NA,NA,NA,NA,0,NA,solid,0");
   string posStr = "NA";
   if(!z.posNa)
      posStr = IntegerToString(z.pos);
   string actStr = "0";
   if(z.active)
      actStr = "1";
   string brkStr = "0";
   if(z.box.brokenFill)
      brkStr = "1";
   line = line + "1," + IntegerToString(z.box.left) + "," + Num17(z.box.top) + "," +
          IntegerToString(z.box.right) + "," + Num17(z.box.bottom) + "," +
          actStr + "," + posStr + "," + BorderName(z.box.border) + "," + brkStr;
   return(line);
  }

// Writes the committed state after bar rates_total-2 plus the bars needed to recompute it.
void WriteExport(const int rates_total, const datetime &tm[], const double &o[], const double &h[],
                 const double &l[], const double &c[])
  {
   int    i;
   int    lastCommitted = rates_total - 2;
   int    firstIdx      = 0;
   string perStr        = "NA";
   if(InpMode == MODE_PRESENT)
     {
      firstIdx = IMax(0, g_perStart - g_len - 3);
      perStr   = IntegerToString(g_perStart);
     }
   if(lastCommitted < firstIdx)
      return;

   string fname = ExportFileName();
   int    fh    = FileOpen(fname, FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(fh == INVALID_HANDLE)
     {
      Print("LuxAlgo_BPR: cannot open export file ", fname, " error ", GetLastError());
      return;
     }

   FileWriteString(fh, "# LuxAlgo_BPR export v1\n");
   FileWriteString(fh, "PARAMS," + ModeName() + "," + IntegerToString(g_presentBars) + "," +
                   IntegerToString(g_len) + "," + (InpShowFVG ? "1" : "0") + "," +
                   (InpBPR ? "1" : "0") + "," + FvgTypeName() + "," + IntegerToString(g_vis) + "," +
                   perStr + "," + IntegerToString(firstIdx) + "," + IntegerToString(lastCommitted) + "\n");
   for(i = firstIdx; i <= lastCommitted; i++)
     {
      FileWriteString(fh, "BAR," + IntegerToString(i) + "," + IntegerToString((long)tm[i]) + "," +
                      Num17(o[i]) + "," + Num17(h[i]) + "," + Num17(l[i]) + "," + Num17(c[i]) + "\n");
     }
   // One ZONE line per existing array slot, as in Pine: FVG arrays hold visBxs entries; the BPR arrays hold
   // visBxs entries when BPR is on and none when it is off (Pine L598-604).
   for(i = 0; i < g_state.nFu; i++)
      FileWriteString(fh, ZoneLine(LXB_KIND_FU, i, g_state.nFu, g_state.fu[i]) + "\n");
   for(i = 0; i < g_state.nFd; i++)
      FileWriteString(fh, ZoneLine(LXB_KIND_FD, i, g_state.nFd, g_state.fd[i]) + "\n");
   for(i = 0; i < g_state.nBu; i++)
      FileWriteString(fh, ZoneLine(LXB_KIND_BU, i, g_state.nBu, g_state.bu[i]) + "\n");
   for(i = 0; i < g_state.nBd; i++)
      FileWriteString(fh, ZoneLine(LXB_KIND_BD, i, g_state.nBd, g_state.bd[i]) + "\n");
   FileClose(fh);
   // FileOpen writes to the sandbox of the running program: <data folder>\MQL5\Files, or the agent's folder
   // in the Strategy Tester. TERMINAL_DATA_PATH resolves to the right one in both cases.
   Print("LuxAlgo_BPR: parity export written to ", TerminalInfoString(TERMINAL_DATA_PATH), "\\MQL5\\Files\\",
         fname, " (bars ", firstIdx, "..", lastCommitted, ")");
  }

//+------------------------------------------------------------------+
//| Alert                                                            |
//+------------------------------------------------------------------+
void AlertNewBpr(const StateS &s, const bool up, const int n, const datetime &tm[])
  {
   string what;
   double top;
   double bottom;
   int    pos;
   bool   active;
   if(up)
     {
      what = "BPR UP (bullish)";
      top = s.bu[0].box.top;
      bottom = s.bu[0].box.bottom;
      pos = s.bu[0].pos;
      active = s.bu[0].active;
     }
   else
     {
      what = "BPR DN (bearish)";
      top = s.bd[0].box.top;
      bottom = s.bd[0].box.bottom;
      pos = s.bd[0].pos;
      active = s.bd[0].active;
     }
   string msg = "LuxAlgo BPR " + _Symbol + " " + StringSubstr(EnumToString(_Period), 7) + ": new " + what +
                " on bar " + TimeToString(tm[n], TIME_DATE | TIME_MINUTES) +
                " zone " + DoubleToString(bottom, _Digits) + " - " + DoubleToString(top, _Digits) +
                " pos " + IntegerToString(pos) + (active ? "" : " (already broken on its creation bar)");
   Alert(msg);
  }

// A committed bar alerts only if it closed after the previous OnCalculate call and is recent. This suppresses
// alerts for history (first calculation after OnInit), for bars back-filled after an outage, and for Friday's
// last bar that is only committed by Monday's first tick. It applies to full and incremental calculations alike.
bool AlertFresh(const int n, const datetime &tm[])
  {
   if(g_lastCommittedTime == 0)
      return(false);
   if(tm[n] <= g_lastCommittedTime)
      return(false);
   return((long)tm[n] >= (long)TimeCurrent() - 2 * (long)PeriodSeconds());
  }

void AlertsForBar(const int n, const bool du, const bool dd, const datetime &tm[])
  {
   if(!InpAlertNewBPR || !InpBPR || !AlertFresh(n, tm))
      return;
   if(du)
      AlertNewBpr(g_state, true, n, tm);
   if(dd)
      AlertNewBpr(g_state, false, n, tm);
  }
// Last index i with tm[i] <= t (tm ascending); -1 if t is before the first bar.
int FindTimeIndex(const datetime &tm[], const int rates_total, const datetime t)
  {
   int lo_ = 0;
   int hi_ = rates_total - 1;
   if(rates_total <= 0 || tm[0] > t)
      return(-1);
   while(lo_ < hi_)
     {
      int mid = (lo_ + hi_ + 1) / 2;
      if(tm[mid] <= t)
         lo_ = mid;
      else
         hi_ = mid - 1;
     }
   return(lo_);
  }

//+------------------------------------------------------------------+
//| Indicator lifecycle                                              |
//+------------------------------------------------------------------+
int OnInit()
  {
   g_len         = IClamp(InpLength, 3, 10);
   g_vis         = IClamp(InpVisibleBoxes, 1, LXB_MAXB);
   g_presentBars = IMax(0, InpPresentBars);
   g_fillT       = IClamp(InpFillTransp, 0, 100);
   g_borderT     = IClamp(InpBorderTransp, 0, 100);
   g_breakT      = IClamp(InpBreakTransp, 0, 100);

   SetIndexBuffer(0, g_bufUp, INDICATOR_DATA);
   SetIndexBuffer(1, g_bufDn, INDICATOR_DATA);
   ArraySetAsSeries(g_bufUp, false);
   ArraySetAsSeries(g_bufDn, false);
   PlotIndexSetInteger(0, PLOT_ARROW, 233);
   PlotIndexSetInteger(1, PLOT_ARROW, 234);
   PlotIndexSetInteger(0, PLOT_ARROW_SHIFT, 10);
   PlotIndexSetInteger(1, PLOT_ARROW_SHIFT, -10);
   PlotIndexSetDouble(0, PLOT_EMPTY_VALUE, EMPTY_VALUE);
   PlotIndexSetDouble(1, PLOT_EMPTY_VALUE, EMPTY_VALUE);

   IndicatorSetString(INDICATOR_SHORTNAME, "LuxAlgo BPR (" + ModeName() + "," + IntegerToString(g_len) + "," +
                      FvgTypeName() + "," + IntegerToString(g_vis) + (InpBPR ? ",BPR" : ",FVG only") + ")");
   IndicatorSetInteger(INDICATOR_DIGITS, _Digits);

   ObjectsDeleteAll(0, LXB_PREFIX);
   ResetDrawCache();
   ResetState(g_state);
   ResetState(g_tmp);
   g_dirty     = false;
   g_perStart  = 0;
   g_procStart = 0;
   g_nextBar   = 0;
   g_lastTotal = 0;
   g_firstTime = 0;
   g_initDone  = false;
   g_anchorTime = 0;
   g_lastCommittedTime = 0;
   g_lastFormTime = 0;
   g_lastWasTmp = false;
   g_lastBg    = clrNONE;
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   ObjectsDeleteAll(0, LXB_PREFIX);
   ChartRedraw(0);
  }

// The fill colours are blended with the chart background. When the user changes the background, re-render
// the last state at once instead of waiting for the next tick (which can be days away on a closed market).
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
  {
   if(id != CHARTEVENT_CHART_CHANGE || !g_initDone || g_lastTotal < 3)
      return;
   color bg = (color)ChartGetInteger(0, CHART_COLOR_BACKGROUND);
   if(bg == g_lastBg)
      return;
   datetime t[];
   ArraySetAsSeries(t, false);
   if(CopyTime(_Symbol, _Period, 0, g_lastTotal, t) != g_lastTotal)
      return;                                                   // data not ready: the next tick redraws
   if(t[g_lastTotal - 1] != g_lastFormTime)
      return;                                                   // a new bar arrived: the next tick redraws
   if(g_lastWasTmp)
      RenderState(g_tmp, g_lastTotal, t);
   else
      RenderState(g_state, g_lastTotal, t);
  }

//+------------------------------------------------------------------+
//| OnCalculate                                                      |
//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &tm[],
                const double &op[],
                const double &hi[],
                const double &lo[],
                const double &cl[],
                const long &tickVol[],
                const long &realVol[],
                const int &spr[])
  {
   int  n;
   bool du = false;
   bool dd = false;

   if(rates_total < 3)
      return(0);

   ArraySetAsSeries(tm, false);
   ArraySetAsSeries(op, false);
   ArraySetAsSeries(hi, false);
   ArraySetAsSeries(lo, false);
   ArraySetAsSeries(cl, false);
   ArraySetAsSeries(g_bufUp, false);
   ArraySetAsSeries(g_bufDn, false);

   int formingBar = rates_total - 1;
   int lastClosed = rates_total - 2;

   bool full = (!g_initDone || prev_calculated == 0 || tm[0] != g_firstTime || rates_total < g_lastTotal);

   if(full)
     {
      //--- FULL recalculation: new history, history shifted (bar 0 changed) or first call.
      // Pine last_bar_index is fixed at load: anchor the Present window now (spec s.7).
      ResetState(g_state);
      // Anchor by TIME, not by index: the first full calculation after OnInit fixes the forming bar's time
      // (Pine last_bar_index at load). Later full recalculations (older history loaded by scrolling back, a
      // resync after a reconnect, Max-bars trimming) find that bar again, so the window does not move.
      // Re-anchoring happens only in OnInit: attach, input change or timeframe change, like a TradingView reload.
      int anchorIdx = formingBar;
      if(g_anchorTime == 0)
         g_anchorTime = tm[formingBar];
      else
         anchorIdx = FindTimeIndex(tm, rates_total, g_anchorTime);
      g_perStart  = anchorIdx - g_presentBars;
      // Present mode starts at max(0, g_perStart). This is exact, not an approximation:
      // for n < g_perStart, per(n) is false, so steps 2-3 (the only writers of FVG entries) are
      // skipped and FVG_UP / FVG_DN keep only the na entries of barstate.isfirst. Step 4 needs both
      // FVG_UP[0] and FVG_DN[0] to be non-na (an na comparison is false), so no BPR is created.
      // Steps 5-6 touch active entries only, and there are none. Hence the state on entry to bar
      // g_perStart equals the initial state. The series ProcessBar reads (body, meanBody,
      // imbalance at n and n-1) come from the price arrays, not from the state, so they are
      // unaffected; the displacement plot is gated by per(n) and is empty before the window too.
      g_procStart = (InpMode == MODE_PRESENT) ? IMax(0, g_perStart) : 0;

      ArrayInitialize(g_bufUp, EMPTY_VALUE);
      ArrayInitialize(g_bufDn, EMPTY_VALUE);

      for(n = g_procStart; n <= lastClosed; n++)
        {
         ProcessBar(g_state, n, op, hi, lo, cl, du, dd);
         SetDispl(n, op, hi, lo, cl);
         AlertsForBar(n, du, dd, tm);                           // only bars that closed since the last call
        }
      g_nextBar   = IMax(g_procStart, formingBar);
      g_firstTime = tm[0];
      g_initDone  = true;

      ObjectsDeleteAll(0, LXB_PREFIX);
      ResetDrawCache();
      g_dirty = true;

      // Parity export: rewritten after every full calculation, so it always matches the history on the chart
      // (the first pass can run on a partial history that MT5 completes later).
      if(InpExportCSV)
         WriteExport(rates_total, tm, op, hi, lo, cl);
     }
   else
     {
      //--- INCREMENTAL: commit the bars that closed since the previous call.
      for(n = g_nextBar; n <= lastClosed; n++)
        {
         ProcessBar(g_state, n, op, hi, lo, cl, du, dd);
         SetDispl(n, op, hi, lo, cl);
         AlertsForBar(n, du, dd, tm);
        }
      if(formingBar > g_nextBar)
         g_nextBar = formingBar;
     }
   g_lastTotal = rates_total;
   g_lastFormTime = tm[formingBar];
   if(lastClosed >= 0)
      g_lastCommittedTime = tm[lastClosed];

   //--- forming bar: Pine realtime rollback = run it on a copy of the committed state (spec s.7).
   if(InpLiveBar && formingBar >= g_procStart)
     {
      CopyState(g_tmp, g_state);
      ProcessBar(g_tmp, formingBar, op, hi, lo, cl, du, dd);
      SetDispl(formingBar, op, hi, lo, cl);
      g_lastWasTmp = true;
      RenderState(g_tmp, rates_total, tm);
     }
   else
     {
      g_bufUp[formingBar] = EMPTY_VALUE;
      g_bufDn[formingBar] = EMPTY_VALUE;
      g_lastWasTmp = false;
      RenderState(g_state, rates_total, tm);
     }

   return(rates_total);
  }
//+------------------------------------------------------------------+
