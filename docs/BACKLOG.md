# Backlog

Legend: `[ ]` open · `[x]` done · `[!]` blocked (reason) · `[?]` needs user decision/approval

## Research (Days 1–3)
- [x] R-1 Repository scaffold, rules (CLAUDE.md), config, CI — Day 1
- [x] R-2a Literature review draft (docs/research/literature_review.md) — Day 1
- [ ] R-2b Verify every citation's bibliographic details and key numbers (needs web access to journals/SSRN)
- [!] R-3 Official IC Markets Raw specs per symbol (icmarkets.com blocked) → user can verify via MT5 Specification (see broker_specs.md)
- [x] R-4 Hypothesis register H-01…H-10 with measurable definitions — Day 1
- [ ] R-5 Economic-calendar source for tier-1 news blackout (H-10) — find a licensed/free historical calendar with timestamps
- [ ] R-6 Write de-seasonalised impulse definition (vol normalised by same-minute-of-week median over trailing 20 weeks) — code + causality test

## Infrastructure (done Day 1, all unit-tested)
- [x] I-1 Canonical M1 bid/ask schema + quality report
- [x] I-2 Dukascopy .bi5 decoder + M1 aggregation; HistData parser; MT5 spread export script (uncompiled)
- [x] I-3 DST-correct sessions, FX day (17:00 NY), rollover blackout
- [x] I-4 Cost model (spread + commission + slippage, USD conversion) and cost-in-R
- [x] I-5 Risk engine (0.20% sizing incl. costs, 1% daily lockout, open-risk cap, correlation guard, breaker)
- [x] I-6 Execution-aware trade simulator (next-bar fill, stop-first, gap fills, time exit ≤120m, rollover exit)
- [x] I-7 Purged/embargoed walk-forward, final-test lock, trial registry
- [x] I-8 Stats: stationary bootstrap, PSR, DSR, MC drawdown, calibration (Brier/ECE)

## Data (Days 4–7)
- [!] D-1 Download Dukascopy 2020-01→latest for EURUSD, GBPUSD, USDJPY, XAUUSD, XAGUSD (`scripts/fetch_dukascopy.py`) — BLOCKED by egress policy; needs `datafeed.dukascopy.com` allowed, or user uploads data
- [?] D-2 User exports IC Markets MT5 M1 + spread (`tools/mql5/ExportM1WithSpread.mq5`) to measure broker-specific spreads
- [ ] D-3 Spread & volatility seasonality by minute-of-week per symbol; recompute exp003 with measured spreads
- [ ] D-4 Data-quality report per symbol/year; reconcile Dukascopy vs MT5 bars (price & spread deltas)
- [?] D-5 User runs `pine/tools/m1_coverage_probe.pine` on TradingView M1 for each symbol and reports first-bar date

## Probability engine (Days 8–12)
- [ ] P-1 Event-conditional models (fit only on impulse/sweep events, not all bars) — lesson from M-04
- [ ] P-2 Baseline = cost/regime-only model; directional model must beat it (rule from M-03)
- [ ] P-3 Symmetric long/short labels; time-to-target survival curves (Kaplan–Meier) per horizon
- [ ] P-4 Candidate models: calibrated logistic, HMM regime, GARCH vol forecast, CUSUM change-points — keep only what adds OOS value
- [ ] P-5 Power analysis on real data: trades/year needed to detect net EV of 0.05/0.1R (exp001 suggests >1 symbol-year is necessary)

## Validation / later
- [ ] V-1 Cost stress (+50% spread, +1 bar latency, 2 ticks slippage)
- [ ] V-2 Parameter-stability heatmaps
- [ ] V-3 Year/session/regime breakdowns
- [ ] V-4 Probability of Backtest Overfitting (CSCV)
- [ ] T-1 Pine v6 strategy + dashboard (only after edge gate)
- [?] Q-1 MQL5 EA — requires explicit human approval after validation
