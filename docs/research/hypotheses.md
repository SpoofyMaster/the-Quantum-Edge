# Hypothesis Register

Status legend: `HYPOTHESIS` (not tested) · `TESTING` · `VERIFIED` (our experiment, result file linked) ·
`REJECTED` · `BLOCKED`.
**Acceptance bar for a trading hypothesis:** net-of-cost EV > 0 with a 95% stationary-bootstrap CI above
0 on the validation period, Deflated Sharpe > 0.95 given the trial count in `results/trial_registry.jsonl`,
positive in ≥ 2 of 3 calendar sub-periods, and no collapse under +50% cost or +1 bar latency.

## Methodology hypotheses (about our pipeline)

| ID | Statement | Status | Evidence |
|---|---|---|---|
| M-01 | On a driftless random walk the pipeline reports no gross edge and a net EV of about −cost. | **VERIFIED (synthetic)** | [exp001](../../results/exp001_pipeline_null_and_power.json): with 0 edge, 5 of 6 variants have a gross EV CI covering 0. One (reversal, k=2.5, +0.052R, CI [0.001, 0.101]) is a borderline false positive, in line with testing 6 variants at α=5%. Net EV is −0.15R to −0.25R, with all CIs below 0. |
| M-02 | Directional features carry no look-ahead leakage. | **VERIFIED (synthetic)** | [exp002](../../results/exp002_null_auc_diagnostic.json): directional-only model OOS AUC = 0.4997 on null data. Also the unit test `test_features_are_causal`. |
| M-03 | A "target-before-stop" label's AUC is inflated by cost and volatility structure, not direction. | **VERIFIED (synthetic)** | exp002: cost/regime-only features AUC 0.517 (Brier skill +0.0015), all features 0.510. **Rule adopted:** every directional model must beat a cost/regime-only baseline model, not AUC 0.5. |
| M-04 | The pipeline can detect a planted continuation edge. | **PARTIAL (synthetic)** | exp001: a planted drift of 0.2σ/min for 20 min after a 3σ impulse gives a gross EV of +0.36R (CI [0.22, 0.51]) at k=3.5. Net EV is only +0.09R (CI [−0.05, 0.22]) on 1 year of one symbol, so it is **not significant**. The unconditional logistic model (events every 5 bars) did **not** detect it (AUC 0.511 vs 0.510 null), because the edge affects only about 2% of bars. |
| M-05 | Round-trip cost is a first-order constraint at M1 stop sizes. | **VERIFIED (arithmetic, unverified specs)** | [exp003](../../results/exp003_cost_in_R_table.json): EURUSD cost is ≈0.22R at a 5-pip stop and 0.09R at 12 pips. XAUUSD cost is ≈0.38R at a 5-point ($0.50) stop. A 1.5R target with a 5-pip stop needs a win rate of ≥ 48.8% on EURUSD. |

## Market hypotheses — status after EXP005 (dev period 2020-01 → 2023-12, HistData M1, modelled spreads)

EXP005 ([results](../../results/exp005_event_study_dev.json)) measures the signed forward mid move from the
next-bar open, in units of round-trip cost, for H ∈ {5, 15, 30, 60, 120} min. It covers 275 cells
(5 symbols × 11 families × 5 horizons), with Benjamini–Hochberg FDR at q ≤ 0.10 across all of them.

| ID | Statement (measurable) | Status | Evidence (dev period only) |
|---|---|---|---|
| H-01 | After a de-seasonalised 5-min impulse > k·σ in London/NY, price **continues**. | **REJECTED** | Significantly **negative** on EURUSD, GBPUSD, XAUUSD, XAGUSD for k = 3/4/5 and H = 5–60 (q ≤ 0.05). Example: XAUUSD k=5 at H=30 is −1.51× cost. USDJPY is not significant. |
| H-02 | The same impulse in Asia / late NY **reverts**. | **SUPPORTED on dev, pending validation** | EURUSD k=5 at H=120: +1.59 pips = 1.32× cost, CI [0.93, 2.24], q = 0.0001. GBPUSD k=3 at H=120: 0.66× cost. XAUUSD k=3 at H=30: 0.40× cost. |
| H-03 | London-open 30-min range break continues. | REJECTED (no evidence) | No FDR survivor. Best cell is USDJPY H=60 at 0.66× cost, CI includes 0. |
| H-04 | Previous-FX-day high/low sweep reverts. | REJECTED (no evidence) | No survivor. |
| H-05 | Round-number break with range expansion continues. | REJECTED | Where significant, the sign is *negative* (GBPUSD, XAUUSD, XAGUSD). |
| H-06 | Stall at untouched round numbers. | NOT TESTED | Deprioritised after H-05. |
| H-07 | Trending-regime filter improves continuation. | MOOT | Continuation itself is rejected (H-01). |
| H-08 | USD strength into the 16:00 London fix, weakness after. | REJECTED (no evidence) | No survivor on any symbol. |
| H-09 | USD-led metal impulses continue. | NOT TESTED | Continuation is rejected generally. |
| H-10 | Spread/news suspension improves net EV. | BLOCKED | Needs observed spreads and a news calendar. |
| **H-11** | **Fade** a de-seasonalised 5-min impulse > k·σ in London/NY (mean reversion within 15–60 min). | **GENERATED from dev data → EXP006, then one-shot validation (EXP007)** | This is the mirror image of H-01's rejection. It is data-snooped by construction, so only the untouched validation period can support it. |

Caveats that apply to every row:
- HistData is bid-only, so spreads are **modelled**, not observed.
- 2023 has about 48k missing minutes.
- Mid prices are bid + half the modelled spread.
- Short-horizon reversal is also the signature of **bad-print noise** in retail data feeds. Measuring
  from the *next* bar's open removes single-print bounce-backs, but multi-bar data errors could remain.
  Confirmation on a second, independent data source (Dukascopy or IC Markets MT5 export) is required
  before any real-money consideration.

