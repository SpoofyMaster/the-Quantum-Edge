//+------------------------------------------------------------------+
//| MarketData.mqh — closed M1 bar series for gold and DXY            |
//| COR-5 / A-10: DXY from a broker symbol or the ICE formula.        |
//| Only CLOSED bars are ever loaded (CopyRates from shift 1).        |
//+------------------------------------------------------------------+
#ifndef VSEA_MARKETDATA_MQH
#define VSEA_MARKETDATA_MQH

#include "Defines.mqh"

bool VsValid(const double v) { return v != VSEA_NA && MathIsValidNumber(v); }

//--- chronological bar series (index 0 = oldest). Missing DXY minutes hold VSEA_NA.
class CSeries
  {
public:
   datetime          t[];
   double            o[];
   double            h[];
   double            l[];
   double            c[];
   int               phPrev[];     // last pivot-high index <= k (or -1)
   int               plPrev[];     // last pivot-low index <= k (or -1)
   int               n;

                     CSeries(void) : n(0) {}
   void              Resize(const int size)
     {
      n = size;
      ArrayResize(t, size); ArrayResize(o, size); ArrayResize(h, size); ArrayResize(l, size); ArrayResize(c, size);
      ArrayResize(phPrev, size); ArrayResize(plPrev, size);
     }
   bool              ValidBar(const int k) const { return k >= 0 && k < n && VsValid(h[k]) && VsValid(l[k]); }

   //--- first index with t[k] >= when (n if none)
   int               LowerBound(const datetime when) const
     {
      int lo = 0, hi = n;
      while(lo < hi)
        {
         int mid = (lo + hi) / 2;
         if(t[mid] < when) lo = mid + 1;
         else hi = mid;
        }
      return lo;
     }

   //--- SHF-1: fractal pivots, strength N; flag at k uses bars k-N..k+N (callers only query k <= t-N)
   void              ComputePivots(const int N)
     {
      int lastH = -1, lastL = -1;
      for(int k = 0; k < n; k++)
        {
         bool ph = (k - N >= 0 && k + N < n && ValidBar(k));
         bool pl = ph;
         for(int i = 1; i <= N && (ph || pl); i++)
           {
            if(!ValidBar(k - i) || !ValidBar(k + i)) { ph = false; pl = false; break; }
            if(!(h[k] > h[k - i] && h[k] >= h[k + i])) ph = false;
            if(!(l[k] < l[k - i] && l[k] <= l[k + i])) pl = false;
           }
         if(ph) lastH = k;
         if(pl) lastL = k;
         phPrev[k] = lastH;
         plPrev[k] = lastL;
        }
     }

   //--- simple-mean ATR over the n true ranges ending at k (VSEA_NA if not enough valid bars)
   double            AtrAt(const int k, const int period) const
     {
      if(k - period < 0) return VSEA_NA;
      double s = 0.0;
      for(int j = k - period + 1; j <= k; j++)
        {
         if(!ValidBar(j) || !VsValid(c[j - 1])) return VSEA_NA;
         s += MathMax(h[j], c[j - 1]) - MathMin(l[j], c[j - 1]);
        }
      return s / period;
     }
  };

//--- loads gold and DXY series
class CMarketData
  {
private:
   string            m_gold;
   string            m_dxySymbol;
   int               m_dxySource;      // resolved: VS_DXYSRC_BROKER or VS_DXYSRC_SYNTHETIC
   string            m_comp[6];
   double            m_w[6];
   int               m_bars;

   bool              LoadRates(const string sym, const datetime from, const datetime to, MqlRates &r[])
     {
      ArraySetAsSeries(r, false);
      int got = CopyRates(sym, PERIOD_M1, from, to, r);
      return got > 0;
     }

public:
   string            lastError;

                     CMarketData(void) : m_dxySource(VS_DXYSRC_SYNTHETIC), m_bars(500) {}

   bool              Init(const string gold, const int dxySource, const string dxySymbol, const string suffix, const int bars)
     {
      m_gold = gold;
      m_bars = bars;
      string names[6] = {"EURUSD", "USDJPY", "GBPUSD", "USDCAD", "USDSEK", "USDCHF"};
      double w[6]     = {-0.576, 0.136, -0.119, 0.091, 0.042, 0.036};
      for(int i = 0; i < 6; i++) { m_comp[i] = names[i] + suffix; m_w[i] = w[i]; }
      bool brokerOk = (dxySymbol != "" && SymbolSelect(dxySymbol, true));
      if(dxySource == VS_DXYSRC_BROKER || (dxySource == VS_DXYSRC_AUTO && brokerOk))
        {
         if(!brokerOk) { lastError = "DXY symbol '" + dxySymbol + "' not found"; return false; }
         m_dxySource = VS_DXYSRC_BROKER;
         m_dxySymbol = dxySymbol;
         return true;
        }
      for(int i = 0; i < 6; i++)
         if(!SymbolSelect(m_comp[i], true)) { lastError = "synthetic DXY needs " + m_comp[i]; return false; }
      m_dxySource = VS_DXYSRC_SYNTHETIC;
      return true;
     }

   string            DxyDescription(void) const
     {
      if(m_dxySource == VS_DXYSRC_BROKER) return "broker " + m_dxySymbol;
      return "synthetic ICE (" + m_comp[0] + ",...," + m_comp[5] + ")";
     }

   //--- the last `m_bars` CLOSED M1 bars of gold
   bool              LoadGold(CSeries &g)
     {
      MqlRates r[];
      ArraySetAsSeries(r, false);
      int got = CopyRates(m_gold, PERIOD_M1, 1, m_bars, r);
      if(got <= 0) { lastError = "CopyRates gold failed " + IntegerToString(GetLastError()); return false; }
      g.Resize(got);
      for(int i = 0; i < got; i++)
        {
         g.t[i] = r[i].time; g.o[i] = r[i].open; g.h[i] = r[i].high; g.l[i] = r[i].low; g.c[i] = r[i].close;
        }
      return true;
     }

   //--- DXY bars aligned minute-by-minute to gold's timestamps (never a forming bar, never forward-filled)
   bool              LoadDxy(const CSeries &g, CSeries &x)
     {
      x.Resize(g.n);
      for(int i = 0; i < g.n; i++) { x.t[i] = g.t[i]; x.o[i] = VSEA_NA; x.h[i] = VSEA_NA; x.l[i] = VSEA_NA; x.c[i] = VSEA_NA; }
      if(g.n == 0) return false;
      datetime from = g.t[0] - 60, to = g.t[g.n - 1];
      if(m_dxySource == VS_DXYSRC_BROKER)
        {
         MqlRates r[];
         if(!LoadRates(m_dxySymbol, from, to, r)) { lastError = "CopyRates DXY failed"; return false; }
         int j = 0, m = ArraySize(r);
         for(int i = 0; i < g.n; i++)
           {
            while(j < m && r[j].time < g.t[i]) j++;
            if(j < m && r[j].time == g.t[i])
              { x.o[i] = r[j].open; x.h[i] = r[j].high; x.l[i] = r[j].low; x.c[i] = r[j].close; }
           }
         return true;
        }
      //--- synthetic: close-only "line" bars (o = previous synthetic close)
      MqlRates comp0[], comp1[], comp2[], comp3[], comp4[], comp5[];
      if(!LoadRates(m_comp[0], from, to, comp0) || !LoadRates(m_comp[1], from, to, comp1) ||
         !LoadRates(m_comp[2], from, to, comp2) || !LoadRates(m_comp[3], from, to, comp3) ||
         !LoadRates(m_comp[4], from, to, comp4) || !LoadRates(m_comp[5], from, to, comp5))
        { lastError = "CopyRates synthetic DXY components failed"; return false; }
      int p0 = 0, p1 = 0, p2 = 0, p3 = 0, p4 = 0, p5 = 0;
      double prev = VSEA_NA;
      double logK = MathLog(50.14348112);
      for(int i = 0; i < g.n; i++)
        {
         datetime ti = g.t[i];
         double v0 = FindClose(comp0, p0, ti), v1 = FindClose(comp1, p1, ti), v2 = FindClose(comp2, p2, ti);
         double v3 = FindClose(comp3, p3, ti), v4 = FindClose(comp4, p4, ti), v5 = FindClose(comp5, p5, ti);
         if(v0 <= 0 || v1 <= 0 || v2 <= 0 || v3 <= 0 || v4 <= 0 || v5 <= 0)
            continue;
         double lv = logK + m_w[0] * MathLog(v0) + m_w[1] * MathLog(v1) + m_w[2] * MathLog(v2)
                     + m_w[3] * MathLog(v3) + m_w[4] * MathLog(v4) + m_w[5] * MathLog(v5);
         double cl = MathExp(lv);
         double op = VsValid(prev) ? prev : cl;
         x.o[i] = op; x.c[i] = cl; x.h[i] = MathMax(op, cl); x.l[i] = MathMin(op, cl);
         prev = cl;
        }
      return true;
     }

   //--- close of the bar with exactly this time (advancing pointer), or -1
   static double     FindClose(const MqlRates &r[], int &p, const datetime when)
     {
      int m = ArraySize(r);
      while(p < m && r[p].time < when) p++;
      if(p < m && r[p].time == when) return r[p].close;
      return -1.0;
     }
  };

#endif
