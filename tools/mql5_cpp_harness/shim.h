// Stubs for the MT5 API used by LuxAlgo_BPR.mq5, so its logic compiles with g++ (see README.md). Not MT5.
#pragma once
#include <cstdio>
#include <cmath>
#include <cfloat>
#include <string>
#include <set>
#include <sstream>
#include <iostream>
#define MAXBARS 20000
typedef unsigned int color;
typedef long long datetime;
using string = std::string;
#define RGBC(r,g,b) ((color)(((b)<<16)|((g)<<8)|(r)))
#define clrNONE ((color)0xFFFFFFFF)
#define clrWhite ((color)0xFFFFFF)
#define EMPTY_VALUE DBL_MAX
enum ENUM_LINE_STYLE { STYLE_SOLID = 0, STYLE_DASH = 1, STYLE_DOT = 2 };
enum { OBJ_RECTANGLE = 1, OBJ_TEXT = 2, OBJ_TREND = 3 };
enum { OBJPROP_SELECTABLE = 1, OBJPROP_SELECTED, OBJPROP_HIDDEN, OBJPROP_WIDTH, OBJPROP_COLOR, OBJPROP_FILL,
       OBJPROP_BACK, OBJPROP_STYLE, OBJPROP_TOOLTIP, OBJPROP_ANCHOR, OBJPROP_FONTSIZE, OBJPROP_FONT, OBJPROP_TEXT,
       OBJPROP_RAY_LEFT, OBJPROP_RAY_RIGHT };
enum { ANCHOR_CENTER = 8, CHART_COLOR_BACKGROUND = 100, INDICATOR_DATA = 0, PLOT_ARROW = 1, PLOT_ARROW_SHIFT = 2,
       PLOT_EMPTY_VALUE = 3, INDICATOR_SHORTNAME = 4, INDICATOR_DIGITS = 5, INIT_SUCCEEDED = 0 };
#define FILE_WRITE 1
#define FILE_TXT 2
#define FILE_ANSI 4
#define INVALID_HANDLE (-1)
#define TIME_DATE 1
#define TIME_MINUTES 2
static string _Symbol = "TEST/SYM";
static int _Period = 1;
static int _Digits = 2;
static std::set<string> g_objs;
static int g_alerts = 0;
static string g_lastAlert;
static string g_filesDir = ".";
template<typename T> bool ArraySetAsSeries(T, bool) { return true; }
template<size_t N> int ArrayInitialize(double (&a)[N], double v) { for(size_t i = 0; i < N; i++) a[i] = v; return (int)N; }
template<size_t N> bool SetIndexBuffer(int, double (&)[N], int) { return true; }
inline bool PlotIndexSetInteger(int, int, int) { return true; }
inline bool PlotIndexSetDouble(int, int, double) { return true; }
inline bool IndicatorSetString(int, const string &) { return true; }
inline bool IndicatorSetInteger(int, int) { return true; }
inline double MathAbs(double x) { return std::fabs(x); }
inline double MathMax(double a, double b) { return a > b ? a : b; }
inline double MathMin(double a, double b) { return a < b ? a : b; }
inline double MathRound(double x) { return std::round(x); }
inline string IntegerToString(long long v) { return std::to_string(v); }
inline string DoubleToString(double v, int d) { char b[64]; snprintf(b, 64, "%.*f", d, v); return b; }
inline string StringFormat(const char *f, double v) { char b[64]; snprintf(b, 64, f, v); return b; }
inline string EnumToString(int) { return "PERIOD_M1"; }
inline string TimeToString(datetime t, int) { return std::to_string(t); }
inline int StringFind(const string &s, const string &f) { size_t p = s.find(f); return p == string::npos ? -1 : (int)p; }
inline string StringSubstr(const string &s, int a) { return s.substr(a); }
inline int StringReplace(string &s, const string &f, const string &r) { int n = 0; size_t p = 0;
  while((p = s.find(f, p)) != string::npos) { s.replace(p, f.size(), r); p += r.size(); n++; } return n; }
inline int PeriodSeconds() { return 60; }
inline long long ChartGetInteger(long, int) { return 0; }
inline void ChartRedraw(long = 0) {}
inline void Alert(const string &m) { g_alerts++; g_lastAlert = m; }
inline int GetLastError() { return 0; }
inline int ObjectFind(long, const string &n) { return g_objs.count(n) ? 0 : -1; }
inline bool ObjectCreate(long, const string &n, int, int, datetime, double, datetime = 0, double = 0) { g_objs.insert(n); return true; }
inline bool ObjectMove(long, const string &, int, datetime, double) { return true; }
inline bool ObjectDelete(long, const string &n) { return g_objs.erase(n) > 0; }
inline int ObjectsDeleteAll(long, const string &pfx) { int k = 0; for(auto it = g_objs.begin(); it != g_objs.end();) {
  if(it->compare(0, pfx.size(), pfx) == 0) { it = g_objs.erase(it); k++; } else ++it; } return k; }
inline bool ObjectSetInteger(long, const string &, int, long long) { return true; }
inline bool ObjectSetString(long, const string &, int, const string &) { return true; }
static FILE *g_fh = nullptr;
inline int FileOpen(const string &n, int) { g_fh = fopen((g_filesDir + "/" + n).c_str(), "w"); return g_fh ? 1 : -1; }
inline unsigned FileWriteString(int, const string &s) { fputs(s.c_str(), g_fh); return (unsigned)s.size(); }
inline void FileClose(int) { fclose(g_fh); g_fh = nullptr; }
template<typename... A> void Print(A... a) { std::ostringstream o; (o << ... << a); std::cerr << o.str() << "\n"; }
