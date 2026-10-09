//+------------------------------------------------------------------+
//| BfRisk.mqh                                                       |
//| BprFvgEA: position sizing and the daily-loss lockout (spec s.6)  |
//+------------------------------------------------------------------+
//
// Part of BprFvgEA (distributed as a whole under CC BY-NC-SA 4.0 because it includes a port of LuxAlgo code; see
// BfEngine.mqh). This file contains no LuxAlgo logic. Adapted from mql5/VideoStrategyEA/include/RiskManager.mqh.
//
// Hard rules (CLAUDE.md), with no input to override them:
//   * at most 0.20 % of equity per position, INCLUDING the round-trip commission (input capped at 0.20);
//   * planned daily loss 1.00 % (FX day = 17:00 New York) -> lockout for the rest of that FX day (capped at 1.00);
//   * size depends only on equity and stop distance: never larger after losses, never rounded UP to the minimum.
// Sizing (spec s.6, same formula as qe/risk.py size_position):
//   lots = floor( equity*risk% / ( LossPerLot(|P - SL| + slippage*tick) + 2*commission_per_lot_side ) / step ) * step
// The realised result of the FX day is rebuilt from this EA's deals in the account history, so it survives restarts.
// It is recomputed once per new bar and right before every order, so a restart before the history was synchronised
// cannot leave a stale lockout state for long.
// The FX-day baseline is committed only once the account is ready (equity > 0, see DayCheck in BprFvgEA.mq5); until
// then RiskOk() / CheckNewTrade() refuse every new trade (fail closed).
// The budget is PER EA INSTANCE (this symbol + magic): only ONE instance per account is supported, otherwise the
// account could lose a multiple of the 1.00 % planned daily loss.
//+------------------------------------------------------------------+
#ifndef BF_RISK_MQH
#define BF_RISK_MQH

#include "BfDefines.mqh"
#include "BfSession.mqh"

class CBfRisk
  {
private:
   string            m_sym;
   long              m_magic;
   double            m_riskPct;
   double            m_dayLossPct;
   double            m_commLotSide;
   int               m_maxTradesDay;
   long              m_fxDay;
   double            m_dayStartEq;
   double            m_realised;        // net P&L of this EA's deals in the current FX day (account currency)
   int               m_trades;          // positions opened by this EA in the current FX day (distinct position ids)
   bool              m_lockout;
   double            m_lastBudget;      // equity * risk% of the last SizeLots call (account currency)

public:
                     CBfRisk(void)
     {
      m_sym          = "";
      m_magic        = 0;
      m_riskPct      = 0.20;
      m_dayLossPct   = 1.00;
      m_commLotSide  = 3.50;
      m_maxTradesDay = 0;
      m_fxDay        = -1;
      m_dayStartEq   = 0.0;
      m_realised     = 0.0;
      m_trades       = 0;
      m_lockout      = false;
      m_lastBudget   = 0.0;
     }

   void              Init(const string sym, const long magic, const double riskPct, const double dayLossPct,
                          const double commLotSide, const int maxTradesDay)
     {
      m_sym          = sym;
      m_magic        = magic;
      m_riskPct      = MathMin(riskPct, 0.20);       // never above the research limit
      m_dayLossPct   = MathMin(dayLossPct, 1.00);
      m_commLotSide  = MathMax(commLotSide, 0.0);
      m_maxTradesDay = maxTradesDay;
      m_fxDay        = -1;
      m_dayStartEq   = 0.0;
      m_realised     = 0.0;
      m_trades       = 0;
      m_lockout      = false;
      m_lastBudget   = 0.0;
     }

   double            RiskPct(void)
     {
      return(m_riskPct);
     }

   bool              Lockout(void)
     {
      return(m_lockout);
     }

   int               TradesToday(void)
     {
      return(m_trades);
     }

   double            RealisedToday(void)
     {
      return(m_realised);
     }

   //--- a valid FX-day baseline exists (the account was ready when the day was committed)
   bool              Ready(void)
     {
      return(m_fxDay >= 0 && m_dayStartEq > 0.0);
     }

   double            LastBudget(void)
     {
      return(m_lastBudget);
     }

   double            DayLimit(void)
     {
      return(m_dayStartEq * m_dayLossPct / 100.0);
     }

   double            NominalRisk(void)
     {
      return(m_dayStartEq * m_riskPct / 100.0);
     }

   //--- today's realised result in units of the nominal risk per trade (panel)
   double            RealisedR(void)
     {
      double nominal = NominalRisk();
      if(nominal <= 0.0)
         return(0.0);
      return(m_realised / nominal);
     }

   //--- rebuilds the realised P&L and the trade count of the current FX day from the deal history
   void              Recompute(CBfSession &ses)
     {
      int      i;
      int      total;
      ulong    d;
      int      j;
      int      nIds = 0;
      bool     seen;
      ulong    pid;
      ulong    ids[];
      datetime now = TimeCurrent();
      long     entry;
      m_realised = 0.0;
      m_trades   = 0;
      if(!HistorySelect((datetime)((long)now - 4 * 86400), (datetime)((long)now + 3600)))
         return;
      total = HistoryDealsTotal();
      for(i = 0; i < total; i++)
        {
         d = HistoryDealGetTicket(i);
         if(d == 0)
            continue;
         if(HistoryDealGetString(d, DEAL_SYMBOL) != m_sym)
            continue;
         if(HistoryDealGetInteger(d, DEAL_MAGIC) != m_magic)
            continue;
         if(ses.FxDay((datetime)HistoryDealGetInteger(d, DEAL_TIME)) != m_fxDay)
            continue;
         entry = HistoryDealGetInteger(d, DEAL_ENTRY);
         if(entry == (long)DEAL_ENTRY_IN)
           {
            // a limit filled in several deals is one trade: count distinct position ids
            pid  = (ulong)HistoryDealGetInteger(d, DEAL_POSITION_ID);
            seen = false;
            for(j = 0; j < nIds; j++)
              {
               if(ids[j] == pid)
                 {
                  seen = true;
                  break;
                 }
              }
            if(!seen)
              {
               ArrayResize(ids, nIds + 1, 16);
               ids[nIds] = pid;
               nIds++;
              }
           }
         m_realised += HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_COMMISSION) +
                       HistoryDealGetDouble(d, DEAL_SWAP) + HistoryDealGetDouble(d, DEAL_FEE);
        }
      m_trades = nIds;
      if(!m_lockout && m_dayStartEq > 0.0 && -m_realised >= DayLimit() - 1e-9)
         m_lockout = true;
     }

   //--- commits a new FX day. false (nothing stored, retried by the caller) while the equity is not available:
   //    a 0 baseline is never stored.
   bool              UpdateDay(const long fxDay, CBfSession &ses)
     {
      double eq = AccountInfoDouble(ACCOUNT_EQUITY);
      if(fxDay == m_fxDay && m_dayStartEq > 0.0)
         return(true);
      if(eq <= 0.0)
         return(false);
      m_fxDay    = fxDay;
      m_lockout  = false;
      m_realised = 0.0;
      Recompute(ses);
      // equity at the start of the FX day: current equity minus what was already realised today (restart-safe)
      m_dayStartEq = eq - m_realised;
      if(m_dayStartEq <= 0.0)
         m_dayStartEq = eq;
      if(-m_realised >= DayLimit() - 1e-9 && m_realised < 0.0)
         m_lockout = true;
      return(true);
     }

   //--- after a trade closes / opens
   void              OnTradeEvent(CBfSession &ses)
     {
      Recompute(ses);
     }

   //--- spec s.4 step 5 "risk OK": no lockout, the trade limit is not reached, and one more full-risk loss
   //    still fits in the daily budget.
   bool              RiskOk(void)
     {
      if(!Ready())
         return(false);                                  // no valid baseline yet: fail closed
      if(m_lockout)
         return(false);
      if(m_maxTradesDay > 0 && m_trades >= m_maxTradesDay)
         return(false);
      double loss = MathMax(0.0, -m_realised);
      return(loss + NominalRisk() <= DayLimit() + 1e-9);
     }

   //--- spec s.6 pre-trade check: realised loss today + planned risk <= daily limit
   bool              CheckNewTrade(const double plannedRisk)
     {
      if(!Ready())
         return(false);                                  // no valid baseline yet: fail closed
      if(m_lockout)
         return(false);
      double loss = MathMax(0.0, -m_realised);
      return(loss + plannedRisk <= DayLimit() + 1e-9);
     }

   //--- account-currency loss for 1.0 lot when price moves 'dist' against the position
   double            LossPerLot(const double dist)
     {
      double tv = SymbolInfoDouble(m_sym, SYMBOL_TRADE_TICK_VALUE_LOSS);
      if(tv <= 0.0)
         tv = SymbolInfoDouble(m_sym, SYMBOL_TRADE_TICK_VALUE);
      double ts = SymbolInfoDouble(m_sym, SYMBOL_TRADE_TICK_SIZE);
      if(ts <= 0.0 || tv <= 0.0)
         return(0.0);
      return(dist / ts * tv);
     }

   //--- planned loss of 1.0 lot at the stop incl. the round-trip commission; 0 when the symbol data is not ready
   double            PerLotRisk(const double stopDist)
     {
      double loss = LossPerLot(stopDist);
      if(loss <= 0.0)
         return(0.0);
      return(loss + 2.0 * m_commLotSide);
     }

   //--- value of a 1.0 price move for 1.0 lot (account currency); 0 when the symbol data is not ready
   double            ValuePerPriceUnit(void)
     {
      return(LossPerLot(1.0));
     }

   //--- comm_price of spec s.4 step 5: round-trip commission per lot / value of a 1.0 price move per lot
   double            CommPrice(void)
     {
      double v = ValuePerPriceUnit();
      if(v <= 0.0)
         return(0.0);
      return(2.0 * m_commLotSide / v);
     }

   //--- spec s.6: largest volume (rounded DOWN to the step) whose loss at the stop + round-trip commission
   //    <= equity * risk%. Returns 0 when that is below the minimum volume (never rounded up).
   double            SizeLots(const double stopDist, double &plannedRisk)
     {
      plannedRisk  = 0.0;
      m_lastBudget = 0.0;
      if(stopDist <= 0.0)
         return(0.0);
      double eq     = AccountInfoDouble(ACCOUNT_EQUITY);
      double budget = eq * m_riskPct / 100.0;
      m_lastBudget  = budget;
      double perLot = LossPerLot(stopDist) + 2.0 * m_commLotSide;
      if(perLot <= 0.0)
         return(0.0);
      double step = SymbolInfoDouble(m_sym, SYMBOL_VOLUME_STEP);
      double vmin = SymbolInfoDouble(m_sym, SYMBOL_VOLUME_MIN);
      double vmax = SymbolInfoDouble(m_sym, SYMBOL_VOLUME_MAX);
      double vlim = SymbolInfoDouble(m_sym, SYMBOL_VOLUME_LIMIT);
      if(step <= 0.0)
         step = 0.01;
      double lots = MathFloor(budget / perLot / step + 1e-9) * step;
      if(vmax > 0.0)
         lots = MathMin(lots, MathFloor(vmax / step + 1e-9) * step);
      if(vlim > 0.0)
         lots = MathMin(lots, MathFloor(vlim / step + 1e-9) * step);
      if(lots < vmin - 1e-12 || lots <= 0.0)
         return(0.0);                                    // never round UP to the minimum
      int digits = (int)MathMax(0.0, MathCeil(-MathLog10(step) - 1e-9));
      lots = NormalizeDouble(lots, digits);
      plannedRisk = lots * perLot;
      return(lots);
     }
  };

#endif
//+------------------------------------------------------------------+
