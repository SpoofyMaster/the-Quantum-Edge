"""Tests of the pure-Python FVG / BPR reference port (qe/indicators/luxalgo_bpr.py) and of the MT5 parity tool.

Licence and attribution: (c) LuxAlgo (original Pine v5 logic of 'ICT Concepts [LuxAlgo]'), licensed CC BY-NC-SA 4.0
(https://creativecommons.org/licenses/by-nc-sa/4.0/). These tests check a port (a derivative work) of that logic, for
non-commercial research use; the changes made by the ports are listed in research/indicators/LUXALGO_BPR_SPEC.md
section 10.

Every scenario below is hand-built with exact (binary-representable) prices, and the expected box coordinates were
derived by hand from the Pine source (research/indicators/luxalgo_ict_concepts.pine) and the spec
(research/indicators/LUXALGO_BPR_SPEC.md). Line numbers in docstrings refer to the Pine file.

No conftest fixtures are used, so the file runs on its own:
    cd /home/user/the-Quantum-Edge && PYTHONPATH=. pytest --noconftest -q tests/test_luxalgo_bpr.py
"""
from __future__ import annotations

import ast
import importlib.util
import random
import subprocess
import sys
from pathlib import Path

import pytest

from qe.indicators import luxalgo_bpr as lb
from qe.indicators.luxalgo_bpr import Box, BprParams, LuxBprEngine, Zone, fib_bpr, live_view, per_start_for, run

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "luxbpr_parity.py"


def _load_tool():
    spec = importlib.util.spec_from_file_location("luxbpr_parity", TOOL)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod  # dataclasses need the module registered while it executes
    spec.loader.exec_module(mod)
    return mod


parity = _load_tool()

# --------------------------------------------------------------------------------------------- helpers
HIST = BprParams(mode="Historical")  # BPR on (port default), FVG mode, vis_boxes 2
HIST_NOBPR = BprParams(mode="Historical", bpr=False)
HIST_IFVG = BprParams(mode="Historical", fvg_mode="IFVG")
HIST_IFVG_NOBPR = BprParams(mode="Historical", fvg_mode="IFVG", bpr=False)


def F(p: float) -> tuple[float, float, float, float]:
    """Filler bar (o, h, l, c): body 0.5, wicks 0.5 and 1.0, so never a displacement candle."""
    return (p, p + 1, p - 1, p + 0.5)


def geom(z: Zone):
    """(left, top, right, bottom) of a zone, or None for box(na)."""
    return None if z.box is None else (z.box.left, z.box.top, z.box.right, z.box.bottom)


def zstate(z: Zone):
    b = z.box
    return (None if b is None else (b.left, b.top, b.right, b.bottom, b.border, b.broken_fill), z.active, z.pos)


def snap(e: LuxBprEngine):
    """Full comparable state of an engine."""
    return (
        tuple(zstate(z) for z in e.fvg_up),
        tuple(zstate(z) for z in e.fvg_dn),
        tuple(zstate(z) for z in e.bpr_up),
        tuple(zstate(z) for z in e.bpr_dn),
        tuple(e.events),
        e.last_index,
        e.disp_up,
        e.disp_dn,
    )


def zones_snap(e: LuxBprEngine):
    return snap(e)[:4]


def feed(e: LuxBprEngine, bars, start: int | None = None) -> LuxBprEngine:
    n = (0 if e.last_index is None else e.last_index + 1) if start is None else start
    for i, b in enumerate(bars):
        e.process_bar(n + i, *b)
    return e


def _random_bars(seed: int, n: int, start: float = 100.0):
    """Deterministic random series with frequent displacement candles (so FVGs and BPRs occur often)."""
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
        out.append((round(o, 5), round(h, 5), round(lo, 5), round(cl, 5)))
        c = cl
    return out


# --------------------------------------------------------------------------------------------- scenarios
# Bullish FVG at bar 7: bar 5 high 101, bar 6 displacement up (body 4, wicks 0.5), bar 7 low 103 > 101.
BULL_FVG = [F(100)] * 6 + [(101, 105.5, 100.5, 105), (105, 106, 103, 105.5)]
# Bullish IFVG at bar 7: bar 5 high 104, bar 6 displacement, bar 7 low 103.5 < 104.
BULL_IFVG = [F(100)] * 5 + [(100, 104, 99, 100.5), (101, 105.5, 100.5, 105), (105, 110.5, 103.5, 110)]
# Two consecutive bullish imbalances (bars 7 and 8): bars 6 and 7 are both displacement candles.
BULL_CONSEC = [F(100)] * 6 + [(101, 105.5, 100.5, 105), (105, 110.5, 104.5, 110), (110, 111, 108, 110.5)]
# IFVG chain: imbalances at bars 7, 8, 9 (bars 6, 7, 8 are displacement candles), then a quiet bar 10.
IFVG_CHAIN = [F(100)] * 5 + [
    (100, 104, 99, 100.5),
    (101, 105.5, 100.5, 105),
    (105, 110.5, 103.5, 110),
    (106, 112.5, 105, 112),
    (112, 113, 110, 112.5),
    (112, 113, 111, 112.5),
]
# Bearish FVG at bar 7: bar 5 low 110, bar 6 displacement down (body 6, wicks 0.25), bar 7 high 106 < 110.
BEAR_FVG = [F(110)] * 5 + [(110.5, 111, 110, 111), (110, 110.25, 103.75, 104), (104, 106, 103, 104.5)]
# Bearish IFVG at bar 7: bar 7 high 112 > bar 5 low 110.
BEAR_IFVG = [F(110)] * 5 + [(110.5, 111, 110, 111), (110, 110.25, 103.75, 104), (104, 112, 103.5, 104.25)]
# Two consecutive bearish imbalances (bars 7 and 8).
BEAR_CONSEC = [F(110)] * 5 + [
    (110.5, 111, 110, 111),
    (110, 110.25, 103.75, 104),
    (104, 104.25, 98.75, 99),
    (99, 100, 98, 99.5),
]
# Scenario A: bearish FVG (bar 7) then bullish FVG (bar 10) whose bottom lies inside it -> BPR_UP pos 1 (QUIRK 4);
# bar 13: a second bullish FVG with the same older bearish FVG -> same BPR (QUIRK 6);
# bar 16: a new bearish FVG replaces the older one -> new BPR_UP, pos -1, built from a broken bullish FVG (QUIRK 9).
SC_A = BEAR_FVG + [
    (104.5, 107, 104, 105),  # 8: high 107 = future bullish bottom
    (106.5, 109.75, 106.25, 109.5),  # 9: displacement up (body 3)
    (109.5, 109.75, 108, 109),  # 10: low 108 > 107 -> FVG_UP and BPR_UP
    (108.25, 108.5, 108, 108.4),  # 11: high 108.5
    (108.5, 111.75, 108.25, 111.5),  # 12: displacement up, breaks the bearish FVG (high > 110)
    (111.5, 112, 109, 111.75),  # 13: low 109 > 108.5 -> second FVG_UP, same BPR left
    (111.75, 112, 111.5, 111.6),  # 14: low 111.5
    (111.5, 111.75, 107.75, 108),  # 15: displacement down, breaks FVG_UP #2 (low < 108.5)
    (108, 108.25, 107.5, 107.75),  # 16: high 108.25 < 111.5 -> FVG_DN #2 and new BPR_UP
]
# Scenario B: bullish FVG (bar 7), broken at bar 9, bearish FVG (bar 10) -> BPR_UP pos -1; dashed 11, broken 12.
SC_B = BULL_FVG + [
    (105, 106, 102, 104.5),
    (104, 104.25, 98.75, 99),
    (99, 100, 98, 98.5),
    (98.5, 101.5, 98, 99),
    (99, 102.5, 98.5, 102),
]
# Scenario C1: bullish FVG then bearish FVG whose bottom lies inside it -> BPR_DN pos -1; dashed 11, broken 12.
SC_C1 = BULL_FVG + [
    (105, 106, 104.5, 105.5),
    (105, 105.25, 101.75, 102),
    (102, 102.5, 101.5, 101.75),
    (101.75, 102.75, 101.5, 102),
    (102, 103.5, 101.5, 103),
]
# Scenario C2: bearish FVG then bullish FVG around its bottom -> BPR_DN pos 1; dashed 11, broken 12.
SC_C2 = BEAR_FVG + [
    (104.5, 105, 104, 104.75),
    (105, 108.25, 104.75, 108),
    (108, 108.5, 107, 108.25),
    (108.25, 108.5, 106.5, 107),
    (107, 107.5, 105.5, 106),
]
# IFVG mode: bearish IFVG [110, 112] (bar 7), displacement up (bar 8), bullish IFVG on bar 9.
SC_I1 = BEAR_IFVG + [(104.25, 111, 104, 110.75), (110.75, 111.5, 109.5, 111)]  # BPR_DN pos 1, broken same bar
SC_I2 = BEAR_IFVG + [(104.25, 111, 104, 110.75), (112.5, 113, 111, 111)]  # BPR_UP pos -1, broken same bar


# ============================================================================================= displacement
def _disp_after(bars, params=HIST):
    e = run(bars, params)
    return e.disp_up, e.disp_dn


WARM = [(100, 100.5, 99.5, 100.25)] * 4  # bodies 0.25, never displacement


def test_wick_exactly_36pct_is_not_displacement():
    """Pine 548-553: L_body uses strict '<' against body*perc_Body (0.36). Body 100 -> limit 36.0 exactly."""
    assert 100 * 0.36 == 36.0
    assert _disp_after(WARM + [(1000, 1136, 1000, 1100)]) == (False, False)  # upper wick 36 == limit
    assert _disp_after(WARM + [(1000, 1135.5, 1000, 1100)]) == (True, False)  # upper wick 35.5
    assert _disp_after(WARM + [(1000, 1100, 964, 1100)]) == (False, False)  # lower wick 36
    assert _disp_after(WARM + [(1000, 1100, 964.5, 1100)]) == (True, False)  # lower wick 35.5
    assert _disp_after(WARM + [(1100, 1136, 1000, 1000)]) == (False, False)  # bearish, upper wick 36
    assert _disp_after(WARM + [(1100, 1135.5, 1000, 1000)]) == (False, True)
    assert _disp_after(WARM + [(1100, 1100, 964, 1000)]) == (False, False)  # bearish, lower wick 36


def test_doji_is_never_displacement():
    """Pine 548-553: body = 0 gives 'x < 0' (false) for both wicks, and neither close > open nor close < open."""
    assert _disp_after(WARM + [(100, 100, 100, 100)]) == (False, False)
    assert _disp_after(WARM + [(100, 101, 99, 100)]) == (False, False)


def test_mean_body_na_during_warmup_and_length_param():
    """Pine 130 (meanBody = sma(body, len)) and 552-553: L_bodyUP is false while meanBody is na (first len-1 bars)."""
    perfect = [(100, 101, 100, 101)] * 4  # body 1, no wicks: a displacement shape
    e = LuxBprEngine(HIST)  # length 5
    for i, b in enumerate(perfect):
        e.process_bar(i, *b)
        assert (e.disp_up, e.disp_dn) == (False, False), f"bar {i}: meanBody must be na"
    e.process_bar(4, 100, 102, 100, 102)  # body 2 > mean (1+1+1+1+2)/5 = 1.2
    assert e.disp_up is True
    # a huge body on bar 3 is still not a displacement with length 5 (na), but it is with length 3
    big = [(100, 101, 100, 101)] * 3 + [(100, 110, 100, 110)]
    assert _disp_after(big, BprParams(mode="Historical", length=5)) == (False, False)
    assert _disp_after(big, BprParams(mode="Historical", length=3)) == (True, False)  # mean (1+1+10)/3 = 4
    e3 = LuxBprEngine(BprParams(mode="Historical", length=3))
    feed(e3, [(100, 101, 100, 101)] * 2)
    assert e3.disp_up is False  # bar 1: only 2 bodies
    feed(e3, [(100, 102, 100, 102)])
    assert e3.disp_up is True  # bar 2: mean (1+1+2)/3


def test_body_equal_to_mean_is_not_displacement():
    """Pine 552: 'body > meanBody' is strict; five identical bodies give body == meanBody."""
    assert _disp_after([(100, 102, 100, 102)] * 5) == (False, False)
    assert _disp_after([(102, 102, 100, 100)] * 5) == (False, False)


def test_history_before_first_processed_bar_is_na():
    """Pine semantics: values before the first bar are na. Starting at bar 3, bar 6 has only 4 bodies -> no
    displacement -> no FVG; the same bars from bar 0 create one. Bar indices may start anywhere."""
    e = LuxBprEngine(HIST_NOBPR)
    feed(e, BULL_FVG[3:], start=3)
    assert all(z.box is None for z in e.fvg_up) and e.events == []
    e2 = run(BULL_FVG, HIST_NOBPR, first_index=1000)
    assert geom(e2.fvg_up[0]) == (1005, 103, 1015, 101)
    assert e2.events == [(1007, "FVG_UP", "new")]


# ============================================================================================= FVG creation
def test_bullish_fvg_creation_fvg_mode():
    """Pine 565 + 610-624: box(left n-2, top low, right n, bottom high[2]); the break loop (700-703) then sets
    right = n+8 on the creation bar. active = true, pos = na."""
    e = run(BULL_FVG, HIST_NOBPR)
    z = e.fvg_up[0]
    assert geom(z) == (5, 103, 15, 101)
    assert (z.active, z.pos, z.box.border, z.box.broken_fill) == (True, None, "solid", False)
    assert e.fvg_up[1].box is None and all(x.box is None for x in e.fvg_dn)
    assert e.events == [(7, "FVG_UP", "new")]
    feed(e, [F(104)])  # low 103 is not < top 103: no dashed border
    assert geom(e.fvg_up[0]) == (5, 103, 16, 101) and e.fvg_up[0].box.border == "solid"


def test_bullish_fvg_creation_ifvg_mode():
    """Pine 565 (IFVG: low < high[2]) + 610-624: top = high[2], bottom = low. The creation bar's low is below the
    top, so the border turns dashed at once when BPR is off (704-705). The same bars make no FVG in FVG mode."""
    e = run(BULL_IFVG, HIST_IFVG_NOBPR)
    z = e.fvg_up[0]
    assert geom(z) == (5, 104, 15, 103.5)
    assert (z.active, z.box.border, z.box.broken_fill) == (True, "dashed", False)
    assert run(BULL_IFVG, HIST_NOBPR).events == []
    assert run(BULL_IFVG, HIST_IFVG).fvg_up[0].box.border == "solid"  # BPR on: FVG style never changes


def test_bearish_fvg_creation_fvg_and_ifvg_mode():
    """Pine 566 + 630-644: FVG mode top = low[2], bottom = high; IFVG mode top = high, bottom = low[2]."""
    e = run(BEAR_FVG, HIST_NOBPR)
    assert geom(e.fvg_dn[0]) == (5, 110, 15, 106)
    assert (e.fvg_dn[0].active, e.fvg_dn[0].pos) == (True, None)
    assert e.events == [(7, "FVG_DN", "new")]
    ei = run(BEAR_IFVG, HIST_IFVG_NOBPR)
    assert geom(ei.fvg_dn[0]) == (5, 112, 15, 110)
    assert ei.fvg_dn[0].box.border == "dashed"  # high 112 > bottom 110 (Pine 717-718)
    assert ei.fvg_dn[0].active is True
    assert run(BEAR_IFVG, HIST_NOBPR).events == []


# ============================================================================================= FVG update
def test_consecutive_bullish_update_fvg_mode():
    """Pine 607-609: imbalanceUP and imbalanceUP[1] -> set_lefttop(n-2, low), set_rightbottom(n+8, high[2]) on
    FVG_UP[0]; no new entry."""
    e = run(BULL_CONSEC[:8], HIST_NOBPR)
    assert geom(e.fvg_up[0]) == (5, 104.5, 15, 101)
    feed(e, BULL_CONSEC[8:])
    assert geom(e.fvg_up[0]) == (6, 108, 16, 105.5)
    assert e.fvg_up[0].active is True and e.fvg_up[1].box is None
    assert e.events == [(7, "FVG_UP", "new"), (8, "FVG_UP", "update")]


def test_consecutive_bearish_update_fvg_mode():
    """Pine 627-629: set_lefttop(n-2, low[2]), set_rightbottom(n+8, high) on FVG_DN[0]."""
    e = run(BEAR_CONSEC[:8], HIST_NOBPR)
    assert geom(e.fvg_dn[0]) == (5, 110, 15, 104.25)
    feed(e, BEAR_CONSEC[8:])
    assert geom(e.fvg_dn[0]) == (6, 103.75, 16, 100)
    assert e.events == [(7, "FVG_DN", "new"), (8, "FVG_DN", "update")]


def test_ifvg_update_uses_fvg_geometry_quirk1_and_keeps_inactive_quirk2():
    """QUIRK 1: the consecutive update (Pine 608-609) uses FVG geometry in IFVG mode -> top < bottom, and the bar's
    low is then below the bottom so the box breaks at once (706-711). QUIRK 2: a later update moves the broken box
    (right = n+8) but leaves it inactive, so it stays frozen."""
    e = LuxBprEngine(HIST_IFVG_NOBPR)
    feed(e, IFVG_CHAIN[:8])
    assert geom(e.fvg_up[0]) == (5, 104, 15, 103.5) and e.fvg_up[0].active
    feed(e, IFVG_CHAIN[8:9])  # bar 8
    z = e.fvg_up[0]
    assert geom(z) == (6, 105, 8, 105.5)  # top 105 < bottom 105.5, right = n (broken)
    assert z.box.top < z.box.bottom
    assert (z.active, z.box.border, z.box.broken_fill) == (False, "dotted", True)
    feed(e, IFVG_CHAIN[9:10])  # bar 9: update of an inactive entry
    assert geom(e.fvg_up[0]) == (7, 110, 17, 110.5) and e.fvg_up[0].active is False
    feed(e, IFVG_CHAIN[10:])  # bar 10: no imbalance, the break loop skips the inactive entry
    assert geom(e.fvg_up[0]) == (7, 110, 17, 110.5)
    assert (e.fvg_up[0].box.border, e.fvg_up[0].box.broken_fill) == ("dotted", True)
    assert e.events == [
        (7, "FVG_UP", "new"),
        (8, "FVG_UP", "update"),
        (8, "FVG_UP", "broken"),
        (9, "FVG_UP", "update"),
    ]


def test_vis_boxes_pop_order():
    """Pine 606-624: unshift the new FVG at index 0 and pop (delete) the last one; the arrays keep visBxs entries."""

    def cycle(p):
        return [F(p), (p + 1, p + 5.25, p + 0.75, p + 5), (p + 5.5, p + 6.5, p + 2, p + 6)]

    bars = [F(100)] * 4 + cycle(100) + cycle(108) + cycle(116)  # FVGs with left 4, 7, 10
    e2 = run(bars, BprParams(mode="Historical", vis_boxes=2))
    assert [geom(z) for z in e2.fvg_up] == [(10, 118, 20, 117), (7, 110, 20, 109)]
    e3 = run(bars, BprParams(mode="Historical", vis_boxes=3))
    assert [z.box.left for z in e3.fvg_up] == [10, 7, 4]
    e1 = run(bars, BprParams(mode="Historical", vis_boxes=1))
    assert [geom(z) for z in e1.fvg_up] == [(10, 118, 20, 117)]
    assert len(e1.fvg_dn) == len(e1.bpr_up) == len(e1.bpr_dn) == 1


# ============================================================================================= FVG breaks
def test_fvg_up_break_without_and_with_bpr():
    """Pine 700-711: active entries get right = n+8; low < top -> dashed (BPR off only); low < bottom -> fill
    break colour + dotted (BPR off only), right = n, active = false. After the break, right stays frozen."""
    bars = BULL_FVG + [(105.5, 106, 102, 105), (105, 105.5, 100, 104.5), (104.5, 105, 99, 104)]
    e = run(bars[:9], HIST_NOBPR)  # bar 8: low 102 < top 103, > bottom 101
    z = e.fvg_up[0]
    assert geom(z) == (5, 103, 16, 101) and z.active and z.box.border == "dashed" and not z.box.broken_fill
    feed(e, bars[9:10])  # bar 9: low 100 < bottom 101
    assert geom(z) == (5, 103, 9, 101)
    assert (z.active, z.box.border, z.box.broken_fill) == (False, "dotted", True)
    assert e.events[-1] == (9, "FVG_UP", "broken")
    feed(e, bars[10:])
    assert geom(z) == (5, 103, 9, 101)
    eb = run(bars, HIST)  # BPR on: same geometry and state, style untouched
    zb = eb.fvg_up[0]
    assert geom(zb) == (5, 103, 9, 101)
    assert (zb.active, zb.box.border, zb.box.broken_fill) == (False, "solid", False)


def test_fvg_dn_break_without_and_with_bpr():
    """Pine 713-724: high > bottom -> dashed (BPR off only); high > top -> broken, right = n, inactive."""
    bars = BEAR_FVG + [(104.5, 107, 104, 105), (105, 111, 104.5, 105.5)]
    e = run(bars[:9], HIST_NOBPR)
    assert geom(e.fvg_dn[0]) == (5, 110, 16, 106) and e.fvg_dn[0].box.border == "dashed"
    feed(e, bars[9:])
    z = e.fvg_dn[0]
    assert geom(z) == (5, 110, 9, 106)
    assert (z.active, z.box.border, z.box.broken_fill) == (False, "dotted", True)
    zb = run(bars, HIST).fvg_dn[0]
    assert geom(zb) == (5, 110, 9, 106) and (zb.active, zb.box.border, zb.box.broken_fill) == (False, "solid", False)


# ============================================================================================= BPR creation
def test_bpr_up_creation_geometry_pos_plus1_quirk4_quirk10():
    """Pine 657-676: BPR_UP if up.bottom < dn.top and dn.bottom < up.bottom; box(left=min lefts, top=dn.top,
    bottom=up.bottom); pos = close > up.bottom ? 1 : ... QUIRK 4: up.top (108) < dn.top (110) and the box still
    reaches dn.top. QUIRK 10: the BPR appears on the bar the bullish FVG is created. The creation bar's low 108 is
    below the box top, so the BPR break loop (741-742) makes the border dashed at once."""
    e = run(SC_A[:11], HIST)
    assert geom(e.fvg_dn[0]) == (5, 110, 18, 106)
    assert geom(e.fvg_up[0]) == (8, 108, 18, 107)
    z = e.bpr_up[0]
    assert geom(z) == (5, 110, 18, 107)
    assert z.box.top > e.fvg_up[0].box.top  # QUIRK 4
    assert (z.active, z.pos, z.box.border, z.box.broken_fill) == (True, 1, "dashed", False)
    assert e.bpr_up[1].box is None and all(x.box is None for x in e.bpr_dn)
    assert e.events[-2:] == [(10, "FVG_UP", "new"), (10, "BPR_UP", "new")]


def test_bpr_up_pos_minus1_from_broken_fvg_quirk9_and_break():
    """Pine 657-676 with the bearish FVG newer: close 98.5 <= up.bottom -> pos -1 (QUIRK 5: never 0). QUIRK 9: the
    bullish FVG was broken on bar 9 and still makes the BPR. Pine 732-739: pos -1 -> high > bottom dashed (bar 11),
    high > top broken with right = n (bar 12); the BPR break loop runs after the FVG break loop."""
    e = run(SC_B[:11], HIST)
    assert geom(e.fvg_up[0]) == (5, 103, 9, 101) and e.fvg_up[0].active is False
    assert geom(e.fvg_dn[0]) == (8, 102, 18, 100)
    z = e.bpr_up[0]
    assert geom(z) == (5, 102, 18, 101)
    assert (z.active, z.pos, z.box.border) == (True, -1, "solid")
    feed(e, SC_B[11:12])  # high 101.5 > bottom 101, < top 102
    assert geom(z) == (5, 102, 19, 101) and z.active and z.box.border == "dashed" and not z.box.broken_fill
    feed(e, SC_B[12:])  # high 102.5 > top 102
    assert geom(z) == (5, 102, 12, 101)
    assert (z.active, z.box.border, z.box.broken_fill) == (False, "dotted", True)
    assert e.events[-2:] == [(12, "FVG_DN", "broken"), (12, "BPR_UP", "broken")]


def test_bpr_dn_creation_pos_minus1_and_break():
    """Pine 678-697: BPR_DN if dn.bottom < up.top and up.bottom < dn.bottom; box(top=up.top, bottom=dn.bottom);
    pos = close > dn.bottom ? 1 : close < up.top ? -1 : 0 -> -1 here. Break (Pine 754-761): high > top."""
    e = run(SC_C1[:11], HIST)
    assert geom(e.fvg_up[0]) == (5, 103, 18, 101) and geom(e.fvg_dn[0]) == (8, 104.5, 18, 102.5)
    z = e.bpr_dn[0]
    assert geom(z) == (5, 103, 18, 102.5)
    assert (z.active, z.pos, z.box.border) == (True, -1, "solid")
    assert all(x.box is None for x in e.bpr_up)  # the two conditions exclude each other
    feed(e, SC_C1[11:12])
    assert geom(z) == (5, 103, 19, 102.5) and z.box.border == "dashed"
    feed(e, SC_C1[12:])
    assert geom(z) == (5, 103, 12, 102.5) and (z.active, z.box.border, z.box.broken_fill) == (False, "dotted", True)
    assert e.events[-1] == (12, "BPR_DN", "broken")


def test_bpr_dn_creation_pos_plus1_and_break():
    """Pine 678-697 with the bullish FVG newer: close 108.25 > dn.bottom -> pos 1. Break (Pine 762-769): low < top
    dashed (bar 11), low < bottom broken (bar 12)."""
    e = run(SC_C2[:11], HIST)
    assert geom(e.fvg_dn[0]) == (5, 110, 18, 106) and geom(e.fvg_up[0]) == (8, 107, 18, 105)
    z = e.bpr_dn[0]
    assert geom(z) == (5, 107, 18, 106)
    assert (z.active, z.pos, z.box.border) == (True, 1, "solid")
    feed(e, SC_C2[11:12])
    assert geom(z) == (5, 107, 19, 106) and z.active and z.box.border == "dashed"
    feed(e, SC_C2[12:])
    assert geom(z) == (5, 107, 12, 106) and (z.active, z.box.border, z.box.broken_fill) == (False, "dotted", True)


def test_bpr_created_and_broken_on_the_same_bar_ifvg():
    """Spec section 6: the BPR break loop runs on the creation bar with that bar's own high/low.
    IFVG mode, bar 9: (a) BPR_DN pos 1 (close 111 > dn.bottom 110) with low 109.5 < bottom 110 -> broken at once;
    (b) BPR_UP pos -1 (close 111 == up.bottom) with high 113 > top 112 -> broken at once. Event order follows the
    Pine order: FVG creation, BPR block, FVG break loops, BPR break loops."""
    e1 = run(SC_I1, HIST_IFVG)
    assert geom(e1.fvg_dn[0]) == (5, 112, 17, 110) and geom(e1.fvg_up[0]) == (7, 112, 17, 109.5)
    z = e1.bpr_dn[0]
    assert geom(z) == (5, 112, 9, 110)
    assert (z.active, z.pos, z.box.border, z.box.broken_fill) == (False, 1, "dotted", True)
    assert e1.events[-3:] == [(9, "FVG_UP", "new"), (9, "BPR_DN", "new"), (9, "BPR_DN", "broken")]
    e2 = run(SC_I2, HIST_IFVG)
    z = e2.bpr_up[0]
    assert geom(z) == (5, 112, 9, 111)
    assert (z.active, z.pos, z.box.border, z.box.broken_fill) == (False, -1, "dotted", True)
    assert e2.events[-4:] == [
        (9, "FVG_UP", "new"),
        (9, "BPR_UP", "new"),
        (9, "FVG_DN", "broken"),
        (9, "BPR_UP", "broken"),
    ]


def test_bpr_identity_by_left_quirk6_and_new_bpr_when_older_fvg_replaced():
    """QUIRK 6 (Pine 659-661): a new bullish FVG on bar 13 with the same older bearish FVG gives the same left (5),
    so the existing BPR is kept with its OLD geometry and no new BPR is made, even though the bearish FVG is broken.
    Bar 16: a new bearish FVG replaces the older one, left becomes 11 -> new BPR_UP (pos -1), built from the broken
    bullish FVG #2 (QUIRK 9); the old BPR moves to index 1."""
    e = run(SC_A[:14], HIST)
    assert geom(e.fvg_up[0]) == (11, 109, 21, 108.5) and geom(e.fvg_up[1]) == (8, 108, 21, 107)
    assert geom(e.fvg_dn[0]) == (5, 110, 12, 106) and e.fvg_dn[0].active is False
    assert geom(e.bpr_up[0]) == (5, 110, 21, 107)  # old bottom 107 kept, not 108.5
    assert e.bpr_up[1].box is None
    assert [ev for ev in e.events if ev[1] == "BPR_UP"] == [(10, "BPR_UP", "new")]
    feed(e, SC_A[14:])
    assert geom(e.fvg_up[0]) == (11, 109, 15, 108.5) and e.fvg_up[0].active is False
    assert geom(e.fvg_dn[0]) == (14, 111.5, 24, 108.25) and geom(e.fvg_dn[1]) == (5, 110, 12, 106)
    new, old = e.bpr_up
    assert geom(new) == (11, 111.5, 24, 108.5) and (new.active, new.pos, new.box.border) == (True, -1, "solid")
    assert geom(old) == (5, 110, 24, 107) and (old.active, old.pos, old.box.border) == (True, 1, "dashed")
    assert e.events[-2:] == [(16, "FVG_DN", "new"), (16, "BPR_UP", "new")]
    assert all(x.box is None for x in e.bpr_dn)


def test_bpr_right_is_n_plus_8_while_active_quirk8():
    """QUIRK 8: the BPR block's set_right(max(rights)) is overwritten in the same bar by the BPR break loop
    (Pine 730), so an active BPR within 0..bxBack always has right = n+8 after the bar, and a broken one keeps n."""
    e = LuxBprEngine(HIST)
    for n, bar in enumerate(SC_A):
        e.process_bar(n, *bar)
        for z in e.bpr_up + e.bpr_dn:
            if z.active:
                assert z.box.right == n + 8
    # at bar 16 the BPR block computed right = max(up.right 15, dn.right 16) = 16, but the box shows 24
    assert e.bpr_up[0].box.right == 24
    e = LuxBprEngine(HIST)
    for n, bar in enumerate(SC_B):
        e.process_bar(n, *bar)
    assert e.bpr_up[0].box.right == 12 and e.bpr_up[0].active is False


def test_no_bpr_when_show_fvg_false_or_bpr_false():
    """Pine 606/626: shwFVG false -> no FVG is ever created, so no BPR (Pine 647-655 read na boxes). Pine 602-604 and
    647/726: i_BPR false -> the BPR arrays stay empty and nothing BPR-related runs; the FVGs are unchanged."""
    e = run(SC_A, BprParams(mode="Historical", show_fvg=False))
    assert all(z.box is None for z in e.fvg_up + e.fvg_dn + e.bpr_up + e.bpr_dn)
    assert len(e.bpr_up) == len(e.bpr_dn) == 2 and e.events == []
    e2 = run(SC_A, HIST_NOBPR)
    assert e2.bpr_up == [] and e2.bpr_dn == []
    assert not any(k.startswith("BPR") for _, k, _ in e2.events)
    e3 = run(SC_A, HIST)
    assert [geom(z) for z in e2.fvg_up + e2.fvg_dn] == [geom(z) for z in e3.fvg_up + e3.fvg_dn]
    assert [z.active for z in e2.fvg_up + e2.fvg_dn] == [z.active for z in e3.fvg_up + e3.fvg_dn]
    assert fib_bpr(e2) is None


# ============================================================================================= Present mode
def test_present_mode_gating():
    """Pine 122: per = last_bar_index - bar_index <= 500 gates FVG creation only. An imbalance before per_start
    creates nothing; the same imbalance at/after per_start does."""
    assert per_start_for(1000, BprParams()) == 500
    assert per_start_for(1000, BprParams(present_bars=10)) == 990
    assert per_start_for(1000, BprParams(mode="Historical")) is None
    p0 = BprParams(mode="Present", present_bars=0)
    e = run(BULL_FVG, p0)  # last_bar_index 7 -> per_start 7
    assert e.per_start == 7 and geom(e.fvg_up[0]) == (5, 103, 15, 101)
    e = run(BULL_FVG, p0, last_bar_index=8)  # per_start 8 > 7: outside the window
    assert e.per_start == 8 and all(z.box is None for z in e.fvg_up) and e.events == []
    assert run(BULL_FVG[:7], p0, last_bar_index=100).disp_up is True  # displacement itself is not gated
    e = run(BULL_FVG, BprParams(mode="Present", present_bars=1), last_bar_index=8)  # per_start 7
    assert geom(e.fvg_up[0]) == (5, 103, 15, 101)
    assert run(BULL_FVG).fvg_up[0].box is not None  # defaults: Present, 500 bars -> whole short series in window


def test_quirk3_update_lost_at_window_start():
    """QUIRK 3 (Pine 607-609): imbalance at bar 7 is before per_start = 8 (not created); bar 8 has imbalanceUP and
    imbalanceUP[1], so it tries to update FVG_UP[0], which is box(na): nothing happens and the gap is lost.
    A later non-consecutive imbalance inside the window is created normally."""
    e = LuxBprEngine(BprParams(mode="Present", bpr=False), per_start=8)
    feed(e, BULL_CONSEC)
    assert all(z.box is None for z in e.fvg_up) and e.events == []
    tail = [(110.5, 111, 110, 110.75), (111, 115.25, 110.75, 115), (115, 116, 113, 115.5)]
    feed(e, tail)  # bar 10 displacement, bar 11 low 113 > high[2] 111
    assert geom(e.fvg_up[0]) == (9, 113, 19, 111)
    assert e.events == [(11, "FVG_UP", "new")]
    e7 = LuxBprEngine(BprParams(mode="Present", bpr=False), per_start=7)
    feed(e7, BULL_CONSEC)
    assert e7.events == [(7, "FVG_UP", "new"), (8, "FVG_UP", "update")]


# ============================================================================================= bxBack
def test_bx_back_limit_with_more_than_11_boxes():
    """Pine 700/713 (bxBack = 10): the break loops only visit indices 0..min(10, size-1). With visBxs = 13 the
    entries at indices 11 and 12 keep their last right and are never broken."""

    def cycle(p):
        return [F(p), (p + 1, p + 5.25, p + 0.75, p + 5), (p + 5.5, p + 6.5, p + 2, p + 6)]

    bars = [F(100)] * 4
    for j in range(13):
        bars += cycle(100 + 8 * j)  # bullish FVG with left 4 + 3j, created on bar 6 + 3j
    e = run(bars, BprParams(mode="Historical", vis_boxes=13, bpr=False))
    assert e.last_index == 42
    assert [z.box.left for z in e.fvg_up] == [40 - 3 * i for i in range(13)]
    assert all(z.active for z in e.fvg_up)
    assert [z.box.right for z in e.fvg_up[:11]] == [50] * 11
    # left 7 moved to index 11 on bar 42 (last seen at index 10 on bar 41); left 4 on bar 39 (last seen bar 38)
    assert (e.fvg_up[11].box.right, e.fvg_up[12].box.right) == (49, 46)
    e.process_bar(43, 200, 201, 50, 60)  # low 50 is below every bottom
    assert [(z.active, z.box.right, z.box.border) for z in e.fvg_up[:11]] == [(False, 43, "dotted")] * 11
    assert [(z.active, z.box.right, z.box.border) for z in e.fvg_up[11:]] == [(True, 49, "solid"), (True, 46, "solid")]
    assert sum(1 for ev in e.events if ev == (43, "FVG_UP", "broken")) == 11


# ============================================================================================= causality etc.
@pytest.mark.parametrize("fvg_mode", ["FVG", "IFVG"])
def test_causality_truncation_invariance(fvg_mode):
    """No look-ahead: in Historical mode the state after bar k of a run on the full series equals the state of a
    run on bars[:k+1] only, and does not change when the bars after k are replaced by different ones."""
    params = BprParams(mode="Historical", fvg_mode=fvg_mode, vis_boxes=3)
    bars = _random_bars(7, 600)
    other = _random_bars(8, 600)
    full = LuxBprEngine(params)
    states = []
    for n, b in enumerate(bars):
        full.process_bar(n, *b)
        states.append(snap(full))
    ks = list(range(0, 600, 13)) + [599]
    for k in ks:
        assert snap(run(bars[: k + 1], params)) == states[k], f"k={k}"
    for k in ks[::4]:
        spliced = bars[: k + 1] + other[k + 1 :]
        e = LuxBprEngine(params)
        for n, b in enumerate(spliced):
            e.process_bar(n, *b)
            if n == k:
                assert snap(e) == states[k]
    assert any(ev[1].startswith("BPR") for ev in full.events)


def test_present_mode_truncation_invariance_with_fixed_window():
    """With the Present window fixed (per_start passed explicitly, as on TradingView after load), processing is
    still causal."""
    params = BprParams(mode="Present", present_bars=300)
    bars = _random_bars(11, 500)
    assert run(bars, params).per_start == 199
    full = LuxBprEngine(params, per_start=199)
    states = []
    for n, b in enumerate(bars):
        full.process_bar(n, *b)
        states.append(snap(full))
    assert not any(ev[0] < 199 for ev in full.events)  # nothing can happen before the window
    for k in (150, 198, 199, 200, 250, 400, 499):
        e = LuxBprEngine(params, per_start=199)
        feed(e, bars[: k + 1])
        assert snap(e) == states[k], f"k={k}"


def test_process_bar_requires_consecutive_indices_and_clone_is_independent():
    """Bars must arrive with consecutive bar_index values; clone() is a deep copy."""
    e = run(SC_A[:11], HIST)
    with pytest.raises(ValueError):
        e.process_bar(12, 1, 2, 0, 1)
    with pytest.raises(ValueError):
        e.process_bar(10, 1, 2, 0, 1)
    before = snap(e)
    c = e.clone()
    assert snap(c) == before
    c.bpr_up[0].box.top = -1.0
    c.fvg_up[0].active = False
    c.events.append((99, "BPR_UP", "new"))
    feed(c, SC_A[11:])
    assert snap(e) == before


def test_live_view_leaves_engine_unchanged_and_final_view_equals_commit():
    """Spec section 7 (HYPOTHESIS on Pine's realtime rollback): every tick re-runs the forming bar from the committed
    state. The BPR can appear and disappear while bar 10 forms; the committed engine never changes; a view with the
    final bar values equals committing that bar."""
    e = run(SC_A[:10], HIST)
    committed = snap(e)
    v1 = live_view(e, 10, (109.5, 109.6, 107.5, 109))  # low 107.5 > 107: FVG_UP and BPR_UP appear
    assert geom(v1.fvg_up[0]) == (8, 107.5, 18, 107) and geom(v1.bpr_up[0]) == (5, 110, 18, 107)
    assert snap(e) == committed
    v2 = live_view(e, 10, (109.5, 109.6, 106.9, 107))  # low 106.9 < 107: no gap, the BPR disappears
    assert v2.fvg_up[0].box is None and v2.bpr_up[0].box is None
    assert snap(e) == committed
    final = SC_A[10]
    v3 = live_view(e, 10, final)
    assert snap(e) == committed
    e.process_bar(10, *final)
    assert snap(v3) == snap(e)
    # random series: the final live view always equals the commit
    bars = _random_bars(3, 300)
    eng = LuxBprEngine(BprParams(mode="Historical", vis_boxes=3))
    for n, b in enumerate(bars):
        before = snap(eng)
        o, h, lo, c = b
        live_view(eng, n, (o, o, o, o))
        live_view(eng, n, (o, h, o, (o + h) / 2))
        view = live_view(eng, n, b)
        assert snap(eng) == before
        eng.process_bar(n, *b)
        assert snap(view) == snap(eng)


# ============================================================================================= Fibonacci
def _fib_engine(up: Box, dn: Box) -> LuxBprEngine:
    e = LuxBprEngine(HIST)
    e.bpr_up[0] = Zone(up, True, 1)
    e.bpr_dn[0] = Zone(dn, True, -1)
    return e


def test_fib_bpr_dn_first_branch():
    """Pine 976-990 + 1093-1118 with dnFirst (up.left > dn.left). dnBottm true: y1 = dn.bottom, y2 = up.top;
    dnBottm false: y1 = dn.top, y2 = up.bottom. rt = max(x1, x2) = x2, so _0 = y2 and _1 = y1."""
    f = fib_bpr(_fib_engine(Box(20, 3.0, 30, 2.5), Box(10, 2.0, 25, 1.0)))
    assert (f["x1"], f["y1"], f["x2"], f["y2"]) == (10, 1.0, 30, 3.0)
    assert (f["rt"], f["zero"], f["one"], f["line_end"]) == (30, 3.0, 1.0, 80)
    df = 1.0 - 3.0
    assert f["levels"] == {
        0.0: 3.0,
        0.236: 3.0 + df * 0.236,
        0.382: 3.0 + df * 0.382,
        0.5: 2.0,
        0.618: 3.0 + df * 0.618,
        0.786: 3.0 + df * 0.786,
        1.0: 1.0,
        1.618: 3.0 + df * 1.618,
    }
    assert f["levels"][0.236] == pytest.approx(2.528) and f["levels"][1.618] == pytest.approx(-0.236)
    g = fib_bpr(_fib_engine(Box(20, 1.5, 30, 1.0), Box(10, 2.0, 25, 1.75)))  # up.top 1.5 < dn.top 2.0
    assert (g["x1"], g["y1"], g["x2"], g["y2"], g["rt"]) == (10, 2.0, 30, 1.0, 30)
    assert (g["zero"], g["one"]) == (1.0, 2.0) and g["levels"][0.5] == 1.5 and g["levels"][1.618] == 1.0 + 1.618


def test_fib_bpr_up_first_branch_and_edge_cases():
    """Pine 976-990 without dnFirst (up.left <= dn.left): x1 = up.left, x2 = dn.right; dnBottm true -> y1 = up.top,
    y2 = dn.bottom; false -> y1 = up.bottom, y2 = dn.top. rt == x1 (all lefts/rights equal) -> _0 = y1.
    No BPR box on either side -> None."""
    f = fib_bpr(_fib_engine(Box(10, 3.0, 25, 2.5), Box(20, 2.0, 30, 1.0)))
    assert (f["x1"], f["y1"], f["x2"], f["y2"], f["rt"]) == (10, 3.0, 30, 1.0, 30)
    assert (f["zero"], f["one"]) == (1.0, 3.0)
    assert f["levels"][0.5] == 2.0 and f["levels"][0.618] == 1.0 + 2.0 * 0.618 and f["levels"][1.0] == 3.0
    g = fib_bpr(_fib_engine(Box(10, 1.5, 25, 1.0), Box(20, 3.0, 30, 2.0)))
    assert (g["x1"], g["y1"], g["x2"], g["y2"]) == (10, 1.0, 30, 3.0)
    assert (g["zero"], g["one"]) == (3.0, 1.0)
    h = fib_bpr(_fib_engine(Box(40, 3.0, 40, 2.0), Box(40, 2.5, 40, 1.0)))  # x1 == x2 == 40
    assert (h["rt"], h["zero"], h["one"], h["line_end"]) == (40, 3.0, 1.0, 90)
    assert fib_bpr(LuxBprEngine(HIST)) is None
    e = LuxBprEngine(HIST)
    e.bpr_up[0] = Zone(Box(1, 2.0, 3, 1.0), True, 1)
    assert fib_bpr(e) is None  # BPR_DN[0] is box(na)
    assert fib_bpr(LuxBprEngine(HIST_NOBPR)) is None


# ============================================================================================= invariants
@pytest.mark.parametrize("fvg_mode,vis_boxes,seed", [("FVG", 2, 1), ("FVG", 5, 2), ("IFVG", 3, 3), ("FVG", 13, 4)])
def test_invariants_on_long_random_series(fvg_mode, vis_boxes, seed):
    """Invariants of Pine 597-769 on 4000 random bars: array sizes stay visBxs; BPR boxes have bottom < top (the
    creation conditions are strict); every BPR left is the left of an FVG seen before (QUIRK 6 identity); pos is
    never 0 (QUIRK 5); active boxes within 0..bxBack have right = n+8; FVG styles never change with BPR on; in FVG
    mode every FVG box has top > bottom."""
    params = BprParams(mode="Historical", fvg_mode=fvg_mode, vis_boxes=vis_boxes)
    bars = _random_bars(seed, 4000)
    e = LuxBprEngine(params)
    fvg_lefts: set[int] = set()
    bpr_new = 0
    for n, b in enumerate(bars):
        e.process_bar(n, *b)
        for arr in (e.fvg_up, e.fvg_dn, e.bpr_up, e.bpr_dn):
            assert len(arr) == vis_boxes
        for z in e.fvg_up + e.fvg_dn:
            if z.box is not None:
                fvg_lefts.add(z.box.left)
                assert z.pos is None
                assert (z.box.border, z.box.broken_fill) == ("solid", False)
                if fvg_mode == "FVG":
                    assert z.box.top > z.box.bottom
                assert z.box.right <= n + 8
            else:
                assert z.active is False
        for arr in (e.bpr_up, e.bpr_dn):
            for i, z in enumerate(arr):
                if z.box is None:
                    assert z.active is False
                    continue
                assert z.box.bottom < z.box.top
                assert z.box.left in fvg_lefts
                assert z.pos in (1, -1)
                if z.active and i <= params.bx_back:
                    assert z.box.right == n + 8
                if not z.active:
                    assert z.box.border == "dotted" and z.box.broken_fill
        for arr in (e.fvg_up, e.fvg_dn):
            for i, z in enumerate(arr):
                if z.active and i <= params.bx_back:
                    assert z.box.right == n + 8
        bpr_new = sum(1 for ev in e.events if ev[1].startswith("BPR") and ev[2] == "new")
    assert bpr_new > 20, "the random series must exercise the BPR logic"
    kinds = {(k, w) for _, k, w in e.events}
    assert {("BPR_UP", "new"), ("BPR_DN", "new"), ("BPR_UP", "broken"), ("BPR_DN", "broken")} <= kinds
    for kind in ("FVG_UP", "FVG_DN", "BPR_UP", "BPR_DN"):
        new = sum(1 for _, k, w in e.events if k == kind and w == "new")
        broken = sum(1 for _, k, w in e.events if k == kind and w == "broken")
        assert broken <= new  # an entry breaks once; a later update (QUIRK 2) never re-activates it


# ============================================================================================= API / params
def test_params_validation_and_public_api():
    """BprParams mirrors the Pine input ranges (len 3..10, visBxs 1..20) and the option lists."""
    for bad in (
        dict(mode="present"),
        dict(fvg_mode="fvg"),
        dict(length=2),
        dict(length=11),
        dict(vis_boxes=0),
        dict(vis_boxes=21),
    ):
        with pytest.raises(ValueError):
            BprParams(**bad)
    p = BprParams()
    assert (p.mode, p.present_bars, p.length, p.perc_body, p.show_fvg, p.bpr, p.fvg_mode) == (
        "Present",
        500,
        5,
        0.36,
        True,
        True,
        "FVG",
    )
    assert (p.vis_boxes, p.bx_back, p.ext_bars) == (2, 10, 8)
    e = LuxBprEngine()
    assert e.last_index is None and e.events == [] and (e.disp_up, e.disp_dn) == (False, False)
    assert [len(a) for a in (e.fvg_up, e.fvg_dn, e.bpr_up, e.bpr_dn)] == [2, 2, 2, 2]
    import qe.indicators as pkg

    for name in ("BprParams", "Box", "Zone", "LuxBprEngine", "per_start_for", "run", "live_view", "fib_bpr"):
        assert getattr(pkg, name) is getattr(lb, name)


def test_module_is_standard_library_only():
    """The reference must stay pure standard library (no numpy / pandas) and carry the licence header."""
    for path in (ROOT / "qe" / "indicators" / "luxalgo_bpr.py", TOOL):
        src = path.read_text(encoding="utf-8")
        assert "CC BY-NC-SA 4.0" in src and "creativecommons.org/licenses/by-nc-sa/4.0" in src
        assert "LuxAlgo" in src and "section 10" in src
        mods = set()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Import):
                mods |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods.add(node.module.split(".")[0])
        assert mods <= {"__future__", "collections", "dataclasses", "typing", "math", "sys", "pathlib", "qe"}, mods


# ============================================================================================= parity tool
def _export_present(tmp_path: Path, seed: int = 21, n_bars: int = 400, with_time: bool = False):
    params = BprParams(mode="Present", present_bars=150, vis_boxes=3)
    bars = _random_bars(seed, n_bars)
    eng = run(bars, params)  # processed from bar 0
    per_start = eng.per_start
    assert per_start == n_bars - 1 - 150
    first = max(0, per_start - params.length - 3)
    rows = bars[first:]
    if with_time:
        rows = [(1_700_000_000 + 60 * (first + i),) + tuple(b) for i, b in enumerate(rows)]
    path = tmp_path / "export.csv"
    parity.write_export(eng, rows, first, params, per_start, path)
    return path, eng


def test_parity_tool_round_trip_identical(tmp_path, capsys):
    """write_export -> parse -> replay from the warm-up start (per_start - len - 3) gives the same committed state
    as the engine that processed the whole history (FVG creation is gated by per, so earlier bars cannot matter)."""
    path, eng = _export_present(tmp_path, with_time=True)
    assert any(z.box is not None for z in eng.bpr_up + eng.bpr_dn), "export must contain BPR boxes"
    text = path.read_text().splitlines()
    assert text[0] == "# LuxAlgo_BPR export v1"
    assert text[1] == f"PARAMS,Present,150,5,1,1,FVG,3,{eng.per_start},{eng.per_start - 8},399"
    assert sum(1 for ln in text if ln.startswith("ZONE,")) == 12
    exp = parity.parse_export(path)
    assert exp.per_start == eng.per_start and exp.warnings == []
    assert parity.compare(exp) == []
    assert parity.main([str(path)]) == 0
    out = capsys.readouterr().out
    assert "RESULT: IDENTICAL" in out
    # Historical mode, from bar 0, IFVG, BPR off
    params = BprParams(mode="Historical", fvg_mode="IFVG", bpr=False, vis_boxes=4)
    bars = _random_bars(5, 300)
    e2 = run(bars, params)
    p2 = tmp_path / "hist.csv"
    parity.write_export(e2, bars, 0, params, None, p2)
    assert ",NA,0,299" in p2.read_text().splitlines()[1]
    assert parity.main([str(p2)]) == 0


def test_parity_tool_reports_mismatches(tmp_path, capsys):
    """A changed price, flag or a missing row is reported field by field with exit code 1; a difference far below
    1e-9 * price scale is tolerated."""
    path, _ = _export_present(tmp_path)
    lines = path.read_text().splitlines()
    idx = next(i for i, ln in enumerate(lines) if ln.startswith("ZONE,BPR_") and ln.split(",")[3] == "1")
    f = lines[idx].split(",")
    kind, slot = f[1], f[2]

    def write(mod):
        p = tmp_path / "mod.csv"
        p.write_text("\n".join(mod) + "\n")
        return p

    tiny = list(lines)
    g = list(f)
    g[5] = format(float(g[5]) + 1e-12, ".17g")
    tiny[idx] = ",".join(g)
    assert parity.main([str(write(tiny))]) == 0
    capsys.readouterr()
    bad = list(lines)
    g = list(f)
    g[5] = format(float(g[5]) + 0.001, ".17g")
    g[8] = "0" if g[8] == "1" else "1"
    bad[idx] = ",".join(g)
    assert parity.main([str(write(bad))]) == 1
    out = capsys.readouterr().out
    assert f"{kind}[{slot}] top" in out and f"{kind}[{slot}] active" in out and "RESULT: MISMATCH" in out
    missing = [ln for i, ln in enumerate(lines) if i != idx]
    assert parity.main([str(write(missing))]) == 1
    assert "missing in export" in capsys.readouterr().out


def test_parity_tool_rejects_malformed_input(tmp_path):
    """Malformed exports exit with code 2 (header, non-consecutive bars, wrong field count)."""
    path, _ = _export_present(tmp_path)
    lines = path.read_text().splitlines()
    cases = [
        lines[1:],  # no header
        [lines[0], lines[1]] + lines[3:],  # first BAR row removed -> indices do not start at first_index
        [lines[0], lines[1] + ",x"] + lines[2:],  # PARAMS with 12 fields
    ]
    for i, mod in enumerate(cases):
        p = tmp_path / f"bad{i}.csv"
        p.write_text("\n".join(mod) + "\n")
        assert parity.main([str(p)]) == 2, i
    assert parity.main([]) == 2
    assert parity.main([str(tmp_path / "does_not_exist.csv")]) == 2


def test_parity_tool_cli_and_crlf_utf16(tmp_path):
    """The CLI runs as a script from any directory (it finds the qe package itself) and accepts MT5 files with
    CRLF line ends or UTF-16 encoding."""
    path, _ = _export_present(tmp_path)
    crlf = tmp_path / "crlf.csv"
    crlf.write_bytes(path.read_text().replace("\n", "\r\n").encode("utf-8"))
    u16 = tmp_path / "u16.csv"
    u16.write_bytes(path.read_text().encode("utf-16"))
    for p in (crlf, u16):
        r = subprocess.run([sys.executable, str(TOOL), str(p)], cwd=tmp_path, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        assert "RESULT: IDENTICAL" in r.stdout


def test_run_with_forming_bar_anchors_present_window_like_mt5():
    """Spec section 7: with a forming bar on the chart, Pine's last_bar_index is the forming bar, so the window is
    [L - present_bars, L] with L = first_index + len(closed). The MT5 indicator uses formingBar - InpPresentBars."""
    p = BprParams(mode="Present", present_bars=50)
    closed = [(100.0, 101.0, 99.0, 100.5)] * 80
    assert run(closed, p).per_start == 79 - 50
    assert run(closed, p, forming_bar=True).per_start == 80 - 50
    assert run(closed, p, first_index=10, forming_bar=True).per_start == 90 - 50
    assert run(closed, p, last_bar_index=200, forming_bar=True).per_start == 150  # explicit index wins
    assert run(closed, BprParams(mode="Historical"), forming_bar=True).per_start is None

