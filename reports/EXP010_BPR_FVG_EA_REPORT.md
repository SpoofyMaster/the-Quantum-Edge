# EXP010: BPR + FVG EA setups on XAUUSD (hypothesis H-13)

**Verdict: REJECTED as specified.** The default setup lost **−0.37 R per trade** after costs, and no variant passes the
pre-registered acceptance rules. Every claim below is `VERIFIED` and comes from
[`results/exp010_bpr_fvg_ea.json`](../results/exp010_bpr_fvg_ea.json).

| | |
|---|---|
| **CI run** | `research` workflow, run 37792966182 |
| **Code** | branch `claude/modest-brown-81jwa0` at `8ed8730` |
| **Pre-registration** | `experiments/exp010_bpr_fvg_ea.py` as of commit `880ac1c` (`spec_commit` in the result). The file has not changed since. |
| **Rules** | [`research/indicators/BPR_FVG_EA_SPEC.md`](../research/indicators/BPR_FVG_EA_SPEC.md), fixed from the owner's sketch before any data was looked at. |
| **Implementation** | `qe/strategies/bpr_fvg.py`. Its decisions equal the MQL5 EA's pure modules event by event (`tests/test_bpr_fvg_ea_harness.py`). |

## Setup

| Item | Value |
|---|---|
| Market | XAUUSD, HistData M1 bid bars, 2020-01-01 → 2025-06-30. That is 1,901,183 M1 bars, or 380,348 M5 bars. The final-test period from 2025-07-01 stays locked. |
| Spreads | Time-of-day model, base 0.10 (**assumed**: HistData is bid-only) |
| Commission | 3.50 USD per lot per side (`UNVERIFIED`) |
| Slippage | 1 tick on market orders and stops |
| Execution | Spec §5, bar-based, with conservative same-bar rules: a stop is assumed to hit before a target, and a limit order that touches TP1 on its fill bar is cancelled. |
| Risk and session | 0.20 % per trade including costs; daily lockout at −5 R. Entries 08:00 London → 14:45 New York; flat at 16:44 New York; holds ≤ 120 min. |
| Trials | 7, registered in `results/trial_registry.jsonl` (`data_kind = market_bpr_ea`). The registry now has 357 lines. |

## Results

| Variant | Trades | Per month | Win rate | EV (R) | 95 % CI | PF | DSR | Max DD |
|---|---|---|---|---|---|---|---|---|
| **V0** BPR, LIMIT, M1 (EA defaults) | 62 | 0.94 | 19.4 % | **−0.368** | [−0.705, +0.030] | 0.54 | 0.086 | 4.8 % |
| V1 BPR, CONFIRM, M1 | 92 | 1.42 | 22.8 % | −0.343 | [−0.580, −0.105] | 0.56 | 0.010 | 6.3 % |
| V2 BPR, LIMIT, no sweep/MSS (ablation) | 360 | 5.45 | 26.9 % | −0.233 | [−0.372, −0.077] | 0.68 | 0.000 | 18.4 % |
| V3 FVG, LIMIT, M1 | 565 | 8.56 | 32.9 % | −0.121 | [−0.238, +0.001] | 0.82 | 0.000 | 16.6 % |
| V4 BPR, LIMIT, M5 | 63 | 0.98 | 30.2 % | −0.067 | [−0.387, +0.286] | 0.90 | 0.112 | 3.8 % |
| V0, spread × 2 | 19 | 0.32 | 36.8 % | +0.036 | [−0.667, +0.763] | 1.06 | 0.321 | 1.2 % |
| V0, slippage 3 ticks | 30 | 0.47 | 20.0 % | −0.338 | [−0.699, +0.032] | 0.58 | 0.063 | 2.5 % |

**Sub-periods for V0** (EV in R):

| Period | Trades | EV (R) |
|---|---|---|
| 2020–21 | 15 | −0.47 |
| 2022–23 | 13 | +0.10 |
| 2024–25H1 | 34 | −0.50 |

**V0 acceptance:** CI above 0 ✗, DSR > 0.95 ✗, positive in ≥ 2 of 3 sub-periods ✗, survives the cost stress ✗.
**REJECTED.**

## What happened to V0's 66,565 BPR setups

| Outcome | Setups | Share |
|---|---|---|
| Zone broken before an order was placed | 35,489 | 53 % |
| No sweep | 23,455 | 35 % |
| Expired (60 bars) | 7,146 | 11 % |
| Order placed, cancelled because price reached TP1 first (runaway) | 410 | 0.6 % |
| **Filled and traded** | **62** | **0.09 %** |

In V0, 50 of 62 trades hit the full stop. The R distribution is almost binary:

| | |
|---|---|
| Median trade | −1 R |
| 95th percentile | +3.7 R |
| Average winner | +2.27 R |

## Reading

1. **The sketch's entry is adversely selected.** A limit order near the far edge of the zone fills mostly when price
   is breaking through the zone. Pullbacks that respect the zone tend to turn before reaching it: those are the 410
   runaway cancellations. The fills are therefore skewed toward losers. The CONFIRM entry (V1) waits for a rejection
   candle, but it is no better (−0.34 R).
2. **The filters do not add value.** Removing the sweep and MSS filters (V2) gives more trades and a smaller loss per
   trade (−0.23 R vs −0.37 R). They do not pick better trades. They only cut the sample.
3. **FVG and M5 are less bad, but they still lose.** Plain FVG retests (V3) lose −0.12 R, with the CI touching zero
   from below. M5 (V4) is close to −cost, which is what a strategy with no edge returns. Neither was the
   pre-registered primary.
4. **The "spread × 2" row is not evidence of anything.** Wider spreads made the cost filter (≤ 0.15 R) reject most
   setups, leaving 19 trades. A +0.04 R mean with a CI of ±0.7 R is noise.
5. **This matches earlier findings in the project.** No price-only M1 rule on these markets has survived costs (H-04,
   H-11, H-12). With no edge, the expected result is about −cost per trade.

## Limitations

- **Spreads are modelled, not observed** (HistData is bid-only). The commission is `UNVERIFIED`.
- **Fills are bar-based**, with conservative same-bar rules. The MT5 Strategy Tester with real ticks could fill some
  limits differently. `BprFvgEA` exists for exactly that check (U-12 below).
- **The sample is small** for V0, V4 and the stress rows (19–63 trades), so their confidence intervals are wide.
  However, V0's point estimate is −0.37 R, and V1 has a CI entirely below zero.
- **This tests the rules as specified from the sketch.** Discretionary judgement on which BPR to take (for example the
  manual sell-off ∩ rally overlap described in the playbook) is not captured.

## What this means for the EA

The EA works as a **charting and research tool**:
- it draws the LuxAlgo zones like the indicator;
- it detects the same setups as the Python reference.

Its default trading rules **did not show an edge**. They should not be traded with real money, and the project rules
forbid that anyway. Do not tune them on these results: any change is a new trial and would need fresh, untouched data.
Useful next steps:
- run the EA in the MT5 Strategy Tester (real ticks, 2020-01 → 2025-06), to confirm the reference result on broker
  data (U-12);
- use the EA visually to study BPR behaviour.
