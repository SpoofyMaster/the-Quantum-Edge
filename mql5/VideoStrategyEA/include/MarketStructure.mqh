//+------------------------------------------------------------------+
//| MarketStructure.mqh — extension tracker, zig-zag, MTF context,    |
//| location level and the type-3 shift.                              |
//| Mirrors qe/video_strategy/structure.py and engine.py one-to-one.  |
//+------------------------------------------------------------------+
#ifndef VSEA_STRUCTURE_MQH
#define VSEA_STRUCTURE_MQH

#include "Defines.mqh"
#include "MarketData.mqh"

//+------------------------------------------------------------------+
//| EXT-1..3: incremental extension tracker (spec section 4)          |
//| sign +1 = bullish extension (sell setup), -1 = bearish (buy)      |
//+------------------------------------------------------------------+
class CExtTracker
  {
public:
   int               sign;
   double            E;        // extreme
   int               e;        // first index that set the extreme
   double            O;        // origin
   int               o;        // last index of the origin
   double            PB;       // max internal pullback / size over (o, e]
   double            run;
   int               runI;
   double            dd;
   double            rm;

                     CExtTracker(void) : sign(1) { Reset(); }
   void              Reset(void)
     {
      E = VSEA_NA; e = -1; O = VSEA_NA; o = -1; PB = 0.0; run = VSEA_NA; runI = -1; dd = 0.0; rm = VSEA_NA;
     }
   double            Size(void) const { return (e >= 0) ? (E - O) * sign : 0.0; }

   void              Update(const int k, const double hk, const double lk)
     {
      if(!VsValid(hk) || !VsValid(lk)) return;
      if(sign > 0)
        {
         if(runI < 0 || lk <= run) { run = lk; runI = k; dd = 0.0; rm = hk; }
         else { dd = MathMax(dd, rm - lk); rm = MathMax(rm, hk); }
         if(e < 0 || hk > E)
           {
            E = hk; e = k; O = run; o = runI;
            double size = E - O;
            PB = (size > 0) ? dd / size : 0.0;
           }
        }
      else
        {
         if(runI < 0 || hk >= run) { run = hk; runI = k; dd = 0.0; rm = lk; }
         else { dd = MathMax(dd, hk - rm); rm = MathMin(rm, lk); }
         if(e < 0 || lk < E)
           {
            E = lk; e = k; O = run; o = runI;
            double size = O - E;
            PB = (size > 0) ? dd / size : 0.0;
           }
        }
     }
  };

//+------------------------------------------------------------------+
//| SHF-2: type-3 shift against `ext` at bar t (spec section 6)       |
//+------------------------------------------------------------------+
bool FindShift(const CSeries &a, const CExtTracker &ext, const int t, const int N, const bool wick,
               const double minBreak, int &protIdx, double &protPrice)
  {
   protIdx = -1;
   protPrice = VSEA_NA;
   if(ext.e < 0 || t <= ext.e || t >= a.n) return false;
   int lim = MathMin(ext.e - 1, t - N);
   if(lim < 0) return false;
   if(ext.sign > 0)
     {
      int k = a.plPrev[lim];
      if(k < ext.o) return false;
      int lim2 = MathMin(k - 1, t - N);
      if(lim2 < 0 || a.phPrev[lim2] < ext.o) return false;
      double px = wick ? a.l[t] : a.c[t];
      if(!VsValid(px) || !(px < a.l[k] - minBreak)) return false;
      protIdx = k; protPrice = a.l[k];
      return true;
     }
   int k = a.phPrev[lim];
   if(k < ext.o) return false;
   int lim2 = MathMin(k - 1, t - N);
   if(lim2 < 0 || a.plPrev[lim2] < ext.o) return false;
   double px = wick ? a.h[t] : a.c[t];
   if(!VsValid(px) || !(px > a.h[k] + minBreak)) return false;
   protIdx = k; protPrice = a.h[k];
   return true;
  }

//+------------------------------------------------------------------+
//| helpers for the context                                           |
//+------------------------------------------------------------------+
double MedianOf(double &v[], const int cnt)
  {
   double tmp[];
   ArrayResize(tmp, cnt);
   for(int i = 0; i < cnt; i++) tmp[i] = v[i];
   ArraySort(tmp);
   if(cnt % 2 == 1) return tmp[cnt / 2];
   return 0.5 * (tmp[cnt / 2 - 1] + tmp[cnt / 2]);
  }

//+------------------------------------------------------------------+
//| CTX-1..6: middle-timeframe context at a candle open (spec 2)      |
//+------------------------------------------------------------------+
void ComputeMtfContext(const CSeries &s, const datetime candleOpen, const SStrategyParams &p, SMtfContext &ctx)
  {
   ZeroMemory(ctx);
   ctx.condition = VS_COND_UNDEFINED;
   ctx.ratioMedian = VSEA_NA;
   ctx.theta = VSEA_NA;
   datetime w0 = candleOpen - p.mtfLookbackMin * 60;
   int i0 = s.LowerBound(w0), i1 = s.LowerBound(candleOpen);
   //--- 2.1 coverage
   int valid = 0;
   for(int k = i0; k < i1; k++) if(s.ValidBar(k)) valid++;
   ctx.coverage = (double)valid / p.mtfLookbackMin;
   if(ctx.coverage < p.minCoverage) return;
   //--- 2.2 aggregate valid bars to M5 buckets aligned to w0
   double mo[], mh[], ml[], mc[];
   ArrayResize(mo, 0); ArrayResize(mh, 0); ArrayResize(ml, 0); ArrayResize(mc, 0);
   datetime mt[];
   ArrayResize(mt, 0);
   long curBucket = -1;
   int K = 0;
   for(int k = i0; k < i1; k++)
     {
      if(!s.ValidBar(k)) continue;
      long b = (long)((s.t[k] - w0) / 300);
      if(b != curBucket)
        {
         K++;
         ArrayResize(mo, K); ArrayResize(mh, K); ArrayResize(ml, K); ArrayResize(mc, K); ArrayResize(mt, K);
         mo[K - 1] = s.o[k]; mh[K - 1] = s.h[k]; ml[K - 1] = s.l[k]; mc[K - 1] = s.c[k]; mt[K - 1] = s.t[k];
         curBucket = b;
        }
      else
        {
         mh[K - 1] = MathMax(mh[K - 1], s.h[k]);
         ml[K - 1] = MathMin(ml[K - 1], s.l[k]);
         mc[K - 1] = s.c[k];
        }
     }
   int nAtr = p.zzAtrPeriod;
   if(K < nAtr + 1) return;
   double sumTr = 0.0;
   for(int k = K - nAtr; k < K; k++)
      sumTr += MathMax(mh[k], mc[k - 1]) - MathMin(ml[k], mc[k - 1]);
   double theta = p.zzAtrMult * sumTr / nAtr;
   ctx.theta = theta;
   if(!(theta > 0)) return;
   //--- 2.3 zig-zag
   int    pvIdx[];
   double pvPrice[];
   int    pvKind[];
   int nPv = 0;
   ArrayResize(pvIdx, 0); ArrayResize(pvPrice, 0); ArrayResize(pvKind, 0);
   int d = 0;
   double hi = mh[0], lo = ml[0], ext = VSEA_NA;
   int hiI = 0, loI = 0, extI = -1;
   for(int k = 1; k < K; k++)
     {
      if(d == 0)
        {
         if(mh[k] > hi) { hi = mh[k]; hiI = k; }
         if(ml[k] < lo) { lo = ml[k]; loI = k; }
         if(hi - lo >= theta)
           {
            nPv++;
            ArrayResize(pvIdx, nPv); ArrayResize(pvPrice, nPv); ArrayResize(pvKind, nPv);
            if(hiI > loI || (hiI == loI && mc[hiI] >= mo[hiI]))
              { pvIdx[nPv - 1] = loI; pvPrice[nPv - 1] = lo; pvKind[nPv - 1] = -1; d = 1; ext = hi; extI = hiI; }
            else
              { pvIdx[nPv - 1] = hiI; pvPrice[nPv - 1] = hi; pvKind[nPv - 1] = 1; d = -1; ext = lo; extI = loI; }
           }
        }
      else if(d == 1)
        {
         if(mh[k] > ext) { ext = mh[k]; extI = k; }
         else if(ext - ml[k] >= theta)
           {
            nPv++;
            ArrayResize(pvIdx, nPv); ArrayResize(pvPrice, nPv); ArrayResize(pvKind, nPv);
            pvIdx[nPv - 1] = extI; pvPrice[nPv - 1] = ext; pvKind[nPv - 1] = 1;
            d = -1; ext = ml[k]; extI = k;
           }
        }
      else
        {
         if(ml[k] < ext) { ext = ml[k]; extI = k; }
         else if(mh[k] - ext >= theta)
           {
            nPv++;
            ArrayResize(pvIdx, nPv); ArrayResize(pvPrice, nPv); ArrayResize(pvKind, nPv);
            pvIdx[nPv - 1] = extI; pvPrice[nPv - 1] = ext; pvKind[nPv - 1] = -1;
            d = 1; ext = mh[k]; extI = k;
           }
        }
     }
   //--- drawing data: pivots + tentative extreme
   int nDraw = MathMin(nPv, VSEA_MAX_PIVOTS - 1);
   for(int i = 0; i < nDraw; i++) { ctx.pvTime[i] = mt[pvIdx[nPv - nDraw + i]]; ctx.pvPrice[i] = pvPrice[nPv - nDraw + i]; }
   ctx.nPivots = nDraw;
   if(d != 0 && extI >= 0) { ctx.pvTime[nDraw] = mt[extI]; ctx.pvPrice[nDraw] = ext; ctx.nPivots = nDraw + 1; }
   //--- 2.8 reference legs (in-progress leg included)
   int nPts = nPv + ((d != 0) ? 1 : 0);
   for(int i = nPts - 1; i >= 1; i--)
     {
      double a = pvPrice[i - 1];
      double b = (i < nPv) ? pvPrice[i] : ext;
      if(b < a && !ctx.hasDown) { ctx.hasDown = true; ctx.downHs = a; ctx.downLe = b; }
      if(b > a && !ctx.hasUp)   { ctx.hasUp = true; ctx.upLs = a; ctx.upHe = b; }
      if(ctx.hasDown && ctx.hasUp) break;
     }
   //--- 2.4-2.6 condition from completed legs
   int nLegs = nPv - 1;
   ctx.nCompleted = MathMax(nLegs, 0);
   if(nLegs < 3) return;
   double ratios[];
   ArrayResize(ratios, 0);
   int nr = 0;
   for(int i = 2; i < nPv; i++)
     {
      double L1 = MathAbs(pvPrice[i - 1] - pvPrice[i - 2]);
      double L2 = MathAbs(pvPrice[i] - pvPrice[i - 1]);
      double mx = MathMax(L1, L2);
      if(mx <= 0) continue;
      nr++;
      ArrayResize(ratios, nr);
      ratios[nr - 1] = MathMin(L1, L2) / mx;
     }
   if(nr < 2) return;
   ctx.ratioMedian = MedianOf(ratios, nr);
   if(ctx.ratioMedian < p.trendMaxRatio) ctx.condition = VS_COND_TREND;
   else if(ctx.ratioMedian < p.rangeMinRatio) ctx.condition = VS_COND_TRENDING_RANGE;
   else ctx.condition = VS_COND_RANGE;
   //--- 2.7 direction from the last two highs and lows
   double h1 = VSEA_NA, h2 = VSEA_NA, l1 = VSEA_NA, l2 = VSEA_NA;
   for(int i = nPv - 1; i >= 0; i--)
     {
      if(pvKind[i] == 1) { if(!VsValid(h2)) h2 = pvPrice[i]; else if(!VsValid(h1)) h1 = pvPrice[i]; }
      else               { if(!VsValid(l2)) l2 = pvPrice[i]; else if(!VsValid(l1)) l1 = pvPrice[i]; }
     }
   if(VsValid(h1) && VsValid(h2) && VsValid(l1) && VsValid(l2))
     {
      if(h2 > h1 && l2 > l1) ctx.direction = 1;
      else if(h2 < h1 && l2 < l1) ctx.direction = -1;
     }
  }

bool ContextTradable(const SMtfContext &ctx)
  {
   return ctx.condition == VS_COND_RANGE || ctx.condition == VS_COND_TRENDING_RANGE;
  }

string ConditionName(const int c)
  {
   switch(c)
     {
      case VS_COND_TREND:          return "TREND";
      case VS_COND_TRENDING_RANGE: return "TRENDING_RANGE";
      case VS_COND_RANGE:          return "RANGE";
     }
   return "UNDEFINED";
  }

//+------------------------------------------------------------------+
//| EXT-4 / COR-2: location level (spec section 3)                    |
//+------------------------------------------------------------------+
bool LocationLevel(const SMtfContext &ctx, const int tradeDir, const SStrategyParams &p, double &level)
  {
   double f = p.minLocRetrace;
   if(p.locationMode == VS_LOC_CONDITION_AWARE)
     {
      if(ctx.condition == VS_COND_RANGE || ctx.direction == 0) f = 0.75;
      else f = (ctx.direction == tradeDir) ? 0.50 : 1.00;
     }
   if(tradeDir < 0)
     {
      if(!ctx.hasDown) return false;
      level = ctx.downLe + f * (ctx.downHs - ctx.downLe);
      return true;
     }
   if(!ctx.hasUp) return false;
   level = ctx.upHe - f * (ctx.upHe - ctx.upLs);
   return true;
  }

#endif
