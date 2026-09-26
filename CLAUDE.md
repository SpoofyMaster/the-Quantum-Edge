# PROJECT QUANTUM EDGE — Operating Rules for Agents

Read this file first in every session, then read, in this order:

1. `docs/PLAN.md` — the approved 30-day plan and the status of each phase.
2. `docs/BACKLOG.md` — the task list. Pick the next incomplete task that is not blocked.
3. The newest file in `docs/journal/` — the last verified checkpoint.
4. `results/` — the latest experiment outputs (JSON). Never re-run an experiment
   that has a result file unless you document why in the journal.

## Mission (short form)

Find out, scientifically, whether a repeatable M1 intraday edge (holding 5–120 min)
exists on liquid FX / metals **after IC Markets Raw Spread costs**, and deliver a
reproducible system only if the evidence supports it. "No edge found" is a valid,
publishable result.

## Hard rules (never violate)

- **No live trading.** Research is historical backtest or paper trading only.
  Live deployment needs separate, explicit human approval. MQL5 work also needs
  explicit human approval after validation.
- **No look-ahead.** A feature at bar `t` may use only bars `<= t` (bar `t` is
  complete at its close). Entries execute at the **next** bar's open at the ask
  (long) / bid (short). Every new feature needs a causality test
  (see `tests/test_features.py::test_features_are_causal`).
- **Untouched final test set.** The period in `config/research.toml` → `[splits].final_test_start`
  onward is locked. Do not read it, plot it, or tune on it until the
  strategy is frozen and the freeze is recorded in the journal.
- **Honest reporting.** Never claim a test passed unless it was executed in this
  repo and the output is saved. Label every claim as one of:
  `PUBLISHED` (from literature, cite it), `HYPOTHESIS` (not yet tested),
  `VERIFIED` (our own experiment, link the result file), `REJECTED`.
- **Costs are always on.** Every backtest includes spread, commission and slippage.
  Broker values marked `UNVERIFIED` in `config/instruments.toml` must be confirmed
  against official IC Markets documentation before any final claim.
- **Risk limits:** 0.20% equity per new position (incl. costs), 1.00% planned daily
  loss (incl. commissions), no martingale / grids / averaging down / size-up after losses,
  every position closed ≤ 120 minutes after entry.
- **Multiple testing.** Keep a count of every strategy variant evaluated
  (`results/trial_registry.jsonl`). Report Deflated Sharpe Ratio, not raw Sharpe alone.
- **TradingView ≠ broker data.** Never present TradingView bars as IC Markets bid/ask
  execution. Never claim TradingView tested bars that the subscription does not load.

## Code conventions

- Python 3.11, package `qe/`. Dependencies in `requirements.txt`.
- Run tests: `python -m pytest -q`. All tests must pass before committing.
- Experiments live in `experiments/expNNN_<name>.py`, are deterministic (fixed seeds),
  and write `results/expNNN_<name>.json`. Record each in the journal and the
  hypothesis register (`docs/research/hypotheses.md`).
- Timestamps are UTC, timezone-aware, bar-open labelled. Session logic uses
  `zoneinfo` (DST-correct), never fixed UTC offsets.
- Pine Script lives in `pine/` and must declare `//@version=6`. It cannot be compiled
  in this sandbox — mark Pine files "not yet compiled on TradingView" until the user confirms.

## Journal routine (end of every working session)

Create/append `docs/journal/YYYY-MM-DD_dayNN.md` with: experiments performed,
hypotheses accepted/rejected, code changes, reproducible test results (commands +
outputs), current limitations, blockers, next actions. Update `docs/BACKLOG.md`.
