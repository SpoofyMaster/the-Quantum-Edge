//+------------------------------------------------------------------+
//| BfRender.mqh                                                     |
//| BprFvgEA v2: chart objects - LuxAlgo zones, displacement markers,|
//| Fibonacci, per-setup drawings and the panel (v2 spec s.8)        |
//+------------------------------------------------------------------+
//
// © LuxAlgo (original Pine v5 logic of 'ICT Concepts [LuxAlgo]')
// Licence: Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)
//          https://creativecommons.org/licenses/by-nc-sa/4.0/
//
// The zone, colour-blend and Fibonacci drawing below is a PORT / DERIVATIVE WORK of the FVG, Balance Price Range and
// "Fibonacci between last: BPR" display of the Pine v5 script "ICT Concepts [LuxAlgo]", adapted from
// mql5/Indicators/LuxAlgo_BPR/LuxAlgo_BPR.mq5. It is distributed under the same licence (CC BY-NC-SA 4.0):
// NON-COMMERCIAL use only, attribution to LuxAlgo required, share-alike. Not affiliated with or endorsed by LuxAlgo.
// The per-setup drawings (touch / breakout marks, the setup Fibonacci, entry / SL / TP lines) and the panel are this
// project's own.
//
// Differences from the indicator's renderer (all display-only):
//   * object prefix "BFEA_";
//   * times come from the EA's own bar-time array; indices to the right of the last closed bar use the forming
//     bar's time and then extrapolate with PeriodSeconds();
//   * displacement markers are OBJ_ARROW_UP / OBJ_ARROW_DOWN objects on the last N bars (an EA has no plot buffers).
// "Pine Lnnn" = line nnn of research/indicators/luxalgo_ict_concepts.pine.
//+------------------------------------------------------------------+
#ifndef BF_RENDER_MQH
#define BF_RENDER_MQH

#include "BfDefines.mqh"
#include "BfEngine.mqh"

#define BF_PREFIX         "BFEA_"
#define BF_NSLOTS         80      // 4 kinds x BF_MAXB slots (draw cache)
#define BF_SK_KEEP        40      // setups whose drawings stay on the chart (v2 spec s.8)
#define BF_SK_BARS        15      // Fibonacci lines run this many bars past the leg extreme / decision
#define BF_PANEL_ROWS     12

//+------------------------------------------------------------------+
//| Colour helpers (MQL5 colour layout is 0x00BBGGRR)                |
//+------------------------------------------------------------------+
int BfColorR(const color c)
  {
   return(((int)c) & 0xFF);
  }

int BfColorG(const color c)
  {
   return((((int)c) >> 8) & 0xFF);
  }

int BfColorB(const color c)
  {
   return((((int)c) >> 16) & 0xFF);
  }

color BfMakeColor(const int r, const int g, const int b)
  {
   int rr = BfIClamp(r, 0, 255);
   int gg = BfIClamp(g, 0, 255);
   int bb = BfIClamp(b, 0, 255);
   return((color)((bb << 16) | (gg << 8) | rr));
  }

// Emulates a Pine colour with transparency on an opaque MT5 object (LUXALGO_BPR_SPEC.md s.9):
// shown = (1 - t) * colour + t * background, t = transp / 100.
color BfBlendColor(const color fg, const int transp, const color bg)
  {
   if(fg == clrNONE)
      return(clrNONE);
   color bgc = bg;
   if(bgc == clrNONE)
      bgc = clrWhite;
   double t = (double)BfIClamp(transp, 0, 100) / 100.0;
   double u = 1.0 - t;
   int    r = (int)MathRound(u * (double)BfColorR(fg) + t * (double)BfColorR(bgc));
   int    g = (int)MathRound(u * (double)BfColorG(fg) + t * (double)BfColorG(bgc));
   int    b = (int)MathRound(u * (double)BfColorB(fg) + t * (double)BfColorB(bgc));
   return(BfMakeColor(r, g, b));
  }

ENUM_LINE_STYLE BfBorderToStyle(const int border)
  {
   if(border == BF_BORDER_DASHED)
      return(STYLE_DASH);
   if(border == BF_BORDER_DOTTED)
      return(STYLE_DOT);
   return(STYLE_SOLID);
  }

string BfKindName(const int kind)
  {
   if(kind == BF_KIND_FU)
      return("FVG_UP");
   if(kind == BF_KIND_FD)
      return("FVG_DN");
   if(kind == BF_KIND_BU)
      return("BPR_UP");
   return("BPR_DN");
  }

//+------------------------------------------------------------------+
//| Draw caches                                                      |
//+------------------------------------------------------------------+
// What was last drawn for one zone slot (to skip unchanged object updates).
struct BfDrawCache
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
struct BfFibCache
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
//| Object primitives                                                |
//+------------------------------------------------------------------+
void BfDrawRect(const string name, const datetime t1, const double p1, const datetime t2, const double p2,
                const color clr, const bool fill, const bool back, const ENUM_LINE_STYLE style, const string tip)
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

void BfDrawText(const string name, const datetime t, const double p, const string txt, const color clr,
                const string tip, const ENUM_ANCHOR_POINT anchor)
  {
   if(ObjectFind(0, name) < 0)
     {
      if(!ObjectCreate(0, name, OBJ_TEXT, 0, t, p))
         return;
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_SELECTED, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_BACK, false);
      ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 8);
      ObjectSetString(0, name, OBJPROP_FONT, "Arial");
     }
   else
     {
      ObjectMove(0, name, 0, t, p);
     }
   ObjectSetInteger(0, name, OBJPROP_ANCHOR, anchor);
   ObjectSetString(0, name, OBJPROP_TEXT, txt);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetString(0, name, OBJPROP_TOOLTIP, tip);
  }

void BfDrawTrend(const string name, const datetime t1, const double p1, const datetime t2, const double p2,
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

void BfDrawArrow(const string name, const ENUM_OBJECT kind, const datetime t, const double p, const color clr,
                 const ENUM_ARROW_ANCHOR anchor, const string tip)
  {
   if(ObjectFind(0, name) < 0)
     {
      if(!ObjectCreate(0, name, kind, 0, t, p))
         return;
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_SELECTED, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_BACK, false);
      ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
     }
   else
     {
      ObjectMove(0, name, 0, t, p);
     }
   ObjectSetInteger(0, name, OBJPROP_ANCHOR, anchor);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetString(0, name, OBJPROP_TOOLTIP, tip);
  }

//+------------------------------------------------------------------+
//| Renderer                                                         |
//+------------------------------------------------------------------+
class CBfRender
  {
private:
   bool              m_showZones;
   bool              m_showBpr;         // BPR boxes shown (InpShowBPR); false = FVG boxes shown
   bool              m_fvgDebug;        // also show FVG boxes in BPR mode
   bool              m_fibOn;
   bool              m_fibExt;
   bool              m_showDispl;
   bool              m_showSetups;
   bool              m_showPanel;
   color             m_bull;
   color             m_bullBrk;
   color             m_bear;
   color             m_bearBrk;
   int               m_fillT;
   int               m_borderT;
   int               m_breakT;
   string            m_fvgText;         // "FVG" or "IFVG"
   int               m_digits;
   BfDrawCache       m_zc[BF_NSLOTS];
   BfFibCache        m_fc;
   bool              m_dirty;
   color             m_lastBg;
   int               m_skIds[BF_SK_KEEP];
   int               m_skCount;
   string            m_panel[BF_PANEL_ROWS];
   string            m_panelShown[BF_PANEL_ROWS];

public:
   // Bar index -> time. tm[0..count-1] are the closed bars; index 'count' is the forming bar (time formTime
   // when known); later indices are extrapolated with the bar period.
   datetime          IdxToTime(const int idx, const int count, const datetime &tm[], const datetime formTime)
     {
      long secs = (long)PeriodSeconds();
      if(count <= 0)
         return((datetime)((long)formTime + (long)BfIMax(idx, 0) * secs));
      if(idx < 0)
         return(tm[0]);
      if(idx < count)
         return(tm[idx]);
      if((long)formTime > (long)tm[count - 1])
         return((datetime)((long)formTime + (long)(idx - count) * secs));
      return((datetime)((long)tm[count - 1] + (long)(idx - (count - 1)) * secs));
     }

   void              ResetCache(void)
     {
      int i;
      for(i = 0; i < BF_NSLOTS; i++)
        {
         m_zc[i].drawn   = false;
         m_zc[i].t1      = 0;
         m_zc[i].t2      = 0;
         m_zc[i].p1      = 0.0;
         m_zc[i].p2      = 0.0;
         m_zc[i].fillClr = clrNONE;
         m_zc[i].lineClr = clrNONE;
         m_zc[i].style   = -1;
         m_zc[i].active  = false;
         m_zc[i].pos     = 0;
        }
      m_fc.drawn = false;
      m_fc.tx1   = 0;
      m_fc.tx2   = 0;
      m_fc.trt   = 0;
      m_fc.tend  = 0;
      m_fc.y1    = 0.0;
      m_fc.y2    = 0.0;
      m_fc.f0    = 0.0;
      m_fc.f1    = 0.0;
      m_fc.bg    = clrNONE;
     }

private:
   void              DeleteZoneObjects(const string baseName)
     {
      ObjectDelete(0, baseName + "_F");
      ObjectDelete(0, baseName + "_B");
      ObjectDelete(0, baseName + "_T");
     }

   void              DeleteFibObjects(void)
     {
      ObjectDelete(0, BF_PREFIX + "FIB_DIAG");
      ObjectDelete(0, BF_PREFIX + "FIB_VERT");
      ObjectDelete(0, BF_PREFIX + "FIB_0");
      ObjectDelete(0, BF_PREFIX + "FIB_0236");
      ObjectDelete(0, BF_PREFIX + "FIB_0382");
      ObjectDelete(0, BF_PREFIX + "FIB_0500");
      ObjectDelete(0, BF_PREFIX + "FIB_0618");
      ObjectDelete(0, BF_PREFIX + "FIB_0786");
      ObjectDelete(0, BF_PREFIX + "FIB_1");
      ObjectDelete(0, BF_PREFIX + "FIB_1618");
     }

   void              RenderSlot(const int kind, const int slot, const bool visible, const ZoneS &z, const int count,
                                const datetime &tm[], const datetime formTime, const color bg)
     {
      int    ci       = kind * BF_MAXB + slot;
      string baseName = BF_PREFIX + BfKindName(kind) + IntegerToString(slot);

      if(!visible || !z.box.exists)
        {
         if(m_zc[ci].drawn)
           {
            DeleteZoneObjects(baseName);
            m_zc[ci].drawn = false;
            m_dirty = true;
           }
         return;
        }

      bool     bull    = (kind == BF_KIND_FU || kind == BF_KIND_BU);
      color    baseClr = bull ? m_bull : m_bear;
      color    brkClr  = bull ? m_bullBrk : m_bearBrk;
      color    fillClr = z.box.brokenFill ? BfBlendColor(brkClr, m_breakT, bg) : BfBlendColor(baseClr, m_fillT, bg);
      color    lineClr = BfBlendColor(baseClr, m_borderT, bg);
      datetime t1      = IdxToTime(z.box.left, count, tm, formTime);
      datetime t2      = IdxToTime(z.box.right, count, tm, formTime);
      int      posVal  = z.posNa ? 0 : z.pos;

      if(m_zc[ci].drawn && m_zc[ci].t1 == t1 && m_zc[ci].t2 == t2 &&
         m_zc[ci].p1 == z.box.top && m_zc[ci].p2 == z.box.bottom &&
         m_zc[ci].fillClr == fillClr && m_zc[ci].lineClr == lineClr &&
         m_zc[ci].style == z.box.border && m_zc[ci].active == z.active && m_zc[ci].pos == posVal &&
         ObjectFind(0, baseName + "_F") >= 0 && ObjectFind(0, baseName + "_B") >= 0 &&
         ObjectFind(0, baseName + "_T") >= 0)
         return;                                                // nothing changed and still on the chart

      bool   isBpr = (kind == BF_KIND_BU || kind == BF_KIND_BD);
      string txt   = isBpr ? "BPR" : m_fvgText;
      string tip   = BfKindName(kind) + " #" + IntegerToString(slot) +
                     " top " + DoubleToString(z.box.top, m_digits) +
                     " bottom " + DoubleToString(z.box.bottom, m_digits) +
                     (z.active ? " active" : " inactive");
      if(!z.posNa)
         tip = tip + " pos " + IntegerToString(z.pos);

      BfDrawRect(baseName + "_F", t1, z.box.top, t2, z.box.bottom, fillClr, true, true, STYLE_SOLID, tip);
      BfDrawRect(baseName + "_B", t1, z.box.top, t2, z.box.bottom, lineClr, false, false,
                 BfBorderToStyle(z.box.border), tip);
      // Pine centres box text in bar-index space (xloc.bar_index): a weekend or session gap inside the box
      // does not pull the label off-centre.
      datetime tc = IdxToTime((z.box.left + z.box.right) / 2, count, tm, formTime);
      if(((z.box.left + z.box.right) % 2) != 0)
         tc = (datetime)((long)tc + (long)(PeriodSeconds() / 2));
      BfDrawText(baseName + "_T", tc, (z.box.top + z.box.bottom) / 2.0, txt, lineClr, tip, ANCHOR_CENTER);

      m_zc[ci].drawn   = true;
      m_zc[ci].t1      = t1;
      m_zc[ci].t2      = t2;
      m_zc[ci].p1      = z.box.top;
      m_zc[ci].p2      = z.box.bottom;
      m_zc[ci].fillClr = fillClr;
      m_zc[ci].lineClr = lineClr;
      m_zc[ci].style   = z.box.border;
      m_zc[ci].active  = z.active;
      m_zc[ci].pos     = posVal;
      m_dirty = true;
     }

   // Fibonacci between the last BPR up and the last BPR down (Pine L976-989, L1093-1118; LUXALGO_BPR_SPEC s.8).
   // Pine line definitions L251-260: diag silver@50 dashed, vert silver@50 dotted, levels solid,
   // 0 / 1 silver@5, 0.236 / 0.786 orange@25, 0.382 / 0.618 / 1.618 yellow@25, 0.5 green@25.
   // Only the 8 level lines take 'Extend lines' (extend=ext). Nothing is drawn when the BPRs are hidden
   // (the indicator with BPR off draws nothing, spec s.10).
   void              RenderFib(const StateS &s, const int count, const datetime &tm[], const datetime formTime,
                               const color bg)
     {
      bool ok = (m_fibOn && m_showBpr && s.nBu > 0 && s.nBd > 0 && s.bu[0].box.exists && s.bd[0].box.exists);
      if(!ok)
        {
         if(m_fc.drawn)
           {
            DeleteFibObjects();
            m_fc.drawn = false;
            m_dirty = true;
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

      int    rt  = BfIMax(x1, x2);                                    // L1094
      double f0  = (rt == x1) ? y1 : y2;                              // L1098 _0
      double f1  = (rt == x1) ? y2 : y1;                              // L1099 _1
      double df  = f1 - f0;                                           // L1101

      datetime tx1  = IdxToTime(x1, count, tm, formTime);
      datetime tx2  = IdxToTime(x2, count, tm, formTime);
      datetime trt  = IdxToTime(rt, count, tm, formTime);
      datetime tend = IdxToTime(rt + BF_FIB_LEN, count, tm, formTime); // rt + plus

      if(m_fc.drawn && m_fc.tx1 == tx1 && m_fc.tx2 == tx2 && m_fc.trt == trt && m_fc.tend == tend &&
         m_fc.y1 == y1 && m_fc.y2 == y2 && m_fc.f0 == f0 && m_fc.f1 == f1 && m_fc.bg == bg &&
         ObjectFind(0, BF_PREFIX + "FIB_0") >= 0 && ObjectFind(0, BF_PREFIX + "FIB_DIAG") >= 0)
         return;

      color silver50 = BfBlendColor(C'178,181,190', 50, bg);
      color silver05 = BfBlendColor(C'178,181,190', 5, bg);
      color orange25 = BfBlendColor(C'255,152,0', 25, bg);
      color yellow25 = BfBlendColor(C'255,235,59', 25, bg);
      color green25  = BfBlendColor(C'76,175,80', 25, bg);
      bool  ext      = m_fibExt;

      BfDrawTrend(BF_PREFIX + "FIB_DIAG", tx1, y1, tx2, y2, silver50, STYLE_DASH, false);                    // L1109
      BfDrawTrend(BF_PREFIX + "FIB_VERT", trt, f0, trt, f0 + df * 1.618, silver50, STYLE_DOT, false);        // L1110
      BfDrawTrend(BF_PREFIX + "FIB_0",    trt, f0, tend, f0, silver05, STYLE_SOLID, ext);                    // L1111
      BfDrawTrend(BF_PREFIX + "FIB_0236", trt, f0 + df * 0.236, tend, f0 + df * 0.236, orange25, STYLE_SOLID, ext); // L1112
      BfDrawTrend(BF_PREFIX + "FIB_0382", trt, f0 + df * 0.382, tend, f0 + df * 0.382, yellow25, STYLE_SOLID, ext); // L1113
      BfDrawTrend(BF_PREFIX + "FIB_0500", trt, f0 + df * 0.500, tend, f0 + df * 0.500, green25, STYLE_SOLID, ext);  // L1114
      BfDrawTrend(BF_PREFIX + "FIB_0618", trt, f0 + df * 0.618, tend, f0 + df * 0.618, yellow25, STYLE_SOLID, ext); // L1115
      BfDrawTrend(BF_PREFIX + "FIB_0786", trt, f0 + df * 0.786, tend, f0 + df * 0.786, orange25, STYLE_SOLID, ext); // L1116
      BfDrawTrend(BF_PREFIX + "FIB_1",    trt, f1, tend, f1, silver05, STYLE_SOLID, ext);                    // L1117
      BfDrawTrend(BF_PREFIX + "FIB_1618", trt, f0 + df * 1.618, tend, f0 + df * 1.618, yellow25, STYLE_SOLID, ext); // L1118

      m_fc.drawn = true;
      m_fc.tx1   = tx1;
      m_fc.tx2   = tx2;
      m_fc.trt   = trt;
      m_fc.tend  = tend;
      m_fc.y1    = y1;
      m_fc.y2    = y2;
      m_fc.f0    = f0;
      m_fc.f1    = f1;
      m_fc.bg    = bg;
      m_dirty = true;
     }

public:
                     CBfRender(void)
     {
      int i;
      m_showZones = true;
      m_showBpr   = true;
      m_fvgDebug  = false;
      m_fibOn     = false;
      m_fibExt    = false;
      m_showDispl = false;
      m_showSetups = true;
      m_showPanel = true;
      m_bull      = C'0,230,118';
      m_bullBrk   = C'128,128,0';
      m_bear      = C'255,82,82';
      m_bearBrk   = C'255,0,0';
      m_fillT     = 90;
      m_borderT   = 65;
      m_breakT    = 95;
      m_fvgText   = "FVG";
      m_digits    = 2;
      m_dirty     = false;
      m_lastBg    = clrNONE;
      m_skCount   = 0;
      for(i = 0; i < BF_SK_KEEP; i++)
         m_skIds[i] = 0;
      for(i = 0; i < BF_PANEL_ROWS; i++)
        {
         m_panel[i]      = "";
         m_panelShown[i] = "";
        }
      ResetCache();
     }

   void              Init(const bool showZones, const bool showBpr, const bool fvgDebug, const bool fibOn,
                          const bool fibExt, const bool showDispl, const bool showSetups, const bool showPanel,
                          const color bull, const color bullBrk, const color bear, const color bearBrk,
                          const int fillT, const int borderT, const int breakT, const bool ifvg, const int digits)
     {
      m_showZones = showZones;
      m_showBpr   = showBpr;
      m_fvgDebug  = fvgDebug;
      m_fibOn     = fibOn;
      m_fibExt    = fibExt;
      m_showDispl = showDispl;
      m_showSetups = showSetups;
      m_showPanel = showPanel;
      m_bull      = bull;
      m_bullBrk   = bullBrk;
      m_bear      = bear;
      m_bearBrk   = bearBrk;
      m_fillT     = BfIClamp(fillT, 0, 100);
      m_borderT   = BfIClamp(borderT, 0, 100);
      m_breakT    = BfIClamp(breakT, 0, 100);
      m_fvgText   = ifvg ? "IFVG" : "FVG";
      m_digits    = digits;
      ResetCache();
     }

   color             LastBg(void)
     {
      return(m_lastBg);
     }

   // Draws one engine state. Pine BPR mode: the FVG boxes are invisible but still drive the BPR; the debug
   // input shows them anyway. With BPR hidden, the FVG boxes are shown (styled like the indicator with BPR off).
   void              RenderState(const StateS &s, const int count, const datetime &tm[], const datetime formTime)
     {
      int   i;
      color bg      = (color)ChartGetInteger(0, CHART_COLOR_BACKGROUND);
      bool  showFvg = m_showZones && (!m_showBpr || m_fvgDebug);
      bool  showBpr = m_showZones && m_showBpr;
      m_lastBg = bg;
      for(i = 0; i < BF_MAXB; i++)
        {
         RenderSlot(BF_KIND_FU, i, showFvg && (i < s.nFu), s.fu[i], count, tm, formTime, bg);
         RenderSlot(BF_KIND_FD, i, showFvg && (i < s.nFd), s.fd[i], count, tm, formTime, bg);
         RenderSlot(BF_KIND_BU, i, showBpr && (i < s.nBu), s.bu[i], count, tm, formTime, bg);
         RenderSlot(BF_KIND_BD, i, showBpr && (i < s.nBd), s.bd[i], count, tm, formTime, bg);
        }
      RenderFib(s, count, tm, formTime, bg);
     }

   //--- displacement markers (Pine L1123-1134): up = lime arrow below the bar, down = red arrow above the bar.
   //    'key' identifies the bar (its time as text, or "F" for the forming bar).
   void              DisplMark(const string key, const bool up, const bool dn, const datetime t, const double lo,
                               const double hi)
     {
      string nu = BF_PREFIX + "DSP" + key + "U";
      string nd = BF_PREFIX + "DSP" + key + "D";
      if(!m_showDispl)
         return;
      if(up)
         BfDrawArrow(nu, OBJ_ARROW_UP, t, lo, m_bull, ANCHOR_TOP, "Displacement UP");
      else
         if(ObjectFind(0, nu) >= 0)
            ObjectDelete(0, nu);
      if(dn)
         BfDrawArrow(nd, OBJ_ARROW_DOWN, t, hi, m_bear, ANCHOR_BOTTOM, "Displacement DN");
      else
         if(ObjectFind(0, nd) >= 0)
            ObjectDelete(0, nd);
      m_dirty = true;
     }

   void              DisplDelete(const string key)
     {
      ObjectDelete(0, BF_PREFIX + "DSP" + key + "U");
      ObjectDelete(0, BF_PREFIX + "DSP" + key + "D");
     }

   //+---------------------------------------------------------------+
   //| v2 spec s.8: per-setup drawings. Every object of setup id is  |
   //| named BFEA_S<id>_<key>; the last BF_SK_KEEP setups are kept.  |
   //+---------------------------------------------------------------+
   string            SetupBase(const int id)
     {
      return(BF_PREFIX + "S" + IntegerToString(id) + "_");
     }

   bool              SetupsOn(void)
     {
      return(m_showSetups);
     }

   //--- a setup that gets drawings: the oldest drawn setup is deleted once BF_SK_KEEP are on the chart
   void              SetupRegister(const int id)
     {
      int i;
      for(i = 0; i < m_skCount; i++)
         if(m_skIds[i] == id)
            return;
      if(m_skCount >= BF_SK_KEEP)
        {
         ObjectsDeleteAll(0, SetupBase(m_skIds[0]));
         for(i = 1; i < BF_SK_KEEP; i++)
            m_skIds[i - 1] = m_skIds[i];
         m_skCount = BF_SK_KEEP - 1;
        }
      m_skIds[m_skCount] = id;
      m_skCount++;
     }

   void              SetupText(const int id, const string key, const datetime t, const double p, const string txt,
                               const color clr, const ENUM_ANCHOR_POINT anchor, const string tip)
     {
      if(!m_showSetups)
         return;
      SetupRegister(id);
      BfDrawText(SetupBase(id) + key, t, p, txt, clr, tip, anchor);
      m_dirty = true;
     }

   //--- a horizontal segment [t1, t2] at price p with a label at its right end
   void              SetupHLine(const int id, const string key, const datetime t1, const datetime t2, const double p,
                                const color clr, const ENUM_LINE_STYLE style, const string label, const string tip)
     {
      string b = SetupBase(id) + key;
      if(!m_showSetups)
         return;
      SetupRegister(id);
      BfDrawTrend(b, t1, p, t2, p, clr, style, false);
      ObjectSetString(0, b, OBJPROP_TOOLTIP, tip);
      if(label != "")
         BfDrawText(b + "T", t2, p, label, clr, tip, ANCHOR_LEFT);
      else
         ObjectDelete(0, b + "T");
      m_dirty = true;
     }

   void              SetupSegment(const int id, const string key, const datetime t1, const double p1, const datetime t2,
                                  const double p2, const color clr, const ENUM_LINE_STYLE style)
     {
      if(!m_showSetups)
         return;
      SetupRegister(id);
      BfDrawTrend(SetupBase(id) + key, t1, p1, t2, p2, clr, style, false);
      m_dirty = true;
     }

   //--- a rectangle of the setup (its own zone: the LuxAlgo box may leave the engine arrays, and its colour is the
   //    gap that created it, not the trade direction)
   void              SetupRect(const int id, const string key, const datetime t1, const double p1, const datetime t2,
                               const double p2, const color clr, const string tip)
     {
      color bg = (color)ChartGetInteger(0, CHART_COLOR_BACKGROUND);
      if(!m_showSetups)
         return;
      SetupRegister(id);
      BfDrawRect(SetupBase(id) + key, t1, p1, t2, p2, BfBlendColor(clr, 60, bg), false, false, STYLE_DASHDOT, tip);
      m_dirty = true;
     }

   //--- new text for an existing label (the label of line 'key')
   void              SetupLabel(const int id, const string key, const string txt)
     {
      string nm = SetupBase(id) + key + "T";
      if(!m_showSetups || ObjectFind(0, nm) < 0)
         return;
      ObjectSetString(0, nm, OBJPROP_TEXT, txt);
      m_dirty = true;
     }

   void              SetupDelete(const int id, const string key)
     {
      ObjectDelete(0, SetupBase(id) + key);
      ObjectDelete(0, SetupBase(id) + key + "T");
      m_dirty = true;
     }

   //--- a finished setup (DONE / CLOSED / re-anchored): its drawings turn grey, they stay for review
   void              SetupGrey(const int id)
     {
      int    i;
      bool   known = false;
      string pre = SetupBase(id);
      string nm;
      if(!m_showSetups)
         return;
      for(i = 0; i < m_skCount; i++)
         if(m_skIds[i] == id)
            known = true;
      if(!known)
         return;                                                // nothing was drawn for this setup
      for(i = ObjectsTotal(0) - 1; i >= 0; i--)
        {
         nm = ObjectName(0, i);
         if(StringFind(nm, pre) == 0)
            ObjectSetInteger(0, nm, OBJPROP_COLOR, C'128,128,128');
        }
      m_dirty = true;
     }

   //--- panel (top-left labels)
   void              PanelSet(const int row, const string text)
     {
      if(row >= 0 && row < BF_PANEL_ROWS)
         m_panel[row] = text;
     }

   void              PanelDraw(void)
     {
      int    i;
      string name;
      if(!m_showPanel)
         return;
      for(i = 0; i < BF_PANEL_ROWS; i++)
        {
         name = BF_PREFIX + "PANEL" + IntegerToString(i);
         if(ObjectFind(0, name) < 0)
           {
            if(!ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0))
               continue;
            ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
            ObjectSetInteger(0, name, OBJPROP_ANCHOR, ANCHOR_LEFT_UPPER);
            ObjectSetInteger(0, name, OBJPROP_XDISTANCE, 10);
            ObjectSetInteger(0, name, OBJPROP_YDISTANCE, 30 + 15 * i);
            ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 9);
            ObjectSetString(0, name, OBJPROP_FONT, "Consolas");
            ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
            ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
            ObjectSetInteger(0, name, OBJPROP_COLOR, (i == 0) ? clrGold : clrSilver);
            m_panelShown[i] = "<unset>";                        // force the first text update
           }
         if(m_panelShown[i] != m_panel[i])
           {
            ObjectSetString(0, name, OBJPROP_TEXT, (m_panel[i] == "") ? " " : m_panel[i]);
            m_panelShown[i] = m_panel[i];
            m_dirty = true;
           }
        }
     }

   void              Redraw(void)
     {
      if(m_dirty)
        {
         ChartRedraw(0);
         m_dirty = false;
        }
     }

   void              DeleteAll(void)
     {
      ObjectsDeleteAll(0, BF_PREFIX);
      ResetCache();
      m_skCount = 0;
      ChartRedraw(0);
     }
  };

#endif
//+------------------------------------------------------------------+
