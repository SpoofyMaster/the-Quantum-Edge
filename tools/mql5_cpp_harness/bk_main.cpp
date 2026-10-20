// Drives the pure modules of mql5/BprFvgEA v2 (BfDefines, BfEngine, BfDetector) bar by bar under the parity-harness
// executor of research/indicators/BPR_BREAKOUT_FIB_SPEC.md section 7 and prints the detector's event records as JSON
// lines, then one "STATS" line with the diagnostic counters. Usage: bk_harness <bars.txt> key=value ...
#include "bf_pure.cpp"
#include <vector>
#include <string>
#include <algorithm>
#include <map>
#include <cstdlib>
#include <cstring>

static int sessCancelBar = -1, sessOffBar = -1;   // v5 tests: one bar with env.sessionCancel / !env.sessionEntryOk
static int sessOffFrom = -1;                       // 9.01 tests: !env.sessionEntryOk from this bar on
static int barSec = 60;                            // v10 tests: env.now = (u + 1) * barSec (the next bar's open)
static bool fillsOut = false;                      // v10 tests: print H_FILL lines (fills of levels)
static bool slotsOut = false;                      // v10 tests: print one H_SLOTS line per bar (multi mode)
static int riskOffFrom = -1, spreadOffFrom = -1;  // v10 tests: !env.riskOk / !env.spreadOk from this bar on
static bool intentsOut = false;                    // v10 tests: print one H_CANCEL line per cancel intent (with pt)
static int ghostBars = 0;                          // v10 tests: the first NEW_EXTREME cancel of a setup leaves its EA context
                                                   // busy for this many bars (a fill that raced the cancel): counted as used,
                                                   // listed in env.busyIds, and its decisions answered with NotifyRetry
static int retryBar = -1;                          // v10 tests: on this bar the executor answers every PLACE_LIMIT
                                                   // decision with NotifyRetry (no order sent), like the EA's waits
static bool keepOrders = false;                    // 9.01 tests: env.keepOrders = !env.sessionEntryOk (the EA's mapping
                                                   // with InpCancelAtSessionEnd = false, without its rollover timing)
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
   else if(k == "rev_rej_c") p.revRejCandles = (int)v;               // v9, EA only: 0 = v8
   else if(k == "max_setups") p.maxSetups = (int)v;                  // v10, EA only: 1 = one setup at a time
   else if(k == "pend_max_sec") p.pendingMaxSec = (int)v;            // v10, EA only: 0 = off
   else if(k == "bar_sec") barSec = (int)v;                          // v10 tests
   else if(k == "fills") fillsOut = v != 0;                          // v10 tests
   else if(k == "slots") slotsOut = v != 0;                          // v10 tests
   else if(k == "retry_bar") retryBar = (int)v;                      // v10 tests
   else if(k == "risk_off_from") riskOffFrom = (int)v;               // v10 tests
   else if(k == "spread_off_from") spreadOffFrom = (int)v;           // v10 tests
   else if(k == "intents") intentsOut = v != 0;                      // v10 tests
   else if(k == "ghost_bars") ghostBars = (int)v;                    // v10 tests
   else if(k == "ext") extOut = v != 0;                              // v7 tests: + kind / zdir / lvl / lvlBar per record
   else if(k == "length") { p.length = (int)v; ep.length = (int)v; }
   else if(k == "vis_boxes") { p.visBoxes = (int)v; ep.visBoxes = (int)v; }
   else if(k == "sp") sp = v;
   else if(k == "trade_from") tradeFrom = (int)v;
   else if(k == "hold_bars") holdBars = (int)v;
   else if(k == "sess_cancel") sessCancelBar = (int)v;
   else if(k == "sess_off") sessOffBar = (int)v;
   else if(k == "sess_off_from") sessOffFrom = (int)v;
   else if(k == "keep_orders") keepOrders = v != 0;
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
   int maxBusy = 0;                                     // v10 tests: the most setups ORDERED / FILLED at a bar's end
   std::map<int, int> ghost;                            // v10 tests (ghost_bars): setup id -> last bar of its busy context
   std::map<int, bool> ghosted;                         // a setup gets one ghost at most
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
            printf(",\"kind\":%d,\"zdir\":%d,\"lvl\":%s,\"lvlBar\":%d,\"rc\":%d,\"pt\":%d,\"dup\":%d", e.kind, e.zdir,
                   Num(e.lvl).c_str(), e.lvlBar, e.rejC, e.pendTime ? 1 : 0, e.dupOf);
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
            if(fillsOut)
               printf("{\"n\":%d,\"id\":%d,\"ev\":\"H_FILL\",\"dir\":%d,\"k\":%d,\"reason\":null,\"P\":%s,\"SL\":%s,\"TP\":%s,\"O\":null,\"X\":null}\n",
                      u, key.first, q.dir, key.second, Num(q.P).c_str(), Num(q.SL).c_str(), Num(q.TP).c_str());
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
      // v10: several setups at a time. A setup holds a slot while it is ORDERED / FILLED, or while its touch
      // position is open (the EA: its busy contexts, plus a touch position whose setup has none)
      for(auto it = ghost.begin(); it != ghost.end();)
         if(it->second < u) it = ghost.erase(it); else ++it;
      std::string ghostIds;
      if(p.maxSetups > 1)
        {
         int used = det.BusyCount();
         env.slotOwner = 0;
         for(const HTouch &t : touch)
           {
            int ph = det.PhaseOf(t.id);
            if(ph != BF_PH_ORDERED && ph != BF_PH_FILLED) used++;
            env.slotOwner = t.id;
           }
         // env.busyIds = the EA's busy contexts: every setup ORDERED / FILLED, plus the ghosts
         for(int k = 0; k < det.TrackedCount(); k++)
           {
            BfSetup bs;
            if(det.GetTracked(k, bs) && (bs.phase == BF_PH_ORDERED || bs.phase == BF_PH_FILLED) && env.nBusy < BF_MAX_BUSY)
               env.busyIds[env.nBusy++] = bs.id;
           }
         for(const auto &g : ghost)
           {
            int ph = det.PhaseOf(g.first);
            if(ph != BF_PH_ORDERED && ph != BF_PH_FILLED)
              {
               used++;
               if(env.nBusy < BF_MAX_BUSY) env.busyIds[env.nBusy++] = g.first;
              }
            ghostIds += (ghostIds.empty() ? "" : ",") + std::to_string(g.first);
           }
         env.freeSlots = (p.maxSetups > used) ? p.maxSetups - used : 0;
         env.slotFree = (env.freeSlots > 0);
        }
      env.now = (long)(u + 1) * barSec;
      std::string busyIds;                              // v10 tests (slots=1): the setups ORDERED / FILLED now
      for(int k = 0; k < det.TrackedCount(); k++)
        {
         BfSetup ts;
         if(det.GetTracked(k, ts) && (ts.phase == BF_PH_ORDERED || ts.phase == BF_PH_FILLED))
            busyIds += (busyIds.empty() ? "" : ",") + std::to_string(ts.id);
        }
      int blk0 = det.StatValue(BF_STAT_BLK_SLOT);
      env.sessionEntryOk = (u != sessOffBar && (sessOffFrom < 0 || u < sessOffFrom)); env.sessionCancel = (u == sessCancelBar);
      env.keepOrders = keepOrders && !env.sessionEntryOk;
      env.riskOk = (riskOffFrom < 0 || u < riskOffFrom); env.spreadOk = (spreadOffFrom < 0 || u < spreadOffFrom);
      env.sp = sp;
      det.OnBarClosed(u, O.data(), H.data(), L.data(), C.data(), st, ev, env);
      std::vector<int> retried;
      for(int k = 0; k < det.IntentCount(); k++)
        {
         BfIntent it;
         det.GetIntent(k, it);
         std::pair<int, int> key(it.id, it.k);
         if(it.type == BF_EV_PLACE_LIMIT && (u == retryBar || ghost.count(it.id)))
           {
            if(std::find(retried.begin(), retried.end(), it.id) == retried.end()) retried.push_back(it.id);
            continue;
           }
         if(it.type == BF_EV_CANCEL && ghostBars > 0 && it.reason == BF_R_NEW_EXTREME && it.k == 1 && !ghosted[it.id])
           {
            ghosted[it.id] = true;
            ghost[it.id] = u + ghostBars;
           }
         if(it.type == BF_EV_CANCEL && intentsOut)
            printf("{\"n\":%d,\"id\":%d,\"ev\":\"H_CANCEL\",\"dir\":%d,\"k\":%d,\"reason\":\"%s\",\"pt\":%d}\n", u, it.id,
                   it.dir, it.k, BfReasonName(it.reason).c_str(), it.pendTime ? 1 : 0);
         if(it.type == BF_EV_PLACE_LIMIT) pend[key] = HOrd{it.P, it.SL, it.TP, it.dir, u};
         else if(it.type == BF_EV_CANCEL) pend.erase(key);
         else if(it.type == BF_EV_TOUCH_ENTRY) touch.push_back(HTouch{it.id, it.dir, u, it.SL, it.TP, it.P, false});
        }
      det.ClearIntents();
      for(int id : retried) det.NotifyRetry(id);
      flush();
      if(det.BusyCount() > maxBusy) maxBusy = det.BusyCount();
      if(slotsOut)
         printf("{\"n\":%d,\"id\":0,\"ev\":\"H_SLOTS\",\"busy\":[%s],\"free\":%d,\"blk\":%d,\"after\":%d,\"owner\":%d,\"ghosts\":[%s]}\n", u,
                busyIds.c_str(), env.freeSlots, det.StatValue(BF_STAT_BLK_SLOT) - blk0, det.BusyCount(), env.slotOwner,
                ghostIds.c_str());
     }
   fprintf(stderr, "MAXBUSY %d\n", maxBusy);
   printf("STATS");
   for(int k = 0; k < BF_NSTAT; k++) printf(" %d", det.StatValue(k));
   printf("\n");
   fprintf(stderr, "lost events %d intents %d\n", det.LostEvents(), det.LostIntents());
   return 0;
  }
