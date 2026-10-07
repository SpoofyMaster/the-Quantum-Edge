# "ICT Concepts [LuxAlgo]": reference of every input, constant and algorithm

## 1. Introduction

Source: `research/indicators/luxalgo_ict_concepts.pine` (1144 lines, Pine v5, unmodified). Line numbers below refer
to that file.

The script is an overlay. It draws:

- market structure: MSS and BOS lines and labels, built on an internal zig-zag that is never drawn itself;
- displacement candles (optional shapes);
- volume imbalances (VI);
- order blocks (OB) and breaker blocks, with optional polarity-change labels;
- buyside and sellside liquidity zones (clusters of equal highs or lows);
- fair value gaps (FVG) or implied fair value gaps (IFVG);
- balance price ranges (BPR), built from the newest bullish and bearish FVG;
- new week and new day opening gaps (NWOG, NDOG);
- one Fibonacci set between the last two zones of a chosen type;
- killzone backgrounds (New York, London open, London close, Asian).

The BPR is specified in full, with its intentional quirks, in `research/indicators/LUXALGO_BPR_SPEC.md`. This
document only summarises it (section 4.8).

**Licence.** The Pine code is © LuxAlgo (original Pine v5 logic of 'ICT Concepts [LuxAlgo]'), licensed CC BY-NC-SA
4.0, https://creativecommons.org/licenses/by-nc-sa/4.0/ . This document is a derivative description of that code. It
quotes short fragments, is for non-commercial use, and is shared under the same licence. What the repo's ports change
on purpose is listed in `LUXALGO_BPR_SPEC.md` section 10.

### Labels and notation

| Label | Meaning |
|---|---|
| `PUBLISHED` | Read from the Pine source. **Every statement in this file has this label unless it is marked otherwise.** |
| `HYPOTHESIS` | Depends on Pine runtime behaviour that cannot be confirmed from the code. Not checked on TradingView. |

- `n` = `bar_index` (line 116). `x[k]` = value `k` bars ago. `mx = max(open, close)`, `mn = min(open, close)`,
  `body = |close - open|` (lines 127–129).
- UI titles are shown trimmed. The code pads many titles with the spacer strings `sp1` (7 spaces) and `sp2`
  (14 spaces), lines 10–11.
- "tN" after a colour means Pine transparency N (0 = opaque, 100 = invisible).

## 2. Inputs, constants and couplings

### 2.1 Script declaration (line 5)

| Setting | Value | Effect |
|---|---|---|
| `overlay` | true | Drawn on the price pane. |
| `max_lines_count` / `max_boxes_count` / `max_labels_count` | 500 each | Budget shared by all modules. When it is exceeded, Pine removes the oldest drawings of that kind (HYPOTHESIS: Pine runtime). |
| `max_bars_back` | 3000 | History buffer size. `draw()` also calls `max_bars_back(time, 1000)` (line 346). |

### 2.2 Mode

| Pine variable | UI title | Default | Options | What it does in the code | Drawings affected |
|---|---|---|---|---|---|
| `i_mode` | Mode | `Present` | Present, Historical | Present: `per = last_bar_index - bar_index <= 500` (122), so `per`-gated steps run only on the last 501 bars. Historical: `per = true`. In Present mode, every new MSS also deletes **all** MSS and BOS lines and labels (475–479, 489–493). | Liquidity, FVG and therefore BPR, OB, displacement, killzones (via `per`); MSS/BOS (via clearing). See 2.14. |

### 2.3 Market Structures

| Pine variable | UI title | Default | Range / options | What it does in the code | Drawings affected |
|---|---|---|---|---|---|
| `showMS` | (checkbox, no title) | true | bool | Gates the whole MSS/BOS block inside `draw()` (466). The zig-zag and liquidity scans still run. | MSS, BOS |
| `len` | Length | 5 | 3–10 | (1) Left bars of the zig-zag pivots `ta.pivothigh(high, len, 1)` and `ta.pivotlow(low, len, 1)` (`draw(len, …)` at 527, used at 351–352). (2) Period of `meanBody = ta.sma(body, len)` (130), which defines displacement candles, and through them FVGs and BPRs. | MSS, BOS, liquidity, displacement, FVG, BPR, Fibonacci |
| `iMSS` | MSS | true | bool | When false, after the MSS/BOS switch on every bar, the colour of the newest bullish and the newest bearish MSS line and label is set to `na` (518–520). MSS state (`MSS.dir`) still changes, so BOS still needs an MSS. HYPOTHESIS: `array.get(0)` on an empty array is a Pine runtime error. Both MSS arrays are empty on the first bar, and in Present mode one of them is empty after every MSS, so `iMSS = false` would stop the script. | MSS |
| `cMSSbl` / `cMSSbr` | bullish / bearish (MSS row) | #00e6a1 / #e60400 | colour | MSS line colour and MSS label text colour (482, 485, 496, 499). | MSS |
| `iBOS` | BOS | true | bool | Enables the two BOS cases of the switch (501, 510). | BOS |
| `cBOSbl` / `cBOSbr` | bullish / bearish (BOS row) | #00e6a1 / #e60400 | colour | **Not used anywhere.** BOS lines and labels use hard-coded `color.lime` (bullish) and `color.red` (bearish) in `set_lin` / `set_lab` (337, 341). | none |

### 2.4 Displacement

| Pine variable | UI title | Default | Range | What it does in the code | Drawings affected |
|---|---|---|---|---|---|
| `sDispl` | Show Displacement | false | bool | Plots a lime `labelup` below each `L_bodyUP` candle and a red `labeldown` above each `L_bodyDN` candle, only where `per` is true (1123–1134). It does not change any other logic. | Displacement shapes |
| `perc_Body` | (constant) | 0.36 | — | Line 38. Comment shows a disabled input of 1–36 %. Both wicks must be strictly shorter than `0.36 × body` (548–550). | Displacement, FVG, BPR |
| `bxBack` | (constant) | 10 | — | Line 39. Comment shows a disabled input of 0–10. The FVG and BPR break loops visit indices `0..min(10, size-1)` only (700, 713, 727, 749). | FVG, BPR |

### 2.5 Volume Imbalance

| Pine variable | UI title | Default | Range | What it does in the code | Drawings affected |
|---|---|---|---|---|---|
| `sVimbl` | (checkbox) | true | bool | Gates VI creation (572). | VI |
| `visVim` | # Visible VI's | 2 | 2–100 | Maximum VI drawings kept. Bullish and bearish VIs share one array; the oldest is deleted when the size exceeds `visVim` (591–595). | VI, Fibonacci `VI` |
| `cVimbl` | (colour) | #06b2d0 | colour | Both lines and the `VI` label text, for both directions (576–588). | VI |
| `maxVimb` | (constant) | 2 | — | Line 217. **Unused.** | none |

### 2.6 Order Blocks

| Pine variable | UI title | Default | Range | What it does in the code | Drawings affected |
|---|---|---|---|---|---|
| `showOB` | Show Order Blocks | true | bool | Gates OB detection, breaker updates and polarity labels (861, 896), and the display on the last bar (934, 290). | OB, breakers, polarity labels, Fibonacci `OB` |
| `length` | Swing Lookback | 10 | ≥ 3 (no max) | Window of `swings(length)` (859): `ta.highest(length)`, `ta.lowest(length)` (321–322). The function also reads the **global** `length` for `high[length]`, `low[length]`, `bar_index[length]` (328, 331). This is consistent only because it is called with `length`. Not related to `len`. | OB |
| `showBull` | Show Last Bullish OB | 1 | ≥ 0 | Number of newest bullish OBs drawn (942–947). Also the index limit for the bullish polarity check (`i < showBull`, 886). Also changes which pair Fibonacci `OB` uses (4.10). | OB, polarity labels, Fibonacci |
| `showBear` | Show Last Bearish OB | 1 | ≥ 0 | Mirror for bearish OBs (949–954, 921). | same |
| `useBody` | Use Candle Body | true | bool | `max = useBody ? mx : high`, `min = useBody ? mn : low` (131–132). Defines the OB zone and the search for the extreme candle (865–872, 900–907). The breaker test uses the candle body regardless (880, 915). The input has **no `group`**, so it is not in the "Order Blocks" section of the settings dialog (exact placement: TradingView UI). | OB |
| `bullCss` | Bullish OB | #3e89fa | colour | `+OB` line and label of an unbroken bullish OB (947, 307–313). Also the text colour of the `▲` label, made opaque by `notransp()` (927). | OB, polarity labels |
| `bullBrkCss` | Bullish Break | #4785f9 t85 | colour | Fill of a bullish breaker box (295). | breakers |
| `bearCss` | Bearish OB | #FF3131 | colour | `-OB` line and label. Also the opaque text colour of the `▼` label (892). | OB, polarity labels |
| `bearBrkCss` | Bearish Break | #f9ff57 t85 | colour | Fill of a bearish breaker box. | breakers |
| `showLabels` | Show Historical Polarity Changes | false | bool | `▼` / `▲` labels (890–894, 925–929). | polarity labels |

### 2.7 Liquidity

| Pine variable | UI title | Default | Range | What it does in the code | Drawings affected |
|---|---|---|---|---|---|
| `showLq` | Show Liquidity | true | bool | Gates zone creation inside `draw()` (366, 422). The sweep loop (822–856) runs regardless. | Liquidity |
| `a` | margin | input 4 → `a = 10/4 = 2.5` | margin 2–7, step 0.1 | `a = 10 / margin` (63). The tolerance and box half-height is `atr / a = ATR(10) × margin / 10`. That is 0.4 × ATR by default, and 0.2–0.7 × ATR over the range. Used for clustering (374, 377, 430, 433) and box height (388–393, 444–449). A larger margin gives a wider tolerance and taller boxes. | Liquidity, Fibonacci `Liq` |
| `visLiq` | # Visible Liq. boxes | 2 | 1–50 | Maximum zones per side (404, 460). Each array starts with **one dummy entry** with `box(na)` (227–228), which counts towards this limit until it is pushed out. | Liquidity |
| `cLIQ_B` | Buyside Liquidity | #fa451c | colour | Box text (t25), level line (t0), fill after a close enters the zone (t90) (395, 401, 834). | Buyside zones |
| `cLIQ_S` | Sellside Liquidity | #1ce4fa | colour | Same, for sellside (451, 457, 852). | Sellside zones |

### 2.8 Fair Value Gaps

| Pine variable | UI title | Default | Range / options | What it does in the code | Drawings affected |
|---|---|---|---|---|---|
| `shwFVG` | Show FVGs | true | bool | Gates FVG creation and consecutive updates (606, 626). With `false` no FVG exists, so no BPR can exist and Fibonacci `FVG` / `BPR` have nothing to draw. | FVG, BPR, Fibonacci |
| `i_BPR` | Balance Price Range | false | bool | Fills the BPR arrays on the first bar (602–604) and enables the BPR block (647) and the BPR break loops (726). FVG boxes then get `na` colours, which makes them invisible (616–618, 636–638). FVG dashed, dotted and break styling is also switched off (704–709, 717–722). | FVG (hidden), BPR |
| `i_FVG` | Options | `FVG` | FVG, IFVG | Gap condition (565–566), box geometry (614–615, 634–635), and box text (`FVG` / `IFVG`). | FVG, BPR |
| `visBxs` | # Visible FVG's | 2 | 1–20 | Fixed length of each of the four arrays: FVG up, FVG down, BPR up, BPR down (598–604). The break loops stop at index 10 (`bxBack`). With `visBxs ≥ 12`, entries 11..`visBxs-1` are never extended or broken again. | FVG, BPR |
| `cFVGbl` | Bullish FVG | #00e676 | colour | Bullish FVG fill t90, border and text t65. Also the BPR_UP colour (666–668). | FVG, BPR |
| `cFVGblBR` | Break | #808000 | colour | Fill of a broken bullish FVG or BPR_UP, t95 (708, 736, 744). | FVG, BPR |
| `cFVGbr` | Bearish FVG | #ff5252 | colour | Bearish FVG and BPR_DN colour. | FVG, BPR |
| `cFVGbrBR` | Break | #FF0000 | colour | Fill of a broken bearish FVG or BPR_DN, t95. | FVG, BPR |

### 2.9 NWOG/NDOG

| Pine variable | UI title | Default | Range | What it does in the code | Drawings affected |
|---|---|---|---|---|---|
| `iNWOG` | (checkbox) | true | bool | Creates an NWOG on the first bar of each Monday (782). | NWOG |
| `cNWOG1` | NWOG | #ff5252 t28 | colour | Dotted midline (795). | NWOG |
| `cNWOG2` | (colour) | #b2b5be t50 | colour | Box border. The box has no fill (788–789). | NWOG |
| `maxNWOG` | Show max | 3 | 0–50 | Number of placeholder entries pushed on the first bar (773–774). Every new NWOG is pushed and the oldest popped, so this is the number kept. HYPOTHESIS: `for i = 0 to -1` counts down in Pine, so `maxNWOG = 0` would create 2 placeholders and keep 2 NWOGs. | NWOG, Fibonacci `NWOG` |
| `iNDOG` | (checkbox) | false | bool | Creates an NDOG on the first bar of every new day (800). | NDOG |
| `cNDOG1` | NDOG | #ff9800 t20 | colour | Dotted midline. | NDOG |
| `cNDOG2` | (colour) | #4dd0e1 t65 | colour | Box border. | NDOG |
| `maxNDOG` | Show max | 1 | 0–50 | Same as `maxNWOG` (775–776). The same HYPOTHESIS applies to 0. | NDOG |

### 2.10 Fibonacci

| Pine variable | UI title | Default | Options | What it does in the code | Drawings affected |
|---|---|---|---|---|---|
| `iFib` | Fibonacci between last: | `NONE` | FVG, BPR, OB, Liq, VI, NWOG, NONE | Chooses the pair of zones (961–1091). `OB` also switches `xloc` to `xloc.bar_time` (124) and `plus` to `50 × tf_msec` (126) for all ten Fibonacci lines, because OB drawings use time coordinates. NDOG is not an option. | Fibonacci lines |
| `iExt` | Extend lines | false | bool | `ext = extend.right` (125) for the eight level lines (253–260). The diagonal and the vertical line are not extended. | Fibonacci levels |

### 2.11 Killzones (lines 99–111 and 538–541)

| Pine variable | UI title | Default | Range | What it does in the code | Drawings affected |
|---|---|---|---|---|---|
| `showKZ` | Show Killzones | false | bool | Master switch. It is ANDed into each of the four flags below (101–110). | all killzones |
| `showNy` / `nyCss` | New York / (colour) | true / #ff5d00 t93 | bool / colour | Background where `per` and the bar is inside the NY session (538, 1139). | NY background |
| (session input, line 538) | (no title, NY row) | `0700-0900` | session | Hours. The time zone `America/New_York` is hard-coded. | NY |
| `showLdno` / `ldnoCss` | London Open / (colour) | true / #00bcd4 t93 | | Line 539, 1140. | London open |
| (session input, line 539) | (no title) | `0700-1000` | session | Time zone `Europe/London` is hard-coded. | London open |
| `showLdnc` / `ldncCss` | London Close / (colour) | true / #2157f3 t93 | | Line 540, 1141. | London close |
| (session input, line 540) | (no title) | `1500-1700` | session | Time zone `Europe/London` is hard-coded. | London close |
| `showAsia` / `asiaCss` | Asian / (colour) | true / #e91e63 t93 | | Line 541, 1142. | Asian |
| (session input, line 541) | (no title) | `1000-1400` | session | Time zone `Asia/Tokyo` is hard-coded. | Asian |

The code comments give winter-only UTC-5 equivalents. The time zones are IANA names, so the sessions follow DST. In UTC:

| Killzone | Local | UTC in winter | UTC in summer |
|---|---|---|---|
| New York | 07:00–09:00 New York | 12:00–14:00 | 11:00–13:00 |
| London open | 07:00–10:00 London | 07:00–10:00 | 06:00–09:00 |
| London close | 15:00–17:00 London | 15:00–17:00 | 14:00–16:00 |
| Asian | 10:00–14:00 Tokyo (no DST) | 01:00–05:00 | 01:00–05:00 |

The four `bgcolor` calls have `editable = false` (1139–1142), so their colours can only be changed through the inputs.
HYPOTHESIS (Pine runtime): two points cannot be read from the code. The session strings have no `:days` suffix, so
which weekdays count depends on Pine's default. How `time(timeframe.period, session, tz)` treats a bar that straddles a
session edge also depends on the runtime.

### 2.12 Hidden and derived constants (General Calculations, lines 116–138, and others)

| Name | Line | Value / formula | Used by |
|---|---|---|---|
| `hi`, `lo` | 117–118 | aliases of `high`, `low` | zig-zag pivots (351–352, 357, 413) |
| `tf_msec` | 119 | chart timeframe in milliseconds | OB drawing widths (294, 307, 309); `plus` |
| `maxSize` | 120 | 50 | length of the zig-zag arrays (246–249). The liquidity scan also hard-codes 50 (372, 428). |
| `atr` | 121 | `ta.atr(10)` | **Liquidity only**: tolerance and box height `atr/a`. ATR period 10 is fixed. |
| `per` | 122 | Present: `last_bar_index - bar_index <= 500`; Historical: true | see 2.14 |
| `perB` | 123 | `last_bar_index - bar_index <= 1000` | **unused** |
| `xloc` | 124 | `iFib == 'OB' ? xloc.bar_time : xloc.bar_index` | the ten Fibonacci lines (251–260), created once with `var` |
| `ext` | 125 | `iExt ? extend.right : extend.none` | the eight Fibonacci level lines |
| `plus` | 126 | `iFib == 'OB' ? tf_msec*50 : 50` | length of the Fibonacci level lines: 50 bars |
| `mx`, `mn`, `body` | 127–129 | body top, body bottom, body size | displacement, VI |
| `meanBody` | 130 | `ta.sma(body, len)`, includes the current bar | displacement, so FVG and BPR |
| `max`, `min` | 131–132 | body or wick extremes (`useBody`) | OB |
| `blBrkConf`, `brBrkConf` | 133–134 | reset to 0 on every bar | polarity labels (rising edge `x > x[1]`) |
| `r`, `g`, `b`, `isDark` | 135–138 | `isDark` = all background RGB channels < 80 | **unused** |
| `maxVimb` | 217 | 2 | **unused** |
| BOS cap | 529–535 | 200 lines and labels per side | BOS. MSS arrays have no cap. |
| zig-zag right bars | 351–352 | 1 | pivots are confirmed one bar after the extreme |
| liquidity minimum count | 385, 441 | `count > 2`, so at least 3 matching swing points | Liquidity |
| liquidity extension | 389, 393, 825 | `n+10` at creation, then `n+3` on every bar | Liquidity |
| `maxP` start value | 371, 427 | `10e6` = 1e7 | Liquidity. It would be wrong for prices above 1e7. |
| VI length | 576–588 | lines end at `n+3` and are never extended | VI |
| OB drawing width | 294, 307, 309 | 10 bars in time units (`10 × tf_msec`) | OB |
| FVG / BPR extension | 609, 629, 703, 716, 730, 752 | `n+8` | FVG, BPR |
| Fibonacci levels | 1102–1107 | 0, 0.236, 0.382, 0.5, 0.618, 0.786, 1, 1.618 | Fibonacci |
| Killzone transparency | 102–111 | 93 | Killzones |

### 2.13 Declared but unused (dead code)

| Item | Lines | Note |
|---|---|---|
| `cBOSbl`, `cBOSbr` | 32–33 | BOS colours are hard-coded lime and red. |
| `perB`, `isDark` (and `r`, `g`, `b`), `maxVimb`, string `hl` | 123, 135–138, 217, 12 | — |
| `ph`, `pl`, `lPh`, `lPl` (`ta.pivothigh(3,1)`, `ta.pivotlow(3,1)`) | 544–545 | They feed only `lwst` and `hgst` (561–562), which are never read. |
| `bsNOTbodyUP/DN`, `bsIs_bodyUP/DN` | 555–559 | `bsNOT…` only feed `lwst` / `hgst`; `bsIs_…` are never read. |
| `col` argument of `draw()` / `in_out()` (`color.yellow`), `ZZ.b` array, `x1`/`y1` of `in_out` | 265–266, 344, 527 | The zig-zag is stored but **never drawn**. |
| `ob.break_loc` | 190, 882, 917 | Written, never read. The breaker box starts at the OB candle, not at the break. |
| `timeinrange`, `clear_aLine`, type `ln_d` | 268, 272–275, 149 | — |
| `lt`, `tp`, `bt` | 1095–1097 | Computed in the Fibonacci block and never used. |

### 2.14 What Present mode (`per`) gates

| Step | Gated by `per`? | Lines |
|---|---|---|
| Zig-zag points | no | 351–363, 409–419 |
| Liquidity zone creation / reshaping | **yes** | 366, 422 |
| Liquidity extension and sweep | no | 822–856 |
| MSS / BOS | no. In Present mode every new MSS **deletes all MSS and BOS drawings** instead. | 466–520 |
| Displacement shapes | **yes** | 1123, 1129 |
| Volume imbalance | no | 572 |
| FVG creation and consecutive update | **yes** | 606, 626 |
| BPR creation, FVG and BPR break loops | no | 647–769 |
| OB detection, breaker updates, polarity labels | **yes** | 861, 896 |
| OB display, Fibonacci (last bar only) | no | 934, 959 |
| NWOG / NDOG | no | 778–819 |
| Killzone backgrounds | **yes** | 1139–1142 |

### 2.15 Couplings and surprises

1. **`len` drives two unrelated things**: the zig-zag (MSS, BOS, liquidity) and `meanBody` (displacement, FVG, BPR). You
   cannot tune the FVG body filter without moving the market structure, and the reverse.
2. **`length` is the OB swing window only.** It is a different input from `len`. `swings()` names its parameter `len`
   (which hides the global `len` inside the function) but reads the global `length` directly at lines 328 and 331.
3. **Present mode is not a uniform "last 500 bars" filter** (2.14). For MSS/BOS it means "only since the last MSS".
4. **`i_BPR` hides the FVG boxes** but they still exist, still count towards `max_boxes_count`, and still drive the BPR
   and Fibonacci `FVG`.
5. **`iFib = 'OB'` switches every Fibonacci line to `xloc.bar_time`.**
6. **Fibonacci `OB` depends on `showBull`.** The drawing array ends with the newest bullish OB (4.5), and Fibonacci
   reads the last two entries. With `showBull = 1` it pairs the newest bullish OB with the newest
   bearish OB. With `showBull ≥ 2` it pairs the two newest bullish OBs.
7. **An unbroken OB is drawn as a single 10-bar line**, at the OB bottom (bullish) or top (bearish), with a `+OB` / `-OB`
   label. Only breakers are drawn as boxes, and their right edge is `timenow + 10 bars`, which is wall-clock time.
8. **IFVG boxes are dashed from the bar they are created on** when `i_BPR` is off. The box top is `high[2]` and the
   creation bar's low is below it, so the "entered" test `low < top` is already true (4.7).
9. **Right edges set at creation are overwritten on the same bar.** FVG: `n` becomes `n+8`. BPR: `max(rights)` becomes
   `n+8`. Liquidity: `n+10` becomes `n+3`. The later loops on the same bar do this. The exception is a liquidity zone that
   was already broken and is reshaped: it keeps `n+10` and stays frozen there.
10. **`iMSS = false` and `maxNWOG/maxNDOG = 0` probably do not do what the UI suggests** (HYPOTHESIS, 2.3 and 2.9).

## 3. Per-bar execution order

The order matters, because later steps overwrite earlier ones on the same bar.

1. General series (116–138), including `atr`, `meanBody`, `per`.
2. `draw(len, color.yellow)` (527): zig-zag update on a pivot high, then buyside liquidity creation; zig-zag update on a
   pivot low, then sellside liquidity creation; then MSS/BOS.
3. BOS cap (529–535). Killzone flags (538–541). Displacement flags (548–553). Imbalance flags (565–566).
4. Volume imbalance (569–595).
5. FVG initialisation and creation (597–644), then BPR (646–697), then FVG breaks (699–724), then BPR breaks (726–769).
6. NWOG / NDOG (771–819).
7. Liquidity extension and sweep (821–856).
8. OB swings, creation, breakers, polarity labels (858–929).
9. Last bar only: OB display (934–954), then Fibonacci (959–1118).
10. Plots: displacement shapes (1123–1134), killzone backgrounds (1139–1142).

## 4. Algorithms by module

### 4.1 Zig-zag (lines 244–249, 265–266, 344–363, 409–419)

The state is four arrays of fixed length 50, newest first: `d` (1 = swing high, -1 = swing low, 0 = empty), `x` (bar
index), `y` (price) and `b` (unused). The initial values are `d = 0` and `y = na`.

```
ph = ta.pivothigh(high, len, 1)          // high[1] is a pivot; confirmed one bar after the extreme
pl = ta.pivotlow (low,  len, 1)
if ph:
    if d[0] < 1:      unshift(d=1, x=n-1, y=high[1]); pop oldest   // new swing high
    elif ph > y[0]:   x[0] = n-1; y[0] = high[1]                   // higher high replaces the current leg's high
    (buyside liquidity scan, 4.6)
if pl:                                                             // mirror; runs after ph on the same bar
    if d[0] > -1:     unshift(-1, n-1, low[1]); pop
    elif pl < y[0]:   x[0] = n-1; y[0] = low[1]
    (sellside liquidity scan)
```

Points therefore alternate between high and low. Lower highs inside an up-leg are ignored, and so are higher lows inside
a down-leg. How Pine's `ta.pivothigh` / `ta.pivotlow` handle equal highs or lows is not visible in the code
(HYPOTHESIS).

### 4.2 Market structure: MSS and BOS (lines 465–535)

This runs on **every bar's close** when `showMS` is on. It is not gated by `per`. `MSS.dir` starts at 0.

```
iH = (d[2] == 1)  ? 2 : 1     // newest swing high that is NOT zig-zag point 0 (a high still forming is skipped)
iL = (d[2] == -1) ? 2 : 1     // same for lows
switch (first true case only):
  close > y[iH] and d[iH] == 1  and dir < 1   → dir = 1;  [Present: delete all MSS+BOS lines/labels]
                                               line (x[iH], y[iH]) → (n, y[iH]) in cMSSbl; label 'MSS' at x = round(avg(x[iH], n))
  close < y[iL] and d[iL] == -1 and dir > -1  → dir = -1; mirror in cMSSbr
  dir == 1  and close > y[iH] and iBOS        → BOS: dotted lime line + 'BOS' label at the same coordinates,
                                               unless y[iH] equals the level of the newest bullish BOS or of the newest bullish MSS
  dir == -1 and close < y[iL] and iBOS        → mirror (red)
if not iMSS: colour of newest MSS line/label (both sides) = na        // see 2.3 HYPOTHESIS
after draw(): if a BOS array has more than 200 entries → delete its oldest line and label
```

- An MSS is the first close beyond the reference swing against the current `dir`. The first break on the chart is
  always an MSS. A BOS is a further close beyond a new reference level in the same direction.
- The duplicate check compares the level only with the newest BOS and the newest MSS of that side.
- Lines end at the break bar and are not extended afterwards.

### 4.3 Displacement (lines 127–130, 548–553, 1123–1134)

```
L_body   = (high - mx < 0.36*body) and (mn - low < 0.36*body)
L_bodyUP = body > meanBody and L_body and close > open
L_bodyDN = body > meanBody and L_body and close < open
plot: if sDispl and per: lime label below an L_bodyUP bar, red label above an L_bodyDN bar
```

All comparisons are strict. `meanBody` is `na` for the first `len-1` bars, so nothing qualifies there. A doji never
qualifies. The shape is drawn on the displacement candle itself. The FVG test uses `L_body…[1]` (4.7).

### 4.4 Volume imbalance (lines 569–595)

```
bull VI: open > close[1] and close > close[1] and open > open[1]
         and high[1] < mn            // previous high below the current body
         and high[1] > low           // current lower wick reaches below the previous high
   draw: line (n-1, mx[1]) → (n+3, mx[1]); line (n, mn) → (n+3, mn); label 'VI' at (n+3, avg(mx[1], mn))
bear VI: open < close[1] and close < close[1] and open < open[1] and low[1] > mx and low[1] < high
   draw: line (n-1, mn[1]) → (n+3); line (n, mx) → (n+3); label at (n+3, avg(mn[1], mx))
keep the newest visVim (one shared array; delete the oldest)
```

In words: the two bodies do not overlap, but the wicks do. The zone runs from the previous body edge to the current body
edge. The two conditions exclude each other (`close > close[1]` against `close < close[1]`), so at most one VI forms
per bar. VI is not gated by `per`.

### 4.5 Order blocks and breakers (lines 289–333, 858–954)

```
swings(length):                                  // ta.highest/lowest over bars n-length+1 .. n
    os = high[length] > highest(length) ? 0 : low[length] < lowest(length) ? 1 : os
    os becomes 0 → top = {y: high[length], x: n-length, crossed: false}
    os becomes 1 → btm = {y: low[length],  x: n-length, crossed: false}
if showOB and per:
    if close > top.y and not top.crossed:        // close above the last swing high
        top.crossed = true
        over bars n-1 … top.x+1 (strictly between the swing bar and now):
            pick the bar with the lowest `min`; on ties the OLDER bar wins
        push bullish OB {top: that bar's `max`, btm: its `min`, loc: its time}
    for each bullish OB, oldest first:
        if not breaker: if min(open, close) < btm → breaker = true
        else: if close > top → remove the OB
              elif index < showBull and btm < top.y < top → blBrkConf = 1
    if blBrkConf rose from 0 to 1 and showLabels → label '▼' (bearCss, opaque) at (top.x, top.y)
bearish mirror: close < btm.y → bar with the highest `max`; breaker if max(open, close) > top;
                removed if close < btm; '▲' label (bullCss) when btm.y is inside a displayed bearish breaker
last bar only (showOB): delete all previous OB drawings, then for the newest showBull bullish, then showBear bearish:
    breaker  → box from loc to timenow + 10 bars, top..btm, fill *BrkCss, no border, xloc = bar_time
    unbroken → 2-px line at btm (bullish) / top (bearish) from loc to loc + 10 bars, label '+OB' / '-OB'
```

- A swing is registered only when `os` changes, so two swing highs in a row without a swing low keep the first one.
- The bullish OB is the lowest candle (body or wick, per `useBody`) between the swing high and the breakout bar. The
  bearish OB is the highest candle between the swing low and the breakdown bar.
- A bullish OB becomes a **breaker** when a candle body opens or closes below its bottom. It is **deleted** when a later
  close goes back above its top. The arrays have no size cap; deletion is the only removal.
- Polarity label: the latest swing high (`top.y`) lies inside one of the displayed bullish breakers, i.e. the broken
  support was retested as resistance. The label is drawn on the 0→1 edge of `blBrkConf`, so it can repeat if the condition stops and resumes.
- Present-mode edge case: a swing crossed before the 501-bar window is still "uncrossed" when the window starts. It can
  then create an OB on the first bar inside the window.
- Display order: bullish items are unshifted first and bearish items after. The array is therefore
  `[bear(k-1) … bear(0), bull(m-1) … bull(0)]`, where (0) is the newest of its side (see 2.15 item 6).
- HYPOTHESIS: the search reads `time[i]`, `min[i]` and `max[i]` up to `n - top.x` bars back. `max_bars_back(time, 1000)`
  (346) and `max_bars_back = 3000` (5) may cause a history-buffer error for a swing that is crossed very late.

### 4.6 Liquidity: buyside and sellside (lines 365–407, 421–463, 821–856)

```
on a zig-zag pivot high ph (after the zig-zag update), if showLq and per:
    tol = atr(10) / a                               // = ATR·margin/10
    for i = 0..49 over zig-zag points (newest first), swing highs only:
        if y[i] > ph + tol: stop                    // a clearly higher high ends the search
        if ph - tol < y[i] < ph + tol: count += 1; remember (x[i], y[i]) → ends as the OLDEST match;
                                       track highest and lowest matching price
    if count >= 3:
        mid = (highest match + lowest match) / 2
        if oldest-match bar == left edge of the newest buyside box: reshape that box to mid ± tol, right = n+10
        else: new box [left = oldest-match bar, mid ± tol, right = n+10], text 'Buyside liquidity' (bottom-left, tiny),
              no fill, no border; solid line at the oldest match's price from its bar to n-1; keep visLiq boxes
every bar, for each buyside zone not yet broken:
    right = n+3, line end = n+3
    close > bottom (first time) → fill cLIQ_B t90, delete the line
    close > top    (first time) → broken: right = n (frozen)
sellside: mirror with zig-zag lows, 'Sellside liquidity', close < top → filled, close < bottom → broken
```

- The scan usually includes the pivot just added (index 0). Lower swing highs (below `ph - tol`) are skipped, not a
  stop. The variable names `minP` / `maxP` are swapped: `minP` holds the highest match and `maxP` the lowest.
- The box height is always `2·tol` and is centred on the midpoint of the matched range. The line marks the oldest
  matching high.
- A reshape changes only the box. The line and the broken flags are kept.
- A sweep needs a **close** beyond the zone, not a wick.

### 4.7 FVG / IFVG (lines 565–566, 597–644, 699–724)

```
FVG : bullUP = L_bodyUP[1] and low  > high[2]     bearDN = L_bodyDN[1] and high < low[2]
IFVG: bullUP = L_bodyUP[1] and low  < high[2]     bearDN = L_bodyDN[1] and high > low[2]
if bullUP and per and shwFVG:
    if bullUP[1]: newest bullish box := (n-2, low) – (n+8, high[2])       // always FVG geometry, even in IFVG mode
    else: unshift box left n-2, right n, FVG: [high[2], low] / IFVG: [low, high[2]], active; pop oldest
break loop, i = 0..min(10, visBxs-1), active boxes: right = n+8;
    bullish: low < top → dashed (BPR off); low < bottom → [BPR off: fill *BR t95, dotted]; right = n; inactive
    bearish: high > bottom → dashed; high > top → broken
```

Box ranges above are written `[bottom, top]`. In IFVG mode the bullish box is `[low, high[2]]` by formula. It is usually
the overlap of the wicks of bar `n-2` and bar `n`, but not always: if bar `n` lies entirely below bar `n-2`, the box
spans both bars and the space between them. Its top is `high[2]` and the creation bar's low is below that, so with
BPR off it is dashed from the first bar. In IFVG mode, a consecutive update writes FVG geometry (an inverted box) that
is always broken on the same bar. The exact array, update and consecutive-gap behaviour (QUIRKS 1–3, 11) is in
`LUXALGO_BPR_SPEC.md` sections 3–5.

### 4.8 Balance Price Range (lines 646–697, 726–769)

When `i_BPR` is on, on **every bar** the script compares the newest bullish and the newest bearish FVG (index 0, active
or broken).

- **BPR_UP** (green, `cFVGbl`) is created when the bullish gap's bottom lies strictly inside the bearish gap:
  `dn.bottom < up.bottom < dn.top`. The box spans `[up.bottom, dn.top]`.
- **BPR_DN** (red, `cFVGbr`) is created when the bearish gap's bottom lies strictly inside the bullish gap:
  `up.bottom < dn.bottom < up.top`. The box spans `[dn.bottom, up.top]`.

The box `left` is `min` of the two FVG lefts and is the BPR's identity. A BPR with the same `left` is not created again,
and its geometry is never updated. `pos` is +1 if the creation bar closes above the box bottom, otherwise -1. In the
break loop:

- `pos = +1` acts as support. A low below the top makes the border dashed; a low below the bottom breaks it.
- `pos = -1` acts as resistance. A high above the bottom makes the border dashed; a high above the top breaks it.

The full specification, the execution order and all quirks (QUIRKS 1–11, including the broken-BPR case 6b) are in
`LUXALGO_BPR_SPEC.md`.

### 4.9 NWOG / NDOG (lines 771–819)

```
first bar: push maxNWOG empty entries to the NWOG array and maxNDOG to the NDOG array
every bar:  if dayofweek == Friday: friCp = close, friCi = n          // ends as the last Friday bar's close
if ta.change(dayofweek) != 0:                                        // first bar of a new calendar day
    if Monday and iNWOG: box (friCi, max(friCp, open)) – (n, min(friCp, open)), border cNWOG2, no fill, extend right;
                         dotted midline at avg(friCp, open) from n, extend right, cNWOG1; push, pop + delete oldest
    if iNDOG:            same with close[1] at bar n-1 and open at bar n; colours cNDOG1/cNDOG2
```

- The boxes and lines extend right forever and are never "filled" or broken. NWOG/NDOG ignore `per`.
- An NDOG is also created on Mondays.
- If a week has no Friday bar, the previous Friday is used.
- HYPOTHESIS (Pine runtime): `dayofweek` is evaluated in the symbol's exchange time zone. For a 24-hour FX symbol whose
  week opens on Sunday evening, the first "Monday" bar is then not the week's first bar. The NWOG would measure Friday
  close → Monday open, which includes Sunday trading, not the weekend gap. For the same reason an NDOG on a 24-hour
  market is a midnight-bar gap, usually tiny.

### 4.10 Fibonacci (lines 251–260, 959–1118; last bar only)

| `iFib` | Zone A | Zone B | x used | Precondition |
|---|---|---|---|---|
| FVG | newest bullish FVG box | newest bearish FVG box | older `left` → newer `right` | always true (arrays have `visBxs` entries); `na` boxes give no lines |
| BPR | newest BPR_UP | newest BPR_DN | older `left` → newer `right` | arrays non-empty, so `i_BPR` must be on |
| OB | `a_bx_ln_lb[size-1]` | `a_bx_ln_lb[size-2]` | line `x1` or box `left` of each (time) | at least 2 OB drawings |
| Liq | newest buyside | newest sellside | line `x1` or box `left` | always true (dummy entry) |
| VI | `Vimbal[1]` | `Vimbal[0]` | bar of each VI | at least 2 VIs |
| NWOG | `bl_NWOG[1]` | `bl_NWOG[0]` | older `left` → newer `right` (= its Monday bar) | at least 2 entries |

Rule shared by every case: the diagonal runs from the **older zone's outer edge** to the **newer zone's outer edge**.
"Outer" means the edge facing away from the other zone. Which zone is "lower" is decided by tops (FVG, BPR, NWOG), by
bottoms (OB, Liq), or by the lowest price (VI).

```
rt = max(x1, x2);  _0 = (rt == x1 ? y1 : y2);  _1 = (rt == x1 ? y2 : y1);  df = _1 - _0
diag (x1,y1)–(x2,y2) silver t50 dashed;   vert (rt,_0)–(rt,_0+1.618·df) silver t50 dotted
levels from rt to rt+plus at _0 + k·df, k ∈ {0, .236, .382, .5, .618, .786, 1.618}, and at _1
colours: 0 and 1 silver t5; .236 and .786 orange t25; .382, .618 and 1.618 yellow t25; .5 green t25
```

- Level 0 sits at the newer zone and level 1 at the older zone. 1.618 projects beyond the older zone.
- Only one set exists (`var` lines) and it is redrawn on the last bar, including on every realtime tick.
- If a precondition fails, `x1..y2` keep their initial value 0 and the lines are set to bar 0 or time 0 at price 0.
  How that displays is runtime-dependent (HYPOTHESIS).
- For `Liq`, the line of a swept zone has been deleted. The code falls back to the box edges only if a deleted line's
  getters return `na` (HYPOTHESIS).

### 4.11 Killzones (lines 538–541, 1139–1142)

```
ny = time(timeframe.period, '0700-0900', 'America/New_York') is not na and showNy   // showNy already includes showKZ
(same for London open/close in Europe/London and Asian in Asia/Tokyo)
bgcolor(per and ny ? nyCss : na)   … one call per session, colours t93, not editable in the Style tab
```

The background colours whole bars. On timeframes where a bar is longer than the session, the result depends on how the
runtime evaluates `time()` with a session (HYPOTHESIS).
