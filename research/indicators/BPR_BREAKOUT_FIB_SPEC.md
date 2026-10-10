# BprFvgEA v3: BPR rejection → breakout → Fibonacci pullback

**Status:** hypothesis **H-14**. `HYPOTHESIS`: it has not been tested. Nothing here is evidence of an edge.

**Origin:** the rules come from the project owner's message of 2026-10-09 (quoted in §0). The defaults were fixed
from that message **before any data was looked at**.

**Implementations.** This file is the single source of truth for:
- the MQL5 EA `mql5/BprFvgEA/` (version 3.00; v3 = v2 plus the EA-only switches of §8): pure detector `include/BfDetector.mqh`, executor `BprFvgEA.mq5`;
- the Python reference `qe/strategies/bpr_breakout.py`.

The two detectors must emit the same event records; `tests/test_bpr_breakout_ea_harness.py` checks this.

**v1.** v1 (H-13, the sweep / MSS / far-edge limit rules) was **REJECTED** by EXP010. It is frozen in
`mql5/archive/BprFvgEA_v1_H13/`, and its spec is `BPR_FVG_EA_SPEC.md`.

**Licence:** the zones come from the LuxAlgo FVG / BPR engine (CC BY-NC-SA 4.0, non-commercial). The setup rules
are the project owner's, not LuxAlgo's.

## 0. The owner's rule (verbatim) and how it is read

> "first condition is a BPR must be used one time and price must test it maximum two time, and also between this
> two touches or retests it must a price action moves by other words not two successives candles but one candle
> touches price must be rejected from the BPR to the opposite direction like if the BPR is a rejection zone, after
> that price must comeback and make the BREAKOUT with minimum 1 FVG of the high or low of last candle before
> rejection from the BPR, after that price must close above or below this last high or low with the body of the
> candle and also the second candle bodys after the breakout must close above or below this last high or low, and
> the EA must track, follow and update the high or low of the breakout to detect the retracement and pullback phase
> to draw a fibo from the low/high of the breakout leg to his high/low before retracement, and the entry is on fib
> levels 50, 61 and 71 targeting this last high/low before retracement"

How each phrase is read. Every choice not fixed by the text is an input with the default shown.

| Phrase | Reading (example: a long from a bullish BPR) |
|---|---|
| "a BPR must be used one time" | Each BPR gives at most **one** setup. Once that setup ends, for any reason, the BPR is never used again. |
| "test it maximum two time" | A **touch** is a candle whose low reaches the zone (`low ≤ top`). Consecutive touching candles are **one** touch. A 3rd touch ends the setup (`TOUCH_LIMIT`). Input `InpMaxTouches = 2`. |
| "not two successive candles … rejected … to the opposite direction" | Two touches must be separated by a **rejection**: at least one candle that does not touch the zone (it stays on the far side, `low > top`). |
| "the high … of last candle before rejection" | The **reference candle** is the last candle of the latest touch. Its high is the **breakout level**. |
| "make the BREAKOUT … close above … with the body" | **Breakout candle:** a candle that does **not** touch the zone closes above the breakout level. A wick alone does not count. A touching candle that closes above the level is still part of the touch: it becomes the new reference candle, and its high the new level (revision 2, from the adversarial review). Stricter option `InpRejectBeforeBreak` (default off): the previous candle must not touch either, so a rejection candle comes before the breakout candle. |
| "the second candle … must close above" | **Confirmation:** the next candle also closes above the level. `InpConfirmCloses = 2` counts both closes. If the second close fails, the breakout fails and the setup waits for a new one (touch rules still apply). |
| "with minimum 1 FVG" | At least one **bullish FVG** has formed on a bar after the reference candle. The setup cannot place orders until one has. Input `InpFvgRule`: `LUXALGO` (default) = the engine's FVGs, the boxes the indicator draws (displacement candle + gap); `ANY_GAP` = any 3-candle gap `low[j] > high[j-2]`. |
| "track, follow and update the high of the breakout" | After confirmation the **leg extreme** `X` (highest high) is updated on every new high. The **leg origin** `O` is the lowest low since the latest touch began, the low of the breakout leg. |
| "detect the retracement and pullback phase" | **Pullback** = the first closed candle that does **not** make a new high (`high ≤ X`). Only then are orders placed. A new high before any fill cancels the orders and moves the Fibonacci (re-anchor). |
| "fibo from the low of the breakout leg to his high" | Fibonacci with 100 % at `O` and 0 % at `X`. |
| "entry is on fib levels 50, 61 and 71" | Three **limit orders** at the 50.0 %, 61.8 % and 71.0 % retracement. Inputs `InpFib1..3`; 0 turns a level off. "61" is read as the standard 61.8 %, and "71" as 71.0 %. |
| "targeting this last high" | Every level's take-profit is the leg extreme `X` (`InpTargetFib = 0`; a negative value is an extension beyond `X`). |
| (not stated) stop | Beyond the leg origin: `InpStopFib = 100` % plus `InpStopBufferTicks = 10` ticks. |
| (not stated) risk | `InpRiskPct = 0.20` % is the **total** per setup, split equally over the enabled levels (0.067 % each with 3 levels). This stays under the project limit of 0.20 % per position, including costs. |

The short side is the exact mirror: a bearish BPR, touches from below, the breakout level is the **low** of the
reference candle, the leg runs from a high `O` down to a low `X`, and sell limits sit at the retracements.

## 1. Inputs (EA) / `BreakoutParams` (Python)

| EA input | Python field | Default | Meaning |
|---|---|---|---|
| `InpDirection` | `direction` | `BOTH` | `BOTH` / `LONG_ONLY` / `SHORT_ONLY` |
| `InpMaxTouches` | `max_touches` | 2 | Touches allowed (1..5); one more ends the setup |
| `InpConfirmCloses` | `confirm_closes` | 2 | Consecutive closes beyond the level, breakout candle included (1..5) |
| `InpRejectBeforeBreak` | `reject_before_break` | false | The breakout candle must come after a rejection candle (it cannot be the first candle out of the zone) |
| `InpFvgRule` | `fvg_rule` | `LUXALGO` | `LUXALGO` / `ANY_GAP` / `NONE` (`NONE` drops the FVG condition) |
| `InpSetupExpiryBars` | `setup_expiry_bars` | 240 | Bars after the BPR's creation to reach confirmation |
| `InpLegExpiryBars` | `leg_expiry_bars` | 60 | Bars after confirmation during which orders may be placed or filled |
| `InpFib1` / `2` / `3` | `fib_levels` | 50.0 / 61.8 / 71.0 | Entry retracements, % of the leg (0 = off) |
| `InpStopFib` | `stop_fib` | 100.0 | Stop at this retracement, % (100 = the leg origin) |
| `InpStopBufferTicks` | `stop_buffer_ticks` | 10 | Extra ticks beyond the stop level |
| `InpTargetFib` | `target_fib` | 0.0 | Take-profit retracement, % (0 = the leg extreme, < 0 = extension) |
| `InpMinRR` | `min_rr` | 0.0 | Minimum reward:risk per level (0 = off) |
| `InpMaxCostR` | `max_cost_r` | 0.30 | Maximum round-trip cost per level, as a fraction of its risk (0 = off) |
| `InpMaxHoldMin` | `max_hold_min` | 120 | Time stop per position, minutes (hard cap 120) |
| `InpUseSession` | `use_session` | true | Entries 08:00 London → 14:45 New York, Mon–Fri. Orders are cancelled at 14:45 NY (EA: unless the switches of §8 change it). |
| `InpUseCostFilter` / `InpUseRRFilter` | (EA only) | true / true | Switches, §8 |
| `InpCancelAtSessionEnd` / `InpEntriesAfterSessionEnd` | (EA only) | true / false | Switches, §8 |
| `InpRiskPct` | (simulator) | 0.20 | Total risk per setup, % of equity, split over the enabled levels |
| `InpSlippageTicks` | `slippage_ticks` | 1 | Used in the cost check and for sizing |
| `InpCommissionPerLotSide` | `commission_per_lot_side` | 3.50 | Account currency per lot per side (`UNVERIFIED`) |
| (engine) | `length`, `vis_boxes` | 5, 2 | LuxAlgo engine `len` / `visBxs` (unchanged) |
| (fixed) | `capacity` | 128 | Tracked setups |

The engine is the LuxAlgo engine of `LUXALGO_BPR_SPEC.md` in **Historical** mode, unchanged from v1 (spec v1 §2).

## 2. Notation

- Bars `u = 0, 1, …` are closed bars, using bid prices `o, h, l, c`. A decision at the close of `u` executes from the
  first tick of `u+1`.
- `sp` is the spread at the decision moment (`env.sp`). `tick` is the symbol tick. `RoundTick(x)` is
  `NormalizeDouble(MathRound(x / tick) * tick, digits)`.
- Each setup has a direction `d = +1` (long) or `d = −1` (short). With `d`, the definitions are:

| Term | `d = +1` | `d = −1` |
|---|---|---|
| zone | drawn BPR box `[B, T]` (LuxAlgo `box.bottom` / `box.top`) | same |
| `touch(u)` | `l[u] ≤ T` | `h[u] ≥ B` |
| `broken(u)` (LuxAlgo break rule) | `l[u] < B` | `h[u] > T` |
| `beyond(u)` (close beyond the level) | `c[u] > lvl` | `c[u] < lvl` |
| level of the reference candle `r` | `lvl = h[r]` | `lvl = l[r]` |
| `Track(u)`: origin `O` and extreme `X` | if `l[u] < O`: `O = l[u]`, `X = h[u]`; else `X = max(X, h[u])` | if `h[u] > O`: `O = h[u]`, `X = l[u]`; else `X = min(X, l[u])` |
| `newExt(u)` | `h[u] > X` | `l[u] < X` |
| `originBroken(u)` | `l[u] < O` | `h[u] > O` |
| `fvgBar[d]` (last FVG bar in direction `d`) | bullish FVG event | bearish FVG event |

**FVG events** (`fvgBar`), updated on every bar before the setups are processed:
- `LUXALGO`: a new or updated FVG of that side in the engine on bar `u`. The engine flags are `newFvgUp | updFvgUp`
  and `newFvgDn | updFvgDn`.
- `ANY_GAP`: `l[u] > h[u-2]` (bullish) or `h[u] < l[u-2]` (bearish), for `u ≥ 2`.
- `NONE`: the condition is always true.

## 3. Setup creation

On bar `u`, the detector reads each new BPR the engine reports: the `BPR_UP` array first, then `BPR_DN`. The same
guards as v1 apply: both newest FVGs exist, and the BPR box exists with `pos ∈ {+1, −1}`.

1. **Direction and filter.** `d = pos`. A BPR removed by the direction filter is never logged and gets no id.
2. **Zone.** `B = box.bottom`, `T = box.top`: the box the chart shows.
3. **Checks at creation**, in this order. The first that fails ends the setup as `DONE(reason)` on bar `u`:
   1. `T ≤ B` → `BAD_GEOMETRY`;
   2. the box is not active after this bar's break loop → `BROKEN_AT_CREATION`;
   3. 128 setups are already tracked → `CAPACITY`.
4. **Otherwise** the setup is created with record `ARMED`, phase `WAIT`, `touches = 0`, `inEp = false`.

A setup is never processed on its creation bar. Its first touch can come at `u + 1` at the earliest.

## 4. Per-bar algorithm (closed bar `u`)

The steps run in this order:
1. engine `ProcessBar(u)`;
2. update `fvgBar`;
3. **existing setups**, in creation order (§4.1–§4.4);
4. **new setups** (§3);
5. **decisions** (§5).

A setup stops being tracked when it reaches `DONE` or `CLOSED`.

### 4.1 Phases `WAIT`, `ZONE`, `BREAK` (before confirmation)

1. `broken(u)` → `DONE(BROKEN)`.
2. `u − created > setup_expiry_bars` → `DONE(EXPIRED)`.
3. `tn = touch(u)`.
4. **Phase `BREAK`** (breakout candle seen, `nClose` closes so far):
   - **If `beyond(u)`:** `nClose += 1` and `Track(u)`. Once `nClose ≥ confirm_closes`:
     - the phase becomes `LEG`, with `confirmBar = u`;
     - record `CONFIRM`;
     - `inEp = tn`, and processing of this setup ends for this bar.

     If `nClose` is still short, set `inEp = tn` and end processing here too.
   - **Otherwise:** record `BREAK_FAIL`. The phase becomes `ZONE`, `nClose = 0`, and processing continues at step 6.
5. **Phase `ZONE`** (at least one touch) with `beyond(u)`, `!tn` (the candle does not touch the zone) and, with
   `reject_before_break`, `!inEp` (the previous candle did not touch either):
   - the phase becomes `BREAK`, with `brkBar = u`, `nClose = 1`, `Track(u)`;
   - record `BREAKOUT`.

   If `confirm_closes = 1`, confirm at once, as in step 4. Then set `inEp = tn` and end processing for this bar.
6. **Touch logic.**
   - **If `tn`:**
     - if `!inEp` (a new touch): `touches += 1`.
       - If `touches > max_touches` → `DONE(TOUCH_LIMIT)`; stop.
       - Otherwise record `TOUCH(k = touches)`, set `O = l[u]` and `X = h[u]` (long; short: `O = h[u]`,
         `X = l[u]`).
     - if `inEp`: `Track(u)`.
     - In both cases: `ref = u`, `lvl` = level of candle `u`, phase `ZONE`, `inEp = true`.
   - **If `!tn`:**
     - if `inEp`: record `REJECT`, and set `inEp = false`;
     - then, if the phase is `ZONE`: `Track(u)`.

### 4.2 Phase `LEG` (confirmed, no order)

These rules apply from `confirmBar + 1` onwards. `ready` is reset to false at the start of every bar.

1. `originBroken(u)` → `DONE(LEG_BROKEN)`.
2. `u − confirmBar > leg_expiry_bars` → `DONE(EXPIRED)`.
3. If `newExt(u)`, update `X` (long: `X = h[u]`; short: `X = l[u]`).

   Otherwise this is a pullback bar. Set `ready = (fvgBar[d] > ref)`, or always true with `fvg_rule = NONE`.

   A pullback bar without an FVG counts in the diagnostics (`noFvg`); the setup keeps waiting.

### 4.3 Phase `ORDERED` (at least one level pending, none filled)

1. **`newExt(u)` → re-anchor.**
   - every pending level is cancelled, with a `CANCEL(k, NEW_EXTREME)` record and a cancel intent;
   - all levels go back to `NONE`, `X` is updated, and the phase becomes `LEG`;
   - `ready = false` for this bar.
2. **`originBroken(u)`** → every pending level is cancelled (`CANCEL(k, LEG_BROKEN)`), then `DONE(LEG_BROKEN)`.
3. **`u − confirmBar > leg_expiry_bars`** → every pending level is cancelled (`CANCEL(k, EXPIRED)`), then
   `DONE(EXPIRED)`.
4. **Session end** (`use_session && env.sessionCancel`) → every pending level is cancelled
   (`CANCEL(k, SESSION_END)`), then `DONE(SESSION_END)`.

### 4.4 Phase `FILLED` (at least one level filled)

These rules apply only while a level is still pending:
1. long `h[u] ≥ tgt`, short `l[u] ≤ tgt` (target touched), **or** `newExt(u)` → cancel the pending levels
   (`CANCEL(k, TARGET)`);
2. `u − confirmBar > leg_expiry_bars` → cancel the pending levels (`CANCEL(k, EXPIRED)`);
3. session end → cancel the pending levels (`CANCEL(k, SESSION_END)`).

The setup becomes `CLOSED` (record `CLOSED`) once no level is pending and no level's position is open. That
happens through `NotifyClosed`, or through step 1–3 when the filled positions have already closed.

## 5. Decisions (step 5)

**When.** A decision needs all of `env.slotFree`, (`use_session` → `env.sessionEntryOk`), `env.riskOk` and
`env.spreadOk`, on bars `u ≥ trade_from`. If any is false, no setup decides on this bar. The ready setups count in
the `blocked*` diagnostics and try again on the next bar.

**Which setup.** Setups in phase `LEG` with `ready = true`, in creation order. The first that places at least one
level ends step 5: one setup per bar. A setup that places nothing ends `DONE(NO_LEVEL)`, and the next one is tried.

**Prices.** For one setup:
- `L = d·(X − O)`. If `L ≤ 0` → `DONE(BAD_GEOMETRY)`.
- `F(f) = X − d·(f/100)·L` is the bid price at retracement `f` %. 0 % is `X`; 100 % is `O`.
- Stop: `SL = F(stop_fib) − d·stop_buffer_ticks·tick`, plus `sp` for a short (an ask level).
- Target: `tgt = F(target_fib)` (bid level). `TP = tgt`, plus `sp` for a short (an ask level).
- Entry of level `k` (enabled when `f_k > 0`): `P_k = F(f_k)`, plus `sp` for a long. A buy limit is an ask level:
  it fills when the bid touches `F(f_k)`.

**Checks per level**, in this order, on the unrounded values. A failed check is recorded as `SKIP(k, reason)`:
1. `d·(P_k − SL) ≤ 0` or `d·(TP − P_k) ≤ 0` → `BAD_LEVEL`;
2. already passed: long `c[u] + sp ≤ P_k`; short `c[u] ≥ P_k` → `MISSED`;
3. `min_rr > 0` and `|TP − P_k| / |P_k − SL| < min_rr` → `RR`;
4. `max_cost_r > 0` and `(sp + comm_price + 2·slippage_ticks·tick) / |P_k − SL| > max_cost_r` → `COST`;
5. otherwise **place** `P_k`, `SL` and `TP`, all rounded with `RoundTick`. `tgt` is rounded too.

**Result.** Records are emitted in level order: `PLACE_LIMIT(k)` with an intent, or `SKIP(k, reason)`. With at least
one placed level, the phase becomes `ORDERED` and `decisionBar = u`. With none, the result is `DONE(NO_LEVEL)`.

## 6. Executor feedback

| Call | When | Effect |
|---|---|---|
| `NotifyFilled(id, k)` | A level's order became a position | The level becomes `FILLED`; an `ORDERED` setup becomes `FILLED`. |
| `NotifyClosed(id, k)` | That position closed | The level becomes `CLOSED`. With nothing pending and nothing open, the setup becomes `CLOSED`. |
| `NotifyCancelled(id, k, reason)` | The broker refused or removed a pending level | Record `DROP(k, reason)`. With nothing pending and nothing open, the setup becomes `CLOSED` if any level filled, otherwise `DONE(reason)`. |
| `NotifyRetry(id)` | **No order of the decision was sent**, for a transient reason: slot busy, breaker, risk baseline not ready, no tick, algo trading off, daily-loss budget | Every pending level goes back to `NONE`, and the phase becomes `LEG`. No record. |

A fill on a level the detector has already cancelled cannot be passed back: the executor manages that position on
its own. It still gets the time stop, the 16:44 New York flat and its server SL / TP.

## 7. Event records (parity)

Each record has these fields:

| Field | Content |
|---|---|
| `n` | Bar index |
| `id` | Setup id |
| `ev` | Record type (list below) |
| `dir` | Direction |
| `k` | Touch number for `TOUCH`; level 1..3 for level records; 0 otherwise |
| `reason` | Reason, if any |
| `P`, `SL`, `TP` | `PLACE_LIMIT` only |
| `O`, `X` | `CONFIRM` and `PLACE_LIMIT` only |

Record types: `ARMED`, `TOUCH`, `REJECT`, `BREAKOUT`, `BREAK_FAIL`, `CONFIRM`, `PLACE_LIMIT`, `SKIP`, `CANCEL`,
`DROP`, `CLOSED` and `DONE`.

Reasons: `BAD_GEOMETRY`, `BROKEN_AT_CREATION`, `CAPACITY`, `WARMUP`, `BROKEN`, `EXPIRED`, `TOUCH_LIMIT`,
`LEG_BROKEN`, `NEW_EXTREME`, `TARGET`, `SESSION_END`, `NO_LEVEL`, `MISSED`, `RR`, `COST`, `BAD_LEVEL`,
`SIZE_BELOW_MIN` and `ORDER_FAILED`.

Records made by a `Notify*` call carry `n` = the last processed bar.

**Warm-up.** Setups created on bars `< trade_from` become `DONE(WARMUP)` when the first bar `≥ trade_from` is
processed, before anything else on that bar. `n` is the last warm-up bar. No decision happens on warm-up bars.

### Parity harness

Python `harness_run` and the C++ driver `tools/mql5_cpp_harness/bk_main.cpp` use the same simple executor. On each
bar `u`, **before** the detector runs:
1. **Exits** of positions filled on a bar `< u`:
   - long: `l[u] ≤ SL` (stop first), else `h[u] ≥ TP`, else `u − fillBar ≥ hold_bars`;
   - short: `h[u] + sp ≥ SL`, else `l[u] + sp ≤ TP`, else time.

   Each exit calls `NotifyClosed`.
2. **Fills** of levels decided on a bar `< u`: long `l[u] + sp ≤ P`; short `h[u] ≥ P`. Each fill calls
   `NotifyFilled` and is checked for exits from the next bar.

The environment is fixed: `slotFree` is true while no setup is `ORDERED` or `FILLED`; session and risk are always
OK; the spread is a constant `sp`. Cancel intents remove the level at once.

## 8. Executor (EA)

- **Account guard.** Unchanged from v1: orders go out in the Strategy Tester and on DEMO accounts only. A REAL
  account is log-only. The guard fails closed.
- **One setup at a time.** One setup holds orders or positions at a time, with up to 3 limit orders. Each filled
  level is its own position on a hedging account. On a netting account the fills merge into one position, so
  `NotifyClosed` is sent for every level that shares the position.
- **Placement of one decision (the batch of `PLACE_LIMIT` intents).**
  1. **Global checks first:**
     - account permitted;
     - algo trading allowed (terminal and program);
     - order breaker not tripped;
     - risk baseline ready;
     - a tick available;
     - no other order or position of the EA.

     If any fails, nothing is sent and the executor calls `NotifyRetry`.
  2. **Per level:**
     - **Size:** `lots = floor(equity·risk%/n_enabled / (LossPerLot(|P−SL| + slippage) + 2·commission) / step)
       · step`. It is never rounded up to the minimum volume. If it falls below the minimum →
       `NotifyCancelled(SIZE_BELOW_MIN)`.
     - **Live tick at or through `P`:** sent as a market order with the same SL / TP (a better price than planned).
     - **Limit inside the stops level, or SL / TP invalid:** `NotifyCancelled(ORDER_FAILED)`.
  3. **Daily budget.** Realised loss today plus the total planned risk of the batch must be ≤ the daily limit.
     Otherwise → `NotifyRetry`.
- **Limit orders.**
  - Sent through `CTrade`, whose `FillingCheck` sets the symbol's mode (FOK / IOC on market-execution symbols, also for
    pending orders). On `INVALID_FILL` the order is sent again by a raw `OrderSend` with `ORDER_FILLING_RETURN`. The
    filling actually sent is shown on the panel.
  - A server-side expiration (`ORDER_TIME_SPECIFIED`, `leg_expiry_bars + 3` bars) is used when the symbol allows it.
    On `INVALID_EXPIRATION` the order is sent again as GTC.
  - The detector cancels orders through its own intents.
- **Order-error breaker.**
  - A decision whose sends were **all** refused for a non-transient reason is one strike. Three strikes trip the
    breaker.
  - Transient or permission retcodes never count: requote, timeout, price changed, connection, too many requests,
    locked, frozen, algo trading off, market closed.
  - It resets after 30 minutes, or at the next FX day.
  - While it is tripped, decisions call `NotifyRetry` with the reason; it is not folded into `riskOk`.
- **Rollover window** 16:44–17:00 New York, whatever `use_session` is set to: no decision is sent (`NotifyRetry`), and
  pending orders are deleted (`SESSION_END`).
- **Account not confirmed yet** (terminal reconnecting): `NotifyRetry`. Only a REAL account is log-only.
- **Daily loss** counts every deal of the EA's positions, whatever its magic, so manual closes count too.
- **Removal.** When the EA is removed, or its chart or the terminal is closed, its positions are closed: nothing would
  run their time stop any more. A recompile or an input change keeps them, and the restarted EA adopts them.
- **EA-only switches (v3, owner request 2026-10-10).** These are not part of H-14's default rules, and the Python
  reference has no counterpart for them:
  - `InpUseCostFilter = false`: the executor passes `max_cost_r = 0` (off) to the detector.
  - `InpUseRRFilter = false`: the executor passes `min_rr = 0` (off).
  - `InpEntriesAfterSessionEnd = true`: `env.sessionEntryOk` also covers 14:45–16:44 New York, Mon–Fri, so the entry
    window ends at 16:44.
  - `InpCancelAtSessionEnd = false`: `env.sessionCancel` no longer fires when the entry window ends. It fires only at
    the **rollover cut**: the next bar opens at or after 16:44 New York, on a weekend, or in another FX day than the
    bar that closed (a data gap). The cut acts on the first tick after the gap, so a fill on that tick is not
    prevented by it; the server-side expiry below covers that case.
  - With `InpCancelAtSessionEnd = true`, `env.sessionCancel = !env.sessionEntryOk`, which is v2's `SessionCancel`
    with the defaults. With the extended window it also fires on a new FX day after a data gap.
  - **Every limit order's server-side expiry is capped at the next 16:44 New York** (all settings). The broker removes
    the order even without a tick. The cap is GTC only when the symbol refuses expiry times. No new order is sent in
    the last 2 minutes before 16:44.

  The detector applies both session signals only with `use_session = true`. The executor's 16:44–17:00 rules (no new
  order; pending orders deleted on a tick in that window) still apply whatever the switches are.

  The first two equal `max_cost_r = 0` / `min_rr = 0` in the reference. Any backtest that uses a switch is a new
  trial.
- **Positions.** Each one has:
  - its server SL / TP;
  - a time stop `fill_time + max_hold_min` (at most 120 min);
  - a flat at 16:44 New York;
  - for a market fill only, an excess-risk trim, as in v1.

  There is no partial TP and no break-even: the owner's rule has a single target.
- **Diagnostics** (panel and Experts log):
  - the number of setups per phase;
  - counts of every `DONE` / `SKIP` reason;
  - ready setups blocked by the slot, session, risk or spread;
  - pullbacks without an FVG;
  - orders sent, failed and retried, with the last broker retcode;
  - the algo-trading state.

  A startup self-check prints:
  - the account mode;
  - algo-trading permissions;
  - hedging or netting;
  - filling and expiration modes;
  - stops and freeze levels;
  - tick size and value;
  - volume limits;
  - the risk budget per level;
  - today's entry window in server time.
- **Drawing**, per setup:
  - touch marks `T1` / `T2`;
  - the breakout level from the reference candle to the breakout;
  - `B1` / `B2` marks on the breakout and confirmation candles;
  - the Fibonacci lines 0 / 50 / 61.8 / 71 / 100 % from the leg origin to the extreme, redrawn when the leg is
    re-anchored;
  - the entry, SL and TP lines of the placed levels.

## 9. What is NOT claimed

- That these rules are profitable. H-14 is untested. A pre-registered backtest (EXP011) is the next research step.
- That the EA compiles. It was written without MetaEditor.
- That the default inputs are good. They were chosen from the owner's words and common usage, not from data.
