"""Hand-built bar sequences for the BprFvgEA v2 detector (spec research/indicators/BPR_BREAKOUT_FIB_SPEC.md).

Used by tests/test_bpr_breakout_strategy.py (expected records) and tests/test_bpr_breakout_ea_harness.py (the same
sequences through the C++ transliteration of the EA). Not a test module itself.

PREFIX builds a bullish BPR: quiet bars, a bearish displacement candle (bearish FVG [97.5, 99.9] at bar 10), a
bullish displacement candle (bullish FVG [98.0, 99.95] at bar 13). The BPR_UP box is [98.0, 99.9], pos = +1, and the
long setup id 1 is ARMED on bar 13. `mirror()` turns any sequence into its short-side image (price -> 200 - price).
"""


def _r(x: float) -> float:
    return round(x, 2)


def bar(o: float, h: float, l: float, c: float) -> tuple[float, float, float, float]:  # noqa: E741
    return (_r(o), _r(h), _r(l), _r(c))


def prefix() -> list[tuple[float, float, float, float]]:
    out = []
    for i in range(8):
        o = 100.0 + (0.1 if i % 2 else 0.0)
        c = o + (0.1 if i % 2 == 0 else -0.1)
        out.append(bar(o, max(o, c) + 0.02, min(o, c) - 0.02, c))
    out += [
        bar(100.0, 100.05, 99.9, 99.95),   # 8
        bar(99.95, 99.97, 97.98, 98.0),    # 9  bearish displacement
        bar(97.4, 97.5, 97.0, 97.1),       # 10 bearish FVG [97.5, 99.9]
        bar(97.1, 98.0, 97.05, 97.9),      # 11
        bar(97.9, 99.92, 97.88, 99.9),     # 12 bullish displacement
        bar(99.95, 100.3, 99.95, 100.2),   # 13 bullish FVG [98.0, 99.95]; BPR_UP [98.0, 99.9] -> setup 1 ARMED
    ]
    return out


# touch 1 on 14 (ref 14, level 100.2), rejection on 15, breakout on 16, confirmation + gap (ANY_GAP) on 17,
# new high on 18, first pullback bar 19 -> decision: O = 99.5, X = 101.6
BASE_TAIL = [
    bar(100.1, 100.2, 99.5, 100.0),     # 14 TOUCH 1
    bar(100.0, 100.15, 100.0, 100.1),   # 15 REJECT
    bar(100.1, 100.7, 100.05, 100.6),   # 16 BREAKOUT (close 100.6 > 100.2)
    bar(100.8, 101.3, 100.8, 101.2),    # 17 CONFIRM; gap: low 100.8 > high[15] 100.15
    bar(101.2, 101.6, 101.0, 101.5),    # 18 new high
    bar(101.5, 101.5, 101.1, 101.2),    # 19 pullback -> PLACE_LIMIT x3
]


def base() -> list[tuple[float, float, float, float]]:
    return prefix() + list(BASE_TAIL)


def check(bars: list) -> list:
    """Every bar must be a valid OHLC bar (low <= open, close <= high)."""
    for i, (o, h, l, c) in enumerate(bars):  # noqa: E741
        assert l <= min(o, c) and max(o, c) <= h, (i, (o, h, l, c))
    return bars


def mirror(bars: list, k: float = 200.0) -> list[tuple[float, float, float, float]]:
    return [bar(k - o, k - l, k - h, k - c) for (o, h, l, c) in bars]


def scenarios() -> dict[str, list]:
    """name -> bars. Every sequence is valid for the parity harness (fixed environment)."""
    b = base()
    sc: dict[str, list] = {}
    sc["base"] = b
    # fills: 50 % at 20, 61.8 % at 21, then the target 101.6 is touched on 23 (positions exit on later bars)
    sc["fill_target"] = b + [bar(101.2, 101.25, 100.5, 100.6), bar(100.6, 100.7, 100.25, 100.5),
                             bar(100.5, 101.0, 100.45, 100.9), bar(100.9, 101.7, 100.85, 101.65),
                             bar(101.65, 101.8, 101.5, 101.7), bar(101.7, 101.75, 101.6, 101.7)]
    # re-anchor: a new high on 20 before any fill, pullback on 21 -> new levels
    sc["reanchor"] = b + [bar(101.2, 102.0, 101.15, 101.9), bar(101.9, 101.95, 101.6, 101.7),
                          bar(101.7, 101.8, 101.5, 101.6)]
    # breakout fails: 16 closes above, 17 closes back below the level
    sc["break_fail"] = prefix() + [BASE_TAIL[0], BASE_TAIL[1], BASE_TAIL[2], bar(100.6, 100.65, 100.0, 100.1),
                                   bar(100.1, 100.15, 99.6, 99.8), bar(100.0, 100.1, 100.0, 100.05)]
    # touches: 14-15 touch (one touch), 16 rejects, 17 touch 2, 18 rejects, 19 touch 3 -> TOUCH_LIMIT
    sc["touch_limit"] = prefix() + [bar(100.1, 100.15, 99.6, 99.8), bar(99.8, 100.0, 99.7, 99.95),
                                    bar(99.95, 100.1, 99.95, 100.05), bar(100.05, 100.1, 99.8, 99.9),
                                    bar(99.95, 100.15, 99.95, 100.1), bar(100.1, 100.12, 99.85, 99.95)]
    # broken: low below the BPR bottom 98.0 before any breakout
    sc["broken"] = prefix() + [BASE_TAIL[0], bar(100.0, 100.1, 97.9, 98.2)]
    # leg broken: after the confirmation, price goes below the leg origin 99.5 before a decision (no FVG: NONE rule
    # off -> the pullback bars do not decide with LUXALGO, so the leg can break)
    sc["leg_broken"] = b[:19] + [bar(101.5, 101.55, 99.4, 99.6)]
    # the decision bar closes so that close + spread == the 50 % entry exactly (MISSED boundary): P50 = 100.65,
    # spread 0.1 -> close 100.55
    sc["missed_boundary"] = b[:19] + [bar(101.5, 101.5, 100.5, 100.55)]
    # FVG exactly on the reference candle (ANY_GAP): the only gap is on bar 17, which is also the last touching candle
    # (ref = 17). The rule needs a gap on a bar AFTER the reference candle, so no order may be decided.
    sc["fvg_on_ref"] = prefix() + [bar(100.1, 100.15, 99.6, 99.7),    # 14 touch 1
                                   bar(99.7, 99.75, 99.3, 99.4),      # 15 same touch (origin 99.3)
                                   bar(99.4, 99.95, 99.35, 99.75),    # 16 same touch (close below the level 99.75)
                                   bar(99.76, 99.85, 99.76, 99.8),    # 17 same touch; gap 99.76 > high[15] 99.75
                                   bar(99.95, 100.3, 99.92, 100.25),  # 18 BREAKOUT (> 99.85, does not touch)
                                   bar(100.25, 100.6, 99.84, 100.5),  # 19 CONFIRM (no gap: 99.84 < 99.85)
                                   bar(100.5, 100.55, 100.2, 100.3),  # 20 pullback, no FVG after ref
                                   bar(100.3, 100.4, 100.1, 100.2)]   # 21 pullback, no FVG after ref
    # A/B/C of the review: B closes above A's high but still touches the zone -> B is part of the touch (new
    # reference, level = B's high); C closes below B's high -> no breakout
    sc["touching_close_above"] = prefix() + [bar(100.1, 100.2, 99.6, 99.8),     # 14 TOUCH 1 (level 100.2)
                                             bar(99.8, 101.0, 99.7, 100.6),     # 15 touches, closes above 100.2
                                             bar(100.6, 100.8, 100.0, 100.7),   # 16 REJECT, close below 101.0
                                             bar(100.7, 100.9, 100.3, 100.5)]   # 17
    # the first candle out of the zone closes above the level: a breakout by default; with reject_before_break it
    # is only the rejection, and the next close above the level is the breakout
    sc["reject_is_breakout"] = prefix() + [bar(100.1, 100.2, 99.5, 100.0),     # 14 TOUCH 1
                                           bar(100.0, 100.6, 99.95, 100.5),    # 15 out of the zone, close > 100.2
                                           bar(100.5, 100.9, 100.4, 100.8),    # 16
                                           bar(100.8, 101.3, 100.7, 101.2),    # 17
                                           bar(101.2, 101.25, 100.9, 101.0)]   # 18
    # the same as base, but candle 17 has a long upper wick: not a LuxAlgo displacement candle, so the engine makes
    # no FVG after the reference candle (LUXALGO waits); the plain gap on 17 still counts for ANY_GAP
    sc["no_lux_fvg"] = b[:17] + [bar(100.8, 101.45, 100.8, 101.2)] + b[18:]
    # the full rule with two touches: touch 1 (14), a wick above the level that does not close above it (15),
    # touch 2 (17) after a rejection candle (16) -> the level becomes the high of candle 17; rejection (18),
    # breakout close (19, a displacement candle), second close + LuxAlgo FVG (20), new high (21), pullback (22) ->
    # three buy limits; 23 fills L1 and L2, 25 touches the target: L3 is cancelled and the setup closes
    sc["two_touches"] = prefix() + [bar(100.1, 100.2, 99.5, 100.0),     # 14 TOUCH 1
                                    bar(100.0, 100.3, 100.0, 100.15),   # 15 REJECT (wick above 100.2, close below)
                                    bar(100.15, 100.2, 99.95, 100.0),   # 16 still away from the zone
                                    bar(100.0, 100.05, 99.7, 99.8),     # 17 TOUCH 2 (ref; level 100.05)
                                    bar(99.92, 100.0, 99.92, 99.95),    # 18 REJECT
                                    bar(99.95, 100.6, 99.93, 100.5),    # 19 BREAKOUT (displacement candle)
                                    bar(100.65, 101.2, 100.65, 101.1),  # 20 CONFIRM; LuxAlgo FVG (gap over 18)
                                    bar(101.1, 101.5, 101.0, 101.4),    # 21 new high
                                    bar(101.4, 101.45, 101.0, 101.1),   # 22 pullback -> PLACE_LIMIT x3
                                    bar(101.1, 101.15, 100.35, 100.45),  # 23 fills L1 100.70 and L2 100.49
                                    bar(100.45, 100.9, 100.4, 100.85),  # 24
                                    bar(100.85, 101.55, 100.8, 101.5),  # 25 target 101.5 touched
                                    bar(101.5, 101.6, 101.4, 101.55)]   # 26
    sc["short_base"] = mirror(b)
    sc["short_fill_target"] = mirror(sc["fill_target"])
    sc["short_reanchor"] = mirror(sc["reanchor"])
    for v in sc.values():
        check(v)
    return sc


def v5_sequences() -> dict[str, list]:
    """Sequences of the BprFvgEA v5 entry switches (tests/test_bpr_breakout_v5_switches.py). They are also in the
    parity set at the default settings, where the EA must still equal the (v4) Python reference."""
    b = base()
    nolux = scenarios()["no_lux_fvg"]
    sq = {
        # the owner's case: last new high on 20, ONE candle (21) falls through all entries and below the origin 99.5,
        # 22 goes through the stop 99.40
        "fast_pullback": b + [bar(101.2, 102.0, 101.15, 101.9), bar(101.9, 101.95, 99.45, 99.6),
                              bar(99.6, 99.7, 99.3, 99.35)],
        # no LuxAlgo FVG after the reference candle: 20 wicks below the origin and closes above it, 21 closes below
        "wick_below_origin": nolux[:20] + [bar(101.2, 101.25, 99.45, 100.3), bar(100.3, 100.35, 99.3, 99.4)],
        # as above, but 20 closes EXACTLY on the origin, 21 one tick below
        "close_on_origin": nolux[:20] + [bar(101.2, 101.25, 99.45, 99.5), bar(99.5, 99.6, 99.45, 99.49)],
        # the first pullback candle 19 wicks below the origin and closes at 100.3
        "wick_then_decide": b[:19] + [bar(101.5, 101.55, 99.45, 100.3)],
        # the confirmation candle 17 spikes to 102.5 and closes at 100.3, beyond every entry; 18 pulls back up
        "spike_confirm": b[:17] + [bar(100.8, 102.5, 100.25, 100.3), bar(100.3, 101.0, 100.25, 100.95)],
        # pending limits from the leg to 101.6; 20 spikes to 104.0 (new extreme) and closes at 100.7, beyond every
        # new entry, without reaching the old ones; 21 comes back to 101.0; 22 dips to 100.7
        "spike_reanchor": b + [bar(101.2, 104.0, 100.6, 100.7), bar(100.7, 101.05, 100.65, 101.0),
                               bar(101.0, 101.0, 100.7, 100.75)],
        # as spike_confirm, but the next candle 18 is an ordinary pullback candle that also closes beyond every entry
        "spike_then_low": b[:17] + [bar(100.8, 102.5, 100.25, 100.3), bar(100.3, 100.4, 100.25, 100.3)],
        # the confirmation candle spikes to 102.5 and closes at 100.9 (beyond the 50 % entry only); 18 is an ordinary
        # pullback candle closing at 100.8
        "spike_confirm_mid": b[:17] + [bar(100.8, 102.5, 100.25, 100.9), bar(100.9, 101.0, 100.7, 100.8)],
        # a short leg at the confirmation: touch 14 (origin 99.5), reject 15, breakout 16, confirmation + gap 17 with
        # X = 100.35 (leg 0.85: costs above 0.30 of the risk), new high 101.0 on 18, pullback 19
        "short_leg_confirm": prefix() + [bar(100.1, 100.2, 99.5, 100.0), bar(100.0, 100.15, 100.0, 100.1),
                                         bar(100.1, 100.3, 100.05, 100.25), bar(100.25, 100.35, 100.2, 100.3),
                                         bar(100.3, 101.0, 100.3, 100.95), bar(100.95, 100.95, 100.7, 100.8)],
        # a second new high on 20 after a pullback on 19, then 21 (leg expiry tests)
        "late_high": b + [bar(101.2, 102.0, 101.15, 101.9), bar(101.9, 101.95, 101.6, 101.7)],
    }
    for v in sq.values():
        check(v)
    return sq


def v6_sequences() -> dict[str, list]:
    """Sequences of the BprFvgEA v6 setups (tests/test_bpr_breakout_v6_setups.py): the reversal setup and the touch
    entry. Also in the parity set at the default settings (CONTINUATION, no touch entry). Bullish BPR [98.0, 99.9]
    armed on 13 (prefix); mirror() gives the bearish / long side."""
    p = prefix()
    sq = {
        # T1 on 14 (its low 99.5 = the reversal level, its high 100.2 = the reversal leg origin); 15 closes below
        # 99.5 (reversal breakout), 16 closes below it again (confirmation, short; gap 99.35 < low[14] 99.5);
        # 17 new low 98.4; 18 pullback -> three sell limits; 19 fills the 50 % (99.3); 20 reaches the target
        "reversal": p + [bar(100.1, 100.2, 99.5, 100.0), bar(100.0, 100.05, 99.2, 99.3),
                         bar(99.3, 99.35, 98.8, 98.9), bar(98.9, 98.95, 98.4, 98.5),
                         bar(98.5, 98.8, 98.45, 98.7), bar(98.7, 99.4, 98.65, 99.35),
                         bar(99.35, 99.4, 98.3, 98.35)],
        # 15 closes below 99.5 (reversal breakout), 16 closes back above it (BREAK_FAIL: still the same touch);
        # 17 is a rejection (above the zone), 18 closes above the touch level 99.8 of candle 16 (continuation breakout
        # with BOTH), 19 confirms
        "rev_fail_then_cont": p + [bar(100.1, 100.2, 99.5, 100.0), bar(100.0, 100.05, 99.2, 99.3),
                                   bar(99.3, 99.8, 99.25, 99.7), bar(99.95, 100.0, 99.92, 99.95),
                                   bar(99.95, 100.4, 99.93, 100.3), bar(100.3, 100.8, 100.25, 100.7)],
        # T1 on 14, rejection 15, T2 on 16 (its low 99.6 = the new reversal level), 17 closes at 99.55: below the
        # T2 candle's low but above the T1 candle's low -> reversal breakout; 18 confirms
        "rev_t2": p + [bar(100.1, 100.2, 99.5, 100.0), bar(100.0, 100.15, 99.95, 100.1),
                       bar(100.1, 100.12, 99.6, 99.8), bar(99.8, 99.85, 99.5, 99.55),
                       bar(99.55, 99.6, 99.1, 99.2), bar(99.2, 99.25, 98.9, 99.0)],
        # 15 breaks the BPR (low 97.9) but closes above the T1 candle's low (no reversal); 16 does not touch and closes
        # above the touch level (100.1, high of 15): a continuation breakout - not any more once the BPR is broken (BOTH)
        "broken_then_up": p + [bar(100.1, 100.2, 99.5, 100.0), bar(100.0, 100.1, 97.9, 99.6),
                               bar(99.95, 100.5, 99.95, 100.4), bar(100.4, 100.8, 100.35, 100.7)],
        # continuation breakout on 15; 16 closes above the level again but its low breaks the BPR (97.9): no
        # confirmation once the BPR is broken (BOTH: BREAK_FAIL)
        "broken_in_break": p + [bar(100.1, 100.2, 99.5, 100.0), bar(100.1, 100.7, 100.05, 100.6),
                                bar(100.6, 100.65, 97.9, 100.3), bar(100.3, 100.6, 100.2, 100.5)],
        # 15 closes EXACTLY on the T1 candle's low 99.5 (no reversal: the rule is strict); 16 closes below it
        "rev_close_on_level": p + [bar(100.1, 100.2, 99.5, 100.0), bar(100.0, 100.05, 99.3, 99.5),
                                   bar(99.5, 99.55, 99.2, 99.3), bar(99.3, 99.35, 98.9, 99.0)],
        # same touch: 15 dips to 99.3 (closes 99.6, no reversal), 16 makes a new high 100.3 (the reversal leg restarts
        # there: its extreme is reset to 16's low 99.7); 17 closes below 99.5 (low 99.4), 18 confirms: X = 99.4, not 99.3
        "rev_new_origin": p + [bar(100.1, 100.2, 99.5, 100.0), bar(100.0, 100.05, 99.3, 99.6),
                               bar(99.75, 100.3, 99.7, 99.8), bar(99.8, 99.85, 99.4, 99.45),
                               bar(99.45, 99.5, 99.41, 99.42)],
        # bull trap then breakdown: T1 14, rejection 15, T2 16 (low 99.6, high 100.12), 17 continuation breakout
        # (no touch, close 100.25 > 100.12), 18 closes back below the T2 low (BREAK_FAIL of the continuation and,
        # with BOTH, the reversal breakout on the same candle), 19 confirms the reversal
        "cont_fail_then_rev": p + [bar(100.1, 100.2, 99.5, 100.0), bar(100.0, 100.15, 99.95, 100.1),
                                   bar(100.1, 100.12, 99.6, 99.8), bar(99.95, 100.3, 99.95, 100.25),
                                   bar(100.25, 100.3, 99.3, 99.4), bar(99.4, 99.45, 99.1, 99.2)],
        # the other way round: reversal breakout 15, then 16 does not touch and closes above the touch level 100.2
        # (BREAK_FAIL of the reversal and, with BOTH, the continuation breakout on the same candle), 17 confirms
        "rev_fail_then_cont_bar": p + [bar(100.1, 100.2, 99.5, 100.0), bar(100.0, 100.05, 99.2, 99.3),
                                       bar(99.95, 100.6, 99.95, 100.5), bar(100.5, 100.9, 100.45, 100.8)],
        # the T1 candle 14 already breaks the BPR (low 97.9 < 98.0): no touch entry; CONTINUATION ends BROKEN
        "t1_breaks": p + [bar(100.1, 100.2, 97.9, 99.0), bar(99.0, 99.2, 98.6, 98.7)],
    }
    for v in sq.values():
        check(v)
    return sq



def v7_sequences() -> dict[str, list]:
    """Sequences of the BprFvgEA v7 reversal rules (tests/test_bpr_breakout_v7_reversal.py), from the owner's example of
    2026-10-15 ("t1 + rejection from it and pullback with breakout of T1 or T2 wick with closing below or above it").
    Also in the parity set at the default settings. Bullish BPR [98.0, 99.9] armed on 13 (prefix); mirror() gives the
    bearish side."""
    p = prefix()
    sq = {
        # the owner's screenshot: 'two_touches' (T1 14 wick 99.5, T2 17 wick 99.7, continuation trade 19-25 up to
        # 101.6), then the drop: 28 is the first close below the T1 wick, 29 the second (and breaks the BPR), 30 the
        # low 96.4 (0 %), 31-32 pull back to the 50 % (99.0), 34 reaches the target. Fibonacci 101.6 (100 %) -> 96.4.
        "owner_example": scenarios()["two_touches"] + [
            bar(101.55, 101.6, 100.85, 100.9), bar(100.9, 101.0, 98.95, 99.05), bar(99.05, 99.4, 97.1, 97.2),
            bar(97.2, 97.4, 96.4, 96.5), bar(96.5, 98.1, 96.45, 98.0), bar(98.0, 99.3, 97.9, 99.1),
            bar(99.1, 99.2, 97.0, 97.1), bar(97.1, 97.2, 96.2, 96.3)],
        # T1 14 (wick 99.5), rejection 15, T2 16 (wick 99.7, shallower), rejection 17; 18 visits the zone and closes at
        # 99.6 - below the T2 wick, above the T1 wick; 19 closes below both (99.3), 20 again (99.1)
        "rev_level_between": p + [bar(100.1, 100.2, 99.5, 100.0), bar(100.0, 100.3, 99.95, 100.2),
                                  bar(100.2, 100.25, 99.7, 99.95), bar(99.95, 100.3, 99.92, 100.2),
                                  bar(100.2, 100.22, 99.55, 99.6), bar(99.6, 99.65, 99.2, 99.3),
                                  bar(99.3, 99.35, 98.9, 99.1), bar(99.1, 99.4, 99.05, 99.35)],
        # T1 14 (wick 99.6), rejection 15, T2 16 (wick 99.4, deeper), rejection 17; 18 closes at 99.5 - below the T1
        # wick, above the T2 wick; 19 closes below both (99.2), 20 again (99.0)
        "rev_level_deeper_t2": p + [bar(100.1, 100.2, 99.6, 100.0), bar(100.0, 100.3, 99.95, 100.2),
                                    bar(100.2, 100.25, 99.4, 99.95), bar(99.95, 100.3, 99.92, 100.2),
                                    bar(100.2, 100.22, 99.45, 99.5), bar(99.5, 99.55, 99.1, 99.2),
                                    bar(99.2, 99.25, 98.8, 99.0), bar(99.0, 99.3, 98.95, 99.25)],
        # T1 14, rejection 15, T2 16, rejection 17 (wick to 100.9; closes below the continuation level 100.15), 18 a
        # third visit of the zone that closes inside it (99.7, above the T1 wick): the pullback; 19 closes below the
        # T1 wick, 20 confirms (low 98.9), 21 pulls back -> sell limits on 100.9 -> 98.9
        "pullback_in_zone": p + [bar(100.1, 100.2, 99.5, 100.0), bar(100.0, 100.18, 99.95, 100.1),
                                 bar(100.1, 100.15, 99.7, 99.85), bar(99.95, 100.9, 99.93, 100.1),
                                 bar(100.1, 100.12, 99.6, 99.7), bar(99.7, 99.75, 99.2, 99.3),
                                 bar(99.3, 99.35, 98.9, 99.0), bar(99.0, 99.6, 98.95, 99.5)],
        # T1 14, rejection 15 with a wick to 101.6, T2 16, rejection 17 (the last bounce: top 100.6), 18 closes below
        # the T1 wick from inside the zone, 19 confirms: the 100 % is the last bounce's top 100.6, not 101.6
        "bounce_origin": p + [bar(100.1, 100.2, 99.5, 100.0), bar(100.0, 101.6, 99.95, 100.1),
                              bar(100.1, 100.15, 99.7, 99.85), bar(99.95, 100.6, 99.93, 100.1),
                              bar(100.1, 100.12, 99.3, 99.4), bar(99.4, 99.45, 99.0, 99.1),
                              bar(99.1, 99.5, 99.05, 99.45)],
        # T1 14 and T2 16 have the same wick 99.5: DEEPEST keeps the T1 candle (strictly deeper only); 18 closes below
        "rev_level_equal": p + [bar(100.1, 100.2, 99.5, 100.0), bar(100.0, 100.3, 99.95, 100.2),
                                bar(100.2, 100.25, 99.5, 99.95), bar(99.95, 100.3, 99.92, 100.2),
                                bar(100.2, 100.22, 99.3, 99.4), bar(99.4, 99.45, 99.0, 99.1),
                                bar(99.1, 99.5, 99.05, 99.45)],
        # T1 14, R 15, T2 16, R 17 (top 101.4), 18 a third visit (the pullback, closes inside), 19 rejects it (bounce
        # top 100.7), 20 closes below the T1 wick, 21 confirms: the 100 % is the last bounce's top 100.7
        "pullback_bounce": p + [bar(100.1, 100.2, 99.5, 100.0), bar(100.0, 100.18, 99.95, 100.1),
                                bar(100.1, 100.15, 99.7, 99.85), bar(99.95, 101.4, 99.93, 100.1),
                                bar(100.1, 100.12, 99.6, 99.7), bar(99.95, 100.7, 99.92, 100.0),
                                bar(100.0, 100.05, 99.3, 99.4), bar(99.4, 99.45, 99.0, 99.1),
                                bar(99.1, 99.6, 99.05, 99.55)],
        # T1 14, R 15, T2 16 spikes to 101.2 and falls into the zone; 17 closes below the T1 wick from that visit
        # (not rejected): the 100 % is the highest high since T1, the T2 candle's 101.2; 18 confirms
        "t2_spike": p + [bar(100.1, 100.2, 99.5, 100.0), bar(100.0, 100.18, 99.95, 100.1),
                         bar(100.1, 101.2, 99.7, 99.8), bar(99.8, 99.85, 99.3, 99.4),
                         bar(99.4, 99.45, 99.0, 99.1), bar(99.1, 99.6, 99.05, 99.55)],
        # T1 14, R 15, T2 16 (top 100.9), 17 still in the visit with a wick to 99.25 (below the T1 wick, close above
        # it), 18 rejects it, 19 closes below the T1 wick (low 99.3), 20 confirms (low 99.28): 100 % = 100.9, 0 % =
        # the lowest low after it, 17's 99.25
        "visit_deep_wick": p + [bar(100.1, 100.2, 99.5, 100.0), bar(100.0, 100.18, 99.95, 100.1),
                                bar(100.1, 100.9, 99.7, 99.8), bar(99.8, 99.85, 99.25, 99.6),
                                bar(99.95, 100.3, 99.92, 100.0), bar(100.0, 100.05, 99.3, 99.4),
                                bar(99.4, 99.45, 99.28, 99.35), bar(99.35, 99.6, 99.3, 99.55)],
        # v7.01 (review): the same descent split into candles two ways. After 'two_touches' (top 101.6 on 26) price
        # visits the zone on 28 (low 99.6), bounces to 100.35 (REJECT on 30) and breaks down 31-32. split_a: 27
        # already falls to 100.0; split_b: 27 stays high and 28 falls the whole way. Both: 100 % = 100.35.
        "split_a": scenarios()["two_touches"] + [
            bar(101.55, 101.6, 100.0, 100.1), bar(100.1, 100.15, 99.6, 99.7), bar(99.7, 100.3, 99.65, 100.2),
            bar(100.2, 100.35, 99.95, 100.0), bar(100.0, 100.05, 99.3, 99.4), bar(99.4, 99.45, 98.9, 99.0),
            bar(99.0, 99.05, 98.4, 98.5), bar(98.5, 99.0, 98.45, 98.95)],
        "split_b": scenarios()["two_touches"] + [
            bar(101.55, 101.6, 101.0, 101.1), bar(101.1, 101.15, 99.6, 99.7), bar(99.7, 100.3, 99.65, 100.2),
            bar(100.2, 100.35, 99.95, 100.0), bar(100.0, 100.05, 99.3, 99.4), bar(99.4, 99.45, 98.9, 99.0),
            bar(99.0, 99.05, 98.4, 98.5), bar(98.5, 99.0, 98.45, 98.95)],
        # v7.01 (review): T1 14, rejection 15 (top 101.6), 17 enters the zone and closes below the T1 wick (BREAKOUT,
        # a visit but not a touch), 18 closes back above it (BREAK_FAIL), 19 rejects the visit (bounce top 100.5),
        # 21 breaks out again, 22 confirms: 100 % = 100.5, the bounce after the visit's low 99.3
        "failed_break_visit": p + [bar(100.1, 100.2, 99.5, 100.0), bar(100.0, 101.6, 99.95, 101.5),
                                   bar(101.5, 101.55, 100.3, 100.35), bar(100.35, 100.4, 99.3, 99.4),
                                   bar(99.4, 99.95, 99.35, 99.9), bar(100.0, 100.5, 99.95, 100.4),
                                   bar(100.4, 100.45, 100.0, 100.1), bar(100.1, 100.15, 99.3, 99.35),
                                   bar(99.35, 99.4, 98.9, 99.0), bar(99.0, 99.6, 98.95, 99.5),
                                   bar(99.5, 99.6, 98.0, 98.1)],
        # v7.01 (review): T1 14, then a crash through the BPR within the T1 visit (low 95.0 on 17, no rejection yet),
        # back up to 21 (REJECT, top 100.15), 22 closes below the T1 wick, 23 confirms, 24 pulls back: the leg is the
        # bounce 100.15 -> 99.0, not T1's high -> the crash low
        "t1_crash": p + [bar(100.1, 100.2, 99.5, 100.0), bar(100.0, 100.05, 99.0, 99.1), bar(99.1, 99.2, 97.0, 97.1),
                         bar(97.1, 97.2, 95.0, 95.2), bar(95.2, 97.0, 95.1, 96.9), bar(96.9, 99.0, 96.8, 98.9),
                         bar(98.9, 100.1, 98.8, 100.0), bar(100.0, 100.15, 99.95, 100.1),
                         bar(100.1, 100.12, 99.3, 99.4), bar(99.4, 99.45, 99.0, 99.1), bar(99.1, 99.4, 99.05, 99.3)],
        # v7.01 (review): 'fill_target' (T1 14 wick 99.5, long trade to 101.8), then the drop: 27 enters the zone
        # with a wick to 99.2 and closes 99.7 (T2, never rejected), 28 and 29 close below the T1 wick: the
        # breakout (an unrejected T2 does not move the DEEPEST level), 30 the low 98.6, 32 fills, 33 the target
        "drop_after_t1": scenarios()["fill_target"] + [
            bar(101.7, 101.75, 100.9, 101.0), bar(101.0, 101.05, 99.2, 99.7), bar(99.7, 99.8, 99.25, 99.35),
            bar(99.35, 99.4, 99.22, 99.3), bar(99.3, 99.35, 98.6, 98.7), bar(98.7, 99.3, 98.65, 99.25),
            bar(99.25, 100.3, 99.2, 100.2), bar(100.2, 100.25, 98.0, 98.1), bar(98.1, 98.15, 97.0, 97.1)],
        # v7.01 (review): 'two_touches', then a drop without any bearish gap: the only bearish gap after T2 is bar 24,
        # inside the long trade before the reversal's 100 % (26). No reversal orders (FVG rule).
        "fvg_before_top": scenarios()["two_touches"] + [
            bar(101.55, 101.6, 100.85, 100.9), bar(100.9, 101.4, 100.3, 100.4), bar(100.4, 100.85, 99.3, 99.4),
            bar(99.4, 100.3, 98.9, 99.0), bar(99.0, 99.3, 98.4, 98.5), bar(98.5, 98.95, 98.45, 98.9),
            bar(98.9, 100.1, 98.85, 100.0), bar(100.0, 100.05, 98.6, 98.7), bar(98.7, 98.9, 98.3, 98.35)],
        # v7.01: T1 14, R 15, T2 16 (wick 99.7), 17 a wide candle in the visit (high 100.8) that makes its low 99.6,
        # 18 rejects (top 100.4), 19 closes below the T1 wick, 20 confirms: the bounce is measured after the visit's
        # low, so the 100 % is 100.4, not 17's high
        "visit_wide_candle": p + [bar(100.1, 100.2, 99.5, 100.0), bar(100.0, 100.18, 99.95, 100.1),
                                  bar(100.1, 100.15, 99.7, 99.85), bar(99.85, 100.8, 99.6, 99.7),
                                  bar(99.95, 100.4, 99.93, 100.3), bar(100.3, 100.32, 99.3, 99.4),
                                  bar(99.4, 99.45, 99.0, 99.1), bar(99.1, 99.5, 99.05, 99.45)],
        # v7.01: T1 14, R 15, T2 16, 17 the visit's low 99.25, 18 a spike to 100.6 inside the visit, 19 closes below
        # the T1 wick inside the same visit (BREAKOUT, low 99.35: not a new visit low), 20 fails, 21 rejects (top
        # 100.4), 22 breaks out, 23 confirms: the bounce after the visit's low tops at 100.6
        "visit_lower_high": p + [bar(100.1, 100.2, 99.5, 100.0), bar(100.0, 100.18, 99.95, 100.1),
                                 bar(100.1, 100.15, 99.7, 99.8), bar(99.8, 99.85, 99.25, 99.6),
                                 bar(99.6, 100.6, 99.45, 99.7), bar(99.7, 99.75, 99.35, 99.4),
                                 bar(99.4, 99.9, 99.38, 99.85), bar(99.95, 100.4, 99.93, 100.3),
                                 bar(100.3, 100.32, 99.3, 99.4), bar(99.4, 99.45, 99.0, 99.1),
                                 bar(99.1, 99.6, 99.05, 99.55)],
        # v7.01: the visit's low 99.2 (17), its bounce top 100.6 (18, still in the zone), a lower low 99.3 after that
        # top (19), the rejection (20), then two closes below the T1 wick with lows 99.35 / 99.32: the 0 % is 99.3,
        # the lowest low after the 100 %
        "cand_x_after_top": p + [bar(100.1, 100.2, 99.5, 100.0), bar(100.0, 100.18, 99.95, 100.1),
                                 bar(100.1, 100.15, 99.7, 99.8), bar(99.8, 99.85, 99.2, 99.6),
                                 bar(99.6, 100.6, 99.55, 99.7), bar(99.7, 99.75, 99.3, 99.55),
                                 bar(99.95, 100.3, 99.93, 100.2), bar(100.2, 100.22, 99.35, 99.4),
                                 bar(99.4, 99.45, 99.32, 99.35), bar(99.35, 99.6, 99.33, 99.55)],
    }
    for v in sq.values():
        check(v)
    return sq


def v8_sequences() -> dict[str, list]:
    """Sequences of the BprFvgEA v8 rules (tests/test_bpr_breakout_v8_tracking.py), from the owner's example of
    2026-10-16: the T1 is not right after the BPR's creation. Also in the parity set at the default settings. Bullish
    BPR [98.0, 99.9] armed on 13 (prefix); mirror() gives the bearish side."""
    p = prefix()
    away = [bar(101.0 + 0.1 * (i % 2), 101.25, 100.95, 101.1 - 0.1 * (i % 2)) for i in range(300)]
    sq = {
        # the owner's drawing: the BPR forms (13), price goes on up (14-15) without touching it, comes back (16) and
        # taps it from above on 17 (T1, wick 99.0), reacts up (18 in the zone, 19 the rejection, 20-21 up to 101.6),
        # then drops: 22, 23 closes below the T1 wick (BREAKOUT), 24 again (CONFIRM: limits at once with v8), 25 a new
        # low (the limits move), 26-27 pull back and fill the 50 % (99.6), 28 reaches the target
        "tap_from_above": p + [bar(100.2, 100.95, 100.15, 100.9), bar(100.9, 101.6, 100.85, 101.5),
                               bar(101.5, 101.55, 100.0, 100.1), bar(100.1, 100.15, 99.0, 99.6),
                               bar(99.6, 100.3, 99.55, 100.2), bar(100.2, 100.8, 100.15, 100.7),
                               bar(100.7, 101.5, 100.6, 101.4), bar(101.4, 101.6, 101.2, 101.3),
                               bar(101.3, 101.35, 100.2, 100.3), bar(100.3, 100.35, 98.8, 98.9),
                               bar(98.9, 99.0, 98.2, 98.3), bar(98.3, 98.5, 97.6, 97.7),
                               bar(97.7, 98.9, 97.65, 98.8), bar(98.8, 99.7, 98.7, 99.3),
                               bar(99.3, 99.35, 97.3, 97.4)],
        # the BPR forms (13), price goes up (14) and stays away above it for 300 bars (15-314), then taps it (T1 on
        # 315, wick 99.5), rejects (316), and later closes twice below the T1 wick (319-320: the reversal)
        "late_t1": p + [bar(100.2, 101.05, 100.15, 101.0)] + away + [
            bar(101.0, 101.05, 99.5, 100.0), bar(100.0, 100.3, 99.95, 100.2), bar(100.2, 100.25, 100.0, 100.1),
            bar(100.1, 100.15, 99.95, 100.05), bar(100.05, 100.1, 99.4, 99.45), bar(99.45, 99.5, 98.9, 99.0),
            bar(99.0, 99.05, 98.5, 98.6), bar(98.6, 99.3, 98.55, 99.2), bar(99.2, 99.6, 99.1, 99.55),
            bar(99.55, 99.6, 98.3, 98.4)],
    }
    for v in sq.values():
        check(v)
    return sq

def boundary_cases() -> dict[str, tuple[list, dict]]:
    """Sequences that sit exactly on a comparison boundary, built from the detector's own arithmetic so the float
    values are identical in Python and in the C++ transliteration. name -> (bars, BreakoutParams overrides)."""
    b = base()
    X, O = 101.6, 99.5  # noqa: E741 (decision anchors of base())
    L = 1 * (X - O)
    # close + spread == the 50 % entry exactly (sp = 0.1): MISSED (the rule is <=)
    c50 = X - 1 * (50.0 / 100.0) * L
    missed = b[:19] + [(101.5, 101.5, min(101.1, c50), c50)]
    # cost / risk == max_cost_r exactly on the 71 % level: placed (the rule is >)
    sp, tk = 0.1, 0.01
    SL = X - 1 * (100.0 / 100.0) * L - 1 * 10 * tk
    P71 = X - 1 * (71.0 / 100.0) * L + sp
    cost = sp + 2.0 * 3.5 / 100.0 + 2.0 * 1.0 * tk
    exact = cost / abs(P71 - SL)
    # short mirror: close == the 50 % sell-limit price exactly: MISSED (the rule is >=)
    mb = mirror(b)
    Xs, Os = 98.4, 100.5
    Ls = -1 * (Xs - Os)
    c50s = Xs - (-1) * (50.0 / 100.0) * Ls
    o19, h19, l19, _ = mb[19]
    short_missed = mb[:19] + [(o19, max(h19, c50s + 0.01), l19, c50s)]
    out = {"missed_exact": (missed, {}), "cost_exact": (b, {"max_cost_r": exact}),
           "short_missed_exact": (short_missed, {})}
    for v, _ in out.values():
        check(v)
    return out
