# Project Quantum Edge — Research Report (v1.0, 2026-09-26)

**Question.** Under which measurable conditions does the probability of a sustained 5–120 minute
directional move become high enough to overcome IC Markets Raw Spread costs on liquid FX and metals?

**Answer (evidence-based, with the caveats in §8).** Within the hypotheses tested, **no such
condition was found**:
- On M1 data from 2020-01 to 2023-12, no rule survives realistic execution and costs with a
  confidence interval above zero.
- No rule has a Deflated Sharpe Ratio above 0 after 317 recorded market trials.
- No rule survives cost and latency stress.

What we *did* find is a statistically robust but economically too small **short-term reversal after
large de-seasonalised impulses**. Its net information ratio is about 0.02 per trade, so roughly 20–40
years of trading would be needed just to confirm it at t = 3 (EXP008). **Recommendation: do not
trade. Do not start MQL5 development.** §9 sets out what would change this verdict.

Status labels follow CLAUDE.md: `PUBLISHED`, `HYPOTHESIS`, `VERIFIED`, `REJECTED`.

---

## 1. How the 30-day plan was executed (honest account)
The plan was run in **two working sessions** on 2026-09-26, not over 30 calendar days. Research only
happened while a session was running.

| Phase | Planned days | What was done | Where |
|---|---|---|---|
| Research | 1–3 | Literature review, hypothesis register, broker-cost model, pipeline null and power tests | `docs/research/`, EXP001–003 |
| Data | 4–7 | HistData M1, 5 symbols, 2020-01 → 2025-06; quality report; volatility seasonality | EXP004, `data_provenance.md` |
| Probability engine | 8–12 | Time-of-week seasonal volatility model; event study with FDR; purged walk-forward meta-label models vs cost-only baseline; competing-risks tools | EXP005, EXP006, `qe/` |
| TradingView prototype | 13–18 | Pine v6 strategy with risk engine and dashboard; algorithm parity test against Python | `pine/`, `tests/test_pine_parity.py` |
| Validation | 19–23 | Walk-forward, 4 stress variants, 2 exit variants, DSR, bootstrap CIs; one pre-registered validation look | EXP006, EXP007 |
| Robustness | 24–27 | Per-year breakdown, SNR/cost frontier | EXP006, EXP008 |
| Delivery | 28–30 | This report, reproduction guide, paper-trading plan, MQL5 spec | `docs/deliverables/` |

**Not done**, because each needs calendar time, the user, or data we could not get:
- Real-time forward paper trading.
- An interactive TradingView demonstration.
- Checking the Pine script compiles on TradingView.
- IC Markets spec verification.
- A second, independent bid/ask data source (Dukascopy refuses GitHub's cloud runners with HTTP 503).

## 2. Methodology
- **Causality.** Every feature and event at bar t uses bars ≤ t only. This is enforced by
  perturbation tests (`tests/test_features.py`, `tests/test_events.py`,
  `tests/test_survival_seasonal.py`). Entries fill at the next bar's open, at the ask for longs and
  the bid for shorts. If a bar touches both stop and target, the stop is assumed hit first. Gaps
  through a stop fill at the bar's open.
- **Splits.**
  - Development: 2020-01 → 2023-12. All exploration happened here.
  - Validation: 2024-01 → 2025-06. Used once, for a pre-registered look (EXP007).
  - Final test: 2025-07 onward. **Never loaded.** The code-level lock is in `qe/validation.py`, and
    fetchers drop that period before storing anything.
- **Multiple testing.**
  - Every variant is logged in `results/trial_registry.jsonl`: 317 on market development data at
    freeze time.
  - The event study uses Benjamini–Hochberg FDR across all 275 cells.
  - Strategies are reported with the Deflated Sharpe Ratio (Bailey & López de Prado 2014, `PUBLISHED`).
- **Pipeline self-tests (EXP001–002, `VERIFIED` on synthetic data).**
  - The pipeline finds no edge in a random walk.
  - It detects a planted edge before costs.
  - It has no directional look-ahead leakage.
  - One lesson: AUC must be compared with a cost/regime-only baseline (M-03).

## 3. Data provenance & quality (EXP004)
| Symbol | Bars 2020-01→2025-06 | Missing min (2023) | Median 60-min range, overlap / Asia | Cost in R (stop = 1× 60-min range), overlap / Asia |
|---|---|---|---|---|
| EURUSD | 1,993,457 | 48,791 | 19.2 / 7.9 pips | 0.057 / 0.139 |
| GBPUSD | 1,993,668 | 48,264 | 25.7 / 10.5 pips | 0.051 / 0.124 |
| USDJPY | 1,992,426 | 48,086 | 21.4 / 15.2 pips | 0.070 / 0.099 |
| XAUUSD | 1,901,183 | 56,088 | $7.27 / $3.27 | 0.026 / 0.058 |
| XAGUSD | 1,885,592 | 61,171 | 18.3 / 8.6 (×0.01) | 0.128 / 0.272 |

- **Source:** HistData.com M1, **bid only**, in EST without DST, converted to UTC. Obtained by the
  GitHub Actions research workflow and kept in the repo-private Actions cache. It is never committed.
- **Checks:** prices are within plausible ranges, and there are zero OHLC inconsistencies.
- **No volume** in this source, so tick-volume features are disabled automatically.
- **Spreads are modelled, not observed:** the placeholder IC Markets Raw spread times a New York
  hour profile, widest around the rollover (an assumption, `qe/data/store.py`).
- **Commission:** USD 3.50 per lot per side, `UNVERIFIED` (the official site was blocked;
  secondary sources only).

## 4. Hypotheses tested (including failures) — full register in `docs/research/hypotheses.md`
| ID | Hypothesis | Verdict |
|---|---|---|
| H-01 | Impulse continuation in London/NY | **REJECTED**: significantly *negative* on 4 of 5 symbols |
| H-02 | Impulse reversion in quiet hours | Real gross effect (EURUSD 1.3× cost at 120 min); **REJECTED as a strategy** (EXP006 net −0.017R) |
| H-03 | London-open range break | REJECTED (no evidence) |
| H-04 | Previous-day high/low sweep reversal | REJECTED (no evidence) |
| H-05 | Round-number break continuation | REJECTED (the sign is reversed where significant) |
| H-08 | USD into / after the 16:00 London fix | REJECTED (no evidence) |
| H-11 | Fade impulses in London/NY (generated on dev data) | Real gross effect (XAUUSD 1.5× cost at 30 min); **REJECTED as a strategy** on dev (see §5), plus the validation look in §6 |
| H-06, H-07, H-09 | Stall at round numbers; regime filter; USD-led metal moves | Not tested or moot (they depend on continuation, which was rejected) |
| H-10 | Suspension on spread spikes or news | BLOCKED (needs observed spreads and a news calendar) |

## 5. Executable-strategy results (EXP006, dev 2020–2023, costs on, 0.20% risk, 1% daily lockout)
Net EV per trade in R, with 95% stationary-bootstrap CI:

| Symbol | Family | H | Trades | Net EV [95% CI] | PF | Max DD | Exit B (time exit) | Spread ×2 | Slippage 3 ticks | +1 bar latency | Meta filter (n) | Cost-only baseline (n) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| XAUUSD | H11 fade k5 | 30 | 1933 | +0.021 [-0.017, +0.059] | 1.06 | 7.0% | +0.004 | -0.001 | +0.013 | -0.004 | +0.002 (213) | -0.110 (94) |
| EURUSD | H02 revert k5 | 120 | 1192 | -0.017 [-0.063, +0.029] | 0.95 | 11.1% | +0.001 | -0.045 | -0.045 | -0.031 | +0.042 (268) | +0.048 (247) |
| XAUUSD | H11 fade k4 | 15 | 3904 | -0.021 [-0.049, +0.005] | 0.94 | 27.6% | -0.009 | -0.069 | -0.035 | -0.049 | +0.031 (349) | +0.038 (251) |
| EURUSD | H11 fade k5 | 60 | 1391 | -0.046 [-0.083, -0.005] | 0.87 | 12.4% | -0.034 | -0.053 | -0.060 | -0.049 | -0.051 (260) | -0.084 (141) |
| XAUUSD | H11 fade k3 | 60 | 5083 | -0.029 [-0.051, -0.007] | 0.92 | 27.3% | -0.014 | -0.052 | -0.036 | -0.036 | -0.065 (427) | -0.033 (75) |
| EURUSD | H11 fade k4 | 30 | 3026 | -0.060 [-0.088, -0.031] | 0.84 | 30.9% | -0.034 | -0.078 | -0.089 | -0.064 | -0.050 (456) | -0.024 (189) |

- Deflated Sharpe is 0.00 for every row (317 trials).
- The best row by year, in R: 2020 +20.6, 2021 +25.1, 2022 +11.5, 2023 −15.9.
- **Probability models:** the walk-forward logistic meta-label model never beat the cost/regime-only
  baseline out of sample. Its "P(win)" outputs are therefore **not presented as calibrated
  probabilities** of anything useful.

## 6. One-shot validation look (EXP007, 2024-01 → 2025-06)
See `results/exp007_validation_confirm.json`. The candidate was pre-registered in
`config/preregistered_candidates.json` (commit `28465a3`) before the run. Because the edge gate had
already failed on the development period, the look is documentation-only.

| XAUUSD H-11 fade k5, H = 30 | Trades | Net EV [95% CI] | PF | Win rate | Max DD | Net return | R by year |
|---|---|---|---|---|---|---|---|
| Base costs | 784 | **−0.055R** [−0.110, +0.000] | 0.86 | 46.2% | 9.8% | −8.3% | 2024: −35.2, 2025 H1: −8.1 |
| Spread ×2 | 779 | **−0.073R** [−0.127, −0.017] | 0.82 | 45.4% | 11.8% | −10.8% | 2024: −47.6, 2025 H1: −9.4 |

The dev-period sign **reversed out of sample**. H-11 is **REJECTED** (`VERIFIED` by EXP007). The final
test period (from 2025-07) was not touched and remains available for any future, genuinely new
hypothesis.

## 7. Why the edge does not survive (EXP008)
- The reversal is statistically real in gross terms: thousands of events, and FDR q < 0.01.
- But its gross information ratio per event is only 0.05–0.09, and 0.02 after costs.
- At about 1,000 events per year, that gives an annual t-statistic of roughly 0.6. Confirming such an
  edge at t = 3 would take **20–40 years**.
- Any small error in the spread model, slippage or latency easily wipes it out, and the stress rows
  in §5 show exactly that.
- This matches the literature prior (`PUBLISHED`, §6 of `literature_review.md`): published intraday
  FX effects are a few basis points and usually measured before costs.

## 8. Limitations
1. Bid-only data with **modelled spreads**. Real IC Markets spreads could be tighter (helping) or
   wider in stressed minutes (hurting); reversals after impulses often coincide with spread spikes.
2. Commission and contract specs are unverified.
3. Single data vendor. Retail M1 feeds contain bad prints, and short-horizon reversal is also what
   data noise looks like. Entry at the next bar's open removes single-print bounce-backs, but not
   every possible artifact.
4. 2023 has about 50k missing minutes.
5. The hypothesis set is finite. "No edge found" applies to what was tested, not to every possible
   M1 strategy. True order-flow or order-book data, which we lack, is where the microstructure
   literature finds predictability.
6. The Pine prototype has not been compiled on TradingView. The signal *algorithm* was verified
   against Python (`tests/test_pine_parity.py`), but not its syntax.

## 9. What would change the verdict (recommended next research, in order)
1. **Observed spreads.** Export IC Markets MT5 M1 data with spread (`tools/mql5/ExportM1WithSpread.mq5`),
   or allow Dukascopy data, and re-run EXP005/006 with the real cost at the event minute.
2. **Forward paper test of the single best idea** (XAUUSD H-11 k5/30 m) on an IC Markets demo. Use a
   sequential stopping rule (`paper_trading_plan.md`), mainly to *measure real costs at impulse
   moments*.
3. New hypotheses need new information: economic-calendar surprises (ABDV 2003), or order-flow data.
   Recycling price-only M1 features is unlikely to help.

**MQL5:** not recommended. A spec exists (`mql5_spec.md`), but per the project rules no EA code will
be written without explicit human approval, and the evidence does not justify asking for it.

## 10. Reproducibility
See `docs/deliverables/REPRODUCE.md`. All experiments are deterministic scripts with JSON outputs in
`results/`. The CI logs for each run are on the `ci-results` branch.
