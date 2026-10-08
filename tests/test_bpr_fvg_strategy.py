"""Tests of the BPR + FVG EA's Python reference (qe/strategies/bpr_fvg.py): detector, parity harness, simulator.

Licence and attribution: the zones come from the port of the FVG / BPR logic of 'ICT Concepts [LuxAlgo]',
(c) LuxAlgo (original Pine v5 logic), licensed CC BY-NC-SA 4.0 (https://creativecommons.org/licenses/by-nc-sa/4.0/).
These tests check code built on that port (a derivative work), for non-commercial research use; the changes made by
the ports are listed in research/indicators/LUXALGO_BPR_SPEC.md section 10.

The single source of truth is research/indicators/BPR_FVG_EA_SPEC.md ("spec s.N" below). Every scenario is
hand-built and every expected number was derived by hand from the spec; the derivation is in the comments.
Most detector tests use a scripted stand-in for the LuxAlgo engine (``StubEngine``) so that a zone appears exactly
on the bar and with the geometry the test needs; the geometry tests use the real engine.

No conftest fixtures are used, so the file runs on its own:
    cd /home/user/the-Quantum-Edge && PYTHONPATH=. pytest --noconftest -q tests/test_bpr_fvg_strategy.py
"""
from __future__ import annotations

import json
import math
import random

import pytest

from qe.indicators.luxalgo_bpr import Box, Zone
from qe.strategies.bpr_fvg import (
    Env,
    Intent,
    SetupDetector,
    StrategyParams,
    harness_run,
    r_unit,
    round_to_tick,
    simulate,
    trade_r,
)

SP = 0.1  # constant spread of the detector tests


# =============================================================================================== helpers
def close(a, b, tol=1e-9) -> bool:
    if a is None or b is None:
        return a is b
    return math.isclose(a, b, rel_tol=0.0, abs_tol=tol)


def assert_levels(e: dict, P, SL, TP1, TP2) -> None:
    got = (e["P"], e["SL"], e["TP1"], e["TP2"])
    want = (P, SL, TP1, TP2)
    assert all(close(g, w) for g, w in zip(got, want)), f"levels {got} != {want}"


def brief(det: SetupDetector) -> list[tuple]:
    """(n, id, ev, reason) of every event record."""
    return [(e["n"], e["id"], e["ev"], e["reason"]) for e in det.events]


class StubEngine:
    """Scripted stand-in for ``LuxBprEngine`` with the attributes the detector reads.

    ``script[n]`` lists ``(array, action, zone)``: ``set`` replaces index 0 silently, ``new`` unshifts the zone (and
    pops the oldest) with a ``new`` event, ``update`` replaces index 0 with an ``update`` event.
    """

    def __init__(self, script: dict, vis: int = 2) -> None:
        self.script = script
        self.arrays = {k: [Zone() for _ in range(vis)] for k in ("FVG_UP", "FVG_DN", "BPR_UP", "BPR_DN")}
        self.fvg_up = self.arrays["FVG_UP"]
        self.fvg_dn = self.arrays["FVG_DN"]
        self.bpr_up = self.arrays["BPR_UP"]
        self.bpr_dn = self.arrays["BPR_DN"]
        self.events: list[tuple[int, str, str]] = []

    def process_bar(self, n, o, h, l, c):  # noqa: E741
        for kind, action, zone in self.script.get(n, []):
            arr = self.arrays[kind]
            if action == "new":
                arr.insert(0, zone)
                arr.pop()
                self.events.append((n, kind, "new"))
            elif action == "update":
                arr[0] = zone
                self.events.append((n, kind, "update"))
            else:
                arr[0] = zone


def stub_detector(params: StrategyParams, script: dict, trade_from: int = 0) -> SetupDetector:
    det = SetupDetector(params, trade_from)
    det.engine = StubEngine(script)
    return det


def drive(det: SetupDetector, bars, sp: float = SP, at: dict | None = None, **const) -> list[Intent]:
    """Feed ``bars`` after the detector's last bar with a harness-like Env (slot_free = no order or position).
    ``const``: Env fields for every bar; ``at``: ``{u: {field: value}}`` for single bars."""
    out: list[Intent] = []
    u0 = 0 if det.last_bar is None else det.last_bar + 1
    for i, b in enumerate(bars):
        u = u0 + i
        f = dict(slot_free=not det.has_order_or_position(), session_entry_ok=True, session_cancel=False,
                 risk_ok=True, spread_ok=True, sp=sp)
        f.update(const)
        f.update((at or {}).get(u, {}))
        out.extend(det.on_bar_closed(u, b[0], b[1], b[2], b[3], Env(**f)))
    return out


def mirror(bars, axis: float = 200.0):
    """Price mirror p -> axis - p: (o, h, l, c) -> (axis-o, axis-l, axis-h, axis-c)."""
    return [(axis - b[0], axis - b[2], axis - b[1], axis - b[3]) for b in bars]


# Small windows for the hand-built scenarios (sweep 5, range 5, MSS 5, rally 3, expiry 10); other inputs default.
PS = StrategyParams(sweep_window=5, range_bars=5, mss_bars=5, rally_bars=3, expiry_bars=10)
FLAT = (100, 101, 99, 100)

# BASE (long): range lows 99 (R), sweep low 97 at bar 8 (s), close 101.5 > M = 101 at bar 10 (MSS), zone at bar 12.
#   s = argmin l[7..12] = 8 (lows 99, 97, 97.5, 99.5, 101, 102); R = min l[3..7] = 99 > 97 -> sweep OK
#   M = max h[3..7] = 101; first close > 101 in (8, 12] is bar 10 -> mss_bar 10
#   X = max h[8..12] = 104; O = min l[12-3 .. 12] = min(97.5, 99.5, 101, 102) = 97.5
BASE = [FLAT] * 8 + [
    (99, 99.5, 97, 98),  # 8: s
    (98, 100, 97.5, 99.5),  # 9
    (99.5, 102, 99.5, 101.5),  # 10: MSS
    (101.5, 103, 101, 102.5),  # 11
    (102.5, 104, 102, 103.5),  # 12: zone
]
BASE_S = mirror(BASE)  # the short mirror (all prices 200 - p)


def long_zones():
    """Bearish FVG [99.5, 101.5] and bullish FVG [100, 101] -> BPR_UP box [100, 101.5] with pos +1 (long).
    B = 100, T = min(101, 101.5) = 101 < box top 101.5 (QUIRK 4), h = 1, Lo = min(100, 99.5) = 99.5, break l < 100."""
    return [
        ("FVG_DN", "set", Zone(Box(3, 101.5, 12, 99.5), True)),
        ("FVG_UP", "set", Zone(Box(10, 101.0, 12, 100.0), True)),
        ("BPR_UP", "new", Zone(Box(3, 101.5, 20, 100.0), True, 1)),
    ]


def short_zones():
    """Mirror of ``long_zones``: bullish FVG [98.5, 100.5], bearish FVG [99, 100] -> BPR_DN box [99, 100.5], pos -1.
    B = 99, T = min(100.5, 100) = 100 < box top 100.5 (QUIRK 4), h = 1, Hi = max(100.5, 100) = 100.5,
    break h > 100.5."""
    return [
        ("FVG_UP", "set", Zone(Box(3, 100.5, 12, 98.5), True)),
        ("FVG_DN", "set", Zone(Box(10, 100.0, 12, 99.0), True)),
        ("BPR_DN", "new", Zone(Box(3, 100.5, 20, 99.0), True, -1)),
    ]


def long_det(params: StrategyParams = PS, trade_from: int = 0, extra: dict | None = None) -> SetupDetector:
    script = {12: long_zones()}
    script.update(extra or {})
    return stub_detector(params, script, trade_from)


def short_det(params: StrategyParams = PS, extra: dict | None = None) -> SetupDetector:
    script = {12: short_zones()}
    script.update(extra or {})
    return stub_detector(params, script)


# Real-engine scenarios (same bars as tests/test_luxalgo_bpr.py; boxes derived there from the Pine source).
def F(p: float):
    """Filler bar: body 0.5, wicks 0.5 and 1.0, never a displacement candle."""
    return (p, p + 1, p - 1, p + 0.5)


BULL_FVG = [F(100)] * 6 + [(101, 105.5, 100.5, 105), (105, 106, 103, 105.5)]  # FVG_UP at 7: [101, 103]
BEAR_FVG = [F(110)] * 5 + [(110.5, 111, 110, 111), (110, 110.25, 103.75, 104), (104, 106, 103, 104.5)]  # FVG_DN 7
BULL_CONSEC = [F(100)] * 6 + [(101, 105.5, 100.5, 105), (105, 110.5, 104.5, 110), (110, 111, 108, 110.5)]
BEAR_CONSEC = [F(110)] * 5 + [
    (110.5, 111, 110, 111),
    (110, 110.25, 103.75, 104),
    (104, 104.25, 98.75, 99),
    (99, 100, 98, 99.5),
]
SC_A = BEAR_FVG + [
    (104.5, 107, 104, 105),
    (106.5, 109.75, 106.25, 109.5),
    (109.5, 109.75, 108, 109),  # 10: FVG_UP [107, 108] + BPR_UP box [107, 110], pos +1
    (108.25, 108.5, 108, 108.4),
    (108.5, 111.75, 108.25, 111.5),
    (111.5, 112, 109, 111.75),  # 13: FVG_UP [108.5, 109]
    (111.75, 112, 111.5, 111.6),
    (111.5, 111.75, 107.75, 108),
    (108, 108.25, 107.5, 107.75),  # 16: FVG_DN [108.25, 111.5] + BPR_UP box [108.5, 111.5], pos -1
]
SC_C1 = BULL_FVG + [
    (105, 106, 104.5, 105.5),
    (105, 105.25, 101.75, 102),
    (102, 102.5, 101.5, 101.75),  # 10: FVG_DN [102.5, 104.5] + BPR_DN box [102.5, 103], pos -1
    (101.75, 102.75, 101.5, 102),
    (102, 103.5, 101.5, 103),
]
SC_C2 = BEAR_FVG + [
    (104.5, 105, 104, 104.75),
    (105, 108.25, 104.75, 108),
    (108, 108.5, 107, 108.25),  # 10: FVG_UP [105, 107] + BPR_DN box [106, 107], pos +1
    (108.25, 108.5, 106.5, 107),
    (107, 107.5, 105.5, 106),
]
# No sweep / MSS filter and short windows (5 bars), so the early zones of these short series are tradeable.
NOFILT = dict(use_sweep=False, use_mss=False, sweep_window=5, range_bars=5, mss_bars=5)
GEO = StrategyParams(source="BOTH", **NOFILT)


def real_run(bars, params: StrategyParams = GEO, **const) -> SetupDetector:
    det = SetupDetector(params)
    drive(det, bars, **const)
    return det


# =============================================================================================== s.1 inputs
def test_params_defaults_and_validation():
    """Spec s.1 and s.10: the defaults are the spec values; bad values are refused; max hold is capped at 120."""
    p = StrategyParams()
    assert (p.source, p.direction, p.entry_mode, p.entry_offset_ticks) == ("BPR", "BOTH", "LIMIT", 5)
    assert (p.use_sweep, p.sweep_window, p.range_bars, p.use_mss, p.mss_bars, p.rally_bars) == (
        True, 30, 30, True, 20, 10)
    assert (p.expiry_bars, p.stop_zone_mult, p.min_rr, p.max_cost_r) == (60, 1.2, 1.0, 0.15)
    assert (p.tp_mode, p.tp1_fraction, p.break_even, p.max_hold_min, p.use_session) == (
        "TP1_TP2", 0.5, True, 120, True)
    assert (p.slippage_ticks, p.commission_per_lot_side, p.capacity, p.length, p.vis_boxes) == (1, 3.5, 128, 5, 2)
    assert close(p.comm_price, 0.07)  # 2 * 3.50 / 100 (XAUUSD-like contract)
    for bad in (
        dict(source="ALL"), dict(direction="UP"), dict(entry_mode="STOP"), dict(tp_mode="TP3"),
        dict(max_hold_min=121), dict(max_hold_min=0), dict(tp1_fraction=1.0), dict(tp1_fraction=0.0),
        dict(sweep_window=0), dict(range_bars=0), dict(mss_bars=0), dict(expiry_bars=0), dict(capacity=0),
        dict(length=2), dict(vis_boxes=21), dict(tick_size=0.0), dict(stop_zone_mult=-1.0), dict(use_sweep=1),
        dict(entry_offset_ticks=-1), dict(slippage_ticks=-1), dict(min_rr=float("nan")),
    ):
        with pytest.raises(ValueError):
            StrategyParams(**bad)


def test_engine_is_historical_fvg_mode_with_bpr_always_on():
    """Spec s.2: the engine runs in Historical mode, FVG gaps, perc_body 0.36, bx_back 10, ext 8, BPR always on."""
    ep = SetupDetector(StrategyParams(length=7, vis_boxes=4)).engine.params
    assert (ep.mode, ep.fvg_mode, ep.bpr, ep.show_fvg) == ("Historical", "FVG", True, True)
    assert (ep.perc_body, ep.bx_back, ep.ext_bars, ep.length, ep.vis_boxes) == (0.36, 10, 8, 7, 4)


# =============================================================================================== s.3.1 geometry
def test_bpr_long_and_short_geometry_real_engine_with_quirk4():
    """Spec s.3.1 (BPR rows, pos mapping) with the real engine on SC_A.

    Bar 10: FVG_DN [106, 110] and FVG_UP [107, 108] -> BPR_UP box [107, 110], pos +1 -> LONG with B = 107,
    T = min(108, 110) = 108 < box top 110 (QUIRK 4), Lo = min(107, 106) = 106, break l < 107.
    Bar 16: FVG_UP [108.5, 109] and FVG_DN [108.25, 111.5] -> BPR_UP box [108.5, 111.5], pos -1 -> SHORT with
    B = 108.5, T = min(109, 111.5) = 109 < box top 111.5, Hi = 111.5, break h > box top 111.5 (not T).
    """
    det = real_run(SC_A, StrategyParams(source="BPR", **NOFILT), risk_ok=False)
    lng, sht = det.setups
    assert (lng.id, lng.src, lng.dir, lng.created, lng.status) == (1, "BPR", 1, 10, "ARMED")
    assert (lng.B, lng.T, lng.h, lng.Lo_or_Hi, lng.break_level, lng.zone_top, lng.zone_bottom) == (
        107, 108, 1, 106, 107, 110, 107)
    assert lng.T < lng.zone_top
    assert (sht.id, sht.src, sht.dir, sht.created, sht.status) == (2, "BPR", -1, 16, "ARMED")
    assert (sht.B, sht.T, sht.h, sht.Lo_or_Hi, sht.break_level, sht.zone_top) == (108.5, 109, 0.5, 111.5, 111.5, 111.5)
    # a high above T but below the box top does not break the short; a high above the box top does
    drive(det, [(107.75, 110, 107.5, 108)], risk_ok=False)
    assert sht.status == "ARMED"
    drive(det, [(108, 111.75, 107.9, 108.1)], risk_ok=False)
    assert (sht.status, sht.reason, sht.end_bar) == ("DONE", "BROKEN", 18)
    assert lng.status == "ARMED"  # lows 107.5 / 107.9 are not below the long's B = 107


def test_bpr_dn_array_pos_mapping_real_engine():
    """Spec s.3.1: the direction comes from pos, not from the array (colour != direction).

    SC_C1 bar 10: BPR_DN box [102.5, 103] with pos -1 -> SHORT, B 102.5, T = min(103, 104.5) = 103, Hi = 104.5,
    break h > 103. SC_C2 bar 10: BPR_DN box [106, 107] with pos +1 -> LONG, B 106, T = min(107, 110) = 107,
    Lo = min(105, 106) = 105, break l < 106.
    """
    p = StrategyParams(source="BPR", **NOFILT)
    (s1,) = real_run(SC_C1[:11], p, risk_ok=False).setups
    assert (s1.src, s1.dir, s1.created, s1.B, s1.T, s1.h, s1.Lo_or_Hi, s1.break_level) == (
        "BPR", -1, 10, 102.5, 103, 0.5, 104.5, 103)
    (s2,) = real_run(SC_C2[:11], p, risk_ok=False).setups
    assert (s2.src, s2.dir, s2.created, s2.B, s2.T, s2.h, s2.Lo_or_Hi, s2.break_level) == (
        "BPR", 1, 10, 106, 107, 1, 105, 106)


def test_fvg_candidate_geometry_real_engine():
    """Spec s.3.1 (FVG rows): bullish B = high[u-2], T = low[u], Lo = B, break l < B; bearish B = high[u],
    T = low[u-2], Hi = T, break h > T."""
    p = StrategyParams(source="FVG", **NOFILT)
    (b,) = real_run(BULL_FVG, p, risk_ok=False).setups
    assert (b.src, b.dir, b.created, b.B, b.T, b.h, b.Lo_or_Hi, b.break_level) == ("FVG", 1, 7, 101, 103, 2, 101, 101)
    (s,) = real_run(BEAR_FVG, p, risk_ok=False).setups
    assert (s.src, s.dir, s.created, s.B, s.T, s.h, s.Lo_or_Hi, s.break_level) == ("FVG", -1, 7, 106, 110, 4, 110, 110)


def test_candidate_order_and_source_direction_filters():
    """Spec s.3.1: candidates of one bar come in the order BPR(UP array), BPR(DN array), bullish FVG, bearish FVG;
    the source / direction filters drop candidates silently (no id, no record).

    SC_C1: bullish FVG at bar 7 (long); at bar 10 a BPR_DN with pos -1 (short) and a bearish FVG (short).
    """
    bars = SC_C1[:11]

    def kinds(params):
        det = real_run(bars, params, risk_ok=False)
        return [(s.id, s.created, s.src, s.dir) for s in det.setups], sorted({e["id"] for e in det.events})

    base = NOFILT
    assert kinds(StrategyParams(source="BOTH", **base)) == (
        [(1, 7, "FVG", 1), (2, 10, "BPR", -1), (3, 10, "FVG", -1)], [1, 2, 3])
    assert kinds(StrategyParams(source="FVG", **base)) == ([(1, 7, "FVG", 1), (2, 10, "FVG", -1)], [1, 2])
    assert kinds(StrategyParams(source="BPR", **base)) == ([(1, 10, "BPR", -1)], [1])
    assert kinds(StrategyParams(source="BOTH", direction="LONG_ONLY", **base)) == ([(1, 7, "FVG", 1)], [1])
    assert kinds(StrategyParams(source="BOTH", direction="SHORT_ONLY", **base)) == (
        [(1, 10, "BPR", -1), (2, 10, "FVG", -1)], [1, 2])


def test_bad_geometry_and_broken_at_creation():
    """Spec s.3.1 notes: h <= 0 -> DONE(BAD_GEOMETRY); a BPR inactive on its creation bar -> DONE(BROKEN_AT_CREATION).
    Neither can happen in FVG mode, so the zones are scripted."""
    p = StrategyParams(**NOFILT)
    flat_zone = [  # T = min(up.top, dn.top) = 100 = B -> h = 0
        ("FVG_DN", "set", Zone(Box(3, 100.0, 12, 99.5), True)),
        ("FVG_UP", "set", Zone(Box(4, 101.0, 12, 100.0), True)),
        ("BPR_UP", "new", Zone(Box(3, 100.0, 20, 100.0), True, 1)),
    ]
    det = stub_detector(p, {6: flat_zone})
    drive(det, [FLAT] * 7)
    assert brief(det) == [(6, 1, "DONE", "BAD_GEOMETRY")]
    zones = long_zones()
    zones[2] = ("BPR_UP", "new", Zone(Box(3, 101.5, 6, 100.0), False, 1))  # already broken
    det = stub_detector(p, {6: zones})
    drive(det, [FLAT] * 7)
    assert brief(det) == [(6, 1, "DONE", "BROKEN_AT_CREATION")]
    assert (det.setups[0].B, det.setups[0].T, det.setups[0].status) == (100.0, 101.0, "DONE")


# =============================================================================================== s.3.2 sweep
def test_sweep_ok_base_long_and_short():
    """Spec s.3.2: s = lowest low of [u-5, u] = bar 8 (97), R = min l[3..7] = 99, 97 < 99 -> sweep OK.
    Short mirror: s = highest high = bar 8 (103), R = max h[3..7] = 101, 103 > 101."""
    det = long_det()
    drive(det, BASE, risk_ok=False)
    st = det.setups[0]
    assert (st.status, st.s, st.sweep_extreme, st.sweep_ref) == ("ARMED", 8, 97, 99)
    det = short_det()
    drive(det, BASE_S, risk_ok=False)
    st = det.setups[0]
    assert (st.status, st.dir, st.s, st.sweep_extreme, st.sweep_ref) == ("ARMED", -1, 8, 103, 101)


def test_sweep_ties_go_to_the_latest_bar():
    """Spec s.3.2: ties -> the LATEST bar. With lows 97 at bars 8 and 9, s = 9; then R = min l[4..8] = 97 contains
    the earlier 97 and 97 < 97 is false -> DONE(NO_SWEEP). Without the sweep filter the setup is ARMED with s = 9
    (R is still computed; M = max h[4..8] = 101, MSS at bar 10). The short mirror behaves the same."""
    tie = list(BASE)
    tie[9] = (98, 100, 97, 99.5)
    det = long_det()
    drive(det, tie)
    assert brief(det) == [(12, 1, "DONE", "NO_SWEEP")]
    assert (det.setups[0].s, det.setups[0].sweep_ref) == (9, 97)
    det = long_det(StrategyParams(sweep_window=5, range_bars=5, mss_bars=5, rally_bars=3, use_sweep=False))
    drive(det, tie, risk_ok=False)
    st = det.setups[0]
    assert (st.status, st.s, st.sweep_extreme, st.sweep_ref, st.M, st.mss_bar) == ("ARMED", 9, 97, 97, 101, 10)
    det = short_det()
    drive(det, mirror(tie))
    assert brief(det) == [(12, 1, "DONE", "NO_SWEEP")] and det.setups[0].s == 9


def test_sweep_needs_a_strictly_lower_low():
    """Spec s.3.2: sweepOK = legLow < R (strict). Lows 99 at bars 7 and 8 (s = 8, the latest) and R = 99 -> NO_SWEEP."""
    bars = list(BASE)
    bars[8] = (99, 99.5, 99, 99.25)
    bars[9] = (99.25, 100, 99.2, 99.5)
    det = long_det()
    drive(det, bars)
    assert brief(det) == [(12, 1, "DONE", "NO_SWEEP")]
    assert (det.setups[0].s, det.setups[0].sweep_extreme, det.setups[0].sweep_ref) == (8, 99, 99)


def test_insufficient_history():
    """Spec s.3.2 / s.3.3: missing windows give DONE(INSUFFICIENT_HISTORY).

    (a) zone at bar 4 < sweep_window 5: the sweep window is clipped to [0, 4], s = 3, then s - range_bars < 0;
        with range_bars = mss_bars = 3 the same zone is ARMED with s = 3;
    (b) zone at bar 7, lowest low at bar 3: s - range_bars = -2 < 0;
    (c) the range window is required even without the sweep filter (range 5, MSS 3);
    (d) the MSS window is required even without the MSS filter (range 3, MSS 5);
    (e) range 3 and MSS 3 fit (s - 3 = 0) -> ARMED, with or without the filters (R = min l[0..2] = 99 > 97).
    """
    bars = [FLAT] * 8
    bars[3] = (99, 100, 97, 99.5)
    det = long_det(extra={12: [], 4: long_zones()})
    drive(det, bars[:5])
    assert brief(det) == [(4, 1, "DONE", "INSUFFICIENT_HISTORY")] and det.setups[0].s == 3
    det = long_det(StrategyParams(sweep_window=5, range_bars=3, mss_bars=3), extra={12: [], 4: long_zones()})
    drive(det, bars[:5], risk_ok=False)
    assert (det.setups[0].status, det.setups[0].s) == ("ARMED", 3)
    for params, want in (
        (PS, "INSUFFICIENT_HISTORY"),
        (StrategyParams(sweep_window=5, range_bars=5, mss_bars=3, use_sweep=False), "INSUFFICIENT_HISTORY"),
        (StrategyParams(sweep_window=5, range_bars=3, mss_bars=5, use_mss=False), "INSUFFICIENT_HISTORY"),
        (StrategyParams(sweep_window=5, range_bars=3, mss_bars=3), None),
        (StrategyParams(sweep_window=5, range_bars=3, mss_bars=3, use_sweep=False, use_mss=False), None),
    ):
        det = long_det(params, extra={12: [], 7: long_zones()})
        drive(det, bars, risk_ok=False)
        st = det.setups[0]
        assert st.s == 3
        assert (st.status, st.reason) == (("DONE", want) if want else ("ARMED", None))


# =============================================================================================== s.3.3 MSS
def test_mss_before_creation_is_logged_after_armed():
    """Spec s.3.3: at creation bars (s, u] are checked; bar 10 closes 101.5 > M = 101 -> mss_bar 10, and the MSS
    record (n = 12) follows the ARMED record."""
    det = long_det()
    drive(det, BASE, risk_ok=False)
    assert brief(det) == [(12, 1, "ARMED", None), (12, 1, "MSS", None)]
    assert (det.setups[0].M, det.setups[0].mss_bar) == (101, 10)


# MSS_LATE: bar 10 closes exactly at M = 101 (not a shift), the zone appears at bar 12 without a shift, and bar 13
# closes 101.25 > 101 -> MSS at 13. X = max h[8..12] = 101 at creation, 101.5 after bar 13, 103 after bar 14.
MSS_LATE = [FLAT] * 8 + [
    (99, 99.5, 97, 98),  # 8: s
    (98, 100, 97.5, 99.5),
    (99.5, 101, 99.5, 101),  # 10: close == M
    (101, 101, 100.5, 100.75),
    (100.75, 101, 100.25, 100.5),  # 12: zone
    (100.5, 101.5, 100.25, 101.25),  # 13: MSS
    (101.25, 103, 101, 102.75),  # 14
]


def test_mss_after_creation_strict_and_rr_retry():
    """Spec s.3.3 and s.4 step 5 (RR check keeps ARMED and retries with the new X).

    Bar 13: MSS (101.25 > 101). LIMIT long: P = 100 + 0.05 + 0.1 = 100.15, SL = min(100 - 1.2, 99.5 - 0.2) = 98.8,
    TP1 = X - 0.2 = 101.3 -> rr1 = 1.15 / 1.35 = 0.85 < 1 -> no order, still ARMED.
    Bar 14: X = 103 -> TP1 = 102.8, rr1 = 2.65 / 1.35 = 1.96 >= 1 -> PLACE_LIMIT; TP2 = P + (X - O) = 100.15 + (103 -
    97.5) = 105.65.
    """
    det = long_det()
    drive(det, MSS_LATE[:13])
    st = det.setups[0]
    assert (st.status, st.mss_bar, st.X) == ("ARMED", None, 101)
    drive(det, MSS_LATE[13:14])
    assert (st.status, st.mss_bar, st.X) == ("ARMED", 13, 101.5)
    out = drive(det, MSS_LATE[14:])
    assert brief(det) == [(12, 1, "ARMED", None), (13, 1, "MSS", None), (14, 1, "PLACE_LIMIT", None)]
    assert out == [Intent("PLACE_LIMIT", 1, 1, "BPR", det.events[-1]["P"], det.events[-1]["SL"],
                          det.events[-1]["TP1"], det.events[-1]["TP2"])]
    assert_levels(det.events[-1], 100.15, 98.8, 102.8, 105.65)
    assert (st.status, st.order, st.decision_bar, st.X) == ("ORDERED", "LIMIT", 14, 103)


def test_mss_bar_must_come_after_the_sweep_bar():
    """Spec s.3.3: the MSS bar m needs s < m. The sweep bar itself closes 101.25 > M = 101 but does not count."""
    bars = list(MSS_LATE)
    bars[8] = (99, 101.5, 97, 101.25)
    det = long_det()
    drive(det, bars[:13])
    assert (det.setups[0].s, det.setups[0].M, det.setups[0].mss_bar) == (8, 101, None)
    drive(det, bars[13:14], risk_ok=False)
    assert det.setups[0].mss_bar == 13


def test_mss_disabled_counts_as_done_at_creation():
    """Spec s.3.3: use_mss false -> MSS treated as done at creation (MSS record at n = u); M is still computed."""
    det = long_det(StrategyParams(sweep_window=5, range_bars=5, mss_bars=5, rally_bars=3, use_mss=False))
    drive(det, MSS_LATE[:13], risk_ok=False)
    st = det.setups[0]
    assert (st.M, st.mss_bar) == (101, 12)
    assert brief(det) == [(12, 1, "ARMED", None), (12, 1, "MSS", None)]


def test_short_mss_mirror():
    """Spec s.3.3 (short): M = min l[s-5 .. s-1] = 99; MSS at the first close < 99 after s (bar 10 closes 98.5)."""
    det = short_det()
    drive(det, BASE_S, risk_ok=False)
    st = det.setups[0]
    assert (st.dir, st.s, st.M, st.mss_bar) == (-1, 8, 99, 10)
    det = short_det()
    drive(det, mirror(MSS_LATE), risk_ok=False)
    assert brief(det) == [(12, 1, "ARMED", None), (13, 1, "MSS", None)]


# =============================================================================================== s.3.4 X and O
def test_x_and_o_windows():
    """Spec s.3.4: X = max h over [s, k] (bars before s ignored), updated while ARMED and frozen once ordered;
    O = min l over [u - rally_bars, u], clipped at 0."""
    no_mss = StrategyParams(sweep_window=5, range_bars=5, mss_bars=5, rally_bars=3, use_mss=False)
    bars = list(BASE)
    bars[7] = (100, 105, 99, 100)  # a higher high just before s = 8
    det = long_det(no_mss)
    drive(det, bars, risk_ok=False)
    st = det.setups[0]
    assert (st.s, st.X, st.O) == (8, 104, 97.5)  # O over bars 9..12
    drive(det, [(103.5, 104.5, 103, 104)], risk_ok=False)
    assert st.X == 104.5  # updated while ARMED
    drive(det, [(104, 104.25, 103.5, 104)])  # order decided here: TP1 = 104.5 - 0.2 = 104.3
    assert (st.status, st.X, st.TP1) == ("ORDERED", 104.5, 104.3)
    drive(det, [(104, 104.2, 103.5, 104)])  # an ORDERED setup skips step 3e: X stays frozen
    assert (st.status, st.X) == ("ORDERED", 104.5)
    det = long_det(StrategyParams(sweep_window=5, range_bars=5, mss_bars=5, rally_bars=4, use_mss=False))
    drive(det, BASE, risk_ok=False)
    assert det.setups[0].O == 97  # rally_bars 4: bars 8..12
    det = long_det(StrategyParams(sweep_window=2, range_bars=1, mss_bars=1, use_sweep=False, use_mss=False,
                                  rally_bars=10),
                   extra={12: [], 3: long_zones()})
    bars = [(100, 101, 98.5, 100), FLAT, FLAT, (100, 102, 99.5, 101)]
    drive(det, bars, risk_ok=False)
    assert (det.setups[0].s, det.setups[0].X, det.setups[0].O) == (2, 102, 98.5)  # O window clipped to [0, 3]


# =============================================================================================== s.4 step 5 LIMIT
def test_limit_levels_long():
    """Spec s.4 step 5 (LIMIT, long; sp 0.1, tick 0.01, delta 5):
    P = B + 5*0.01 + sp = 100.15 (ask); SL = min(B - 1.2h, Lo - 2sp) = min(98.8, 99.3) = 98.8 (bid);
    TP1 = X - 2sp = 103.8 (bid); TP2 = P + (X - O) = 100.15 + (104 - 97.5) = 106.65 (bid).
    risk 1.35, rr1 = 3.65 / 1.35 = 2.70, cost = (0.1 + 0.07 + 0.02) / 1.35 = 0.141 <= 0.15."""
    det = long_det()
    out = drive(det, BASE)
    assert brief(det) == [(12, 1, "ARMED", None), (12, 1, "MSS", None), (12, 1, "PLACE_LIMIT", None)]
    e = det.events[-1]
    assert (e["dir"], e["src"]) == (1, "BPR")
    assert_levels(e, 100.15, 98.8, 103.8, 106.65)
    assert len(out) == 1 and out[0].type == "PLACE_LIMIT" and (out[0].id, out[0].dir) == (1, 1)
    st = det.setups[0]
    assert (st.status, st.order, st.decision_bar) == ("ORDERED", "LIMIT", 12)
    assert all(close(a, b) for a, b in zip((st.P, st.SL, st.TP1, st.TP2), (100.15, 98.8, 103.8, 106.65)))


def test_limit_levels_short():
    """Spec s.4 step 5 (LIMIT, short): P = T - 5*0.01 = 99.95 (bid); SL = max(T + 1.2h, Hi + 2sp) + sp =
    max(101.2, 100.7) + 0.1 = 101.3 (ask); TP1 = X + 2sp = 96 + 0.2 = 96.2 (ask); TP2 = P - (O - X) =
    99.95 - (102.5 - 96) = 93.45 (ask). risk 1.35, rr1 = 3.75 / 1.35."""
    det = short_det()
    drive(det, BASE_S)
    assert brief(det) == [(12, 1, "ARMED", None), (12, 1, "MSS", None), (12, 1, "PLACE_LIMIT", None)]
    assert det.events[-1]["dir"] == -1
    assert_levels(det.events[-1], 99.95, 101.3, 96.2, 93.45)
    st = det.setups[0]
    assert (st.B, st.T, st.h, st.Lo_or_Hi, st.break_level, st.X, st.O) == (99, 100, 1, 100.5, 100.5, 96, 102.5)


def test_limit_stop_takes_the_further_of_the_two_rules():
    """Spec s.4 step 5: with stop_zone_mult 0.5 the gap rule is further away.
    Long: SL = min(100 - 0.5, 99.5 - 0.2) = 99.3. Short: SL = max(100 + 0.5, 100.5 + 0.2) + 0.1 = 100.8."""
    p = StrategyParams(sweep_window=5, range_bars=5, mss_bars=5, rally_bars=3, stop_zone_mult=0.5, max_cost_r=1.0)
    det = long_det(p)
    drive(det, BASE)
    assert_levels(det.events[-1], 100.15, 99.3, 103.8, 106.65)
    det = short_det(p)
    drive(det, BASE_S)
    assert_levels(det.events[-1], 99.95, 100.8, 96.2, 93.45)


def test_limit_marketability_waits_including_the_equal_case():
    """Spec s.4 step 5: long waits while the decision ask c + sp <= P; short waits while the bid c >= P.
    Exact binary numbers: tick 0.25, sp 0.25, delta 1 -> long P = 100 + 0.25 + 0.25 = 100.5, short P = 100 - 0.25.
    Long: bar 12 closes 100.25 (ask 100.5 == P) -> wait; bar 13 closes 100.5 (ask 100.75 > P) -> order at 13.
    Short: bar 12 closes 99.75 (== P) -> wait; bar 13 closes 99.5 -> order at 13."""
    p = StrategyParams(sweep_window=5, range_bars=5, mss_bars=5, rally_bars=3, tick_size=0.25, entry_offset_ticks=1,
                       max_cost_r=1.0)
    bars = BASE[:12] + [(102.5, 104, 100.25, 100.25), (100.25, 101, 100, 100.5)]
    det = long_det(p)
    drive(det, bars, sp=0.25)
    assert [e["ev"] for e in det.events] == ["ARMED", "MSS", "PLACE_LIMIT"] and det.events[-1]["n"] == 13
    assert det.events[-1]["P"] == 100.5
    det = short_det(p)
    drive(det, mirror(bars), sp=0.25)
    assert [e["ev"] for e in det.events] == ["ARMED", "MSS", "PLACE_LIMIT"] and det.events[-1]["n"] == 13
    assert det.events[-1]["P"] == 99.75


def test_cost_check_keeps_armed_and_retries():
    """Spec s.4 step 5: sp 0.3 -> P = 100.35, SL = min(98.8, 98.9) = 98.8, risk 1.55, cost = (0.3 + 0.07 + 0.02)
    / 1.55 = 0.252 > 0.15 -> wait. Next bar sp 0.1 -> the base levels are placed (X still 104)."""
    det = long_det()
    drive(det, BASE, sp=0.3)
    assert det.setups[0].status == "ARMED" and [e["ev"] for e in det.events] == ["ARMED", "MSS"]
    drive(det, [(103.5, 103.75, 103, 103.25)], sp=0.1)
    assert det.events[-1]["n"] == 13 and det.events[-1]["ev"] == "PLACE_LIMIT"
    assert_levels(det.events[-1], 100.15, 98.8, 103.8, 106.65)


def test_tp2_rules_and_tp_modes():
    """Spec s.4 step 5: TP1_TP2 with TP2 not beyond TP1 -> the trade uses TP1 only (TP2 set equal to TP1).
    rally_bars 0 -> O = l[12] = 102 -> long TP2 = 100.15 + 2 = 102.15 <= TP1 103.8; short: O = h[12] = 98 ->
    TP2 = 99.95 - 2 = 97.95 >= TP1 96.2. TP1_ONLY records the computed TP2 (unused); TP2_ONLY keeps it."""
    p0 = StrategyParams(sweep_window=5, range_bars=5, mss_bars=5, rally_bars=0)
    det = long_det(p0)
    drive(det, BASE)
    assert_levels(det.events[-1], 100.15, 98.8, 103.8, 103.8)
    det = short_det(p0)
    drive(det, BASE_S)
    assert_levels(det.events[-1], 99.95, 101.3, 96.2, 96.2)
    det = long_det(StrategyParams(sweep_window=5, range_bars=5, mss_bars=5, rally_bars=3, tp_mode="TP1_ONLY"))
    drive(det, BASE)
    assert_levels(det.events[-1], 100.15, 98.8, 103.8, 106.65)
    det = long_det(StrategyParams(sweep_window=5, range_bars=5, mss_bars=5, rally_bars=0, tp_mode="TP2_ONLY"))
    drive(det, BASE)
    assert_levels(det.events[-1], 100.15, 98.8, 103.8, 102.15)


def test_round_to_tick():
    """Spec s.4 step 5 ("all levels are rounded to the tick"): MathRound(x / tick) * tick, half away from zero."""
    assert round_to_tick(100.154, 0.01) == 100.15
    assert round_to_tick(100.156, 0.01) == 100.16
    assert round_to_tick(98.8 + 1e-12, 0.01) == 98.8
    assert round_to_tick(100.125, 0.25) == 100.25 and round_to_tick(-100.125, 0.25) == -100.25
    assert round_to_tick(1.234567, 0.00001) == 1.23457


# =============================================================================================== s.4 step 5 CONFIRM
CONFIRM_TAIL = [
    (103.5, 103.6, 101, 101.2),  # 13: low 101 > B + h/4 = 100.25 -> no trigger
    (101.2, 101.3, 100.25, 100.5),  # 14: close 100.5 < open -> no trigger
    (100.4, 100.9, 100.25, 100.5),  # 15: low == 100.25, close == 100.5 == B + h/2, close > open -> MARKET
]


def test_confirm_trigger_long():
    """Spec s.4 step 5 (CONFIRM, long): l <= B + h/4, c >= B + h/2, c > o. Bar 15 triggers (both equalities).
    P = c + sp = 100.6; SL 98.8; X = max h[8..15] = 104 -> TP1 103.8; TP2 = 100.6 + (104 - 97.5) = 107.1."""
    p = StrategyParams(sweep_window=5, range_bars=5, mss_bars=5, rally_bars=3, entry_mode="CONFIRM")
    det = long_det(p)
    out = drive(det, BASE + CONFIRM_TAIL)
    assert brief(det) == [(12, 1, "ARMED", None), (12, 1, "MSS", None), (15, 1, "MARKET", None)]
    assert_levels(det.events[-1], 100.6, 98.8, 103.8, 107.1)
    assert out[0].type == "MARKET" and det.setups[0].order == "MARKET"
    for bad in ((100.4, 100.9, 100.26, 100.5), (100.4, 100.9, 100.25, 100.49), (100.5, 100.9, 100.25, 100.5)):
        det = long_det(p)
        drive(det, BASE + CONFIRM_TAIL[:2] + [bad])
        assert [e["ev"] for e in det.events] == ["ARMED", "MSS"], bad


def test_confirm_trigger_short():
    """Spec s.4 step 5 (CONFIRM, short): h >= T - h/4 = 99.75, c <= T - h/2 = 99.5, c < o. Mirror bar 15 triggers:
    P = c = 99.5 (bid); SL 101.3; TP1 = 96 + 0.2 = 96.2; TP2 = 99.5 - (102.5 - 96) = 93.0."""
    p = StrategyParams(sweep_window=5, range_bars=5, mss_bars=5, rally_bars=3, entry_mode="CONFIRM")
    det = short_det(p)
    drive(det, mirror(BASE + CONFIRM_TAIL))
    assert brief(det) == [(12, 1, "ARMED", None), (12, 1, "MSS", None), (15, 1, "MARKET", None)]
    assert_levels(det.events[-1], 99.5, 101.3, 96.2, 93.0)


def test_undecided_market_order_is_pending_in_step3():
    """Spec s.4 step 3 / s.9: a MARKET order that has not filled (the harness never fills) is a pending order:
    a break gives DONE(BROKEN) + CANCEL; runaway is for pending LIMIT orders only ("pending LIMIT only" in 3c versus
    "pending only" in 3d), so a high above TP1 103.8 leaves it ORDERED."""
    p = StrategyParams(sweep_window=5, range_bars=5, mss_bars=5, rally_bars=3, entry_mode="CONFIRM")
    det = long_det(p)
    drive(det, BASE + CONFIRM_TAIL + [(100.6, 104, 100.5, 103.9)])
    assert det.setups[0].status == "ORDERED" and det.setups[0].order == "MARKET"
    out = drive(det, [(103.9, 104, 99.9, 100)])
    assert brief(det)[-2:] == [(17, 1, "DONE", "BROKEN"), (17, 1, "CANCEL", "BROKEN")]
    assert out == [Intent("CANCEL", 1, 1, "BPR", reason="BROKEN")]


# =============================================================================================== s.4 step 3
QUIET = (103.5, 103.6, 103, 103.25)  # no break, no runaway (TP1 103.8)


def test_step3_break_before_expiry():
    """Spec s.4 step 3 order (a before b): expiry_bars 1 -> bar 13 is not expired (13 - 12 = 1); bar 14 is expired
    and breaks (low 99.9 < 100) -> BROKEN wins; the pending order gets DONE(BROKEN) then CANCEL(BROKEN)."""
    p = StrategyParams(sweep_window=5, range_bars=5, mss_bars=5, rally_bars=3, expiry_bars=1)
    det = long_det(p)
    out = drive(det, BASE + [QUIET, (103, 103.2, 99.9, 100.5)])
    assert brief(det)[3:] == [(14, 1, "DONE", "BROKEN"), (14, 1, "CANCEL", "BROKEN")]
    assert out[-1] == Intent("CANCEL", 1, 1, "BPR", reason="BROKEN")
    assert (det.setups[0].status, det.setups[0].reason, det.setups[0].end_bar) == ("DONE", "BROKEN", 14)


def test_step3_expiry_before_runaway():
    """Spec s.4 step 3 (b before c): bar 14 is expired and its high reaches TP1 -> EXPIRED."""
    p = StrategyParams(sweep_window=5, range_bars=5, mss_bars=5, rally_bars=3, expiry_bars=1)
    det = long_det(p)
    drive(det, BASE + [QUIET, (103, 104, 102, 103.5)])
    assert brief(det)[3:] == [(14, 1, "DONE", "EXPIRED"), (14, 1, "CANCEL", "EXPIRED")]


def test_step3_runaway_before_session_and_equality():
    """Spec s.4 step 3 (c before d): high == TP1 103.8 counts (>=), and wins over a session cancel on the same bar."""
    det = long_det()
    drive(det, BASE + [(103.5, 103.8, 102, 103)], at={13: dict(session_cancel=True)})
    assert brief(det)[3:] == [(13, 1, "DONE", "RUNAWAY"), (13, 1, "CANCEL", "RUNAWAY")]


def test_step3_session_cancel_pending_only():
    """Spec s.4 step 3d: a pending order is cancelled when the next open is at/after the last entry time
    (SESSION_END); ignored when use_session is false; an ARMED setup is not session-cancelled."""
    det = long_det()
    drive(det, BASE + [QUIET], at={13: dict(session_cancel=True)})
    assert brief(det)[3:] == [(13, 1, "DONE", "SESSION_END"), (13, 1, "CANCEL", "SESSION_END")]
    det = long_det(StrategyParams(sweep_window=5, range_bars=5, mss_bars=5, rally_bars=3, use_session=False))
    drive(det, BASE + [QUIET], at={13: dict(session_cancel=True)})
    assert det.setups[0].status == "ORDERED"
    det = long_det()
    drive(det, BASE + [QUIET], risk_ok=False, at={13: dict(session_cancel=True)})
    assert det.setups[0].status == "ARMED"


def test_step3_armed_break_and_expiry_have_no_cancel():
    """Spec s.4 step 3a/3b on an ARMED setup: DONE(BROKEN) / DONE(EXPIRED) without a CANCEL record or intent;
    expiry needs u - created > expiry_bars (bar 13 is still alive with expiry 1)."""
    det = long_det()
    out = drive(det, BASE + [(103.5, 103.6, 99.5, 100)], risk_ok=False)
    assert out == [] and brief(det)[2:] == [(13, 1, "DONE", "BROKEN")]
    p = StrategyParams(sweep_window=5, range_bars=5, mss_bars=5, rally_bars=3, expiry_bars=1)
    det = long_det(p)
    drive(det, BASE + [QUIET], risk_ok=False)
    assert det.setups[0].status == "ARMED"
    drive(det, [QUIET], risk_ok=False)
    assert brief(det)[2:] == [(14, 1, "DONE", "EXPIRED")]


def test_step3_short_runaway_uses_the_ask():
    """Spec s.4 step 3c (short): runaway when l <= TP1 - spread (TP1 96.2 is an ask level, sp 0.1 -> 96.1).
    Low 96.15 does not trigger; low 96.05 does."""
    det = short_det()
    drive(det, BASE_S + [(96.5, 97, 96.15, 96.75)])
    assert det.setups[0].status == "ORDERED"
    drive(det, [(96.75, 97, 96.05, 96.5)])
    assert brief(det)[3:] == [(14, 1, "DONE", "RUNAWAY"), (14, 1, "CANCEL", "RUNAWAY")]


def test_step3_short_break_uses_the_box_top():
    """Spec s.3.1 / s.4 step 3a (short BPR): broken when h > box top 100.5 (not T = 100)."""
    det = short_det()
    drive(det, BASE_S + [(97, 100.5, 96.5, 97)], risk_ok=False)
    assert det.setups[0].status == "ARMED"
    drive(det, [(97, 100.6, 96.5, 97)], risk_ok=False)
    assert brief(det)[2:] == [(14, 1, "DONE", "BROKEN")]


# =============================================================================================== s.4 step 2 refresh
def test_fvg_update_refresh_long_and_short_real_engine():
    """Spec s.4 step 2 with the real engine. BULL_CONSEC: FVG_UP [101, 104.5] at bar 7, consecutive update at bar 8
    to [high[6] = 105.5, low[8] = 108] -> the ARMED long setup takes B 105.5, T 108, h 2.5, Lo 105.5, break 105.5.
    BEAR_CONSEC: FVG_DN [104.25, 110] at bar 7, update at 8 to [high[8] = 100, low[6] = 103.75] -> B 100, T 103.75,
    Hi 103.75, break 103.75."""
    p = StrategyParams(source="FVG", **NOFILT)
    det = SetupDetector(p)
    drive(det, BULL_CONSEC[:8], risk_ok=False)
    st = det.setups[0]
    assert (st.B, st.T, st.h) == (101, 104.5, 3.5)
    drive(det, BULL_CONSEC[8:], risk_ok=False)
    assert (st.status, st.B, st.T, st.h, st.Lo_or_Hi, st.break_level) == ("ARMED", 105.5, 108, 2.5, 105.5, 105.5)
    det = SetupDetector(p)
    drive(det, BEAR_CONSEC[:8], risk_ok=False)
    st = det.setups[0]
    assert (st.dir, st.B, st.T, st.h) == (-1, 104.25, 110, 5.75)
    drive(det, BEAR_CONSEC[8:], risk_ok=False)
    assert (st.status, st.B, st.T, st.h, st.Lo_or_Hi, st.break_level) == ("ARMED", 100, 103.75, 3.75, 103.75, 103.75)


def test_fvg_update_does_not_touch_an_ordered_setup():
    """Spec s.4 step 2: setups that are ORDERED or later keep their levels. The long FVG setup of BULL_CONSEC is
    ordered at bar 7 (P = 101.15, TP1 = X - 0.2 = 110.3 with X = max h[5..7] = 110.5), so the bar-8 update leaves
    B = 101 (bar 8's high 111 then cancels it as RUNAWAY)."""
    p = StrategyParams(source="FVG", **NOFILT)
    det = SetupDetector(p)
    drive(det, BULL_CONSEC)
    st = det.setups[0]
    assert (st.decision_bar, st.B, st.T, st.reason) == (7, 101, 104.5, "RUNAWAY")
    assert_levels(det.events[2], 101.15, 96.8, 110.3, 101.15 + (110.5 - 99))


def test_fvg_update_refreshes_only_the_most_recent_setup_on_index0():
    """Spec s.4 step 2: only the most recent FVG setup of that side, if ARMED and built from FVG_UP[0].
    (a) update at bar 7 refreshes setup 1. (b) capacity 1: a newer bullish FVG at bar 7 makes setup 2 DONE(CAPACITY);
    the update at bar 8 belongs to that newer gap, so neither setup changes. (c) a bearish update leaves longs alone."""
    p = StrategyParams(source="FVG", use_sweep=False, use_mss=False, sweep_window=5, range_bars=3, mss_bars=3)
    z1 = Zone(Box(4, 99.0, 6, 98.0), True)
    bars = [(100, 101, 99.5, 100.5)] * 9
    det = stub_detector(p, {6: [("FVG_UP", "new", z1)], 7: [("FVG_UP", "update", Zone(Box(5, 99.5, 7, 98.25), True))]})
    drive(det, bars[:8], risk_ok=False)
    st = det.setups[0]
    assert (st.B, st.T, st.h, st.Lo_or_Hi, st.break_level) == (98.25, 99.5, 1.25, 98.25, 98.25)
    p1 = StrategyParams(source="FVG", use_sweep=False, use_mss=False, sweep_window=5, range_bars=3, mss_bars=3,
                        capacity=1)
    det = stub_detector(p1, {
        6: [("FVG_UP", "new", Zone(Box(4, 99.0, 6, 98.0), True))],
        7: [("FVG_UP", "new", Zone(Box(5, 99.25, 7, 98.5), True))],
        8: [("FVG_UP", "update", Zone(Box(6, 99.75, 8, 98.75), True))],
    })
    drive(det, bars, risk_ok=False)
    s1, s2 = det.setups
    assert (s1.status, s1.B, s1.T) == ("ARMED", 98.0, 99.0)
    assert (s2.status, s2.reason, s2.B, s2.T) == ("DONE", "CAPACITY", 98.5, 99.25)
    det = stub_detector(p, {
        6: [("FVG_UP", "new", Zone(Box(4, 99.0, 6, 98.0), True))],
        7: [("FVG_DN", "update", Zone(Box(5, 103.0, 7, 102.0), True))],
    })
    drive(det, bars[:8], risk_ok=False)
    assert (det.setups[0].B, det.setups[0].T) == (98.0, 99.0)


# =============================================================================================== s.4 step 4
def test_capacity():
    """Spec s.4 step 4: above `capacity` tracked (ARMED / ORDERED / FILLED) setups the reason is CAPACITY; a DONE
    setup frees its place."""
    p = StrategyParams(source="FVG", use_sweep=False, use_mss=False, sweep_window=5, range_bars=3, mss_bars=3,
                       capacity=1)

    def z():
        return Zone(Box(4, 99.0, 6, 98.0), True)

    det = stub_detector(p, {6: [("FVG_UP", "new", z())], 7: [("FVG_UP", "new", z())], 9: [("FVG_UP", "new", z())]})
    bars = [(100, 101, 99.5, 100.5)] * 8 + [(100, 101, 97.5, 100.5), (100, 101, 99.5, 100.5)]
    drive(det, bars, risk_ok=False)
    assert brief(det) == [
        (6, 1, "ARMED", None), (6, 1, "MSS", None),
        (7, 2, "DONE", "CAPACITY"),
        (8, 1, "DONE", "BROKEN"),
        (9, 3, "ARMED", None), (9, 3, "MSS", None),
    ]


def test_warmup_setups_are_never_traded():
    """Spec s.4 step 4: setups created during warm-up (u < trade_from = 14) become DONE(WARMUP) when warm-up ends
    (logged at the last warm-up bar, 13); no decision is taken on warm-up bars; later setups trade."""
    p = StrategyParams(sweep_window=5, range_bars=5, mss_bars=5, rally_bars=3, use_sweep=False, use_mss=False)
    extra = {15: [("BPR_UP", "new", Zone(Box(3, 101.5, 20, 100.0), True, 1))]}
    det = long_det(p, trade_from=14, extra=extra)
    drive(det, BASE + [QUIET, QUIET, QUIET])
    assert brief(det) == [
        (12, 1, "ARMED", None), (12, 1, "MSS", None),
        (13, 1, "DONE", "WARMUP"),
        (15, 2, "ARMED", None), (15, 2, "MSS", None), (15, 2, "PLACE_LIMIT", None),
    ]


# =============================================================================================== s.4 step 5 gating
def two_long_setups(params: StrategyParams) -> SetupDetector:
    """A BPR long (id 1) and an FVG long (id 2, the bullish FVG [100, 101]) created on bar 12."""
    zones = long_zones()
    script = {12: [zones[0], ("FVG_UP", "new", Zone(Box(10, 101.0, 12, 100.0), True)), zones[2]]}
    return stub_detector(params, script)


def test_one_order_per_bar_and_slot_gating():
    """Spec s.4 step 5: at most one order per bar, in creation order; slot_free gates every decision.
    Bar 12: setup 1 ordered, setup 2 waits. Bar 13 (high 104.5 >= TP1): setup 1 RUNAWAY; the slot was not free
    when the bar started, so setup 2 waits. Bar 14: setup 2 ordered with X = 104.5 -> TP1 104.3, TP2 = 100.15 +
    (104.5 - 97.5) = 107.15, SL = min(98.8, Lo 100 - 0.2) = 98.8."""
    p = StrategyParams(source="BOTH", sweep_window=5, range_bars=5, mss_bars=5, rally_bars=3)
    det = two_long_setups(p)
    drive(det, BASE + [(103.5, 104.5, 103, 104), (104, 104.25, 103.5, 104)])
    assert brief(det) == [
        (12, 1, "ARMED", None), (12, 1, "MSS", None),
        (12, 2, "ARMED", None), (12, 2, "MSS", None),
        (12, 1, "PLACE_LIMIT", None),
        (13, 1, "DONE", "RUNAWAY"), (13, 1, "CANCEL", "RUNAWAY"),
        (14, 2, "PLACE_LIMIT", None),
    ]
    assert_levels(det.events[-1], 100.15, 98.8, 104.3, 107.15)
    det = two_long_setups(p)
    drive(det, BASE, slot_free=False)
    assert [e["ev"] for e in det.events] == ["ARMED", "MSS", "ARMED", "MSS"]


@pytest.mark.parametrize("field", ["slot_free", "session_entry_ok", "risk_ok", "spread_ok"])
def test_env_conditions_block_decisions(field):
    """Spec s.4 step 5: slot free, session OK, risk OK and spread OK are all needed; the setup stays ARMED."""
    det = long_det()
    drive(det, BASE, **{field: False})
    assert det.setups[0].status == "ARMED" and [e["ev"] for e in det.events] == ["ARMED", "MSS"]


def test_session_entry_flag_ignored_without_use_session():
    """Spec s.1 (use_session): with use_session false the session flags do not gate entries."""
    det = long_det(StrategyParams(sweep_window=5, range_bars=5, mss_bars=5, rally_bars=3, use_session=False))
    drive(det, BASE, session_entry_ok=False)
    assert det.setups[0].status == "ORDERED"


def test_notify_lifecycle():
    """Spec s.4 (executor feedback): filled -> FILLED, closed -> CLOSED; a failed order -> DONE(reason) with a DONE
    record; a cancel report after the detector's own cancel is ignored; impossible transitions raise."""
    det = long_det()
    drive(det, BASE)
    assert det.has_order_or_position()
    det.notify_filled(1)
    assert det.setups[0].status == "FILLED" and det.has_order_or_position()
    with pytest.raises(ValueError):
        det.notify_filled(1)
    det.notify_closed(1, n=20)
    assert (det.setups[0].status, det.setups[0].end_bar) == ("CLOSED", 20) and not det.has_order_or_position()
    det = long_det()
    drive(det, BASE)
    det.notify_cancelled(1, "SIZE_BELOW_MIN")
    assert brief(det)[-1] == (12, 1, "DONE", "SIZE_BELOW_MIN") and not det.has_order_or_position()
    det.notify_cancelled(1, "ORDER_FAILED")  # already DONE: ignored
    assert det.setups[0].reason == "SIZE_BELOW_MIN"
    with pytest.raises(ValueError):
        det.notify_cancelled(1, "NOT_A_REASON")
    with pytest.raises(ValueError):
        det.notify_closed(1)
    with pytest.raises(ValueError):
        det.on_bar_closed(14, *QUIET, Env(True, True, False, True, True, SP))  # bar 13 was skipped


# =============================================================================================== s.9 harness
def _random_bars(seed: int, n: int, start: float = 100.0):
    """Deterministic random series with frequent displacement candles (prices on a 0.01 grid)."""
    rng = random.Random(seed)
    out = []
    c = start
    for _ in range(n):
        o = c + rng.choice([0.0, 0.0, rng.uniform(-0.2, 0.2)])
        if rng.random() < 0.3:
            body = rng.uniform(2.0, 5.0)
            cl = o + rng.choice([1, -1]) * body
            h = max(o, cl) + rng.uniform(0, 0.3) * body * 0.3
            lo = min(o, cl) - rng.uniform(0, 0.3) * body * 0.3
        else:
            cl = o + rng.uniform(-1, 1)
            h = max(o, cl) + rng.uniform(0, 1.5)
            lo = min(o, cl) - rng.uniform(0, 1.5)
        o, h, lo, cl = round(o, 2), round(h, 2), round(lo, 2), round(cl, 2)
        out.append((o, max(o, h, lo, cl), min(o, h, lo, cl), cl))
        c = cl
    return out


HARNESS_PARAMS = [
    StrategyParams(),
    StrategyParams(source="BOTH", max_cost_r=1.0),
    StrategyParams(source="BOTH", entry_mode="CONFIRM", use_sweep=False),
]


def test_harness_run_determinism_and_record_format():
    """Spec s.9: one record per intent / status change with keys n, id, ev, dir, src, reason, P, SL, TP1, TP2 (absent
    values None); two runs give the identical sequence; records are JSON-serialisable and in bar order."""
    bars = _random_bars(7, 1500)
    for params in HARNESS_PARAMS:
        a = harness_run(bars, params, SP)
        b = harness_run(bars, params, SP)
        assert a == b and len(a) > 50
        assert json.loads(json.dumps(a)) == a
        assert [e["n"] for e in a] == sorted(e["n"] for e in a)
        for e in a:
            assert list(e) == ["n", "id", "ev", "dir", "src", "reason", "P", "SL", "TP1", "TP2"]
            assert e["ev"] in ("ARMED", "DONE", "MSS", "PLACE_LIMIT", "MARKET", "CANCEL")
            assert e["dir"] in (1, -1) and e["src"] in ("BPR", "FVG")
            assert (e["reason"] is not None) == (e["ev"] in ("DONE", "CANCEL"))
            assert (e["P"] is not None) == (e["ev"] in ("PLACE_LIMIT", "MARKET"))


def test_harness_invariants_one_order_at_a_time():
    """Spec s.9 harness: orders never fill, so an order ends only through the detector's own DONE + CANCEL
    (BROKEN, EXPIRED, RUNAWAY; never SESSION_END), and a new order is decided only once no other order is open."""
    seen = set()
    for seed in range(4):
        bars = _random_bars(100 + seed, 1500)
        for params in HARNESS_PARAMS:
            ev = harness_run(bars, params, SP)
            open_id = None
            for i, e in enumerate(ev):
                seen.add(e["ev"])
                if e["ev"] in ("PLACE_LIMIT", "MARKET"):
                    assert open_id is None
                    open_id = e["id"]
                elif e["ev"] == "CANCEL":
                    prev = ev[i - 1]
                    assert e["id"] == open_id and (prev["ev"], prev["id"], prev["reason"], prev["n"]) == (
                        "DONE", e["id"], e["reason"], e["n"])
                    assert e["reason"] in ("BROKEN", "EXPIRED", "RUNAWAY")
                    open_id = None
                elif e["ev"] == "DONE" and e["id"] == open_id:
                    assert ev[i + 1]["ev"] == "CANCEL"
    assert seen == {"ARMED", "DONE", "MSS", "PLACE_LIMIT", "MARKET", "CANCEL"}


@pytest.mark.parametrize("params", HARNESS_PARAMS)
def test_causality_truncation_invariance(params):
    """CLAUDE.md no look-ahead / spec s.2 (closed bars only): the records up to bar k are identical when the series
    is cut after bar k, for many k on random series."""
    for seed in (1, 2, 3):
        bars = _random_bars(seed, 700)
        full = harness_run(bars, params, SP)
        rng = random.Random(1000 + seed)
        for k in sorted(rng.sample(range(len(bars)), 12)) + [len(bars) - 1]:
            assert harness_run(bars[: k + 1], params, SP) == [e for e in full if e["n"] <= k], (seed, k)


def test_bar_buffer_trimming_does_not_change_records():
    """Spec s.2 / s.9: the detector keeps only the bars its windows need; the records equal those of a detector
    that keeps every bar."""
    bars = _random_bars(5, 3000)
    params = StrategyParams(source="BOTH", max_cost_r=1.0)
    full = SetupDetector(params)
    full._keep = 10**9  # never trims
    drive(full, bars)
    assert harness_run(bars, params, SP) == full.events and len(full._h) == 3000


# =============================================================================================== s.5 simulator
T0 = 1_700_000_000
XAU = StrategyParams()  # tick 0.01, contract 100, 3.50 / side -> comm_price 0.07, slippage 1 tick
# Playbook worked example (BPR_RETEST_PLAYBOOK s.4): buy limit 2650.55, SL 2649.20, TP1 2653.80, TP2 2655.95.
# R_unit = |P - SL| + slippage + comm_price = 1.35 + 0.01 + 0.07 = 1.43.
LP, LSL, LTP1, LTP2 = 2650.55, 2649.20, 2653.80, 2655.95
# Mirror short: sell limit 2653.80 (bid), SL 2655.15, TP1 2650.55, TP2 2648.40 (ask levels); R_unit 1.43.
SP_, SSL, STP1, STP2 = 2653.80, 2655.15, 2650.55, 2648.40
UNIT = 1.43
DECIDE = (2652.0, 2652.5, 2651.5, 2652.0)  # bar 0: the decision bar


class ScriptedDetector:
    """Stand-in detector for the simulator tests: emits scripted intents (only while slot, risk and session allow)
    and records every call in order."""

    def __init__(self, script):
        self.script = script
        self.calls: list[tuple] = []
        self.setups: list = []

    def on_bar_closed(self, u, o, h, l, c, env):  # noqa: E741
        self.calls.append(("bar", u, env.slot_free, env.risk_ok, env.sp))
        items = self.script(u) if callable(self.script) else self.script.get(u, [])
        out = []
        for it in items:
            if it.type == "CANCEL" or (env.slot_free and env.risk_ok and env.session_entry_ok and not out):
                out.append(it)
        return out

    def notify_filled(self, sid):
        self.calls.append(("filled", sid))

    def notify_cancelled(self, sid, reason, n=None):
        self.calls.append(("cancelled", sid, reason, n))

    def notify_closed(self, sid, n=None):
        self.calls.append(("closed", sid, n))


def long_limit(sid=1, tp2=LTP2):
    return Intent("PLACE_LIMIT", sid, 1, "BPR", LP, LSL, LTP1, tp2)


def short_limit(sid=1, tp2=STP2):
    return Intent("PLACE_LIMIT", sid, -1, "BPR", SP_, SSL, STP1, tp2)


def run_sim(bars, script, params=XAU, sp=0.10, times=None, flat=None, days=None, cancel=None):
    n = len(bars)
    det = ScriptedDetector(script)
    res = simulate(
        bars,
        [sp] * n,
        times if times is not None else [T0 + 60 * i for i in range(n)],
        [True] * n,
        cancel if cancel is not None else [False] * n,
        flat if flat is not None else [False] * n,
        days if days is not None else [0] * n,
        params,
        detector=det,
    )
    return res, det


def test_r_accounting_playbook_worked_example():
    """Spec s.5 R accounting on the playbook example (tick 0.01, contract 100, 3.50 / side, slippage 1 tick):
    R_unit = 1.35 + 0.01 + 0.07 = 1.43. TP1 only: (3.25 - 0.07) / 1.43 = 3.18 / 1.43 = +2.2238R (playbook +2.22R);
    TP2 only: 5.33 / 1.43 = +3.7273R (+3.73R); 50/50: (1.625 + 2.70 - 0.07) / 1.43 = 4.255 / 1.43 = +2.9755R;
    50 % TP1 + 50 % at the break-even level 2650.62: (1.625 + 0.035 - 0.07) / 1.43 = 1.59 / 1.43 = +1.1119R;
    stop at SL - slippage 2649.19: (-1.36 - 0.07) / 1.43 = -1R exactly."""
    assert close(r_unit(LP, LSL, XAU), UNIT)
    assert close(trade_r(1, LP, [(1.0, LTP1, "TP1")], UNIT, 0.07), 3.18 / 1.43)
    assert round(3.18 / 1.43, 2) == 2.22 and round(5.33 / 1.43, 2) == 3.73
    assert close(trade_r(1, LP, [(1.0, LTP2, "TP2")], UNIT, 0.07), 5.33 / 1.43)
    assert close(trade_r(1, LP, [(0.5, LTP1, "TP1"), (0.5, LTP2, "TP2")], UNIT, 0.07), 4.255 / 1.43)
    assert close(trade_r(1, LP, [(0.5, LTP1, "TP1"), (0.5, 2650.62, "BE")], UNIT, 0.07), 1.59 / 1.43)
    assert close(trade_r(1, LP, [(1.0, 2649.19, "SL")], UNIT, 0.07), -1.0)
    assert close(trade_r(-1, SP_, [(1.0, STP1, "TP1")], UNIT, 0.07), 3.18 / 1.43)


def _one_trade(res):
    assert len(res.trades) == 1, res.trades
    return res.trades[0]


def test_sim_limit_fill_price_and_fill_bar_rules_long():
    """Spec s.5 (limit long): fills on the first bar k >= u+1 with ask_low <= P, at min(P, ask_open).
    (a) ask_open 2651.10 > P -> fill at P. (b) a gap: ask_open 2650.40 < P -> fill at 2650.40.
    (c) the fill bar also reaches TP1 (bid high 2653.80) -> cancelled instead (RUNAWAY_SAME_BAR), no trade.
    (d) the fill bar's bid low reaches SL -> loss on that bar at SL - slippage = 2649.19 -> -1R."""
    quiet = (2651.0, 2651.5, 2650.70, 2651.2)
    res, det = run_sim([DECIDE, (2651.0, 2651.2, 2650.40, 2650.8), quiet], {0: [long_limit()]})
    t = _one_trade(res)
    assert (t["fill_bar"], t["fill_price"], t["decision_bar"], t["exit_reason"]) == (1, LP, 0, "END")
    assert det.calls.index(("filled", 1)) < det.calls.index(("bar", 1, False, True, 0.10))
    res, _ = run_sim([DECIDE, (2650.30, 2650.6, 2650.2, 2650.5), quiet], {0: [long_limit()]})
    assert close(_one_trade(res)["fill_price"], 2650.40)
    res, det = run_sim([DECIDE, (2651.0, 2653.80, 2650.40, 2653.0), quiet], {0: [long_limit()]})
    assert res.trades == [] and ("cancelled", 1, "RUNAWAY_SAME_BAR", 1) in det.calls
    assert res.counters["runaway_same_bar"] == 1 and res.counters["fills"] == 0
    res, _ = run_sim([DECIDE, (2651.0, 2651.2, 2649.20, 2649.5), quiet], {0: [long_limit()]})
    t = _one_trade(res)
    assert (t["fill_bar"], t["exit_bar"], t["exit_reason"]) == (1, 1, "SL")
    assert close(t["parts"][0][1], 2649.19) and close(t["R"], -1.0)


def test_sim_stop_first_tp1_partial_be_next_bar_and_tp2_long():
    """Spec s.5 exits (long): stop first when stop and TP1 are touched on one bar; TP1 partial (50 %) then
    break-even (entry + comm = 2650.62) only from the next bar; TP1 and TP2 on the same bar."""
    fill = (2651.0, 2651.2, 2650.40, 2650.8)
    res, _ = run_sim([DECIDE, fill, (2651.0, 2654.0, 2649.0, 2651.0)], {0: [long_limit()]})
    t = _one_trade(res)
    assert (t["exit_bar"], t["exit_reason"], len(t["parts"])) == (2, "SL", 1) and close(t["R"], -1.0)
    # TP1 on bar 2 whose low 2650.50 is under the BE level (BE not active yet); bar 3 low 2650.62 hits BE
    res, _ = run_sim([DECIDE, fill, (2651.0, 2653.80, 2650.50, 2652.0), (2652.0, 2652.5, 2650.62, 2651.0)],
                     {0: [long_limit()]})
    t = _one_trade(res)
    assert [(f, r) for f, _, r in t["parts"]] == [(0.5, "TP1"), (0.5, "BE")]
    assert close(t["parts"][1][1], 2650.61) and t["exit_bar"] == 3
    assert close(t["R"], (0.5 * 3.25 + 0.5 * 0.06 - 0.07) / 1.43)  # = 1.585 / 1.43 = +1.1084R
    res, _ = run_sim([DECIDE, fill, (2651.0, 2656.0, 2650.6, 2655.0)], {0: [long_limit()]})
    t = _one_trade(res)
    assert [r for _, _, r in t["parts"]] == ["TP1", "TP2"] and close(t["R"], 4.255 / 1.43)
    no_be = StrategyParams(break_even=False)
    res, _ = run_sim([DECIDE, fill, (2651.0, 2653.80, 2650.50, 2652.0), (2652.0, 2652.5, 2650.0, 2651.0)],
                     {0: [long_limit()]}, params=no_be)
    assert _one_trade(res)["exit_reason"] == "END"  # no BE: the original stop 2649.20 is not hit


def test_sim_tp_modes():
    """Spec s.5 / s.4 step 5: TP2 equal to TP1 (or None, or TP1_ONLY) -> everything at TP1 (+2.2238R); TP2_ONLY ->
    everything at TP2 (+3.7273R)."""
    fill = (2651.0, 2651.2, 2650.40, 2650.8)
    big = (2651.0, 2656.0, 2650.6, 2655.0)
    for tp2 in (None, LTP1):  # TP2 equal to TP1 (TP2 not beyond TP1) means TP1 only
        res, _ = run_sim([DECIDE, fill, big], {0: [long_limit(tp2=tp2)]})
        t = _one_trade(res)
        assert t["parts"] == [(1.0, LTP1, "TP1")] and close(t["R"], 3.18 / 1.43)
    res, _ = run_sim([DECIDE, fill, big], {0: [long_limit()]}, params=StrategyParams(tp_mode="TP1_ONLY"))
    assert _one_trade(res)["parts"] == [(1.0, LTP1, "TP1")]
    res, _ = run_sim([DECIDE, fill, big], {0: [long_limit()]}, params=StrategyParams(tp_mode="TP2_ONLY"))
    t = _one_trade(res)
    assert t["parts"] == [(1.0, LTP2, "TP2")] and close(t["R"], 5.33 / 1.43)


def test_sim_time_stop_and_flat_now():
    """Spec s.5: time stop at the bid open of the first bar whose open >= fill_time + max_hold_min, minus slippage
    (max_hold 3 min, fill bar 1 -> bar 4 open 2651.30 -> exit 2651.29, R = (0.74 - 0.07) / 1.43); with a weekend
    gap in the times the exit is the first bar after it; flat_now forces an exit at that bar's open."""
    fill = (2651.0, 2651.2, 2650.40, 2650.8)
    mid = (2650.8, 2651.5, 2650.6, 2651.0)
    bars = [DECIDE, fill, mid, mid, (2651.30, 2651.5, 2651.0, 2651.2), mid]
    p3 = StrategyParams(max_hold_min=3)
    res, _ = run_sim(bars, {0: [long_limit()]}, params=p3)
    t = _one_trade(res)
    assert (t["exit_bar"], t["exit_reason"]) == (4, "TIME") and close(t["parts"][0][1], 2651.29)
    assert close(t["R"], 0.67 / 1.43)
    times = [T0, T0 + 60, T0 + 120, T0 + 3 * 86400, T0 + 3 * 86400 + 60, T0 + 3 * 86400 + 120]
    res, _ = run_sim(bars, {0: [long_limit()]}, params=p3, times=times)
    assert (_one_trade(res)["exit_bar"], _one_trade(res)["exit_reason"]) == (3, "TIME")
    res, _ = run_sim(bars, {0: [long_limit()]}, flat=[False, False, True, False, False, False])
    t = _one_trade(res)
    assert (t["exit_bar"], t["exit_reason"]) == (2, "FLAT") and close(t["parts"][0][1], 2650.79)


def test_sim_market_fill_long_and_short():
    """Spec s.5: market fill at ask_open[u+1] + slippage (long) / bid_open[u+1] - slippage (short); R_unit uses the
    planned P. Long: fill 2650.60 + 0.10 + 0.01 = 2650.71, TP1 on the fill bar, TP2 on the next ->
    R = (0.5 * 3.09 + 0.5 * 5.24 - 0.07) / 1.43. Short: fill 2653.90 - 0.01 = 2653.89, stop on the ask on the
    fill bar (ask high 2655.20 >= 2655.15) -> exit 2655.16, R = (2653.89 - 2655.16 - 0.07) / 1.43."""
    mk = Intent("MARKET", 1, 1, "BPR", LP, LSL, LTP1, LTP2)
    res, det = run_sim([DECIDE, (2650.60, 2653.90, 2650.50, 2653.0), (2653.0, 2656.0, 2652.0, 2655.0)], {0: [mk]})
    t = _one_trade(res)
    assert (t["fill_bar"], t["exit_bar"]) == (1, 2) and close(t["fill_price"], 2650.71)
    assert close(t["R_unit"], UNIT) and close(t["R"], (0.5 * 3.09 + 0.5 * 5.24 - 0.07) / 1.43)
    mk = Intent("MARKET", 1, -1, "BPR", SP_, SSL, STP1, STP2)
    res, _ = run_sim([DECIDE, (2653.90, 2655.10, 2653.0, 2654.0)], {0: [mk]})
    t = _one_trade(res)
    assert close(t["fill_price"], 2653.89) and t["exit_reason"] == "SL" and t["exit_bar"] == 1
    assert close(t["R"], (2653.89 - 2655.16 - 0.07) / 1.43)


def test_sim_shorts_mirrored():
    """Spec s.5 (shorts mirror longs): a sell limit fills when bid_high >= P at max(P, bid_open); stop and targets
    are ask levels (ask = bid + 0.10). Gap fill 2654.00; same-bar runaway (ask low 2650.50 <= TP1); same-bar stop
    at SL + slippage 2655.16 (-1R); TP1 + TP2 (+2.9755R); TP1 then break-even 2653.73 from the next bar -> exit
    2653.74 (+1.1084R)."""
    fill = (2653.0, 2653.9, 2652.8, 2653.5)
    res, _ = run_sim([DECIDE, fill], {0: [short_limit()]})
    assert close(_one_trade(res)["fill_price"], SP_)
    res, _ = run_sim([DECIDE, (2654.0, 2654.2, 2653.9, 2654.1)], {0: [short_limit()]})
    assert close(_one_trade(res)["fill_price"], 2654.0)
    res, det = run_sim([DECIDE, (2653.0, 2653.9, 2650.40, 2651.0)], {0: [short_limit()]})
    assert res.trades == [] and ("cancelled", 1, "RUNAWAY_SAME_BAR", 1) in det.calls
    res, _ = run_sim([DECIDE, (2653.0, 2655.10, 2652.8, 2655.0)], {0: [short_limit()]})
    t = _one_trade(res)
    assert t["exit_reason"] == "SL" and close(t["parts"][0][1], 2655.16) and close(t["R"], -1.0)
    res, _ = run_sim([DECIDE, fill, (2652.0, 2652.5, 2648.20, 2649.0)], {0: [short_limit()]})
    assert close(_one_trade(res)["R"], 4.255 / 1.43)
    res, _ = run_sim([DECIDE, fill, (2653.0, 2653.70, 2650.40, 2651.0), (2652.0, 2653.70, 2651.5, 2653.0)],
                     {0: [short_limit()]})
    t = _one_trade(res)
    assert [r for _, _, r in t["parts"]] == ["TP1", "BE"] and t["exit_bar"] == 3
    assert close(t["parts"][1][1], 2653.74) and close(t["R"], 1.585 / 1.43)


def test_sim_daily_lockout():
    """Spec s.5 / CLAUDE.md: 1 % / 0.2 % = 5R per FX day. Every bar loses exactly 1R (fill and stop on the next bar);
    after 5 losses on day 1 no order is decided until day 2 (bars 10..14) starts."""
    loser = (2651.0, 2651.2, 2649.0, 2650.0)
    bars = [loser] * 15
    res, _ = run_sim(bars, lambda u: [long_limit(sid=u + 1)], days=[1] * 10 + [2] * 5)
    assert [t["fill_bar"] for t in res.trades] == [1, 2, 3, 4, 5, 10, 11, 12, 13, 14]
    assert all(close(t["R"], -1.0) for t in res.trades)
    assert res.counters["locked_days"] == 1 and close(res.counters["total_R"], -10.0)


def test_sim_pending_order_cancel_and_one_position_rule():
    """Spec s.5: a CANCEL intent removes the pending limit; the slot is free again only after the cancel."""
    script = {0: [long_limit(sid=1)], 1: [Intent("CANCEL", 1, 1, "BPR", reason="EXPIRED")], 2: [long_limit(sid=2)]}
    quiet = (2652.0, 2652.5, 2651.5, 2652.0)
    res, det = run_sim([DECIDE, quiet, quiet, (2651.0, 2651.2, 2650.40, 2650.8)], script)
    assert [c for c in det.calls if c[0] == "bar"][1][2] is False  # bar 1: slot taken by the pending order
    assert [c for c in det.calls if c[0] == "bar"][2][2] is True
    t = _one_trade(res)
    assert (t["id"], t["fill_bar"], t["exit_reason"]) == (2, 3, "END")
    assert res.counters["cancels"] == 1 and res.counters["orders_limit"] == 2


def test_sim_end_to_end_with_the_detector():
    """Spec s.4 + s.5 end to end: the BASE long is ordered at bar 12 (P 100.15, SL 98.8, TP1 103.8, TP2 106.65);
    bar 13 fills it (ask low 100.10 <= P, at P since ask open 103.60 > P); bar 14 reaches TP1 and TP2.
    R_unit = 1.35 + 0.01 + 0.07 = 1.43; R = (0.5 * 3.65 + 0.5 * 6.5 - 0.07) / 1.43 = 5.005 / 1.43 = +3.5R.
    A fill bar that also reaches TP1 makes the setup DONE(RUNAWAY_SAME_BAR) instead."""
    bars = BASE + [(103.5, 103.6, 100.0, 100.2), (100.2, 107.0, 100.1, 106.8)]
    n = len(bars)
    common = ([SP] * n, [T0 + 60 * i for i in range(n)], [True] * n, [False] * n, [False] * n, [0] * n, PS)
    det = long_det()
    res = simulate(bars, *common, detector=det)
    t = _one_trade(res)
    assert (t["id"], t["src"], t["dir"], t["decision_bar"], t["fill_bar"], t["exit_bar"]) == (1, "BPR", 1, 12, 13, 14)
    assert close(t["fill_price"], 100.15) and close(t["R"], 3.5)
    assert res.setups[0]["status"] == "CLOSED" and res.setups[0]["end_bar"] == 14
    assert res.counters["setup_status"] == {"CLOSED": 1}
    bars = BASE + [(103.5, 103.9, 100.0, 100.2), (100.2, 101.0, 100.1, 100.8)]
    det = long_det()
    res = simulate(bars, *common, detector=det)
    assert res.trades == [] and res.setups[0]["reason"] == "RUNAWAY_SAME_BAR"
    assert brief(det)[-1] == (13, 1, "DONE", "RUNAWAY_SAME_BAR")


def test_sim_causality_truncation():
    """CLAUDE.md no look-ahead: trades that end before bar k are identical when the data is cut after bar k."""
    params = StrategyParams(source="BOTH", max_cost_r=1.0, use_session=False)
    bars = _random_bars(11, 1200)
    n = len(bars)

    def run(m):
        return simulate(bars[:m], [SP] * m, [T0 + 60 * i for i in range(m)], [True] * m, [False] * m,
                        [False] * m, [i // 120 for i in range(m)], params).trades

    full = run(n)
    assert len(full) > 10
    for k in (150, 333, 600, 901, 1100):
        assert [t for t in run(k + 1) if t["exit_bar"] < k] == [t for t in full if t["exit_bar"] < k]
