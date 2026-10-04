//+------------------------------------------------------------------+
//| RiskManager.mqh — RSK-1..4 ([PROJECT] hard rules)                 |
//| * risk per trade (default 0.20% of equity) INCLUDING commission   |
//| * planned daily loss 1.00% (FX day = 17:00 New York) -> lockout   |
//| * size never increases after losses (depends on equity + stop)    |
//| Same rules as qe/risk.py (size_position, RiskManager).            |
//+------------------------------------------------------------------+
#ifndef VSEA_RISK_MQH
#define VSEA_RISK_MQH

#include "Defines.mqh"

class CRiskManager
  {
private:
   string            m_sym;
   double            m_riskPct;
   double            m_dayLossPct;
   double            m_commLotSide;
   int               m_maxTradesDay;
   long              m_fxDay;
   double            m_dayStartEq;
   int               m_tradesToday;
   bool              m_lockout;

public:
                     CRiskManager(void) : m_riskPct(0.20), m_dayLossPct(1.0), m_commLotSide(3.5), m_maxTradesDay(0),
                     m_fxDay(-1), m_dayStartEq(0), m_tradesToday(0), m_lockout(false) {}

   void              Init(const string sym, const double riskPct, const double dayLossPct, const double commLotSide,
                          const int maxTradesDay)
     {
      m_sym = sym;
      m_riskPct = MathMin(riskPct, 0.20);          // never above the research limit
      m_dayLossPct = MathMin(dayLossPct, 1.00);
      m_commLotSide = commLotSide;
      m_maxTradesDay = maxTradesDay;
     }

   double            RiskPct(void) const { return m_riskPct; }
   bool              Lockout(void) const { return m_lockout; }
   int               TradesToday(void) const { return m_tradesToday; }

   void              UpdateDay(const long fxDay)
     {
      double eq = AccountInfoDouble(ACCOUNT_EQUITY);
      if(fxDay != m_fxDay)
        {
         m_fxDay = fxDay;
         m_dayStartEq = eq;
         m_tradesToday = 0;
         m_lockout = false;
        }
      double loss = MathMax(0.0, m_dayStartEq - eq);
      if(!m_lockout && loss >= m_dayStartEq * m_dayLossPct / 100.0 - 1e-9)
         m_lockout = true;
     }

   //--- "" if a new trade with this planned risk is allowed, else the SAFE_* reason
   string            CheckNewTrade(const double plannedRisk)
     {
      if(m_lockout) return R_SAFE_DAILY_LOSS;
      if(m_maxTradesDay > 0 && m_tradesToday >= m_maxTradesDay) return R_SAFE_MAX_TRADES;
      double eq = AccountInfoDouble(ACCOUNT_EQUITY);
      double limit = m_dayStartEq * m_dayLossPct / 100.0;
      double remaining = limit - MathMax(0.0, m_dayStartEq - eq);
      double nominal = eq * m_riskPct / 100.0;
      if(MathMax(plannedRisk, nominal) > remaining + 1e-9) return R_SAFE_DAILY_LOSS;
      return "";
     }

   void              OnTradeOpened(void) { m_tradesToday++; }

   //--- account-currency loss for 1.0 lot when price moves `dist` against the position
   double            LossPerLot(const double dist) const
     {
      double tv = SymbolInfoDouble(m_sym, SYMBOL_TRADE_TICK_VALUE_LOSS);
      if(tv <= 0.0) tv = SymbolInfoDouble(m_sym, SYMBOL_TRADE_TICK_VALUE);
      double ts = SymbolInfoDouble(m_sym, SYMBOL_TRADE_TICK_SIZE);
      if(ts <= 0.0 || tv <= 0.0) return 0.0;
      return dist / ts * tv;
     }

   //--- RSK-1: largest volume (rounded DOWN) whose loss at the stop + round-trip commission <= budget
   double            SizeLots(const double stopDist, double &plannedRisk) const
     {
      plannedRisk = 0.0;
      if(stopDist <= 0) return 0.0;
      double eq = AccountInfoDouble(ACCOUNT_EQUITY);
      double budget = eq * m_riskPct / 100.0;
      double perLot = LossPerLot(stopDist) + 2.0 * m_commLotSide;
      if(perLot <= 0.0) return 0.0;
      double step = SymbolInfoDouble(m_sym, SYMBOL_VOLUME_STEP);
      double vmin = SymbolInfoDouble(m_sym, SYMBOL_VOLUME_MIN);
      double vmax = SymbolInfoDouble(m_sym, SYMBOL_VOLUME_MAX);
      double vlim = SymbolInfoDouble(m_sym, SYMBOL_VOLUME_LIMIT);
      if(step <= 0) step = 0.01;
      double lots = MathFloor(budget / perLot / step + 1e-9) * step;
      lots = MathMin(lots, vmax);
      if(vlim > 0) lots = MathMin(lots, vlim);
      if(lots < vmin - 1e-12) return 0.0;              // never round UP to the minimum
      int digits = (int)MathMax(0.0, MathCeil(-MathLog10(step)));
      lots = NormalizeDouble(lots, digits);
      plannedRisk = lots * perLot;
      return lots;
     }
  };

#endif
