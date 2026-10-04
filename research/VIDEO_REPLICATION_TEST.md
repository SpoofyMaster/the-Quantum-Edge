# Video replication test (Phase 14) — replaying V's examples through the specification

**Method.** Each example in [`VIDEO_TRADE_DATABASE.md`](VIDEO_TRADE_DATABASE.md) is replayed *by reasoning* through
[`ALGORITHM_SPECIFICATION.md`](ALGORITHM_SPECIFICATION.md), using what the author says and what the 320×180 frames show.
Prices and clock times are not readable, so numeric conditions (18 minutes, minute 22–52, 50% levels) can only be checked
where the speech or the frame geometry makes them evident. Each example is then encoded as a synthetic bar sequence with the
same geometry and replayed through the Python reference (`tests/test_video_examples.py`); those tests are the executable
part of this phase.

Legend: ✓ the spec reproduces it · ✗ the spec differs · ? not determinable from the video.

| Check | T-01 buy idea | T-02 sell (taken) | T-03 sell (loss) | T-04 sell (live) | T-05 sell (avoided) | T-06 buy (live) |
|---|---|---|---|---|---|---|
| Candle used by the author | ? ("the candle") | **M15** | **M15** | **M15** | ? | **H1** |
| Context tradable (CTX-4) | ✓ bullish TR | ✓ "little range" | ✓ range | ✓ bearish TR | ? | ✓ bearish TR |
| Extension exists (EXT-2/3) | ? duration | ✓ under the M15 preset; ✗ under H1 (a spike inside one 15-min box) | ✓ M15 | ✓ M15; ? H1 | ✓ | ✓ H1 (drop spans most of the hourly box before the 2nd half) |
| Location (EXT-4, HALF) | ✓ "into 50% of the previous move" | ✓ "high of this range" | ✓ "upper half" | ✓ "50% of the previous bearish move" | ✓ | ✓ "lower half of this bearish TR" |
| Shift timing (SHF-3) | ? | ✓ "halfway point of this candle" | ✓ | ✓ | — | ✓ "second half of the hour" |
| Type-3 shift (SHF-2) | ✓ "a bit of a shift" | ✓ "1-minute break of a low" | ✓ | ✓ "we'd broken this low" | — | ✓ "take out this low into taking out this high" |
| COR-1 not same direction | ✓ | ✓ DXY drove bearish | **✗ → reject** (DXY "pushing bullish") | ✓ DXY drove bearish | **✗ → reject** | ✓ DXY drove bullish |
| COR-2 DXY opposite half | ✓ | ✓ "below the lower half" | ✗ | ✓ "lower half of this previous bullish move" | ✗ ("at the highs") | ? (plausible) |
| COR-3 DXY opposite shift by signal time | ✓ "had a bit of a shift" | ? ("DXY's doing the opposite") | — | ✓ "come into the low … nice reaction" (≈) | — | ✓ explicit DXY bearish type-3 |
| Algorithm decision (default H1) | ? | **no trade** (H1 drive too short) | no trade ✓ | ? (depends on the hour) | no trade ✓ | **trade** ✓ |
| Algorithm decision (M15 preset) | ? | **trade** ✓ | no trade ✓ | **trade** ✓ | no trade ✓ | ? |
| Entry vs author | — | ✓ BREAK = "on the break" | — | ✓ BREAK | — | ✗ BREAK is earlier than the author's "after a bit of a pullback"; ✓ PULLBACK_50 |
| Stop vs author | — | ✓ above the high | — | ✓ above the high | — | ✓ below the low |
| Target vs author | — | ✓ 50% | — | **✗** author exited at "previous lows" (≈1.7R, discretionary); spec targets 50% of the drive (closer) | — | ✓ "one-to-one into 50%" |
| Author's outcome | — | win | loss | win | (would have lost) | win |

## Findings
1. **Both rejections are reproduced.** The two counter-examples (T-03 loss, T-05 avoided fake-out) are rejected by COR-1
   (and COR-2), exactly for the author's reason. This is the core claim of the video and the spec captures it.
2. **The candle timeframe matters (A-07).** The slide and T-06 use the **hourly** candle, but T-02, T-03 and T-04 use
   **15-minute** candle behavior. With the H1 default, T-02 would not trade and T-04 is uncertain. The specification was
   therefore extended (before any backtest): the engine runs *candle trackers* per timeframe, and `CandleMode` can be
   `H1`, `M15` or `H1_AND_M15` (one position at a time across both). H1 remains the default because it is the only
   timeframe with author-given numbers; the M15 numbers (≥ 5-min drive, shift at minute 6–13) are a proportional
   extrapolation and are labelled experimental. **Recommendation: test `H1_AND_M15`, which is the closest to what the
   video demonstrates.**
3. **Entry (A-01).** BREAK matches T-02 and T-04; PULLBACK_50 matches T-06. Neither alone matches all three. Both are kept
   as pre-declared variants; no rule was added to pick between them per trade.
4. **Target (A-12).** Spec = author in T-02 and T-06. The Monday target is discretionary and is not reproduced; this makes
   the spec's average reward per trade *smaller* than the author's on such trades.
5. **What could not be checked:** exact 18-minute durations, exact minutes of the shifts, ρ̃ of the MTF context, and the
   exact DXY shift timing in T-02/T-04. These need the real prices; see the note at the end of the trade database.

No filter was added to make an example pass. The only specification change caused by this replay is (2), which *adds* the
timeframe the author demonstrated; it does not tighten anything.

## Executable replay
`tests/test_video_examples.py` builds, for each example, a synthetic minute series with the example's geometry (MTF
legs, drive, protected swing, shift minute, DXY path) and asserts the decision in the table above (trade / which INV_*
reason, direction, stop above/below the extreme, target at 50% of the drive, entry on the next bar). Run it with
`python -m pytest -q tests/test_video_examples.py`.
