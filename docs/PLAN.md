# Approved 30-Day Plan — status board

Day numbering counts **working sessions actually executed**, not calendar days. Research happens only
while a session runs. Nothing is claimed for offline time.

| Phase | Days | Goal | Status |
|---|---|---|---|
| Research | 1–3 | Literature, broker specs, measurable hypotheses, research infrastructure | **Day 1 done** (infra + null/power tests + literature draft). Broker specs UNVERIFIED (site blocked). |
| Data | 4–7 | Acquire/clean M1 bid/ask 2020→present, quality report, spread & volatility seasonality | **BLOCKED**: egress policy blocks all data hosts (see docs/research/data_provenance.md) |
| Probability engine | 8–12 | Event-conditional models, calibration, time-to-target, reject non-OOS models | Pipeline pieces ready (labels, purged WF, calibration metrics); waiting on data |
| TradingView prototype | 13–18 | Pine v6 strategy + risk/cost dashboard | Coverage probe written (not compiled) |
| Validation | 19–23 | Walk-forward, sensitivity, cost stress | Stats toolkit ready (bootstrap, PSR/DSR, MC drawdown) |
| Robustness | 24–27 | Untested periods, other symbols, adverse regimes | — |
| Delivery | 28–30 | Report, final Pine, paper-trading plan, MQL5 spec (no MQL5 code without approval) | — |

## Gates
1. **Data gate** (before Day 8): ≥ 2020-01 → 2025-06 M1 bid/ask for ≥ 3 symbols with quality report.
2. **Edge gate** (before Day 13): at least one hypothesis passes the acceptance bar in
   docs/research/hypotheses.md on the validation period. If none do, the correct deliverable is a
   negative-result report + recommended next research directions, NOT a tuned prototype.
3. **Freeze gate** (before touching final test ≥ 2025-07-01): strategy frozen and journaled.
4. **Human approval** before MQL5 implementation and before any live trading (live trading is out of scope).
