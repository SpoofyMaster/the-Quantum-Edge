# LuxAlgo_BPR: Fair Value Gaps + Balance Price Range for MetaTrader 5

> **NOT YET COMPILED in MetaEditor.** This indicator was written without access to a compiler. If MetaEditor
> shows errors or warnings when you press F7, send the full list of compiler messages and they will be fixed.

`LuxAlgo_BPR.mq5` is an MT5 custom indicator that reproduces the **Fair Value Gap (FVG)** and **Balance Price
Range (BPR)** logic of the TradingView script *"ICT Concepts [LuxAlgo]"* (Pine v5). It draws the zones live
on the chart. It also ports two related features: the "Show Displacement" markers and "Fibonacci between last:
BPR".

The calculation follows the specification in `research/indicators/LUXALGO_BPR_SPEC.md`, including the
unexpected behaviours that the specification calls QUIRK 1–10. The port copies those behaviours on purpose so
that it matches the Pine script exactly. The Python reference in `qe/indicators/luxalgo_bpr.py` follows the
same specification.

This is a charting tool. It does not trade, and nothing in it is evidence of a trading edge.

---

## 1. Licence and attribution

- Original logic: **© LuxAlgo**, "ICT Concepts [LuxAlgo]" (Pine v5). Licence:
  **CC BY-NC-SA 4.0**, <https://creativecommons.org/licenses/by-nc-sa/4.0/>.
- This indicator is a **port, which makes it a derivative work**, so the same licence applies:
  - **Non-commercial use only.** Do not sell it, and do not use it in a paid product or service.
  - **Attribution.** Keep the credit to LuxAlgo and the licence header in the source file.
  - **ShareAlike.** If you redistribute this file or a modified version, use CC BY-NC-SA 4.0.
- LuxAlgo has not affiliated with or endorsed this port.
- The deliberate changes from the original are listed in `research/indicators/LUXALGO_BPR_SPEC.md`, section 10.
  The main one: **Balance Price Range is ON by default here** (it is off in Pine).

## 2. Installation

1. In MT5, open **File → Open Data Folder**, then go to `MQL5/Indicators/`.
2. Create a folder `LuxAlgo_BPR` there, or use any folder you like, and copy `LuxAlgo_BPR.mq5` into it.
3. Open the file in MetaEditor (F4 in MT5) and press **Compile** (F7). The result must be **0 errors**.
   Warnings are acceptable, but please report them as well.
4. In MT5, refresh the **Navigator** (right-click → Refresh). Then drag **LuxAlgo_BPR** onto a chart, or
   double-click it.
5. Leave the defaults to get the Pine behaviour with BPR enabled.

Attach **only one instance per chart**. All instances name their objects with the same prefix `LXBPR_`, so a
second copy on the same chart would overwrite or delete the first copy's boxes.

## 3. Inputs

| Input | Default | Meaning |
|---|---|---|
| **Mode** | | |
| `InpMode` | Present | Pine `Mode`. **Present**: FVGs are created only on the last `InpPresentBars` + 1 bars. The window is anchored when the indicator loads (see section 6). **Historical**: the whole chart history is used. |
| `InpPresentBars` | 500 | Size of the Present window. The value 500 is hard-coded in Pine (`last_bar_index - bar_index <= 500`). Keep 500 for parity. |
| **Market structure** | | |
| `InpLength` | 5 | Pine `Length` (3–10; values outside are clamped). It is the period of the average body size `meanBody = SMA(|close-open|, Length)` used to detect displacement candles. |
| **Displacement** | | |
| `InpShowDisplacement` | false | Pine `Show Displacement`. Draws an up arrow under bullish displacement candles and a down arrow over bearish ones, inside the Present window only. A displacement candle has a body larger than `meanBody`, and both wicks are smaller than 36 % of the body. |
| **Fair Value Gaps** | | |
| `InpShowFVG` | true | Pine `Show FVGs`. With false, no FVG is ever created, so no BPR can exist either. |
| `InpBPR` | **true** | Pine `Balance Price Range` (Pine default: false). When it is on, the BPR boxes are drawn and the FVG boxes are hidden, as in Pine; the FVGs are still computed because they produce the BPRs. When it is off, the FVG boxes are drawn. |
| `InpFvgType` | FVG | Pine `Options`. **FVG**: the gap between the wicks of bar n-2 and bar n. **IFVG** (implied FVG): the overlap of those wicks. |
| `InpVisibleBoxes` | 2 | Pine `# Visible FVG's` (1–20, clamped). This is the number of zones kept per direction, for FVGs and for BPRs. It also changes the results, because only these zones are tracked. |
| `InpShowFVGinBPRmode` | false | Debug option, not in Pine. When BPR is on, it also draws the FVG boxes, so you can see which two gaps formed a BPR. In BPR mode, Pine never restyles FVG boxes, so they stay solid even after they break. |
| **Style** | | |
| `InpBullColor` | `C'0,230,118'` (#00E676) | Bullish FVG / BPR_UP colour. |
| `InpBullBreakColor` | `C'128,128,0'` (#808000) | Fill of a broken bullish zone. |
| `InpBearColor` | `C'255,82,82'` (#FF5252) | Bearish FVG / BPR_DN colour. |
| `InpBearBreakColor` | `C'255,0,0'` (#FF0000) | Fill of a broken bearish zone. |
| `InpFillTransp` | 90 | Fill transparency in Pine units (0 = opaque, 100 = invisible). |
| `InpBorderTransp` | 65 | Transparency of the border and the label. |
| `InpBreakTransp` | 95 | Transparency of a broken zone's fill. |
| **Fibonacci** | | |
| `InpFib` | NONE | Pine `Fibonacci between last:`. **BPR** draws the Pine Fibonacci set between the latest BPR_UP and the latest BPR_DN. It needs BPR on and at least one zone of each kind. |
| `InpFibExtend` | false | Pine `Extend lines`. Extends the 8 level lines to the right. |
| **Live / alerts / export** | | |
| `InpLiveBar` | true | Processes the forming bar like a Pine realtime bar: the zones can appear, change and disappear until the bar closes (repaint). With false, only closed bars are used, so nothing repaints, but the chart lags by one bar. |
| `InpAlertNewBPR` | false | Raises a popup `Alert` when a **new BPR is created on a closed bar**. It fires only for bars that close after the indicator loaded, never for history. The message gives the zone, its `pos`, and whether the creation bar already broke it. |
| `InpExportCSV` | false | Writes the parity export file once, right after the first full calculation (section 7). |

Fixed constants, the same as in Pine: wick limit 0.36 × body; break checks on zone indices 0..10; active zones
extend 8 bars to the right; Fibonacci level lines are 50 bars long.

## 4. How to read the chart

### BPR boxes (default mode)

A **Balance Price Range** is built from the **latest** bullish FVG and the **latest** bearish FVG, whether
those gaps are still active or already broken. The order in which the two gaps formed does not matter.

| Box | Colour | Condition | Box from → to |
|---|---|---|---|
| **BPR_UP** | green (`InpBullColor`) | the bullish gap's **bottom** lies strictly inside the bearish gap | bullish bottom → bearish top |
| **BPR_DN** | red (`InpBearColor`) | the bearish gap's **bottom** lies strictly inside the bullish gap | bearish bottom → bullish top |

The box's left edge is the left edge of the older of the two gaps. Its top is the **other** gap's top, not the
top of the true overlap (QUIRK 4). So a box can reach beyond the overlap of the two gaps. The geometry of a BPR
never changes after it is created (QUIRK 6). Each box is labelled "BPR" in its centre. Hover over a box to see
its kind, top, bottom, status and `pos`.

**`pos`** is fixed on the bar that creates the zone:

- `pos = 1`: that bar closed **above** the zone bottom. The zone acts as **support**. It is entered when a
  later low trades below the top, and it breaks when a low trades **below the bottom**.
- `pos = -1`: that bar closed at or below the zone bottom. The zone acts as **resistance**. It is entered when
  a later high trades above the bottom, and it breaks when a high trades **above the top**.
- `pos = 0` cannot occur (QUIRK 5).

**Border and fill:**

| Look | Meaning |
|---|---|
| solid border, faint base-colour fill | active and not yet entered |
| **dashed** border | price has entered the zone; still active |
| **dotted** border + break-colour fill | **broken**. The right edge is frozen at the bar that broke it. |
| right edge 8 bars ahead of the current bar | the zone is still active |

The colours do not show the direction of `pos`. Green always means BPR_UP and red always means BPR_DN; read
`pos` from the tooltip. A BPR can be created and broken on the same bar, when the wick of its creation bar
already crosses it.

### FVG boxes (`InpBPR = false`)

These are the same rules as Pine. A bullish FVG uses the base colour at 90 % transparency and is labelled
"FVG" or "IFVG". Its border turns **dashed** when a low enters the gap. It is **broken**, with a dotted border
and the break colour, when a low trades below its bottom. Bearish FVGs mirror this with highs.

### Fibonacci (`InpFib = BPR`)

The port draws a dashed diagonal between the two latest BPRs and a dotted vertical line. It also draws level
lines over 50 bars at 0, 0.236, 0.382, 0.5, 0.618, 0.786, 1 and 1.618 of the distance, with the Pine colours
and styles. Pine draws these lines from the state on the last bar, and so does the port.

## 5. Live bar and repainting

- **Closed bars** are processed once, into a "committed" state.
- **The forming bar**, with `InpLiveBar = true`, is processed on a **copy** of the committed state at every
  tick, and that copy is what you see. When the bar closes, its final OHLC is committed. This mirrors how Pine
  restores the committed state before each realtime tick. So a BPR shown on the forming bar can still vanish
  before the close; that is a repaint, and it is expected. Only closed-bar zones are final.
- Alerts fire only on closed bars, so they never repaint.

## 6. Present mode anchoring

Pine fixes `last_bar_index` when the script loads. The Present window therefore starts at
`load-time last bar − 500` and then grows as new bars arrive. The port does the same: it anchors the window
at every **full recalculation**, which happens in these cases:

- the indicator is attached;
- an input or the timeframe changes;
- MT5 reloads or extends the history;
- the oldest bar changes (for example when the terminal trims history at *Tools → Options → Charts → Max bars
  in chart*).

On TradingView, a reload re-anchors the window in the same way. Bars before the window are skipped. This does
not change the result: before the window, nothing can be created.

## 7. Parity check against the Python reference

1. Set `InpExportCSV = true`, either when attaching or by changing the input. The indicator writes
   `MQL5/Files/LuxAlgo_BPR_<symbol>_<period>.csv` (for example `LuxAlgo_BPR_XAUUSD_M1.csv`) once, right after
   its first full calculation. To find it, use *File → Open Data Folder → MQL5 → Files*. To write a fresh file,
   change any input or attach the indicator again. The Experts log prints the path.
2. Copy the file to the repo machine and run:

   ```
   python tools/luxbpr_parity.py <path/to/LuxAlgo_BPR_<symbol>_<period>.csv>
   ```

   The tool rebuilds the state from the exported bars with the Python reference. It then compares that state
   with the indicator's committed state, zone by zone.

File format (`# LuxAlgo_BPR export v1`; comma separated; `.` decimal point; prices printed with 17 significant
digits; lines may end in CRLF):

```
# LuxAlgo_BPR export v1
PARAMS,<Present|Historical>,<present_bars>,<length>,<show_fvg 0|1>,<bpr 0|1>,<FVG|IFVG>,<vis_boxes>,<per_start or NA>,<first_index>,<last_committed_index>
BAR,<index>,<time_unix>,<open>,<high>,<low>,<close>        one line per bar, first_index..last_committed_index
ZONE,<FVG_UP|FVG_DN|BPR_UP|BPR_DN>,<slot>,<exists 0|1>,<left>,<top>,<right>,<bottom>,<active 0|1>,<pos -1|1|NA>,<solid|dashed|dotted>,<broken_fill 0|1>
```

- `first_index` is `max(0, per_start − length − 3)` in Present mode and `0` in Historical mode.
- The ZONE lines hold the **committed** state after `last_committed_index`, which is the last closed bar. The
  forming bar is not included.
- There is one ZONE line per array slot, as in Pine. FVG_UP and FVG_DN have `vis_boxes` lines each. BPR_UP
  and BPR_DN have `vis_boxes` lines each when BPR is on, and **none** when BPR is off, because Pine leaves those
  arrays empty. An empty slot (Pine `box(na)`) is written as `0,NA,NA,NA,NA,0,NA,solid,0`.
- `time_unix` is the MT5 bar time, which is **broker server time** and not UTC. The comparison uses the bar
  index, not the time.

## 8. Known differences versus TradingView

- **Data feed.** MT5 broker bars, for example IC Markets bid OHLC on server time, differ from TradingView's feed
  in prices, session boundaries and missing bars. Different bars give different gaps, so the zones will not
  match TradingView bar for bar. For an exact comparison, run the logic on the **same** bars with the parity
  export (section 7). Do not compare screenshots.
- **Present window.** It is anchored at load or at a full recalculation (section 6). If the two platforms load
  at different times, their windows differ.
- **Transparency.** MT5 objects are opaque, so the port emulates Pine transparency by blending each colour with
  the chart background: `shown = (1 − t)·colour + t·background`. If you change the background colour, the
  blend updates on the next tick.
- **Scope.** The port covers only FVG, BPR, the displacement markers and the Fibonacci set between BPRs. Market
  structure (MSS/BOS), order blocks, liquidity, volume imbalance, NWOG/NDOG and killzones are **not** ported.
- **Displacement markers** are arrows (Wingdings 233/234) instead of Pine label shapes.
- **Fibonacci with BPR off.** In Pine, `Fibonacci = BPR` with BPR off leaves the line coordinates at 0, so Pine
  draws degenerate lines at price 0. The port draws nothing in that case.
- **Ticks.** Pine and MT5 sample intrabar ticks differently, so the forming-bar display can differ while the bar
  is open. Committed (closed-bar) results depend only on the final OHLC.
- **Rounding.** `meanBody` is a fresh sum of the last `Length` bodies divided by `Length`. Pine's `ta.sma` could
  differ in the last bit; that matters only when a body equals `meanBody` to about 1e-16.

## 9. Status

| Item | Status |
|---|---|
| Compiles in MetaEditor | **NOT YET COMPILED.** Please send the compiler messages. |
| Matches Pine / Python on the same bars | To be checked with the parity export (section 7) |
| Mechanical source check (`python3 tools/mql5_static_check.py mql5/Indicators/LuxAlgo_BPR`) | Brackets balanced. The tool's built-in list is short, so it flags standard MQL5 functions such as `SetIndexBuffer` and `PlotIndexSetInteger` as "possibly undefined". |
