# BprFvgEA: LuxAlgo FVG / BPR zones + retest setups (MetaTrader 5)

One Expert Advisor that does two things:

1. **Draws** the Fair Value Gaps (FVG) and Balance Price Ranges (BPR) exactly like the LuxAlgo indicator
   ("ICT Concepts [LuxAlgo]", ported in `mql5/Indicators/LuxAlgo_BPR`).
2. **Uses** those zones to detect **buy and sell setups** (sweep, structure shift, retest of the zone) and, in the
   Strategy Tester or on a demo account, to place the orders.

The rules are written in [`research/indicators/BPR_FVG_EA_SPEC.md`](../../research/indicators/BPR_FVG_EA_SPEC.md),
the single source of truth. The zone engine follows
[`research/indicators/LUXALGO_BPR_SPEC.md`](../../research/indicators/LUXALGO_BPR_SPEC.md); the trade idea comes
from the owner's sketch, [`BPR_RETEST_PLAYBOOK.md`](../../research/indicators/BPR_RETEST_PLAYBOOK.md). The Python
reference with the same decisions is `qe/strategies/bpr_fvg.py`.

> **Status: NOT YET COMPILED.** No MetaEditor was available where it was written. The ad-hoc checks run instead are
> listed under [Verification so far](#verification-so-far) (not `VERIFIED`). Compile it and send back the complete
> list of errors and warnings.

## Safety (read first)

- **Tester and demo only.** Orders are sent only in the Strategy Tester and on **demo** accounts. On a **real
  account the EA is log-only**: it draws, detects and logs, and sends no order. There is deliberately no input to
  change this; live trading needs a separate, explicit human approval.
  - The account check **fails closed** and runs again on every tick and before every order, delete, close or stop
    change. Outside the tester the EA trades only when the terminal is connected, the account is known (login > 0)
    and its trade mode is `DEMO`. Until the account is known it is log-only (`WAITING FOR ACCOUNT: LOG-ONLY`);
    contest accounts are log-only as well.
- **One EA instance per account.** The 1.00 % daily budget, the lockout and the trade count are computed per EA
  instance (symbol + magic number). Several instances would each get their own 1.00 %, so run only one.
- **The default rules lost money in the backtest.** The setup rules are hypothesis **H-13**. The pre-registered
  experiment EXP010 (XAUUSD M1, 2020-01 → 2025-06, costs included) **REJECTED** them:
  - defaults: 62 trades, win rate 19 %, **−0.37 R per trade**;
  - every variant (CONFIRM entry, no filters, FVG setups, M5) was also negative.

  See [`reports/EXP010_BPR_FVG_EA_REPORT.md`](../../reports/EXP010_BPR_FVG_EA_REPORT.md). Use the EA to **see** the
  zones and to study setups in the tester or on demo, not to make money. Do not tune the rules on these results: every
  change is a new trial and needs fresh, untouched data.
- **Locked final-test period.** Do not use data from **2025-07-01 onward** (`config/research.toml`,
  `final_test_start`) to choose or tune anything, including demo results from today. Any change of a default is a
  new trial and must be registered in `results/trial_registry.jsonl`.
- **Hard limits in code** (no input can raise them): 0.20 % of equity per position including commission, 1.00 %
  planned daily loss per FX day (17:00 New York) then lockout, one position or pending order per EA instance, every
  position closed at most 120 minutes after entry and before 16:44 New York. No martingale, grid, averaging down or
  size increase after losses: size depends only on equity and stop distance.
- **Broker values are `UNVERIFIED`**: commission 3.50 USD per lot per side, contract size, tick value, stops level and
  the server-time convention (IC Markets = New York + 7 h). Check them against your account before trusting any
  number.

## Licence and attribution

The FVG / BPR / displacement / Fibonacci logic is a port of the Pine v5 script **"ICT Concepts [LuxAlgo]"**,
© LuxAlgo, licensed under **Creative Commons Attribution-NonCommercial-ShareAlike 4.0**
(<https://creativecommons.org/licenses/by-nc-sa/4.0/>). This EA contains that port, so the EA as a whole is
distributed under the same licence: **non-commercial use only, attribution to LuxAlgo, share-alike**. It is not
affiliated with or endorsed by LuxAlgo. The setup rules (sweep, structure shift, entries, stops, targets) are this
project's own. Every source file that contains LuxAlgo logic carries the attribution header.

## Install

1. Copy the **whole** `BprFvgEA` folder (`BprFvgEA.mq5` **and** `include/`) to `MQL5/Experts/` of your terminal
   (File → Open Data Folder).
2. Open `BprFvgEA.mq5` in MetaEditor and compile (F7). The include files are found through the relative path
   `include/...`.
3. Attach it to an **XAUUSD M1** chart (any symbol and timeframe work; the research targets XAUUSD M1). Allow algo
   trading only on a demo account.

| File | Contents |
|---|---|
| `BprFvgEA.mq5` | Inputs, warm-up, new-bar loop, order execution, position management, logs, display calls |
| `include/BfDefines.mqh` | Input enums, reason / event / status codes, parameter and record structures (pure) |
| `include/BfEngine.mqh` | The LuxAlgo FVG / BPR engine, copied from the indicator (pure; LuxAlgo licence) |
| `include/BfDetector.mqh` | The setup detector of spec §4 (pure) |
| `include/BfSession.mqh` | Server time → UTC / New York / London with DST, entry window, FX day, 16:44 flat |
| `include/BfRisk.mqh` | Position sizing and the daily-loss lockout |
| `include/BfTrade.mqh` | Orders through `CTrade`, stops / margin checks, real-account log-only switch |
| `include/BfRender.mqh` | Zones, Fibonacci, displacement markers, trade overlays, panel (LuxAlgo licence) |
| `include/BfLogger.mqh` | Experts-log lines and CSV files |

"Pure" files use no MT5 function at all, so they can be compiled as C++ and checked against the Python reference.

## Inputs

### Display (LuxAlgo look)

| Input | Default | Meaning |
|---|---|---|
| `InpShowZones` | true | Draw the LuxAlgo boxes. |
| `InpShowBPR` | true | Show BPR boxes (FVG boxes hidden). False: show FVG boxes, styled like the indicator with BPR off. The engine always computes BPRs; this changes the display only. |
| `InpShowFVGinBPRmode` | false | Debug: also draw the FVG boxes while BPRs are shown (shows which two gaps made a BPR). |
| `InpVisibleBoxes` | 2 | 1–20. Length of the engine's four arrays. Values ≥ 12 trigger LuxAlgo QUIRK 11 (a warning is logged). |
| `InpLength` | 5 | 3–10. Period of the body average that defines a displacement candle. |
| `InpFvgType` | FVG | FVG or IFVG. **Setups need FVG**: with IFVG the EA only draws, trading is disabled and a warning is logged. |
| `InpShowDisplacement` | false | Arrows on displacement candles (up: green arrow below the bar; down: red arrow above). |
| `InpDisplacementBars` | 300 | Arrows are kept on the last N bars only. |
| `InpFib` | NONE | NONE or BPR: Fibonacci between the last BPR up and the last BPR down (drawn only while BPRs are shown). |
| `InpFibExtend` | false | Extend the eight Fibonacci level lines to the right. |
| `InpLiveBar` | true | Display the forming bar on a throw-away copy, like the indicator. **Decisions never use the forming bar.** |
| `InpBullColor` / `InpBullBreakColor` | C'0,230,118' / C'128,128,0' | Bullish zone colour / break colour. |
| `InpBearColor` / `InpBearBreakColor` | C'255,82,82' / C'255,0,0' | Bearish zone colour / break colour. |
| `InpFillTransp` / `InpBorderTransp` / `InpBreakTransp` | 90 / 65 / 95 | Pine transparencies, emulated by blending with the chart background. |
| `InpShowTradeBoxes` | true | Position-tool overlay for every decided order. |
| `InpShowPanel` | true | Status panel, top left. |

### Setups (hypothesis H-13; defaults fixed before any data was looked at)

| Input | Default | Meaning |
|---|---|---|
| `InpSetupSource` | BPR | Zones that create setups: BPR, FVG or BOTH. |
| `InpDirection` | BOTH | BOTH, LONG_ONLY or SHORT_ONLY. |
| `InpEntryMode` | LIMIT | LIMIT: a limit order just inside the far edge of the zone (R1). CONFIRM: wait for a rejection candle in the zone, then a market order at the next bar's open (R3). |
| `InpEntryOffsetTicks` | 5 | LIMIT: δ, how far inside the edge the limit sits (long: `B + δ·tick + spread`, an ask price). |
| `InpUseSweep` | true | Require a liquidity sweep before the zone. |
| `InpSweepWindow` | 30 | Bars searched for the sweep extreme (up to and including the zone's bar). |
| `InpRangeBars` | 30 | Bars before the sweep that define the range it must break. |
| `InpUseMss` | true | Require a structure shift (a close beyond `M`). |
| `InpMssBars` | 20 | Bars before the sweep that define `M`. |
| `InpRallyBars` | 10 | Bars that define the measured-move origin `O`. |
| `InpExpiryBars` | 60 | A setup (and its pending order) ends after this many bars. |
| `InpStopZoneMult` | 1.2 | Stop distance beyond the far edge, in zone heights. |
| `InpMinRR` | 1.0 | Minimum reward:risk at TP1. |
| `InpMaxCostR` | 0.15 | Maximum round-trip cost (spread + commission + 2 ticks of slippage) as a fraction of the risk. |
| `InpTpMode` | TP1_TP2 | TP1_TP2: close `InpTp1Fraction` at TP1, rest at TP2. TP1_ONLY, TP2_ONLY: one target on the server. **On a netting account TP1_TP2 falls back to TP1_ONLY** (with a warning in the log), because the partial close of `CTrade` works on hedging accounts only. |
| `InpTp1Fraction` | 0.5 | Fraction closed at TP1 (rounded down to the volume step). |
| `InpBreakEven` | true | After TP1, move the stop to entry ± commission (profit side). |
| `InpMaxHoldMin` | 120 | Time stop in minutes. Capped at 120. |

### Session, risk and execution

| Input | Default | Meaning |
|---|---|---|
| `InpServerMode` | NY+7 | How server time maps to UTC: NY+7 (IC Markets, `UNVERIFIED`), EU DST (UTC+2/+3) or a fixed offset. |
| `InpServerOffsetH` | 0 | Fixed-offset mode only: server = UTC + this many hours. |
| `InpUseSession` | true | New orders only from 08:00 Europe/London to 14:45 America/New_York, Monday–Friday; pending orders are cancelled at 14:45 New York. |
| `InpRiskPct` | 0.20 | Risk per position in % of equity, commission included. Capped at 0.20. |
| `InpDailyLossPct` | 1.00 | Planned daily loss in % (FX day from 17:00 New York); reaching it locks the EA out until the next FX day. Capped at 1.00. Per EA instance: run one instance per account. |
| `InpMaxTradesDay` | 0 | Maximum positions per FX day (0 = no limit). A limit filled in several deals counts once. |
| `InpCommissionPerLotSide` | 3.50 | Commission per lot per side in the account currency (`UNVERIFIED`; check your account). |
| `InpSlippageTicks` | 1 | Ticks added to the stop distance for sizing and to the cost check. |
| `InpMaxSpreadPts` | 0 | Skip new orders while the spread is above this many points (0 = off). |
| `InpMagic` | 2610081 | Magic number. Only one EA instance per account is supported (see Safety). |
| `InpDeviationPts` | 30 | Maximum deviation for market orders, in points. The server applies it only on instant / request execution; on market execution (most ECN accounts) it is ignored. Market orders are therefore sized with an entry buffer of max(`InpSlippageTicks` ticks, `InpDeviationPts` points), and any excess risk after the fill is closed. |
| `InpWarmupBars` | 5000 | Closed bars processed at start to rebuild the zones and the state. **No setup created during warm-up is ever traded.** |
| `InpLogCsv` | true | Write the CSV logs to the Common Files folder. |

## How a setup works (long; a short is the mirror image)

Every step uses **closed bars only**. Bar `u` is the bar that just closed.

```
                          X  rally extreme since the sweep  ->  TP1 = X - 2 spreads
                         /\
   M  - - - - - - - - - / - -   highest high of the 20 bars before the sweep: a close above M = structure shift
            /\         /
   T  =====/==\=======/=====    zone created on bar u (BPR, or FVG)        h = T - B
   B  ====/====\=====/======    <- buy limit  P = B + 5 ticks + spread  (ask)
         /      \   /
   R  - / - - - -\-/- - - - -   lowest low of the 30 bars before the sweep
                  V
                  s  sweep: the lowest low of the last 30 bars, below R

   SL  = min(B - 1.2 h,  lower gap's bottom - 2 spreads)            (bid level)
   TP2 = P + (X - O),  O = lowest low of the last 10 bars at creation (measured move)
```

1. **Zone.** The LuxAlgo engine processes bar `u` (Historical mode). A new BPR with `pos = +1` (support) or a new
   bullish FVG becomes a long candidate; a BPR with `pos = −1` or a bearish FVG a short candidate. Order inside one
   bar: BPR from the UP array, BPR from the DN array, bullish FVG, bearish FVG.
2. **Sweep.** `s` = the bar with the lowest low in the last `InpSweepWindow` bars (ties: the latest). That low must
   be below the lowest low of the `InpRangeBars` bars before `s`. Otherwise the candidate ends `DONE(NO_SWEEP)`.
3. **Structure shift.** `M` = the highest high of the `InpMssBars` bars before `s`. The first close above `M` after
   `s` is the MSS (it may already have happened at creation).
4. **Waiting (`ARMED`).** On every new closed bar the setup ends if the zone breaks (a low below its bottom:
   `BROKEN`) or after `InpExpiryBars` bars (`EXPIRED`); otherwise the rally extreme `X` is updated and the MSS is
   checked.
5. **Decision.** With the MSS done, a free slot, the session open, no lockout and an acceptable spread, the EA
   computes `P`, `SL`, `TP1`, `TP2`. It waits (stays `ARMED`) if the market is already through `P`, if TP1 is less
   than `InpMinRR` times the risk, or if the costs exceed `InpMaxCostR` of the risk. At most one order per bar.
   - The decision uses the close of bar `u` plus the spread. At the first tick of the next bar the EA reads the live
     price again. If the market has already reached `P`, it sends a **market order** with the same SL and TP (the
     Python backtest fills that limit at the better open price). If `P` is on the right side but inside the broker's
     stops level, no order is sent and the setup stays `ARMED` for the next bar.
6. **Order (`ORDERED`).** A buy limit at `P` with SL and the server TP (TP2 in TP1_TP2 mode). The detector cancels
   it if the zone breaks, the setup expires, price runs to TP1 without filling (`RUNAWAY`) or 14:45 New York
   arrives (`SESSION_END`).
7. **Trade (`FILLED` → `CLOSED`).** At TP1 the EA closes half (virtual TP1) and moves the stop to break-even plus
   commission; the rest goes to TP2, the stop, the 120-minute time stop or the 16:44 New York flat time.

Shorts mirror everything: the sweep takes the highest high, `M` is a low, the sell limit is `T − 5 ticks` (bid), and
the SL / TP levels add the spread because a short exits on the ask.

## What you see on the chart

- **Zones** as in the LuxAlgo indicator: green "BPR" boxes (BPR up) and red ones (BPR down), the fill blended to
  look like the Pine transparency. The border is solid, dashed once price entered the zone, dotted with the break
  colour once broken. With `InpShowBPR = false` the FVG boxes are shown instead ("FVG" text). Hover a box for its
  top, bottom, active flag and `pos`.
- **Displacement arrows** (optional) on the last 300 bars, and **Fibonacci** lines between the last two BPRs
  (optional).
- **Trade overlays** like TradingView's position tool, for every decided order: a green rectangle from `P` to the
  final target, a red rectangle from `P` to the stop, a dashed line at TP1 (TP1_TP2 mode), from the decision bar to
  20 bars later, labelled `L#id` or `S#id`. They turn grey when the order is cancelled. The last 20 are kept. On a
  real account they carry "(log-only)".
- **Panel** (top left): mode (`TESTER`, `DEMO`, `REAL: LOG-ONLY` or `WAITING FOR ACCOUNT: LOG-ONLY`); source, entry
  mode and direction; setups armed;
  order or position state; today's realised result in R (realised P&L divided by the nominal 0.20 % risk) and the
  lockout state; the last event.

All objects are named `BFEA_...` and are deleted when the EA is removed. In a non-visual Strategy Tester run nothing is
drawn (faster).

**Removing or stopping the EA** (outside the tester) deletes its pending orders. An open position is kept, but only
its server SL/TP protect it: the 120-minute time stop, the 16:44 New York flat and the virtual TP1 / break-even run
only while the EA runs. The log then shows an error line for every reason except a recompile. An input change or a
chart change also gets the warning, because with a new magic number or symbol the restarted EA does not see the
position. Close the position by hand, or start the EA again on the same symbol with the same magic number: it adopts
the position again.

## Strategy Tester settings

| Setting | Value |
|---|---|
| Expert | `BprFvgEA` |
| Symbol / period | XAUUSD, M1 |
| Model | Every tick based on real ticks |
| Dates | **2020-01-01 → 2025-06-30** (never past 2025-06-30: the final-test period is locked) |
| Deposit / leverage | e.g. 100,000 USD, as on your account |
| Inputs | defaults (do not optimise; each changed value is a new registered trial) |

- The warm-up uses the 5,000 M1 bars before the start date, which the tester loads as history.
- Check in the tester's deal list that a **commission** is charged. If it is not, the P&L excludes it (the EA still
  sizes and filters with `InpCommissionPerLotSide`).
- `OnTester` returns the average R per closed trade, net of costs.
- Visual mode shows the zones, the overlays and the panel; the run is much slower.

## Logs

- **Experts log**: one line per setup state change, for example
  `[BFEA] #12 BPR LONG ARMED B=2650.40 T=2651.40 h=1.0000 sweep=2024.03.06 14:02 M=2652.10 ... | bar 2024.03.06 14:20`,
  then `MSS`, `PLACE_LIMIT ... P= SL= TP1= TP2=`, `FILLED`, `TP1 reached`, `CLOSED SL pnl ... R=...` or
  `DONE(BROKEN)` + `CANCEL(BROKEN)`. Warm-up setups are only counted in one summary line.
- **CSV** in the Common Files folder (`...\MetaQuotes\Terminal\Common\Files`); not written during optimisation.
  The name carries the symbol, timeframe, magic number and run mode, so a tester run never touches the files of a
  chart: `..._TESTER.csv` is rewritten at the start of each tester run, `..._LIVE.csv` (chart: demo or log-only) is
  appended to and flushed after every row. Files are opened with shared read access only: a second writer with the
  same file name gets an open error instead of overwriting rows.
  - `BFEA_setups_<symbol>_<tf>_<magic>_<TESTER|LIVE>.csv`: one row per setup when it ends (`DONE` or `CLOSED`), plus
    the open ones when the EA stops. Columns `run, id, source, dir, created_time, B, T, h, sweep_bar_time, M,
    mss_time, status, reason, P, SL, TP1, TP2, decision_time`.
  - `BFEA_trades_<symbol>_<tf>_<magic>_<TESTER|LIVE>.csv`: one row per closed trade. Columns `run, id, dir,
    entry_time, entry, lots, SL, TP1, TP2, exit_time, exit, exit_reason, pnl_usd, R, planned_risk_usd`.
    `exit_reason` is `SL`, `TP`, `BE_SL`, `TIME`, `ROLLOVER`, `TP1`, `BE`, `RISK` (excess risk after a market fill),
    prefixed with `TP1+` after a partial close.
  - `run` is the server time at which the EA started. Setup ids restart at 1 on every start, so `(run, id)`
    identifies a setup.
  - Times are **server time**, bar-open labelled (`created_time` = open of the creation bar, `decision_time` = open
    of the decision bar; the order is sent at the next bar's first tick).
- Reason codes (`DONE(reason)`): `BAD_GEOMETRY`, `BROKEN_AT_CREATION`, `INSUFFICIENT_HISTORY`, `NO_SWEEP`,
  `CAPACITY`, `WARMUP`, `BROKEN`, `EXPIRED`, `RUNAWAY`, `SESSION_END`, `SIZE_BELOW_MIN`, `ORDER_FAILED`. On a real
  account every decided setup ends `ORDER_FAILED` with a "LOG-ONLY ... not sent" line; that is the log-only rule,
  not an error. Otherwise `ORDER_FAILED` means a real refusal (margin, stops level on SL/TP, broker error); a
  transient condition (slot busy, no tick, stops level of the limit price, daily budget) logs "order not sent now"
  and the setup stays `ARMED`.

## Choices made where the specification leaves room

- Event records: a cancellation emits `DONE(reason)` first, then `CANCEL(reason)`; an order decision emits one
  `PLACE_LIMIT` or `MARKET` record (that is also the `ARMED → ORDERED` change). An MSS already present at creation
  (or `InpUseMss = false`) emits `MSS` right after `ARMED`. Fills and closes are logged by the EA, not as detector
  records. `P/SL/TP1/TP2` in a record are the setup's order levels (0 before an order is decided). Setup ids start
  at 1 and are given only to candidates that pass the source / direction filters.
- The sweep window is clipped at bar 0; `INSUFFICIENT_HISTORY` comes from the range and MSS windows, which are
  required even when `InpUseSweep` / `InpUseMss` are false.
- The checks of the decision (marketability, reward:risk, cost) use the unrounded levels; the levels are rounded to
  the tick when the order is decided. When TP2 is not beyond TP1 in TP1_TP2 mode, TP2 is set equal to TP1 and the
  trade uses TP1 only.
- `CAPACITY` is checked last, only for a candidate that would otherwise be `ARMED`.
- Session cancel: a pending order is cancelled when the next bar opens outside the entry window (14:45 New York, or
  a data gap past it).
- Bars caught up after a disconnection are processed in order, but no new order is decided on them (their decision
  spread is unknown); the setups stay `ARMED` and are tried on the latest bar.
- Daily risk: "risk OK" also requires that one more full 0.20 % loss still fits in today's budget, and the realised
  result is rebuilt from this EA's deals in the account history (restart-safe) on every new bar and right before
  every order. The FX day starts only once the account is connected and its equity is known; until then no new
  trade is allowed.
- Positions and orders are reconciled on every tick: a position with this EA's symbol and magic number that the EA
  does not track is adopted (time stop, 16:44 flat; logged as an error), and a pending order that is not the EA's
  live limit is deleted.
- If the TP1 split would leave less than the minimum volume, the whole position is closed at TP1. If the market is
  already through the break-even level when it should be set, the position is closed.
- 16:44 New York: a position is closed when the most recent 16:44 New York lies after its fill, or while the New York
  time is between 16:44 and 17:00.

## Known limitations

- Not compiled yet (see the status above). The mechanical checks cannot find MQL5-specific type or overload errors.
- The trading rules are hypothesis H-13. The EA-vs-Python parity harness runs in CI and covers the pure modules only
  (decision logic, not execution or drawing). EXP010 was pre-registered at commit `880ac1c` and has run; see
  `reports/EXP010_BPR_FVG_EA_REPORT.md`.
- Decisions use the live spread at the first tick of the next bar; the Python simulator uses a modelled spread. A
  limit can fill and reach TP1 inside one bar in the EA; the Python simulator cancels that case
  (`RUNAWAY_SAME_BAR`). A limit that is already marketable at the first tick of the next bar is sent at market by
  the EA (fill at the live ask/bid) and filled by Python at `min(P, ask_open)`. A limit inside the stops level waits
  for the next bar in the EA. Expect such differences between EA and Python trade lists.
- The EA keeps every bar since it started in memory (about 40 bytes per bar, roughly 80 MB for 2020–2025 M1).
- After a restart, setups in progress are not restored (the warm-up rebuilds the zones; warm-up setups are never
  traded). A restored position is managed (server SL/TP, time stop from its open time, TP1 from the order comment
  `BF|<id>|<TP1>`), but its R multiple is not known.
- One position or order per symbol and magic number, and one EA instance per account (the daily budget is per
  instance). Do not run other trading on the same symbol on a netting account (positions would merge).
- Netting accounts: TP1_TP2 falls back to TP1_ONLY (no partial close). If a market fill there exceeds the risk budget,
  the whole position is closed instead of the excess volume.
- If the EA is removed while a position is open, that position keeps only its server SL/TP until the EA runs again.
- No news filter. Spread widening at the rollover or on news can trigger the stop (a long's stop triggers on the
  bid).
- Boxes that extend into the future are placed by bar count times the period, which ignores weekends and holidays.
- Objects are deleted when the EA stops, including at the end of a visual test.

## Verification so far

**Reproducible, run in CI on every push:**

| Test | What it checks |
|---|---|
| `tests/test_bpr_fvg_ea_harness.py` | The pure files (`BfDefines`, `BfEngine`, `BfDetector`) are transliterated to C++, compiled with g++ and compared **event by event** with the Python reference `qe/strategies/bpr_fvg.py`.<br>• Records compared: every ARMED, MSS, PLACE_LIMIT, MARKET, DONE and CANCEL record, with prices.<br>• 10 configurations: BPR/FVG/BOTH sources, LIMIT/CONFIRM entry, filters on and off, long-only and short-only, three TP modes, warm-up, price ties.<br>• Mutation checks: deliberate one-character bugs were caught. |
| `tests/test_bpr_fvg_strategy.py` | 63 scenario tests of the Python reference (spec sections 3–5), including causality and the simulator fill and exit rules. |
| `tests/test_luxbpr_mql5_harness.py` | The same engine code in the indicator, checked against the LuxAlgo Python reference. |

These checks cover the EA's decision logic only. They do not cover MetaEditor compilation, MT5 order execution, or
the drawing code.

**Earlier ad-hoc checks**, made while writing the EA. Their outputs are not saved, so they are not `VERIFIED`:

| Check | Outcome of the ad-hoc run |
|---|---|
| `python3 tools/mql5_static_check.py mql5/BprFvgEA` | brackets balanced, includes resolve; the only names it flags are MQL5 built-ins and `CTrade` methods missing from its list |
| The pure files (`BfDefines`, `BfEngine`, `BfDetector`) compiled as C++ with `-Wall -Wextra -Wshadow -Wconversion` | no warnings |
| Engine state after every bar vs. the indicator `LuxAlgo_BPR.mq5` (Historical mode, via its C++ harness), 6,000 random bars, 5 parameter sets incl. IFVG and ≥ 12 boxes, plus the BPR-off FVG styling | identical |
| Detector causality: events for bars before N are identical with and without later bars (all sources, entry modes and directions) | identical |
| Whole EA type-checked as C++ against stub MT5 declarations | no errors, no warnings |

None of this proves that MetaEditor compiles the code or that the strategy has an edge.
