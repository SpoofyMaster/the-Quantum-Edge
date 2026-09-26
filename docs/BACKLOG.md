# Backlog

Legend: `[ ]` open · `[x]` done · `[!]` blocked (reason) · `[?]` needs user decision/approval

## Research (Days 1–3)
- [x] R-1 Repository scaffold, rules (CLAUDE.md), config, CI — Day 1
- [x] R-2a Literature review draft (docs/research/literature_review.md) — Day 1
- [ ] R-2b Verify every citation's bibliographic details and key numbers (needs web access to journals/SSRN)
- [!] R-3 Official IC Markets Raw specs per symbol (icmarkets.com blocked) → user can verify via MT5 Specification (see broker_specs.md)
- [x] R-4 Hypothesis register H-01…H-10 with measurable definitions — Day 1
- [ ] R-5 Economic-calendar source for tier-1 news blackout (H-10) — find a licensed/free historical calendar with timestamps
- [x] R-6 De-seasonalised impulse (qe.features.seasonal_sigma) + causality test — Day 2

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
- [x] D-1 M1 2020-01→2025-06 for 5 symbols via GitHub Actions (HistData, bid-only) — Day 2. Dukascopy returned HTTP 503 to GitHub runners → [!] D-1b observed bid/ask source still missing
- [?] D-2 User exports IC Markets MT5 M1 + spread (`tools/mql5/ExportM1WithSpread.mq5`) to measure broker-specific spreads
- [x] D-3 Volatility seasonality + cost-in-R by session (EXP004) — Day 2. Spread part blocked (no observed spreads)
- [x] D-4 Data-quality report per symbol/year (EXP004) — Day 2; [ ] D-4b reconcile against a second source
- [?] D-5 User runs `pine/tools/m1_coverage_probe.pine` on TradingView M1 for each symbol and reports first-bar date

## Probability engine (Days 8–12)
- [x] P-1 Event-conditional meta-label models on strategy trades (EXP006) — no OOS value → rejected
- [x] P-2 Cost/regime-only baseline implemented and compared (EXP006)
- [x] P-3 Competing-risks cumulative incidence tooling (qe.survival) — Day 2; [ ] apply to a future candidate
- [ ] P-4 Candidate models: calibrated logistic, HMM regime, GARCH vol forecast, CUSUM change-points — keep only what adds OOS value
- [x] P-5 SNR/cost frontier on real data (EXP008): best net IR ≈ 0.02 → 20–40 years for t=3

## Validation / later
- [x] V-1 Cost stress: spread ×2, slippage 3 ticks, +1 bar latency (EXP006/007)
- [ ] V-2 Parameter-stability heatmaps
- [x] V-3 Per-year breakdowns (EXP006/007); session split built into families
- [ ] V-4 Probability of Backtest Overfitting (CSCV)
- [x] T-1 Pine v6 research prototype + dashboard (pine/quantum_edge_impulse_reversion.pine) — NOT compiled; demo/paper only
- [?] Q-1 MQL5 EA — requires explicit human approval after validation

## Day 2 outcome and next research cycle (needs user input or new data)
- [x] EXP005 event study (275 cells, FDR), EXP006 executable strategies + stress + meta-labels, EXP007 pre-registered validation look, EXP008 SNR frontier
- [x] Final deliverables: docs/deliverables/{FINAL_REPORT, REPRODUCE, paper_trading_plan, mql5_spec}.md
- [?] U-1 User: compile `pine/quantum_edge_impulse_reversion.pine` and `pine/tools/m1_coverage_probe.pine` on TradingView; report errors or first-bar dates
- [?] U-2 User: verify IC Markets specs in MT5 (docs/research/broker_specs.md); export M1 + spread with tools/mql5/ExportM1WithSpread.mq5
- [?] U-3 User: decide whether to run the forward paper test (docs/deliverables/paper_trading_plan.md)
- [ ] N-1 Re-run EXP005/006 with observed spreads once U-2 data exists (new trial family; validation already used once for H-11 only)
- [ ] N-2 New information sources for new hypotheses: economic-calendar surprises; order-flow data
- [ ] N-3 Retry Dukascopy from CI with low concurrency (503 may be rate-limiting); reconcile vs HistData (D-4b)
