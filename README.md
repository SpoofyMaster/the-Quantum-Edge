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
