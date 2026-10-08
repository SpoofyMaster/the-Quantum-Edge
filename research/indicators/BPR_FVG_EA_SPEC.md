# BPR + FVG Expert Advisor: specification (single source of truth)

**Owner request (2026-10-08).** Combine the LuxAlgo BPR/FVG features into **one MQL5 EA**. The EA must draw them like
the LuxAlgo indicator and use them to take **buy and sell setups**.

**Status.** The trading rules come from the owner's sketch ([`BPR_RETEST_PLAYBOOK.md`](BPR_RETEST_PLAYBOOK.md),
hypothesis **H-13**). They are an untested `HYPOTHESIS`. The defaults below were fixed from the sketch and the
playbook **before any market data was looked at**; none of them is tuned.

## Files that follow this spec

| Port | File |
|---|---|
| MQL5 EA | `mql5/BprFvgEA/BprFvgEA.mq5` and `mql5/BprFvgEA/include/*.mqh` |
| Python reference | `qe/strategies/bpr_fvg.py`: a detector with the same decisions, plus a bar-based execution simulator for backtests |

Parity between the two is checked by a C++ transliteration of the EA's pure modules
(`tests/test_bpr_fvg_ea_harness.py`).

## Hard rules (CLAUDE.md), enforced in code with no input to override them

- **Accounts.** Orders are sent only in the Strategy Tester and on **demo** accounts. On a **real account the EA is
  log-only**: it draws, detects and logs, but sends no orders. Live trading needs separate human approval.
- **Risk per trade.** At most 0.20 % of equity per position, including commission. The input is capped at 0.20.
- **Daily loss.** A planned daily loss of 1.00 % (FX day starts at 17:00 New York) triggers a lockout for the rest of
  that FX day. The input is capped at 1.00.
- **Banned methods.** No martingale, grid, averaging down, or larger size after losses: size depends only on equity
  and stop distance. Only one position or pending order per EA instance at a time.
- **Time limit.** Every position is closed **≤ 120 minutes** after entry. The input is capped at 120.
- **No look-ahead.** Decisions use **closed bars only**, through the LuxAlgo engine in **Historical** mode (spec §7 of
  `LUXALGO_BPR_SPEC.md`). Present mode looks ahead and is never used for decisions.

---

## 1. Inputs (MQL5 name = Python field; defaults)

### Display (LuxAlgo look, same meaning as the indicator)

| Input | Default | Notes |
|---|---|---|
| `InpShowZones` | true | Draw the LuxAlgo boxes. |
| `InpShowBPR` / `bpr` | true | Pine `i_BPR`. When true, BPR boxes are drawn and FVG boxes are hidden. When false, FVG boxes are drawn. **The engine always computes BPRs**, because setups need them; this input changes only the display. |
| `InpShowFVGinBPRmode` | false | Debug: also draw the FVG boxes when BPRs are shown. |
| `InpVisibleBoxes` / `vis_boxes` | 2 | 1–20. Engine array length. It does not change which zones are created. Setups keep their own copy of the zone. |
| `InpLength` / `length` | 5 | 3–10. |
| `InpFvgType` | FVG | **Setups need FVG.** With IFVG the EA displays only; trading is disabled and a warning is logged. |
| `InpShowDisplacement` | false | Markers on the last `InpDisplacementBars` (300) bars. |
| `InpFib`, `InpFibExtend` | NONE, false | Fibonacci between the last BPRs, as in the indicator. |
| `InpLiveBar` | true | Display only: the forming bar is processed on a copy, like the indicator. **Decisions never use it.** |
| Colours and transparencies | as indicator | `InpBullColor` C'0,230,118', `InpBullBreakColor` C'128,128,0', `InpBearColor` C'255,82,82', `InpBearBreakColor` C'255,0,0'; transparencies 90 / 65 / 95. |
| `InpShowTradeBoxes` | true | Position-tool overlay for each order (green target / red stop), §8. |
| `InpShowPanel` | true | Status panel. |

### Setups

| Input / Python | Default | Meaning |
|---|---|---|
| `InpSetupSource` / `source` | BPR | `BPR`, `FVG` or `BOTH`. |
| `InpDirection` / `direction` | BOTH | `BOTH`, `LONG_ONLY` or `SHORT_ONLY`. |
| `InpEntryMode` / `entry_mode` | LIMIT | `LIMIT` (R1: front-run limit near the far edge) or `CONFIRM` (R3: rejection candle, then a market order). |
| `InpEntryOffsetTicks` / `entry_offset_ticks` | 5 | δ for LIMIT. |
| `InpUseSweep` / `use_sweep` | true | Liquidity-sweep filter (§3.2). |
| `InpSweepWindow` / `sweep_window` | 30 | Bars. |
| `InpRangeBars` / `range_bars` | 30 | Bars. |
| `InpUseMss` / `use_mss` | true | Structure-shift requirement (§3.3). |
| `InpMssBars` / `mss_bars` | 20 | Bars. |
| `InpRallyBars` / `rally_bars` | 10 | Bars, for the measured-move origin. |
| `InpExpiryBars` / `expiry_bars` | 60 | Bars after creation. |
| `InpStopZoneMult` / `stop_zone_mult` | 1.2 | Stop = 1.2 zone heights beyond the far edge (sketch). |
| `InpMinRR` / `min_rr` | 1.0 | Minimum (TP1 − entry) / (entry − stop). |
| `InpMaxCostR` / `max_cost_r` | 0.15 | Maximum round-trip cost as a fraction of R. |
| `InpTpMode` / `tp_mode` | TP1_TP2 | `TP1_TP2` (partial at TP1, rest at TP2), `TP1_ONLY` or `TP2_ONLY`. |
| `InpTp1Fraction` / `tp1_fraction` | 0.5 | |
| `InpBreakEven` / `break_even` | true | Stop to entry + commission after TP1. |
| `InpMaxHoldMin` / `max_hold_min` | 120 | Capped at 120. |

### Session, risk and execution

| Input / Python | Default | Meaning |
|---|---|---|
| `InpServerMode`, `InpServerOffsetH` | NY+7, 0 | Server-time → UTC conversion (the same module as VideoStrategyEA; IC Markets is NY+7). |
| `InpUseSession` / `use_session` | true | Entries only from **08:00 Europe/London** to **14:45 America/New_York**, Monday–Friday. |
| `InpRiskPct` | 0.20 | Capped at 0.20. |
| `InpDailyLossPct` | 1.00 | Capped at 1.00. |
| `InpMaxTradesDay` | 0 | 0 = no limit. |
| `InpCommissionPerLotSide` / `commission_per_lot_side` | 3.50 USD | `UNVERIFIED`; check against your account. |
| `InpSlippageTicks` / `slippage_ticks` | 1 | Used in planned risk and in the Python fills. |
| `InpMaxSpreadPts` | 0 | 0 = off. Otherwise orders are skipped while the spread is above this. |
| `InpMagic` | 2610081 | |
| `InpDeviationPts` | 30 | |
| `InpWarmupBars` | 5000 | Closed bars processed at start for display and state. **No setup created during warm-up is traded.** |
| `InpLogCsv` | true | CSV logs in the Common Files folder. |

---

## 2. Bars, indices, engine

- **Bars.** Chart-timeframe bars, bid prices, closed bars only.
  - The EA keeps its own arrays `o[], h[], l[], c[], t[]` with absolute indices `0..`. Index 0 is the first warm-up bar.
  - A new bar is detected on the first tick whose bar time differs from the last processed bar.
  - Missed bars (after a disconnection) are fetched with `CopyRates` and processed in order.
- **Engine.** The LuxAlgo FVG/BPR engine as in `LUXALGO_BPR_SPEC.md`:
  - same code as the indicator;
  - **Historical** mode;
  - `perc_body` 0.36, `bx_back` 10, ext 8;
  - BPR always computed.
- **What `ProcessBar(n)` reports for bar n:**

  | Event | Meaning |
  |---|---|
  | `newBprUp` / `newBprDn` | A new BPR, at index 0 of its array. Both cannot be true at once. |
  | `newFvgUp` / `newFvgDn` | A new FVG at index 0. |
  | `updFvgUp` / `updFvgDn` | A consecutive-gap update of index 0, applied to an existing box. |

- **Displacement and FVG mode.** In FVG mode a bar can create or update at most one FVG.

## 3. Turning zones into candidates (at the close of bar `u`, after `ProcessBar(u)`)

### 3.1 Candidate geometry

`up = FVG_UP[0].box`, `dn = FVG_DN[0].box`, `Z` = the new zone's box. All values are copied at creation.

| Source | Dir | Edge `B` (bottom) | `T` (true top) | `Lo` / `Hi` (deep edge) | Break rule (bar `k > u`) |
|---|---|---|---|---|---|
| new BPR (UP or DN array), `pos = +1` | **+1 long** | `Z.bottom` | `min(up.top, dn.top)` | `Lo = min(up.bottom, dn.bottom)` | `l[k] < Z.bottom` |
| new BPR, `pos = −1` | **−1 short** | `Z.bottom` | `min(up.top, dn.top)` | `Hi = max(up.top, dn.top)` | `h[k] > Z.top` |
| new bullish FVG | **+1 long** | `Z.bottom` (= high[u−2]) | `Z.top` (= low[u]) | `Lo = B` | `l[k] < B` |
| new bearish FVG | **−1 short** | `Z.bottom` (= high[u]) | `Z.top` (= low[u−2]) | `Hi = T` | `h[k] > T` |

Notes:
- `h = T − B`. A candidate with `h ≤ 0` is dropped (reason `BAD_GEOMETRY`); this cannot happen in FVG mode, but the
  check stays.
- `pos = 0` cannot occur (QUIRK 5).
- A BPR that is already **inactive** on its creation bar (created and broken on the same bar) is dropped with reason
  `BROKEN_AT_CREATION`.

Candidate order within one bar:
1. the BPR from the UP array;
2. the BPR from the DN array;
3. the bullish FVG;
4. the bearish FVG.

They are filtered by `source` and `direction`; a candidate removed by these filters is never logged.

### 3.2 Sweep (computed at creation bar `u`; long shown, short mirrored)

```
s      = the bar with the LOWEST low in [u − sweep_window, u]   (ties → the LATEST bar)
legLow = l[s]
R      = min l over [s − range_bars, s − 1]
sweepOK = legLow < R
```

- The range window must exist (`s − range_bars ≥ 0`); otherwise the reason is `INSUFFICIENT_HISTORY`.
- **Short:** `s` = the bar with the highest high (ties → latest), `legHigh = h[s]`, `R = max h over [s − range_bars, s − 1]`,
  `sweepOK = legHigh > R`.
- If `use_sweep` is false, `s` is still computed (it anchors the structure shift and the extreme), and `sweepOK` is
  treated as true.
- If `use_sweep` is true and `sweepOK` is false, the candidate is dropped (reason `NO_SWEEP`).

### 3.3 Structure shift (MSS)

```
M = max h over [s − mss_bars, s − 1]        (long)        M = min l over [s − mss_bars, s − 1]   (short)
```

- `s − mss_bars ≥ 0` is required; otherwise the reason is `INSUFFICIENT_HISTORY`.
- **Long:** MSS happens on the first closed bar `m` with `s < m` and `c[m] > M`. **Short:** `c[m] < M`.
- At creation, bars `(s, u]` are checked; afterwards, each new closed bar is checked.
- If `use_mss` is false, the MSS is treated as having happened at creation.

### 3.4 Extremes for the targets

| Quantity | Long | Short | When |
|---|---|---|---|
| Rally extreme `X` | `max h over [s, k]` | `min l over [s, k]` | Updated on every closed bar `k` while the setup is `ARMED`; frozen once an order is decided. |
| Measured-move origin `O` | `min l over [u − rally_bars, u]` (window clipped at 0) | `max h over [u − rally_bars, u]` | Computed once at creation. |

## 4. Setup life cycle (per closed bar `u`, in this order)

Status values:

| Status | Meaning |
|---|---|
| `ARMED` | Waiting for MSS and entry. |
| `ORDERED` | A limit order is pending, or a market order was decided. |
| `FILLED` | In a position. |
| `CLOSED` | Position closed. |
| `DONE(reason)` | Never traded. |

Steps on each closed bar `u`:

1. **Engine:** `ProcessBar(u)`.
2. **FVG update refresh.**
   - If `updFvgUp` at `u` and the most recent FVG-long setup is `ARMED` and refers to `FVG_UP[0]` (no newer bullish
     FVG was created since it), copy the new `B`, `T` and `Lo` from `FVG_UP[0].box` and recompute `h`.
   - The same applies to `updFvgDn` and the most recent FVG-short setup.
   - Setups that are `ORDERED` or later keep their levels.
3. **Existing setups** (`ARMED` or `ORDERED`-pending), in creation order:
   - a. **Break:** if the break rule (§3.1) holds on bar `u`, the setup becomes `DONE(BROKEN)`; a pending order is
     cancelled.
   - b. **Expiry:** if `u − created > expiry_bars` and the setup is not filled, it becomes `DONE(EXPIRED)`, and a
     pending order is cancelled.
   - c. **Runaway (pending LIMIT only):** long `h[u] ≥ TP1`, short `l[u] ≤ TP1 − spread` (the short TP1 is an ask
     level). The setup becomes `DONE(RUNAWAY)` and the order is cancelled.
   - d. **Session cancel (pending only):** if `use_session` and the next bar's open is at or after the last entry time,
     the setup becomes `DONE(SESSION_END)` and the order is cancelled.
   - e. **ARMED setups:** update the extreme `X`; check the MSS (§3.3).
4. **New candidates** from bar `u` (§3.1–§3.3):
   - created `ARMED`, or `DONE(reason)`;
   - capacity is 128 tracked setups; above that the reason is `CAPACITY`;
   - setups created during warm-up (`u < trade_from`) become `DONE(WARMUP)` when warm-up ends;
   - **a candidate created on bar `u` takes part in step 5 on the same bar.**
5. **Entry decisions** for `ARMED` setups with the MSS done, in creation order. Each needs all of:
   - **slot free:** no pending order or position of this EA;
   - **session OK** at the next bar's open;
   - **risk OK:** no lockout, and the trade limit is not reached;
   - **spread OK.**

   If one of these fails, the setup stays `ARMED` and is tried again on the next bar. At most one order is decided per
   bar.
   - **LIMIT:**
     - **Prices.** Spread `sp` = the spread at the decision moment, which is the first tick of bar `u+1` (Python: the
       modelled spread of bar `u+1`). Tick size is `tk`.
     - **Long:**
       - `P = B + δ·tk + sp` (ask buy-limit price);
       - `SL = min(B − stop_zone_mult·h, Lo − 2·sp)` (bid level);
       - `TP1 = X − 2·sp` (bid);
       - `TP2 = P + (X − O)` (bid).
     - **Short:**
       - `P = T − δ·tk` (bid sell-limit price);
       - `SL = max(T + stop_zone_mult·h, Hi + 2·sp) + sp` (ask level);
       - `TP1 = X + 2·sp` (ask);
       - `TP2 = P − (O − X)` (ask).
     - **Marketability.** If the market is already through `P`, the setup waits for the next bar (stays `ARMED`). Long:
       `ask ≤ P`, where the decision ask is `c[u] + sp` for Python and parity. Short: `bid ≥ P`, with the decision bid
       `c[u]`.
     - **Checks** (if one fails, the setup stays `ARMED` and is retried on the next bar; levels are recomputed with the
       new `X`):
       - `risk = |P − SL|`;
       - `rr1 = |TP1 − P| / risk ≥ min_rr`, and TP1 must be on the profit side;
       - `cost_R = (sp + comm_price + 2·slippage_ticks·tk) / risk ≤ max_cost_r`, where `comm_price` is the round-trip
         commission per lot divided by the value of a 1.0 price move per lot.
     - If `tp_mode == TP1_TP2` and TP2 is not beyond TP1, the trade uses TP1 only.
     - **Result:** the setup becomes `ORDERED`, and the intent `PLACE_LIMIT(id, dir, P, SL, TP1, TP2)` is emitted. All
       levels are rounded to the tick.
   - **CONFIRM:**
     - **Trigger.** On the same bar `u`, the MSS must already be done and the zone not broken (step 3a ran first).
       - **Long:** `l[u] ≤ B + h/4`, `c[u] ≥ B + h/2` and `c[u] > o[u]`.
       - **Short:** `h[u] ≥ T − h/4`, `c[u] ≤ T − h/2` and `c[u] < o[u]`.
     - **Levels.** The expected entry is `P = c[u] + sp` for longs (ask) and `P = c[u]` for shorts (bid). `SL`, `TP1` and
       `TP2` use the same formulas, checks and rounding as LIMIT.
     - **Result:** the setup becomes `ORDERED`, and the intent `MARKET(id, dir, P, SL, TP1, TP2)` is emitted. The fill is
       at the next bar's open.

The detector is **pure**. It gets bars plus an environment and emits intents:
- environment: `slot_free`, `session_entry_ok`, `session_cancel`, `risk_ok`, `spread_ok`, `sp`;
- intents: `PLACE_LIMIT`, `MARKET`, `CANCEL(id, reason)`.

The executor reports back with `filled(id)`, `cancelled(id, reason)` and `closed(id)`.

## 5. Execution and trade management

**EA:** real orders through `CTrade`.

- **Order settings.** Filling mode from the symbol; prices normalised to the tick; stops/freeze levels and margin
  checked before sending.
- **Server-side levels.**
  - The order carries `SL`, plus `TP2` (`TP1_TP2` or `TP2_ONLY` mode) or `TP1` (`TP1_ONLY` mode).
  - In `TP1_TP2` mode, `TP1` is **virtual**. When the bid reaches TP1 (ask for shorts), the EA closes `tp1_fraction` of
    the volume, rounded down to the volume step. If that leaves less than the minimum volume, it closes everything.
  - If `break_even` is on, the stop then moves to `entry ± comm_price` (in the profit direction).
- **Pending limits** expire through the detector's cancel intents. As a safety net they also carry an expiration time
  where the symbol allows it.
- **Time stop.** Close at market when `now ≥ fill_time + max_hold_min`.
- **Before the rollover.** Also close at 16:44 New York on trading days.
- **Restart.** A position carrying this EA's magic number is managed again: its SL/TP are on the server, the time stop
  comes from `POSITION_TIME`, and TP1 is read from the comment `BF|<id>|<TP1>`. A pending order left from before the
  restart is deleted.

**Python simulator** (bar-based, for backtests; `ask = bid + spread_k` for bar `k`):

- **Limit fill (long).** The first bar `k ≥ u+1` with `ask_low ≤ P` fills at `min(P, ask_open_k)`. The decision steps
  for bar `k` run after its fill check.
  - On the fill bar, if `bid_high ≥ TP1` as well, the order is **cancelled instead** (`RUNAWAY_SAME_BAR`). This is
    conservative and follows `qe/video_strategy/engine.py`.
  - On the fill bar, if `bid_low ≤ SL`, it is a **loss** on that bar.
  - Shorts mirror this: a sell limit fills when `bid_high ≥ P`, at `max(P, bid_open)`.
- **Market fill:** `ask_open[u+1] + slippage` for longs, `bid_open[u+1] − slippage` for shorts.
- **Exits on bars after the fill**, checked in this order within a bar:
  1. **Stop:** `bid_low ≤ SL` (long), exit at `SL − slippage`. Stop first if both levels are touched.
  2. **TP1 partial:** `bid_high ≥ TP1`. The stop moves to break-even **from the next bar**.
  3. **TP2:** `bid_high ≥ TP2`, the rest at TP2. TP1 and TP2 can both fill on the same bar.
- **Time stop:** exit at the `bid_open` of the first bar whose open is at or after `fill_time + max_hold_min`, minus
  slippage.
- **Rollover:** a forced exit at the `bid_open` of the first bar at or after 16:44 New York.
- **R accounting:**
  - `R_unit = |P − SL| + slippage_ticks·tk + comm_price` (planned risk per unit, costs included, as in
    `qe.risk.size_position`);
  - `trade R = Σ fraction·(exit − P)·dir / R_unit − comm_price / R_unit`;
  - the spread is inside `P` and the exits, because entries are on the ask and long exits on the bid.
- **Daily lockout:** −5 R realised (1 % / 0.2 %) within one FX day.

## 6. Risk sizing (EA)

```
lots = floor( equity·risk% / ( LossPerLot(|P − SL| + slippage·tk) + 2·commission_per_lot_side ) / step ) · step
```

- **Rounding.** The result is never rounded up to the minimum volume; if it falls below the minimum volume, the order
  is skipped (reason `SIZE_BELOW_MIN`).
- **Pre-trade check.** Daily check before each order: `realised loss today + planned risk ≤ daily limit`.
- **Same formula as** `qe/risk.py` and `VideoStrategyEA/include/RiskManager.mqh`.

## 7. Logging (EA)

CSV files go to the Common Files folder (`FILE_COMMON`) and carry the symbol and timeframe in the name.

| File | Columns |
|---|---|
| `BFEA_setups_<sym>_<tf>.csv` | `id`, `source`, `dir`, `created_time`, `B`, `T`, `h`, `sweep_bar_time`, `M`, `mss_time`, `status`, `reason`, `P`, `SL`, `TP1`, `TP2`, `decision_time` |
| `BFEA_trades_<sym>_<tf>.csv` | `id`, `dir`, `entry_time`, `entry`, `lots`, `SL`, `TP1`, `TP2`, `exit_time`, `exit`, `exit_reason`, `pnl_usd`, `R`, `planned_risk_usd` |

The Experts log gets one line per setup state change.

## 8. Display

- **LuxAlgo zones.** Exactly as the indicator: BPR boxes, or FVG boxes when `InpShowBPR = false`, plus the optional
  debug FVGs, displacement markers and Fibonacci between the BPRs.
  - The forming bar is shown when `InpLiveBar` is on.
  - Object prefix `BFEA_`; colours are blended with the chart background.
- **Trade boxes.** When an order is decided, draw a **position-tool overlay** like the owner's sketch:
  - a green rectangle from `P` to the final target (TP2, or TP1);
  - a red rectangle from `P` to `SL`;
  - a dashed line at TP1 (`TP1_TP2` mode);
  - all from the decision bar to +20 bars;
  - the label `L#id` or `S#id`.
  - After cancellation the rectangles turn grey. The last 20 overlays are kept.
- **Panel** (top-left labels):
  - mode: `TESTER`, `DEMO` or `REAL: LOG-ONLY`;
  - source, entry mode and direction;
  - setups armed;
  - order or position state;
  - today's realised result in R and the lockout state;
  - the last event.

## 9. Parity harness contract

The detector is driven by bars plus an environment and emits one JSON line per intent and per status change:

```
{"n": u, "id": k, "ev": "ARMED|DONE|PLACE_LIMIT|MARKET|CANCEL|MSS", "dir": ±1, "src": "BPR|FVG",
 "reason": "...", "P": ..., "SL": ..., "TP1": ..., "TP2": ...}
```

**Harness environment.** Both ports run under the same environment:
- the session is always open, risk is always OK, the spread is a constant `sp`;
- `slot_free` = no setup in `ORDERED` or `FILLED`;
- orders never fill, so they end only through the detector's own cancellations (`BROKEN`, `EXPIRED`, `RUNAWAY`).

The Python port must produce the identical sequence. Prices are compared to 1e-9 times the price scale.

## 10. Defaults and what they are based on

| Default | Source |
|---|---|
| BPR, LIMIT entry, the stop of 1.2 zone heights, the measured-move TP2 | The sketch: the entry at the BPR bottom edge, about 1.2 h below for the stop, the target ≈ the rally length. |
| Sweep (D under B) and structure shift (the rally breaks C) | The playbook checklist. |
| 60-bar expiry, the session window, 120 min, 0.20 % / 1 % | The playbook and CLAUDE.md. |

Both ports must use these exact values as defaults. Any other value is a **new trial** and must be registered
(`results/trial_registry.jsonl`).
