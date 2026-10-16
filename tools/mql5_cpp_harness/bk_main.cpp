// Drives the pure modules of mql5/BprFvgEA v2 (BfDefines, BfEngine, BfDetector) bar by bar under the parity-harness
// executor of research/indicators/BPR_BREAKOUT_FIB_SPEC.md section 7 and prints the detector's event records as JSON
// lines, then one "STATS" line with the diagnostic counters. Usage: bk_harness <bars.txt> key=value ...
#include "bf_pure.cpp"
#include <vector>
#include <map>
#include <cstdlib>
#include <cstring>

static int sessCancelBar = -1, sessOffBar = -1;   // v5 tests: one bar with env.sessionCancel / !env.sessionEntryOk
static bool extOut = false;                        // v7 tests: extra fields (never in the parity runs)

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
   else if(k == "anticipate") p.anticipate = v != 0;                 // v5, EA only (no Python counterpart)
   else if(k == "leg_break_on_close") p.legBreakOnClose = v != 0;    // v5, EA only (no Python counterpart)
   else if(k == "setup_type") p.setupType = (int)v;                  // v6, EA only: 0 CONT, 1 REVERSAL, 2 BOTH
   else if(k == "touch_entry") p.touchEntry = v != 0;                // v6, EA only
   else if(k == "touch_rr") p.touchTargetRR = v;                     // v6, EA only
   else if(k == "rev_level") p.revLevel = (int)v;                    // v7, EA only: 0 DEEPEST, 1 T1, 2 LAST
   else if(k == "rev_reject") p.revNeedReject = v != 0;              // v7, EA only
   else if(k == "t1_wait") p.t1WaitBars = (int)v;                    // v8, EA only: -1 = v7, 0 = no limit
   else if(k == "rev_fvg") p.revNeedFvg = v != 0;                    // v8, EA only
   else if(k == "ext") extOut = v != 0;                              // v7 tests: + kind / zdir / lvl / lvlBar per record
   else if(k == "length") { p.length = (int)v; ep.length = (int)v; }
   else if(k == "vis_boxes") { p.visBoxes = (int)v; ep.visBoxes = (int)v; }
   else if(k == "sp") sp = v;
   else if(k == "trade_from") tradeFrom = (int)v;
   else if(k == "hold_bars") holdBars = (int)v;
   else if(k == "sess_cancel") sessCancelBar = (int)v;
   else if(k == "sess_off") sessOffBar = (int)v;
  }

static std::string Num(double v) { char b[64]; snprintf(b, 64, "%.17g", v); return b; }

struct HOrd { double P, SL, TP; int dir, bar; };
// v6 touch entry: a market order decided on bar 'bar', opened at the next bar's open, then like a filled level
struct HTouch { int id, dir, bar; double SL, TP, P; bool open; };

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
   std::vector<HTouch> touch;                           // v6: at most one (slot rule); printed as H_TOUCH_* lines
   auto hline = [&](int n, const HTouch &t, const char *ev)
     {
      printf("{\"n\":%d,\"id\":%d,\"ev\":\"%s\",\"dir\":%d,\"k\":0,\"reason\":null,\"P\":%s,\"SL\":%s,\"TP\":%s,\"O\":null,\"X\":null}\n",
             n, t.id, ev, t.dir, Num(t.P).c_str(), Num(t.SL).c_str(), Num(t.TP).c_str());
     };
   auto flush = [&]()
     {
      for(int k = 0; k < det.EventCount(); k++)
        {
         BfEvent e;
         det.GetEvent(k, e);
         bool px = (e.ev == BF_EV_PLACE_LIMIT || e.ev == BF_EV_TOUCH_ENTRY);
         bool ox = (e.ev == BF_EV_PLACE_LIMIT || e.ev == BF_EV_CONFIRM);
         printf("{\"n\":%d,\"id\":%d,\"ev\":\"%s\",\"dir\":%d,\"k\":%d,\"reason\":%s,\"P\":%s,\"SL\":%s,\"TP\":%s,\"O\":%s,\"X\":%s",
                e.n, e.id, BfEventName(e.ev).c_str(), e.dir, e.k,
                e.reason == BF_R_NONE ? "null" : ("\"" + BfReasonName(e.reason) + "\"").c_str(),
                px ? Num(e.P).c_str() : "null", px ? Num(e.SL).c_str() : "null", px ? Num(e.TP).c_str() : "null",
                ox ? Num(e.O).c_str() : "null", ox ? Num(e.X).c_str() : "null");
         if(extOut)
            printf(",\"kind\":%d,\"zdir\":%d,\"lvl\":%s,\"lvlBar\":%d", e.kind, e.zdir, Num(e.lvl).c_str(), e.lvlBar);
         printf("}\n");
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
      // v6 touch entries: open at this bar's open (decided on an earlier bar), exits from the next bar on
      for(auto it = touch.begin(); it != touch.end();)
        {
         HTouch &t = *it;
         if(!t.open)
           {
            double e = (t.dir > 0) ? O[u] + sp : O[u];
            double risk = t.dir * (e - t.SL);
            if(risk <= 0.0) { hline(u, t, "H_TOUCH_SKIP"); it = touch.erase(it); continue; }
            t.P = e; t.TP = e + t.dir * p.touchTargetRR * risk; t.open = true; t.bar = u;
            hline(u, t, "H_TOUCH_OPEN");
            ++it;
            continue;
           }
         bool out = false;
         if(t.bar < u)
           {
            if(t.dir > 0) out = (l <= t.SL || h >= t.TP || u - t.bar >= holdBars);
            else out = (h + sp >= t.SL || l + sp <= t.TP || u - t.bar >= holdBars);
           }
         if(out) { hline(u, t, "H_TOUCH_CLOSE"); it = touch.erase(it); }
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
      env.slotFree = !det.HasOrderOrPosition() && touch.empty();
      // v5 anticipate: the setup whose own pending limits alone hold the slot; v6 touch entry: or whose own touch
      // position does (the EA reads both from its context, hedging accounts)
      env.slotOwner = 0;
      if(!env.slotFree && (p.anticipate || p.touchEntry))
        {
         int occ = det.OccupyingId();
         int tid = touch.empty() ? 0 : touch[0].id;
         int own = 0;
         bool ok = (occ >= 0);
         if(ok && occ > 0 && (det.PhaseOf(occ) != BF_PH_ORDERED || !p.anticipate)) ok = false;
         if(ok && occ > 0 && tid > 0 && occ != tid) ok = false;
         if(ok) own = (occ > 0) ? occ : tid;
         env.slotOwner = own;
        }
      env.sessionEntryOk = (u != sessOffBar); env.sessionCancel = (u == sessCancelBar);
      env.riskOk = true; env.spreadOk = true; env.sp = sp;
      det.OnBarClosed(u, O.data(), H.data(), L.data(), C.data(), st, ev, env);
      for(int k = 0; k < det.IntentCount(); k++)
        {
         BfIntent it;
         det.GetIntent(k, it);
         std::pair<int, int> key(it.id, it.k);
         if(it.type == BF_EV_PLACE_LIMIT) pend[key] = HOrd{it.P, it.SL, it.TP, it.dir, u};
         else if(it.type == BF_EV_CANCEL) pend.erase(key);
         else if(it.type == BF_EV_TOUCH_ENTRY) touch.push_back(HTouch{it.id, it.dir, u, it.SL, it.TP, it.P, false});
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
