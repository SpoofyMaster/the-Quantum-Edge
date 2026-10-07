// Drives OnInit/OnCalculate of the transliterated LuxAlgo_BPR.mq5 like MT5 does and prints the states as JSON lines.
// Usage: harness <bars.txt> <mode 0=Present|1=Historical> <length> <fvg 0|1=IFVG> <vis> <bpr 0|1> <showFVG 0|1>
//        <live 0|1> <K = bars at load> <presentBars> <ticks per bar> <reload at rates_total or -1> <export 0|1>
#include "lxbpr.cpp"
#include <vector>
#include <cstdlib>
static double O[MAXBARS], H[MAXBARS], L[MAXBARS], C[MAXBARS];
static datetime T[MAXBARS];
static long TV[MAXBARS], RV[MAXBARS];
static int SP[MAXBARS];
static std::vector<double> FO, FH, FL, FC;

static string num(double v) { char b[64]; snprintf(b, 64, "%.17g", v); return b; }
static string zoneJson(const ZoneS &z) {
  if(!z.box.exists) return "[0,null,null,null,null," + string(z.active ? "1" : "0") + ",null,null,null]";
  return "[1," + std::to_string(z.box.left) + "," + num(z.box.top) + "," + std::to_string(z.box.right) + "," +
         num(z.box.bottom) + "," + (z.active ? "1" : "0") + "," + (z.posNa ? string("null") : std::to_string(z.pos)) +
         ",\"" + BorderName(z.box.border) + "\"," + (z.box.brokenFill ? "1" : "0") + "]";
}
static string arrJson(const ZoneS *a, int cnt) {
  string s = "["; for(int i = 0; i < cnt; i++) { if(i) s += ","; s += zoneJson(a[i]); } return s + "]";
}
static void emit(const char *tag, int n, const StateS &s) {
  printf("{\"t\":\"%s\",\"n\":%d,\"fu\":%s,\"fd\":%s,\"bu\":%s,\"bd\":%s}\n", tag, n, arrJson(s.fu, s.nFu).c_str(),
         arrJson(s.fd, s.nFd).c_str(), arrJson(s.bu, s.nBu).c_str(), arrJson(s.bd, s.nBd).c_str());
}
int main(int argc, char **argv) {
  if(argc < 14) { fprintf(stderr, "usage\n"); return 2; }
  const char *bf = argv[1];
  InpMode = (ENUM_LXB_MODE)atoi(argv[2]);
  InpLength = atoi(argv[3]);
  InpFvgType = (ENUM_LXB_FVGTYPE)atoi(argv[4]);
  InpVisibleBoxes = atoi(argv[5]);
  InpBPR = atoi(argv[6]) != 0;
  InpShowFVG = atoi(argv[7]) != 0;
  InpLiveBar = atoi(argv[8]) != 0;
  int K = atoi(argv[9]);
  InpPresentBars = atoi(argv[10]);
  int ticks = atoi(argv[11]);
  int reloadAt = atoi(argv[12]);
  InpExportCSV = atoi(argv[13]) != 0;
  InpShowDisplacement = true;
  InpAlertNewBPR = true;
  InpFib = FIB_BPR;
  FILE *f = fopen(bf, "r");
  double a, b, c, d;
  while(fscanf(f, "%lf %lf %lf %lf", &a, &b, &c, &d) == 4) { FO.push_back(a); FH.push_back(b); FL.push_back(c); FC.push_back(d); }
  fclose(f);
  int N = (int)FO.size();
  for(int i = 0; i < N; i++) { O[i] = FO[i]; H[i] = FH[i]; L[i] = FL[i]; C[i] = FC[i]; T[i] = 1700000000LL + 60LL * i; }
  OnInit();
  g_now = T[K - 1];
  int prev = OnCalculate(K, 0, T, O, H, L, C, TV, RV, SP);
  emit("C", K - 2, g_state);
  if(InpLiveBar) emit("L", K - 1, g_tmp);
  int alertsAtLoad = g_alerts;
  for(int r = K + 1; r <= N; r++) {
    int fb = r - 1;
    for(int t = 0; t < ticks; t++) {
      if(t == ticks - 1) { O[fb] = FO[fb]; H[fb] = FH[fb]; L[fb] = FL[fb]; C[fb] = FC[fb]; }
      else {
        double fr = (double)(t + 1) / (double)ticks;
        double o = FO[fb], ct = o + (FC[fb] - o) * fr;
        O[fb] = o; C[fb] = ct;
        H[fb] = std::max(std::max(o, ct), o + (FH[fb] - o) * fr);
        L[fb] = std::min(std::min(o, ct), o + (FL[fb] - o) * fr);
      }
      int pc = prev;
      if(reloadAt == r && t == 0) pc = 0;
      g_now = T[r - 1];
      prev = OnCalculate(r, pc, T, O, H, L, C, TV, RV, SP);
      if(t == 0) emit("C", r - 2, g_state);
    }
    if(InpLiveBar) emit("L", r - 1, g_tmp);
  }
  for(int n = 0; n < N - 1; n++)
    if(g_bufUp[n] != EMPTY_VALUE || g_bufDn[n] != EMPTY_VALUE)
      printf("{\"t\":\"D\",\"n\":%d,\"u\":%d,\"d\":%d}\n", n, g_bufUp[n] != EMPTY_VALUE ? 1 : 0, g_bufDn[n] != EMPTY_VALUE ? 1 : 0);
  printf("{\"t\":\"A\",\"load\":%d,\"total\":%d,\"perStart\":%d,\"objs\":%d}\n", alertsAtLoad, g_alerts, g_perStart, (int)g_objs.size());
  return 0;
}
