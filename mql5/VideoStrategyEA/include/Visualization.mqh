//+------------------------------------------------------------------+
//| Visualization.mqh — chart objects for comparing the EA with the   |
//| video: candle box, MTF zig-zag and condition, location level,     |
//| extension leg, protected swing + shift arrow, entry/SL/TP,        |
//| invalidation labels and a state panel.                            |
//+------------------------------------------------------------------+
#ifndef VSEA_VISUAL_MQH
#define VSEA_VISUAL_MQH

#include "Defines.mqh"
#include "MarketData.mqh"

class CVisual
  {
private:
   bool              m_structure;
   bool              m_levels;
   bool              m_entries;
   bool              m_panel;
   string            m_panelLines[12];

   string            Name(const int setupId, const int tf, const string what) const
     {
      return VSEA_PREFIX + IntegerToString(setupId) + "_" + IntegerToString(tf) + "_" + what;
     }

   void              Line(const string name, const datetime t1, const double p1, const datetime t2, const double p2,
                          const color clr, const int style, const int width, const string tip)
     {
      if(ObjectFind(0, name) < 0) ObjectCreate(0, name, OBJ_TREND, 0, t1, p1, t2, p2);
      else { ObjectMove(0, name, 0, t1, p1); ObjectMove(0, name, 1, t2, p2); }
      ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
      ObjectSetInteger(0, name, OBJPROP_STYLE, style);
      ObjectSetInteger(0, name, OBJPROP_WIDTH, width);
      ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, false);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_BACK, true);
      ObjectSetString(0, name, OBJPROP_TOOLTIP, tip);
     }

   void              Text(const string name, const datetime t, const double p, const string txt, const color clr)
     {
      if(ObjectFind(0, name) < 0) ObjectCreate(0, name, OBJ_TEXT, 0, t, p);
      else ObjectMove(0, name, 0, t, p);
      ObjectSetString(0, name, OBJPROP_TEXT, txt);
      ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
      ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 8);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
     }

public:
                     CVisual(void) : m_structure(true), m_levels(true), m_entries(true), m_panel(true) {}

   void              Init(const bool structure, const bool levels, const bool entries, const bool panel)
     {
      m_structure = structure; m_levels = levels; m_entries = entries; m_panel = panel;
     }

   //--- candle box (updated every bar)
   void              CandleBox(const int setupId, const int tf, const datetime open, const datetime end,
                               const double hi, const double lo, const string label)
     {
      if(!m_structure) return;
      string name = Name(setupId, tf, "box");
      if(ObjectFind(0, name) < 0) ObjectCreate(0, name, OBJ_RECTANGLE, 0, open, hi, end, lo);
      else { ObjectMove(0, name, 0, open, hi); ObjectMove(0, name, 1, end, lo); }
      ObjectSetInteger(0, name, OBJPROP_COLOR, tf >= 60 ? clrSlateGray : clrDimGray);
      ObjectSetInteger(0, name, OBJPROP_FILL, false);
      ObjectSetInteger(0, name, OBJPROP_BACK, true);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetString(0, name, OBJPROP_TOOLTIP, label);
     }

   //--- MTF zig-zag pivots of the context (drawn once per candle)
   void              MtfLegs(const int setupId, const int tf, const SMtfContext &ctx, const string label)
     {
      if(!m_structure) return;
      for(int i = 1; i < ctx.nPivots; i++)
         Line(Name(setupId, tf, "mtf" + IntegerToString(i)), ctx.pvTime[i - 1], ctx.pvPrice[i - 1], ctx.pvTime[i],
              ctx.pvPrice[i], clrSteelBlue, STYLE_SOLID, 1, label);
      if(ctx.nPivots > 0)
         Text(Name(setupId, tf, "mtflabel"), ctx.pvTime[ctx.nPivots - 1], ctx.pvPrice[ctx.nPivots - 1], label, clrSteelBlue);
     }

   void              Level(const int setupId, const int tf, const string what, const datetime t1, const datetime t2,
                           const double price, const color clr, const string tip)
     {
      if(!m_levels || !VsValid(price)) return;
      Line(Name(setupId, tf, what), t1, price, t2, price, clr, STYLE_DOT, 1, tip);
     }

   void              Extension(const int setupId, const int tf, const string what, const datetime to, const double po,
                               const datetime te, const double pe, const string tip)
     {
      if(!m_structure) return;
      Line(Name(setupId, tf, what), to, po, te, pe, clrGold, STYLE_SOLID, 2, tip);
     }

   void              Shift(const int setupId, const int tf, const int dir, const datetime protTime, const double protPrice,
                           const datetime when, const double price, const string tip)
     {
      if(!m_structure) return;
      Line(Name(setupId, tf, "prot"), protTime, protPrice, when, protPrice, clrOrange, STYLE_DASH, 1, tip);
      string name = Name(setupId, tf, "shift");
      if(ObjectFind(0, name) < 0) ObjectCreate(0, name, OBJ_ARROW, 0, when, price);
      ObjectSetInteger(0, name, OBJPROP_ARROWCODE, dir < 0 ? 234 : 233);
      ObjectSetInteger(0, name, OBJPROP_COLOR, dir < 0 ? clrTomato : clrLimeGreen);
      ObjectSetInteger(0, name, OBJPROP_ANCHOR, dir < 0 ? ANCHOR_BOTTOM : ANCHOR_TOP);
      ObjectSetString(0, name, OBJPROP_TOOLTIP, tip);
     }

   void              Orders(const int setupId, const int tf, const datetime when, const datetime until,
                            const double entry, const double sl, const double tp)
     {
      if(!m_entries) return;
      Line(Name(setupId, tf, "entry"), when, entry, until, entry, clrWhite, STYLE_SOLID, 1, "entry");
      Line(Name(setupId, tf, "sl"), when, sl, until, sl, clrRed, STYLE_SOLID, 1, "stop loss");
      Line(Name(setupId, tf, "tp"), when, tp, until, tp, clrLime, STYLE_SOLID, 1, "take profit (50% of extension)");
     }

   void              Invalidation(const int setupId, const int tf, const datetime t, const double p, const string reason)
     {
      if(!m_structure) return;
      Text(Name(setupId, tf, "inv"), t, p, reason, clrIndianRed);
     }

   //--- panel
   void              PanelSet(const int row, const string text) { if(row >= 0 && row < 12) m_panelLines[row] = text; }
   void              PanelDraw(void)
     {
      if(!m_panel) return;
      for(int i = 0; i < 12; i++)
        {
         string name = VSEA_PREFIX + "panel" + IntegerToString(i);
         if(ObjectFind(0, name) < 0)
           {
            ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
            ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
            ObjectSetInteger(0, name, OBJPROP_XDISTANCE, 10);
            ObjectSetInteger(0, name, OBJPROP_YDISTANCE, 20 + 14 * i);
            ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 9);
            ObjectSetString(0, name, OBJPROP_FONT, "Consolas");
            ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
           }
         ObjectSetString(0, name, OBJPROP_TEXT, m_panelLines[i]);
         ObjectSetInteger(0, name, OBJPROP_COLOR, i == 0 ? clrGold : clrSilver);
        }
     }

   void              DeleteAll(void) { ObjectsDeleteAll(0, VSEA_PREFIX); }
  };

#endif
