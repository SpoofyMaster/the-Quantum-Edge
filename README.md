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

**Current state:** infrastructure and synthetic validation only. No market data has been analysed yet.
