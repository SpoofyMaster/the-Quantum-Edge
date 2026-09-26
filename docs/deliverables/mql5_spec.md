# MQL5 Expert Advisor — Technical Specification (conditional)

**Status: specification only. No EA code has been or will be written without explicit human
approval** (project rule). The research does **not** currently justify asking for that approval
(FINAL_REPORT). This document exists so that, if a future research cycle validates an edge, the
implementation is unambiguous and matches the Python and Pine signals.

## 1. Scope
- One EA, symbol-agnostic, running on M1 charts. One instance per symbol, with portfolio risk
  coordinated through a global-variable ledger.
- Magic number per strategy family. Hedging account assumed (IC Markets MT5 default); must also
  work on netting.
- `MQLInfoInteger(MQL_TESTER)` is required; otherwise the EA starts in **paper/log-only mode**.
  Live order sending is behind an input `AllowLiveOrders=false`, which must be enabled manually
  after written approval.

## 2. Signal (must match `qe/features.py`, `qe/events.py`, `pine/...impulse_reversion.pine`)
- **Seasonal sigma:**
  - Buckets: New-York-local 5-minute time-of-week buckets (2016), weeks starting Sunday 00:00 NY.
  - Per-week mean |log return| per bucket, kept in a ring buffer of 20 weeks.
  - Expectation = median of the non-empty weeks (at least 4 required) × √(π/2), using previous weeks
    only.
  - NY time from `TimeGMT()` plus a DST-aware conversion. Server time must not be used for session
    logic; the server-UTC offset changes with DST.
- **Impulse:** `impulse_ds5 = ln(C_t/C_{t-5}) / sqrt(Σ_{i=0..4} e²_{t-i})`, using **bid** closes for
  parity with the research data.
- **Event:** the first bar with |impulse| > k, evaluated on bar close (new-bar detection on M1).
  - Active fade: London 08:00–16:30 Europe/London or NY 08:00–17:00 America/New_York.
  - Quiet revert: neither of those, and not in the rollover blackout.
- **Direction:** −sign(impulse).

## 3. Orders & exits
- Market order at the open of the next bar (the first tick after the new bar is detected).
  `ORDER_FILLING_IOC` or whatever the symbol allows. Maximum deviation = 3 points; on requote,
  retry once and then skip.
- **Stop:** entry ∓ stopMult × max(seasonal, realised σ60) × √H × price. **Target:** targetMult × the
  same distance (optional). Both are sent with the order, respecting `SYMBOL_TRADE_STOPS_LEVEL` and
  `SYMBOL_TRADE_FREEZE_LEVEL`.
- **Time exit:** close at H minutes (≤ 120). **Forced exit** at 16:45 NY (rollover blackout until
  17:30 NY). No new entries during the blackout.

## 4. Risk engine (parity with `qe/risk.py`)
- **Lot size:** `floor(0.002·Equity / (StopDist·TickValue/TickSize + 2·Commission_per_lot) / LotStep) · LotStep`.
  Reject if the result is below `SYMBOL_VOLUME_MIN`.
- **Daily lockout:** the FX day starts at 17:00 NY. Reject a new order if
  realised loss today + open planned risk + max(new risk, 0.2%·Equity) > 1%·day-start equity.
  Lock when realised loss reaches 1% or more.
- **Portfolio caps:** at most 3 positions and at most 0.6% open risk. Correlation guard: reject a
  same-direction exposure when |ρ| ≥ 0.6, using a correlation table computed offline.
- **Execution-health breaker:**
  - 3 consecutive rejects or requotes, or spread > 3× its median for this hour-of-week, suspends
    trading for the day.
  - A disconnect longer than 60 s with an open position triggers a close attempt on reconnect.
- Forbidden: martingale, grids, averaging down, increasing size after losses.

## 5. Logging & parity verification
- A CSV per day records every signal, including rejected ones with the reason, plus orders, fills,
  spread at fill and slippage.
- **Parity test:** replay the same period in the MT5 Strategy Tester ("Every tick based on real
  ticks") and compare signal timestamps and directions with the Python output for the same broker
  data. Target: at least 99% of signals identical, with every mismatch explained.

## 6. Acceptance before any demo deployment
Parity ≥ 99%; tester results within bootstrap CI of Python backtest on identical data; all risk-limit
unit scenarios (lockout, budget, correlation, breaker) reproduced in tester logs.
