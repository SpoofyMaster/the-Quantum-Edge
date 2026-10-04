# VideoStrategyEA — gold reversal with DXY entry-model inversion

MQL5 Expert Advisor reconstructing the method of *"I Made $1.4M Trading Gold, Here's What Actually Works"* (tomtrades,
<https://www.youtube.com/watch?v=xSVlVpXLuV0>). Specification: [`research/STRATEGY_RULEBOOK.md`](../../research/STRATEGY_RULEBOOK.md).
Python reference (unit-tested, same functions and reason codes): [`qe/video_strategy/`](../../qe/video_strategy/).

> **Status: NOT YET COMPILED.** No MetaEditor was available where it was written. A mechanical check passed
> (balanced brackets, includes resolve, no undefined function names), and every definition is mirrored in the tested
> Python reference. Compile it and send back the error/warning list (see `reports/COMPILATION_REPORT.md`).
> **Safety:** it trades only in the Strategy Tester or on a **demo** account. On a real account it logs signals
> ("PAPER") and sends no orders. No input changes that. Live trading needs a separate, explicit approval.

## Install
1. Copy the whole `VideoStrategyEA` folder (the `.mq5` file **and** `include/`) to `MQL5/Experts/`.
2. Open `VideoStrategyEA.mq5` in MetaEditor → Compile (F7).
3. Attach to an **XAUUSD M1** chart (any chart timeframe works; the EA reads M1 internally).
4. DXY: if your broker lists a dollar-index symbol, enter it in `InpDxySymbol`. Otherwise the EA builds a synthetic ICE
   DXY from EURUSD, USDJPY, GBPUSD, USDCAD, USDSEK and USDCHF; all six must exist in Market Watch (set `InpSymbolSuffix`
   if your broker uses suffixes). IC Markets: check whether a DXY/USDX CFD is listed (UNVERIFIED).

## Strategy Tester settings (replication test, Phase 17)
- Symbol XAUUSD, period M1, model **"Every tick based on real ticks"** (needs the broker's tick history).
- Deposit 100,000 USD, leverage as on your account, commission as charged by your account type.
- Run the defaults first (`CandleMode = H1`, `EntryMode = BREAK`, `DxyMode = FULL`). Then, without changing anything
  else, the pre-declared variants: `EntryMode = PULLBACK_50`, `CandleMode = M15`, `CandleMode = H1_AND_M15`. Do not
  optimise.
- Visual mode: the chart shows the candle box, the MTF zig-zag with its condition, the location levels, the extension
  leg, the protected swing with the shift arrow, entry/SL/TP and red invalidation labels; the panel shows the state of
  each candle tracker, the DXY status and the spread.

## Inputs (groups)
| Group | Inputs | Notes |
|---|---|---|
| GENERAL | `InpMagic`, `InpComment` | |
| RISK | `InpRiskPercent` 0.20, `InpMaxDailyLossPct` 1.00, `InpMaxTradesPerDay` 0, `InpCommissionLotSide` 3.50 | project hard limits; risk includes commission |
| SESSION | `InpSessionPreset`, `InpServerTime` (NY+7 for IC Markets), `InpFixedUtcOffsetH` | DST handled |
| EXECUTION | `InpMaxSpreadPoints` (0 = off), `InpSlippagePoints`, `InpSizingSlipTicks`, `InpMaxOrderErrors` | safety layer, separate from the strategy |
| STRATEGY | candle mode, H1/M15 timings, extension pullback, MTF lookback, zig-zag ATR multiple, ratio thresholds, location mode, pivot strength, break confirmation, entry mode, target mode, stop buffer, time stop | defaults = the video profile |
| CORRELATION | `InpDxyMode` FULL, `InpDxySource` AUTO, `InpDxySymbol`, `InpSymbolSuffix` | `OFF` is a research ablation |
| RESEARCH OPTIONS | previous-candle break, min extension ATR, min break ATR | all off = video |
| VISUALIZATION | structure, levels, entries, panel, log level, CSV | |

## Logs (for verification)
- Journal: `[SETUP #123 M60] 2024.03.06 02:00 candle open; MTF condition=TRENDING_RANGE ...`, the shift with the DXY
  gate result, the order, the close, or `REJECTED reason=INV_...`.
- `Common/Files/VSEA_events_<symbol>_<magic>.csv`: one row per in-session setup with its reason code.
- `Common/Files/VSEA_trades_<symbol>_<magic>.csv`: one row per closed trade (R multiple, exit reason, session).
- Phase-23 report from the trades CSV: `python -m qe.video_strategy.report VSEA_trades_XAUUSD_26100401.csv`.
- Parity: run the Python reference on the same period/data and compare signal times and reason codes
  (`qe.video_strategy.engine.run(...).setups`). Expected differences: broker spreads and ticks vs. modelled spreads;
  PULLBACK_50 fills (the EA fills intrabar, the reference is conservative when a bar touches both limit and target).

## Module map
| File | Rules |
|---|---|
| `include/SessionManager.mqh` | MKT-5/6/7, MGT-3 (server→UTC, US/UK DST, trading candles, rollover) |
| `include/MarketData.mqh` | closed M1 series, pivots (SHF-1), ATR, broker/synthetic DXY (COR-5) |
| `include/MarketStructure.mqh` | extension tracker (EXT-1..3), type-3 shift (SHF-2), MTF context (CTX-1..6), location (EXT-4) |
| `include/EntryEngine.mqh` | candle state machine (section M), SHF-3..5, DXY gate (COR-1..4) |
| `include/RiskManager.mqh` | RSK-1..4 |
| `include/TradeManager.mqh` | ENT-1/2, SL-1, TP-1 orders; stops/freeze/margin checks; SAF-4 log-only on real accounts |
| `include/DebugLogger.mqh`, `include/Visualization.mqh` | logs and chart objects |
