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
