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

## Project B — video strategy reconstruction (started 2026-10-04, journal day03)
The user asked for a reverse-engineering of a YouTube gold strategy into an MQL5 EA (explicit approval for MQL5 work;
tester/demo only). It reuses this project's rules: no look-ahead, costs on, locked final-test period, trial registry.

| Phase (user brief) | Status |
|---|---|
| 1–2 Video, transcript, frames | **Done with limits**: full captions; storyboard frames only (320×180) |
| 3–13 Rulebook, trade DB, ambiguities, spec, pseudocode | **Done** (`research/`) |
| 14 Replication test | **Done** (qualitative + executable fixtures); led to `CandleMode` H1_AND_M15 |
| 15–16 EA + compilation | EA **written**; **not compiled** (no MetaEditor) → U-5 |
| 17 Backtest | Python reference EXP009 (CI): **no edge** (V0 −0.164R/trade, CI below 0; DXY gate adds nothing); MT5 tester → U-6 |
| 18–19 Visual validation, regression tests | regression tests done (CI); visual MT5 check → U-6 |
| 20–23 Robustness, reports | cost stress in EXP009; reports in `reports/` |
