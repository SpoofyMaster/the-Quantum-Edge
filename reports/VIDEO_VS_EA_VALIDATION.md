# Video vs. EA validation (traceability)

Each key rule of the video → where it is said/shown → how the bot implements it → code (EA module · Python reference) →
confidence. Timestamps are from the video's captions (`research/video_transcript_analysis.md`); S-IDs are the author's
other videos used only to define his terms (`research/supplementary_sources.md`). "Tested" means a CI-executed test of the
Python reference; the MQL5 mirror is **not compiled yet** (`reports/COMPILATION_REPORT.md`).

| # | Video rule | Video timestamp | Bot implementation | Code (EA · Python) | Test | Confidence |
|---|---|---|---|---|---|---|
| 1 | Trade gold (XAU/USD or GC); price is gold *against the dollar* | 00:38–00:57 | Runs on XAUUSD; warns on other symbols | `VideoStrategyEA.mq5::OnInit` | — | HIGH |
| 2 | Big moves need a strength mismatch between gold and the dollar; avoid equal strength | 00:57–01:36 | Expressed through the DXY gate (rows 13–16); the optional strength gauge is not used (V 09:02) | `EntryEngine.mqh::Gate` · `engine.py::CandleTracker.gate` | `test_t03_is_rejected_only_because_of_dxy` | MEDIUM |
| 3 | "I am a reversal trader" — trade the correction of the candle's overextension | 01:36 | Only reversal setups: SELL after a bullish extension, BUY after a bearish one | `EntryEngine.mqh::OnBar` · `engine.py::check_signals` | `test_video_example_decision[*]` | HIGH |
| 4 | Identify a middle-timeframe **range** (not a trend) | 01:36, slide 01:49 | 300-min M5 zig-zag; median pullback ratio < 0.50 → TREND → no trade (S2 218:28, S4 03:07) | `MarketStructure.mqh::ComputeMtfContext` · `structure.py::mtf_context` | `test_mtf_condition_classification`, `test_trend_context_is_rejected` | MEDIUM |
| 5 | The **hourly** candle opens and **overextends ~20 minutes** | 01:36, slide 01:49, 09:21 | Extension inside the candle, ≥ 18 min origin→extreme, no internal pullback ≥ 50% (S1 06:19) | `MarketStructure.mqh::CExtTracker`, `EntryEngine.mqh::ExtValid` · `engine.py::ExtTracker`, `ext_valid` | `test_extension_tracker_matches_bruteforce` | MEDIUM–HIGH |
| 6 | 15-minute candle behavior is also demonstrated | 04:25, 05:29, 06:15 | `CandleMode` M15 / H1_AND_M15 (experimental timings 5 / 6–13) | `VideoStrategyEA.mq5::OnInit` (trackers) · `params.py::m15_preset` | `test_t02_needs_the_m15_candle` | MEDIUM (H1) / LOW (M15 numbers) |
| 7 | Overextend **into the high or low** / **upper or lower half** of the range / **into 50% of the previous move** | 01:36, 02:59, 03:42, 04:47, 06:15, 09:21 | Extreme beyond the 50% level of the most recent opposite MTF leg | `MarketStructure.mqh::LocationLevel` · `structure.py::location_level` | `test_location_levels_half_and_condition_aware` | MEDIUM |
| 8 | Around the **30-minute mark / halfway point** of the candle | 01:36, 04:04, 05:29, 09:21 | Shift bar must close at minute 22–52 (S2 104:47) | `EntryEngine.mqh::OnBar` (minute window) · `engine.py::check_signals` | video fixtures | MEDIUM–HIGH |
| 9 | **Market structure shift** on 1-minute ("type three shift": take out a high, then a low) | 01:36, 02:00, 04:04, 07:37, 10:06 | Close beyond the protected M1 pivot low/high that sits between origin and extreme, after a prior pivot was taken out (S4 05:32) | `MarketStructure.mqh::FindShift` · `engine.py::find_shift` | `test_pivots_are_causal…`, video fixtures with N = 1, 2, 3 | HIGH (concept) / MEDIUM (close vs wick) |
| 10 | **Enter on that shift** ("look for a break of this low") | slide 01:49, 04:04, 07:37 | `EntryMode = BREAK`: market order at the next bar's open | `VideoStrategyEA.mq5::HandleSignal` · `engine.py::_execute` | `test_video_example_decision` (entry 60 s after the signal) | MEDIUM |
| 11 | "… into a bit of a pullback. So I had an entry here" | 10:06 | `EntryMode = PULLBACK_50`: limit at 50% of the breaking leg, re-anchored, cancelled if the target trades first or the candle ends (S1 02:50, S4 13:40) | `VideoStrategyEA.mq5::HandleSignal`, `ManagePending` · `engine.py::_execute` | `test_t06_pullback_entry_is_better_than_break` | MEDIUM |
| 12 | **Stop above the high / below the low** | slide 01:49, 04:04, 07:37, 10:27 | SL = extension extreme ± (spread for sells) ± buffer 0.10·ATR(M1) | `VideoStrategyEA.mq5::HandleSignal` · `engine.py::_execute` | video fixtures (SL beyond extreme) | HIGH (place) / LOW (buffer) |
| 13 | **Target 50% of the overextension** | 01:36, 02:59, 04:04, 10:27 | TP = origin + 0.5·(extreme − origin), wicks included; sell TP raised by the spread | `VideoStrategyEA.mq5::HandleSignal` · `engine.py::_execute` | video fixtures (TP = 50% of the drive) | HIGH |
| 14 | Run the **same checklist on DXY**, opposite direction ("inversion of my entry model") | 02:00, slide 02:09 | DXY must show a mirrored setup at the same time (rows 15–17) | `EntryEngine.mqh::Gate` · `engine.py::CandleTracker.gate` | video fixtures T-02…T-06 | HIGH |
| 15 | **"If it's opened and gone in the same direction, I'm not looking to take a trade"** | 05:52 (also 05:08, 08:22) | COR-1: reject if DXY's dominant move since the candle open is in gold's direction, or DXY is above/below its open at gold's extreme | `EntryEngine.mqh::Gate` · `engine.py::gate` | T-03 and T-05 must give `INV_DXY_SAME_DIRECTION` | HIGH |
| 16 | DXY must overextend **into the opposite half** of its range | 02:40, 03:42, 05:29, 06:35 | COR-2: DXY extreme beyond 50% of DXY's own previous opposite MTF leg | `EntryEngine.mqh::Gate` · `engine.py::gate` | video fixtures | MEDIUM–HIGH |
| 17 | "Would I enter exactly where this [DXY] pair currently is **right now**?" / DXY type-3 shift is "a positive indicator" | 02:21–02:40, 02:59, 09:42 | COR-3 (`FULL`): DXY opposite type-3 shift after DXY's extreme and no later than gold's signal bar | `EntryEngine.mqh::OnBar` (DXY replay) + `Gate` · `engine.py::update_bar` + `gate` | `test_t06_dxy_shift_is_required_in_full_mode` | MEDIUM |
| 18 | A "low volume" DXY push in the opposite direction is still acceptable | 09:21 | COR-4: no 18-min/no-pullback test on DXY | `EntryEngine.mqh::Gate` · `engine.py::gate` | T-06 fixture (DXY pullback > 50%) | MEDIUM |
| 19 | "If the answer is no or it's **unclear**, I just don't take a trade" | 02:40 | Undefined MTF context (insufficient legs or data) → no trade; missing DXY data → no trade | `ComputeMtfContext`, `Gate` · `mtf_context`, `gate` | `test_mtf_context_undefined_without_enough_history` | MEDIUM |
| 20 | Indicator optional; a plain DXY chart is enough | 09:02 | Broker DXY symbol or synthetic ICE DXY | `MarketData.mqh::CMarketData` · `dxy.py` | `test_synthetic_dxy_formula` | MEDIUM |
| 21 | No break-even, partials or trailing are shown | (absence) | None implemented; exits = TP, SL, 120-min project time stop, rollover | `VideoStrategyEA.mq5::ManagePosition` · `engine.py::run_exit` | `test_run_exit_stop_first_gap_and_time` | HIGH |
| 22 | Trading hours (not stated in V) | — (S1 00:21, S4 02:26, S2 285:14) | Candles opening 10:00 Tokyo … 11:00 London, DST-correct; no New York | `SessionManager.mqh::IsTradingCandle` · `sessions.py::is_trading_candle` | `test_session_window_is_dst_correct` | MEDIUM |
| 23 | No look-ahead / no repainting (brief requirement) | — | Closed bars only; pivots used only after N right bars; the candle is replayed from closed bars each minute | `MarketData.mqh::LoadGold` (shift 1), `FindShift` limits · `engine.py` | `test_no_lookahead_truncation_and_future_scramble` (3 variants) | HIGH |
| 24 | Risk 0.20% incl. costs, 1% daily loss, ≤ 120 min, no martingale (project rules, not video) | — | Sizing via tick value/size + commission; FX-day lockout; time stop | `RiskManager.mqh` · `qe/risk.py` | `test_risk_per_trade_and_one_position` | HIGH |

## Example-by-example (Phase 18/19)
| Example | Author's decision | Bot (default H1) | Bot (H1_AND_M15) | Test |
|---|---|---|---|---|
| T-01 continuation buy idea | (illustration) | buy | buy | `test_video_example_decision[T-01-*]` |
| T-02 sell, small range, M15 | sell, win | **no trade** (drive too short for H1) | sell, win | `[T-02-*]`, `test_t02_needs_the_m15_candle` |
| T-03 sell without inversion | sell, **loss** | rejected `INV_DXY_SAME_DIRECTION` | rejected | `[T-03-*]` |
| T-04 Monday live sell, M15 | sell, win (discretionary target) | depends on the hour (not encoded) | sell, win (closer target) | `[T-04-*]` |
| T-05 sell avoided | no trade | rejected `INV_DXY_SAME_DIRECTION` | rejected | `[T-05-*]` |
| T-06 Wednesday live buy, H1 | buy, win | buy, win | buy, win | `[T-06-*]`, pullback and DXY-shift tests |

The fixtures reproduce the *described geometry*, not the real prices (unreadable at 320×180). What remains unverified:
the EA's behaviour on real MT5 data (needs compilation and a tester run — `docs/BACKLOG.md` U-5/U-6) and a real-price
replay of T-04/T-06 (needs exact dates/times; they also fall in the locked final-test period).
