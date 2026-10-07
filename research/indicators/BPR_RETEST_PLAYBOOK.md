# BPR retest long: reading the sketch and executing the trade

Sketch: [`sketches/bpr_retest_long.jpg`](sketches/bpr_retest_long.jpg), drawn by the project owner on 2026-10-07.

How this was produced:
- Two independent readings of the image, plus my own.
- One execution plan.
- One adversarial review of that plan, whose corrections are applied here (journal day04).

Status labels follow CLAUDE.md:

| Label | What it covers here |
|---|---|
| `PUBLISHED` | How the zone is calculated. Source: `LUXALGO_BPR_SPEC.md`, read from the LuxAlgo Pine code. |
| `HYPOTHESIS` | Whether the trade makes money. **This setup has not been tested in this project.** |

Paper/demo only; live trading needs separate, explicit approval.

---

## 1. What the sketch shows

Approximate pixel coordinates on the 1206 × 1154 image (y grows downward; a smaller y is a higher price).

| # | Point | Where | Meaning |
|---|---|---|---|
| A | start ≈ (35, 405) | above the box | prior high |
| B | low ≈ (147, 742) | below the box | first range low (sell-side liquidity) |
| C | high ≈ (269, 500) | above the box | lower high, the last swing high before the sweep |
| D | low ≈ (313, 1005) | far below | **sweep** of B: the lowest point |
| E | high ≈ (425, 678) | touches the box bottom from below | failed rally, the "W" neckline |
| F | low ≈ (510, 887) | below | **higher low** |
| H | high ≈ (583, 290) | far above | **one spike high**. The pen was lifted at the top, so this is one peak, not a double top. |
| G | end ≈ (697, 690) | box bottom level, to the right of the box | retracement end; the horizontal tail leads to the entry |

**Box "BPR":** y ≈ 575–681 (height h ≈ 107 px). It spans the range from the left until the rally leg. Price crosses
it 4 times in full, E touches it from below, and the final retracement comes back to its price band.

**Position tool:** a TradingView-style **Long Position**. The green target sits above, the red stop below.

| Level | y (px) | Distance |
|---|---|---|
| Entry | ≈ 688 | at the BPR **bottom** |
| Stop | ≈ 820 | about 1.2 h below the entry, and above F and D, so it is a "zone" stop, not a structure stop |
| Target | ≈ 97 | about 590 px above the entry, which is about the length of the F → H leg (597 px), so a **measured move**; it lies above H |

The drawn reward:risk is about **4.4–4.5 : 1**.

**The story in ICT terms:**
1. Price ranges around an equilibrium zone.
2. The C → D sell-off sweeps the sell-side liquidity under B and leaves a bearish fair value gap.
3. F holds as a higher low.
4. The F → H rally displaces through the zone, leaves a bullish fair value gap and breaks C, the market structure
   shift.
5. The overlap of the two gaps is the **Balance Price Range**.
6. Price retraces into it and you buy, expecting the rally to continue to a new high.

## 2. How LuxAlgo computes this BPR, and why it may draw it somewhere else

`PUBLISHED` (spec §2–§5):

- **Displacement candle:** body > `sma(body, 5)`, where the average includes the candle itself, and both wicks
  < 36 % of the body.
- **Gaps:**
  - bearish FVG on the next bar if `high < low[2]` (box `[high, low[2]]`);
  - bullish FVG if `low > high[2]` (box `[high[2], low]`).
- **The BPR pairs only the newest bullish gap with the newest bearish gap.**
  - **BPR_UP (green):** `dn.bottom < up.bottom < dn.top`. The box is `[up.bottom, dn.top]`.
  - **BPR_DN (red):** `up.bottom < dn.bottom < up.top`. The box is `[dn.bottom, up.top]`.
  - In both, the box top is the *other* gap's top (QUIRK 4). The true overlap top is `T* = min(up.top, dn.top)`.
- **`pos` for this setup is +1.** A BPR created on a bar that makes a bullish gap always closes above its bottom, so
  it counts as **support**:
  - a low below the top → border **dashed** ("entered");
  - a low below the bottom → **broken** (dotted, break colour).
- **When the box appears:** at the close of the bar after the displacement candle. Its left edge is the older gap's
  left edge, which is why the sketch's long box only exists in hindsight.

**Important for your sketch:**
- The E → F drop is about two box-heights deep. If it prints any bearish FVG, that gap becomes the newest bearish
  gap. The rally's gap is then paired with **it**, not with the C → D gap.
- The indicator's BPR then forms between F and E, **below your box, near your stop**.
- The box you drew (C → D gap ∩ F → H gap) is a *manual* ICT BPR. The indicator will usually not draw it.
- A toy simulation of the sketch confirmed this: 1 of about 1,130 BPRs fell in the drawn band. It is an ad-hoc run
  and not saved, so it is not `VERIFIED`.

What to do about it:
- Turn on **"Debug: draw the underlying FVG boxes"** and set **visible boxes to 4**. You then still see the older
  C → D gap and can mark the manual overlap yourself.
- Decide in advance which BPR you trade:
  - (a) only the indicator's box, as the default;
  - (b) the manual sell-off ∩ rally overlap, which needs its own written definition.

## 3. Setup checklist (all must be visible on closed bars)

| # | Item | Observable rule (suggested defaults; fix them before any test) |
|---|---|---|
| 1 | Liquidity pool | A known pool of sell stops below the range: the Asia low, the previous FX-day low (17:00 New York boundary) or ≥ 2 equal M5 lows. Each must be known **at that time**; the Asia low is final only after 15:00 Tokyo. |
| 2 | Sweep | The bid trades ≥ 1 spread below that low, then an M1 close comes back above it within ≤ 10 bars. There is no later close below D. |
| 3 | Displacement | The rally prints a displacement arrow, and a **new BPR with `pos = +1`** appears (alert or tooltip). The debug boxes show which bearish gap is the partner (§2). |
| 4 | Structure shift | An M1 close above the highest confirmed pivot high (5 bars left, 1 right) formed between the sell-off gap's left edge and the sweep, which is C in the sketch. A variant: a close above E, the W neckline. |
| 5 | Zone still active | The border is solid or dashed, **not dotted**, and the zone has not been pushed out by newer zones. |
| 6 | Pullback | No bearish displacement arrow and no new bearish FVG into the zone during the pullback. *Note: the sketch's last leg is near-vertical and would likely print one. Under this filter, the trade as drawn would be skipped. This filter is an addition, not part of the sketch.* |
| 7 | Room and costs | TP1 gives ≥ 1.5R net. Costs, computed as `qe.costs.cost_in_R`, are ≤ 0.15R. |
| 8 | Session | London 08:00–16:30 (Europe/London) or New York 08:00–17:00 (America/New_York). The last entry is at 14:45 New York, so the 120-minute time stop ends before the 16:45 rollover. No entry from 30 min before to 30 min after high-impact USD news. The spread is ≤ 3× the median for that clock hour over the previous 20 days. |
| 9 | Risk state | `realised loss today + planned risk of open trades + 0.20 % ≤ 1.00 %` of day-start equity. Open risk ≤ 0.60 %. ≤ 3 positions. No correlated position, e.g. a long XAGUSD. **One attempt per zone.** |

## 4. Execution on MT5 with `LuxAlgo_BPR`

**Before you start:**
- Compile the indicator in MetaEditor (U-9). Run the parity export once (U-10).
- Check the XAUUSD specification in MT5 (contract size, tick, volume step, stops level), plus the real commission
  from your deal history. The repo's values are `UNVERIFIED`.
- Confirm whether the account uses **hedging** or **netting**. On netting, two tickets merge into one position.

**Charts:**
- M5 or M1 chart with the indicator. One instance per chart.
- Ask line on (F8 → Show → Ask price line). Candles show the **bid**; buy orders fill on the **ask**.

**Inputs:**

| Input | Setting |
|---|---|
| Mode | **Historical** |
| Length | 5 |
| Show Displacement | true |
| Show FVGs | true |
| Balance Price Range | true |
| Options | **FVG** |
| # Visible FVG's | **4** (never ≥ 12) |
| Debug FVG boxes | **true** |
| Process forming bar | **false** (no repaint) |
| Alert on new BPR | true |

The debug FVG boxes are never restyled in BPR mode, so they show which gaps exist, not whether a gap is broken.

**Levels to write down** after the structure shift, before price returns:

| Level | Definition |
|---|---|
| `B` | box bottom (the true overlap bottom) |
| `T*` | `min(bullish gap top, bearish gap top)` (true overlap top; not the box top) |
| `h` | `T* − B` |
| `CE` | `B + h/2` |
| `H` | the rally high |
| `F` | the higher low |

### The entry problem at the bottom edge (as drawn)

The indicator breaks a `pos = +1` zone as soon as a bid **low < B**, and a wick is enough. A buy limit **at** `B` fills
only when ask ≤ B, which means bid ≤ B − spread. So a literal bottom-edge fill always happens on a bar that breaks the
zone. Choose one rule in advance:

| Rule | Entry | Comment |
|---|---|---|
| **R1, front-run** (closest to the sketch) | Buy Limit at **ask `B + δ + spread`**, with δ = 5 ticks on XAUUSD | Fills while the bid is still above `B`. |
| **R2, own invalidation** | Accept fills below `B` | A break *before* the fill cancels the order. After the fill, only the stop decides. |
| **R3, confirmation** | A closed M1 candle wicks into `[B, B + h/4]` and closes ≥ CE with close > open | Buy at the next bar's open. Fewer fills, worse price, confirmed zone. |

**Order rules:**
- The limit price and the targets are fixed when the order is placed; no re-pricing.
- Cancel the order if any of these happens:
  - the zone breaks before the fill;
  - 60 M1 bars pass since the BPR formed;
  - the bid reaches TP1 first;
  - a bearish displacement prints into the zone;
  - 14:45 New York arrives;
  - a news window starts.
- A zone that breaks before the fill is finished; there is no re-entry.

### Stop, targets and size

| Item | Rule |
|---|---|
| **Stop (bid)** | The lower of `B − 1.2·h` (the sketch) and the lower gap's bottom − 2 × spread. A structure stop under F is a wider alternative; choose in advance. A long's stop triggers on the **bid**, so spread widening that drops the bid can trigger it, typically at rollover and news. |
| **TP1 (bid)** | `H − 2 × spread`, just under the rally high. That buy stops rest above it is an ICT `HYPOTHESIS`. |
| **TP2 (bid), as drawn** | `entry + (H − F)`, a measured move. Or the next higher-timeframe liquidity, whichever comes first. A fixed 4.5R target is a separate variant. |
| **Size** | `lots = floor( (equity × 0.20 %) / ((ask_entry − SL_bid + slippage) × 100 + 2 × 3.50) / 0.01 ) × 0.01`, the same as `qe.risk.size_position`. |
| **Risk** | Spread and commission are inside the 0.20 %. Stop slippage beyond 1 tick (gaps, news) can make the loss larger. |

**Worked example.** XAUUSD:
- 100 oz per lot, tick 0.01, 3.50 USD per lot per side, spread 0.10, slippage 1 tick (all `UNVERIFIED`);
- equity 100,000 USD, so the risk budget is 200 USD.

| | Value |
|---|---|
| Bearish gap / bullish gap | [2,650.10, 2,651.40] / [2,650.40, 2,651.90] |
| `B` / `T*` / `h` / `CE` | 2,650.40 / 2,651.40 / 1.00 / 2,650.90 |
| `H` / `F` / `D` | 2,654.00 / 2,648.60 / 2,647.50 |
| Buy Limit (ask), R1 | 2,650.40 + 0.05 + 0.10 = **2,650.55** |
| Stop (bid) | min(2,649.20, 2,649.90) = **2,649.20** |
| Risk per lot | (1.35 + 0.01) × 100 + 7.00 = 143.00 USD |
| Size | floor(200 / 143 / 0.01) × 0.01 = **1.39 lots** → 198.77 USD = 1R |
| Costs | ≈ 0.14R (`cost_in_R`) |
| TP1 = 2,653.80 | +442.02 USD = **+2.22R**, break-even win rate 31.0 % |
| TP2 as drawn = 2,650.55 + 5.40 = 2,655.95 | +740.87 USD = **+3.73R**, break-even win rate 21.2 % |
| 50 % at TP1 + 50 % at TP2 (0.70 + 0.69 lots) | **+2.97R** |
| 50 % at TP1, rest at break-even + costs (2,650.62) | +1.12R |
| Stop hit | **−1.00R** |

**MT5 ticket (F9):**
- Pending order: Buy Limit 2,650.55, SL 2,649.20, TP 2,653.80, 0.70 lots.
- A second ticket of 0.69 lots with TP 2,655.95, on a hedging account.
- Count both tickets as one position for the risk limits.

## 5. Trade management

1. Stop and targets live on the server from the start. Never widen the stop, never average down, never add after a
   loss.
2. At TP1, close 50 %. Only then move the stop to entry + costs (2,650.62).
3. Trail the rest under each new confirmed M1 swing low, with the spread as a buffer.
4. Close at market 120 minutes after entry, and be flat before the 16:45 New York rollover and the weekend.
5. If price **closes through the BPR**:
   - the support failed; take no more longs on this zone;
   - a short is only a brand-new setup (§6).
6. **News:** no entries from 30 minutes before to 30 minutes after high-impact USD releases; close or reduce before
   the release. This project never tested a news filter.
7. **Daily stop:** −1 % realised, including commissions.

## 6. Mirror short

Run everything in mirror image:
- **Context:** a sweep of **buy-side** liquidity, then a bearish displacement down through the zone. That gives a
  **new BPR with `pos = −1`**, which counts as resistance and breaks on a bid **high > box top**. The box top can sit
  above `T*` (QUIRK 4).
- **Entry:** Sell Limit (bid) a few ticks below `T*`.
- **Stop:** `max(T* + 1.2h, upper gap top + 2 × spread)`, **plus the spread**, because a short's SL and TP trigger on
  the **ask**.
- **Targets:** TP1 just above the equal lows, plus the spread; TP2 a measured move down.

## 7. Pitfalls

| Pitfall | Effect | Remedy |
|---|---|---|
| Forming-bar repaint | A box can vanish before the close; `pos` changes tick by tick | Process forming bar = false; act on closed bars |
| Newest-pair rule (§2) | The indicator pairs the E → F gap and draws the BPR lower, or not at all | Debug FVG boxes on; decide (a)/(b) in advance |
| QUIRK 4 | Box top above the true overlap (about a third of creations on synthetic data) | Use `T*` and `CE` computed from the gaps |
| QUIRK 6 / 6b | Geometry is fixed at creation; a broken same-left box blocks new ones | No box does not mean no overlap; trade only what your rule defines |
| Visible boxes 2 | Newer BPRs push your zone off the chart | Use 4; never use 12 or more (QUIRK 11) |
| Present mode | The window depends on the data end (look-ahead in tests) | Historical mode |
| TradingView vs broker | Different bars give different gaps | Plan and execute on the broker's own chart |
| Server time | IC Markets is UTC+2/+3 (`UNVERIFIED`) | Convert session and news times to UTC with DST rules |
| Wick breaks | Breaks use high/low, not the close | Build this into the entry rule (§4) |
| Colour ≠ direction | Green/red is the geometry (UP/DN), not support or resistance | Read `pos` from the tooltip or alert |

## 8. Honesty: what is known about this trade

- **The drawn 4.5 : 1 is a payoff, not a probability.** With costs:
  - break-even win rate at TP1 is 31.0 %; at TP2 it is 21.2 %;
  - at a ~20 % win rate, losing streaks of ~16 trades are normal within 200 trades;
  - proving even +0.1R per trade would take ~1,700 trades.
- **This setup is untested (`HYPOTHESIS`).**
  - It has no experiment and no trial-registry entry.
  - The indicator is not yet compiled in MetaEditor and has no broker-data parity check.
- **Prior evidence in this project is discouraging.** Across 326 market trials (plus 24 synthetic checks), no
  price-only M1 rule was net-positive with a confidence interval above 0, and no Deflated Sharpe came near 0.95 (all
  ≤ 0.05). The closest relatives failed:
  - **H-04**, the previous-day high/low sweep: REJECTED;
  - **H-11**: +0.021R in development reversed to −0.055R out of sample;
  - **H-12**, the video strategy: its V1 used a 50 % pullback limit entry, with a 42.4 % win rate, −0.124R and a CI of
    [−0.270, +0.027].

  With no gross edge, the expected result is about **−cost ≈ −0.13R per trade**.
- **How to test it properly.** A pre-registered `EXP010`:
  - **Rules:** all of them frozen first, then a commit hash recorded.
  - **Data:** develop on 2020–2023, with one validation look at 2024-01 → 2025-06.
  - **Execution:** next-bar fills or the limit-fill model of `qe/video_strategy/engine.py`. Costs always on, plus a
    stress test.
  - **Baselines:** the same entries at a random level, and random direction.
  - **Reporting:** Deflated Sharpe over all trials.
  - **Locked period:** the final-test period (≥ 2025-07-01) stays locked. Demo trading today falls inside it, so
    demo results must not be used to tune the rules.
