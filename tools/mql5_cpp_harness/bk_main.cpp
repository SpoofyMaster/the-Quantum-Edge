// Drives the pure modules of mql5/BprFvgEA v2 (BfDefines, BfEngine, BfDetector) bar by bar under the parity-harness
// executor of research/indicators/BPR_BREAKOUT_FIB_SPEC.md section 7 and prints the detector's event records as JSON
// lines, then one "STATS" line with the diagnostic counters. Usage: bk_harness <bars.txt> key=value ...
#include "bf_pure.cpp"
#include <vector>
#include <map>
#include <cstdlib>
#include <cstring>

static void SetParam(BfParams &p, BfEngineParams &ep, double &sp, int &tradeFrom, int &holdBars, const char *kv)
  {
   std::string s(kv);
   size_t eq = s.find('=');
   if(eq == std::string::npos) return;
   std::string k = s.substr(0, eq);
   double v = atof(s.c_str() + eq + 1);
   if(k == "direction") p.direction = (int)v;
   else if(k == "max_touches") p.maxTouches = (int)v;
   else if(k == "confirm_closes") p.confirmCloses = (int)v;
   else if(k == "reject_before_break") p.rejectBeforeBreak = v != 0;
   else if(k == "fvg_rule") p.fvgRule = (int)v;
   else if(k == "setup_expiry_bars") p.setupExpiryBars = (int)v;
   else if(k == "leg_expiry_bars") p.legExpiryBars = (int)v;
   else if(k == "fib1") p.fib1 = v;
   else if(k == "fib2") p.fib2 = v;
   else if(k == "fib3") p.fib3 = v;
   else if(k == "stop_fib") p.stopFib = v;
   else if(k == "stop_buffer_ticks") p.stopBufferTicks = (int)v;
   else if(k == "target_fib") p.targetFib = v;
   else if(k == "min_rr") p.minRR = v;
   else if(k == "max_cost_r") p.maxCostR = v;
   else if(k == "slippage_ticks") p.slippageTicks = v;
   else if(k == "tick_size") p.tickSize = v;
   else if(k == "digits") p.digits = (int)v;
   else if(k == "comm_price") p.commPrice = v;
   else if(k == "use_session") p.useSession = v != 0;
   else if(k == "length") { p.length = (int)v; ep.length = (int)v; }
   else if(k == "vis_boxes") { p.visBoxes = (int)v; ep.visBoxes = (int)v; }
   else if(k == "sp") sp = v;
   else if(k == "trade_from") tradeFrom = (int)v;
   else if(k == "hold_bars") holdBars = (int)v;
  }

static std::string Num(double v) { char b[64]; snprintf(b, 64, "%.17g", v); return b; }

struct HOrd { double P, SL, TP; int dir, bar; };

int main(int argc, char **argv)
  {
   if(argc < 2) { fprintf(stderr, "usage: bk_harness bars.txt key=value...\n"); return 2; }
   BfParams p;
   BfDefaultParams(p);
   BfEngineParams ep;
   ep.length = p.length; ep.visBoxes = p.visBoxes; ep.fvgMode = BF_FVGTYPE_FVG;
   ep.showFVG = true; ep.bpr = true; ep.fvgStyled = false;
   double sp = 0.10;
   int tradeFrom = 0, holdBars = 120;
   for(int i = 2; i < argc; i++) SetParam(p, ep, sp, tradeFrom, holdBars, argv[i]);
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
   std::map<std::pair<int, int>, HOrd> pend, pos;      // (id, k), ordered like Python's sorted()
   auto flush = [&]()
     {
      for(int k = 0; k < det.EventCount(); k++)
        {
         BfEvent e;
         det.GetEvent(k, e);
         bool px = (e.ev == BF_EV_PLACE_LIMIT);
         bool ox = (e.ev == BF_EV_PLACE_LIMIT || e.ev == BF_EV_CONFIRM);
         printf("{\"n\":%d,\"id\":%d,\"ev\":\"%s\",\"dir\":%d,\"k\":%d,\"reason\":%s,\"P\":%s,\"SL\":%s,\"TP\":%s,\"O\":%s,\"X\":%s}\n",
                e.n, e.id, BfEventName(e.ev).c_str(), e.dir, e.k,
                e.reason == BF_R_NONE ? "null" : ("\"" + BfReasonName(e.reason) + "\"").c_str(),
                px ? Num(e.P).c_str() : "null", px ? Num(e.SL).c_str() : "null", px ? Num(e.TP).c_str() : "null",
                ox ? Num(e.O).c_str() : "null", ox ? Num(e.X).c_str() : "null");
        }
      det.ClearEvents();
     };
   for(int u = 0; u < (int)O.size(); u++)
     {
      double h = H[u], l = L[u];
      // exits of positions filled on an earlier bar
      for(auto it = pos.begin(); it != pos.end();)
        {
         const HOrd &q = it->second;
         bool out = false;
         if(q.bar < u)
           {
            if(q.dir > 0) out = (l <= q.SL || h >= q.TP || u - q.bar >= holdBars);
            else out = (h + sp >= q.SL || l + sp <= q.TP || u - q.bar >= holdBars);
           }
         if(out) { std::pair<int, int> key = it->first; it = pos.erase(it); det.NotifyClosed(key.first, key.second); }
         else ++it;
        }
      // fills of levels decided on an earlier bar
      for(auto it = pend.begin(); it != pend.end();)
        {
         const HOrd &q = it->second;
         bool hit = false;
         if(q.bar < u) hit = (q.dir > 0) ? (l + sp <= q.P) : (h >= q.P);
         if(hit)
           {
            std::pair<int, int> key = it->first;
            HOrd np = q; np.bar = u;
            pos[key] = np;
            it = pend.erase(it);
            det.NotifyFilled(key.first, key.second);
           }
         else ++it;
        }
      flush();
      BfEngineEvents ev;
      BfClearEngineEvents(ev);
      ProcessBar(ep, st, u, O.data(), H.data(), L.data(), C.data(), ev);
      BfEnv env;
      BfClearEnv(env);
      env.slotFree = !det.HasOrderOrPosition();
      env.sessionEntryOk = true; env.sessionCancel = false; env.riskOk = true; env.spreadOk = true; env.sp = sp;
      det.OnBarClosed(u, O.data(), H.data(), L.data(), C.data(), st, ev, env);
      for(int k = 0; k < det.IntentCount(); k++)
        {
         BfIntent it;
         det.GetIntent(k, it);
         std::pair<int, int> key(it.id, it.k);
         if(it.type == BF_EV_PLACE_LIMIT) pend[key] = HOrd{it.P, it.SL, it.TP, it.dir, u};
         else if(it.type == BF_EV_CANCEL) pend.erase(key);
        }
      det.ClearIntents();
      flush();
     }
   printf("STATS");
   for(int k = 0; k < BF_NSTAT; k++) printf(" %d", det.StatValue(k));
   printf("\n");
   fprintf(stderr, "lost events %d intents %d\n", det.LostEvents(), det.LostIntents());
   return 0;
  }
