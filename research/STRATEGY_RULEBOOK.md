# STRATEGY RULEBOOK — "Gold reversal with DXY entry-model inversion" (tomtrades, V = xSVlVpXLuV0)

This is the authoritative specification. Code, tests and reports refer to the rule IDs below.
Source tags: **V mm:ss** = the target video; **S#** = the same author's other videos (definitions only, see
[`supplementary_sources.md`](supplementary_sources.md)); **[A-##]** = an ambiguity decision in [`AMBIGUITIES.md`](AMBIGUITIES.md);
**[PROJECT]** = a Quantum Edge hard rule from `CLAUDE.md`, not from the video.
Status of the whole strategy: **HYPOTHESIS** (not yet tested by us). Author claims (64% → 82% win rate) are unverified.

## 0. One-paragraph summary
Gold is traded only as a **reversal of a one-hour candle's overextension**. In a middle-timeframe market that is ranging
(not trending), wait for a new **hourly candle** to open and **drive one way for ≥ ~20 minutes without a real pullback**
into the outer half of the previous middle-timeframe move. Around **minute 30** (22–52), wait for a **1-minute "type three"
shift** against that drive (the drive takes out a high, then price breaks the last swing low). Take the trade **only if DXY
shows the mirror image at the same time**: DXY drove the other way in the same candle, into the opposite half of its own
previous move, and shifted the other way. Stop beyond the drive's extreme, target **50% of the drive**.

## A. Market
| ID | Rule | Source | Conf. |
|---|---|---|---|
| MKT-1 | Instrument: **XAUUSD** (spot/CFD; GC futures equivalent). The video does not apply the method to other symbols. | V 00:38 | HIGH |
| MKT-2 | Correlated instrument: **DXY** (US dollar index), inverse relationship. | V 00:38–02:21, 09:02 | HIGH |
| MKT-3 | Execution / structure timeframe: **M1**. | V 04:04 ("1-minute break"), V 10:06 | HIGH |
| MKT-4 | Candle (timing) timeframe: **H1** (default, the only one with author-given numbers). V also demonstrates **M15** candles (T-02..T-04), so `CandleMode` = H1 / M15 / H1_AND_M15 runs independent candle trackers (one position at a time). M15 timings are an extrapolation (experimental). | V slide 01:49, V 09:21, V 04:25, 05:29, 06:15; S1, S2, S4 [A-07] | MED–HIGH (H1) / LOW (M15 numbers) |
| MKT-5 | Trading hours: the trade candle must open between **10:00 Asia/Tokyo** (2nd hour of Asia) and **11:00 Europe/London** (4th hour of London), DST-correct. No New York. | S1 00:21, S4 02:26, S2 285:14 [A-13] | MEDIUM |
| MKT-6 | Days: Monday–Friday; no day is excluded by the video. | V 05:52 (Monday), 09:02 (Wednesday) | MEDIUM |
| MKT-7 | Timezone: all session logic in local exchange time via DST rules (Tokyo has no DST); bar timestamps are server time converted to UTC. | [PROJECT] | HIGH |

## B. Middle-timeframe context (where the video says "identify a middle time frame range")
| ID | Rule | Source | Conf. |
|---|---|---|---|
| CTX-1 | MTF = the **300 minutes** (5 h) of closed bars before the candle opens. | S6 01:22, S3 01:22, S4 02:46 (4–5 h) | MEDIUM |
| CTX-2 | MTF swings: zig-zag on M5 bars, reversal threshold = 2.0 × ATR(M5,14). | [A-04] (our formalisation) | LOW |
| CTX-3 | Condition from the **median pullback ratio** r̃ of completed zig-zag legs: r̃ < 0.50 **TREND**; 0.50 ≤ r̃ < 0.75 **TRENDING_RANGE**; r̃ ≥ 0.75 **RANGE**. | S2 218:28–222:27, S4 03:07 | MEDIUM |
| CTX-4 | **TREND ⇒ no trade.** TRENDING_RANGE and RANGE are tradable. | V 01:36 ("range"); S4 02:46, S2 104:47 | HIGH |
| CTX-5 | Undefined condition (fewer than 2 ratios, or < 80% of the window's minutes present) ⇒ no trade. | V 02:40 ("unclear … don't take a trade") | MEDIUM |
| CTX-6 | MTF direction (HH+HL bullish, LH+LL bearish, else neutral) is recorded; it only matters in `CONDITION_AWARE` location mode. | S2 205:39 | MEDIUM |

Formal: BullishContext / BearishContext do not exist as entry requirements. The video's setups go both with and against the
MTF direction (V 02:59 with, V 03:20 against). The context gate is `Tradable = condition ∈ {RANGE, TRENDING_RANGE}`.

## C. Trigger — the hourly candle's overextension (how price must arrive)
For a **SELL** setup the candle drives **up** (bullish extension); for a **BUY** setup it drives **down**. Definitions below
are for the bullish extension; the bearish one is the mirror.
| ID | Rule | Source | Conf. |
|---|---|---|---|
| EXT-1 | Only bars **inside the current candle** count. extreme E = highest high since the candle open (first bar that set it); origin O = lowest low from the candle open to the extreme bar. | V 01:49 slide ("wait for the hourly candle to open and overextend"), S1 00:43 | HIGH |
| EXT-2 | Duration: (extreme bar − origin bar + 1) ≥ **18 minutes** ("around 20", "not lower than 18"). A late start is allowed. | V 01:36; S1 01:24, 05:57, 06:19 [A-05] | MEDIUM–HIGH |
| EXT-3 | One-directional: for every bar k between origin and extreme, (running max high − Low[k]) / (E − O) < **0.50**. | S1 01:24, 07:45 [A-05] | MEDIUM |
| EXT-4 | **Location**: E ≥ the 50% level of the most recent MTF **down**-leg (upper half of the previous bearish move / of the range). Mirror for buys. | V 01:36, 02:59, 03:42, 04:47, 06:15, 09:21; S3 02:04 [A-06] | MEDIUM |
| EXT-5 | (optional, off) E must exceed the previous candle's high. | S1 00:43 [A-21] | — |
| EXT-6 | (optional, off) E − O ≥ k × ATR(M1,14) ("high volume"). | S1 01:04 [A-15] | — |

## D. Entry model — the 1-minute type-three shift
| ID | Rule | Source | Conf. |
|---|---|---|---|
| SHF-1 | M1 swing points: fractal pivots, strength N = 2 (known only after N bars close). | [A-03] | LOW–MED |
| SHF-2 | **Bearish type-three shift**: the extension took out a prior M1 swing high (E > that pivot high), and then an M1 bar **closes below the protected low** PL = the most recent confirmed M1 pivot low before the extreme bar. Mirror for bullish. | S4 05:32 ("break a high into immediately breaking a low"), S2 240:36; V 04:04, 07:37, 10:06 | HIGH (concept) / MEDIUM (close) [A-02] |
| SHF-3 | Timing: the bar confirming the shift must close at minute **22–52** of the candle. Shifts outside the window are ignored. | V 01:36 ("around the 30-minute mark"), V 04:04, 09:21; S2 104:47 [A-08] | MED–HIGH |
| SHF-4 | The extension that the shift reverses must satisfy EXT-1…EXT-4 at the shift bar. A new extreme after a shift restarts the search. | V 01:36 (sequence) | HIGH |
| SHF-5 | Each extension extreme is evaluated (shift + DXY gate) at most once per direction; a new extreme restarts the search (SHF-4). At most one trade per candle. | [A-20] | MEDIUM |

## E. Correlation gate — DXY entry-model inversion (the subject of the video)
Evaluated at gold's signal bar, on DXY bars with the same timestamps. For a gold SELL the DXY mirror is a DXY BUY setup.
| ID | Rule | Source | Conf. |
|---|---|---|---|
| COR-1 | **Reject if DXY moved in the same direction** as gold since the candle open (for a gold sell: DXY's largest excursion since the open is upward, or DXY was above its open when gold made its extreme). | V 05:08, 05:52, 08:22 | HIGH |
| COR-2 | DXY's opposite extreme (for a gold sell: DXY's low since the open) lies in the **opposite half** of DXY's own previous MTF move (≤ 50% of DXY's most recent MTF up-leg). | V 02:40, 03:42, 05:29, 06:35 | MED–HIGH |
| COR-3 | DXY printed the **opposite type-three shift** (for a gold sell: a bullish DXY shift) after its extreme and **no later than gold's signal bar**, inside the same candle. | V 02:00, 02:21 ("would I enter exactly where this pair currently is right now?"), 02:59 ("ideally"), 09:42 | MEDIUM [A-09] |
| COR-4 | DXY's own drive is **not** required to meet the 18-minute / no-pullback test. | V 09:21 ("low volume … not exactly what I want … but still … opposite") | MEDIUM |
| COR-5 | DXY data: broker DXY symbol if present, else the synthetic ICE formula from six USD pairs (close-only). | [A-10] | MEDIUM |

`DxyMode`: **FULL** = COR-1+2+3 (default) · MIRROR_DIRECTION = COR-1+2 · OFF = research ablation only.

## F. Entry execution
| ID | Rule | Source | Conf. |
|---|---|---|---|
| ENT-1 | **BREAK** (default): market order at the open of the next M1 bar after the shift bar closes; sell at bid, buy at ask. | V 01:49 ("enter on that shift"), V 04:04, 07:37 [A-01] | MEDIUM |
| ENT-2 | **PULLBACK_50** (variant): limit at 50% of the breaking leg (E → lowest low since E, for a sell); re-anchored while the leg extends; cancelled if TP trades first, if E is exceeded, or at the candle's end. | S1 02:50, S4 13:40, V 10:06 [A-01] | MEDIUM |
| ENT-3 | Reject if the entry price is already beyond the target (no reward) or if the stop distance ≤ 0. | V 01:36 (the trade *is* the correction) | HIGH |
| ENT-4 | At most one open position from this strategy. | [PROJECT] | HIGH |

## G. Stop loss
| ID | Rule | Source | Conf. |
|---|---|---|---|
| SL-1 | Sell: SL = extension high E + spread at entry + buffer. Buy: SL = extension low − buffer. buffer = max(StopBufferPoints, 0.10 × ATR(M1,14)). | V 01:49 slide ("stop behind the most recent high or low"), V 04:04, 07:37, 10:27; S5 07:00 [A-11] | HIGH (location) / LOW (buffer) |

## H. Take profit
| ID | Rule | Source | Conf. |
|---|---|---|---|
| TP-1 | TP = 50% of the extension: O + 0.5 × (E − O), wicks included, on the bid chart. For sells the order TP is placed one entry-spread higher so it triggers when the bid touches the level. | V 01:36, 01:49, 02:59, 04:04, 10:27; S1 03:11, 06:41 [A-12] | HIGH |
| TP-2 | (option) Fixed R multiple. Discretionary targets (V 07:37 "previous lows") are not reproducible and not implemented. | [A-12] | — |

## I. Trade management
| ID | Rule | Source | Conf. |
|---|---|---|---|
| MGT-1 | No break-even, no partial close, no trailing, no adding. | V (never mentioned); S5 (5–10 min trades) [A-14] | HIGH |
| MGT-2 | Time stop: close after **120 minutes** at the latest. | [PROJECT] | HIGH |
| MGT-3 | Close before the 17:00 New York rollover blackout. | [PROJECT] | HIGH |

## J. Invalidation (reasons NOT to trade) — each one is logged with this code
| Code | Condition | Source |
|---|---|---|
| INV_SESSION | candle outside MKT-5 | S1, S2 |
| INV_CONTEXT_TREND | CTX-4 | V 01:36; S4 02:46 |
| INV_CONTEXT_UNDEFINED | CTX-5 | V 02:40 |
| INV_NO_EXTENSION | no extension satisfying EXT-2/EXT-3 before minute 52 | V 01:36; S1 |
| INV_LOCATION | extension never reached EXT-4 | V 04:47, 06:15 |
| INV_NO_SHIFT | no type-three shift by minute 52 | V 01:36; S2 104:47 |
| INV_DXY_SAME_DIRECTION | COR-1 failed | V 05:52 |
| INV_DXY_NO_INVERSION | COR-2 or COR-3 failed | V 02:40 |
| INV_TARGET_REACHED | ENT-3 | V 01:36 |
| INV_NO_PULLBACK | PULLBACK_50 limit not filled (author: "you miss the trade") | S4 13:40 |
| INV_STRUCTURE_BROKEN | extreme exceeded before a PULLBACK_50 fill | S4 14:45 |
| SAFE_SPREAD / SAFE_DAILY_LOSS / SAFE_MAX_TRADES / SAFE_POSITION_OPEN | safety layer (section L) | [PROJECT] |

## K. Risk ([PROJECT] hard rules, not from the video)
RSK-1 risk 0.20% of equity per trade at the stop, **including commission** · RSK-2 1.00% planned daily loss lockout (FX day
17:00 New York) · RSK-3 one position at a time · RSK-4 no martingale, grid, averaging down, or size-up after losses.
Lot size = floor(budget / (loss per lot at the stop distance via tick value/tick size + round-trip commission per lot) /
volume step) × volume step, clamped to [min, max] volume; a trade below min volume is skipped (never rounded up).

## L. Safety layer (separate from the strategy; every rejection is logged)
SAF-1 max spread (points) · SAF-2 max deviation/slippage (points) · SAF-3 max trades per day (0 = off) · SAF-4 **real
accounts are log-only** (tester and demo trade; there is no input to override this — live trading needs separate human
approval) · SAF-5 order-error breaker.

## M. State machine (per candle)
```
IDLE ──candle opens in session──▶ CONTEXT ──trend/undefined──▶ DONE(INV_CONTEXT_*)
CONTEXT ──tradable──▶ TRACK_EXTENSION (both directions, every closed M1 bar)
TRACK_EXTENSION ──EXT-2..4 hold for a direction──▶ WAIT_SHIFT(dir)   (the extension can keep growing)
WAIT_SHIFT ──type-3 shift closes at minute 22–52──▶ CORRELATION_CHECK
CORRELATION_CHECK ──fail──▶ WAIT_SHIFT (other direction may still fire) / log INV_DXY_*
CORRELATION_CHECK ──pass──▶ ORDER (BREAK: market next bar; PULLBACK_50: pending limit)
ORDER ──filled──▶ IN_POSITION ──TP / SL / 120 min / rollover──▶ DONE
ORDER ──expired / TP first / extreme exceeded──▶ DONE(INV_NO_PULLBACK / INV_TARGET_REACHED / INV_STRUCTURE_BROKEN)
any state ──minute 52 passes without a signal──▶ DONE(INV_NO_SHIFT or INV_NO_EXTENSION or INV_LOCATION)
```
All transitions happen on closed M1 bars; no state uses a bar that has not closed.
