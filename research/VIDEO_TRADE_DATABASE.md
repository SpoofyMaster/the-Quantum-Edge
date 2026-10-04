# Video trade database

Six chart examples are shown in V. Frames are YouTube storyboard thumbnails (320×180, one every ≈4.96 s, upscaled ×2 in
`screenshots/`). Frame timestamps are ±5 s. **No price, date or clock time is readable at this resolution**; fields that
need them say "not readable". Symbols: the video says gold (XAU/USD) and DXY throughout; the TradingView header is not
readable. Each example ends with its *algorithm equivalent* — the fixture used in `tests/test_video_examples.py`.

Common chart layout seen in frames: TradingView, gold on a 1-minute line/candle chart with **higher-timeframe candle boxes
overlaid** (the author's "candle overlay" indicator), DXY in a lower pane, grey horizontal bands = the author's 50% zones,
red/green rectangles = TradingView position tool (red = risk, green = reward).

---

## T-01 — Illustrative continuation-reversal (gold BUY idea, DXY mirror) · V 02:59–03:20
| Field | Value |
|---|---|
| Frames | `setup_01_context_extension_into_50pct.jpg` (≈03:14), `setup_01_shift_markup.jpg` (≈03:24) |
| Timeframe | M1 chart, candle boxes overlaid (box size not readable; the speech says "the candle") |
| HTF/MTF context | "previous bullish move" (red arrow up in the frame) — gold in a bullish leg / trending range |
| Liquidity / extension | "The candle opened, immediately overextended into 50% of the previous move" (red arrow down into the grey 50% band) |
| Structure | "a little bit of a shift" (circled low then high) |
| Trigger | 1-min shift up after the candle's drive down |
| Entry / Stop / Target | not shown (illustration) |
| DXY | "overall bearish, had the candle open, immediately pushed bullish … came into 50% of the previous move, had a bit of a shift, and then pushed bearish" — the exact mirror |
| Outcome | gold continued up; DXY down |
| Why valid | candle drive into the discount half of the previous move + LTF shift + DXY mirror |
| Algorithm equivalent | BUY: bearish extension inside the candle, extreme ≤ 50% of the last MTF up-leg (EXT-4), bullish type-3 shift (SHF-2); DXY: bullish drive since open into the premium half of its last MTF down-leg, bearish DXY shift (COR-1..3). Fixture `T01`. |

## T-02 — Sell at the high of a small range (taken, win) · V 03:20–04:25
| Field | Value |
|---|---|
| Frames | `setup_02_context_gold_and_dxy.jpg` (≈03:43), `setup_02_gold_drives_up_dxy_drives_down.jpg` (≈03:58), `setup_02_entry_short.jpg` (≈04:18), `setup_02_exit_dxy_mirror.jpg` (≈04:28) |
| Timeframe | gold M1 with **15-minute** candle boxes (04:25 "this next 15-minute candle") |
| Context | "a reversal within this little lower time frame range" |
| Extension | "the new candle open and immediately driven bullish … extend into the high of this range, take out the previous high" (frame: a near-vertical push inside the newest box) |
| Structure / trigger | "coming into around the halfway point of this candle … a little bit of a 1-minute break of a low" |
| Entry | **on the break** of the 1-min low (market) |
| Stop | "above this high" (extension extreme) |
| Target | "50% of this for a bit of a low time frame correction"; position box shows reward ≈ risk |
| DXY | "open here and immediately drive bearish … below the lower half of the range" (frame: DXY pane falls through its range low, green annotation) |
| Outcome | WIN — "corrects back into 50% of this previous move" |
| Why valid | drive into range high + mid-candle 1-min shift + DXY mirror |
| Algorithm equivalent | SELL; bullish extension ≥ the scaled minimum, E in the premium half; shift at mid-candle; COR-1..3 pass; ENT-1 BREAK; SL-1; TP-1. Fixture `T02` (run with the M15 timing preset because the candle is 15-minute). |

## T-03 — Same setup without inversion (taken in the illustration, LOSS) · V 04:25–05:52
| Field | Value |
|---|---|
| Frames | `setup_03_context_second_overextension.jpg` (≈04:48), `setup_03_entry_short.jpg` (≈05:03), `setup_03_dxy_same_direction.jpg` (≈05:08), `setup_03_dxy_markup_not_inverted.jpg` (≈05:28), `setup_03_ideal_inversion_sketch.jpg` (≈05:52) |
| Timeframe | M1, 15-minute candle |
| Extension | "overextending again into the upper half or the high of this range" |
| Structure / trigger | "a bit of a reaction on the 1-minute … a bit of a shift" |
| Entry / Stop / Target | short box at the top (frame), same construction as T-02 |
| DXY | "**DXY has opened and has been pushing bullish** with gold also being in the highs … no inversion" (frame: DXY pane rising inside the candle box) |
| Outcome | **LOSS** — "This trade goes and hits our stop loss" |
| Why invalid | INV_DXY_SAME_DIRECTION |
| Algorithm equivalent | gold side passes, COR-1 fails ⇒ **no trade**. Fixture `T03` (must produce INV_DXY_SAME_DIRECTION). |

## T-04 — Live trade "Monday" (taken, win) · V 05:52–08:00
| Field | Value |
|---|---|
| Frames | `setup_04_live_recording.jpg` (≈06:02, shows "Profit 700.00"), `setup_04_context_mtf_pullback_50pct.jpg` (≈06:22), `setup_04_dxy_bullish_trending_range.jpg` (≈06:52), `setup_04_entry_short.jpg` (≈07:47), `setup_04_ltf_entry_detail.jpg` (≈07:57), `setup_04_exit_gold_vs_dxy.jpg` (≈08:02) |
| Date | "on Monday" (the video was uploaded Tuesday 2026-03-31, so probably Monday 2026-03-30; **not verified**) |
| Timeframe | M1, **15-minute** candle behavior inside an MTF pullback |
| MTF context | gold "overall bearish" (bearish trending range); MTF type-3 shift ("taken out this previous high into then taking out this low"); pullback into 50% of the previous bearish move (grey band in frame) |
| Extension | "waited for the 15-minute candle to open and immediately drove bullish into 50% of this previous move" |
| Structure / trigger | "wait for a shift within the shift … we'd broken this low" |
| Entry | "an entry on the break of this low" |
| Stop | "above the high" |
| Target | "targeted or exited out around these previous lows" — box reward ≈ 1.7 × risk (discretionary, not 50%) |
| DXY | "opened and … immediately driven bearish into the lower half of this previous bullish move … little bullish trending range that we come into on the low"; HTF DXY bullish; "pretty big bullish candle close in our favor" |
| Outcome | WIN; the bearish trend then continued |
| Why valid | premium-half drive + LTF shift + DXY mirror at the same time, plus MTF alignment |
| Algorithm equivalent | SELL with EXT-4 satisfied by the 50% of the last MTF down-leg; COR-1..3; BREAK entry; TP-1 would be **closer** than the author's discretionary target (A-12). Fixture `T04`. |

## T-05 — Gold extension with DXY also rising (not taken) · V 08:00–08:42
| Field | Value |
|---|---|
| Frames | `setup_05_context_gold_extension.jpg` (≈08:16), `setup_05_rejected_dxy_at_highs_same_direction.jpg` (≈08:36), `setup_05_outcome_gold_continues.jpg` (≈08:46) |
| Timeframe | M1 with hourly-sized boxes (not certain) |
| Extension | "this nice extension, this push higher on gold … looking for a bit of a sell" |
| DXY | "**we've actually been pushing bullish** … low volume … we're even at the highs of this little bullish trending range" (frame: DXY channel drawn in green, circled at its top) |
| Outcome | not taken; "It just continues pushing higher" |
| Why invalid | INV_DXY_SAME_DIRECTION (and COR-2 fails: DXY in its own premium half, not discount) |
| Algorithm equivalent | **no trade**. Fixture `T05`. |

## T-06 — Live trade "Wednesday" (taken, win) · V 09:02–10:46
| Field | Value |
|---|---|
| Frames | `setup_06_context_hourly_open_drive_bearish.jpg` (≈09:21), `setup_06_dxy_opposite_drive.jpg` (≈09:36), `setup_06_dxy_bearish_shift_markup.jpg` (≈10:06), `setup_06_gold_ltf_shift_sketch.jpg` (≈10:16), `setup_06_entry_long.jpg` (≈10:26), `setup_06_exit_outcome.jpg` (≈10:40) |
| Date | "Wednesday" (probably 2026-03-25; **not verified**) |
| Timeframe | M1 with the **hourly** candle box |
| MTF context | "bearish trending range" |
| Extension | "the hourly candle open and then immediately drove bearish, overextended into the lower half of this bearish trending range" |
| Timing | "around the second half of the hour" |
| Structure / trigger | "gold take out this low into taking out this high into a bit of a pullback … an entry here on the one-minute" |
| Entry | after "a bit of a pullback" (A-01) |
| Stop | "below this low" |
| Target | "a little one-to-one trade into 50%" (box: reward ≈ risk) |
| DXY | drove up ("a little bit low volume … not exactly what I want … but … opposite"); then a bearish DXY type-3 shift with a pullback into 50% — "a positive indicator" |
| Outcome | WIN, "went a little bit further"; gold then continued down while DXY rose |
| Why valid | H1 drive into the lower half + second-half shift + DXY opposite drive and opposite shift |
| Algorithm equivalent | BUY; H1 timings (extension ≥ 18 min, shift at 22–52); COR-4 relaxes DXY's extension quality; ENT-1 enters on the break, ENT-2 after the pullback. Fixture `T06`. |

---

## Rule slides (not trades)
| Frame | ≈Time | Content (read at 320×180, consistent with speech) |
|---|---|---|
| `rules_01_slide_my_setup_reversal.jpg` | 01:49 | "The reversal setup": identify the MTF range · wait for the hourly candle to open and overextend into the high or low of that range · around the 30-minute mark wait for a LTF shift in the opposite direction · enter on that shift, stop behind the most recent high or low, target 50% of the previous move. Two chart thumbnails show a short box at a spike top and a long box at a spike low. |
| `rules_02_slide_how_correlation_fits.jpg` | 02:09 | "How correlation fits": open DXY and run the exact same checklist · bearish reversal on gold = bullish reversal on DXY · same setup, opposite direction · one question: would I take this trade on DXY right now? · yes = enter, no = wait. |
| `rules_03_slide_entry_model_inversion.jpg` | 02:24 | "Entry Model Inversion": not just DXY "going in the opposite direction in general" but "the actual mirror image of your entry model at the same time"; quote "Would I enter on the correlated pair exactly where it is right now? If the answer is no, the correlation isn't strong enough. You wait." Mountain-lake mirror image. |
| `rules_04_inversion_sketch_gold_vs_dxy.jpg` | 02:44 | gold zig-zag above, mirrored DXY zig-zag below, matching swing points circled |
| `intro_02..04_balance_indicator_*.jpg` | 00:45–01:24 | the "XAUUSD Balance" gauge: gold strength vs DXY strength, states Neutral / Leaning Bull / Bullish / Bearish (optional per V 09:02) |
| `intro_01_author_journal_dashboard.jpg` | 00:05 | author's journal: net P&L $1,541,580.36, win 78.19%, profit factor 7.59 (author claim) |

## What the examples can and cannot be used for
- They **can** pin down the *sequence* and the *qualitative* geometry (which side of which level, which direction DXY went,
  where the stop and target sit relative to the drive). Those are encoded as synthetic fixtures in
  `tests/test_video_examples.py` and replayed through the reference implementation.
- They **cannot** be replayed on real prices: dates are only "Monday"/"Wednesday" and prices are unreadable. The likely
  dates (late March 2026) also lie inside this project's **locked final-test period** (≥ 2025-07-01), which may not be
  read before a strategy freeze is journaled. If you want a real-price replay of T-04 and T-06, send the exact dates and
  times (or a higher-resolution copy of the video) and record the freeze first.
