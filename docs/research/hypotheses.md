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

## Market hypotheses (to test on real data once it is available)

| ID | Statement (measurable) | Horizon | Source | Status |
|---|---|---|---|---|
| H-01 | After a de-seasonalised 5-min impulse > k·σ **during London/NY/overlap**, continuation probability > 50% + cost hurdle. | 15–60 min | Andersen-Bollerslev seasonality + informed-flow theory | HYPOTHESIS |
| H-02 | The same impulse **in Asia / late NY** mean-reverts (liquidity-driven, not information-driven). | 5–30 min | Elaut et al. 2018 (informed vs liquidity) | HYPOTHESIS |
| H-03 | The first 15–30 min London-open range break predicts direction until the NY open. | 60–120 min | Gao et al. 2018 (analogue), session-transition flow | HYPOTHESIS |
| H-04 | Sweep of the previous FX-day high/low followed by a close back inside the range → reversal. | 15–90 min | Osler 2003 (stop clustering) | HYPOTHESIS |
| H-05 | Break of a round number (00/50 levels) with range expansion → continuation. | 5–30 min | Osler 2003 | HYPOTHESIS |
| H-06 | Approach to an untouched round number without expansion → stall/reversal. | 5–30 min | Osler 2003 | HYPOTHESIS |
| H-07 | High efficiency ratio + rising realised vol ratio (trending regime) raises continuation probability, conditional on H-01. | 15–60 min | Regime literature | HYPOTHESIS |
| H-08 | USD drift into and reversal after the London 16:00 fix. | 30–60 min | Krohn, Mueller & Whelan 2024 | HYPOTHESIS |
| H-09 | XAUUSD/XAGUSD impulses led by the USD leg (DXY proxy from EURUSD+USDJPY) continue more than idiosyncratic metal moves. | 15–60 min | Cross-asset | HYPOTHESIS |
| H-10 | Trading suspension when spread > 3× its hourly median, or within ±N min of tier-1 news, improves net EV. | — | ABDV 2003; execution risk | HYPOTHESIS |

All market hypotheses are **BLOCKED on data** (see [data_provenance.md](data_provenance.md)).
