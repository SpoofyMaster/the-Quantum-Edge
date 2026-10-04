# Ambiguity register

Each item: what is unclear → evidence searched (V = target video, S = same author, see
[`supplementary_sources.md`](supplementary_sources.md)) → interpretation implemented → confidence → how to change it.
Nothing below is resolved by "what would backtest better". Defaults follow V first, then the author's own definitions.

Severity: **CRITICAL** (changes which trades exist) · **IMPORTANT** (changes prices/timing of the same trades) ·
**MINOR** (cosmetic or rare).

| ID | Severity | Topic | Default implemented | Confidence | Input / parameter |
|---|---|---|---|---|---|
| A-01 | CRITICAL | Entry on the break vs. on a 50% pullback | Market entry at the next M1 open after the break bar closes | MEDIUM | `EntryMode` = BREAK / PULLBACK_50 |
| A-02 | CRITICAL | What "break" means: candle close vs. wick | M1 **close** beyond the protected level | MEDIUM | `BreakConfirm` = CLOSE / WICK |
| A-03 | CRITICAL | Pivot (swing) definition on M1 | fractal pivot, 2 bars each side, known only after the 2 right bars close | LOW–MEDIUM | `PivotStrength` (1–5) |
| A-04 | CRITICAL | How to measure "middle-timeframe range vs trend" | median pullback ratio of M5 zig-zag legs over the last 300 min; < 0.50 = trend (no trade) | MEDIUM (thresholds) / LOW (zig-zag size) | `MtfLookbackMin`, `ZigZagAtrMult`, `TrendMaxRatio` |
| A-05 | CRITICAL | What counts as an "overextension" | ≥ 18 min from origin to extreme inside the candle, no internal pullback ≥ 50% of the final extension | MEDIUM | `MinExtMinutes`, `MaxExtPullback` |
| A-06 | IMPORTANT | Where the extension must reach ("high/low of the range", "upper/lower half") | extreme beyond the 50% level of the most recent MTF leg in the opposite direction | MEDIUM | `LocationMode` = HALF / CONDITION_AWARE, `MinLocationRetrace` |
| A-07 | CRITICAL | Hourly vs. 15-minute candle | **H1** (slide, Wednesday trade, S1, S2, S4); M15 and H1_AND_M15 available (V's T-02..T-04 use M15) | MEDIUM–HIGH | `CandleMode` |
| A-08 | IMPORTANT | Shift timing window | shift confirmed at minute **22–52** of the H1 candle | MEDIUM–HIGH | `ShiftStartMin`, `ShiftEndMin` |
| A-09 | CRITICAL | How strict the DXY "inversion" must be | FULL: DXY moved opposite since the candle open **and** reached its opposite half **and** printed the opposite type-3 shift no later than gold's signal bar | MEDIUM | `DxyMode` = FULL / MIRROR_DIRECTION / OFF |
| A-10 | IMPORTANT | DXY data source in MT5 | broker DXY symbol if it exists; otherwise a synthetic ICE-formula DXY from 6 FX pairs (close-only) | MEDIUM | `DxySource`, `DxySymbol` |
| A-11 | IMPORTANT | Stop buffer ("a bit of breathing room") | extreme + spread (sells) + 0.10 × ATR(M1,14) | LOW | `StopBufferAtr`, `StopBufferPoints` |
| A-12 | IMPORTANT | Target: 50% of extension vs. previous lows vs. 1:1 | 50% of the extension (origin → extreme, wicks included) | HIGH (rule) / MEDIUM (exception) | `TargetMode` = EXT50 / FIXED_R |
| A-13 | IMPORTANT | Trading hours | candles opening from Tokyo 10:00 (2nd hour of Asia) to London 11:00 (4th hour of London); no New York | MEDIUM | `SessionPreset` = ASIA2_TO_LONDON4 / STRICT / ALL |
| A-14 | MINOR | Trade management | none (no break-even, partials or trailing); project hard limit 120 min | HIGH | `MaxHoldMinutes` |
| A-15 | IMPORTANT | "High volume" extension and "clear" break | not measured by default (tick volume is not comparable across data sources) | LOW | `MinExtAtrMult`, `MinBreakAtr` (0 = off) |
| A-16 | IMPORTANT | AOI levels (H1 candle-closure flips) | **not required** (not in V; author's wider checklist only) | HIGH that V omits them | `RequireAOI` (off) |
| A-17 | IMPORTANT | "Shift within the shift" (seconds-chart refinement) | not implemented on sub-minute bars; PULLBACK_50 covers the 50% part | HIGH that M1 cannot reproduce it | — |
| A-18 | MINOR | Gold "own strength" (balance indicator / gold spread chart) | not used (V 09:02: "you also don't have to use an indicator") | HIGH | — |
| A-19 | MINOR | News | no filter in V; none implemented (no licensed historical calendar, BACKLOG R-5) | HIGH that V is silent | — |
| A-20 | MINOR | Multiple setups per candle / per day | at most one trade per candle; no daily trade cap by default | MEDIUM | `MaxTradesPerDay` (0 = off) |
| A-21 | MINOR | Previous-candle high/low must be taken out (S1 step 1–2) | not required (V's three detailed trades never mention it) | MEDIUM | `RequirePrevCandleBreak` (off) |

---

## A-01 — Entry on the break or on a 50% pullback (CRITICAL)
**Evidence.** V 01:36 slide: "Enter on that shift". V 04:04: "look for a break of this low, put my stop above this high".
V 07:37 (live): "look for an entry on the break of this low". V 10:06 (live): "take out this low into taking out this high
**into a bit of a pullback**. So, I had an entry here". S1 02:50, S3 06:15, S4 13:40: enter on the pullback to 50% of the
breaking move; "if it doesn't pull back, you miss the trade". S5 09:48: on a very small shift "enter at the breakout".
**Reading.** V's own words for the 1-minute trigger are "on the break" twice and "after a bit of a pullback" once. The
author's longer material prefers the 50% pullback of the 1-minute breaking move, and enters on the break only when the shift
is tiny (which is what a 1-minute shift *inside* a larger pullback is, as in the Monday trade).
**Implemented.** Default `BREAK` (V's literal rule). `PULLBACK_50` implements S1/S4 exactly (limit at 50% of the breaking
leg, re-anchored when the leg extends, cancelled if the target trades first, if the extreme is exceeded, or when the candle
ends). Both are reported in backtests as separate, pre-declared variants.
**Confidence MEDIUM. This is the most consequential open question — please confirm which one you want as the default.**

## A-02 — Close vs. wick for "break" (CRITICAL)
**Evidence.** V never says. S2/S4 say "break"/"take out"; S2 282:17 wants a "clear take out", not "barely". X1 (third
party) says "a candle that closes past the wick high or low". `BREAK` entry is only well defined if the break is known at a
bar close.
**Implemented.** `CLOSE`: the M1 close must be beyond the protected pivot. `WICK` option: the trade is entered as a stop
order at the level (EA) / at the level with slippage (Python). Confidence MEDIUM.

## A-03 — Pivot definition (CRITICAL)
**Evidence.** The author reads 1-minute swings by eye, and suggests the line chart when unsure (S1 06:19). No bar count is
ever given. **Implemented.** Swing high at bar k if `High[k] > High[k-i]` and `High[k] >= High[k+i]` for i = 1..N, with
N = `PivotStrength` = 2; it becomes *known* only after bar k+N closes (no look-ahead). Confidence LOW–MEDIUM. Changing N
changes which "previous low" is broken; the video-example fixtures in `tests/` are run with N = 1, 2 and 3.

## A-04 — Measuring the middle-timeframe condition (CRITICAL)
**Evidence.** S6 01:22 / S3 01:22 / S4 02:46: MTF = past 4–5 hours. S2 218:28: "Condition is defined by the size of the
pullbacks." Thresholds: trend < 50%, trending range ≈ 50–75%, range ≈ 75–100%+ (S2 220:15); S4 03:07 uses > 50% for range.
V: "identify a middle time frame range" (01:36) and "if it's … unclear, I just don't take a trade" (02:40).
**Implemented.** At each candle open: M5 bars of the previous 300 minutes → zig-zag with reversal threshold
`ZigZagAtrMult` × ATR(M5,14) (default 2.0) → leg sizes L₁…Lₙ → ratios rᵢ = Lᵢ/Lᵢ₋₁ for completed legs → median r̃.
r̃ < 0.50 → TREND (no trade); 0.50–0.75 → TRENDING_RANGE; ≥ 0.75 → RANGE. Fewer than 2 ratios, or less than 80% of the
window's minutes present (weekend open, holidays) → UNDEFINED (no trade). Direction (info): HH+HL bullish, LH+LL bearish.
Confidence: thresholds MEDIUM (author's numbers), zig-zag size LOW (our choice, fixed a priori, not tuned).

## A-05 — Overextension (CRITICAL)
**Evidence.** V 01:36 "overextend for around 20 minutes". S1: "around 20 minutes … I wouldn't go any lower than 18",
"without a pullback at all", "without a pullback to 50%". S4 04:50: "at least 15 to 30 minutes … push in one direction".
S1 05:57: a late extension is fine ("delayed entry").
**Implemented.** For a bullish extension (sell setup): extreme = highest high since the candle open (first bar that set it);
origin = lowest low between the candle open and the extreme bar. Valid when (extreme bar − origin bar + 1) ≥ `MinExtMinutes`
= 18, and max over bars k in [origin, extreme] of (running max high − Low[k]) / (extreme − origin) < `MaxExtPullback` = 0.50.
Mirror for bearish. Confidence MEDIUM (the duration is the author's number; the pullback metric is our formalisation of
"without a pullback to 50%").

## A-06 — Where the extension must reach (IMPORTANT)
**Evidence.** V 01:36 "into the high or low of that range"; V 02:59/03:20 "into 50% of the previous move"; V 03:42 "high of
this range, take out the previous high"; V 04:47/05:08 "upper half … of this range"; V 06:15 "pullback into 50% of the
previous bearish move"; V 09:21 "lower half of this bearish trending range". S3 02:04: sells in the upper half of the
previous bearish move, buys in the lower half of the previous bullish move. S2 229:06: range → 75–100%.
**Implemented.** `HALF` (default): a sell needs the extension high ≥ the 50% level of the most recent MTF **down**-leg
(premium half of the previous bearish move); a buy needs the extension low ≤ the 50% level of the most recent MTF **up**-leg.
This single rule is consistent with the descriptions of all five located examples in V (see VIDEO_REPLICATION_TEST.md; qualitative, because prices are not readable). `CONDITION_AWARE` (author's
extended rule): 0.50 in a trending range in the trend's direction, 1.00 (beyond the leg's origin) against a trending range,
0.75 in a range. Confidence MEDIUM.

## A-07 — H1 or M15 candle (CRITICAL)
**Evidence.** Slide: "hourly candle". Wednesday trade: "hourly candle". S1, S2, S4: hourly. But V examples 2–3 (04:25
"this next 15-minute candle", 05:29 "halfway point of the 15-minute candle") and the Monday trade (06:15 "15-minute candle
behavior") use 15-minute candles. S2 263:34 also uses "1-minute type three shift with 15-minute candle behavior".
**Implemented.** H1 is the default (the documented core model). `CandleMode = M15` (extension ≥ 5 min, shift at minutes
6–13) and `H1_AND_M15` (both trackers, one position at a time) are available; the scaled M15 numbers are our
extrapolation, not the author's. The Phase-14 replay shows that H1 alone reproduces only one of the three taken
demonstrations, so `H1_AND_M15` is the variant closest to what V *shows*. Confidence MEDIUM–HIGH for H1 as the core;
LOW for the M15 numbers. **Please confirm which mode you want as the default.**

## A-08 — Shift timing (IMPORTANT)
**Evidence.** V: "around the 30-minute mark" (01:36), "halfway point of this candle" (04:04), "second half of the hour"
(09:21). S2 104:47: "type three shift 22 to 52 minutes into the hour". S1 02:07: 30–45. S5 07:20: 15–30.
**Implemented.** The bar that confirms the shift must *close* between minute 22 and minute 52 of the candle (inclusive).
Confidence MEDIUM–HIGH (explicit author numbers that contain V's "around 30").

## A-09 — DXY inversion strictness (CRITICAL)
**Evidence.** Hard: V 02:40 "If the answer is no or it's unclear, I just don't take a trade"; V 05:52 "If it's opened and
gone in the same direction, I'm not looking to take a trade"; slide "Yes = enter. No = wait". Preferences: V 02:59 "ideally
I'd want to see the same thing on DXY" (the shift); V 09:21 accepted a "low volume … not exactly what I want" DXY push.
Positive: V 09:42 a DXY type-3 shift in the opposite direction is "a positive indicator".
**Implemented.** `FULL` (default) = COR-1 (not the same direction) + COR-2 (DXY extreme in its opposite half) + COR-3 (DXY
opposite type-3 shift confirmed at or before gold's signal bar, after the DXY extreme, inside the same candle). DXY's own
extension is **not** required to last 18 minutes (the Wednesday trade). `MIRROR_DIRECTION` = COR-1 + COR-2 only. `OFF` is
an ablation for research, never the strategy. Confidence MEDIUM.

## A-10 — DXY in MetaTrader 5 (IMPORTANT)
**Evidence.** V uses TradingView's DXY. IC Markets MT5 may not list a dollar-index CFD (UNVERIFIED; check Market Watch).
**Implemented.** `DxySource = AUTO`: use `DxySymbol` if it exists in Market Watch, else synthetic DXY =
50.14348112 × EURUSD^-0.576 × USDJPY^0.136 × GBPUSD^-0.119 × USDCAD^0.091 × USDSEK^0.042 × USDCHF^0.036
(ICE formula) from M1 **closes** of the six pairs; the synthetic bar's high = low = close ("line chart" structure, which
the author himself recommends for reading shifts, S1 06:19). Confidence MEDIUM: correlation of the synthetic with ICE DXY is
very high, but intrabar extremes are lost.

## A-11 — Stop buffer (IMPORTANT)
**Evidence.** V: "stop above this high" (04:04, 07:37), "stop below this low" (10:27). S5 07:00: "a bit of breathing room …
I always account for spread". No number anywhere.
**Implemented.** Sell: SL = extension high + current spread + buffer; buy: SL = extension low − buffer;
buffer = max(`StopBufferPoints`·point, `StopBufferAtr` × ATR(M1,14)) with defaults 0 points and 0.10. Confidence LOW.

## A-12 — Target (IMPORTANT)
**Evidence.** 50% of the overextension: V 01:36, 02:59, 04:04, 10:27; S1 03:11 ("from the swing low to the swing high"),
S1 06:41 ("including the wicks"); S4 09:43 ("if it's a really high volume overextension … I'll go the whole move").
Exceptions: Monday trade "exited around these previous lows" (07:37, discretionary); Wednesday "a little one-to-one trade into
50%" (the two coincided).
**Implemented.** `EXT50`: TP = origin + 0.5 × (extreme − origin), measured on the bid chart; for sells the order TP is
raised by the spread at entry so it triggers when the bid touches the level. `FIXED_R` (option). Discretionary exits are not
reproducible and are not implemented. Confidence HIGH for the rule.

## A-13 — Trading hours (IMPORTANT)
**Evidence.** V is silent. S1 00:21: second hour of Asia → 3rd–4th hour of London. S4 02:26: second hour of Asia, also the
London open. S2: never New York. S8: avoid Sydney / rollover. **Implemented.** `ASIA2_TO_LONDON4`: the trade candle must open
between 10:00 Asia/Tokyo and 11:00 Europe/London inclusive (DST-correct; ≈01:00–10:00 UTC in summer, 01:00–11:00 UTC in
winter). `STRICT`: only the 10:00 Tokyo candle and the 08:00 London candle. `ALL`: any hour (research). Confidence MEDIUM.

## A-14 — Management (MINOR)
V and S-sources show no break-even, partial or trailing. S5: trades last 5–10 minutes. The project's hard rule closes any
position after 120 minutes and before the 17:00 New York rollover.

## A-15 — "High volume" (IMPORTANT)
"High volume" in the author's language means a fast, one-directional move. HistData has no volume and broker tick volume is
not comparable across feeds, so it is **not** used. Optional size floors `MinExtAtrMult` and `MinBreakAtr` exist and default
to 0 (off). Confidence LOW.

## A-16 — AOI levels (IMPORTANT)
S2/S3/S4 refine entries with zones around H1 candle-closure flips. V never mentions them. Default off; `RequireAOI` turns on
"extension extreme within `AoiZoneAtr` × ATR of an H1 open/close flip level from the last 24 h".

## A-17 — Shift within the shift (IMPORTANT)
V 07:15 mentions it; S5 describes it with a 5-second chart. Standard M1 history cannot reproduce sub-minute structure.
The M1 part (wait for the 50% pullback of the 1-minute breaking move) is `EntryMode = PULLBACK_50`. A tick-built 10-second
refinement is listed as future work.

## A-18 … A-21
See the table. A-21: S1 makes "mark the previous hourly high/low" step 1, but none of V's three detailed trades mention it,
so it is an option (`RequirePrevCandleBreak`).

## Contradiction check: transcript vs. visuals
- At 320×180 the frames agree with every spoken description we could check: in example 2 the gold pane rises while the
  DXY pane falls inside the same candle box (`setup_02_gold_drives_up_dxy_drives_down.jpg`); in examples 3 and 5 the DXY pane
  rises with gold (`setup_03_dxy_same_direction.jpg`, `setup_05_rejected_dxy_at_highs_same_direction.jpg`); in the Wednesday
  trade the long position box has reward ≈ risk, matching "a little one-to-one" (`setup_06_entry_long.jpg`).
- One visual detail is *not* in the speech: the Monday short box shows reward ≈ 1.7× risk with the target near the previous
  lows (`setup_04_entry_short.jpg`), confirming that this target was discretionary (A-12).
