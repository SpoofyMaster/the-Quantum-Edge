# BprFvgEA v11: LuxAlgo BPR / FVG zones + BPR rejection → breakout → Fibonacci entries (MetaTrader 5)

> **v11 (2026-10-21)** = v10 plus your rule of 2026-10-21, from your drawing on the v9 chart ("T1 YES" / "T1 NO"):
> "on T1 or T2, the body of those candles must not go out of BPR rectangle ... T1 candles body must not close out of
> the BPR box, after that C1 and C2 must also above or on the box, if they close out of the BPR box no trade, and same
> for a tape from below". The chart `research/indicators/preview/bpr_body_rule_example.svg` (`example_body_rule.svg`
> / `.png` in the zip) shows it, drawn from the detector's own records.
>
> | Input | v11 default | What it does |
> |---|---|---|
> | `InpRevBodyInBox` | true | Reversal: the **bodies** of the T1 / T2 candles and of C1, C2 must stay in the BPR box or on its side of it. Otherwise no trade. `false` = v10. |
>
> **The rule** (a BPR tapped from **above**, i.e. a bullish BPR; tapped from **below** is the mirror image):
> - **T1 / T2:** the body (open and close) of the touch candle must be **in the box or above it**. The touch can last
>   several candles (consecutive candles touching the box are one touch): each of them counts.
> - **A second tap that comes back too early is T2 too.** Example: the T1 wick stays in the box, C1 closes above it,
>   and the next red candle comes back and closes through the box after only one green candle. Since v9 that candle
>   is not a touch, because it closes beyond the T1 wick too early. For this rule it is your T2, and its body must
>   stay in the box. This holds while a second touch is allowed (`InpMaxTouches` ≥ 2, default 2).
> - **C1, C2:** the rejection candles must also be **in the box or above it** (the whole body: a green candle that
>   opens below the box is out too). With `InpRevRejCandles = 2` these are C1 and C2; a third green candle is not
>   checked. After price closes beyond the T1 wick too early, the count starts again and the new C1, C2 are checked.
>   On M1 bars without a gap, a C candle opens where the candle before it closed, so a C body below the box usually
>   means that candle closed below the box already. If that candle is part of the touch, it already ended the setup.
> - **The wicks may go out.** A T1 wick below the box is allowed (it can even be the reversal level).
> - **On the edge counts as in the box:** a T1 closing exactly at the box's bottom is valid; one tick below is not.
> - **Out = no trade:** the setup ends at once, on that candle's close: `DONE (BROKEN: the body of T1 (open 100.10,
>   close 97.80) is below the BPR box (bottom 98.00) - no trade)`. The chart writes `NO TRADE: T1 body out of the
>   BPR` on that candle, on the other side from its `T1` label. For a later candle of a touch it says `T1-touch
>   candle` (in the log: `the body of a later candle of the T1 touch`). The panel's `ended:` row counts them
>   (`body out of the box n`), warm-up included.
>
> **What is not checked** (your words name T1 / T2 and C1 / C2 only):
> - **a pullback visit after the last allowed touch:** with 2 touches allowed, the third visit of the box;
> - **the breakout candles:** they close beyond the T1 wick, through the box, by definition;
> - **the candles after a failed breakout,** in the same visit of the box;
> - **green candles after C1 .. C`InpRevRejCandles`** (C3 with the default 2).
>
> A red candle that comes back into the box while a touch is still allowed is T2, and **is** checked.
>
> **Continuation setups** are not affected: a continuation setup already ends (`BROKEN`) as soon as a wick goes beyond
> the box's far side.
>
> **Your examples:**
> - **"T1 NO":** T1 opens above the box and closes at 97.80, below the box's bottom (98.00). No trade; v10 traded it
>   with limits on bar 23.
> - **C2 below the box:** T1 has its wick below the box but its body in it, C1 is in the box, C2 opens and closes
>   below the box. No trade; v10 traded it. The chart draws this one with a gap (C2 opens 0.60 below the candle
>   before it). Without the gap, the red candle before C2 would close below the box itself and end the setup there,
>   as a `T1-touch candle`.
> - **An early second tap below the box:** T1 with its wick in the box, C1 above the box, then a red candle closes
>   below the box. No trade; v10 traded it (limits on bar 26).
> - **Your C1 / C2 example of 2026-10-17:** unchanged, it trades.
>
> The CSV files are now `BFEA11_*` (same columns). **Research:** H-15 stays `HYPOTHESIS`; this is a new rule for it.

> **v10 (2026-10-19)** = 9.01 plus your two requests of 2026-10-19:
> 1. "a limit time to configure on the input for how many time the EA should let the limit orders before canceling
>    them";
> 2. "the EA should trade all the setups confirmed": until now, when another setup confirmed while one was trading,
>    the EA skipped it and kept tracking only the first.
>
> | Input | v10 default | What it does |
> |---|---|---|
> | `InpPendingMaxMin` | 0 (off) | A setup's limit orders stay in the book **at most this many minutes**, then the EA cancels them (`CANCEL … (EXPIRED: pending-order time limit, N min after the first placement)`). `0` = no time limit (v9). |
> | `InpMaxSetups` | 5 | **Setups traded at the same time.** Every confirmed setup places its limits while fewer than this many setups have orders or positions. `1` = one at a time (v9). Maximum 10. Hedging accounts only (see below). |
>
> **The time limit, exactly.**
> - It counts from the setup's **first placement**. Example with 30 minutes on M1: limits placed at 10:00 are cancelled
>   at 10:30.
> - **A move does not restart it.** With `InpAnticipateEntries` the limits follow every new high / low; they are still
>   cancelled 30 minutes after the first placement.
> - **A filled entry runs on.** If one entry filled, the EA cancels only the ones still pending; the position keeps
>   its SL / TP / time stop.
> - **The setup ends with it.** A setup whose orders were cancelled by the time limit does not place them again (also
>   when it was waiting to send a move, for example after 14:45 New York).
> - **The broker removes each order at that minute** (its expiry time is set to the first placement + the limit), so
>   the limit holds to the minute on any timeframe. The EA also cancels them itself on the first candle close at or
>   after it; the log then says `EXPIRED: pending-order time limit`. If the broker was first, the log says `pending
>   order left the book without a fill (EXPIRED: its broker-side expiry at the pending-order time limit, …)`; both count
>   as time-limit ends on the panel. Some symbols refuse expiry times; their
>   orders are then removed by the EA on the candle close (on M5: up to 5 minutes later).
> - The other limits are unchanged: `InpLegExpiryBars` (60 candles after the confirmation), the 14:45 New York cancel
>   (`InpCancelAtSessionEnd`), the target, a broken leg. Whichever comes first cancels the orders. **On M1 a limit of
>   62 minutes or more never acts with the default `InpLegExpiryBars = 60`**: the leg expiry (61 candles after the
>   confirmation) always comes first, and with orders placed after a pullback candle it can come first for shorter
>   limits too. Raise `InpLegExpiryBars` to let the time limit decide; the self-check warns about it.
> - **It also applies with `InpCancelAtSessionEnd = false`.** That switch stops the session and rollover cancels;
>   the time limit is the cancel you set yourself, so it still ends the orders after 14:45. Leave it at 0 to keep
>   them until they fill or the leg ends.
>
> **Several setups at a time.**
> - When two setups confirm on the same candle, **both** place their limits now. Before v10 the second was skipped.
>   A setup that confirms while others trade places its limits too, as long as a slot is free.
> - **Each setup is tracked on its own**, with its own limits, moves, fills, stop and target. The first trade is
>   followed exactly as before.
> - **One trade per leg.** BPRs stacked close together often give their setups the **same leg** (the same 100 % and
>   0 %), above all with `REVERSAL` / `BOTH`. Their orders would be the same three limits with the same stop: three
>   copies of one trade, three times its risk. A setup whose leg (direction and 100 %, so its stop) another setup
>   already holds (its orders or positions, also while it moves them at a new high / low) therefore ends at once:
>   `DONE (NO_LEVEL: the same leg - direction and 100 % - is already traded by #n; one trade per leg)`. The first
>   trade keeps its leg. Setups with a different leg all trade.
> - **Risk.** Each setup has its own 0.20 % (split over its entries), as before. **The 1.00 % planned daily loss
>   covers all of them together**: a setup places its orders only if the loss realised today + the planned risk of
>   every open position and pending order + its own stay within 1.00 %. So with 5 setups of 0.20 % at once, a
>   sixth waits. After a loss, fewer fit. A setup that cannot place now (all slots taken, or the daily budget) waits
>   and decides again on the next candles while it is still valid.
> - **Same direction.** Several setups can trade the same direction at once (for example two bullish BPRs with
>   different legs), also while an earlier one is in loss. Each is its own confirmed setup with its own leg, its own
>   stop and its own fixed 0.20 %; no position is ever enlarged and no size grows after a loss. Their losses can come
>   together when price moves against all of them: at most 1.00 % of the day at the planned stops (more if several
>   stops slip at once, for example on a gap). If you want only one trade per direction, set `InpMaxSetups = 1`.
> - **Touch entry** (`InpTouchEntry`): still one touch position at a time. It holds one of the slots.
> - **Netting accounts.** One position per symbol: setups would merge into it and share one SL / TP. On a netting
>   account the EA therefore stays at **one setup at a time**, whatever `InpMaxSetups` says (the self-check says so).
> - **Unowned positions.** While the EA manages a position that no setup owns (after a restart, or a fill that raced a
>   cancel), no new setup places orders, as before. A setup whose own old order could not be deleted (or filled just
>   before its cancel) waits for it without taking another slot.
> - **`InpMaxTradesDay`** (if you set it): the other setups' pending orders count as positions they may still open,
>   so a new setup waits when they would go past the limit.
>
> **On the chart and in the log.**
> - The panel row `orders/positions (2 of 5 setups): #12 SHORT …: L1 limit … || #15 LONG …: L2 open …` lists every
>   setup with orders or positions.
> - A setup kept out because all slots are taken is counted on the panel (`blocked: … slot n`); the detector holds it
>   back before any order, so there is no log line per candle. A setup the EA itself has to hold back logs
>   `orders not sent now: slot busy: …` or the daily-loss reason with `+ other setups <planned risk>`.
> - The rules row shows `setups at a time up to 5, most so far n | limit orders cancelled 30 min after the setup's
>   first placement`; the `ended:` row counts the setups ended by the time limit and those ended as the same leg.
> - The CSV files are now `BFEA10_*` (same columns).
>
> **Defaults and research.** With `InpMaxSetups = 1` and `InpPendingMaxMin = 0`, v10 behaves as 9.01. Several setups
> at a time change what a backtest measures (more trades, risks that overlap). A backtest with them is a new trial.

> **9.01 (2026-10-18)** fixes your bug report: with `InpCancelAtSessionEnd = false` the EA still cancelled pending
> orders. With the switch `false` it now cancels **no pending order for a time reason**:
> - not at 14:45 New York (as before);
> - not at the 16:44 New York rollover cut (the detector's `SESSION_END` cancel), and not on a tick between 16:44 and
>   17:00 (the EA's own rollover delete);
> - the broker-side expiry is no longer capped at 16:44; the leg-expiry safety net gets 3 more days, so a weekend or
>   a daily break cannot remove an order before its leg ends;
> - when no order can be sent (after 14:45, in the last 2 minutes before 16:44 and between 16:44 and 17:00), a new
>   high / low no longer cancels the orders to move them (the move could not be sent again, so they were lost). They
>   stay at their last levels. This also applies on the last bar before the window closes (a move that has to wait
>   one bar could not be sent any more) and on bars replayed after a reconnect.
>
> Orders still end by the strategy's own rules: filled, the leg broken, the leg expired (`InpLegExpiryBars`), the
> target reached. Inside the entry window they still follow the Fibonacci at every new high / low.
>
> **Notes.**
> - With `InpFlatBeforeRollover = true`, an order that fills between 16:44 and 17:00 New York is closed at once by the
>   16:44 flat. Set `InpFlatBeforeRollover = false` to hold such a fill.
> - **Changing an input, the timeframe or the symbol, recompiling, or restarting the terminal deletes this EA's pending
>   orders** (positions are kept). This is not the switch: a restarted EA cannot take its old orders back. Set the
>   inputs before the orders exist (in the Strategy Tester: before the run).
> - With `InpAnticipateEntries = false` a move takes the orders off the market until the next pullback candle (the v4
>   rule). If the entry window closes before that candle, they are not sent again. With the default `true` the move
>   is sent on the same bar.
>
> With `InpCancelAtSessionEnd = true` (the default) nothing changes.

> **v9 (2026-10-17)** = v8 plus your rule of 2026-10-17 for the reversal: "after T1 price must absolutely make a
> rejection which a minimum 2 candles successive or not ... before price comes back for breakout", with "a minimum 2
> Green candles for a bullish rejection and 2 RED candles for a bearish rejection". The chart
> `research/indicators/preview/bpr_rejection_example.svg` (`example_rejection.svg` in the zip) shows your C1 / C2
> example as v9 reads it.
>
> | Input | v9 default | What it does |
> |---|---|---|
> | `InpRevRejCandles` | 2 | The reversal breakout needs at least this many **rejection candles** after T1. `0` = v8 (any rejection). |
>
> **What counts as a rejection candle** (bullish BPR; a bearish BPR is the mirror image, with red candles):
> - a **green** candle (close above open) **after** the T1 candle; the T1 candle itself does not count;
> - the candles do not have to follow each other: green, red, green is 2;
> - a candle that closes **below the reversal level** (the T1 wick by default) does not count: price is already
>   through the BPR, so it is no rejection from it;
> - a doji (close = open) does not count.
>
> **Price comes back too early.** A close below the reversal level before the 2 rejection candles is not a breakout.
> It also restarts the count: the 2 candles must come after it, before the next close below the level. That close is
> no touch either: it does not become T2, and its wick does not move the reversal level.
>
> **A failed breakout keeps the count.** If the first close below the level comes after the 2 rejection candles and
> the next candle closes back above it (`BREAK_FAIL`), the rejection still came first. The next close below the level
> is a breakout again, as in v8.
>
> **Unchanged.** The rejection itself is still needed (`InpRevNeedRejection`). The breakout is still 2 closes beyond
> the level, and the limits still go in on the second close. The continuation setup is not affected.
>
> **Your example in numbers** (the chart's bars, `REVERSAL`):
> - T1 on 17 (wick 99.00);
> - C1 on 18, C2 on 19 (green);
> - first close below 99.00 on 22 ("2 rejection candles before it" in the log), second on 23: sell limits on 23 at
>   99.90 / 100.30 / 100.61 (100 % = 101.60, 0 % = 98.20);
> - moved on 24 to 99.60 / 100.07 / 100.44; the 50 % fills on 26, the target is reached on 27.
>
> With only C1 (T1, one green candle, then the drop), v8 took the reversal and v9 does not. Two of the v8 test examples
> are like that (`late_t1`, `one_candle_reaction`); they no longer trade.
>
> **On the chart and in the log.**
> - The chart labels each rejection candle `C1`, `C2`, … as you drew them (above a green candle, below a red one). If
>   price closes beyond the level too early, these labels go and the count starts again. After a breakout they stay.
> - A reversal `REJECT` shows `rejection candles: n, counted after T1 and after the last close beyond the reversal
>   level; the breakout needs 2`.
> - A reversal `BREAKOUT` shows `n rejection candles before it`.
> - The CSV files are now `BFEA9_*` (same columns).

> **v8 (2026-10-16)** = 7.01 plus your example of 2026-10-16. The BPR forms, price goes away, comes back later and taps
> it (T1), reacts, then breaks the T1 wick. "The EA must track every BPR created and where was the first tap"; "the
> moment price closes with the second candle's body beyond the T1 or T2 wick, the EA must place the limits and keep
> following price with the Fibonacci". The chart `research/indicators/preview/bpr_tap_example.svg`
> (`example_tap.svg` in the zip) shows how v8 reads it.
>
> | Input | v8 default | What it does |
> |---|---|---|
> | `InpMaxBarsToT1` | 0 | **Every BPR is followed until its first touch**, however late (0 = no limit; a number = at most that many bars after the BPR forms). `-1` = the v7 rules. |
> | `InpSetupExpiryBars` | 240 | The window to confirm a breakout now runs **only while price is at the BPR**: during a visit (from its first candle) and from a breakout candle. After a rejection, while price is away, there is no limit: the EA waits for price to come back, however late (a late T2, a late break of the T1 wick). |
> | `InpAnticipateEntries` | **true** (was false) | The limits go in **on the confirming close**: the second close beyond the level. At every new low (short) / high (long) they are deleted and sent again at the new Fibonacci. Once one of them has filled, they are no longer moved: a new low (short) / high (long) or the target then deletes the ones still pending. |
> | `InpRevNeedFvg` | false | The reversal no longer waits for an FVG of the drop, so its limits really go in on the second close. `true` = v7: wait for an FVG after the 100 %. The continuation keeps its FVG rule (`InpFvgRule`). |
>
> **Also:**
> - **A one-candle reaction.** For the reversal, a candle inside the T1 (or T2) visit that **closes beyond the BPR**
>   (above it for a bullish BPR) is the rejection, even if its wick is still in the zone. In your drawing the reaction
>   candle opens in the zone and closes above it. Before v8 that candle still counted as part of the touch, and if the
>   next candle came back into the zone the reversal never armed. A close exactly at the edge is not enough.
> - **Older BPRs.** BPRs that formed before the EA started (in the warm-up history) and have not confirmed a breakout
>   yet go on as well. Before v8 every warm-up BPR was dropped. At the start the log lists each one
>   (`#n REV SHORT kept from the warm-up: ZONE, touches 1, T1 <time>, level <price> (candle <time>)`), and the chart
>   shows its T1 / T2 labels and, after a breakout candle, the breakout line and `B1`.
> - **A full list.** If 128 setups are followed at once, the setup **idle the longest** makes room
>   (`DONE(CAPACITY)` in the log): never touched, or away from its BPR since its last rejection. A setup in a visit,
>   in a breakout or trading is never dropped. If every setup is busy, the new BPR is not followed (`CAPACITY`).
>
> **Your example in numbers** (the chart's bars, `REVERSAL`):
> - T1 on 17 (wick 99.0), the rejection on 18 (the candle closes back above the BPR);
> - first close below 99.0 on 23, second on 24: **sell limits on 24** at 99.90 / 100.30 / 100.61 (100 % = 101.60,
>   0 % = 98.20);
> - a new low on 25 moves them to 99.60 / 100.07 / 100.44;
> - the 50 % fills on 27, the target 97.70 is reached on 28.
>
> With the v7 rules the same orders came on bar 26, after a pullback candle.
>
> **The gates are unchanged.** The entry window, the daily loss limit, the spread and one setup at a time can still
> delay the first placement by a bar. Example: with `BOTH`, the continuation setup of the same BPR may still hold its
> stopped-out orders when the reversal confirms.
>
> **Defaults and research.** These defaults differ from the research reference H-14 (Python, parity tests). To run the
> v7 rules, set `InpAnticipateEntries = false`, `InpMaxBarsToT1 = -1` (window, list, warm-up and one-candle rules),
> `InpRevNeedFvg = true`. The CSV files are now
> `BFEA8_*` (same columns).

> **v7 (2026-10-15)** = v6 with the **reversal setup redone from your screenshot**. Defaults (CONTINUATION) = v6 = v5.
> **7.01 (2026-10-16)** applies the review of v7. See "7.01" at the end of this block.
>
> Your example: after T1 / T2 and a rejection from the BPR, price comes back and **closes twice below the T1 wick**.
> The Fibonacci runs from the top of the move (100 %, stop) down to the new low (0 %, target), with entries at
> 50 / 61.8 / 71 %. The chart `research/indicators/preview/bpr_reversal_example.svg` (`example_reversal.svg` in the
> zip) shows how v7 reads it, drawn from the detector's own records.
>
> | Input | Default | Meaning |
> |---|---|---|
> | `InpSetupType` | CONTINUATION | `CONTINUATION` / `REVERSAL` as in v6. **`BOTH` now = two setups per BPR**, a continuation one and a reversal one, each on its own. |
> | `InpRevLevel` | DEEPEST | The reversal level. `DEEPEST` = the deeper wick of the T1 / T2 candles (the T1 wick in your example). `T1` = always the T1 wick. `LAST` = the latest touch candle's wick (v6). |
> | `InpRevNeedRejection` | true | A rejection (a candle that leaves the zone) must come after T1, before the reversal breakout. `false` = v6: a breakdown right after T1 counts too. |
>
> **What changed from v6, and why** (bullish BPR → short; a bearish BPR is the mirror image):
> 1. **The level.** v6 used the latest touch candle (T2, 99.70 in your example); you drew the **T1 wick** (99.50).
>    - The default is now the **deeper of the T1 / T2 wicks**: a close below it is a close below both.
>    - If T2 goes deeper than T1, its wick is the level ("T1 or T2 wick").
> 2. **Rejection first.** "t1 + rejection from it and pullback". A breakdown on the candles right after T1, without a
>    bounce, is no longer a reversal. `InpRevNeedRejection = false` restores v6.
> 3. **The pullback into the zone.** Price that comes back into the zone after T2 is the pullback, **not a third
>    touch**.
>    - It no longer ends the reversal setup (`TOUCH_LIMIT` stays a continuation rule).
>    - It does not move the level.
> 4. **The 100 %.** The top of the move before the breakdown.
>    - That is the highest high since T1. If price came back into the zone and **bounced**, it is the top of that last
>      bounce instead.
>    - A visit of the zone that turns straight into the breakdown keeps the earlier top. In your example that is
>      101.60.
>    - The 0 % is the lowest low after the 100 %, followed while it extends.
> 5. **`BOTH`.** In v6 the first breakout to confirm decided. After the continuation had traded the move up, the
>    reversal of the same BPR could not trade any more, which is exactly your example.
>    - In v7 the continuation and the reversal are **two setups of the BPR**, followed separately: `#n` and `#n REV`
>      in the log, ids next to each other.
>    - One setup trades at a time, as before.
>    - Your example now gives the continuation trade first, then the reversal trade.
> 6. **Unchanged.**
>    - Two successive closes (`InpConfirmCloses`).
>    - The entries: sell limits at 50 / 61.8 / 71 % on the pullback, with the FVG rule.
>    - SL above the 100 % + `InpStopBufferTicks`; TP at the 0 %.
>    - Expiry, session and risk.
>
> **Your example in numbers** (the chart's bars):
> - level 99.50 (T1 wick);
> - first close below on bar 28, second on bar 29;
> - 100 % = 101.60, 0 % = 96.40;
> - sell limits 99.00 / 99.61 / 100.09, SL 101.80 (ask), TP 96.50 (ask).
>
> **Logs and CSV.**
> - Reversal setups are tagged `REV` in the log (`#2 REV SHORT CONFIRM …`).
> - The CSV files are now `BFEA7_*` (same columns as v6). `setup` is the setup's kind: `CONT` or `REV`.
>
> **Status.** H-15 (reversal) is still an untested HYPOTHESIS; its rule is now v7's. Not compiled here.
>
> **7.01 (review of v7).** Your example trades exactly as before. Fixed:
> - **The 100 %.** It is the top of the bounce **after the visit's lowest low**. This applies to every visit of the
>   zone, T1 included.
>   - The candle that enters the zone belongs to the descent, so it no longer counts. Two ways of cutting the same
>     descent into candles now give the same Fibonacci.
>   - A crash through the BPR inside the T1 visit is no longer used as the leg.
>   - A failed breakdown candle that enters the zone also starts a visit. If price then bounces, that bounce is the
>     100 %.
> - **The level.** A T2 wick moves the `DEEPEST` level only once price is rejected from that visit. A T2 visit that
>   turns straight into the breakdown keeps the T1 wick: "first / second closing below T1 wick".
> - **The FVG.** A reversal needs its FVG **after its 100 % bar**. Before, a gap from the earlier move up could count.
> - **Expiry.** A reversal setup counts `InpSetupExpiryBars` from its **last rejection** instead of from the BPR's
>   creation.
> - **Log and CSV.** A reversal setup shows its trade direction from the start (`#2 REV SHORT TOUCH …`).
> - **Risk with `BOTH` + `InpTouchEntry`.** A reversal setup cannot send the touch entry, so its entries share the
>   0.20 % without that share (0.067 % each instead of 0.05 %).
> - **DIAG with `BOTH`.** It counts setups, two per BPR.
> - **Chart.** When one setup of a BPR ends while the other is still followed, its copy of the zone and the T labels
>   is removed instead of greyed on top.

> **v6 (2026-10-12)** = v5 plus a **reversal setup** and a **market entry on T1**, at the owner's request. Defaults =
> v5. *Points 2, 4 and 5 of the reversal list below are as v6 shipped them; v7 changed the level, the `BOTH` rule
> and the touch limit of the reversal (see above).*
>
> | Input | Default | Meaning |
> |---|---|---|
> | `InpSetupType` | CONTINUATION | `CONTINUATION` = v1–v5. `REVERSAL` = the breakout **through** the BPR, traded the other way. `BOTH` = whichever breakout confirms first. |
> | `InpTouchEntry` | false | `true`: when the **T1** candle closes, a **market order in the BPR's direction** at the next candle's open, to catch the first reaction to the BPR. |
> | `InpTouchTargetRR` | 1.5 | Take-profit of that market order, in R (risk = entry to the stop). |
>
> **The reversal setup** (bullish BPR → short; a bearish BPR is the mirror image):
> 1. **Touches.** Exactly as before: T1, and optionally T2 after a rejection candle.
> 2. **Breakout through the zone.** A candle **closes below the low of the candle that made the latest touch** (T1
>    or T2). The next candle must close below it too (`InpConfirmCloses`, default 2).
>    - These candles may be inside or below the zone; going through the BPR is the point.
>    - A close exactly on that low is not enough.
> 3. **Leg and entries.** As before, mirrored:
>    - the leg runs from the **highest high since that touch began** (100 %) down to the lowest low (0 %), tracked
>      while it extends;
>    - on the pullback (with the FVG rule: a bearish FVG after the reference candle), **sell limits** at 50 / 61.8 /
>      71 %;
>    - **SL** above the leg's high + `InpStopBufferTicks`; **TP** at the leg's low.
>
>    `InpAnticipateEntries`, `InpLegBreakOnClose`, expiry and the session rules work the same way.
> 4. **A broken BPR.** With `CONTINUATION`, a low below the BPR still ends the setup (`BROKEN`). With `REVERSAL` /
>    `BOTH`, it only ends the continuation; the reversal stays possible.
> 5. **`BOTH`.** The first breakout that **confirms** decides the direction. A failed reversal breakout (`BREAK_FAIL`)
>    returns to the touch, and a continuation breakout can still follow, and vice versa.
>    - **Even on the failing candle itself.** In a bull trap, the continuation breakout fails on a candle that closes
>      below the touch candle's low; that same candle starts the reversal (it does not count as a new touch).
>    - **No reversal possible.** If the reversal's direction is not allowed (e.g. `BOTH` + `LONG_ONLY` on a bullish
>      BPR), a broken BPR ends with `BROKEN` as in v5.
> 6. **`InpDirection`** applies to the **trade**. A bullish BPR's reversal is a short, so `LONG_ONLY` + `REVERSAL`
>    trades no bullish BPR's reversal. With `InpTouchEntry`, such a BPR is still tracked for its T1 buy.
>
> **The touch entry** (`InpTouchEntry = true`):
> - **When.** Only on **T1** (never T2), only if the T1 candle did **not** break the BPR, and only in an allowed
>   direction. The usual gates apply: entry window, daily risk, spread, the slot. It is sent once or never: nothing
>   is retried on a later candle.
> - **Price, stop and target.**
>   - a **buy** at the ask (bullish BPR) or a sell at the bid;
>   - **SL** beyond the BPR's far edge + `InpStopBufferTicks` (below the BPR bottom for a buy);
>   - **TP** = `InpTouchTargetRR` × the actual risk from the fill price.
> - **Filters.** The cost and RR filters apply (`SKIP` level 0 / "touch entry" in the log).
> - **The fill is checked.** It is a market order, so the fill is checked like a market-filled level. If slippage
>   puts its actual risk above its share, the excess is closed (hedging), or the whole position (netting).
> - **Chart label.** The `BUY MKT` / `SELL MKT` label is drawn once the order is sent. It turns grey with
>   "not sent" (and the reason in its tooltip) when it is not sent, for example on a real account.
> - **The setup goes on.** It still waits for its breakout and pullback and places its limits, **while the touch
>   position is open** (hedging accounts). Every other setup waits for the slot. On a **netting** account the touch
>   position blocks its own setup's limits too.
> - **Risk.** The setup's **0.20 % is shared**: with 3 Fibonacci entries plus the touch entry, each gets 0.05 %
>   (instead of 0.067 %). The daily-loss check also counts an open touch position.
> - **Exits.** Server SL/TP, the time stop and the 16:44 flat, like the other positions. The trades CSV has it with
>   level `T`.
>
> **Not specified by you, so chosen here:**
> - the reversal level (the low/high of the **candle that made the touch**, your wording);
> - the reversal leg origin (the touch's highest high / lowest low);
> - the touch entry's stop (beyond the BPR) and target (1.5 R);
> - "only T1 and only if the T1 candle did not break the BPR".
>
> All are inputs or documented rules; tell me if you meant something else.
>
> **Not a test of H-14.** Both are new rule sets, registered as **H-15** (reversal) and **H-16** (touch entry),
> untested.
>
> **Implementation (MQL5 only, like v5).** Detector params `setupType` / `touchEntry` / `touchTargetRR`. Executor:
> `ExecTouch`, `ManageTouch`, `FinishTouch`, and the touch case in `SlotOwner` / `SlotFreeForDecision`. Checked on the
> C++ copy of the MQL5 detector by `tests/test_bpr_breakout_v6_setups.py`. The new sequences are also in the parity
> set, where the defaults equal the v4 Python reference.

> **v5 (2026-10-11)** = v4 plus two on/off switches for the **entries**, at the owner's request ("the EA didnt place
> orders and the reason is LEG_BROKEN, but sometime this broken leg is the retracement so when price pulls back the EA
> didnt anticipate it"):
>
> | Input | Default | `true` means |
> |---|---|---|
> | `InpAnticipateEntries` | false | The three limits are placed **as soon as the breakout is confirmed** (the second close beyond the level), once the FVG condition holds, without waiting for a pullback candle. At every new high (long) / low (short) of the leg they are **moved**: deleted and sent again at the new Fibonacci on the same bar. A fast pullback then **fills them** instead of ending the setup with `LEG_BROKEN`. |
> | `InpLegBreakOnClose` | false | `LEG_BROKEN` only when a candle **closes** beyond the leg origin (the 100 % level). A wick beyond it no longer ends the setup. |
>
> With both at `false`, v5 behaves exactly like v4.
>
> **Why v4 missed these trades.** v4 decides the orders when a pullback candle has **closed** and sends them at the
> next candle's open. When one candle falls from the leg high through 50 / 61.8 / 71 % and below the origin, the
> retracement is over before any order exists, and the candle's low below the origin ends the setup (`LEG_BROKEN`).
>
> **Which switch does what:**
> - **`InpAnticipateEntries` is the one that catches the fast pullback.** The orders are already in the book when it
>   starts.
>   - Orders exist only once the FVG condition holds (with the `LUXALGO` rule, the FVG often appears one candle after
>     the confirmation) and the slot is free.
>   - Moves stop when `InpLegExpiryBars` has passed, and on a candle that ends the entry window, as orders would.
>   - The extra decision candles (the confirmation, a new extreme) never end a setup. If nothing can be placed there,
>     the setup waits and decides again later, as v4 waits for its pullback candle. That happens when a spike closes
>     beyond every entry, or when the leg is still too short for the cost filter. On an ordinary pullback candle
>     the v4 rules apply.
> - **`InpLegBreakOnClose` alone does not.** After a candle that wicked below the origin, entries above its close are
>   already passed (`SKIP MISSED`); only those still below the close are placed. It helps when the wick comes back up.
>   The origin and the stop stay where they were, even though the wick traded through them.
>
> **Read before switching them on:**
> - **A pullback that goes through the stop is a loss now.** The stop stays at the origin minus `InpStopBufferTicks`
>   (10 ticks). A fast pullback that breaks the origin by more than that fills the limits and **stops them out**.
>   Before, it was a no-trade `LEG_BROKEN`. To give such pullbacks room, widen the stop (`InpStopFib` above 100, or
>   more `InpStopBufferTicks`). Each entry's risk stays within its share of the 0.20 %, because the lot size follows
>   the stop distance.
> - **Many order changes.** While the leg extends, every new high deletes and re-sends up to 3 limits: up to 6 trade
>   requests per candle on M1. Each re-send counts as an "entry decision" on the panel, and `re-anchored` counts the
>   moves.
> - **Still one setup at a time** (v10: up to `InpMaxSetups`). The setup that moves its own orders may reuse its slot
>   on the same candle; other setups wait. The old orders are deleted before the new ones are sent. The new ones go out only if the account
>   history proves that no order the EA deleted in the last minute filled, even partly. On a live or demo server the
>   EA waits up to about half a second for that history. Otherwise (a failed delete, a fill just before the delete,
>   history still missing) nothing new is sent, and the setup decides again on a later candle.
> - **Not a research trial of H-14.** Either switch changes the entry rules, so a backtest with them is a new
>   hypothesis that needs its own pre-registration.
> - **Implementation (MQL5 only).**
>   - Detector: `anticipate` and `legBreakOnClose` in `include/BfDetector.mqh`.
>   - Executor: `SlotOwner`, `DeletedOrdersProven` and `SlotFreeForDecision` in `BprFvgEA.mq5`.
>   - The Python reference is unchanged, so the parity harness covers the defaults. The switched-on rules are checked
>     on the C++ copy of the MQL5 detector by `tests/test_bpr_breakout_v5_switches.py`.

> **v4 (2026-10-10)** = v3 plus two on/off switches for the **position exits**, at the owner's request ("the EA close
> automatically position on `close at market: TIME` so the EA stop the trade to go to the final TP"):
>
> | Input | Default | `false` means |
> |---|---|---|
> | `InpUseTimeStop` | true | No time stop: no more `close at market: TIME` after `InpMaxHoldMin`. The position runs to its stop-loss or its take-profit (the leg extreme), unless the 16:44 New York flat closes it first. |
> | `InpFlatBeforeRollover` | true | No 16:44 New York flat: no more `close at market: ROLLOVER`. The position may be held over the 17:00 New York rollover and over the weekend. |
>
> With both at `true`, v4 behaves exactly like v3. **To let every trade run to its final TP or SL, set both to
> `false`**; with only `InpUseTimeStop = false`, positions are still closed at 16:44 New York.
>
> **Read before switching them off:**
> - **It departs from the project's hard rule** "every position closed ≤ 120 minutes after entry" (`CLAUDE.md`). It
>   is the owner's decision for the Strategy Tester and demo accounts. A run with either switch off is **not a
>   research trial of H-14**; the panel and the log say so (`NOT a research trial`).
> - **Risk.** The 0.20 % per setup is the loss at the stop-loss. Held over the rollover or a weekend, a position pays
>   swap (not in the cost check) and a price gap can fill the stop worse than planned, so a loss can exceed 0.20 %.
>   The 1 % daily limit counts a loss on the FX day the position is closed, also for a position held for more than
>   the 4 days of history the daily count normally reads (it is then looked up by position).
> - **Only `InpFlatBeforeRollover = false`:** the time stop still runs, but it can fall after 16:44 New York, e.g. a
>   fill at 15:03 New York is due at 17:03: the position is held over the 17:00 rollover (swap, triple on Wednesday;
>   the rollover spread). If the market is closed then (a daily break, or
>   after the Friday close) the close waits for the first tick after the reopen, so the position can be held over the
>   weekend. This is why the panel marks this case `NOT a research trial` too.
> - **One setup at a time.** While a position is open, no new setup trades. Without the time stop this can last for
>   hours or days. (v10: with `InpMaxSetups` above 1 the other slots stay free for new setups.)
> - **Unchanged:** pending orders are still deleted at the 16:44–17:00 New York rollover and never live past the
>   next 16:44 New York (server-side expiry); no new order is sent then. Only **positions** may now cross the rollover.
>   (9.01: with `InpCancelAtSessionEnd = false` the pending orders are kept over the rollover too.)
> - **Removing the EA** (or closing its chart or the terminal) no longer closes its positions when **both** switches
>   are off: the EA has no market exit to run, and the positions keep their server SL / TP. With either switch on,
>   they are closed as before. If you start the EA again later **with a switch on**, a kept position is closed at
>   market on the first tick if it is already past `InpMaxHoldMin` (only with `InpUseTimeStop = true`; the time stop
>   counts from the fill) or was opened before the last 16:44 New York (only with `InpFlatBeforeRollover = true`).
> - **Implementation.** EA only (`TimeStopDue`, `RolloverFlatDue` in `BprFvgEA.mq5`). The detector and the Python
>   reference are unchanged; they never closed positions.

> **v3 (2026-10-10)** = v2 plus four on/off switches, at the owner's request. They let entries go out even when they
> would be skipped for **cost**, **reward:risk** or the **14:45 New York session end**:
>
> | Input | Default | `false` means |
> |---|---|---|
> | `InpUseCostFilter` | true | Entries are placed whatever their round-trip cost (`InpMaxCostR` is ignored). No more `SKIP (COST)`. |
> | `InpUseRRFilter` | true | Entries are placed whatever their reward:risk (`InpMinRR` is ignored). No more `SKIP (RR)`. The default `InpMinRR` is already 0 (off). |
> | `InpCancelAtSessionEnd` | true | Pending limit orders are **not** cancelled at 14:45 New York (no more `CANCEL (SESSION_END)` at 14:45). They stay until they fill, the leg expires (`InpLegExpiryBars`), a new high re-anchors the setup, or the rollover cut (16:44 New York) arrives. **9.01:** no rollover cut any more, and no re-anchor when no order can be sent (see the 9.01 note at the top). |
>
> And one switch that is **off** by default:
>
> | Input | Default | `true` means |
> |---|---|---|
> | `InpEntriesAfterSessionEnd` | false | **New** orders may also be placed after 14:45, until 16:44 New York (Mon–Fri). The 08:00 London start stays. |
>
> With the defaults (`true`, `true`, `true`, `false`), v3 behaves exactly like v2.
>
> **What the switches do not change:**
> - **New orders after 16:44 New York.** Those need `InpUseSession = false`, which removes the window entirely,
>   including the 08:00 London start. Even then, no order is sent between 16:44 and 17:00 New York.
> - **The 16:44–17:00 New York rollover rule** (9.01: only with `InpCancelAtSessionEnd = true`). Pending orders are
>   still deleted then, because a fill there would be closed at once by the 16:44 flat.
>   - Every limit order is sent with a **server-side expiry no later than the next 16:44 New York**, so the broker
>     removes it even when no tick arrives. If the broker refuses expiry times, the order is GTC and relies on the
>     EA's own deletes.
>   - The EA also deletes pending orders on the first tick between 16:44 and 17:00.
>   - With `InpUseSession = true`, it cancels them on the first bar after a data gap when the switches extend order
>     life.
>   - No new order is sent in the last 2 minutes before 16:44.
>
>   The log calls these deletes `ROLLOVER`, but the record reason is `SESSION_END`, so these setups also count in the
>   panel's `session` count. The panel shows the number of deleted orders next to it.
> - **The hard limits:** 0.20 % risk per setup, 1 % daily loss, 120-minute time stop (switchable since v4), tester /
>   demo only.
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
  - **1.00 % planned daily loss** per FX day (from 17:00 New York), then lockout. v10: it covers all setups together
    (the loss realised today + the planned risk of every open position and pending order);
  - at most `InpMaxSetups` setups with orders or positions at a time (v10, default 5, at most 10; one on a netting
    account; one at a time up to v9), and one trade per leg (no copies of the same orders);
  - no martingale, grid, averaging down or size increase after losses. The three Fibonacci entries are a fixed plan,
    decided once, with a fixed total risk. They are never added after a loss. v10: another setup (another BPR, another
    leg) may trade the same direction while an earlier one is in loss; it is decided from its own signal, never from
    the loss, and its 0.20 % counts in the 1.00 % of the day.
- **Default exits** (on by default; since v4 each can be switched off for the tester / demo, and a run with either off
  is **not a research trial**, see the top): every position is closed at most **120 minutes after its fill**
  (`InpUseTimeStop`) and before **16:44 New York** (`InpFlatBeforeRollover`).
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
| `InpDirection` | BOTH | BOTH, LONG_ONLY or SHORT_ONLY (of the **trade**: a bullish BPR's reversal is a short) |
| `InpSetupType` | CONTINUATION | **v6/v7.** `CONTINUATION` (v1–v5), `REVERSAL` (breakout through the BPR, traded the other way), `BOTH` (v7: a continuation setup and a reversal setup per BPR, each on its own). See the top. |
| `InpRevLevel` | DEEPEST | **v7.** Reversal level: `DEEPEST` wick of the T1 / T2 candles, `T1` wick, or `LAST` touch candle's wick (v6) |
| `InpRevNeedRejection` | true | **v7.** A rejection after T1 must come before the reversal breakout (`false` = v6) |
| `InpRevBodyInBox` | true | **v11.** Reversal: the bodies of the T1 / T2 candles (every candle of the touch; an early second tap counts as T2) and of C1 .. C`InpRevRejCandles` must stay in the box or on its side of it (tapped from above: not below the box's bottom; on the edge is in). Otherwise the setup ends: no trade (`DONE BROKEN`). The wicks may go out. |
| `InpRevRejCandles` | 2 | **v9.** At least this many candles in the BPR's direction (green for a bullish BPR, red for a bearish one) after the T1 candle, before the reversal breakout. They need not follow each other. A close beyond the reversal level that is not the breakout does not count, restarts the count and is no touch (no T2, the level stays). A failed breakout keeps the count. `0` = v8. |
| `InpRevNeedFvg` | false | **v8.** `true`: the reversal waits for an FVG of the drop after its 100 % before its limits (v7). `false`: the limits can go in on the confirming close. |
| `InpMaxBarsToT1` | 0 | **v8.** Bars from a BPR's creation to its first touch: 0 = no limit (every BPR is followed until it is touched); `-1` = v7 rules (the breakout window counts from the creation, warm-up BPRs are dropped, a full list refuses new BPRs, no one-candle rejection). |
| `InpTouchEntry` | false | **v6.** A market order in the BPR's direction at the next open after the T1 candle (if it did not break the BPR). Stop beyond the BPR + `InpStopBufferTicks`. |
| `InpTouchTargetRR` | 1.5 | **v6.** Take-profit of the touch entry in R (0.1–20) |
| `InpMaxTouches` | 2 | Touches of the BPR allowed. Consecutive touching candles count as one touch. One more touch ends the setup. |
| `InpConfirmCloses` | 2 | Candles that must **close** beyond the breakout level: the breakout candle plus the next one |
| `InpRejectBeforeBreak` | false | Stricter reading. A rejection candle (one that does not touch the zone) must come **before** the breakout candle, so the first candle out of the zone can no longer be the breakout. |
| `InpFvgRule` | LUXALGO | FVG needed in the breakout leg. `LUXALGO`: an FVG the LuxAlgo engine makes (displacement candle + gap). `ANY_GAP`: any 3-candle gap. `NONE`: no FVG needed. |
| `InpSetupExpiryBars` | 240 | v8: the bars a setup may spend **at its BPR** without confirming: from the first candle of its latest visit (T1, T2, a pullback), and in a breakout from the breakout candle. While price is away after a rejection the count stops. With `InpMaxBarsToT1 = -1`: from the BPR's creation (a reversal setup: from its last rejection when later). |
| `InpLegExpiryBars` | 60 | After the confirmation, orders may be placed or filled for this many bars |
| `InpPendingMaxMin` | 0 | **v10.** A setup's limit orders are cancelled this many minutes after its first placement (`EXPIRED`, "pending-order time limit"). A move does not restart it; a filled entry runs on. 0 = no time limit. |
| `InpAnticipateEntries` | **true** | **v5 switch, on by default since v8.** The limits are placed from the confirmation (continuation: FVG condition still needed), without waiting for a pullback candle, and moved at every new high / low of the leg. A fast pullback fills them instead of ending in `LEG_BROKEN`. `false` = wait for a pullback candle (v4–v7). |
| `InpLegBreakOnClose` | false | **v5 switch.** `true`: `LEG_BROKEN` only when a candle closes beyond the leg origin (a wick is not enough). |
| `InpFib1` / `InpFib2` / `InpFib3` | 50 / 61.8 / 71 | Entry retracements in % of the leg. 0 turns an entry off. |
| `InpStopFib` / `InpStopBufferTicks` | 100 / 10 | Stop at this retracement (100 = the leg origin) plus this many ticks |
| `InpTargetFib` | 0 | Take-profit retracement. 0 = the leg high (long) or low (short); negative = an extension beyond it. |
| `InpUseRRFilter` | true | **v3 switch.** `false`: the reward:risk filter is off, whatever `InpMinRR` says |
| `InpMinRR` | 0 | Minimum reward:risk per entry (0 = off) |
| `InpUseCostFilter` | true | **v3 switch.** `false`: the cost filter is off, whatever `InpMaxCostR` says. Entries go out even when costs are a large part of their risk. |
| `InpMaxCostR` | 0.30 | Skip an entry whose round-trip cost (spread + commission + 2 ticks of slippage) exceeds this fraction of its risk (0 = off) |
| `InpUseTimeStop` | true | **v4 switch.** `false`: no time stop (`close at market: TIME`); the position runs to its SL / TP or the 16:44 flat. Not a research trial. |
| `InpMaxHoldMin` | 120 | Time stop per position, minutes (capped at 120; used only while `InpUseTimeStop = true`) |

### Session, risk and execution

| Input | Default | Meaning |
|---|---|---|
| `InpServerMode` / `InpServerOffsetH` | NY+7 / 0 | Server time → UTC. NY+7 is IC Markets (`UNVERIFIED`). The [self-check](#self-check-at-start) prints the resulting entry window. |
| `InpUseSession` | true | New orders only 08:00 London → 14:45 New York, Mon–Fri. Pending orders are cancelled at 14:45 New York (unless `InpCancelAtSessionEnd = false`). |
| `InpCancelAtSessionEnd` | true | **v3 switch.** `false`: pending orders are kept after 14:45 New York until they fill, the leg breaks or expires, or the target is reached. **9.01:** also over the 16:44–17:00 New York rollover (no rollover delete, no 16:44 expiry), and when no order can be sent a new high / low does not cancel them to move them. With `InpFlatBeforeRollover = true` a fill between 16:44 and 17:00 is closed at once. |
| `InpEntriesAfterSessionEnd` | false | **v3 switch.** `true`: new orders may also be placed from 14:45 to 16:44 New York (Mon–Fri). |
| `InpFlatBeforeRollover` | true | **v4 switch.** `false`: no 16:44 New York flat (`close at market: ROLLOVER`); positions may be held over the rollover and the weekend (swap, gap risk). Pending orders are still deleted at 16:44. Not a research trial. |
| `InpRiskPct` | 0.20 | Risk **per setup**, % of equity incl. commission, split over the entries (capped at 0.20) |
| `InpDailyLossPct` | 1.00 | Planned daily loss, % (capped at 1.00). v10: realised loss today + the planned risk of all setups' positions and orders. |
| `InpMaxSetups` | 5 | **v10.** Setups with orders or positions at the same time, each with its own `InpRiskPct` (1 = one at a time, as v2–v9; at most 10). Netting accounts: always 1. |
| `InpMaxTradesDay` | 0 | Maximum positions per FX day (0 = no limit) |
| `InpCommissionPerLotSide` | 3.50 | Commission per lot per side, account currency (`UNVERIFIED`) |
| `InpSlippageTicks` | 1 | Added to the stop distance for sizing, and to the cost check |
| `InpMaxSpreadPts` | 0 | No new orders while the spread is above this (0 = off) |
| `InpMagic` | 2610091 | Magic number, the same for v2, v3 and v4. It differs from v1, so v1 positions are not mixed in. |
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
   - A low below `O` ends the setup (`LEG_BROKEN`). With `InpLegBreakOnClose = true`, only a close below `O` does.
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
   - its costs exceed 0.30 of its risk (`COST`; switched off with `InpUseCostFilter = false`).

   The three entries share 0.20 % of equity: 0.067 % each.

   **With `InpAnticipateEntries = true`**, no pullback candle is needed. The orders are computed on the confirmation
   candle `B2` (if the FVG condition already holds; otherwise on the first candle where it does) and on every later
   candle of the leg.
7. **Re-anchor.** A new high **before any fill** cancels the orders (`CANCEL NEW_EXTREME`). The EA updates `X` and
   places new orders on the next pullback candle. With `InpAnticipateEntries = true`, it places them on the same
   candle at the new Fibonacci, so orders wait in the book during the whole leg.
8. **After a fill.** When the target is touched or a new high comes, the remaining limits are cancelled
   (`CANCEL TARGET`). Each position exits at:
   - its SL or TP;
   - the 120-minute time stop (off with `InpUseTimeStop = false`);
   - the 16:44 New York flat (off with `InpFlatBeforeRollover = false`).

   Unfilled orders are also cancelled at 14:45 New York (`SESSION_END`; kept with `InpCancelAtSessionEnd = false`,
   since 9.01 also over the 16:44 New York rollover) and after `InpLegExpiryBars` (`EXPIRED`).

If a level is already reached when its order is sent (a gap at the next bar's open), it is sent as a **market order**
at the better price, with the same SL / TP.

**v7 reversal (`InpSetupType = REVERSAL / BOTH`).**
- **Steps 1–2.** The same: T1, and T2 after a rejection.
- **Step 3.** After a rejection (`InpRevNeedRejection`), a candle **closes below the reversal level**, and the next one
  closes below it too.
  - The level is the deeper wick of the T1 / T2 candles (`InpRevLevel`).
  - These candles may touch or cross the zone.
  - A visit of the zone after T2 is the pullback, not a third touch.
- **The trade is a short.**
  - The leg runs from the top of the move (100 %) down to the lowest low (0 %).
  - The top is the highest high since T1, or the top of the last bounce from the zone.
  - Steps 5–8 are mirrored: sell limits, SL above, TP at the low.
- **A broken BPR.** A low below the BPR does not end a reversal setup in step 2 (`BROKEN` is continuation-only).
- **`BOTH`.** The BPR has a continuation setup and a reversal setup, each with its own steps.
- **v6 touch entry.** With `InpTouchEntry = true`, the close of T1 (step 2) also sends a market buy with its own stop
  and target (see the top). It belongs to the continuation setup, or to the reversal setup with `REVERSAL`.

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
  - **v7 `BOTH`:** the two setups of a BPR draw the same zone and `T1` / `T2` labels on top of each other. When one
    ends while the other is still followed, its copy is removed (7.01), so the live one stays coloured. The reversal
    setup's breakout line starts at the candle whose wick is the level.

## Panel: why no orders?

The panel (top left) answers "why is nothing happening?" at a glance:

| Row | Example | How to read it |
|---|---|---|
| 1 | `mode: TESTER \| algo trading: ON` | `REAL: LOG-ONLY` or `algo trading: OFF - …` means no order can go out; the reason is spelled out. |
| 2 | `rules: touches <= 2, 2 closes, FVG LUXALGO \| entries 50.0% 61.8% 71.0% \| …` | The active rules |
| 3 | `switches: cost filter <= 0.30 R \| RR filter off (InpMinRR = 0) \| entry window 08:00 LDN-14:45 NY \| cancel at window end ON … \| rollover order deletes 0` | **v3:** the state of the switches and the effective entry window |
| 4 | `exits: server SL/TP \| time stop 120 min \| 16:44 New York flat ON` | **v4:** the position exits that are on. With a switch off it adds `NOT a research trial`. |
| 5 | `tracking: wait 3 zone 1 breakout 0 leg 1 ordered 0 filled 0` | Setups in each phase now |
| 6 | `funnel: BPRs 57 \| touches 31 \| breakouts 9 (failed 3) \| confirmed 6 \| entry decisions 9 (orders accepted 9) \| closed 2` | How far setups get, cumulative since start |
| 7 | `entries skipped: missed 1 cost 7 rr 0 bad 0 \| dropped: size 0 refused 0 expired 0` | Why decided entries were not sent: `cost` → `InpUseCostFilter` / `InpMaxCostR`; `rr` → `InpUseRRFilter` / `InpMinRR`; `size` → the account is too small for the minimum volume; `refused` → the broker refused (see row 10 and the log) |
| 8 | `waiting: no FVG 12 bars \| blocked: session 40 slot 0 daily-risk 0 spread/catch-up 0 \| retried 0 \| re-anchored 2` | Ready setups that could not decide, and why |
| 9 | `ended: broken 30 … session 0 (rollover order deletes 0) refused 0 …` | How setups ended without a trade |
| 10 | `orders: accepted 9 refused 0 \| filling … \| last error: …` | Broker responses, with the last retcode |
| 11 | `orders/positions (2 of 5 setups): #12 LONG SL … TP …: L1 limit … \| L2 open 0.04 @ … \|\| #15 …` | The live orders and positions, per setup (v10: `\|\|` between setups) |
| 12 | `today: … \| lockout: no \| positions 2 \| last: …` | Daily risk state and the last event |

The same rows go to the Experts log as `DIAG` lines at every new FX day and when the EA stops.

## Self-check at start

After the warm-up the Experts log shows `SELF-CHECK` lines:
- **account:** mode, hedging or **netting**, equity, leverage;
- **permissions:** OK, or exactly which switch blocks trading;
- **symbol:** tick size, value of a 1.0 price move per lot, stops and freeze levels, current spread, filling and
  expiration modes;
- **risk:** the budget per entry. It also gives the **largest stop that the minimum volume (e.g. 0.01 lot) still
  fits**. Wider stops give `SIZE_BELOW_MIN`, so raise the test deposit if that number is small;
- **switches and exits:** the v3 switches, and the v4 exits that are on (`exits: …`), with a note on the extra risk
  when the time stop or the 16:44 flat is off;
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
3. `BFEA11_trades_*_TESTER.csv` and `BFEA11_setups_*_TESTER.csv` from the Common Files folder (`BFEA10_*` in v10, `BFEA9_*` in v9, `BFEA8_*` in v8, `BFEA7_*` in v7,
   `BFEA6_*` in v6, `BFEA2_*` before).

## Logs

- **Experts log:** one line per detector record. Examples:
  - `#12 LONG TOUCH 1 of max 2 (zone …)`
  - `#12 LONG BREAKOUT level 2351.20 (high of the candle at …)`
  - `#12 LONG CONFIRM: leg 2349.50 -> 2353.80`
  - `#12 LONG PLACE_LIMIT L2 (61.8%) P= SL= TP=`
  - `#12 LONG SKIP L3 (71.0%) (COST)`
  - `#12 LONG CANCEL L1 (50.0%) (NEW_EXTREME)`
  - `#12 LONG DONE (BROKEN)`
  - `#13 REV SHORT BREAKOUT level 2349.10 (REVERSAL: deepest T1 / T2 wick, the low of the touch candle at …)` (v7: a
    reversal setup)

  The execution layer adds:
  - `… LIMIT LONG sent: lots P= SL= TP= planned risk`;
  - `FILLED`;
  - `CLOSED TP pnl … R=…`;
  - `orders not sent now: <reason>`, and the order-failure lines with the broker's retcode.
- **CSV** in the Common Files folder. `_TESTER` files are rewritten on each tester run; `_LIVE` files are appended to.
  - **`BFEA11_setups_<symbol>_<tf>_<magic>_<TESTER|LIVE>.csv`** (`BFEA10_*` / `BFEA9_*` / `BFEA8_*` / `BFEA7_*` / `BFEA6_*` in v10 / v9 / v8 / v7 / v6, same columns; `BFEA2_*` up to v5,
    two columns fewer). One row per setup when it ends, plus the open ones when the EA stops. Columns:
    - `run, id, dir, created_time, B, T, touches`;
    - `ref_time, level, breakout_time, confirm_time, O, X`;
    - `decision_time, SL, TP, L1, L2, L3, phase, reason`;
    - `bpr_dir, setup`.

    `dir` is the trade direction and `bpr_dir` the BPR's direction; they differ for a reversal. `setup` is the setup's
    kind, `CONT` or `REV` (v7; with `BOTH` each BPR has one row of each). For a reversal setup, `level` / `ref_time`
    are the reversal level and the touch candle whose wick it is.

    `L1`–`L3` hold a state and a price (`CLOSED@2351.23`), a state and a reason (`SKIPPED:COST`), or `off`.
  - **`BFEA11_trades_<symbol>_<tf>_<magic>_<TESTER|LIVE>.csv`.** One row per closed position. Columns:
    - `run, id, levels, dir`;
    - `entry_time, entry, lots, SL, TP`;
    - `exit_time, exit, exit_reason, pnl, R, planned_risk, setup`.

    `setup` is `CONT`, `REV` or `TOUCH`; a touch entry's `levels` is `T`.

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
- **v7 reversal** (from the owner's screenshot; inputs where the words leave a choice):
  - the level is the deeper of the T1 / T2 wicks (`InpRevLevel`);
  - a rejection comes first (`InpRevNeedRejection`);
  - the 100 % is the top of the last bounce from the zone, measured after the visit's lowest low (a visit that turns
    straight into the breakdown keeps the earlier top);
  - with `DEEPEST`, a T2 wick counts once its visit is rejected;
  - the reversal's FVG comes after its 100 % bar;
  - a visit after T2 is the pullback, not a third touch;
  - `BOTH` is two setups per BPR.

## Known limitations

- **Not compiled yet.**
- **Strategy untested** (H-14). A pre-registered backtest (EXP011) is the next research step.
- **v10.**
  - **Several setups at a time** are tested on the C++ copy of the detector (slots, decisions, moves, touch entries).
    The executor's side (one context per setup, the slot and daily-loss checks, the order bookkeeping) is checked by
    reading, the static check and an adversarial review only, not in MT5.
  - **The time limit** is the broker-side expiry of each order (to the minute) plus the EA's cancel on the candle
    close. A symbol that refuses expiry times gets only the candle-close cancel. After a restart a setup is not
    restored, so its old orders are deleted at once anyway.
  - **Netting accounts** stay at one setup at a time.
- **Netting accounts.** The three fills merge into one position:
  - the time stop counts from the first fill;
  - closing one entry closes all of them;
  - one trades-CSV row covers the merged entries.
- **No setup recovery after a restart.** Setups in progress are not restored. Positions found at start are managed
  without their setup: server SL/TP, the time stop and the 16:44 flat (each while its v4 switch is on). Pending
  orders left from before are deleted.
- **Fills that race a cancel.** A fill that happens just as the EA cancels the order is managed without its setup.
- **Stopping the EA.**
  - Removing the EA, or closing its chart or the terminal, **closes its positions**: its market exits (the time stop
    and / or the 16:44 New York flat, whichever is on) would not run any more. It also deletes its pending orders. v4: with `InpUseTimeStop = false` **and** `InpFlatBeforeRollover =
    false`, the positions are kept with their server SL / TP.
  - A recompile, an input change or a timeframe change keeps the positions, and the restarted EA manages them again.
- **Spread and decision time.** Decisions use the spread at the first tick of the next bar. The Python reference uses
  a constant or modelled spread.
- **No news filter.**
- **v8 tracking.**
  - **List size.** With no limit to T1 and no window while price is away, BPRs stay in the list (128 setups; `BOTH`
    uses two per BPR) until they break, reach the touch limit, or newer ones push the one idle the longest out. In a
    long one-way move, BPRs far behind are dropped first.
  - **A visit with no rejection** (price sits in the zone or moves through it without a breakout) still ends after
    `InpSetupExpiryBars` bars.
  - **After a restart.** The warm-up BPRs that go on are rebuilt from the history at every start. One that had
    already traded before a restart is not traded twice: it is confirmed by then and ends at the warm-up.
- **v7 reversal.**
  - **Expiry.** With `InpMaxBarsToT1 = -1` a reversal setup has `InpSetupExpiryBars` (240 bars, 4 hours on M1) from
    its last rejection to confirm, and a slower reversal is not traded. v8 stops the count while price is away.
  - **`BOTH`.** It tracks twice as many setups (the capacity is 128) and writes two setups-CSV rows per BPR.
  - **One trade at a time.** A reversal that confirms while the continuation setup still holds orders or positions
    waits for the slot. Usually the continuation's stop is hit first, because its stop is beyond the touch low.
- **v6 setups (`InpSetupType`, `InpTouchEntry`).**
  - They exist in the MQL5 detector only, like v5. They are tested on the C++ copy of the detector under bar-based
    fills: the touch entry opens at the next bar's open, and exits are checked from the following bar.
  - The touch entry is not restored after a restart. Its position is then managed as an unowned position: server
    SL/TP, the time stop and the 16:44 flat.
  - Hedging and netting:
    - On a hedging account, a reversal short and the touch-entry buy of the same BPR can be open together. Their
      combined planned risk stays within the setup's 0.20 %.
    - On netting, the touch position blocks the slot until it closes.
- **v5 switches (`InpAnticipateEntries`, `InpLegBreakOnClose`).**
  - They exist in the MQL5 detector only. The Python reference and the parity harness cover the default rules.
  - The switched-on rules are tested on the C++ copy of the MQL5 detector, under the harness's bar-based fills, not
    in MT5.
  - On a live or demo server, the terminal can list a deleted order for a moment. The EA tolerates this for its own
    just-deleted orders. Anything else that keeps the slot busy postpones the move by one candle.

## Verification so far

**Reproducible, run in CI on every push:**

| Test | What it checks |
|---|---|
| `tests/test_bpr_breakout_ea_harness.py` | The pure files (`BfDefines`, `BfEngine`, `BfDetector`) are compiled as C++ and compared **record by record** with `qe/strategies/bpr_breakout.py`, under a bar-based fill/exit harness: 10 random configurations and 117 hand-built sequences (114 long and mirrored, incl. the v5 / v6 / v7 / v8 / v9 ones, each with three FVG rules and the strict-rejection option, plus 3 boundary cases), including exact comparison boundaries. Diagnostic counters must match too. Mutation checks: 24 deliberate small bugs (flipped comparisons, removed conditions, a wrong price or buffer) were all caught. |
| `tests/test_bpr_breakout_v8_tracking.py` | **v8 tracking and quick limits, on the C++ copy of the MQL5 detector only (49 tests).** The owner's tap-from-above example, long and short: T1 on 17 (wick 99.0), the one-candle rejection on 18, the limits on the second close (24) with their prices, moved on the new low (25), the target (28); the same bars with the v7 rules wait for a pullback candle (26); `BOTH` trades the continuation then the reversal. A first touch 300 bars after the creation (traded; v7 ended it EXPIRED on 254). `InpMaxBarsToT1 = 100`. The window: no clock while price is away (a continuation T2 300 bars later, a late break of the T1 wick, a late T2 then the break, a late continuation breakout: all traded; v7 ended them EXPIRED), a long visit still expires. The one-candle reaction (rejection, T2, break; not for a continuation setup, not with the v7 rules) and its boundary (a close exactly at the edge is no rejection). Capacity: a ladder of 80 BPRs price never revisits; with the harness built for 4 setups, a setup with pending orders and one in a visit are never dropped, the idle ones go in order of their last zone event (a BPR created first but rejected later is kept), and two random series (every dropped setup was idle). Warm-up setups kept in WAIT and ZONE (in the visit and after the rejection), not when confirmed. The reversal without the FVG wait, and the continuation unchanged by it. 6 random series (v6 / v7 invariants plus: no expiry before T1 without a limit) and causality. Mutation check: 22 of 22 caught; the 7.01 and v5 sets still caught on the v8 code (one known equivalent). |
| `tests/test_bpr_breakout_v9_rejection.py` | **v9 rejection candles, on the C++ copy of the MQL5 detector only (71 tests).** Your C1 / C2 example with its prices (breakout 22 with 2 rejection candles, limits on 23, target 27). Your complaint (T1, one candle, then the break): v8 traded it, v9 does not (DEEPEST / LAST, REVERSAL / BOTH). Two candles that do not follow each other. A close beyond the level too early restarts the count and is no touch (the level stays, with every `InpRevLevel`); a failed breakout keeps the count; a close through the whole BPR. A rule table: one, two and three candles with 1-3 needed, a doji, a red candle, a close exactly at the T1 wick (counts) and one tick below it (does not). The T1 candle does not count; the rejection is still needed; v8 mode unchanged. Your earlier examples still trade, the two one-candle ones no longer do. Warm-up, the continuation unchanged, 6 random series (the count recomputed from the bars; no T2 beyond the T1 wick) and causality. Mutation check: 16 of 18 caught, the 2 others equivalent (0 differences in 600 runs). |
| `tests/test_bpr_breakout_v11_body.py` | **v11 bodies in the box, on the C++ copy of the MQL5 detector only (47 tests).** Tapped from above and from below (the mirrored bars with bar 12 raised, so that no second BPR takes the trade): your "T1 NO" (T1 closes below the box), C1 / C2 below the box, a later candle of the T1 touch below it, T2 below it, an early second tap below it (and its next candle): each ends on that candle with no order, where v10 placed limits; a T1 wick out with its body in, and a T1 close exactly on the edge, still trade (limits on 23); an early second tap is checked only while 2 touches are allowed; one tick below the edge is out; a C candle opening below the box is out; your C1 / C2 example unchanged; continuation setups unchanged; a pullback visit is no touch; only C1 .. C`InpRevRejCandles` are checked; 6 random series recomputed from the bars; causality. Mutation check: 28 of 31 caught, the 3 others identical on 200 runs. |
| `tests/test_bpr_breakout_v10_multi.py` | **v10 time limit and several setups at a time, on the C++ copy of the MQL5 detector only (108 tests).** The time limit on your C1 / C2 example (limits on 23): cancelled exactly m minutes after the first placement (m = 1–9; M5 clock time), not restarted by a move, a filled entry runs on while the others are cancelled, a setup waiting to move after 14:45 ends, no limit before the first placement (also when the first decision could not be sent), the limit also with `InpCancelAtSessionEnd = false` (kept orders); with one and with five slots. Random series: no order placed or left in the book after the limit. Several setups (with and without anticipated entries): the slots are never exceeded and never left unused while a setup waits; when one at a time skipped a setup (in three cases a second setup confirmed on the same candle), v10 places it on that candle and follows the first trade exactly as before; a setup that moves its orders keeps its slot; a setup whose old order is stuck takes no other slot; one trade per leg (no two setups ever hold the same orders, and the first trade keeps its leg while it moves); one touch entry at a time; the entry-window, daily-risk and spread gates and their counters. Defaults (1 setup, no limit) = 9.01 (0 differences in 1006 runs against a 9.01 build). Causality. Mutation check: 42 of 45 caught; the 3 others give identical output (300 runs; two are covered by another guard). |
| `tests/test_bpr_breakout_v7_reversal.py` | **v7 reversal rules, on the C++ copy of the MQL5 detector only (66 tests; 7.01 added the review's cases: the same descent split two ways, a failed-breakout visit, a crash inside the T1 visit, an unrejected T2, the FVG before the 100 %, the expiry from the last rejection, a wide candle at the visit's low, a breakout inside a visit, a low after the bounce top).** The owner's example, long and short: level 99.50 at the T1 wick, closes on 28 / 29, 100 % = 101.6, 0 % = 96.4, the sell-limit prices, SL / TP, the target. With `BOTH` the continuation trade first (identical to `CONTINUATION`), then the reversal (identical to `REVERSAL`). The three level options in both wick orders and with equal wicks. The rejection rule. A pullback into the zone is no third touch. The 100 % at the last rejected bounce, at an unrejected T2 spike, and the 0 % at a wick inside a visit. Expiry; one touch allowed; setups per allowed trade direction; the touch entry once per BPR. On 8 random series it checks the v6 invariants plus the v7 ones: kinds; no `TOUCH_LIMIT` for a reversal setup; the reversal level recomputed from the touch candles' wicks for each option; the breakout close beyond it; a rejection first. It also checks coverage (a reversal after its BPR's continuation confirmed; a level taken from T2) and causality. The new sequences are in the parity set (defaults = v4 Python reference). Mutation check (v7): 31 of 33 deliberate bugs caught. The other 2 produce identical output on 800 random runs (equivalent). 7.01 set: 21 of 22 caught. The 22nd gives identical output on 1000 random runs. The v6 set catches every bug whose code still exists; the v5 set catches 17 of 17. |
| `tests/test_bpr_breakout_v6_setups.py` | **v6 reversal setup and touch entry, on the C++ copy of the MQL5 detector only (60 tests; v7: the v6 sequences that break down right after T1 run with the v6 options, and `BOTH` is checked per setup).** Long and short: the reversal trade (breakout, confirmation, leg 100.2 → 98.4, sell-limit prices, target); the T2 candle as the reversal level; a failed reversal then a continuation (BOTH); a close exactly on the level; a broken BPR ending only the continuation; the leg restarting at a new high; the direction filter on the trade; the touch entry's price, stop, target and RR, T1 only, no entry when T1 breaks the BPR, the cost filter; the setup's limits while its own touch position is open. On 10 random series it checks invariants: one setup with orders or positions at a time (touch positions included), a touch entry only into an empty slot, BPR versus trade direction, leg geometry, order geometry, and every T1 candidate tried after a skipped one. It also checks coverage and causality. With the defaults these sequences equal the v4 Python reference (parity set). Mutation check (v6): 29 of 29 deliberate bugs caught; the v5 set still catches 17 of 17. |
| `tests/test_bpr_breakout_v5_switches.py` | **v5 switches, on the C++ copy of the MQL5 detector only (44 tests).** Hand-built long and short sequences check: orders on the confirmation candle; the same-candle move on a new high; the FVG still required; the owner's fast pullback (filled, then stopped, never `LEG_BROKEN`); the close rule and its exact boundary; moves stopped by the leg expiry (with its boundary) and by a session cancel; the move still blocked by the entry window; spike candles and short legs on the extra decision candles. On 9 random series it checks invariants: one setup with orders at a time; on a move candle only the moving setup decides; no order after the leg expiry; SL < P < TP. It also checks causality: records up to bar t do not depend on later bars. The new sequences are also in the parity set above: with the switches off, they equal the v4 Python reference. Mutation check: 18 of 19 deliberate bugs caught; the 19th only differs in a state the slot rule makes unreachable. |
| `tests/test_bpr_breakout_strategy.py` | 53 scenario tests of the rules: exact Fibonacci prices, touches, breakout and failure, FVG rule, re-anchor, fills and target, cost / RR / missed entries, environment gates, executor feedback, warm-up, **causality (no look-ahead)** |
| `tools/mql5_static_check.py mql5/BprFvgEA` | Mechanical check: names and brackets. It cannot find MQL5 type errors. |

The v3 and v4 switches live in the executor only; the parity harness covers the detector, which they leave unchanged.
The switched-off exits are not covered by any automated test (MT5 execution is not simulated here).

None of this proves that MetaEditor compiles the code, that MT5 executes the orders as intended, or that the strategy
has an edge.
