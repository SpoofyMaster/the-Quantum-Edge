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
- [x] Q-1 MQL5 EA — APPROVED by the project owner on 2026-09-26 for Strategy Tester/demo testing; implemented as mql5/QuantumEdgeImpulseReversion.mq5 (NOT compiled; real accounts log-only). [?] U-4 User: compile + run the tester per mql5/README.md and send the report + QE_tester_summary.csv

## Day 2 outcome and next research cycle (needs user input or new data)
- [x] EXP005 event study (275 cells, FDR), EXP006 executable strategies + stress + meta-labels, EXP007 pre-registered validation look, EXP008 SNR frontier
- [x] Final deliverables: docs/deliverables/{FINAL_REPORT, REPRODUCE, paper_trading_plan, mql5_spec}.md
- [?] U-1 User: compile `pine/quantum_edge_impulse_reversion.pine` and `pine/tools/m1_coverage_probe.pine` on TradingView; report errors or first-bar dates
- [?] U-2 User: verify IC Markets specs in MT5 (docs/research/broker_specs.md); export M1 + spread with tools/mql5/ExportM1WithSpread.mq5
- [?] U-3 User: decide whether to run the forward paper test (docs/deliverables/paper_trading_plan.md)
- [ ] N-1 Re-run EXP005/006 with observed spreads once U-2 data exists (new trial family; validation already used once for H-11 only)
- [ ] N-2 New information sources for new hypotheses: economic-calendar surprises; order-flow data
- [ ] N-3 Retry Dukascopy from CI with low concurrency (503 may be rate-limiting); reconcile vs HistData (D-4b)

## Video strategy reconstruction — tomtrades "I Made $1.4M Trading Gold" (session 2026-10-04, journal day03)
- [x] VS-1 Access the video: metadata, chapters, full auto-captions, storyboard frames. Video stream blocked (YouTube
  bot-check / HTTP 403 from the sandbox) → frames are 320×180 only; prices/times unreadable.
- [x] VS-2 Research docs in `research/`: transcript map, supplementary definitions (S1–S9, same author), rulebook,
  trade database (6 examples), ambiguity register (21 items), algorithm spec, pseudocode, Phase-14 replication test.
- [x] VS-3 Python reference `qe/video_strategy/` + tests (structure, causality, 6 video-example fixtures) — CI green.
- [x] VS-4 MQL5 EA `mql5/VideoStrategyEA/` (9 files) — **NOT compiled**; mechanical check `tools/mql5_static_check.py` passes.
- [x] VS-5 EXP009 pre-registered reference backtest: **REJECTED** (V0 −0.164R, CI [−0.262, −0.061]; DXY gate adds
  nothing; M15 variant 0 trades) — `reports/BACKTEST_REPORT.md`.
- [?] U-5 User: compile `mql5/VideoStrategyEA` in MetaEditor; send the full Errors tab (errors + warnings).
- [?] U-6 User: Strategy Tester (XAUUSD M1, real ticks, 2020-01 → 2025-06): defaults + `PULLBACK_50`, `M15`,
  `H1_AND_M15`; send the tester report and `VSEA_trades_*.csv` / `VSEA_events_*.csv` from Common/Files.
- [?] U-7 User decision on the two CRITICAL ambiguities: default entry (A-01: BREAK vs PULLBACK_50) and candle mode
  (A-07: H1 vs H1_AND_M15).
- [?] U-8 User (optional): a higher-resolution copy of the video or the exact dates/times of the "Monday" and
  "Wednesday" live trades, for a real-price replay (those dates are in the locked final-test period → freeze first).
- [ ] VS-6 Tick-built 10-second bars for the "shift within the shift" refinement (A-17).
- [ ] VS-7 Check IC Markets MT5 for a dollar-index symbol; else confirm the six synthetic-DXY components are listed.
- [ ] VS-8 Python ↔ EA parity run on the same MT5-exported data once U-6 exists (compare signal times and reason codes).

## Indicator port — "ICT Concepts [LuxAlgo]" Balance Price Range (session 2026-10-07, journal day04)
- [x] LX-1 Parameter reference of the whole script (`research/indicators/ICT_CONCEPTS_PARAMETERS.md`) and exact
  BPR spec, revision 2 after an independent re-derivation (`research/indicators/LUXALGO_BPR_SPEC.md`).
- [x] LX-2 Python reference `qe/indicators/luxalgo_bpr.py` + 42 scenario tests.
- [x] LX-3 MT5 indicator `mql5/Indicators/LuxAlgo_BPR/` (live forming-bar emulation, Fibonacci-BPR, alert, parity
  export) — **NOT compiled**. Logic checked bar by bar against the reference via the C++ harness test.
- [x] LX-4 Browser live replay `research/indicators/preview/LuxAlgo_BPR_live_replay.html` (+ JS parity test).
- [?] U-9 User: compile `LuxAlgo_BPR.mq5` in MetaEditor; send all compiler messages.
- [?] U-10 User (optional): run with `InpExportCSV=true`, send `MQL5/Files/LuxAlgo_BPR_<symbol>_<period>.csv` →
  `python tools/luxbpr_parity.py <file>`.
- [?] U-11 User (optional): TradingView screenshot (same symbol/timeframe, BPR on) for a visual cross-check.
- [x] LX-5 Owner sketch "BPR retest long" read and turned into an execution playbook
  (`research/indicators/BPR_RETEST_PLAYBOOK.md`), registered as **H-13 HYPOTHESIS**.
- [x] LX-6 EXP010: pre-registered backtest of H-13 (XAUUSD M1 2020-01 → 2025-06, 7 trials): **REJECTED**
  (V0 −0.368R, CI [−0.705, +0.030]; every variant negative) — `reports/EXP010_BPR_FVG_EA_REPORT.md`.

## BPR + FVG Expert Advisor (session 2026-10-08, journal day05)
- [x] EA-1 Spec `research/indicators/BPR_FVG_EA_SPEC.md` (setups, life cycle, execution, risk, display, parity contract).
- [x] EA-2 MQL5 EA `mql5/BprFvgEA/` (LuxAlgo zones on chart + BPR/FVG retest setups; tester/demo only, real accounts
  log-only) — **NOT compiled**.
- [x] EA-3 Python reference `qe/strategies/bpr_fvg.py` (detector + simulator, 63 tests) and EA-vs-Python parity harness
  (`tests/test_bpr_fvg_ea_harness.py`, 10 configurations, mutation-checked).
- [x] EA-4 Adversarial review (24 findings; 4 critical/major trading-safety issues in the execution layer) → fixed.
- [?] U-12 User: compile `mql5/BprFvgEA` in MetaEditor; run the Strategy Tester (XAUUSD M1, real ticks,
  2020-01-01 → 2025-06-30, defaults) and send the report + `BFEA_trades_*_TESTER.csv` for comparison with EXP010.
