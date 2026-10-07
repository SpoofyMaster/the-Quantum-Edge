# Project Quantum Edge

A research project testing whether a **repeatable M1 intraday edge** (5–120 minute holds) exists in
liquid FX and metals **after IC Markets Raw Spread costs**. The pipeline runs from research to a
TradingView Pine v6 prototype, and on to MQL5 only with explicit human approval. No live trading.

- Start here: [`CLAUDE.md`](CLAUDE.md) (rules), [`docs/PLAN.md`](docs/PLAN.md), [`docs/BACKLOG.md`](docs/BACKLOG.md),
  [`docs/journal/`](docs/journal/).
- Research: [literature](docs/research/literature_review.md) · [hypotheses](docs/research/hypotheses.md) ·
  [broker specs](docs/research/broker_specs.md) · [data provenance](docs/research/data_provenance.md)

```bash
pip install -r requirements.txt
python -m pytest -q                                   # unit tests
python experiments/exp001_pipeline_null_and_power.py  # synthetic pipeline validation
```

**Current state (2026-09-26): research cycle 1 complete — NO tradable edge found.**
- Largest effect found: a short-term reversal after big impulses. It is statistically real, but
  worth about 0.02 information ratio per trade after costs.
- Out of sample, the best candidate lost money: 2024–2025H1 net −0.055R per trade.
- Read [`docs/deliverables/FINAL_REPORT.md`](docs/deliverables/FINAL_REPORT.md). No live trading;
  MQL5 not started (needs approval, not recommended).

## Project B — video strategy reconstruction (2026-10-04)
Reverse-engineering of *"I Made $1.4M Trading Gold, Here's What Actually Works"* (tomtrades,
<https://www.youtube.com/watch?v=xSVlVpXLuV0>): a gold reversal of an hourly candle's overextension, taken only when DXY
mirrors the entry model at the same time.
- Research: [`research/`](research/) — transcript map, rulebook, trade database, ambiguities, formal spec, pseudocode,
  replication test, [screenshots](research/screenshots/).
- EA (MQL5, **not yet compiled**, tester/demo only): [`mql5/VideoStrategyEA/`](mql5/VideoStrategyEA/).
- Python reference + tests: [`qe/video_strategy/`](qe/video_strategy/), `tests/test_video_*.py`.
- Reports: [`reports/`](reports/) — compilation, backtest (EXP009), video-vs-EA validation.

## Project C — Balance Price Range indicator from "ICT Concepts [LuxAlgo]" (2026-10-07)
A port of the FVG / Balance Price Range logic of the TradingView script *ICT Concepts [LuxAlgo]* (© LuxAlgo,
CC BY-NC-SA 4.0: non-commercial, share-alike). It is a charting tool, not a strategy.
- Parameters of the whole script: [`research/indicators/ICT_CONCEPTS_PARAMETERS.md`](research/indicators/ICT_CONCEPTS_PARAMETERS.md).
- How the BPR is calculated, exactly: [`research/indicators/LUXALGO_BPR_SPEC.md`](research/indicators/LUXALGO_BPR_SPEC.md).
- MT5 indicator (live on chart, **not yet compiled**): [`mql5/Indicators/LuxAlgo_BPR/`](mql5/Indicators/LuxAlgo_BPR/).
- Python reference + tests: [`qe/indicators/luxalgo_bpr.py`](qe/indicators/luxalgo_bpr.py), `tests/test_luxalgo_bpr.py`,
  `tests/test_luxbpr_*`.
- Browser replay: [`research/indicators/preview/LuxAlgo_BPR_live_replay.html`](research/indicators/preview/LuxAlgo_BPR_live_replay.html)
  (open it locally; rebuild with `python tools/luxbpr_preview/build.py`).
