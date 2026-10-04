# Algorithm specification (machine-readable rules)

Implements [`STRATEGY_RULEBOOK.md`](STRATEGY_RULEBOOK.md). Every definition below is implemented identically in
`qe/video_strategy/` (Python reference, unit-tested) and `mql5/VideoStrategyEA/` (MQL5). Function names are the same in
both. No subjective words remain: every "strong", "clean", "immediately" is either a number below or explicitly *not used*.

## 0. Data and notation
- M1 **bid** bars of the traded symbol, index t, open time τₜ (UTC), fields oₜ hₜ lₜ cₜ; spread sₜ ≥ 0 (ask = bid + s).
  A bar is usable only after it **closes** (at τₜ + 60 s). Decisions at the close of bar t; market fills at oₜ₊₁.
- DXY M1 bars xₜ with the same timestamps (missing minutes are skipped, never forward-filled into the future).
  Synthetic DXY (A-10): Xₜ = 50.14348112 · EURUSD⁻⁰·⁵⁷⁶ · USDJPY⁰·¹³⁶ · GBPUSD⁻⁰·¹¹⁹ · USDCAD⁰·⁰⁹¹ · USDSEK⁰·⁰⁴² · USDCHF⁰·⁰³⁶
  from closes; bar = (o = Xₜ₋₁, h = max(o, c), l = min(o, c), c = Xₜ).
- Candle c: period P (60 min for H1, 15 for M15), open time T_c (a multiple of P in UTC; broker server offsets are whole
  hours, so server-aligned candles coincide). Bars of the candle: C = { t : T_c ≤ τₜ < T_c + P }.
  Close-minute of bar t: m(t) = (τₜ − T_c)/60 + 1 ∈ [1, P].
- ATR_n(t) on any series = (1/n) Σ_{j=t−n+1..t} TRⱼ, TRⱼ = max(hⱼ, cⱼ₋₁) − min(lⱼ, cⱼ₋₁) (simple mean, as MT5 `iATR`).
- Parameters and defaults: see §9.

## 1. `IsTradingCandle(T_c)` — MKT-5, MKT-6
Let d = UTC date of T_c, `start(d)` = 10:00 Asia/Tokyo on d (= 01:00 UTC; Tokyo has no DST),
`end(d)` = 11:00 Europe/London on d converted to UTC (10:00 UTC in BST, 11:00 UTC in GMT).
- `ASIA2_TO_LONDON4` (default): start(d) ≤ T_c ≤ end(d), weekday(d) ∈ Mon..Fri.
- `STRICT`: T_c ∈ { start(d), 08:00 Europe/London on d } and weekday(d) ∈ Mon..Fri.
- `ALL`: any T_c not inside the rollover blackout (16:45–17:30 New York).

## 2. `ComputeMtfContext(T_c)` — CTX-1…CTX-6 (run once per candle, on bars that closed before T_c)
1. W = M1 bars with T_c − 300 min ≤ τ < T_c. If |W| < 0.8 · 300 → `UNDEFINED`.
2. Aggregate W into M5 bars aligned to multiples of 5 min (o = first open, h = max, l = min, c = last close).
   a = ATR₁₄ of those M5 bars at the last one (needs ≥ 15 bars, else `UNDEFINED`); θ = `ZigZagAtrMult` · a.
3. **ZigZag(θ)** over the M5 bars k = 0..K−1 (deterministic, high/low based):
   ```
   state: dir ∈ {0,+1,−1}; hi, hiIdx, lo, loIdx (dir = 0 only); ext, extIdx; pivots = []
   k = 0: hi = h0, lo = l0, hiIdx = loIdx = 0
   for k ≥ 1:
     if dir == 0:
        if h_k > hi: hi, hiIdx = h_k, k
        if l_k < lo: lo, loIdx = l_k, k
        if hi − lo ≥ θ:
           if hiIdx > loIdx or (hiIdx == loIdx and c[hiIdx] ≥ o[hiIdx]): pivots += (loIdx, lo, LOW); dir = +1; ext, extIdx = hi, hiIdx
           else:                                                pivots += (hiIdx, hi, HIGH); dir = −1; ext, extIdx = lo, loIdx
     elif dir == +1:
        if h_k > ext: ext, extIdx = h_k, k
        elif ext − l_k ≥ θ: pivots += (extIdx, ext, HIGH); dir = −1; ext, extIdx = l_k, k
     else:
        if l_k < ext: ext, extIdx = l_k, k
        elif h_k − ext ≥ θ: pivots += (extIdx, ext, LOW); dir = +1; ext, extIdx = h_k, k
   tentative = (extIdx, ext) if dir ≠ 0
   ```
4. Legs: completed legs between consecutive pivots, plus the in-progress leg (last pivot → tentative).
   Sizes Lᵢ = |priceᵢ − priceᵢ₋₁| over **completed** legs only, i = 1..n.
5. Pullback ratios ρᵢ = min(Lᵢ, Lᵢ₋₁) / max(Lᵢ, Lᵢ₋₁), i = 2..n (symmetric: a 40% pullback and the following impulse both
   give 0.4; equal legs give 1). If n < 3 (fewer than 2 ratios) → `UNDEFINED`. ρ̃ = median(ρ).
6. Condition: ρ̃ < `TrendMaxRatio` (0.50) → `TREND`; ρ̃ < `RangeMinRatio` (0.75) → `TRENDING_RANGE`; else `RANGE`.
7. Direction (info): last two HIGH pivots H₁ < H₂ and last two LOW pivots L₁ < L₂ → `BULL`; both descending → `BEAR`;
   else `NEUTRAL`.
8. Reference legs for location (in-progress leg included): `lastDownLeg` = most recent leg going down (start high Hₛ,
   end low Lₑ); `lastUpLeg` = most recent leg going up (start low Lₛ, end high Hₑ). Missing → location undefined.

`Tradable(T_c)` ⇔ condition ∈ {RANGE, TRENDING_RANGE}.

## 3. `LocationLevel(dir, ctx)` — EXT-4 / COR-2
Fraction f: `HALF` mode → f = `MinLocationRetrace` (0.50). `CONDITION_AWARE` → RANGE: 0.75; TRENDING_RANGE: 0.50 if the
trade is in the MTF direction (sell in BEAR / buy in BULL), 1.00 if against it, 0.75 if NEUTRAL.
- Sell (bullish extension must reach up): level⁺ = Lₑ + f · (Hₛ − Lₑ) of `lastDownLeg`. `LocationOK` ⇔ E ≥ level⁺.
- Buy (bearish extension must reach down): level⁻ = Hₑ − f · (Hₑ − Lₛ) of `lastUpLeg`. `LocationOK` ⇔ E ≤ level⁻.

## 4. `UpdateExtension(t)` — EXT-1…EXT-6 (every closed bar t ∈ C)
Bullish extension (sell candidate), using only bars u ∈ C with u ≤ t:
- E = max hᵤ; e = **first** u with hᵤ = E.
- O = min_{u ≤ e} lᵤ; o = **last** u ≤ e with lᵤ = O. (First-high / last-low make the duration conservative.)
- D = (τₑ − τₒ)/60 + 1 minutes; S = E − O.
- PB = max_{k ∈ (o, e]} ( max_{j ∈ [o, k−1]} hⱼ − lₖ )⁺ / S   (0 if e = o).
- `ExtensionValid⁺(t)` ⇔ S > 0 ∧ D ≥ `MinExtMinutes` (18) ∧ PB < `MaxExtPullback` (0.50) ∧ LocationOK(sell, E)
  ∧ [EXT-5: E > high of the previous candle, if enabled] ∧ [EXT-6: S ≥ `MinExtAtrMult` · ATR₁₄(M1, e), if > 0].
Bearish extension (buy candidate) is the exact mirror: E = min l (first), O = max h before it (last),
PB = max (hₖ − min_{j<k} lⱼ)⁺ / S.

## 5. `Pivots(N)` — SHF-1
Bar k is a **pivot high** if hₖ > hₖ₋ᵢ and hₖ ≥ hₖ₊ᵢ for i = 1..N; a **pivot low** if lₖ < lₖ₋ᵢ and lₖ ≤ lₖ₊ᵢ.
It is *known* at the close of bar k + N, never earlier. Default N = `PivotStrength` = 2. Bars outside the candle may serve as
the i-neighbours of a pivot inside it.

## 6. `DetectShift(t)` — SHF-2…SHF-4 (bearish shift = sell signal; the bullish one mirrors it)
Given the bullish extension (E, e, O, o) at bar t:
- PL = the most recent pivot low k with o ≤ k < e and k + N ≤ t (the *protected low*); none → no shift.
- PH = some pivot high k′ with o ≤ k′ < k(PL) and k′ + N ≤ t (the high that the extension "took out"; E > h_{k′}
  holds by construction); none → no shift.
- Bar t is a **bearish type-3 shift** ⇔ t > e ∧ `Break(t, PL)` ∧ `ShiftStartMin` ≤ m(t) ≤ `ShiftEndMin` ∧
  `ExtensionValid⁺` at e, where `Break` = cₜ < PL − `MinBreakAtr`·ATR₁₄ (CLOSE, default) or lₜ < PL − … (WICK).
- Each extreme e is evaluated at most once per direction (the gate result is final for that extreme); a new extreme
  allows a new evaluation. Once a trade is taken (or a pending order is cancelled) the candle is finished (SHF-5).

## 7. `CorrelationGate(t, dir)` — COR-1…COR-4 (DXY bars of the same candle, up to and including bar t)
For a gold **sell** (DXY must show a DXY **buy** setup); mirror everything for a gold buy.
- X₀ = DXY open of the candle (open of the first DXY bar in C). X⁺ = max DXY high since T_c, X⁻ = min DXY low since T_c,
  e_x = first bar with DXY low = X⁻. x(e) = DXY close at gold's extreme bar e.
- **COR-1** `NotSameDirection` ⇔ (X₀ − X⁻) > (X⁺ − X₀) ∧ x(e) < X₀.
- **COR-2** `OppositeHalf` ⇔ X⁻ ≤ level⁻_DXY, i.e. `LocationLevel(buy, ctx_DXY)` from DXY's own MTF context at T_c.
- **COR-3** `OppositeShift` ⇔ ∃ t_x with e_x < t_x ≤ t, t_x ∈ C, such that DXY bar t_x is a **bullish** type-3 shift of
  DXY's bearish drive (DXY's §6 mirror with DXY's own pivots, protected high PHₓ between DXY's drive origin and e_x).
  No timing window and no 18-minute test on DXY (COR-4).
- `FULL` ⇔ COR-1 ∧ COR-2 ∧ COR-3; `MIRROR_DIRECTION` ⇔ COR-1 ∧ COR-2; `OFF` ⇔ true.
- Missing DXY data for the candle → gate fails (`INV_DXY_NO_DATA`), never passes by default.

## 8. Orders, stop, target, exits — ENT-1…ENT-3, SL-1, TP-1, MGT-1…MGT-3
- buf = max(`StopBufferPoints` · point, `StopBufferAtr` · ATR₁₄(M1, t)).
- Sell: SL = E + s + buf; TP_level = O + 0.5 · (E − O); TP_order = TP_level + s (if `AdjustSellTpForSpread`), where s is the
  spread at the entry bar. Buy: SL = E − buf; TP_level = TP_order = O − 0.5 · (O − E).
- **BREAK**: entry at oₜ₊₁ (sell at bid − slippage; buy at ask + slippage).
- **PULLBACK_50** (sell): B = min l over (e, t]; limit = B + 0.5 · (E − B). For each later bar k while pending:
  if lₖ ≤ TP_level → cancel (`INV_TARGET_REACHED`; a bar touching both the target and the limit is treated as
  target-first, i.e. no trade — conservative); else if hₖ ≥ limit → filled at max(limit, oₖ) (bid); else if lₖ < B →
  B = lₖ and recompute the limit; when the candle ends → cancel (`INV_NO_PULLBACK`). Buy limits are placed one spread
  above the bid-chart level (they fill when the bid touches it). A bar that fills is then checked for SL/TP in the same
  bar, stop first.
- ENT-3: reject if (sell) entry ≤ TP_order or SL ≤ entry; (buy) entry ≥ TP_order or SL ≥ entry.
- Exits on the exit side (sell exits on ask = bid + s): stop first, then target; a bar that opens beyond the stop fills at
  its open; stops get `SlippageTicks` adverse; targets fill at the TP price (no positive slippage); time exit at the close of
  the bar 120 minutes after entry, or before the rollover blackout.

## 9. Parameters (defaults = "VIDEO" profile)
| Name | Default | Rule | Name | Default | Rule |
|---|---|---|---|---|---|
| CandleMinutes | 60 | MKT-4 | MinExtMinutes | 18 | EXT-2 |
| SessionPreset | ASIA2_TO_LONDON4 | MKT-5 | MaxExtPullback | 0.50 | EXT-3 |
| MtfLookbackMin | 300 | CTX-1 | LocationMode / MinLocationRetrace | HALF / 0.50 | EXT-4 |
| ZigZagAtrMult | 2.0 | CTX-2 | RequirePrevCandleBreak | false | EXT-5 |
| TrendMaxRatio / RangeMinRatio | 0.50 / 0.75 | CTX-3 | MinExtAtrMult | 0 (off) | EXT-6 |
| MinCoverage | 0.80 | CTX-5 | PivotStrength | 2 | SHF-1 |
| BreakConfirm | CLOSE | SHF-2 | ShiftStartMin / ShiftEndMin | 22 / 52 | SHF-3 |
| MinBreakAtr | 0 (off) | SHF-2 | DxyMode | FULL | COR |
| EntryMode | BREAK | ENT-1/2 | StopBufferAtr / StopBufferPoints | 0.10 / 0 | SL-1 |
| TargetMode | EXT50 | TP-1 | AdjustSellTpForSpread | true | TP-1 |
| MaxHoldMinutes | 120 | MGT-2 | RiskPct / DailyLossPct | 0.20 / 1.00 | RSK |

M15 timing preset (experimental, A-07): CandleMinutes 15, MinExtMinutes 5, ShiftStartMin 6, ShiftEndMin 13.
`CandleMode` = H1 (default) / M15 / H1_AND_M15: one independent tracker per candle timeframe (each with its own
timings, context and signals); the position limit (one at a time) is shared. Added after the Phase-14 replay showed that
three of V's six examples use 15-minute candles (VIDEO_REPLICATION_TEST.md, finding 2).

## 10. Causality guarantees (tested)
1. Context for candle c uses only bars with τ < T_c. 2. Extension and pivots at bar t use bars ≤ t, pivots only once known
(k + N ≤ t). 3. DXY gate at t uses DXY bars ≤ t. 4. Fills at bar t + 1 or later. `tests/test_video_strategy.py` truncates
the future (and separately scrambles it) and checks that every signal up to t is unchanged.
