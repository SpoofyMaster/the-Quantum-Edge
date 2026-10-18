# BprFvgEA v9: BPR rejection → breakout → Fibonacci pullback (+ reversal setup, touch entry)

**Status:** hypothesis **H-14**. `HYPOTHESIS`: it has not been tested. Nothing here is evidence of an edge.

**Origin:** the rules come from the project owner's message of 2026-10-09 (quoted in §0). The defaults were fixed
from that message **before any data was looked at**.

**Implementations.** This file is the single source of truth for:
- the MQL5 EA `mql5/BprFvgEA/` (version 9.01; v3 = v2 plus the EA-only switches of §8; v4 = v3 plus the EA-only exit switches of §8; v5 = v4 plus the MQL5-only entry switches of §4.2–§5 and §8; v6 = v5 plus the MQL5-only reversal setup and touch entry of §4.5, §5 and §8; v7 = v6 with the reversal rules of the owner's example of 2026-10-15, §4.5; v8 = 7.01 plus tracking every BPR until its first touch and quick reversal limits, §3, §4.1, §4.5, §7; v9 = v8 plus the reversal's rejection candles of the owner's rule of 2026-10-17, §4.5; 9.01 = `InpCancelAtSessionEnd = false` keeps the pending orders, §8): pure detector `include/BfDetector.mqh`, executor `BprFvgEA.mq5`;
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

**The reversal setup (v6 request 2026-10-12, v7 example 2026-10-15; MQL5 only, hypothesis H-15).** Owner, 2026-10-15,
with a screenshot of the v2 example chart and the reversal drawn on it: *"the example of the second type of BPR
Creation, aftert that t1 + rejection from it and pullback with breakout of T1 or T2 wick with closing below or above
it. entry on Fib levels 50, 61 and 71"*. The drawing: a line at the **T1 wick**; the drop from the top of the move;
"First closing below T1 wick" and "Second closing below T1 wick"; "100% SL" at the top and "0% TP" at the low. §4.5
gives the rules.

## 1. Inputs (EA) / `BreakoutParams` (Python)

| EA input | Python field | Default | Meaning |
|---|---|---|---|
| `InpDirection` | `direction` | `BOTH` | `BOTH` / `LONG_ONLY` / `SHORT_ONLY` |
| `InpMaxTouches` | `max_touches` | 2 | Touches allowed (1..5); one more ends the setup |
| `InpConfirmCloses` | `confirm_closes` | 2 | Consecutive closes beyond the level, breakout candle included (1..5) |
| `InpRejectBeforeBreak` | `reject_before_break` | false | The breakout candle must come after a rejection candle (it cannot be the first candle out of the zone) |
| `InpFvgRule` | `fvg_rule` | `LUXALGO` | `LUXALGO` / `ANY_GAP` / `NONE` (`NONE` drops the FVG condition) |
| `InpSetupExpiryBars` | `setup_expiry_bars` | 240 | Bars after the BPR's creation to reach confirmation (v8 EA default: counted only while price is at the BPR, §4.1) |
| `InpLegExpiryBars` | `leg_expiry_bars` | 60 | Bars after confirmation during which orders may be placed or filled |
| `InpAnticipateEntries` | (MQL5 only: `anticipate`) | false (EA: true since v8) | v5: decide without a pullback candle (§4.2–§5 notes) |
| `InpLegBreakOnClose` | (MQL5 only: `legBreakOnClose`) | false | v5: `originBroken` uses the close (§4.2 note) |
| `InpSetupType` | (MQL5 only: `setupType`) | CONTINUATION | v6: CONTINUATION / REVERSAL / BOTH (§4.5; v7: BOTH = two setups per BPR) |
| `InpRevLevel` | (MQL5 only: `revLevel`) | DEEPEST | v7: reversal level = DEEPEST wick of the T1 / T2 candles / T1 wick / LAST touch wick (§4.5) |
| `InpRevNeedRejection` | (MQL5 only: `revNeedReject`) | true | v7: a rejection after T1 before the reversal breakout (§4.5) |
| `InpMaxBarsToT1` | (MQL5 only: `t1WaitBars`) | −1 (EA: 0) | v8: bars from the BPR's creation to T1, 0 = no limit, −1 = v7 rules (§3, §4.1, §4.5, §7) |
| `InpRevNeedFvg` | (MQL5 only: `revNeedFvg`) | true (EA: false) | v8: the reversal waits for its FVG (§4.5) |
| `InpRevRejCandles` | (MQL5 only: `revRejCandles`) | 0 (EA: 2) | v9: rejection candles needed before the reversal breakout (§4.5) |

The research defaults (this table's second-to-last column, the detector's `BfDefaultParams`, the parity set) keep the
v7 rules; the EA's inputs default to the v8 behaviour where marked "EA:".
| `InpTouchEntry` / `InpTouchTargetRR` | (MQL5 only: `touchEntry` / `touchTargetRR`) | false / 1.5 | v6: market entry after T1 (§5 touch entry) |
| `InpFib1` / `2` / `3` | `fib_levels` | 50.0 / 61.8 / 71.0 | Entry retracements, % of the leg (0 = off) |
| `InpStopFib` | `stop_fib` | 100.0 | Stop at this retracement, % (100 = the leg origin) |
| `InpStopBufferTicks` | `stop_buffer_ticks` | 10 | Extra ticks beyond the stop level |
| `InpTargetFib` | `target_fib` | 0.0 | Take-profit retracement, % (0 = the leg extreme, < 0 = extension) |
| `InpMinRR` | `min_rr` | 0.0 | Minimum reward:risk per level (0 = off) |
| `InpMaxCostR` | `max_cost_r` | 0.30 | Maximum round-trip cost per level, as a fraction of its risk (0 = off) |
| `InpMaxHoldMin` | `max_hold_min` | 120 | Time stop per position, minutes (hard cap 120) |
| `InpUseTimeStop` / `InpFlatBeforeRollover` | (EA only) | true / true | Exit switches (v4), §8. Off = not a research trial. |
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
   v6: `zdir = d` (the BPR's direction; `dir` is the trade direction, `−zdir` after a reversal breakout).
   v7: each setup has a **kind**. CONTINUATION creates a continuation setup if `allowed(d)`. REVERSAL creates a
   reversal setup if `allowed(−d) || (touchEntry && allowed(d))`. BOTH creates both, the continuation one first, each
   with its own id and records (continuation: `allowed(d)`; reversal: `allowed(−d)`). With CONTINUATION this is v5.
2. **Zone.** `B = box.bottom`, `T = box.top`: the box the chart shows.
3. **Checks at creation**, in this order. The first that fails ends the setup as `DONE(reason)` on bar `u`:
   1. `T ≤ B` → `BAD_GEOMETRY`;
   2. the box is not active after this bar's break loop → `BROKEN_AT_CREATION`;
   3. 128 setups are already tracked → `CAPACITY`. v8 (`t1WaitBars ≥ 0`): first the setup **idle the longest**
      (created before `u`) ends `DONE(CAPACITY)` and makes room; only if there is none is the new setup refused.
      Idle: phase `WAIT` (since `created`), or phase `ZONE` with `inEp = false` (away from the zone after a
      rejection; since the latest of `created`, the last visit's first bar and the last `REJECT`). A setup in a visit,
      in `BREAK` or confirmed is never dropped. Ties: the earliest in creation order.
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
2. `u − created > setup_expiry_bars` → `DONE(EXPIRED)`. v7.01: a reversal setup counts from its last `REJECT` when
   that is later. v8 (`t1WaitBars ≥ 0`), the clock runs only while price is at the zone:
   - before T1 (`touches = 0`) only `t1WaitBars` applies (`u − created > t1WaitBars`, 0 = never);
   - phase `ZONE` with `inEp = false` (away after a rejection): never (the setup waits for a late T2, a pullback visit
     or a late breakout);
   - otherwise `u − from > setup_expiry_bars`, where `from` is the latest of T1, the first bar of the last visit
     (`lastVisit`: T1, T2, a pullback visit, or a reversal breakout candle that opens a visit) and, in `BREAK`, the
     breakout candle `brkBar`.
   A rejection always comes before the next visit or breakout, so it is never later than `from`.
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

**v5 notes (MQL5 detector only; both off = the rules above):**
- **`legBreakOnClose`:** `originBroken(u)` is long `c[u] < O`, short `c[u] > O`, instead of the low / high. This also
  applies in §4.3.
- **`anticipate`:** every bar of this phase is a decision bar. After steps 1–2, a new extreme updates `X` and the bar
  is **not** skipped: `ready = (fvgBar[d] > ref)` (or true with `NONE`) on new-extreme and pullback bars alike. A bar
  without an FVG counts in `noFvg`. The confirmation bar is a decision bar too: in §4.1 steps 4 and 5, right after
  `CONFIRM`, `ready` is set with the same FVG condition.

### 4.3 Phase `ORDERED` (at least one level pending, none filled)

1. **`newExt(u)` → re-anchor** (9.01: not when `env.keepOrders`, §8: the levels stay pending where they are and steps
   2-4 follow).
   - every pending level is cancelled, with a `CANCEL(k, NEW_EXTREME)` record and a cancel intent;
   - all levels go back to `NONE`, `X` is updated, and the phase becomes `LEG`;
   - `ready = false` for this bar. v5 `anticipate`: `ready` is set with the FVG condition instead, so the setup decides
     again **on this bar** at the new extreme (see §5, slot owner). This happens only while
     `u − confirmBar ≤ leg_expiry_bars`, and not when `use_session && env.sessionCancel`. Otherwise it stays
     `ready = false`. After the expiry, the next `LEG` bar ends the setup (`EXPIRED`). After a session-cancel bar it
     stays in `LEG` and decides again on a later bar inside the entry window, as v4 does after a re-anchor.
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

### 4.5 Reversal setup (v6, rules of v7; `setupType` REVERSAL or BOTH; MQL5 detector only)

Before the confirmation, every zone test of §4.1 uses `zdir` (the BPR's direction): `broken`, `touch`, the touch
anchors and `lvl`. In v1–v5 `dir == zdir` there.

**v7: one kind per setup.** A continuation setup runs §4.1–§4.4 exactly as in v5 (steps 5b and the rules below do not
apply to it). A reversal setup runs the rules below and never step 5. With BOTH a BPR has one setup of each kind, each
with its own phases, records and decisions (one decision per bar and one setup with orders or positions at a time, §5,
as for any two setups). v6 had one setup for both kinds, where the first confirmation decided; v7 replaced it because
in the owner's example the reversal follows a continuation that already traded.

A reversal setup has this state (bullish BPR; a bearish BPR is the mirror image: highs ↔ lows):
- **Touches.** T1 and T2 as in §4.1 (`max_touches`). **v7:** for a reversal setup, a new visit of the zone (a touching
  candle with `inEp = false`) when `touches ≥ max_touches` is the **pullback**: it is not counted, records nothing,
  does not end the setup (`TOUCH_LIMIT` is a continuation rule) and does not move the level.
- **The reversal level `lvlR`** (input `revLevel`), set at each counted touch with `w = l[u]`, the touch candle's wick:
  - `DEEPEST` (default): T1 sets `lvlR = w`. A later touch stores `w` as a candidate. When that visit ends with a
    `REJECT`, the candidate becomes the level if `w < lvlR` (strictly deeper). So the level is the deepest wick of T1
    and of the rejected T2, the T1 wick in the owner's example. A T2 visit that turns straight into the breakdown
    keeps the earlier level (7.01; v7.00 took it at once).
  - `T1`: only T1 sets it.
  - `LAST` (v6): every counted touch sets it.

  `lvlRBar` is the bar of the candle whose wick it is (records, CSV, the chart's breakout line).
- **The rejection flag `rej`** (v7): set at the first `REJECT` record (a touch episode ending with a candle that does
  not touch the zone). It stays set.
- **v8 one-candle rejection** (`t1WaitBars ≥ 0`; reversal setups only): inside a visit (`inEp`), a candle
  that touches the zone but **closes beyond its far edge** (`c[u] > T` for a bullish BPR, `c[u] < B` for a bearish
  one) is taken as not touching: it records `REJECT` with all its effects (`rej`, `lastRej`, the level candidate, the
  leg candidate). A close exactly at the edge is not enough. This is the owner's "bullish reaction" off T1 in one
  candle: before v8, a candle opening inside the zone belonged to the visit, and a re-entry on the next candle kept the
  setup unrejected. A continuation setup keeps the §4.1 rule.
- **v9 rejection candles `nRejC`** (`revRejCandles > 0`; reversal setups only). The owner's rule: "after T1 price must
  absolutely make a rejection which a minimum 2 candles successive or not ... before price comes back for breakout",
  "2 Green candles for a bullish rejection and 2 RED candles for a bearish rejection".
  1. **Count** (before step 4). On a bar `u` after the T1 candle (`touches > 0`, `u > touchBar1`) that does not start
     in `BREAK`: if the candle is in the BPR's direction (`c[u] > o[u]` for a bullish BPR, `c[u] < o[u]` for a bearish
     one) and its close is not beyond `lvlR` (`!BeyondRev(u)`): `nRejC += 1`.
  2. **Too early** (after step 5b, so only when this bar is not the reversal breakout). If the bar started in `ZONE`
     with `touches > 0` and `BeyondRev(u)`: `early`, and `nRejC = 0`. In step 6 a new visit opened by an `early`
     candle (`inEp` false) is a pullback visit, not a touch: it is not counted as T2, `TOUCH_LIMIT` does not apply and
     its wick is no level candidate (`DEEPEST` / `LAST` keep the level).
  3. **A breakout in progress** (`BREAK`) neither counts nor restarts: after a `BREAK_FAIL` the count is the one the
     breakout used, and the next close beyond the level is a breakout again.

  So the reversal breakout needs `revRejCandles` rejection candles after T1 and after the last close beyond the level
  that was not a breakout. A rejection candle never closes beyond the level, so it is never a breakout candle itself.
  A doji and the T1 candle do not count. Every record carries the setup's `nRejC` after its bar (`rejC`; the harness
  prints it as `rc` with `ext=1`). On a `BREAKOUT` it is the count the breakout used.
- **The reversal leg `rO` / `rX`** (100 % / 0 %): `TrackRev(u)` runs on every pre-confirmation bar from T1 on: if
  `h[u] > rO`, then `rO = h[u]` and `rX = l[u]`; otherwise if `l[u] < rX`, then `rX = l[u]`.
  - T1 starts it: `rO = h[u]`, `rX = l[u]`. This only matters while no visit has been rejected
    (`revNeedReject = false`).
  - **Candidate.** Every visit of the zone (7.01: T1 included) starts a candidate. This covers T1, T2, a pullback
    visit, and a visit opened by a reversal breakout candle that enters the zone (7.01). The candidate measures the
    **bounce after the visit's lowest low** `cL` (bullish BPR):
    - at the start, `cL = cO = cX = l[u]`;
    - on each later bar, if `l[u] < cL` then `cL = cO = cX = l[u]` (the bounce restarts after a new low, and the high
      of the bar that made the low is not used);
    - otherwise if `h[u] > cO` then `cO = h[u]` and `cX = l[u]`;
    - otherwise if `l[u] < cX` then `cX = l[u]`.
  - **When the visit ends with a `REJECT`**, the candidate becomes the leg (`rO = cO`, `rX = cX`). The 100 % is the
    top of the last bounce from the zone. Because the REJECT bar is outside the zone, `cO` is always above `cL` there.
  - **A visit that turns into the breakout** without a rejection keeps the earlier `rO` / `rX`: the 100 % is the top
    of the move before it.
  - **History.** v7.00 seeded the candidate with the visit's first candle's high, which belongs to the descent; v6
    restarted the leg at every touch.
- **Broken BPR (step 1).** `broken(u)` does not end a reversal setup (it trades the break), unless `allowed(−zdir)`
  is false (a REVERSAL setup kept only for its touch entry): then `DONE(BROKEN)`. A continuation setup ends
  `DONE(BROKEN)` as in v5.
- **Reversal breakout (step 5b).**
  - **Condition.** Phase `ZONE` (not on the bar of a `BREAK_FAIL`), `allowed(−zdir)`, `nRejC ≥ revRejCandles` (v9), `rej || !revNeedReject` (v7,
    default on: "t1 + rejection from it and pullback"), and `BeyondRev(u)`: bullish BPR `c[u] < lvlR`, bearish
    `c[u] > lvlR`. The candle may touch or cross the zone; it is not a touch.
  - **Then.** The phase becomes `BREAK` with `rev = true` and `dir = −zdir`, and record `BREAKOUT`, whose `dir` is the
    trade direction and whose `lvl` / `lvlBar` are `lvlR` / `lvlRBar`.
  - **v8, `revNeedFvg = false`** (EA default): `FvgOk` is true for a reversal. With `anticipate` the confirmation bar
    is then a decision bar with no FVG wait: the limits go in on the confirming close, and are moved at every new
    extreme (§4.3 re-anchor).
  - **In `BREAK`.** `BeyondRev` is used in place of `beyond`. Once `nClose ≥ confirm_closes`, `O = rO` and
    `X = rX`, then `CONFIRM` as in §4.1.
  - **`BREAK_FAIL`.** Sets `rev = false` and `dir = zdir`, back to `ZONE`; then step 6 runs on that bar.
- **After the confirmation.** §4.2–§4.4 run unchanged with `dir = −zdir`:
  - leg tracking by `newExt`, the pullback;
  - the FVG of the trade direction after `max(ref, oBar)` (7.01: after the reversal's 100 % bar too, not a gap of
    the move before it);
  - the Fibonacci from `O` to `X` (entries 50 / 61.8 / 71 %), `originBroken` against `O`;
  - SL beyond `O` + buffer, TP at `X`, and the decisions.
- **Expiry.** `setup_expiry_bars` to the confirmation. 7.01: counted from the later of the BPR's creation and the
  setup's last `REJECT` (`lastRej`); a continuation setup counts from the creation as before.

## 5. Decisions (step 5)

**When.** A decision needs all of `env.slotFree`, (`use_session` → `env.sessionEntryOk`), `env.riskOk` and
`env.spreadOk`, on bars `u ≥ trade_from`. If any is false, no setup decides on this bar. The ready setups count in
the `blocked*` diagnostics and try again on the next bar.

**v5 slot owner (`anticipate`).** `env.slotOwner` is the id of the setup whose own pending limits are all that held
the slot when the bar closed. The executor sets it only when there is no position, no unowned position, no other
order, and no level being deleted or partly filled. When `env.slotFree` is false and that setup is ready (it
re-anchored on this bar), the slot condition counts as met **for that setup only**. The other conditions still apply.
It alone may decide; every other ready setup counts as `blocked slot`. Its cancel intents come before its new place
intents in the same bar, and the executor deletes the old limits before it sends the new ones.

**v5 early bars (`anticipate`).** The confirmation bar and new-extreme bars are decision bars only because of
`anticipate`. On such a bar (`u = confirmBar` or `u = xBar`), if no level can be placed, whatever the skip reasons
(`MISSED`, `COST`, `RR`, `BAD_LEVEL`), nothing is recorded and the setup stays in `LEG` instead of ending
`DONE(NO_LEVEL)`. So `anticipate` never ends a setup on a bar where v4 would not decide. An ordinary pullback bar keeps
the v4 rule.

**v6 touch entry (`touchEntry`).**
- **When it is ready.** At a **new touch with `touches == 1`** (T1), if that candle did not break the BPR and
  `allowed(zdir)`, the setup is `touchReady` for this bar only. v7: only the setup that owns the touch entry: the
  continuation setup (CONTINUATION / BOTH), or the reversal setup with REVERSAL. So a BPR sends at most one.
- **Step 5.** A `touchReady` setup is a candidate like a ready `LEG` setup: same gates, creation order, one decision
  per bar. It is never a slot owner: it needs `env.slotFree`.
- **The decision (bullish BPR).** `P = c[u] + sp` (estimate), `SL = B − stop_buffer_ticks·tick`,
  `risk = P − SL`, `TP = P + touchTargetRR·risk`. A bearish BPR: `P = c[u]`, `SL = T + buffer + sp`,
  `TP = P − touchTargetRR·risk`.
- **Skips.** `risk ≤ 0` → `SKIP(0, BAD_LEVEL)`; `min_rr > 0 && touchTargetRR < min_rr` → `SKIP(0, RR)`;
  `cost / risk > max_cost_r` → `SKIP(0, COST)`. A skip does not end the setup or step 5: the next candidate is tried.
- **Otherwise.** Record and intent `TOUCH_ENTRY` (level 0, with P / SL / TP).
- **After it.** The detector does not follow the touch entry; the setup goes on.
- **Slot owner.** A setup whose own touch position is all that holds the slot may still decide its limits
  (`env.slotOwner`, hedging accounts; the executor sets it).

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
its own. It still gets the time stop, the 16:44 New York flat (each while its v4 switch is on) and its server SL / TP.

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
v8 (`t1WaitBars ≥ 0`): a warm-up setup in `WAIT`, `ZONE` or `BREAK` (not confirmed) goes on; only the others end
`DONE(WARMUP)`. Every BPR is followed from its creation, also when it formed before the EA started.

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
- **Daily loss** counts every deal of the EA's positions, whatever its magic, so manual closes count too. It reads the
  last 4 days of history; v4: a deal of today whose position has no EA entry deal in that window (a position held for
  days with the exit switches off) is looked up by position, and counted when the EA opened it.
- **Removal.** When the EA is removed, or its chart or the terminal is closed, its positions are closed: nothing would
  run their time stop / 16:44 New York flat (whichever is on) any more. A recompile or an input change keeps them, and the restarted EA adopts them. v4: with
  both exit switches off, they are kept with their server SL / TP (the EA has no market exit to run).
- **EA-only switches (v3, owner request 2026-10-10).** These are not part of H-14's default rules, and the Python
  reference has no counterpart for them:
  - `InpUseCostFilter = false`: the executor passes `max_cost_r = 0` (off) to the detector.
  - `InpUseRRFilter = false`: the executor passes `min_rr = 0` (off).
  - `InpEntriesAfterSessionEnd = true`: `env.sessionEntryOk` also covers 14:45–16:44 New York, Mon–Fri, so the entry
    window ends at 16:44.
  - `InpCancelAtSessionEnd = false`: `env.sessionCancel` never fires (9.01; v3–v9 still fired it at the **rollover
    cut**: the next bar opening at or after 16:44 New York, on a weekend, or in another FX day after a data gap). The
    executor also sets `env.keepOrders` when no order can be sent (with `use_session`: outside the entry window; any
    setting: 16:44–17:00 New York or less than 2 minutes before 16:44) at this bar's decision, on the next bar (a move
    that has to wait or be retried) or now (a bar replayed after a gap). §4.3: in `ORDERED`, a new extreme then does
    not re-anchor; the pending levels stay where they are (a re-anchor would cancel them with no way to send them
    again). No rollover delete and no 16:44 expiry cap either (below); the leg-expiry server-side expiry gets 3 more
    days, so a weekend or a daily break cannot end the order before its bar-count leg expiry.
  - With `InpCancelAtSessionEnd = true`, `env.sessionCancel = !env.sessionEntryOk`, which is v2's `SessionCancel`
    with the defaults. With the extended window it also fires on a new FX day after a data gap.
  - **Every limit order's server-side expiry is capped at the next 16:44 New York** (9.01: only with
    `InpCancelAtSessionEnd = true`). The broker removes the order even without a tick. The cap is GTC only when the
    symbol refuses expiry times. No new order is sent in the last 2 minutes before 16:44.

  The detector applies both session signals only with `use_session = true`. The executor's 16:44–17:00 rules (no new
  order; pending orders deleted on a tick in that window) apply whatever the other switches are; 9.01: the delete
  only with `InpCancelAtSessionEnd = true`.

  The first two equal `max_cost_r = 0` / `min_rr = 0` in the reference. Any backtest that uses a switch is a new
  trial.
- **Positions.** Each one has:
  - its server SL / TP;
  - a time stop `fill_time + max_hold_min` (at most 120 min);
  - a flat at 16:44 New York;
  - for a market fill only, an excess-risk trim, as in v1.

  There is no partial TP and no break-even: the owner's rule has a single target.
- **v7 executor (owner's example 2026-10-15, MQL5 only).**
  - **Inputs.** `InpRevLevel` (`revLevel`) and `InpRevNeedRejection` (`revNeedReject`), §4.5.
  - **Logs.** A reversal setup's lines carry `REV` after its id (`#2 REV SHORT CONFIRM …`). The reversal breakout line
    names the level option and the touch candle (`lvlBar`).
  - **CSV.** The files are `BFEA7_*`, with the v6 columns. The setups `setup` column is the setup's kind (`CONT` / `REV`).
    With BOTH each BPR has two setups-CSV rows.
  - **Drawings.** Unchanged code. With BOTH, the two setups of a BPR draw the same zone and `T` labels.
  - **Nothing else changes.** The slot, risk shares and touch position are as in v6. With BOTH, the touch position
    belongs to the continuation setup, so the reversal setup waits for the slot while it is open.
  - **7.01 (review).**
    - The log and setups-CSV `dir` of a reversal setup is its trade direction (`−zdir`) from the start.
    - With BOTH + `InpTouchEntry`, a reversal setup's entries are sized with `LevelBudget(g_nLevels)` (`SharesOf`),
      since it can never send the touch entry.
    - DIAG labels the counts as setups with BOTH.
    - A finished setup whose BPR sibling is still tracked deletes its `ZONE` / `T*` objects instead of greying them.
- **v6 executor (owner request 2026-10-12, MQL5 only).**
  - **`ExecTouch`.** Sends the `TOUCH_ENTRY` intent as a market order now, at the ask (buy) or bid (sell).
    - **Gates.** The same as a batch: permission, an empty slot, the breaker, the rollover window, risk, tick,
      direction.
    - **SL.** The detector's.
    - **TP.** `entry ± InpTouchTargetRR × |entry − SL|`, from the live price.
    - **Size.** `LevelBudget(g_nShares)`, where `g_nShares` = Fibonacci entries + 1. The fib batches use the same
      share, so a setup's total stays ≤ 0.20 %. The daily-loss check runs.
    - **Not sent.** Logged; never retried.
  - **The touch position (`g_tp`).** One at a time, outside the setup context.
    - **Position id.** `DEAL_POSITION_ID`, else the order ticket: it always opens a new position.
    - **Order of management.** `ManageTouch` runs before `Reconcile`, so the position is never adopted as unowned.
    - **Fill check.** The first time the position is seen, its actual risk is checked against its share. The excess is
      closed (hedging; at least the minimum volume, as for a level), or the whole position (netting). The time stop and
      16:44 flat are checked first, so a refused close cannot hold them back.
    - **Exit reasons.** `TIME` / `ROLLOVER` / `RISK` go to the CSV.
    - **No overlap.** A new touch entry waits while the previous one is open or not yet recorded.
    - `ManageTouch` handles its time stop and 16:44 flat, as the v4 switches say.
    - `FinishTouch` writes a trades-CSV row with level `T`.
    - `IsTracked` includes it, so `Reconcile` does not adopt it.
  - **Slot rules.**
    - `SlotOwner()` returns that setup when its touch position (hedging) and / or its healthy pending limits
      (anticipate) are all that hold the slot.
    - `SlotFreeForDecision(id)` lets that setup's batch through.
    - An open touch position's planned risk counts in a batch's daily-loss check.
    - On netting accounts, the touch position blocks the slot.
- **Entry switches (v5, owner request 2026-10-11, MQL5 only).**
  - **What they change.** `InpAnticipateEntries` (`anticipate`) and `InpLegBreakOnClose` (`legBreakOnClose`) change
    the **detector** (§4.2, §4.3, §5 notes). The Python reference does not have them; both off = v4.
  - **Executor.**
    - `env.slotOwner` comes from `SlotOwner()`.
    - **Before a batch.** `DeletedOrdersProven()` requires the account history to show no filled volume for every
      pending order this EA deleted (server-confirmed) in the last minute, for any setup. A part filled just before a
      delete may not be in the position list yet.
      - Outside the tester, a history record not yet available is polled for up to about 0.5 s.
      - Otherwise `NotifyRetry`.
    - **The slot check.** `SlotFreeForDecision()` then treats those deleted orders as gone, even if the terminal
      still lists them.
    - `SlotOwner()` returns 0 while a tracked order is partly filled.
    - A failed delete, or an old order that filled first, keeps the slot busy. Nothing new is sent (`NotifyRetry`),
      so old and new limits of one setup can never both fill.
  - **Verification.** `tests/test_bpr_breakout_v5_switches.py` checks the rules on the C++ transliteration only.
  - **Research status.** Either switch is a rule change, so a backtest with it is a new hypothesis, not H-14.
- **EA-only exit switches (v4, owner request 2026-10-10).** The owner saw positions closed by `close at market: TIME`
  before they reached the final TP, and asked for an input:
  - `InpUseTimeStop = false`: no time stop. `InpMaxHoldMin` is then unused.
  - `InpFlatBeforeRollover = false`: no 16:44 New York flat. Positions may cross the 17:00 New York rollover and the
    weekend (swap; a gap can fill the stop beyond the planned 0.20 %).

  With only the flat off, the time stop can fall after 16:44 New York (in the rollover spread) or after the Friday
  close, when the close waits for the reopen.

  Both apply to the level positions, a partly filled order's position and the unowned (orphan) positions. Pending
  orders keep every v3 rule: no order lives past the next 16:44 New York. Both default to `true` (= v3).
  **Turning either off departs from the hard rule "every position closed ≤ 120 minutes after entry" (CLAUDE.md).** It
  is the owner's decision for the Strategy Tester / demo. Such a run is not a research trial of H-14 and cannot support
  any claim about it; the panel and the log mark it `NOT a research trial`. The detector and the Python reference are
  unchanged: they never close positions. The harness's bar-based exit (`hold_bars`) models the default exits only.
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
