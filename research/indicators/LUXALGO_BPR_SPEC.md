# Balance Price Range (BPR) in "ICT Concepts [LuxAlgo]": exact specification

Source: `research/indicators/luxalgo_ict_concepts.pine`. This is the unmodified Pine v5 script, © LuxAlgo, licensed
CC BY-NC-SA 4.0. Line numbers below refer to that file. The full list of inputs is in
[`ICT_CONCEPTS_PARAMETERS.md`](ICT_CONCEPTS_PARAMETERS.md).

This document is the single source of truth for the three ports:

| Port | File |
|---|---|
| Python reference | `qe/indicators/luxalgo_bpr.py` |
| MT5 indicator | `mql5/Indicators/LuxAlgo_BPR/LuxAlgo_BPR.mq5` |
| Browser replay engine | `tools/luxbpr_preview/engine.js` |

Every statement is read from the code. Where the code does something a trader might not expect, it is marked
**QUIRK**, and all three ports reproduce it on purpose.

Labels used here:

| Label | Meaning |
|---|---|
| `PUBLISHED` | Read from the Pine source; this is the default for unlabelled statements. |
| `HYPOTHESIS` | Depends on Pine runtime behaviour that the source alone does not show and that has not been checked on TradingView. Evidence is given where the script itself relies on it. |
| `VERIFIED` | Checked by a test in this repo; the test is named. |

**Revision 2 (2026-10-07).** An independent re-derivation from the Pine source found six problems in revision 1, which
this revision corrects:

- the old QUIRK 7 was wrong;
- the look-ahead of "Present" mode was not mentioned;
- the Fibonacci behaviour with BPR off was wrong;
- the IFVG wording was inaccurate;
- the consequences of QUIRKS 1–3 were missing;
- the Pine runtime assumptions were not labelled.

## 1. Inputs that affect the BPR

| Pine variable | Input title | Default | Range | Role |
|---|---|---|---|---|
| `i_mode` | Mode | `Present` | Present / Historical | `per = last_bar_index - bar_index <= 500` in Present mode, else always true. `per` gates **only the creation and update of FVGs** and the displacement plot. The BPR block and all break loops run on every bar. See §7 for the look-ahead this causes. |
| `len` | Market Structures → Length | 5 | 3–10 | Period of `meanBody = ta.sma(body, len)`. The same input also drives market structure, so changing it changes both. |
| `perc_Body` | constant | 0.36 | — | A displacement candle's wicks must each be shorter than this fraction of its body. |
| `bxBack` | constant | 10 | — | The break loops look at indices `0..min(10, size-1)` only (QUIRK 11). |
| `shwFVG` | Show FVGs | true | bool | With `false` no FVG is ever created, so **no BPR can exist**. |
| `i_BPR` | Balance Price Range | **false** | bool | Turns the BPR on. FVG boxes are then drawn with `na` colours (invisible) but are still computed and still drive the BPR. |
| `i_FVG` | Options | `FVG` | FVG / IFVG | Gap definition (§3). |
| `visBxs` | # Visible FVG's | 2 | 1–20 | Fixed length of each of the four arrays (FVG up, FVG down, BPR up, BPR down). |
| `cFVGbl` / `cFVGbr` | Bullish / Bearish FVG | #00e676 / #ff5252 | colour | Colour of BPR up / BPR down. Fill uses 90 transparency; border and text use 65. |
| `cFVGblBR` / `cFVGbrBR` | Break | #808000 / #FF0000 | colour | Fill of a broken BPR, at 95 transparency. |
| `iFib` / `iExt` | Fibonacci between last / Extend lines | NONE / false | — | With `BPR`, Fibonacci lines run between the latest BPR up and BPR down (§8). |
| `sDispl` | Show Displacement | false | bool | Marks displacement candles (§2). |

The script declares `max_boxes_count=500` and `max_bars_back=3000`.

## 2. Displacement candle (lines 127–130, 548–553, plot 1120–1134)

```
mx       = max(close, open)          mn = min(close, open)          body = |close - open|
meanBody = sma(body, len)            // includes the current bar; na for the first len-1 bars
L_body   = (high - mx < body*0.36) and (mn - low < body*0.36)        // both wicks < 36% of body (strict)
L_bodyUP = body > meanBody and L_body and close > open
L_bodyDN = body > meanBody and L_body and close < open
```

- **na and doji cases.** Comparisons with `na` are false, so `L_bodyUP` is false while `meanBody` is `na`. A doji
  (`body = 0`) never qualifies, because `0 < 0` is false.
- **The plot.** It marks the displacement bar **itself**, not the bar after it, and only when `sDispl and per`:
  - up: `shape.labelup`, `color.lime`, `location.belowbar`;
  - down: `shape.labeldown`, `color.red`, `location.abovebar`.
- **Forming bar.** On the forming bar the marker can appear and disappear, because `body` and `meanBody` use the
  current prices.

## 3. FVG detection (lines 565–566, box 611–643)

Bar `n` is the current bar, bar `n-1` the displacement candle, and bar `n-2` the candle before it.

```
FVG  mode: imbalanceUP = L_bodyUP[1] and low  > high[2]     imbalanceDN = L_bodyDN[1] and high < low[2]
IFVG mode: imbalanceUP = L_bodyUP[1] and low  < high[2]     imbalanceDN = L_bodyDN[1] and high > low[2]
```

- The comparisons are strict.
- **New box coordinates:**
  - Bullish: `left = n-2`, `right = n`, `[top, bottom] = FVG ? [low, high[2]] : [high[2], low]`.
  - Bearish: `[top, bottom] = FVG ? [low[2], high] : [high, low[2]]`.
- In IFVG mode the box is defined by that formula. It is not always the overlap of the two candles: if bar `n`
  lies entirely below bar `n-2`, the bullish IFVG box spans both bars and the space between them.
- **At most one FVG event per bar.** `imbalanceUP` needs `L_bodyUP[1]` (an up candle at `n-1`) and `imbalanceDN`
  needs `L_bodyDN[1]` (a down candle at `n-1`), so they cannot both be true on the same bar.

## 4. Per-bar execution order (the order matters)

On every bar `n`, after the series above:

1. **Initialisation**, on the first bar only (lines 598–604). Push `visBxs` empty entries
   `FVG(box=na, active=false, pos=na)` into `FVG_UP` and `FVG_DN`. Push them into `BPR_UP` and `BPR_DN` too, but only if
   `i_BPR` is on (otherwise those two arrays stay **empty**). Every later `unshift` is followed by a `pop` that deletes
   the oldest box, so the sizes never change.
2. **Bullish FVG** (lines 606–624), if `imbalanceUP and per and shwFVG`:
   - If `imbalanceUP[1]` (a consecutive imbalance), update the newest entry in place. `imbalanceUP[1]` is the raw
     series, not gated by `per` or `shwFVG`.
     - New coordinates: `left = n-2`, `top = low`, `right = n+8`, `bottom = high[2]`.
     - `active` is **not** touched.
   - Otherwise `unshift` a new entry with the §3 coordinates, `active = true`, `pos = na`, and `pop` the oldest.
   - **QUIRK 1.** The update always writes the FVG-mode geometry, even in IFVG mode.
     - **Consequence.** In IFVG mode the box becomes inverted (`top < bottom`), and the same bar's break loop
       (step 5) **always** breaks it. For a bullish box, `bottom = high[2] > low` by the IFVG condition.
       - The first chain update (the 2nd bar of a chain) therefore ends with `right = n`, `active = false`.
       - Later updates of the same chain hit an entry that is already broken (QUIRK 2). They leave it inactive
         with `right = n+8`.
   - **QUIRK 2.** An entry that is already broken still receives the new geometry and `right = n+8`, but stays
     inactive. It is then frozen at that `n+8`.
     - Because of QUIRK 1, this happens only in **IFVG chains of 3 or more bars**.
     - In FVG mode the chain entry is always still active when it is updated: the previous bar's break loop cannot
       break a gap it has just created.
   - **QUIRK 3.** If the newest entry is `na`, the update does nothing.
     - When it happens: the chain began before the `per` window, so its first bar created no box.
     - **Effect:** the **whole chain** is lost. Every later bar of the chain hits the same `na` entry, and the first
       box appears only with the next non-consecutive imbalance.
     - `HYPOTHESIS`: setters on an `na` box are silent no-ops. The script itself relies on this from bar 0: it calls
       `set_right` on the `na` liquidity box at lines 821–825.
3. **Bearish FVG** (lines 626–644). The mirror image:
   - update `left = n-2`, `top = low[2]`, `right = n+8`, `bottom = high`;
   - in IFVG mode the update is always broken at once, because `top = low[2] < high`.
4. **BPR block** (lines 647–697), §5. It runs **before** this bar's FVG break loop.
5. **FVG break loops** (lines 700–724). For `i = 0 .. min(10, visBxs-1)` and each **active** entry:
   - set `right = n+8`;
   - bullish entry:
     - if `low < top` and BPR is off, the border becomes dashed;
     - if `low < bottom`, the entry is broken. When BPR is off, the fill becomes the break colour at 95 and the
       border dotted. In all cases `right = n` and `active = false`.
   - bearish entry: dashed if `high > bottom`; broken if `high > top`;
   - the border **colour** never changes;
   - in IFVG mode with BPR off, a new box is dashed on its creation bar, because `low < high[2] = top`.
6. **BPR break loops** (lines 726–769), only if `i_BPR`. Same index range, active entries only (§6).
7. **Fibonacci** (lines 959–1118), on the last bar only (§8).

`HYPOTHESIS`: `box.get_top()` and `box.get_bottom()` return the raw values last written, with no normalisation, so an
inverted IFVG box keeps `top < bottom`. The ports therefore store logical top and bottom themselves. They never sort
the two values and never read them back from chart objects.

## 5. BPR creation and extension (lines 647–697)

The block is evaluated on **every bar** while `i_BPR` is on. It always uses the newest entry of each FVG array,
whether active or broken:

```
up = FVG_UP[0]       dn = FVG_DN[0]          // an na entry makes every comparison false → nothing happens
left  = min(up.left,  dn.left)              // = the left edge of the OLDER of the two FVGs
right = max(up.right, dn.right)

BPR_UP  (green, cFVGbl)  if  dn.bottom < up.bottom < dn.top     box: top = dn.top, bottom = up.bottom
        pos = close > up.bottom ? 1 : (close < dn.top ? -1 : 0)

BPR_DN  (red, cFVGbr)    if  up.bottom < dn.bottom < up.top     box: top = up.top, bottom = dn.bottom
        pos = close > dn.bottom ? 1 : (close < up.top ? -1 : 0)
```

For each of the two cases whose condition is true:

- If `left == BPR_X[0].left`, it is the **same** BPR. If that BPR is still active, set its `right`. Otherwise
  **nothing** happens.
- Otherwise it is a **new** BPR. `unshift(box(left, top, right, bottom, text "BPR"), active = true, pos)`, then `pop`
  and delete the oldest.

### What this means

- **BPR_UP (green).** The newest bullish FVG's bottom lies strictly inside the newest bearish FVG. The bullish gap
  sits higher and overlaps the upper part of the bearish gap. The box runs from the bullish bottom up to the bearish
  top.
- **BPR_DN (red).** The newest bearish FVG's bottom lies strictly inside the newest bullish FVG. The box runs from the
  bearish bottom up to the bullish top.
- The two conditions exclude each other: one needs `dn.bottom < up.bottom`, the other `up.bottom < dn.bottom`. With
  equal bottoms neither fires.
- Which FVG formed first does not matter, only their geometry. The BPR's `left` is always the left edge of the older
  FVG.
- **When a BPR can appear.** Although the block runs every bar, a BPR can only be **created** on a bar where an FVG was
  created or consecutively updated. Between such bars the inputs to the block do not change. `VERIFIED` by simulation
  during the spec review: 0 of 82,143 creations happened on a bar without an FVG event. This also means a "new BPR"
  alert can only fire on such a bar.

### Quirks

- **QUIRK 4.** The box top is the other gap's top, not the top of the true overlap. If `up.top < dn.top`, a BPR_UP
  box reaches above the bullish gap, up to `dn.top`. The true intersection would be
  `[up.bottom, min(up.top, dn.top)]`. BPR_DN mirrors this.
- **QUIRK 5.** `pos` is never 0. For BPR_UP, `close <= up.bottom` implies `close < dn.top`. So `pos = 1` exactly when
  the creation bar closes above the box bottom (a close equal to the bottom gives `-1`).
- **QUIRK 6.** A BPR is identified by its **left** edge alone, which is the left edge of the older FVG.
  - **Unchanged older FVG.** When a new FVG forms but the older one is unchanged, `left` is unchanged. The existing
    BPR keeps its **old** top and bottom, even though the overlap changed. A BPR's geometry never changes after
    creation.
- **QUIRK 6b.** If that same-left BPR is already **broken**, the new overlap is silently dropped, with no box at all.
  It stays dropped until the older FVG leaves index 0 of its array. The spec review saw this case often in random data.
- **QUIRK 7 (corrected).** A consecutive update always changes the **newer** FVG of the pair, so it never changes
  `left`. An opposite FVG cannot form during a chain (§3), so the other array's newest entry is always older. A chain
  update can do one of three things:
  - (a) if a BPR already exists for the pair, it keeps the first gap's geometry (QUIRK 6), and only `right` moves while
    it is active;
  - (b) if the overlap first becomes true on an update bar, the new BPR takes the updated geometry;
  - (c) if the update moves the pair from the BPR_UP condition to the BPR_DN condition (or back), a BPR is created in
    the other array with the **same** `left`.

  Revision 1 claimed a second BPR with a new `left`. That cannot happen: 0 of 25,233 simulated updates changed `left`.
- **QUIRK 8.** `set_right(right)` in the BPR block is always overwritten in the same bar. So is the initial `right` of
  a new BPR. The reason: the BPR break loop runs afterwards and sets `n+8`, or `n` on a break, and index 0 is always
  inside `0..bxBack`.
- **QUIRK 9.** A BPR can be built from broken (inactive) FVGs. A break never removes an FVG from its array; only a
  newer FVG pushes it out.
- **QUIRK 10.** The block sees an FVG created on this bar at once. The other FVG's `right` is still the previous bar's
  value (`n+7` if active). Because of QUIRK 8 this has no visible effect.
- **QUIRK 11.** With `visBxs ≥ 12`, an entry at index 11 or higher is never processed by any break loop. It keeps
  `active = true` for ever, and its `right` stays at the `n+8` of the last bar it sat at index ≤ 10. This applies to
  both FVG and BPR arrays.

## 6. BPR break loops (lines 726–769)

For `i = 0 .. min(10, visBxs-1)` and each active BPR, with `top`/`bottom` taken from the BPR box:

```
right = n + 8
pos == -1:   high > bottom  → border dashed
             high > top     → fill = break colour @95, border dotted, right = n, active = false
pos ==  1:   low  < top     → border dashed
             low  < bottom  → fill = break colour @95, border dotted, right = n, active = false
```

- **Break colour.** `cFVGblBR` (#808000) for BPR_UP and `cFVGbrBR` (#FF0000) for BPR_DN. The border and text keep
  their base colour at 65.
- **What `pos` means:**
  - `pos = 1`: price closed above the zone's bottom on the creation bar, so the zone is support. It breaks when a
    later low trades below the bottom.
  - `pos = -1`: the zone is resistance. It breaks when a high trades above the top.
- **Creation bar.** On the creation bar the loop runs with that bar's own high and low, so a BPR can be created and
  broken on the same bar. In FVG mode the gap conditions make this impossible. In IFVG mode it can happen; see
  `tests/test_luxalgo_bpr.py::test_bpr_created_and_broken_on_the_same_bar_ifvg`.

## 7. Forming bar and "Present" mode

### Forming bar

**History.** Every closed bar runs §4 steps 1–7 once.

**Realtime bar.** `HYPOTHESIS` (Pine execution model). On every tick Pine restores the state committed at the
previous bar's close, including arrays and drawings. It then re-runs the bar with the current OHLC, and only the
values at the bar's close are committed. All three ports emulate this: a committed state for closed bars, plus a
throw-away copy that processes the forming bar.

What can change during the bar:

| Item | Behaviour while the bar forms |
|---|---|
| Breaks of committed boxes | In FVG mode, monotone: high only rises and low only falls, so a box broken on one tick is still broken at the close. In IFVG mode, a new gap can appear on a later tick (next row). The BPR it creates is unshifted, and that can pop a committed zone an earlier tick showed as broken, or push it past index 10 (QUIRK 11). That zone then vanishes or shows as active at the close. |
| A new gap in FVG mode | Can disappear, but cannot appear late. |
| A new gap in IFVG mode | Can appear, but cannot disappear. |
| A forming-bar FVG's top/bottom | Changes tick by tick. |
| A forming-bar BPR's `pos` | Changes tick by tick, because it depends on the current close. |

### Present mode

The window covers the last 501 bars at load time and grows with each new realtime bar. Bars already computed keep
their `per` value; new bars have `per = true`. This holds whether or not Pine updates `last_bar_index` on realtime
bars (`HYPOTHESIS` about the mechanism). In MT5, a full recalculation (new history, or a timeframe change) re-anchors
the window, as a reload does on TradingView.

### Look-ahead warning

Present mode is a **display** setting. Whether an FVG, and so a BPR, exists at a historical bar `t` depends on where
the data ends, not only on bars up to `t`. A chain that straddles the window start is lost entirely (QUIRK 3).

Under this project's no-look-ahead rule, **any backtest or experiment must use Historical mode**, or anchor `per` to
the evaluation time. The Python reference's causality test runs in Historical mode
(`tests/test_luxalgo_bpr.py::test_causality_truncation_invariance`).

## 8. Fibonacci between the last BPRs (`iFib = 'BPR'`, lines 976–990 and 1093–1118)

```
up = BPR_UP[0].box     dn = BPR_DN[0].box
dnFirst = up.left > dn.left                          dnBottm = up.top > dn.top      // compares TOPS
x1 = dnFirst ? dn.left  : up.left                    x2 = dnFirst ? up.right : dn.right
y1 = dnFirst ? (dnBottm ? dn.bottom : dn.top)  : (dnBottm ? up.top    : up.bottom)
y2 = dnFirst ? (dnBottm ? up.top    : up.bottom) : (dnBottm ? dn.bottom : dn.top)
rt = max(x1, x2);  _0 = (rt == x1) ? y1 : y2;  _1 = (rt == x1) ? y2 : y1;  df = _1 - _0
```

| Line | From → to | Style |
|---|---|---|
| Diagonal | `(x1,y1)` → `(x2,y2)` | silver @50, dashed |
| Vertical | `(rt,_0)` → `(rt,_0+1.618·df)` | silver @50, dotted |
| Levels | `rt` → `rt+50` bars, at `_0 + k·df` for k ∈ {0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.618}, and at `_1` | solid |

- **Level colours:** 0 and 1 silver @5; 0.236 and 0.786 orange @25; 0.382, 0.618 and 1.618 yellow @25; 0.5 green @25.
- **Extension.** `iExt` extends only the eight level lines to the right, not the diagonal or the vertical.
- **When it updates.** The lines are redrawn on the last bar only, from the current, possibly forming, state.
- **Which BPR is level 0.** For BPRs, `x2 > x1` always holds, so level 0 sits on the **later** BPR's edge (`y2`) and
  level 1 on the earlier BPR's edge.
- **Edge cases:**
  - equal lefts count as "up first";
  - broken and active BPRs are used alike;
  - if either newest BPR entry is an `na` placeholder, the coordinates are `na` and nothing shows (`HYPOTHESIS`);
  - with `i_BPR` **off**, the BPR arrays are empty, the size guard fails, and `x1 = y1 = x2 = y2 = 0`. Pine then draws
    all ten lines at price 0 from bar 0 to bar 50. The ports draw nothing in that case (§10).

## 9. Colour transparency in MT5

Pine colours carry transparency; MT5 chart objects do not. The MT5 port blends each colour with the chart background:

```
shown = (1 - t) * colour + t * background        // t = Pine transparency / 100, so 90 → 10 % colour
```

- Fills are drawn as filled rectangles behind the candles.
- The border is a second, unfilled rectangle that carries the solid, dashed or dotted style.
- The text "BPR" (or "FVG"/"IFVG" for debug FVG boxes) sits at the box centre, in the border colour.

## 10. What the ports change on purpose

| Item | Pine | Ports | Why |
|---|---|---|---|
| `i_BPR` default | false | **true** | The user asked to see the BPR. |
| FVG boxes in BPR mode | invisible | invisible; an optional debug input shows them | Shows which two gaps made a BPR. |
| Other modules (MSS/BOS, OB, liquidity, VI, NWOG/NDOG, killzones) | drawn | not ported | Not needed for the BPR; documented in `ICT_CONCEPTS_PARAMETERS.md`. |
| Fibonacci = BPR with BPR off | lines at price 0 | no lines | Pine's lines there are a degenerate artefact. |
| Alerts | none | optional "new BPR" alert on closed bars (MT5), default off | Live use. |
| `meanBody` | `ta.sma` builtin | sum of the last `len` bodies (oldest first) / `len` | `HYPOTHESIS`: the builtin's internal summation is not documented. A running sum could differ from a fresh window sum by floating-point rounding. That would matter only when `body` and `meanBody` are equal to within that rounding, which in practice is very rare. |
| MT5 hover tooltip on zones | none | kind, top, bottom, active, pos | Convenience. |
