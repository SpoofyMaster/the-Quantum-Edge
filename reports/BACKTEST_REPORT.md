# Backtest report — EXP009 (Python reference implementation)

**What this is.** The first objective test of the strategy as specified in `research/STRATEGY_RULEBOOK.md`, run with the
Python reference implementation (`qe/video_strategy`), which the MQL5 EA mirrors. **It is not an MT5 Strategy Tester
run** — the EA is not compiled yet (U-5) and the tester runs are U-6. Result file:
[`results/exp009_video_gold_dxy.json`](../results/exp009_video_gold_dxy.json).
Command: GitHub Actions `research` workflow, run
[37216270187](https://github.com/SpoofyMaster/the-Quantum-Edge/actions/runs/37216270187), inputs
`experiment=exp009_video_gold_dxy symbols=XAUUSD,UDXUSD source=histdata start=2020-01-01 end=2025-07-01`.

**Pre-registration.** All seven variants were fixed in `experiments/exp009_video_gold_dxy.py` at commit `efe9070`
(recorded as `spec_commit` in the result) before any market data was loaded. Nothing was tuned afterwards.

## Data and costs
| Item | Value |
|---|---|
| Gold | HistData XAUUSD M1, **bid only**, 2020-01-02 → 2025-06-30, 1,901,183 bars |
| DXY | HistData UDXUSD (ICE dollar index) M1, 1,673,329 bars (≈ 88% of gold minutes; missing minutes are skipped, never filled) |
| Spread | **modelled** (0.10 USD × New-York-hour profile from `qe/data/store.py`), not observed |
| Commission | 3.50 USD per lot per side (UNVERIFIED for IC Markets metals) |
| Slippage | 1 tick on market entries and stops (3 ticks in the stress variant) |
| Risk | 0.20% of equity per trade incl. costs, 1% daily loss lockout, one position at a time, ≤ 120 min |
| Locked period | ≥ 2025-07-01 not loaded (final-test lock) |

## Results (Phase 23 metrics)
| Metric | V0_VIDEO_DEFAULT | V1_PULLBACK_50 | V2_M15 | V3_H1_AND_M15 | V4_ABLATION_DXY_OFF | V0_STRESS_SPREAD2X | V0_STRESS_SLIP3 |
|---|---|---|---|---|---|---|---|
| Trades | 123 | 66 | 0 | 123 | 1330 | 109 | 120 |
| Win rate | 0.593 | 0.424 | — | 0.593 | 0.580 | 0.596 | 0.592 |
| Net profit (USD) | -3,952 | -1,623 | — | -3,952 | -34,879 | -4,689 | -4,190 |
| Net profit (% of 100k) | -3.95 | -1.62 | — | -3.95 | -34.88 | -4.69 | -4.19 |
| Gross profit (USD) | 3,883 | 4,320 | — | 3,883 | 37,177 | 2,916 | 3,629 |
| Gross loss (USD) | 7,835 | 5,943 | — | 7,835 | 72,057 | 7,605 | 7,819 |
| Profit factor | 0.50 | 0.73 | — | 0.50 | 0.52 | 0.38 | 0.46 |
| Expected payoff (USD/trade) | -32.1 | -24.6 | — | -32.1 | -26.2 | -43.0 | -34.9 |
| EV (R/trade, net) | -0.164 | -0.124 | — | -0.164 | -0.162 | -0.221 | -0.179 |
| Max drawdown (USD) | 4,178 | 2,389 | — | 4,178 | 34,897 | 4,707 | 4,349 |
| Max drawdown (%) | 4.18 | 2.39 | — | 4.18 | 34.90 | 4.71 | 4.35 |
| Avg duration (min) | 12.3 | 13.9 | — | 12.3 | 11.1 | 13.4 | 12.6 |
| Avg winner (USD) | 53.2 | 154.3 | — | 53.2 | 48.2 | 44.9 | 51.1 |
| Avg loser (USD) | -156.7 | -156.4 | — | -156.7 | -128.9 | -172.9 | -159.6 |
| Avg winner (R) | 0.274 | 0.782 | — | 0.274 | 0.301 | 0.233 | 0.264 |
| Avg loser (R) | -0.805 | -0.792 | — | -0.805 | -0.799 | -0.891 | -0.821 |
| Max consecutive losses | 5 | 5 | — | 5 | 10 | 5 | 5 |
| Trades per month | 1.86 | 1.00 | — | 1.86 | 20.15 | 1.65 | 1.82 |
| Long / short | 59 / 64 | 28 / 38 | — | 59 / 64 | 593 / 737 | 50 / 59 | 57 / 63 |
| DSR (family trials) | 0.0016 | 0.0520 | — | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| EV 95% CI (R) | [-0.262, -0.061] | [-0.270, 0.027] | — | [-0.262, -0.061] | [-0.199, -0.128] | [-0.316, -0.118] | [-0.267, -0.084] |

### By year (trades, EV R)
| Variant | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|
| V0_VIDEO_DEFAULT | 25, -0.195 | 14, -0.048 | 24, -0.313 | 30, -0.120 | 22, -0.060 | 8, -0.276 |
| V1_PULLBACK_50 | 14, -0.163 | 7, 0.012 | 16, -0.204 | 12, -0.089 | 13, 0.008 | 4, -0.445 |
| V2_M15 | — | — | — | — | — | — |
| V3_H1_AND_M15 | 25, -0.195 | 14, -0.048 | 24, -0.313 | 30, -0.120 | 22, -0.060 | 8, -0.276 |
| V4_ABLATION_DXY_OFF | 239, -0.118 | 262, -0.168 | 237, -0.273 | 199, -0.131 | 255, -0.132 | 138, -0.132 |
| V0_STRESS_SPREAD2X | 23, -0.253 | 13, -0.115 | 21, -0.349 | 24, -0.197 | 21, -0.111 | 7, -0.339 |
| V0_STRESS_SLIP3 | 25, -0.205 | 13, -0.066 | 23, -0.335 | 30, -0.132 | 21, -0.075 | 8, -0.282 |

### By session (trades, win rate, EV R)
| Variant | ASIA | LONDON |
|---|---|---|
| V0_VIDEO_DEFAULT | 34, 0.62, -0.203 | 89, 0.58, -0.150 |
| V1_PULLBACK_50 | 19, 0.42, -0.162 | 47, 0.43, -0.109 |
| V2_M15 | — | — |
| V3_H1_AND_M15 | 34, 0.62, -0.203 | 89, 0.58, -0.150 |
| V4_ABLATION_DXY_OFF | 733, 0.57, -0.183 | 597, 0.59, -0.135 |
| V0_STRESS_SPREAD2X | 29, 0.66, -0.249 | 80, 0.57, -0.211 |
| V0_STRESS_SLIP3 | 33, 0.61, -0.218 | 87, 0.59, -0.164 |

### Sub-periods (acceptance criterion: positive in >= 2 of 3)
| Variant | 2020-2021 | 2022-2023 | 2024-2025H1 |
|---|---|---|---|
| V0_VIDEO_DEFAULT | 39, -0.142 | 54, -0.206 | 30, -0.118 |
| V1_PULLBACK_50 | 21, -0.105 | 28, -0.154 | 17, -0.098 |
| V2_M15 | — | — | — |
| V3_H1_AND_M15 | 39, -0.142 | 54, -0.206 | 30, -0.118 |
| V4_ABLATION_DXY_OFF | 501, -0.144 | 436, -0.208 | 393, -0.132 |
| V0_STRESS_SPREAD2X | 36, -0.203 | 45, -0.268 | 28, -0.168 |
| V0_STRESS_SLIP3 | 38, -0.158 | 53, -0.220 | 29, -0.132 |

### Setup funnel (H1 tracker of V0): reason counts per candle
| Reason | Candles | Share |
|---|---|---|
| INV_NO_SHIFT | 4467 | 30.3% |
| INV_CONTEXT_UNDEFINED | 3495 | 23.7% |
| INV_NO_EXTENSION | 2441 | 16.6% |
| INV_DXY_NO_INVERSION | 1500 | 10.2% |
| INV_DXY_SAME_DIRECTION | 1045 | 7.1% |
| INV_CONTEXT_TREND | 961 | 6.5% |
| INV_LOCATION | 537 | 3.6% |
| INV_TARGET_REACHED | 147 | 1.0% |
| TRADE | 123 | 0.8% |
| INV_DXY_NO_DATA | 7 | 0.0% |


## Acceptance (V0, the video defaults) — `docs/research/hypotheses.md`
| Criterion | Result |
|---|---|
| Net EV > 0 with 95% CI above 0 | **No**: −0.164R, CI [−0.262, −0.061] (significantly *negative*) |
| Deflated Sharpe > 0.95 | **No**: 0.002 (7 trials in this family); ≈ 0 against all 350 project trials |
| Positive in ≥ 2 of 3 sub-periods | **No**: negative in all three |
| Survives cost stress | **No**: −0.221R (spread ×2), −0.179R (3-tick slippage) |

**Verdict: H-12 REJECTED as implemented** (on this data and with this specification).

## What the numbers say
1. **No edge after costs in any variant.** The best variant (V1, 50% pullback entry) is −0.124R per trade, CI
   [−0.270, +0.027], negative in every sub-period. 
2. **The DXY inversion filter — the subject of the video — does not improve expectancy here.** Without the gate (V4)
   the same gold setups give 1,330 trades at −0.162R and a 58.0% win rate; with the gate (V0) 123 trades at −0.164R and a
   59.3% win rate. The author's claim was 64% → 82% win rate when adding correlation; we measure +1.3 percentage points
   and no change in EV. The gate mainly removes trades (−91%), which lowers the drawdown (4.2% vs 34.9%) only because
   fewer losing trades are taken.
3. **Why a 59% win rate still loses:** with the literal "enter on the break" rule, the entry is already close to the 50%
   target. Average winner +0.27R vs. average loser −0.81R (all net of costs); 10 of the 83 target exits in V0 were net
   losers because the reward was smaller than spread + commission. The pullback entry (V1) restores a ~1:1 profile
   (+0.78R / −0.79R) but then wins only 42%.
4. **M15 (V2) produced no trades.** In 470 M15 candles a shift reached the DXY gate and in 3 it passed (0.6%; H1: 270 of
   2,815 candles, 9.6%; counts are per candle, from the reason funnel).
   Requiring DXY to complete its own type-3 shift within the 6–13-minute window is almost never met. V3 (H1+M15) is
   therefore identical to V0. This is a property of the extrapolated M15 timings (A-07, LOW confidence), not a
   crash; the M15 path is covered by the fixture tests T-02/T-04.
5. **Costs matter but are not the whole story.** Doubling the modelled spread costs ≈ 0.057R per trade; removing the
   spread entirely would therefore add roughly +0.06R and leave V0 near −0.10R (an estimate by linear extrapolation,
   not a run).

## Caveats (what this result does NOT show)
- It tests **our reconstruction**. The author trades with discretion (targets such as "previous lows", the "shift
  within the shift" on a 5-second chart, judgement of "high volume"); these are not reproducible from the video.
- The MTF context is a formalisation (A-04): 23.7% of in-session H1 candles were "undefined" (too few zig-zag legs).
  A different zig-zag size changes which candles qualify; it cannot change the finding that the DXY gate adds nothing
  to the setups it filters (V0 vs. V4 use identical gold logic).
- Data: bid-only HistData with modelled spreads, one vendor, a known 2023 gap; DXY from the same vendor.
- Not yet reproduced in MT5. The EA's own tester run (U-6) is the next independent check; expected differences are
  listed in `mql5/VideoStrategyEA/README.md`.
- "No edge found" in this test is a valid result. It does not prove that the author's discretionary trading has no
  edge; it shows that the rules that can be extracted from the video do not produce one in 2020–2025H1.

## Reproduce
```bash
# CI (needs the data cache or network access to histdata.com):
#   Actions → research → Run workflow (ref = this branch) with the inputs above
# locally, after fetching data into data/m1/:
python scripts/fetch_histdata_m1.py XAUUSD,UDXUSD 2020 2025
python experiments/exp009_video_gold_dxy.py
```
