# Forward Paper-Trading Plan (demo only — no real money)

**Status: proposed, not started.** It needs the user: an IC Markets Raw **demo** account and/or a
TradingView chart. The historical research found **no validated edge** (FINAL_REPORT §5–7). This
forward test therefore has two modest goals:
1. **Measure real execution costs at impulse moments.** This is the largest unknown in the
   historical study, because spreads were modelled.
2. **Test the single best historical idea on genuinely new data, with a stopping rule fixed in
   advance.** The idea is XAUUSD H-11: fade a de-seasonalised 5-minute impulse above 5σ during London
   or NY hours, 30-minute horizon.

## Setup
- **Strategy:** `pine/quantum_edge_impulse_reversion.pine` with the inputs below, on an IC Markets
  XAUUSD M1 chart.

  | Input | Value |
  |---|---|
  | Mode | Active fade |
  | k | 5 |
  | H | 30 |
  | stop | 1.0 |
  | target | 1.5 |
  | risk | 0.20% |
  | daily loss | 1% |
  | Properties → Commission | 0.035 USD per unit (= $3.50/lot/side for 100 oz; UNVERIFIED) |

  The chart needs at least 4 weeks of M1 history loaded. The dashboard shows "Seasonal weeks loaded".
- **Alerts:** TradingView alerts on order fills, sent to a log (webhook or e-mail). Every alert is
  recorded, including losers.
- **In parallel,** run `tools/mql5/ExportM1WithSpread.mq5` weekly on the demo terminal to collect
  real M1 spreads.

## Pre-registered decision rule (sequential, fixed before the first trade)
- **Test:** Wald SPRT on per-trade net R. H0: mean = 0; H1: mean = +0.05R. Use σ_R measured on
  development data (about 1.0R). Error rates α = 0.05, β = 0.20.
- **Log-likelihood increment** per trade (normal approximation):
  `Λ += (μ1/σ²)·(R − μ1/2)`, with μ1 = 0.05 and σ = 1.0.
- **Accept H1** (edge plausible) when Λ ≥ ln((1−β)/α) = 2.77.
  **Accept H0** (no edge) when Λ ≤ ln(β/(1−α)) = −1.56.
- **Hard stop at 600 trades,** about 6–9 months at the historical event rate. Stop early if
  cumulative paper drawdown exceeds 10%.
- **Expected outcome given EXP008:** H0 is accepted, or the test runs to the 600-trade cap. Reaching
  H1 would justify a *new* research cycle with observed spreads. It would **not** justify live
  trading.

## What gets reported weekly
- Every trade: entry/exit time, prices, spread at entry (from MT5), slippage versus the signal bar
  close, holding minutes, R.
- The running Λ, cumulative R, drawdown, and lockout days.
- The realised spread distribution at impulse minutes versus the model in `qe/data/store.py`.

## Hard rules
- Demo or paper only. Live trading needs separate, explicit human approval, and the evidence does
  not support requesting it.
- No parameter changes during the test. A change restarts the SPRT and is logged as a new trial.
