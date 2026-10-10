"""Unit tests of the BprFvgEA v2 reference detector (qe/strategies/bpr_breakout.py).

Spec: research/indicators/BPR_BREAKOUT_FIB_SPEC.md. The hand-built sequences are in tests/bk_scenarios.py; the same
sequences are run through the C++ transliteration of the EA in tests/test_bpr_breakout_ea_harness.py.
"""
import random

import pytest

from bk_scenarios import BASE_TAIL, base, bar, mirror, prefix, scenarios
from qe.strategies.bpr_breakout import (BreakoutDetector, BreakoutParams, Env, harness_detector, harness_run,
                                        round_to_tick)

GAP = BreakoutParams(fvg_rule="ANY_GAP")
OPEN = Env(slot_free=True, session_entry_ok=True, session_cancel=False, risk_ok=True, spread_ok=True, sp=0.1)


def _env(**kw):
    d = dict(slot_free=True, session_entry_ok=True, session_cancel=False, risk_ok=True, spread_ok=True, sp=0.1)
    d.update(kw)
    return Env(**d)


def _run(bars, params=GAP, env_of=None, trade_from=0):
    det = BreakoutDetector(params, trade_from=trade_from)
    out = []
    for u, b in enumerate(bars):
        env = env_of(u, det) if env_of else _env(slot_free=not det.has_order_or_position())
        out.append(det.on_bar_closed(u, *b, env))
    return det, out


def _evs(det, frm=0):
    return [(e["n"], e["id"], e["ev"], e["k"], e["reason"]) for e in det.events if e["n"] >= frm]


# ------------------------------------------------------------------------------------------------ parameters
def test_defaults_follow_the_owner_rule():
    p = BreakoutParams()
    assert p.max_touches == 2 and p.confirm_closes == 2 and p.fvg_rule == "LUXALGO"
    assert p.fib_levels == (50.0, 61.8, 71.0) and p.target_fib == 0.0 and p.stop_fib == 100.0
    assert p.max_hold_min == 120


@pytest.mark.parametrize("kw", [{"max_hold_min": 121}, {"direction": "UP"}, {"fvg_rule": "X"},
                                {"reject_before_break": 1},
                                {"fib_levels": (50.0, 61.8)}, {"fib_levels": (0.0, 0.0, 0.0)},
                                {"fib_levels": (50.0, 100.0, 71.0)}, {"stop_fib": 0.0}, {"target_fib": 100.0},
                                {"max_touches": 0}, {"confirm_closes": 6}, {"max_cost_r": -0.1}, {"tick_size": 0},
                                {"use_session": 1}])
def test_invalid_params_are_refused(kw):
    with pytest.raises(ValueError):
        BreakoutParams(**kw)


def test_round_to_tick_is_half_away_from_zero_and_digit_normalised():
    assert round_to_tick(2017.3400000000001, 0.01, 2) == 2017.34
    assert round_to_tick(0.125, 0.25, 2) == 0.25            # exactly half a tick: away from zero
    assert round_to_tick(-0.125, 0.25, 2) == -0.25
    assert round_to_tick(0.12, 0.25, 2) == 0.0
    assert round_to_tick(1.23, 0.0, 2) == 1.23


# ------------------------------------------------------------------------------------------------ the base sequence
def test_base_sequence_records_and_fib_prices():
    det, intents = _run(base())
    assert _evs(det) == [(13, 1, "ARMED", 0, None), (14, 1, "TOUCH", 1, None), (15, 1, "REJECT", 0, None),
                         (16, 1, "BREAKOUT", 0, None), (17, 1, "CONFIRM", 0, None),
                         (19, 1, "PLACE_LIMIT", 1, None), (19, 1, "PLACE_LIMIT", 2, None),
                         (19, 1, "PLACE_LIMIT", 3, None)]
    conf = det.events[4]
    assert (conf["O"], conf["X"]) == (99.5, 101.3)           # origin = touch low, extreme so far
    pl = [e for e in det.events if e["ev"] == "PLACE_LIMIT"]
    # leg 99.5 -> 101.6 (L = 2.1); buy limits are ask levels: fib price + spread 0.1
    assert [e["P"] for e in pl] == [100.65, 100.40, 100.21]   # 50 %, 61.8 %, 71 %
    assert {e["SL"] for e in pl} == {99.4}                    # 100 % minus 10 ticks
    assert {e["TP"] for e in pl} == {101.6}                   # the leg high
    assert {(e["O"], e["X"]) for e in pl} == {(99.5, 101.6)}
    assert [it.type for it in intents[19]] == ["PLACE_LIMIT"] * 3
    st = det.setup(1)
    assert st.phase == "ORDERED" and st.ref == 14 and st.lvl == 100.2 and st.touch_bars == [14]
    assert st.tgt == 101.6 and st.decision_bar == 19


def test_no_decision_on_the_bar_that_makes_a_new_high():
    det, _ = _run(base()[:19])                                  # bar 18 makes a new high: not a pullback
    assert not [e for e in det.events if e["ev"] == "PLACE_LIMIT"]
    assert det.setup(1).X == 101.6 and det.setup(1).phase == "LEG"


def test_luxalgo_rule_needs_an_engine_fvg_after_the_reference_candle():
    det, _ = _run(base(), BreakoutParams())                     # LuxAlgo FVG on 18 (displacement candle 17)
    assert det.setup(1).phase == "ORDERED" and det._fvg_bar[1] == 18
    sc = scenarios()["no_lux_fvg"]                              # candle 17 has a long wick: no LuxAlgo FVG after 14
    det1, _ = _run(sc, BreakoutParams())
    assert det1.setup(1).phase == "LEG" and det1.stats["WAIT_NO_FVG"] == 1
    det2, _ = _run(sc, BreakoutParams(fvg_rule="ANY_GAP"))      # the plain gap on 17 counts
    assert det2.setup(1).phase == "ORDERED"
    det3, _ = _run(sc, BreakoutParams(fvg_rule="NONE"))
    assert det3.setup(1).phase == "ORDERED"


def test_fvg_on_the_reference_candle_does_not_count():
    det, _ = _run(scenarios()["fvg_on_ref"])
    st = det.setup(1)
    assert st.ref == 17 and det._fvg_bar[1] == 17
    assert st.phase == "LEG" and det.stats["WAIT_NO_FVG"] == 2


# ------------------------------------------------------------------------------------------------ touches
def test_consecutive_touching_candles_are_one_touch_and_a_third_touch_ends_the_setup():
    det, _ = _run(scenarios()["touch_limit"])
    assert [e for e in _evs(det) if e[2] in ("TOUCH", "DONE")] == [
        (14, 1, "TOUCH", 1, None), (17, 1, "TOUCH", 2, None), (19, 1, "DONE", 0, "TOUCH_LIMIT")]


def test_max_touches_one_allows_a_single_touch():
    det, _ = _run(scenarios()["break_fail"], BreakoutParams(fvg_rule="ANY_GAP", max_touches=1))
    assert (18, 1, "DONE", 0, "TOUCH_LIMIT") in _evs(det)


def test_breakout_needs_two_closes_beyond_the_level():
    det, _ = _run(scenarios()["break_fail"])
    assert [e[2] for e in _evs(det, 16)] == ["BREAKOUT", "BREAK_FAIL", "TOUCH", "REJECT"]
    assert det.setup(1).phase == "ZONE" and det.setup(1).touches == 2
    det1, _ = _run(scenarios()["break_fail"], BreakoutParams(fvg_rule="ANY_GAP", confirm_closes=1))
    assert [e[2] for e in _evs(det1, 16)][:2] == ["BREAKOUT", "CONFIRM"]


def test_a_wick_beyond_the_level_is_not_a_breakout():
    bars = prefix() + [BASE_TAIL[0], BASE_TAIL[1], bar(100.1, 100.9, 100.0, 100.15)]   # high > 100.2, close below
    det, _ = _run(bars)
    assert "BREAKOUT" not in [e[2] for e in _evs(det)]


def test_a_touching_candle_is_never_the_breakout_candle():
    det, _ = _run(scenarios()["touching_close_above"])
    assert [e[2:] for e in _evs(det, 14)] == [("TOUCH", 1, None), ("REJECT", 0, None)]
    st = det.setup(1)
    assert st.ref == 15 and st.lvl == 101.0 and st.phase == "ZONE"   # the level moved to the touching candle's high


def test_reject_before_break_option():
    sc = scenarios()["reject_is_breakout"]
    det, _ = _run(sc)                                                 # default: candle 15 is the breakout
    assert [e[:3] for e in _evs(det, 15)][:2] == [(15, 1, "BREAKOUT"), (16, 1, "CONFIRM")]
    det2, _ = _run(sc, BreakoutParams(fvg_rule="ANY_GAP", reject_before_break=True))
    assert [e[:3] for e in _evs(det2, 15)][:3] == [(15, 1, "REJECT"), (16, 1, "BREAKOUT"), (17, 1, "CONFIRM")]


def test_broken_zone_ends_the_setup():
    det, _ = _run(scenarios()["broken"])
    assert _evs(det)[-1] == (15, 1, "DONE", 0, "BROKEN")


def test_setup_expiry():
    bars = prefix() + [BASE_TAIL[0]] + [bar(100.0, 100.15, 100.0, 100.1)] * 6
    det, _ = _run(bars, BreakoutParams(fvg_rule="ANY_GAP", setup_expiry_bars=5))
    assert _evs(det)[-1] == (19, 1, "DONE", 0, "EXPIRED")


# ------------------------------------------------------------------------------------------------ leg and orders
def test_leg_broken_before_the_decision():
    det, _ = _run(scenarios()["leg_broken"])
    assert _evs(det)[-1] == (19, 1, "DONE", 0, "LEG_BROKEN")


def test_reanchor_cancels_and_replaces_the_orders():
    det = harness_detector(scenarios()["reanchor"], GAP, 0.1)
    ev = [(e["n"], e["ev"], e["k"], e["reason"], e["P"], e["TP"]) for e in det.events if e["n"] >= 19]
    assert ev == [(19, "PLACE_LIMIT", 1, None, 100.65, 101.6), (19, "PLACE_LIMIT", 2, None, 100.40, 101.6),
                  (19, "PLACE_LIMIT", 3, None, 100.21, 101.6),
                  (20, "CANCEL", 1, "NEW_EXTREME", None, None), (20, "CANCEL", 2, "NEW_EXTREME", None, None),
                  (20, "CANCEL", 3, "NEW_EXTREME", None, None),
                  (21, "PLACE_LIMIT", 1, None, 100.85, 102.0), (21, "PLACE_LIMIT", 2, None, 100.55, 102.0),
                  (21, "PLACE_LIMIT", 3, None, 100.32, 102.0)]
    assert det.stats["REANCHOR"] == 1


def test_fills_then_target_cancels_the_rest_and_closes_the_setup():
    det = harness_detector(scenarios()["fill_target"], GAP, 0.1)
    st = det.setup(1)
    assert [lv.status for lv in st.levels] == ["CLOSED", "CLOSED", "CANCELLED"]
    assert st.phase == "CLOSED" and st.end_bar == 23
    assert [(e["n"], e["ev"], e["k"], e["reason"]) for e in det.events if e["id"] == 1 and e["n"] >= 20] == [
        (23, "CANCEL", 3, "TARGET"), (23, "CLOSED", 0, None)]


def test_missed_level_is_skipped_but_the_others_are_placed():
    det, _ = _run(scenarios()["missed_boundary"])
    assert [e[2:] for e in _evs(det, 19)] == [("SKIP", 1, "MISSED"), ("PLACE_LIMIT", 2, None),
                                              ("PLACE_LIMIT", 3, None)]


def test_cost_filter_skips_levels_and_no_level_ends_the_setup():
    det, _ = _run(base(), BreakoutParams(fvg_rule="ANY_GAP", max_cost_r=0.16))
    assert [e[2:] for e in _evs(det, 19)] == [("PLACE_LIMIT", 1, None), ("SKIP", 2, "COST"), ("SKIP", 3, "COST")]
    det2, _ = _run(base(), BreakoutParams(fvg_rule="ANY_GAP", max_cost_r=0.01))
    assert [e[2:] for e in _evs(det2, 19)] == [("SKIP", 1, "COST"), ("SKIP", 2, "COST"), ("SKIP", 3, "COST"),
                                               ("DONE", 0, "NO_LEVEL")]


def test_min_rr_and_disabled_levels():
    det, _ = _run(base(), BreakoutParams(fvg_rule="ANY_GAP", min_rr=1.0, fib_levels=(50.0, 0.0, 71.0)))
    # 50 %: reward 0.95 / risk 1.25 < 1 -> RR; level 2 is off (no record); 71 %: 1.39 / 0.81 -> placed
    assert [e[2:] for e in _evs(det, 19)] == [("SKIP", 1, "RR"), ("PLACE_LIMIT", 3, None)]


def test_target_extension_and_stop_level():
    det, _ = _run(base(), BreakoutParams(fvg_rule="ANY_GAP", target_fib=-27.0, stop_fib=110.0,
                                         stop_buffer_ticks=0))
    pl = [e for e in det.events if e["ev"] == "PLACE_LIMIT"]
    assert {e["TP"] for e in pl} == {round(101.6 + 0.27 * 2.1, 2)}
    assert {e["SL"] for e in pl} == {round(101.6 - 1.10 * 2.1, 2)}


def test_short_side_is_the_mirror_image():
    det, _ = _run(mirror(base()))
    pl = [e for e in det.events if e["ev"] == "PLACE_LIMIT"]
    assert [(e["dir"], e["P"]) for e in pl] == [(-1, 99.45), (-1, 99.70), (-1, 99.89)]   # sell limits = bid levels
    assert {e["SL"] for e in pl} == {100.7}                   # 100.5 + 10 ticks + spread (an ask level)
    assert {e["TP"] for e in pl} == {98.5}                    # leg low 98.4 + spread (an ask level)


# ------------------------------------------------------------------------------------------------ environment
@pytest.mark.parametrize("field,stat", [("slot_free", "BLOCKED_SLOT"), ("session_entry_ok", "BLOCKED_SESSION"),
                                        ("risk_ok", "BLOCKED_RISK"), ("spread_ok", "BLOCKED_SPREAD")])
def test_a_blocked_environment_delays_the_decision(field, stat):
    bars = base() + [bar(101.2, 101.4, 101.15, 101.3)]
    det, _ = _run(bars, env_of=lambda u, d: _env(**{field: u != 19}))
    assert det.stats[stat] == 1
    assert {e["n"] for e in det.events if e["ev"] == "PLACE_LIMIT"} == {20}


def test_session_is_ignored_when_off():
    det, _ = _run(base(), BreakoutParams(fvg_rule="ANY_GAP", use_session=False),
                  env_of=lambda u, d: _env(session_entry_ok=False))
    assert det.setup(1).phase == "ORDERED"


def test_session_end_cancels_pending_orders():
    bars = base() + [bar(101.2, 101.4, 101.15, 101.3)]
    det, out = _run(bars, env_of=lambda u, d: _env(session_cancel=(u == 20)))
    assert [e[2:] for e in _evs(det, 20)] == [("CANCEL", 1, "SESSION_END"), ("CANCEL", 2, "SESSION_END"),
                                              ("CANCEL", 3, "SESSION_END"), ("DONE", 0, "SESSION_END")]
    assert [it.type for it in out[20]] == ["CANCEL"] * 3


def test_leg_expiry_cancels_pending_orders():
    bars = base() + [bar(101.2, 101.4, 101.15, 101.3)] * 3
    det, _ = _run(bars, BreakoutParams(fvg_rule="ANY_GAP", leg_expiry_bars=4))
    assert _evs(det)[-1] == (22, 1, "DONE", 0, "EXPIRED")


# ------------------------------------------------------------------------------------------------ executor feedback
def test_notify_retry_returns_to_leg_and_decides_again():
    bars = base() + [bar(101.2, 101.4, 101.15, 101.3)]
    det = BreakoutDetector(GAP)
    for u, b in enumerate(bars):
        det.on_bar_closed(u, *b, _env(slot_free=not det.has_order_or_position()))
        if u == 19:
            det.notify_retry(1)
            assert det.setup(1).phase == "LEG" and not det.has_order_or_position()
    assert [e["n"] for e in det.events if e["ev"] == "PLACE_LIMIT"] == [19, 19, 19, 20, 20, 20]
    assert det.stats["RETRY"] == 1


def test_notify_cancelled_drops_levels_and_ends_the_setup():
    det, _ = _run(base())
    det.notify_cancelled(1, 1, "SIZE_BELOW_MIN")
    det.notify_cancelled(1, 2, "ORDER_FAILED")
    assert det.setup(1).phase == "ORDERED"
    det.notify_cancelled(1, 3, "ORDER_FAILED")
    assert det.setup(1).phase == "DONE" and det.setup(1).reason == "ORDER_FAILED"
    assert [e[2:] for e in _evs(det, 19)][-4:] == [("DROP", 1, "SIZE_BELOW_MIN"), ("DROP", 2, "ORDER_FAILED"),
                                                   ("DROP", 3, "ORDER_FAILED"), ("DONE", 0, "ORDER_FAILED")]
    with pytest.raises(ValueError):
        det.notify_cancelled(1, 1, "NOPE")


def test_fill_after_a_detector_cancel_is_ignored():
    # the EA never reports a fill of an order the detector cancelled (it manages that position alone); a stray
    # notification for a level that is not pending changes nothing
    det2, _ = _run(base()[:19] + [BASE_TAIL[5], bar(101.2, 101.8, 101.1, 101.7)])
    assert det2.setup(1).levels[0].status == "NONE"           # re-anchored on 20: nothing pending
    det2.notify_filled(1, 1)
    assert det2.setup(1).phase == "LEG" and not det2.setup(1).ever_filled


def test_partial_fill_then_close_with_drop_closes_the_setup():
    det, _ = _run(base())
    det.notify_filled(1, 2)
    assert det.setup(1).phase == "FILLED"
    det.notify_cancelled(1, 1, "ORDER_FAILED")
    det.notify_cancelled(1, 3, "ORDER_FAILED")
    assert det.setup(1).phase == "FILLED"                     # level 2 still open
    det.notify_closed(1, 2)
    assert det.setup(1).phase == "CLOSED"


# ------------------------------------------------------------------------------------------------ warm-up, causality
def test_warmup_setups_never_trade():
    det, _ = _run(base(), trade_from=15)
    assert _evs(det)[-1] == (14, 1, "DONE", 0, "WARMUP")
    assert not [e for e in det.events if e["ev"] == "PLACE_LIMIT"]


def test_direction_filter():
    det, _ = _run(base(), BreakoutParams(fvg_rule="ANY_GAP", direction="SHORT_ONLY"))
    assert not [e for e in det.events if e["dir"] == 1]
    det2, _ = _run(mirror(base()), BreakoutParams(fvg_rule="ANY_GAP", direction="LONG_ONLY"))
    assert not [e for e in det2.events if e["dir"] == -1]


def _rand_bars(seed, n):
    rnd = random.Random(seed)
    out, c = [], 2000.0
    for _ in range(n):
        o = c
        body = rnd.choice([-1, 1]) * rnd.uniform(1.5, 3.5) if rnd.random() < 0.18 else rnd.gauss(0, 0.7)
        w = 0.05 if abs(body) > 1.4 else 0.6
        c = round(o + body + (2000.0 - o) * 0.03, 2)
        out.append((o, round(max(o, c) + abs(rnd.gauss(0, w)), 2), round(min(o, c) - abs(rnd.gauss(0, w)), 2), c))
    return out


@pytest.mark.parametrize("seed", [11, 12, 13])
def test_features_are_causal(seed):
    """No look-ahead: every record and intent produced while bars 0..t are processed is the same whatever the bars
    after t are (the run on bars[:t+1] is a prefix of the full run and of a run with different future bars)."""
    bars = _rand_bars(seed, 1500)
    p = BreakoutParams(fvg_rule="ANY_GAP")
    full = harness_run(bars, p, 0.1)
    rnd = random.Random(seed + 100)
    for t in (300, 700, 1100):
        trunc = harness_run(bars[: t + 1], p, 0.1)
        alt = bars[: t + 1] + [(o, h + rnd.uniform(0, 5), l - rnd.uniform(0, 5), c) for (o, h, l, c) in bars[t + 1:]]
        other = harness_run(alt, p, 0.1)
        assert full[: len(trunc)] == trunc
        assert other[: len(trunc)] == trunc
        assert trunc and trunc[-1]["n"] <= t


def test_random_series_reach_orders_and_closes():
    det = harness_detector(_rand_bars(5, 4000), BreakoutParams(fvg_rule="ANY_GAP"), 0.1)
    evs = {e["ev"] for e in det.events}
    assert {"ARMED", "TOUCH", "BREAKOUT", "CONFIRM", "PLACE_LIMIT", "CLOSED"} <= evs
