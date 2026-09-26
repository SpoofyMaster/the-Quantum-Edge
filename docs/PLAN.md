# Approved 30-Day Plan — status board

Day numbering counts **working sessions actually executed**, not calendar days. Research happens only
while a session runs. Nothing is claimed for offline time. All phases were executed in two working
sessions on 2026-09-26 (see `docs/journal/`).

| Phase | Days | Goal | Status |
|---|---|---|---|
| Research | 1–3 | Literature, broker specs, hypotheses, infrastructure | **Done**. Broker specs still UNVERIFIED (site blocked) |
| Data | 4–7 | M1 2020→present, quality, spread/volatility seasonality | **Done with caveats**: HistData bid-only via GitHub Actions; spreads modelled; Dukascopy HTTP 503 |
| Probability engine | 8–12 | Event-conditional models, calibration, reject non-OOS models | **Done**: seasonal volatility model, FDR event study, meta-label models (no OOS value, rejected) |
| TradingView prototype | 13–18 | Pine v6 strategy + risk/cost dashboard | **Written, not compiled** (no TradingView access); algorithm parity verified in Python |
| Validation | 19–23 | Walk-forward, sensitivity, cost stress | **Done**: edge gate FAILED on dev; one pre-registered validation look also negative |
| Robustness | 24–27 | Other periods/symbols/regimes, simplify or reject | **Done**: per-year breakdown, SNR/cost frontier (EXP008) |
| Delivery | 28–30 | Report, final Pine, paper-trading plan, MQL5 spec | **Done** (`docs/deliverables/`); forward paper test and TradingView demo need the user |

## Gates
1. Data gate: **passed with caveats** (bid-only, modelled spreads, 2023 gap).
2. Edge gate: **FAILED.** No hypothesis passed the acceptance bar. Deliverable = negative-result report.
3. Freeze gate: not reached. The final test period (≥ 2025-07-01) is **untouched**.
4. Human approval for MQL5 / live trading: **not requested**, because the evidence does not justify it.
