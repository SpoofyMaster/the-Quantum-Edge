# Pseudocode (mirrors `mql5/VideoStrategyEA/VideoStrategyEA.mq5` and `qe/video_strategy/engine.py`)

```text
GLOBALS
  setup            : per-candle record { id, candleOpen, ctxGold, ctxDxy, state, bull: ExtTrack, bear: ExtTrack,
                                         signalDir, entry, sl, tp, limit, B, reasons[] }
  position         : open position or none
  lastBarTime      : open time of the last processed closed M1 bar

OnInit()
  validate inputs (risk ≤ 0.20, daily loss ≤ 1.00, timings 0 < start ≤ end ≤ candle minutes)
  resolve DXY source: DxySymbol in Market Watch ? BROKER : SYNTHETIC (select the 6 pairs) ; none → refuse to init
  real account ? tradingAllowed = false (log-only) : true
  create panel / objects if visual debug is on

OnTick()
  if new M1 bar opened on the gold chart:            # i.e. the previous bar has closed
     for each closed M1 bar not yet processed (catch-up after disconnects, in time order):
        OnClosedBar(bar)
  ManagePosition()                                    # time stop / rollover on every tick; SL/TP live at the broker
  UpdatePanel()

OnClosedBar(bar t)
  UpdateRiskDay(t)                                    # FX day 17:00 NY, 1% lockout
  T = CandleOpen(t)
  if T != setup.candleOpen:                           # first closed bar of a new candle
     FinishSetup(setup)                               # log reason if no trade (INV_*)
     setup = NewSetup(T)
     if !IsTradingCandle(T):            setup.Finish(INV_SESSION)
     else:
        setup.ctxGold = ComputeMtfContext(gold, T)
        setup.ctxDxy  = ComputeMtfContext(dxy,  T)    # needed for COR-2
        if ctxGold.condition == TREND:      setup.Finish(INV_CONTEXT_TREND)
        if ctxGold.condition == UNDEFINED:  setup.Finish(INV_CONTEXT_UNDEFINED)
  if setup.finished: return

  switch setup.state
    TRACK:                                            # both directions, every bar
       for dir in {SELL (bullish extension), BUY (bearish extension)}:
          ext = UpdateExtension(dir, bars of candle ≤ t)          # §4: E, e, O, o, D, PB, LocationOK
          if !ext.valid: continue
          if DetectShift(dir, ext, t):                            # §6: pivots known ≤ t, close beyond PL, minute 22–52
             gate = CorrelationGate(dir, ext, t)                  # §7: COR-1/2/3 on DXY bars ≤ t
             log("[SETUP #id] shift", dir, ext, PL, minute)
             if !gate.pass: log("[SETUP #id] DXY reject", gate.reason); continue   # other direction may still fire
             if safety blocks (spread, lockout, position open, max trades): setup.Finish(SAFE_*); return
             PlaceEntry(dir, ext, t)                              # BREAK: market at next open; PULLBACK_50: pending limit
             setup.state = ORDER; break
       if MinuteOfCandle(t) ≥ ShiftEndMin and setup.state == TRACK:
          setup.Finish(best reason among INV_NO_EXTENSION / INV_LOCATION / INV_NO_SHIFT / INV_DXY_*)

    ORDER (PULLBACK_50 only; BREAK fills immediately on the next tick):
       update B, limit (re-anchor if a new low/high extends the breaking leg)
       if price traded TP_level before fill: cancel → Finish(INV_TARGET_REACHED)
       if price exceeded the extreme E:      cancel → Finish(INV_STRUCTURE_BROKEN)
       if candle ended:                       cancel → Finish(INV_NO_PULLBACK)

PlaceEntry(dir, ext, t)
  sl, tp = StopAndTarget(dir, ext, spread, ATR14)                  # §8
  if reward ≤ 0 or risk ≤ 0: Finish(INV_TARGET_REACHED); return
  lots = SizeLots(|entry − sl|)                                    # 0.20% incl. commission, tick value / tick size
  if lots < min volume: Finish(SAFE_SIZE); return
  if !tradingAllowed: log("PAPER entry", ...); Finish(PAPER); return
  BREAK       → market order with SL/TP attached, deviation = MaxDeviationPoints, retry on requote ≤ 2
  PULLBACK_50 → pending limit with SL/TP and expiration = candle end
  check retcode; on reject: log, count error, breaker after 3 consecutive errors

ManagePosition()
  if position open:
     if minutes since entry ≥ MaxHoldMinutes or rollover blackout: close at market ("TIME"/"ROLLOVER")
     (no break-even, no partials, no trailing — MGT-1)
  if a position just closed: log outcome, R multiple, MAE/MFE, update daily P&L
```

### Ordering and determinism notes
- Everything is driven by **closed** M1 bars of the gold chart. DXY bars are read with `CopyRates` up to the same close
  time; if the DXY bar for that minute is missing, the last *closed* DXY bar at or before it is used (never a forming bar).
- `BREAK` entries are sent on the first tick of bar t + 1, so the fill is the market price at that moment (≈ oₜ₊₁).
- The Python reference processes the same sequence on historical arrays; `tests/test_video_strategy.py` checks causality,
  and `tests/test_video_examples.py` replays the six video examples as synthetic fixtures.
