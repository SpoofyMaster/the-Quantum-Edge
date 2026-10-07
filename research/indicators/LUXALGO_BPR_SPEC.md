# Balance Price Range (BPR) in "ICT Concepts [LuxAlgo]": exact specification

Source: `research/indicators/luxalgo_ict_concepts.pine`. This is the unmodified Pine v5 script, © LuxAlgo, licensed
CC BY-NC-SA 4.0. Line numbers below refer to that file.

This document is the single source of truth for the two ports:
- the Python reference `qe/indicators/luxalgo_bpr.py`;
- the MT5 indicator `mql5/Indicators/LuxAlgo_BPR/LuxAlgo_BPR.mq5`.

Every statement is read from the code. Where the code does something a trader might not expect, it is marked
**QUIRK** and both ports reproduce it on purpose.

Labels used in this document:

| Label | Meaning |
|---|---|
| `PUBLISHED` | From the Pine source. |
| `VERIFIED` | Checked by a test in this repo. The test is named. |
| `HYPOTHESIS` | Pine runtime behaviour taken from the Pine documentation that was not checked on TradingView. |

## 1. Inputs that affect the BPR

| Pine variable | Input title | Default | Range | Role in BPR |
|---|---|---|---|---|
| `i_mode` | Mode | `Present` | Present / Historical | `per = last_bar_index - bar_index <= 500` in Present mode, else always true. `per` gates **only the creation and update of FVGs** (and the displacement plot). The BPR block and all break loops run on every bar. |
| `len` | Market Structures → Length | 5 | 3–10 | Period of `meanBody = ta.sma(body, len)`. The same input also drives the market-structure swings, so changing it changes both. |
| `perc_Body` | (constant) | 0.36 | — | Maximum wick as a fraction of the body for a "displacement" candle. |
| `bxBack` | (constant) | 10 | — | The break loops look at indices `0..min(10, size-1)` only. |
| `shwFVG` | Show FVGs | true | bool | With `false`, no FVG is ever created, so **no BPR can exist**. |
| `i_BPR` | Balance Price Range | **false** | bool | Turns on the BPR. FVG boxes are then drawn with `na` colours (invisible), but they are still computed and still drive the BPR. |
| `i_FVG` | Options | `FVG` | FVG / IFVG | Gap definition (section 3). |
| `visBxs` | # Visible FVG's | 2 | 1–20 | Fixed length of each of the four arrays: FVG up, FVG down, BPR up and BPR down. |
| `cFVGbl` / `cFVGbr` | Bullish / Bearish FVG | #00e676 / #ff5252 | colour | BPR up / BPR down colour. Fill uses 90 transparency, border and text use 65. |
| `cFVGblBR` / `cFVGbrBR` | Break | #808000 / #FF0000 | colour | Fill of a broken BPR, at 95 transparency. |
| `iFib` / `iExt` | Fibonacci between last / Extend lines | NONE / false | — | With `BPR`, Fibonacci lines are drawn between the latest BPR up and the latest BPR down (section 8). |
| `sDispl` | Show Displacement | false | bool | Plots the displacement candles (section 2). |

The script declares `max_boxes_count=500` and `max_bars_back=3000`.

## 2. Displacement candle (lines 127–130, 548–553)

```
mx       = max(close, open)          mn = min(close, open)          body = |close - open|
meanBody = sma(body, len)            // na for the first len-1 bars
L_body   = (high - mx < body*0.36) and (mn - low < body*0.36)        // both wicks < 36% of body (strict)
L_bodyUP = body > meanBody and L_body and close > open
L_bodyDN = body > meanBody and L_body and close < open
```

`na` comparisons are false. So `L_bodyUP` is false while `meanBody` is `na`, and false for a doji (`body = 0`), because
`0 < 0` is false.

## 3. FVG detection (lines 565–566)

Bar `n` is the current bar. Bar `n-1` is the displacement candle. Bar `n-2` is the candle before it.

```
FVG  mode: imbalanceUP = L_bodyUP[1] and low  > high[2]     imbalanceDN = L_bodyDN[1] and high < low[2]
IFVG mode: imbalanceUP = L_bodyUP[1] and low  < high[2]     imbalanceDN = L_bodyDN[1] and high > low[2]
```

The comparisons are strict. In IFVG mode the box covers the overlap of bar `n`'s wick with bar `n-2`'s wick instead of
the gap between them.

## 4. Per-bar execution order (the order matters)

On each bar `n`, after computing the series above:

1. **Initialisation**, on the first bar only (lines 598–604). Push `visBxs` empty entries
   `FVG(box=na, active=false, pos=na)` into `FVG_UP` and `FVG_DN`. Push the same into `BPR_UP` and `BPR_DN` only if
   `i_BPR` is on. From then on every array has exactly `visBxs` entries, because every `unshift` is followed by a `pop`.
2. **Bullish FVG** (lines 606–624), if `imbalanceUP and per and shwFVG`:
   - If `imbalanceUP[1]` (the previous bar also had a bullish imbalance), update the newest entry in place:
     `left = n-2`, `top = low`, `right = n+8`, `bottom = high[2]`. The `active` flag is **not** touched.
     - **QUIRK 1.** This update always uses the FVG geometry, even in IFVG mode. In IFVG mode it produces `top < bottom`.
     - **QUIRK 2.** If that entry was already broken (inactive), it gets the new geometry and `right = n+8` but stays
       inactive. It then stays frozen at `n+8`.
     - **QUIRK 3.** If the entry is `na`, which happens when the previous bar's imbalance was outside the `per`
       window, nothing happens and the gap is lost.
   - Otherwise, `unshift` a new entry and `pop` (and delete) the oldest:
     - `left = n-2`, `right = n`;
     - FVG mode: `top = low`, `bottom = high[2]`;
     - IFVG mode: `top = high[2]`, `bottom = low`;
     - `active = true`, `pos = na`.
3. **Bearish FVG** (lines 626–644), the mirror image:
   - Consecutive update: `left = n-2`, `top = low[2]`, `right = n+8`, `bottom = high`.
   - New box: FVG mode `top = low[2]`, `bottom = high`; IFVG mode `top = high`, `bottom = low[2]`.
4. **BPR block** (lines 647–697). See section 5. It runs **before** this bar's FVG break loop, so it sees FVG
   `right` values from the previous bar.
5. **FVG break loops** (lines 700–724). For `i = 0 .. min(10, visBxs-1)` and each **active** entry:
   - `right = n+8`.
   - Bullish entry:
     - if `low < top` and BPR is off: border becomes dashed;
     - if `low < bottom`: the gap is broken. If BPR is off, the fill becomes the break colour at 95 and the border
       becomes dotted. Then `right = n` and `active = false`.
   - Bearish entry: `high > bottom` → dashed; `high > top` → broken.
6. **BPR break loops** (lines 726–769), only if `i_BPR`. Same index range, active entries only. See section 6.
7. **Fibonacci** (lines 959–1118), on the last bar only.

## 5. BPR creation and extension (lines 647–697)

The block runs on **every bar** when `i_BPR` is on. It does not wait for a new FVG. It always uses the newest entry
of each FVG array, whether that entry is active or broken:

```
up = FVG_UP[0]       dn = FVG_DN[0]
left  = min(up.left,  dn.left)          // = the left edge of the OLDER of the two FVGs
right = max(up.right, dn.right)

BPR_UP  (green, cFVGbl)  if  up.bottom < dn.top  and  dn.bottom < up.bottom
        box: top = dn.top,  bottom = up.bottom
        pos = close > up.bottom ? 1 : (close < dn.top ? -1 : 0)

BPR_DN  (red, cFVGbr)    if  dn.bottom < up.top  and  up.bottom < dn.bottom
        box: top = up.top,  bottom = dn.bottom
        pos = close > dn.bottom ? 1 : (close < up.top ? -1 : 0)
```

For each of the two cases, when its condition is true:

- If `left == BPR_X[0].left`, it is the **same** BPR. If that BPR is still active, set its `right = right`. Nothing
  else changes.
- Otherwise it is a **new** BPR. `unshift(box(left, top, right, bottom), active = true, pos)`, then `pop` and delete
  the oldest.

### What this means

- **BPR_UP (green).** The latest bullish FVG's **bottom** lies strictly inside the latest bearish FVG. The bullish gap
  sits higher and overlaps the bearish gap's upper part. The box runs from the bullish bottom up to the bearish top.
- **BPR_DN (red).** The latest bearish FVG's **bottom** lies strictly inside the latest bullish FVG. The box runs from
  the bearish bottom up to the bullish top.
- The two conditions exclude each other: one needs `dn.bottom < up.bottom` and the other `up.bottom < dn.bottom`.
  With equal bottoms, neither fires.
- The order in which the two FVGs formed does not matter. Only their geometry matters.

### Quirks

- **QUIRK 4.** The box top is the other gap's top, not the top of the true overlap. If `up.top < dn.top`, the BPR_UP
  box extends above the bullish gap up to `dn.top`. The true overlap would be `[up.bottom, min(up.top, dn.top)]`.
  The same applies to BPR_DN.
- **QUIRK 5.** `pos` is never 0. For BPR_UP, `close <= up.bottom` implies `close < dn.top`, because
  `up.bottom < dn.top`. So `pos = 1` exactly when the close of the creation bar is above the box bottom, and `-1`
  otherwise.
- **QUIRK 6.** The identity of a BPR is its **left** edge, which is the left edge of the older FVG. A new FVG that
  forms while the older one stays the same gives the same `left`. The existing BPR is then kept with its **old**
  top and bottom, even though the overlap changed. The BPR geometry is never updated after creation.
- **QUIRK 7.** A consecutive-imbalance update moves an FVG's `left` by one bar. If that FVG is the older of the pair,
  `left` changes and a second BPR is created on the next evaluation. That is the same bar, because the BPR block
  runs after the FVG update.
- **QUIRK 8.** The extension `right = max(...)` in the BPR block is always overwritten in the same bar. The BPR
  break loop, which runs afterwards, sets `right = n+8`, or `right = n` on a break. This is because index 0 is
  always inside `0..bxBack`. The BPR block's `set_right` therefore has no visible effect.
- **QUIRK 9.** A BPR can be created from a broken (inactive) FVG. Breaks do not remove FVGs from the arrays; only a
  newer FVG pushes them out.
- **QUIRK 10.** The BPR block reads the two FVGs at index 0. It sees a new FVG created on this bar at once. The other
  FVG's `right` is still the previous bar's value: `n+7` if it is active, or the bar where it broke.

## 6. BPR break loops (lines 726–769)

For `i = 0 .. min(10, visBxs-1)`, each active BPR, with `top`/`bottom` = the BPR box:

```
right = n + 8
pos == -1:   high > bottom  → border dashed
             high > top     → fill = break colour @95, border dotted, right = n, active = false
pos ==  1:   low  < top     → border dashed
             low  < bottom  → fill = break colour @95, border dotted, right = n, active = false
```

The break colour is `cFVGblBR` (#808000) for BPR_UP and `cFVGbrBR` (#FF0000) for BPR_DN.

`pos = 1` means price closed above the zone's bottom on the creation bar. The zone is then support, and it breaks
when a later low trades below its bottom. `pos = -1` means the zone is resistance, and it breaks when a high trades
above its top.

On the creation bar itself the loop runs with that bar's own high and low. A BPR whose creation bar's wick already
crossed it is therefore created and broken on the same bar.

## 7. Bar time, the forming bar and "Present" mode

- **History.** Every closed bar runs steps 1–7 once.
- **Realtime bar.** `HYPOTHESIS` (Pine documentation on the execution model). On every tick, Pine restores the state
  committed at the previous bar's close, including arrays and drawings. It then re-runs the script with the current
  open/high/low/close. A BPR on the forming bar can appear and disappear until the bar closes ("repaint"). Only the
  values at the bar's close are committed.
  - Both ports emulate this: committed state for closed bars, plus a throw-away copy that runs the forming bar.
- **Present mode.** `last_bar_index` is fixed when the script loads, so the 501-bar window starts at
  `load_last_index - 500` and grows with new realtime bars. In MT5, a full recalculation (new history, or a timeframe
  change) re-anchors the window, the same as a reload on TradingView.

## 8. Fibonacci between the last BPRs (`iFib = 'BPR'`, lines 976–990 and 1093–1118)

```
up = BPR_UP[0].box     dn = BPR_DN[0].box             // either may be na → no lines
dnFirst = up.left > dn.left                          dnBottm = up.top > dn.top
x1 = dnFirst ? dn.left  : up.left                    x2 = dnFirst ? up.right : dn.right
y1 = dnFirst ? (dnBottm ? dn.bottom : dn.top)  : (dnBottm ? up.top    : up.bottom)
y2 = dnFirst ? (dnBottm ? up.top    : up.bottom) : (dnBottm ? dn.bottom : dn.top)
rt = max(x1, x2);  _0 = (rt == x1) ? y1 : y2;  _1 = (rt == x1) ? y2 : y1;  df = _1 - _0
```

Lines are drawn as follows:

| Line | Coordinates | Style |
|---|---|---|
| Diagonal | `(x1,y1)–(x2,y2)` | silver, 50 transparency, dashed |
| Vertical | `(rt,_0)–(rt,_0+1.618·df)` | silver 50, dotted |
| Levels | from `rt` to `rt+50` bars, at `_0 + k·df` for k ∈ {0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.618}, plus `_1` | — |

Level colours:

| Level | Colour |
|---|---|
| 0 and 1 | silver 5 |
| 0.236, 0.786 | orange 25 |
| 0.382, 0.618, 1.618 | yellow 25 |
| 0.5 | green 25 |

With `iExt`, the level lines extend to the right. In the Pine run they are redrawn on the last bar only, using the
current (possibly forming) state.

## 9. Colour transparency in MT5

`HYPOTHESIS` (port design). Pine colours carry transparency; MT5 chart objects do not. The port blends each colour
with the chart background:

```
shown = (1 - t) * colour + t * background
```

where `t` is the Pine transparency / 100, so 90 → 10 % colour. Fills are drawn as filled background rectangles. The
border is a second, unfilled rectangle that carries the solid, dashed or dotted style.

## 10. What the ports change on purpose

| Item | Pine | Port | Why |
|---|---|---|---|
| `i_BPR` default | false | **true** | The user asked to see the BPR. |
| FVG boxes in BPR mode | invisible | invisible; optional debug input shows them | Helps the user see which two gaps made a BPR. |
| Other modules (MSS/BOS, OB, liquidity, VI, NWOG/NDOG, killzones) | drawn | not ported | Not needed for the BPR. They are documented in `ICT_CONCEPTS_PARAMETERS.md`. |
| Alerts | none | optional "new BPR" alert on closed bars, default off | Live use. |
| `meanBody` | `ta.sma` builtin | sum of the last `len` bodies / `len` | Same value. A last-bit rounding difference could only matter when `body == meanBody` to about 1e-16. |
