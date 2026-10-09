//+------------------------------------------------------------------+
//| BfTrade.mqh                                                      |
//| BprFvgEA: order execution through CTrade (spec s.5)              |
//+------------------------------------------------------------------+
//
// Part of BprFvgEA (distributed as a whole under CC BY-NC-SA 4.0 because it includes a port of LuxAlgo code; see
// BfEngine.mqh). This file contains no LuxAlgo logic. Adapted from mql5/VideoStrategyEA/include/TradeManager.mqh.
//
// * filling mode from the symbol; prices normalised to the tick;
// * stops / freeze levels and margin checked BEFORE sending;
// * the account is checked again before EVERY send (Permitted(), fail closed): orders go out only in the Strategy
//   Tester, or when the terminal is connected, the account is known (login > 0) and its trade mode is DEMO. An
//   account that is not known yet (AccountInfoInteger returns 0 = ACCOUNT_TRADE_MODE_DEMO before the login) is
//   log-only, and so are REAL and CONTEST accounts. Refresh() recomputes tradingAllowed / modeNote on every tick.
//   There is deliberately NO input to change this: live trading needs a separate, explicit human approval (CLAUDE.md);
// * only entry failures (market / limit orders) count towards the order-error breaker; management actions (close,
//   partial close, stop modify, order delete) and refusals by the account guard never do.
//+------------------------------------------------------------------+
#ifndef BF_TRADE_MQH
#define BF_TRADE_MQH

#include <Trade/Trade.mqh>
#include "BfDefines.mqh"

class CBfTrade
  {
private:
   CTrade            m_trade;
   string            m_sym;
   long              m_magic;
   int               m_dev;
   int               m_errors;
   int               m_maxErrors;
   bool              m_breaker;
   ulong             m_lastDeal;

public:
   bool              tradingAllowed;
   string            modeNote;
   string            lastError;

private:
   //--- entries (market / limit orders): failures count towards the breaker
   void              OnResult(const bool ok, const string what)
     {
      if(ok)
        {
         m_errors = 0;
         return;
        }
      m_errors++;
      lastError = what + " retcode=" + IntegerToString((long)m_trade.ResultRetcode()) + " " +
                  m_trade.ResultRetcodeDescription();
      if(m_errors >= m_maxErrors)
         m_breaker = true;
     }

   //--- management (close, partial close, stop modify, delete): never counts towards the entry breaker
   void              OnMgmtResult(const bool ok, const string what)
     {
      if(ok)
         return;
      lastError = what + " retcode=" + IntegerToString((long)m_trade.ResultRetcode()) + " " +
                  m_trade.ResultRetcodeDescription();
     }

   //--- 0 tester / optimisation, 1 account not known yet, 2 demo, 3 any other account (real, contest)
   int               ModeCode(void)
     {
      if((bool)MQLInfoInteger(MQL_TESTER) || (bool)MQLInfoInteger(MQL_OPTIMIZATION))
         return(0);
      if(!(bool)TerminalInfoInteger(TERMINAL_CONNECTED))
         return(1);
      if(AccountInfoInteger(ACCOUNT_LOGIN) <= 0)
         return(1);
      if((ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_DEMO)
         return(2);
      return(3);
     }

   string            ModeText(const int code)
     {
      if(code == 0)
         return("TESTER");
      if(code == 1)
         return("WAITING FOR ACCOUNT: LOG-ONLY");
      if(code == 2)
         return("DEMO");
      return("REAL: LOG-ONLY");
     }

   string            Refusal(void)
     {
      return("not sent: trading not permitted (" + ModeText(ModeCode()) + ")");
     }

   double            MinStopDist(void)
     {
      double pt = SymbolInfoDouble(m_sym, SYMBOL_POINT);
      return((double)SymbolInfoInteger(m_sym, SYMBOL_TRADE_STOPS_LEVEL) * pt);
     }

public:
                     CBfTrade(void)
     {
      m_sym          = "";
      m_magic        = 0;
      m_dev          = 30;
      m_errors       = 0;
      m_maxErrors    = 3;
      m_breaker      = false;
      m_lastDeal     = 0;
      tradingAllowed = false;
      modeNote       = "";
      lastError      = "";
     }

   //--- spec "Hard rules": true only in the tester or on a connected, known DEMO account (fail closed)
   bool              Permitted(void)
     {
      int code = ModeCode();
      return(code == 0 || code == 2);
     }

   //--- re-evaluated on every tick (OnTick) and in Init: never latched
   void              Refresh(void)
     {
      int code = ModeCode();
      tradingAllowed = (code == 0 || code == 2);
      modeNote       = ModeText(code);
      m_trade.SetMarginMode();                    // the margin mode is 0 (netting) until the account is known
     }

   bool              Init(const string sym, const long magic, const int deviationPts, const int maxErrors)
     {
      m_sym       = sym;
      m_magic     = magic;
      m_dev       = (deviationPts > 0) ? deviationPts : 0;
      m_maxErrors = (maxErrors > 1) ? maxErrors : 1;
      m_errors    = 0;
      m_breaker   = false;
      m_lastDeal  = 0;
      lastError   = "";
      m_trade.SetExpertMagicNumber((ulong)magic);
      m_trade.SetDeviationInPoints((ulong)m_dev);
      m_trade.SetTypeFillingBySymbol(sym);
      m_trade.LogLevel(LOG_LEVEL_ERRORS);
      Refresh();
      return(true);
     }

   //--- CTrade::PositionClosePartial works on hedging accounts only
   bool              IsHedging(void)
     {
      return((ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE) == ACCOUNT_MARGIN_MODE_RETAIL_HEDGING);
     }

   bool              Breaker(void)
     {
      return(m_breaker);
     }

   void              ResetBreaker(void)
     {
      m_breaker = false;
      m_errors  = 0;
     }

   ulong             LastDeal(void)
     {
      return(m_lastDeal);
     }

   double            TickSize(void)
     {
      double ts = SymbolInfoDouble(m_sym, SYMBOL_TRADE_TICK_SIZE);
      if(ts > 0.0)
         return(ts);
      return(SymbolInfoDouble(m_sym, SYMBOL_POINT));
     }

   int               PriceDigits(void)
     {
      return((int)SymbolInfoInteger(m_sym, SYMBOL_DIGITS));
     }

   double            NormalizePrice(const double price)
     {
      double ts = TickSize();
      if(ts <= 0.0)
         return(NormalizeDouble(price, PriceDigits()));
      return(NormalizeDouble(MathRound(price / ts) * ts, PriceDigits()));
     }

   //--- volume rounded DOWN to the step
   double            FloorVolume(const double vol)
     {
      double step = SymbolInfoDouble(m_sym, SYMBOL_VOLUME_STEP);
      if(step <= 0.0)
         step = 0.01;
      int digits = (int)MathMax(0.0, MathCeil(-MathLog10(step) - 1e-9));
      return(NormalizeDouble(MathFloor(vol / step + 1e-9) * step, digits));
     }

   //--- volume rounded UP to the step
   double            CeilVolume(const double vol)
     {
      double step = SymbolInfoDouble(m_sym, SYMBOL_VOLUME_STEP);
      if(step <= 0.0)
         step = 0.01;
      int digits = (int)MathMax(0.0, MathCeil(-MathLog10(step) - 1e-9));
      return(NormalizeDouble(MathCeil(vol / step - 1e-9) * step, digits));
     }

   double            VolumeStep(void)
     {
      double step = SymbolInfoDouble(m_sym, SYMBOL_VOLUME_STEP);
      if(step <= 0.0)
         step = 0.01;
      return(step);
     }

   double            MinVolume(void)
     {
      return(SymbolInfoDouble(m_sym, SYMBOL_VOLUME_MIN));
     }

   //--- a pending limit must sit on the right side of the market, at least the stops level away
   bool              PendingPriceOk(const int dir, const double price)
     {
      MqlTick tk;
      if(!SymbolInfoTick(m_sym, tk))
         return(false);
      double minDist = MinStopDist();
      if(dir > 0)
         return(price < tk.ask && tk.ask - price >= minDist);
      return(price > tk.bid && price - tk.bid >= minDist);
     }

   //--- SL / TP on the exit side of the reference price, at least the stops level away
   bool              StopsOk(const int dir, const double ref, const double sl, const double tp)
     {
      double minDist = MinStopDist();
      if(dir > 0)
         return(ref - sl >= minDist && ref - sl > 0.0 && tp - ref >= minDist && tp - ref > 0.0);
      return(sl - ref >= minDist && sl - ref > 0.0 && ref - tp >= minDist && ref - tp > 0.0);
     }

   //--- a new SL of an open position: on the exit side of the market and outside the stops / freeze levels
   bool              ModifySlOk(const int dir, const double sl)
     {
      MqlTick tk;
      if(!SymbolInfoTick(m_sym, tk))
         return(false);
      double pt      = SymbolInfoDouble(m_sym, SYMBOL_POINT);
      double minDist = MathMax(MinStopDist(), (double)SymbolInfoInteger(m_sym, SYMBOL_TRADE_FREEZE_LEVEL) * pt);
      if(dir > 0)
         return(tk.bid - sl > minDist);
      return(sl - tk.ask > minDist);
     }

   bool              MarginOk(const int dir, const double lots, const double price)
     {
      double margin = 0.0;
      ENUM_ORDER_TYPE type = (dir > 0) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
      if(!OrderCalcMargin(type, m_sym, lots, price, margin))
         return(false);
      return(margin <= AccountInfoDouble(ACCOUNT_MARGIN_FREE));
     }

   //--- this EA's open position (symbol + magic)
   bool              SelectPosition(ulong &ticket)
     {
      int i;
      ulong tk;
      for(i = PositionsTotal() - 1; i >= 0; i--)
        {
         tk = PositionGetTicket(i);
         if(tk == 0)
            continue;
         if(PositionGetString(POSITION_SYMBOL) != m_sym)
            continue;
         if(PositionGetInteger(POSITION_MAGIC) != m_magic)
            continue;
         ticket = tk;
         return(true);
        }
      ticket = 0;
      return(false);
     }

   //--- this EA's pending order (symbol + magic)
   bool              SelectPendingOrder(ulong &ticket)
     {
      int i;
      ulong tk;
      for(i = OrdersTotal() - 1; i >= 0; i--)
        {
         tk = OrderGetTicket(i);
         if(tk == 0)
            continue;
         if(OrderGetString(ORDER_SYMBOL) != m_sym)
            continue;
         if(OrderGetInteger(ORDER_MAGIC) != m_magic)
            continue;
         ticket = tk;
         return(true);
        }
      ticket = 0;
      return(false);
     }

   //--- market order with SL / TP attached; requotes retried (at most 3 attempts)
   bool              OpenMarket(const int dir, const double lots, const double sl, const double tp, const string comment)
     {
      int     attempt;
      MqlTick tk;
      bool    ok;
      uint    rc;
      double  price;
      m_lastDeal = 0;
      if(!Permitted())
        {
         lastError = Refusal();
         return(false);
        }
      for(attempt = 0; attempt < 3; attempt++)
        {
         if(!SymbolInfoTick(m_sym, tk))
           {
            lastError = "no tick";
            return(false);
           }
         price = (dir > 0) ? tk.ask : tk.bid;
         if(dir > 0)
            ok = m_trade.Buy(lots, m_sym, price, NormalizePrice(sl), NormalizePrice(tp), comment);
         else
            ok = m_trade.Sell(lots, m_sym, price, NormalizePrice(sl), NormalizePrice(tp), comment);
         rc = m_trade.ResultRetcode();
         if(ok && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_DONE_PARTIAL || rc == TRADE_RETCODE_PLACED))
           {
            m_lastDeal = m_trade.ResultDeal();
            OnResult(true, "");
            return(true);
           }
         if(rc == TRADE_RETCODE_REQUOTE || rc == TRADE_RETCODE_PRICE_CHANGED || rc == TRADE_RETCODE_PRICE_OFF)
            continue;
         OnResult(false, "market order");
         return(false);
        }
      OnResult(false, "market order (requotes)");
      return(false);
     }

   //--- limit order with SL / TP; a server-side expiration is added as a safety net when the symbol allows it
   bool              PlaceLimit(const int dir, const double lots, const double price, const double sl, const double tp,
                                const datetime expiry, const string comment, ulong &ticket)
     {
      int  modes     = (int)SymbolInfoInteger(m_sym, SYMBOL_EXPIRATION_MODE);
      bool specified = ((modes & SYMBOL_EXPIRATION_SPECIFIED) != 0);
      ENUM_ORDER_TYPE_TIME tt = specified ? ORDER_TIME_SPECIFIED : ORDER_TIME_GTC;
      datetime expTime = specified ? expiry : (datetime)0;
      bool ok;
      uint rc;
      bool done;
      int  attempt;
      ticket = 0;
      if(!Permitted())
        {
         lastError = Refusal();
         return(false);
        }
      for(attempt = 0; attempt < 2; attempt++)
        {
         if(dir > 0)
            ok = m_trade.BuyLimit(lots, NormalizePrice(price), m_sym, NormalizePrice(sl), NormalizePrice(tp), tt,
                                  expTime, comment);
         else
            ok = m_trade.SellLimit(lots, NormalizePrice(price), m_sym, NormalizePrice(sl), NormalizePrice(tp), tt,
                                   expTime, comment);
         rc   = m_trade.ResultRetcode();
         done = (ok && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_PLACED));
         if(done)
           {
            OnResult(true, "");
            ticket = m_trade.ResultOrder();
            return(true);
           }
         // some servers refuse the symbol's market filling mode on pending orders: retry once with RETURN
         if(attempt == 0 && rc == TRADE_RETCODE_INVALID_FILL)
           {
            m_trade.SetTypeFilling(ORDER_FILLING_RETURN);
            continue;
           }
         break;
        }
      m_trade.SetTypeFillingBySymbol(m_sym);
      OnResult(false, "limit order");
      return(false);
     }

   //--- management actions below: guarded by Permitted(); failures never trip the entry breaker
   bool              DeleteOrder(const ulong ticket)
     {
      bool ok;
      if(!Permitted())
        {
         lastError = Refusal();
         return(false);
        }
      ok = m_trade.OrderDelete(ticket);
      OnMgmtResult(ok, "delete order");
      return(ok);
     }

   bool              ClosePosition(const ulong ticket)
     {
      bool ok;
      if(!Permitted())
        {
         lastError = Refusal();
         return(false);
        }
      ok = m_trade.PositionClose(ticket, (ulong)m_dev);
      OnMgmtResult(ok, "close position");
      return(ok);
     }

   //--- hedging accounts only (CTrade::PositionClosePartial refuses netting accounts without sending anything)
   bool              ClosePartial(const ulong ticket, const double volume)
     {
      bool ok;
      if(!Permitted())
        {
         lastError = Refusal();
         return(false);
        }
      if(!IsHedging())
        {
         lastError = "partial close: not available on a netting account";
         return(false);
        }
      m_trade.SetMarginMode();
      ok = m_trade.PositionClosePartial(ticket, volume, (ulong)m_dev);
      OnMgmtResult(ok, "partial close");
      return(ok);
     }

   bool              ModifyStops(const ulong ticket, const double sl, const double tp)
     {
      bool ok;
      if(!Permitted())
        {
         lastError = Refusal();
         return(false);
        }
      ok = m_trade.PositionModify(ticket, NormalizePrice(sl), NormalizePrice(tp));
      OnMgmtResult(ok, "modify stops");
      return(ok);
     }
  };

#endif
//+------------------------------------------------------------------+
