//+------------------------------------------------------------------+
//| TradeManager.mqh — order execution and position management        |
//| ENT-1/2, SL-1, TP-1, MGT-1..3, SAF-2/4/5                          |
//| * filling mode from the symbol, prices normalized to tick size    |
//| * stops/freeze level and margin checks BEFORE sending             |
//| * requotes/price-changed retried (market orders, max 2)           |
//| * REAL accounts never receive orders (log-only); no input exists  |
//|   to override this: live trading needs separate human approval.   |
//+------------------------------------------------------------------+
#ifndef VSEA_TRADE_MQH
#define VSEA_TRADE_MQH

#include <Trade/Trade.mqh>
#include "Defines.mqh"

class CTradeManager
  {
private:
   CTrade            m_trade;
   string            m_sym;
   long              m_magic;
   int               m_deviation;
   int               m_consecutiveErrors;
   int               m_maxErrors;
   bool              m_breaker;

   double            Tick(void) const
     {
      double ts = SymbolInfoDouble(m_sym, SYMBOL_TRADE_TICK_SIZE);
      return (ts > 0) ? ts : SymbolInfoDouble(m_sym, SYMBOL_POINT);
     }

public:
   bool              tradingAllowed;
   string            modeNote;
   string            lastError;

                     CTradeManager(void) : m_magic(0), m_deviation(30), m_consecutiveErrors(0), m_maxErrors(3),
                     m_breaker(false), tradingAllowed(false) {}

   bool              Init(const string sym, const long magic, const int deviationPts, const int maxErrors)
     {
      m_sym = sym;
      m_magic = magic;
      m_deviation = deviationPts;
      m_maxErrors = maxErrors;
      m_trade.SetExpertMagicNumber((ulong)magic);
      m_trade.SetDeviationInPoints((ulong)MathMax(deviationPts, 0));
      m_trade.SetTypeFillingBySymbol(sym);
      m_trade.SetMarginMode();
      m_trade.LogLevel(LOG_LEVEL_ERRORS);
      bool tester = (bool)MQLInfoInteger(MQL_TESTER) || (bool)MQLInfoInteger(MQL_OPTIMIZATION);
      ENUM_ACCOUNT_TRADE_MODE mode = (ENUM_ACCOUNT_TRADE_MODE)AccountInfoInteger(ACCOUNT_TRADE_MODE);
      if(tester) { tradingAllowed = true; modeNote = "STRATEGY TESTER"; }
      else if(mode == ACCOUNT_TRADE_MODE_DEMO || mode == ACCOUNT_TRADE_MODE_CONTEST) { tradingAllowed = true; modeNote = "DEMO"; }
      else { tradingAllowed = false; modeNote = "REAL ACCOUNT: LOG-ONLY (no orders)"; }
      return true;
     }

   bool              Breaker(void) const { return m_breaker; }
   void              ResetBreaker(void) { m_breaker = false; m_consecutiveErrors = 0; }

   double            NormalizePrice(const double price) const
     {
      double ts = Tick();
      int digits = (int)SymbolInfoInteger(m_sym, SYMBOL_DIGITS);
      return NormalizeDouble(MathRound(price / ts) * ts, digits);
     }

   //--- SAF: stops level relative to the current market (SL/TP on the exit side)
   bool              StopsOk(const int dir, const double entryRef, const double sl, const double tp) const
     {
      double pt = SymbolInfoDouble(m_sym, SYMBOL_POINT);
      double minDist = (double)SymbolInfoInteger(m_sym, SYMBOL_TRADE_STOPS_LEVEL) * pt;
      if(minDist <= 0) return true;
      if(dir > 0) return (entryRef - sl) >= minDist && (tp - entryRef) >= minDist;
      return (sl - entryRef) >= minDist && (entryRef - tp) >= minDist;
     }

   bool              MarginOk(const int dir, const double lots, const double price) const
     {
      double margin = 0.0;
      ENUM_ORDER_TYPE type = (dir > 0) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
      if(!OrderCalcMargin(type, m_sym, lots, price, margin)) return false;
      return margin <= AccountInfoDouble(ACCOUNT_MARGIN_FREE);
     }

   //--- our open position (by symbol + magic)
   bool              SelectPosition(ulong &ticket) const
     {
      for(int i = PositionsTotal() - 1; i >= 0; i--)
        {
         ulong tk = PositionGetTicket(i);
         if(tk == 0) continue;
         if(PositionGetString(POSITION_SYMBOL) != m_sym) continue;
         if(PositionGetInteger(POSITION_MAGIC) != m_magic) continue;
         ticket = tk;
         return true;
        }
      ticket = 0;
      return false;
     }

   bool              SelectPendingOrder(ulong &ticket) const
     {
      for(int i = OrdersTotal() - 1; i >= 0; i--)
        {
         ulong tk = OrderGetTicket(i);
         if(tk == 0) continue;
         if(OrderGetString(ORDER_SYMBOL) != m_sym) continue;
         if(OrderGetInteger(ORDER_MAGIC) != m_magic) continue;
         ticket = tk;
         return true;
        }
      ticket = 0;
      return false;
     }

   void              OnResult(const bool ok, const string what)
     {
      if(ok) { m_consecutiveErrors = 0; return; }
      m_consecutiveErrors++;
      lastError = what + " retcode=" + IntegerToString((int)m_trade.ResultRetcode()) + " " + m_trade.ResultRetcodeDescription();
      if(m_consecutiveErrors >= m_maxErrors) m_breaker = true;
     }

   //--- ENT-1: market order with SL/TP attached. Returns true if a position was opened.
   bool              OpenMarket(const int dir, const double lots, const double sl, const double tp, const string comment)
     {
      for(int attempt = 0; attempt < 3; attempt++)
        {
         MqlTick tk;
         if(!SymbolInfoTick(m_sym, tk)) { lastError = "no tick"; return false; }
         double price = (dir > 0) ? tk.ask : tk.bid;
         bool ok = (dir > 0) ? m_trade.Buy(lots, m_sym, price, NormalizePrice(sl), NormalizePrice(tp), comment)
                             : m_trade.Sell(lots, m_sym, price, NormalizePrice(sl), NormalizePrice(tp), comment);
         uint rc = m_trade.ResultRetcode();
         if(ok && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_DONE_PARTIAL || rc == TRADE_RETCODE_PLACED))
           { OnResult(true, ""); return true; }
         if(rc == TRADE_RETCODE_REQUOTE || rc == TRADE_RETCODE_PRICE_CHANGED || rc == TRADE_RETCODE_PRICE_OFF)
            continue;
         OnResult(false, "market order");
         return false;
        }
      OnResult(false, "market order (requotes)");
      return false;
     }

   //--- ENT-2: limit order with SL/TP and expiration (falls back to GTC + manual expiry)
   bool              PlaceLimit(const int dir, const double lots, const double price, const double sl, const double tp,
                                const datetime expiry, const string comment, ulong &ticket)
     {
      int modes = (int)SymbolInfoInteger(m_sym, SYMBOL_EXPIRATION_MODE);
      bool specified = (modes & SYMBOL_EXPIRATION_SPECIFIED) != 0;
      ENUM_ORDER_TYPE_TIME tt = specified ? ORDER_TIME_SPECIFIED : ORDER_TIME_GTC;
      datetime exp = specified ? expiry : 0;
      bool ok = (dir > 0) ? m_trade.BuyLimit(lots, NormalizePrice(price), m_sym, NormalizePrice(sl), NormalizePrice(tp), tt, exp, comment)
                          : m_trade.SellLimit(lots, NormalizePrice(price), m_sym, NormalizePrice(sl), NormalizePrice(tp), tt, exp, comment);
      uint rc = m_trade.ResultRetcode();
      bool done = ok && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_PLACED);
      OnResult(done, "limit order");
      ticket = done ? m_trade.ResultOrder() : 0;
      return done;
     }

   bool              ModifyLimit(const ulong ticket, const double price, const double sl, const double tp, const datetime expiry)
     {
      if(!OrderSelect(ticket)) return false;
      double pt = SymbolInfoDouble(m_sym, SYMBOL_POINT);
      double freeze = (double)SymbolInfoInteger(m_sym, SYMBOL_TRADE_FREEZE_LEVEL) * pt;
      MqlTick tk;
      if(!SymbolInfoTick(m_sym, tk)) return false;
      double cur = OrderGetDouble(ORDER_PRICE_OPEN);
      if(freeze > 0 && (MathAbs(tk.bid - cur) <= freeze || MathAbs(tk.ask - cur) <= freeze)) return false;
      ENUM_ORDER_TYPE_TIME tt = (ENUM_ORDER_TYPE_TIME)OrderGetInteger(ORDER_TYPE_TIME);
      bool ok = m_trade.OrderModify(ticket, NormalizePrice(price), NormalizePrice(sl), NormalizePrice(tp), tt,
                                    (tt == ORDER_TIME_SPECIFIED) ? expiry : 0, 0.0);
      OnResult(ok, "modify limit");
      return ok;
     }

   bool              DeleteOrder(const ulong ticket)
     {
      bool ok = m_trade.OrderDelete(ticket);
      OnResult(ok, "delete order");
      return ok;
     }

   bool              ClosePosition(const ulong ticket)
     {
      bool ok = m_trade.PositionClose(ticket, (ulong)MathMax(m_deviation, 0));
      OnResult(ok, "close position");
      return ok;
     }
  };

#endif
