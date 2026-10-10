# BprFvgEA v3: LuxAlgo BPR / FVG zones + BPR rejection → breakout → Fibonacci entries (MetaTrader 5)

> **v3 (2026-10-10)** = v2 plus three on/off switches, at the owner's request. They let entries go out even when they
> would be skipped for **cost**, **reward:risk** or the **14:45 New York session end**:
>
> | Input | Default | `false` means |
> |---|---|---|
> | `InpUseCostFilter` | true | Entries are placed whatever their round-trip cost (`InpMaxCostR` is ignored). No more `SKIP (COST)`. |
> | `InpUseRRFilter` | true | Entries are placed whatever their reward:risk (`InpMinRR` is ignored). No more `SKIP (RR)`. The default `InpMinRR` is already 0 (off). |
> | `InpCancelAtSessionEnd` | true | Pending limit orders are **not** cancelled at 14:45 New York (no more `CANCEL (SESSION_END)`). They stay until they fill, the leg expires (`InpLegExpiryBars`) or a new high re-anchors the setup. |
>
> With all three at `true`, v3 behaves exactly like v2.
>
> **What the switches do not change:**
> - **New orders after 14:45 New York.** Those still need `InpUseSession = false`, which also removes the 08:00
>   London start.
> - **The 16:44–17:00 New York rollover rule.** Pending orders are still deleted then, because a fill there would be
>   closed at once by the 16:44 flat. The log calls this `ROLLOVER`, but the record reason is `SESSION_END`, and the
>   panel counts these deletes separately.
> - **The hard limits:** 0.20 % risk per setup, 1 % daily loss, 120-minute time stop, tester / demo only.
>
> **Implementation.** The switches live in the EA only. The executor passes a disabled filter to the detector as 0
> (= off) and withholds the session-end signal, so the detector and its Python reference are unchanged.

One Expert Advisor that does two things:

1. **Draws** the Fair Value Gaps (FVG) and Balance Price Ranges (BPR) like the LuxAlgo indicator ("ICT Concepts
   [LuxAlgo]").
2. **Trades the owner's BPR setup** (2026-10-09), in the Strategy Tester or on a demo account:
   1. a BPR is used once and touched at most twice, with a rejection candle between the touches;
   2. price breaks the high (long) or low (short) of the last candle before the rejection, with at least one FVG;
   3. two closes beyond that level confirm the breakout;
   4. the EA follows the breakout leg until the first pullback candle;
   5. it draws a Fibonacci from the leg's origin to its extreme and places **three limit orders at 50 %, 61.8 % and
      71 %**, all targeting the leg extreme.

The rules are written in [`research/indicators/BPR_BREAKOUT_FIB_SPEC.md`](../../research/indicators/BPR_BREAKOUT_FIB_SPEC.md),
the single source of truth. Section 0 of that spec quotes the owner's message and says how each phrase was read. The
Python reference with the same detector decisions is `qe/strategies/bpr_breakout.py`.

> **Status: NOT YET COMPILED.** No MetaEditor was available where it was written. Compile it and send back the
> complete list of errors and warnings.
>
> **Trading rules: hypothesis H-14, untested.** Nothing here shows that the setup makes money. Version 1 (sweep /
> MSS / far-edge limit, H-13) lost −0.37 R per trade in the pre-registered backtest EXP010. It is frozen in
> `mql5/archive/BprFvgEA_v1_H13`.

## Why v1 placed (almost) no limit orders, and what v2 changes

- **Silent filters.** v1 decided an order only when the round-trip cost was **≤ 0.15 R** and TP1 gave
  **reward:risk ≥ 1.0**. Both checks failed **without a log line**, so setups just sat `ARMED` until they broke or
  expired.
- **Small M1 zones.** Most M1 zones are much smaller than these checks need. On XAUUSD the stop had to be about 1.3–2.6
  price units; on EURUSD about 7–13 pips.
- **Few orders even in the backtest.** With the sweep and structure-shift filters on top, the backtest placed about
  7 orders a month on XAUUSD, and almost none on M1 FX.

v2:
- **Logs every rejection.**
  - A record for every state change and every skipped or refused entry, with its reason.
  - The panel counts every reason (see [Panel](#panel-why-no-orders)).
  - A **self-check** at start prints everything that can stop an order (see [Self-check](#self-check-at-start)).
  - A summary at every new FX day and at the end of a test.
- **Places orders more robustly.**
  - Limit orders go through `CTrade`, which uses the symbol's filling mode. If the server refuses that mode
    (`INVALID_FILL`), the order is sent again with the `RETURN` mode. The panel shows the mode actually sent.
  - When the broker refuses the expiration time, the order is sent again as GTC.
  - The error breaker counts **one strike per decision**, not one per order. It ignores transient refusals (requote,
    timeout, connection, price changed…) and resets after 30 minutes. While it is tripped, the panel says
    `BREAKER TRIPPED`.
- **Checks the "Algo Trading" switches.** It checks the terminal button, the EA's "Allow Algo Trading" box and the
  account's expert permission. Refusals for these reasons do not trip the error breaker.
- **Uses the owner's own rules.** The cost filter is per entry, at 0.30 R, and can be turned off. There is no
  reward:risk filter by default.

## Safety (read first)

- **Tester and demo only.**
  - Orders are sent only in the Strategy Tester and on **demo** accounts.
  - On a **real account the EA is log-only**: it draws, detects and logs, and sends no order. There is no input to
    change this.
  - The account check fails closed: while the account is not known yet, the EA is log-only too.
- **Hard limits in code**, which no input can raise:
  - risk is **0.20 % of equity per setup**, commission included, split equally over the enabled entries (0.067 % each
    with three entries);
  - **1.00 % planned daily loss** per FX day (from 17:00 New York), then lockout;
  - one setup with orders or positions at a time;
  - every position is closed at most **120 minutes after its fill** and before **16:44 New York**;
  - no martingale, grid, averaging down or size increase after losses. The three Fibonacci entries are a fixed plan,
    decided once, with a fixed total risk. They are never added after a loss.
- **One EA instance per account.** The daily budget is per instance.
- **Locked final-test period.** Do not use data from **2025-07-01 onward** to choose or tune anything.
- **Broker values are `UNVERIFIED`:**
  - commission (3.50 per lot per side);
  - contract size, tick value and stops level;
  - server time (IC Markets = New York + 7 h).

## Licence and attribution

The FVG / BPR / displacement / Fibonacci zone logic is a port of the Pine v5 script **"ICT Concepts [LuxAlgo]"**,
© LuxAlgo, licensed under **CC BY-NC-SA 4.0** (<https://creativecommons.org/licenses/by-nc-sa/4.0/>). The EA as a
whole is distributed under the same licence: **non-commercial use only, attribution to LuxAlgo, share-alike**. It is
not affiliated with or endorsed by LuxAlgo. The setup rules are the project owner's.

## Install

1. Copy the **whole** `BprFvgEA` folder (`BprFvgEA.mq5` **and** `include/`) to `MQL5/Experts/`. To find it: File →
   Open Data Folder.
2. Open `BprFvgEA.mq5` in MetaEditor and compile (F7).
3. Attach it to an **XAUUSD M1** chart. Any symbol or timeframe works.
4. On a demo chart, turn on **Algo Trading** (toolbar button) and tick **Allow Algo Trading** in the EA's Common tab.

| File | Contents |
|---|---|
| `BprFvgEA.mq5` | Inputs, warm-up, new-bar loop, execution of the three entries, position management, drawings, panel, logs |
| `include/BfDefines.mqh` | Enums, codes, parameter and record structures (pure) |
| `include/BfEngine.mqh` | The LuxAlgo FVG / BPR engine, unchanged from v1 (pure; LuxAlgo licence) |
| `include/BfDetector.mqh` | The setup detector of the spec (pure; checked against Python) |
| `include/BfSession.mqh` | Server time → UTC / New York / London with DST, entry window, FX day, 16:44 flat |
| `include/BfRisk.mqh` | Sizing per entry and the daily-loss lockout |
| `include/BfTrade.mqh` | Orders through `CTrade`: filling and expiration fallbacks, permissions, account guard |
| `include/BfRender.mqh` | Zones, displacement markers, setup drawings, panel (LuxAlgo licence) |
| `include/BfLogger.mqh` | Experts-log lines and CSV files |

## Inputs

### Display

| Input | Default | Meaning |
|---|---|---|
| `InpShowZones` / `InpShowBPR` / `InpShowFVGinBPRmode` | true / true / false | LuxAlgo boxes. BPR boxes are shown by default; with `InpShowBPR = false` the FVG boxes are shown instead. |
| `InpVisibleBoxes` / `InpLength` | 2 / 5 | LuxAlgo `# Visible FVG's` and `Length` |
| `InpFvgType` | FVG | FVG or IFVG. **Setups need FVG**: in IFVG mode the EA only draws. |
| `InpShowDisplacement` / `InpDisplacementBars` | false / 300 | Displacement arrows |
| `InpFib` / `InpFibExtend` | NONE / false | LuxAlgo's own "Fibonacci between last BPR" (display only; not the setup Fibonacci) |
| `InpLiveBar` | true | Show the forming bar. Decisions never use it. |
| colours, transparencies | as LuxAlgo | |
| `InpShowSetups` | true | The setup drawings (see [What you see](#what-you-see-on-the-chart)) |
| `InpShowPanel` | true | The status and diagnostics panel |

### Setup (the owner's rules; hypothesis H-14)

| Input | Default | Meaning |
|---|---|---|
| `InpDirection` | BOTH | BOTH, LONG_ONLY or SHORT_ONLY |
| `InpMaxTouches` | 2 | Touches of the BPR allowed. Consecutive touching candles count as one touch. One more touch ends the setup. |
| `InpConfirmCloses` | 2 | Candles that must **close** beyond the breakout level: the breakout candle plus the next one |
| `InpRejectBeforeBreak` | false | Stricter reading. A rejection candle (one that does not touch the zone) must come **before** the breakout candle, so the first candle out of the zone can no longer be the breakout. |
| `InpFvgRule` | LUXALGO | FVG needed in the breakout leg. `LUXALGO`: an FVG the LuxAlgo engine makes (displacement candle + gap). `ANY_GAP`: any 3-candle gap. `NONE`: no FVG needed. |
| `InpSetupExpiryBars` | 240 | The breakout must be confirmed within this many bars of the BPR's creation |
| `InpLegExpiryBars` | 60 | After the confirmation, orders may be placed or filled for this many bars |
| `InpFib1` / `InpFib2` / `InpFib3` | 50 / 61.8 / 71 | Entry retracements in % of the leg. 0 turns an entry off. |
| `InpStopFib` / `InpStopBufferTicks` | 100 / 10 | Stop at this retracement (100 = the leg origin) plus this many ticks |
| `InpTargetFib` | 0 | Take-profit retracement. 0 = the leg high (long) or low (short); negative = an extension beyond it. |
| `InpUseRRFilter` | true | **v3 switch.** `false`: the reward:risk filter is off, whatever `InpMinRR` says |
| `InpMinRR` | 0 | Minimum reward:risk per entry (0 = off) |
| `InpUseCostFilter` | true | **v3 switch.** `false`: the cost filter is off, whatever `InpMaxCostR` says. Entries go out even when costs are a large part of their risk. |
| `InpMaxCostR` | 0.30 | Skip an entry whose round-trip cost (spread + commission + 2 ticks of slippage) exceeds this fraction of its risk (0 = off) |
| `InpMaxHoldMin` | 120 | Time stop per position, minutes (capped at 120) |

### Session, risk and execution

| Input | Default | Meaning |
|---|---|---|
| `InpServerMode` / `InpServerOffsetH` | NY+7 / 0 | Server time → UTC. NY+7 is IC Markets (`UNVERIFIED`). The [self-check](#self-check-at-start) prints the resulting entry window. |
| `InpUseSession` | true | New orders only 08:00 London → 14:45 New York, Mon–Fri. Pending orders are cancelled at 14:45 New York (unless `InpCancelAtSessionEnd = false`). |
| `InpCancelAtSessionEnd` | true | **v3 switch.** `false`: pending orders are kept after 14:45 New York until they fill or the leg expires. They are still deleted at the 16:44–17:00 New York rollover. |
| `InpRiskPct` | 0.20 | Risk **per setup**, % of equity incl. commission, split over the entries (capped at 0.20) |
| `InpDailyLossPct` | 1.00 | Planned daily loss, % (capped at 1.00) |
| `InpMaxTradesDay` | 0 | Maximum positions per FX day (0 = no limit) |
| `InpCommissionPerLotSide` | 3.50 | Commission per lot per side, account currency (`UNVERIFIED`) |
| `InpSlippageTicks` | 1 | Added to the stop distance for sizing, and to the cost check |
| `InpMaxSpreadPts` | 0 | No new orders while the spread is above this (0 = off) |
| `InpMagic` | 2610091 | Magic number, the same for v2 and v3. It differs from v1, so v1 positions are not mixed in. |
| `InpDeviationPts` | 30 | Market orders (an entry whose price is already reached when it is sent) |
| `InpWarmupBars` | 5000 | Closed bars processed at start. Setups created during warm-up are never traded. |
| `InpLogCsv` | true | CSV logs in the Common Files folder |

## How a setup works (long; a short is the mirror image)

Every step uses **closed bars only**.

```
                                    X  leg extreme (tracked; fib 0 %)   <- TP (target)
                          B2  /\  /\
                   B1 ___/__\/__\___ first candle that does NOT make a new high = pullback -> orders
   level = high of  /     ..................  50.0 %   L1 buy limit
   the last touching       ..................  61.8 %   L2 buy limit
   candle (ref)  _|_       ..................  71.0 %   L3 buy limit
   T ==========T1===|====T2========== BPR (bullish, pos = +1)
   B ===============|=================
                    O  leg origin = lowest low since the last touch began (fib 100 %)
                       SL = O - 10 ticks
```

1. **BPR.** The LuxAlgo engine creates a BPR on bar `u`.
   - Its `pos` decides the direction: `+1` (price above the box) gives a long setup, `−1` a short setup.
   - **The box colour is not the direction.** Green or red only tells which gap created the box. A red box can be a
     long, and a green one a short. Each setup therefore draws **its own zone outline** in the trade's colour.
   - Each BPR gives one setup ("used one time").
2. **Touches.**
   - A **touch** is a candle whose low reaches the box (`low ≤ top`). Consecutive touching candles are one touch.
   - A **rejection** is a candle that stays above the box. A second touch counts only after a rejection.
   - A third touch ends the setup (`TOUCH_LIMIT`). A low below the box bottom breaks the BPR (`BROKEN`).
3. **Breakout.**
   - The **reference candle** is the last touching candle; its **high is the breakout level**.
   - The **breakout candle** (`B1`) is a candle that **does not touch the box** and **closes** above the level. A
     wick above does not count.
   - A candle that still touches the box and closes above the level is part of the touch. It becomes the new
     reference candle, and its high becomes the new level.
   - The **next candle must also close above it** (`B2`). Otherwise the breakout fails (`BREAK_FAIL`), and the
     setup keeps waiting under the same touch rules.
4. **Leg.**
   - After `B2`, the EA tracks the leg high `X` and updates it on every new high.
   - The leg origin `O` is the lowest low since the last touch began.
   - A low below `O` ends the setup (`LEG_BROKEN`).
5. **FVG.** At least one bullish FVG must have formed after the reference candle. With the `LUXALGO` rule it is a
   LuxAlgo FVG: a displacement candle plus a gap. Until then the setup waits; the panel counts these bars as
   `no FVG`.
6. **Pullback and orders.** On the **first closed candle that does not make a new high**, the EA computes the
   Fibonacci from `O` (100 %) to `X` (0 %). It sends:
   - **buy limits** at 50 / 61.8 / 71 %, each at the Fibonacci price plus the spread, so each fills when the bid
     touches its level;
   - **SL** = `O` − 10 ticks, the same for all three;
   - **TP** = `X`, the same for all three.

   An entry is skipped (`SKIP`) when:
   - price is already through it (`MISSED`);
   - its costs exceed 0.30 of its risk (`COST`).

   The three entries share 0.20 % of equity: 0.067 % each.
7. **Re-anchor.** A new high **before any fill** cancels the orders (`CANCEL NEW_EXTREME`). The EA updates `X` and
   places new orders on the next pullback candle.
8. **After a fill.** When the target is touched or a new high comes, the remaining limits are cancelled
   (`CANCEL TARGET`). Each position exits at:
   - its SL or TP;
   - the 120-minute time stop;
   - the 16:44 New York flat.

   Unfilled orders are also cancelled at 14:45 New York (`SESSION_END`) and after `InpLegExpiryBars` (`EXPIRED`).

If a level is already reached when its order is sent (a gap at the next bar's open), it is sent as a **market order**
at the better price, with the same SL / TP.

## What you see on the chart

- **LuxAlgo zones:**
  - green and red BPR boxes, like the indicator;
  - a dashed border once price enters a box;
  - a dotted border in the break colour once it is broken.
- **Setup drawings** (`InpShowSetups`):
  - the setup's own zone, a dash-dot outline in the trade's colour, from the first touch on;
  - `T1` / `T2` under the touch candles;
  - a dotted line at the **breakout level**, from the reference candle to the breakout;
  - `B1` / `B2` on the breakout and confirmation candles; `x` on a failed confirmation;
  - the **Fibonacci** from the leg origin to the leg extreme: 0 %, 100 % and the three entry levels.
    - While the leg is tracked it is **dashed**, labelled "(tracking)", and follows every new high.
    - Once the orders are placed it is **solid**. Each entry line is labelled with its order price and state, for
      example `61.8% L2 BUY LIMIT 2351.23 PENDING`. Skipped entries carry their reason.
    - Red **SL** and green **TP** lines are added.
  - A finished setup turns grey and stays on the chart. The last 40 setups are kept.

## Panel: why no orders?

The panel (top left) answers "why is nothing happening?" at a glance:

| Row | Example | How to read it |
|---|---|---|
| 1 | `mode: TESTER \| algo trading: ON` | `REAL: LOG-ONLY` or `algo trading: OFF - …` means no order can go out; the reason is spelled out. |
| 2 | `rules: touches <= 2, 2 closes, FVG LUXALGO \| entries 50.0% 61.8% 71.0% \| …` | The active rules |
| 3 | `switches: cost filter <= 0.30 R \| RR filter off (InpMinRR = 0) \| cancel at 14:45 NY ON \| entry window … \| rollover deletes 0` | **v3:** the state of the three switches and the entry window |
| 4 | `tracking: wait 3 zone 1 breakout 0 leg 1 ordered 0 filled 0` | Setups in each phase now |
| 5 | `funnel: BPRs 57 \| touches 31 \| breakouts 9 (failed 3) \| confirmed 6 \| entry decisions 9 (orders accepted 9) \| closed 2` | How far setups get, cumulative since start |
| 6 | `entries skipped: missed 1 cost 7 rr 0 bad 0 \| dropped: size 0 refused 0 expired 0` | Why decided entries were not sent: `cost` → `InpUseCostFilter` / `InpMaxCostR`; `rr` → `InpUseRRFilter` / `InpMinRR`; `size` → the account is too small for the minimum volume; `refused` → the broker refused (see row 9 and the log) |
| 7 | `waiting: no FVG 12 bars \| blocked: session 40 slot 0 daily-risk 0 spread/catch-up 0 \| retried 0 \| re-anchored 2` | Ready setups that could not decide, and why |
| 8 | `ended: broken 30 … session 0 (rollover deletes 0) refused 0 …` | How setups ended without a trade |
| 9 | `orders: accepted 9 refused 0 \| filling … \| last error: …` | Broker responses, with the last retcode |
| 10 | `orders/positions: #12 LONG SL … TP …: L1 limit … \| L2 open 0.04 @ …` | The live orders and positions |
| 11 | `today: … \| lockout: no \| positions 2 \| last: …` | Daily risk state and the last event |

The same rows go to the Experts log as `DIAG` lines at every new FX day and when the EA stops.

## Self-check at start

After the warm-up the Experts log shows `SELF-CHECK` lines:
- **account:** mode, hedging or **netting**, equity, leverage;
- **permissions:** OK, or exactly which switch blocks trading;
- **symbol:** tick size, value of a 1.0 price move per lot, stops and freeze levels, current spread, filling and
  expiration modes;
- **risk:** the budget per entry. It also gives the **largest stop that the minimum volume (e.g. 0.01 lot) still
  fits**. Wider stops give `SIZE_BELOW_MIN`, so raise the test deposit if that number is small;
- **session:** today's entry window in **server time**. Check that it is 08:00 London to 14:45 New York for your
  broker; if not, change `InpServerMode`.

## Strategy Tester settings

| Setting | Value |
|---|---|
| Symbol / period | XAUUSD, M1 |
| Model | Every tick based on real ticks |
| Dates | Up to **2025-06-30** at most. Never later: the final-test period is locked. |
| Deposit | e.g. 10,000 USD or more. The self-check tells you whether the minimum volume fits the budget per entry. |
| Inputs | Defaults. Do not optimise. Each changed value is a new trial. |

**What to send back after a test:**
1. the Journal / Experts lines starting with `[BFEA]`, at least the `SELF-CHECK` and `DIAG` lines;
2. the tester report;
3. `BFEA2_trades_*_TESTER.csv` and `BFEA2_setups_*_TESTER.csv` from the Common Files folder.

## Logs

- **Experts log:** one line per detector record. Examples:
  - `#12 LONG TOUCH 1 of max 2 (zone …)`
  - `#12 LONG BREAKOUT level 2351.20 (high of the candle at …)`
  - `#12 LONG CONFIRM: leg 2349.50 -> 2353.80`
  - `#12 LONG PLACE_LIMIT L2 (61.8%) P= SL= TP=`
  - `#12 LONG SKIP L3 (71.0%) (COST)`
  - `#12 LONG CANCEL L1 (50.0%) (NEW_EXTREME)`
  - `#12 LONG DONE (BROKEN)`

  The execution layer adds:
  - `… LIMIT LONG sent: lots P= SL= TP= planned risk`;
  - `FILLED`;
  - `CLOSED TP pnl … R=…`;
  - `orders not sent now: <reason>`, and the order-failure lines with the broker's retcode.
- **CSV** in the Common Files folder. `_TESTER` files are rewritten on each tester run; `_LIVE` files are appended to.
  - **`BFEA2_setups_<symbol>_<tf>_<magic>_<TESTER|LIVE>.csv`.** One row per setup when it ends, plus the open ones
    when the EA stops. Columns:
    - `run, id, dir, created_time, B, T, touches`;
    - `ref_time, level, breakout_time, confirm_time, O, X`;
    - `decision_time, SL, TP, L1, L2, L3, phase, reason`.

    `L1`–`L3` hold a state and a price (`CLOSED@2351.23`), a state and a reason (`SKIPPED:COST`), or `off`.
  - **`BFEA2_trades_<symbol>_<tf>_<magic>_<TESTER|LIVE>.csv`.** One row per closed position. Columns:
    - `run, id, levels, dir`;
    - `entry_time, entry, lots, SL, TP`;
    - `exit_time, exit, exit_reason, pnl, R, planned_risk`.

    `exit_reason` is `SL`, `TP`, `TIME`, `ROLLOVER`, `RISK` or `MANUAL`. R is net P&L divided by the planned risk of
    that entry.

## Choices where the owner's words leave room

All of these are inputs or are stated in the spec (§0):
- **Touch zone.** A touch is measured against the BPR box **as drawn** (LuxAlgo `top` / `bottom`). The box can be
  slightly taller than the true overlap of the two gaps (LuxAlgo QUIRK 4).
- **Rejection.** At least one candle that does not touch the box.
- **Breakout level.** The high (long) or low (short) of the last touching candle of the latest touch.
- **Leg origin.** The lowest low (long) since the latest touch began.
- **"61" and "71".** Read as 61.8 % and 71.0 %.
- **Stop and risk.** The owner gave neither a stop nor a risk split. The stop is the leg origin minus 10 ticks; the
  0.20 % risk is split equally over the three entries.

## Known limitations

- **Not compiled yet.**
- **Strategy untested** (H-14). A pre-registered backtest (EXP011) is the next research step.
- **Netting accounts.** The three fills merge into one position:
  - the time stop counts from the first fill;
  - closing one entry closes all of them;
  - one trades-CSV row covers the merged entries.
- **No setup recovery after a restart.** Setups in progress are not restored. Positions found at start are managed
  without their setup: server SL/TP, the time stop and the 16:44 flat. Pending orders left from before are deleted.
- **Fills that race a cancel.** A fill that happens just as the EA cancels the order is managed without its setup.
- **Stopping the EA.**
  - Removing the EA, or closing its chart or the terminal, **closes its positions**: no time stop would run any
    more. It also deletes its pending orders.
  - A recompile, an input change or a timeframe change keeps the positions, and the restarted EA manages them again.
- **Spread and decision time.** Decisions use the spread at the first tick of the next bar. The Python reference uses
  a constant or modelled spread.
- **No news filter.**

## Verification so far

**Reproducible, run in CI on every push:**

| Test | What it checks |
|---|---|
| `tests/test_bpr_breakout_ea_harness.py` | The pure files (`BfDefines`, `BfEngine`, `BfDetector`) are compiled as C++ and compared **record by record** with `qe/strategies/bpr_breakout.py`, under a bar-based fill/exit harness: 10 random configurations and 67 hand-built sequences (with the strict-rejection option too), including exact comparison boundaries. Diagnostic counters must match too. Mutation checks: 24 deliberate small bugs (flipped comparisons, removed conditions, a wrong price or buffer) were all caught. |
| `tests/test_bpr_breakout_strategy.py` | 53 scenario tests of the rules: exact Fibonacci prices, touches, breakout and failure, FVG rule, re-anchor, fills and target, cost / RR / missed entries, environment gates, executor feedback, warm-up, **causality (no look-ahead)** |
| `tools/mql5_static_check.py mql5/BprFvgEA` | Mechanical check: names and brackets. It cannot find MQL5 type errors. |

None of this proves that MetaEditor compiles the code, that MT5 executes the orders as intended, or that the strategy
has an edge.
