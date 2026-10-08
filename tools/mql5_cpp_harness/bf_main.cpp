// Drives the pure modules of mql5/BprFvgEA (BfDefines, BfEngine, BfDetector) bar by bar under the parity-harness
// environment of research/indicators/BPR_FVG_EA_SPEC.md section 9 and prints the detector's event records as JSON
// lines. Usage: bf_harness <bars.txt> key=value ...   (keys: see SetParam below; sp = constant spread)
#include "bf_pure.cpp"
#include <vector>
#include <cstdlib>
#include <cstring>

static void SetParam(BfParams &p, BfEngineParams &ep, double &sp, int &tradeFrom, const char *kv)
  {
   std::string s(kv);
   size_t eq = s.find('=');
   if(eq == std::string::npos) return;
   std::string k = s.substr(0, eq);
   double v = atof(s.c_str() + eq + 1);
   if(k == "source") p.source = (int)v;
   else if(k == "direction") p.direction = (int)v;
   else if(k == "entry_mode") p.entryMode = (int)v;
   else if(k == "entry_offset_ticks") p.entryOffsetTicks = (int)v;
   else if(k == "use_sweep") p.useSweep = v != 0;
   else if(k == "sweep_window") p.sweepWindow = (int)v;
   else if(k == "range_bars") p.rangeBars = (int)v;
   else if(k == "use_mss") p.useMss = v != 0;
   else if(k == "mss_bars") p.mssBars = (int)v;
   else if(k == "rally_bars") p.rallyBars = (int)v;
   else if(k == "expiry_bars") p.expiryBars = (int)v;
   else if(k == "stop_zone_mult") p.stopZoneMult = v;
   else if(k == "min_rr") p.minRR = v;
   else if(k == "max_cost_r") p.maxCostR = v;
   else if(k == "tp_mode") p.tpMode = (int)v;
   else if(k == "slippage_ticks") p.slippageTicks = v;
   else if(k == "tick_size") p.tickSize = v;
   else if(k == "digits") p.digits = (int)v;
   else if(k == "comm_price") p.commPrice = v;
   else if(k == "length") { p.length = (int)v; ep.length = (int)v; }
   else if(k == "vis_boxes") { p.visBoxes = (int)v; ep.visBoxes = (int)v; }
   else if(k == "sp") sp = v;
   else if(k == "trade_from") tradeFrom = (int)v;
  }

static std::string Num(double v) { char b[64]; snprintf(b, 64, "%.17g", v); return b; }

int main(int argc, char **argv)
  {
   if(argc < 2) { fprintf(stderr, "usage: bf_harness bars.txt key=value...\n"); return 2; }
   BfParams p;
   BfDefaultParams(p);
   BfEngineParams ep;
   ep.length = p.length; ep.visBoxes = p.visBoxes; ep.fvgMode = BF_FVGTYPE_FVG;
   ep.showFVG = true; ep.bpr = true; ep.fvgStyled = false;
   double sp = 0.10;
   int tradeFrom = 0;
   for(int i = 2; i < argc; i++) SetParam(p, ep, sp, tradeFrom, argv[i]);
   std::vector<double> O, H, L, C;
   FILE *f = fopen(argv[1], "r");
   if(!f) return 2;
   double a, b, c, d;
   while(fscanf(f, "%lf %lf %lf %lf", &a, &b, &c, &d) == 4) { O.push_back(a); H.push_back(b); L.push_back(c); C.push_back(d); }
   fclose(f);
   StateS st;
   ResetState(st, ep);
   static CBfDetector det;
   det.Init(p, tradeFrom);
   for(int u = 0; u < (int)O.size(); u++)
     {
      BfEngineEvents ev;
      BfClearEngineEvents(ev);
      ProcessBar(ep, st, u, O.data(), H.data(), L.data(), C.data(), ev);
      BfEnv env;
      BfClearEnv(env);
      env.slotFree = !det.HasOrderOrPosition();
      env.sessionEntryOk = true; env.sessionCancel = false; env.riskOk = true; env.spreadOk = true; env.sp = sp;
      det.OnBarClosed(u, O.data(), H.data(), L.data(), C.data(), st, ev, env);
      for(int k = 0; k < det.EventCount(); k++)
        {
         BfEvent e;
         det.GetEvent(k, e);
         bool px = (e.ev == BF_EV_PLACE_LIMIT || e.ev == BF_EV_MARKET);
         printf("{\"n\":%d,\"id\":%d,\"ev\":\"%s\",\"dir\":%d,\"src\":\"%s\",\"reason\":%s,\"P\":%s,\"SL\":%s,\"TP1\":%s,\"TP2\":%s}\n",
                e.n, e.id, BfEventName(e.ev).c_str(), e.dir, BfSourceName(e.src).c_str(),
                e.reason == BF_R_NONE ? "null" : ("\"" + BfReasonName(e.reason) + "\"").c_str(),
                px ? Num(e.P).c_str() : "null", px ? Num(e.SL).c_str() : "null",
                px ? Num(e.TP1).c_str() : "null", px ? Num(e.TP2).c_str() : "null");
        }
      det.ClearEvents();
      det.ClearIntents();
     }
   fprintf(stderr, "lost events %d intents %d\n", det.LostEvents(), det.LostIntents());
   return 0;
  }
