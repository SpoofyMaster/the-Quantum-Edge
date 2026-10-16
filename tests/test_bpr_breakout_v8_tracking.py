"""BprFvgEA v8: every BPR tracked until its first touch, and quick reversal limits, checked on the C++ transliteration
of the MQL5 detector only (EA only, like v5-v7).

The owner's example of 2026-10-16 (a screenshot of the v7 chart with a drawing): the BPR forms, price goes on up
without touching it, comes back and taps it from above (T1), reacts up, and finally breaks the T1 wick. "the EA must
track every BPR created and where was the first Tape and reaction on it ... the EA must be quick, the moment when price
close with the second candles body below/above T1 or T2 wicks, the EA must place limits orders and continue tracking
price with fibonacci to update the limit orders levels".

v8 detector params (EA inputs; harness keys in brackets), with the EA's defaults in EA8 below:
- t1WaitBars (InpMaxBarsToT1, t1_wait): bars from the BPR's creation to T1; 0 = no limit (EA default), -1 = v4-v7
  rules (the detector default, used by the parity set). With >= 0: the breakout window (setupExpiryBars) counts from
  T1 (a reversal setup: from its last rejection when later); at capacity (128) the oldest untouched setup makes room
  (DONE(CAPACITY)); warm-up setups that have not confirmed go on after the warm-up.
- revNeedFvg (InpRevNeedFvg, rev_fvg): the reversal waits for an FVG of its trade direction (true = v7, the detector
  default); the EA default false lets its limits go in at the confirming close.
- anticipate (InpAnticipateEntries) is now true by default in the EA (v5 rule: limits at the confirmation, moved at
  every new extreme).
Skipped without g++.
"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from bk_scenarios import bar, base, mirror, prefix, v7_sequences, v8_sequences
from test_bpr_breakout_v6_setups import BOTH, CONT, FVG, REV, SP, _bars, _check, short_fib
from test_bpr_breakout_v6_setups import exe as _exe_fixture  # noqa: F401 (module-scoped harness build)
from test_bpr_breakout_v6_setups import run as _run6
from test_bpr_breakout_v7_reversal import _check7

exe = _exe_fixture
pytestmark = pytest.mark.skipif(shutil.which("g++") is None, reason="g++ not installed")
V8 = v8_sequences()
V7 = v7_sequences()
EA8 = dict(anticipate=1, t1_wait=0, rev_fvg=0)          # the EA's v8 defaults for the new switches
V7R = dict(anticipate=0, t1_wait=-1, rev_fvg=1)         # the v7 rules (detector defaults)


def run(exe, tmp_path, bars, hold=50, **kv):
    kv.setdefault("ext", 1)
    return _run6(exe, tmp_path, bars, hold=hold, **kv)


def seq(name, d):
    return V8[name] if d > 0 else mirror(V8[name])


def of(recs, i, n=None, ev=None):
    return [r for r in recs if r["id"] == i and (n is None or r["n"] == n) and (ev is None or r["ev"] == ev)]


def sid(recs, kind):
    return next(r["id"] for r in recs if r["ev"] == "TOUCH" and r["kind"] == kind)


def main(recs, d, kind=None):
    """the ids of the hand-built BPR's setups: ARMED on bar 13 in the BPR's direction d (the mirrored bars arm another
    BPR on 12, and later bars can make more)"""
    return [r["id"] for r in recs if r["ev"] == "ARMED" and r["n"] == 13 and r["dir"] == d and
            (kind is None or r["kind"] == kind)]


def key(rs):
    return [(r["n"], r["ev"], r["dir"], r["k"], r["reason"]) for r in rs]


def px(d, x):
    return x if d > 0 else round(200.0 - x, 2)


D = pytest.mark.parametrize("d", [1, -1], ids=["bullish-BPR", "bearish-BPR"])


def ladder(nblocks, step=3.0, start=0):
    """BPRs that price never comes back to: the prefix's BPR pattern repeated, each block 3.0 higher (its lows stay
    above every earlier zone). One bullish BPR per block (10 bars). start: blocks to skip at the bottom."""
    out = []
    for b in range(start, start + nblocks):
        k = b * step
        for i in range(4):
            o = 100.0 + k + (0.1 if i % 2 else 0.0)
            c = o + (0.1 if i % 2 == 0 else -0.1)
            out.append(bar(o, max(o, c) + 0.02, min(o, c) - 0.02, c))
        out += [bar(100.0 + k, 100.05 + k, 99.9 + k, 99.95 + k), bar(99.95 + k, 99.97 + k, 97.98 + k, 98.0 + k),
                bar(97.4 + k, 97.5 + k, 97.0 + k, 97.1 + k), bar(97.1 + k, 98.0 + k, 97.05 + k, 97.9 + k),
                bar(97.9 + k, 99.92 + k, 97.88 + k, 99.9 + k), bar(99.95 + k, 100.3 + k, 99.95 + k, 100.2 + k)]
    return out


def walk(a, b, step=0.2):
    """overlapping candles from a to b (each one overlaps the one two bars back: no FVG, so no BPR)"""
    out, o = [], a
    s = step if b > a else -step
    for _ in range(round(abs(b - a) / step)):
        c = round(o + s, 2)
        out.append(bar(o, max(o, c) + 0.05, min(o, c) - 0.05, c))
        o = c
    return out


# ---------------------------------------------------------------------------------------------------------------
# the owner's drawing: tap from above, reaction, break of the T1 wick
# ---------------------------------------------------------------------------------------------------------------
@D
def test_tap_from_above_limits_at_the_second_close(exe, tmp_path, d):
    """REVERSAL with the EA's v8 defaults. The BPR forms on 13, price goes up and comes back: T1 on 17 (wick 99.0),
    rejection 18 (it closes back above the zone), the T1 wick broken on 23 and again on 24. The sell limits go in on 24,
    the second close (100 % = 101.6, 0 % = 98.2), move on 25 to the new low 97.6, the 50 % (99.6) fills on 27, the
    target is reached on 28."""
    recs, _ = run(exe, tmp_path, seq("tap_from_above", d), setup_type=REV, **EA8)
    i = sid(recs, 1)
    assert [r["n"] for r in of(recs, i, ev="TOUCH")] == [17]
    br = of(recs, i, ev="BREAKOUT")[0]
    assert (br["n"], br["lvl"]) == (23, pytest.approx(px(d, 99.0)))
    assert [r["ev"] for r in of(recs, i, n=24)] == ["CONFIRM", "PLACE_LIMIT", "PLACE_LIMIT", "PLACE_LIMIT"]
    pl24 = of(recs, i, n=24, ev="PLACE_LIMIT")
    assert all(r["O"] == pytest.approx(px(d, 101.6)) and r["X"] == pytest.approx(px(d, 98.2)) for r in pl24)
    if d > 0:
        assert [r["P"] for r in pl24] == pytest.approx(short_fib(101.6, 98.2))
        assert all(r["SL"] == pytest.approx(101.6 + 0.1 + SP) for r in pl24)
    ev25 = [r["ev"] for r in of(recs, i, n=25)]
    assert ev25 == ["CANCEL"] * 3 + ["PLACE_LIMIT"] * 3
    assert all(r["X"] == pytest.approx(px(d, 97.6)) for r in of(recs, i, n=25, ev="PLACE_LIMIT"))
    assert of(recs, i, n=28, ev="CLOSED")


@D
def test_tap_from_above_v7_rules_wait_for_a_pullback_candle(exe, tmp_path, d):
    """The same bars with the v7 rules (no anticipation, FVG needed): no order on the confirmation 24; the limits only
    go in on the pullback candle 26."""
    recs, _ = run(exe, tmp_path, seq("tap_from_above", d), setup_type=REV, **V7R)
    i = sid(recs, 1)
    assert not of(recs, i, n=24, ev="PLACE_LIMIT") and of(recs, i, n=26, ev="PLACE_LIMIT")


@D
def test_tap_from_above_both(exe, tmp_path, d):
    """BOTH with the v8 defaults: the continuation setup trades the reaction up first (CONFIRM 20, limits at once),
    is stopped by the drop (CLOSED 23); the reversal setup then places its limits on 24, its second close."""
    recs, _ = run(exe, tmp_path, seq("tap_from_above", d), setup_type=BOTH, **EA8)
    c, r = sid(recs, 0), sid(recs, 1)
    assert of(recs, c, n=20, ev="CONFIRM") and of(recs, c, n=20, ev="PLACE_LIMIT") and of(recs, c, n=23, ev="CLOSED")
    assert len(of(recs, r, n=24, ev="PLACE_LIMIT")) == 3


# ---------------------------------------------------------------------------------------------------------------
# tracking every BPR until its first touch
# ---------------------------------------------------------------------------------------------------------------
@D
@pytest.mark.parametrize("st", [REV, BOTH])
def test_late_first_touch_is_tracked(exe, tmp_path, d, st):
    """The BPR forms on 13, price stays away for 300 bars, then taps it (T1 on 315), rejects (316) and closes twice
    below the T1 wick (319 / 320): v8 trades it. The v7 rules ended it EXPIRED in WAIT on 254 (240 bars after 13)."""
    v8, _ = run(exe, tmp_path, seq("late_t1", d), setup_type=st, **EA8)
    i = sid(v8, 1)
    assert [r["n"] for r in of(v8, i, ev="TOUCH")] == [315]
    assert of(v8, i, n=320, ev="CONFIRM") and of(v8, i, n=320, ev="PLACE_LIMIT")
    v7, _ = run(exe, tmp_path, seq("late_t1", d), setup_type=st, **V7R)
    ids = main(v7, d)
    assert ids and [(r["n"], r["reason"]) for r in v7 if r["ev"] == "DONE" and r["id"] in ids] == [(254, "EXPIRED")] * len(ids)
    assert not [r for r in v7 if r["ev"] == "TOUCH" and r["id"] in ids]


@D
def test_t1_wait_limit(exe, tmp_path, d):
    """InpMaxBarsToT1 = 100: no touch within 100 bars of the creation (13) -> DONE(EXPIRED) on 114 in WAIT."""
    recs, _ = run(exe, tmp_path, seq("late_t1", d), setup_type=REV, anticipate=1, t1_wait=100, rev_fvg=0)
    i = main(recs, d)[0]
    assert key(of(recs, i, ev="DONE")) == [(114, "DONE", d, 0, "EXPIRED")] and not of(recs, i, ev="TOUCH")


@D
def test_window_counts_only_while_in_play(exe, tmp_path, d):
    """setup_expiry_bars 2, continuation. v8: T1 on 315, rejection 316; price is away (no clock) until it comes back
    on 319 (T2); that visit is not resolved, so the setup expires 3 bars later, on 322. The v7 rules count from the
    creation (13) and end it on 16."""
    v8, _ = run(exe, tmp_path, seq("late_t1", d), setup_type=CONT, setup_expiry_bars=2, **EA8)
    assert key(of(v8, main(v8, d)[0], ev="DONE")) == [(322, "DONE", d, 0, "EXPIRED")]
    v7, _ = run(exe, tmp_path, seq("late_t1", d), setup_type=CONT, setup_expiry_bars=2, **V7R)
    assert key(of(v7, main(v7, d)[0], ev="DONE")) == [(16, "DONE", d, 0, "EXPIRED")]


@D
def test_a_long_visit_still_expires(exe, tmp_path, d):
    """setup_expiry_bars 5: T1 on 17, then price stays inside the zone (no rejection, no breakout): the setup expires
    6 bars after the visit began, on 23 (reversal and continuation)."""
    bars = V8["tap_from_above"][:17] + [bar(100.1, 100.15, 99.5, 99.6)] + [bar(99.6, 99.7, 99.4, 99.6)] * 10
    bars = bars if d > 0 else mirror(bars)
    for st, kind in ((REV, 1), (CONT, 0)):
        recs, _ = run(exe, tmp_path, bars, setup_type=st, setup_expiry_bars=5, **EA8)
        assert key(of(recs, main(recs, d, kind)[0], ev="DONE")) == [(23, "DONE", d, 0, "EXPIRED")], st


@D
@pytest.mark.parametrize("st", [REV, BOTH])
def test_late_break_of_the_t1_wick(exe, tmp_path, d, st):
    """The owner's T1 (17) and reaction, then 300 bars away, then the drop: closes below the T1 wick on 323 and 324.
    v8 places the sell limits on 324 (100 % = 101.6) and the trade reaches its target (328). With the v7 rules the
    rejection is on 19 (18 opens inside the zone), and the setup ends EXPIRED on 260, 241 bars later."""
    v8, _ = run(exe, tmp_path, seq("late_break", d), setup_type=st, **EA8)
    i = main(v8, d, 1)[0]
    assert key(of(v8, i, n=323)) == [(323, "BREAKOUT", -d, 0, None)]
    pl = of(v8, i, n=324, ev="PLACE_LIMIT")
    assert len(pl) == 3 and pl[0]["O"] == pytest.approx(px(d, 101.6)) and of(v8, i, n=328, ev="CLOSED")
    v7, _ = run(exe, tmp_path, seq("late_break", d), setup_type=st, **V7R)
    assert key(of(v7, main(v7, d, 1)[0], ev="DONE")) == [(260, "DONE", d, 0, "EXPIRED")]


@D
def test_late_continuation_breakout(exe, tmp_path, d):
    """Continuation: T1 on 14, rejection 15, then 300 bars just outside the zone and below the level (100.2): away, no
    clock. The breakout on 316 starts the window again (from the breakout candle): CONFIRM and limits on 317. The v7
    rules ended the setup EXPIRED on 254 (240 bars after the creation)."""
    v8, _ = run(exe, tmp_path, seq("late_cont_breakout", d), setup_type=CONT, **EA8)
    i = main(v8, d)[0]
    assert key(of(v8, i, n=316)) == [(316, "BREAKOUT", d, 0, None)]
    assert of(v8, i, n=317, ev="CONFIRM") and len(of(v8, i, n=317, ev="PLACE_LIMIT")) == 3
    v7, _ = run(exe, tmp_path, seq("late_cont_breakout", d), setup_type=CONT, **V7R)
    assert key(of(v7, main(v7, d)[0], ev="DONE")) == [(254, "DONE", d, 0, "EXPIRED")]


@D
def test_late_t2_then_the_break(exe, tmp_path, d):
    """T1 and its reaction, 300 bars away, then a late T2 (322, rejected on 323) and the break of the T1 wick (324,
    325): limits on 325, with the 100 % at the T2 bounce (100.5)."""
    recs, _ = run(exe, tmp_path, seq("late_t2", d), setup_type=REV, **EA8)
    i = main(recs, d)[0]
    assert [r["n"] for r in of(recs, i, ev="TOUCH")] == [17, 322]
    assert key(of(recs, i, n=324)) == [(324, "BREAKOUT", -d, 0, None)]
    pl = of(recs, i, n=325, ev="PLACE_LIMIT")
    assert len(pl) == 3 and pl[0]["O"] == pytest.approx(px(d, 100.5))


@D
def test_one_candle_reaction_is_the_rejection(exe, tmp_path, d):
    """T1 on 17 closes inside the zone; 18 is a one-candle bullish reaction whose wick is still in the zone but which
    closes above it: the rejection (v8, reversal setups). 19 comes back (T2), 20 / 21 close below the T1 wick: limits on
    21 with the 100 % at 18's high 101.6. A continuation setup keeps the v2 rule (18 is still part of the touch)."""
    recs, _ = run(exe, tmp_path, seq("one_candle_reaction", d), setup_type=BOTH, **EA8)
    r, c = main(recs, d, 1)[0], main(recs, d, 0)[0]
    assert key(of(recs, r, n=18)) == [(18, "REJECT", d, 0, None)]
    assert [x["n"] for x in of(recs, r, ev="TOUCH")] == [17, 19]
    assert key(of(recs, r, n=20)) == [(20, "BREAKOUT", -d, 0, None)]
    pl = of(recs, r, n=21, ev="PLACE_LIMIT")
    assert len(pl) == 3 and pl[0]["O"] == pytest.approx(px(d, 101.6))
    assert not of(recs, c, n=18, ev="REJECT")
    # the v7 rules: 18 still belongs to the T1 visit and 19 re-enters the zone: no rejection, so no reversal
    v7, _ = run(exe, tmp_path, seq("one_candle_reaction", d), setup_type=REV, **V7R)
    i = main(v7, d)[0]
    assert [x["ev"] for x in of(v7, i) if x["n"] <= 30] == ["ARMED", "TOUCH"]


@D
def test_one_candle_reaction_needs_a_close_beyond_the_zone(exe, tmp_path, d):
    """The boundary: 18 closes exactly at the zone's edge (99.9): not a rejection, the visit goes on. 19 closes above
    it with its wick in the zone: the rejection is on 19."""
    s = V8["one_candle_reaction"]
    bars = s[:18] + [bar(99.6, 100.0, 99.55, 99.9), bar(99.9, 101.6, 99.85, 101.5)] + s[19:]
    recs, _ = run(exe, tmp_path, bars if d > 0 else mirror(bars), setup_type=REV, **EA8)
    i = main(recs, d)[0]
    assert [r["n"] for r in of(recs, i, ev="REJECT")][:1] == [19]
    assert not of(recs, i, n=18)


def test_capacity_drops_the_oldest_untouched(exe, tmp_path):
    """80 BPRs that price never comes back to, BOTH (160 setups, capacity 128). v8: every new BPR is ARMED; the oldest
    untouched setups make room (DONE(CAPACITY), ids 1, 2, 3, ...). v7 rules with a long expiry: the newest ones are
    refused at their creation instead."""
    bars = ladder(80)
    v8, _ = run(exe, tmp_path, bars, setup_type=BOTH, **EA8)
    armed = [r["id"] for r in v8 if r["ev"] == "ARMED"]
    cap = [r["id"] for r in v8 if r["ev"] == "DONE" and r["reason"] == "CAPACITY"]
    assert len(armed) == 160 and cap == list(range(1, 33))
    v7, _ = run(exe, tmp_path, bars, setup_type=BOTH, setup_expiry_bars=100000, **V7R)
    cap7 = [r["id"] for r in v7 if r["ev"] == "DONE" and r["reason"] == "CAPACITY"]
    assert len([r for r in v7 if r["ev"] == "ARMED"]) == 128 and cap7 == list(range(129, 161))


@pytest.fixture(scope="module")
def exe4(tmp_path_factory):
    """The harness built with a capacity of 4 setups (BF_MAX_SETUPS), to test the capacity rule on short series."""
    root = Path(__file__).resolve().parents[1]
    d = tmp_path_factory.mktemp("bk8cap")
    sys.path.insert(0, str(root / "tools/mql5_cpp_harness"))
    try:
        from mq5_to_cpp import transform_pure
    finally:
        sys.path.pop(0)
    inc = root / "mql5/BprFvgEA/include"
    src = [(inc / f).read_text(encoding="utf-8") for f in ("BfDefines.mqh", "BfEngine.mqh", "BfDetector.mqh")]
    old = "#define BF_MAX_SETUPS     128"
    assert src[0].count(old) == 1
    src[0] = src[0].replace(old, "#define BF_MAX_SETUPS     4")
    (d / "bf_pure.cpp").write_text(transform_pure(src))
    shutil.copy(root / "tools/mql5_cpp_harness/shim.h", d / "shim.h")
    shutil.copy(root / "tools/mql5_cpp_harness/bk_main.cpp", d / "bk_main.cpp")
    res = subprocess.run([shutil.which("g++"), "-std=c++17", "-O1", "-w", "-o", str(d / "bk4"), str(d / "bk_main.cpp")],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr[-3000:]
    return d / "bk4"


def test_capacity_drops_idle_setups_only(exe4, tmp_path):
    """Capacity 4, BOTH. The first BPR (base(): T1 14, rejection 15) gives a continuation setup (id 1) that confirms
    and keeps its buy limits pending while price climbs (busy: never dropped) and a reversal setup (id 2) that waits
    away from the zone since its rejection (idle since 15). Then 6 BPRs that price never revisits: every one is
    ARMED, and the idle setups make room in order of their last zone event: 2 (15), then 3, 4, ... (created later)."""
    bars = base() + ladder(6, start=3)
    recs, _ = run(exe4, tmp_path, bars, setup_type=BOTH, leg_expiry_bars=100000, **EA8)
    assert len([r for r in recs if r["ev"] == "ARMED"]) == 14
    cap = [r["id"] for r in recs if r["ev"] == "DONE" and r["reason"] == "CAPACITY"]
    assert cap[:3] == [2, 3, 4] and 1 not in cap
    assert of(recs, 1, ev="PLACE_LIMIT") and not of(recs, 1, ev="DONE") and not of(recs, 1, ev="CLOSED")


def test_capacity_keeps_a_setup_in_a_visit(exe4, tmp_path):
    """Capacity 4, BOTH. base() up to T1 (14), then a gap far below the zone and 6 bearish BPRs further down. The
    continuation setup (id 1) is BROKEN on 15. The reversal setup (id 2) is still in its T1 visit (no rejection yet, so
    the close below the zone is no breakout): busy, never dropped. The new setups make room for each other: 3, 4, ..."""
    bars = base()[:15] + mirror(ladder(6, start=3))
    recs, _ = run(exe4, tmp_path, bars, setup_type=BOTH, leg_expiry_bars=100000, **EA8)
    assert key(of(recs, 1, ev="DONE")) == [(15, "DONE", 1, 0, "BROKEN")]
    cap = [r["id"] for r in recs if r["ev"] == "DONE" and r["reason"] == "CAPACITY"]
    assert cap == list(range(3, 24)) and not of(recs, 2, ev="DONE")


def test_capacity_counts_idle_time_from_the_last_zone_event(exe4, tmp_path):
    """Capacity 4, REVERSAL. A: the prefix's bullish BPR (id 1, created 13). Price walks up, makes two bearish BPRs
    above (ids 2, 3, created 71 / 72), walks back down and taps A (T1 121), which rejects on 122. Then a block makes a
    bearish (id 4, 141) and a bullish BPR (id 5, 144). At 144 the capacity is reached: id 2 is dropped (idle since its
    creation on 71), not id 1 (created first, but idle only since its rejection on 122)."""
    lad = mirror(ladder(1), 210.0)
    bars = (prefix() + walk(100.2, 110.0) + lad + walk(lad[-1][3], 100.2) +
            [bar(100.2, 100.25, 99.5, 99.7), bar(99.7, 100.6, 99.65, 100.5)] + walk(100.5, 103.0) + ladder(1, start=1))
    recs, _ = run(exe4, tmp_path, bars, setup_type=REV, leg_expiry_bars=100000, **EA8)
    assert [(r["n"], r["id"]) for r in recs if r["ev"] == "ARMED"] == [(13, 1), (71, 2), (72, 3), (141, 4), (144, 5)]
    assert key(of(recs, 1)) == [(13, "ARMED", 1, 0, None), (121, "TOUCH", 1, 1, None), (122, "REJECT", 1, 0, None)]
    assert [(r["n"], r["id"]) for r in recs if r["ev"] == "DONE"] == [(144, 2)]


@D
def test_warmup_setups_go_on_until_confirmed(exe, tmp_path, d):
    """trade_from 16: the BPR forms on 13, during the warm-up. v8: its setup goes on and trades the reversal (T1 on
    17, limits on 24). v7 rules: DONE(WARMUP) when the warm-up ends. A setup already confirmed during the warm-up
    (trade_from 25: confirmation on 24) ends in both."""
    v8, _ = run(exe, tmp_path, seq("tap_from_above", d), setup_type=REV, trade_from=16, **EA8)
    assert of(v8, sid(v8, 1), n=24, ev="PLACE_LIMIT")
    # warm-up ending inside the T1 visit (trade_from 18) or after the rejection on 18 (trade_from 19): the setup is in
    # ZONE and goes on as well
    for tf in (18, 19):
        zn, _ = run(exe, tmp_path, seq("tap_from_above", d), setup_type=REV, trade_from=tf, **EA8)
        assert of(zn, main(zn, d)[0], n=24, ev="PLACE_LIMIT"), tf
    v7, _ = run(exe, tmp_path, seq("tap_from_above", d), setup_type=REV, trade_from=16, **V7R)
    i = main(v7, d)[0]
    assert [r["reason"] for r in v7 if r["ev"] == "DONE" and r["id"] == i] == ["WARMUP"]
    late, _ = run(exe, tmp_path, seq("tap_from_above", d), setup_type=REV, trade_from=25, **EA8)
    i = main(late, d)[0]
    assert [r["reason"] for r in late if r["ev"] == "DONE" and r["id"] == i] == ["WARMUP"]
    assert not [r for r in late if r["ev"] == "PLACE_LIMIT" and r["id"] == i]


@D
@pytest.mark.parametrize("rule", ["LUXALGO", "ANY_GAP"])
def test_reversal_without_fvg_condition(exe, tmp_path, d, rule):
    """v7 sequence fvg_before_top: the drop makes no FVG after its 100 %. rev_fvg on (v7): no orders; off (EA
    default): limits at the confirmation (30)."""
    bars = V7["fvg_before_top"] if d > 0 else mirror(V7["fvg_before_top"])
    on, _ = run(exe, tmp_path, bars, setup_type=REV, anticipate=1, rev_fvg=1, fvg_rule=FVG[rule])
    assert not [r for r in on if r["ev"] == "PLACE_LIMIT" and r["id"] in main(on, d)]
    off, _ = run(exe, tmp_path, bars, setup_type=REV, anticipate=1, rev_fvg=0, fvg_rule=FVG[rule])
    assert of(off, main(off, d)[0], n=30, ev="PLACE_LIMIT")


# ---------------------------------------------------------------------------------------------------------------
# random series: invariants, the continuation unchanged by rev_fvg, causality
# ---------------------------------------------------------------------------------------------------------------
RANDOM8 = [
    (71, dict(setup_type=BOTH, **EA8)),
    (72, dict(setup_type=REV, **EA8)),
    (73, dict(setup_type=BOTH, touch_entry=1, **EA8)),
    (74, dict(setup_type=BOTH, t1_wait=50, anticipate=1, rev_fvg=0)),
    (75, dict(setup_type=CONT, **EA8)),
    (76, dict(setup_type=BOTH, trade_from=500, **EA8)),
]


@pytest.mark.parametrize("case", RANDOM8, ids=[f"seed{c[0]}" for c in RANDOM8])
def test_random_series_invariants(exe, tmp_path, case):
    """The v6 and v7 invariants, plus: no setup expires before its T1 without a T1 limit; a setup dropped for capacity
    was idle (its last record is its creation, a rejection or a failed breakout)."""
    seed, kv = case
    bars = _bars(seed, 4000)
    recs, _ = run(exe, tmp_path, bars, hold=60, **kv)
    assert {"CONFIRM", "PLACE_LIMIT"} <= {r["ev"] for r in recs}
    _check(recs, kv)
    _check7(recs, bars, kv)
    touched = {r["id"] for r in recs if r["ev"] == "TOUCH"}
    created = {r["id"]: r["n"] for r in recs if r["ev"] == "ARMED"}
    last = {}
    for r in recs:
        if r["ev"] == "DONE" and r["reason"] == "EXPIRED" and r["id"] not in touched:
            assert kv["t1_wait"] > 0 and r["n"] - created[r["id"]] == kv["t1_wait"] + 1, r
        if r["ev"] == "DONE" and r["reason"] == "CAPACITY":
            assert last.get(r["id"]) in (None, "ARMED", "REJECT", "BREAK_FAIL"), r
        last[r["id"]] = r["ev"]


@pytest.mark.parametrize("st", [BOTH, REV])
def test_capacity_random_series(exe4, tmp_path, st):
    """Capacity 4 on random series: many setups are dropped. Each one was idle (its last record is its creation, a
    rejection or a failed breakout) or is a new one refused because every tracked setup is busy (no record before), and
    the v6 / v7 invariants still hold."""
    kv = dict(setup_type=st, **EA8)
    bars = _bars(61, 3000)
    recs, _ = run(exe4, tmp_path, bars, hold=60, **kv)
    _check(recs, kv)
    _check7(recs, bars, kv)
    last, n = {}, 0
    for r in recs:
        if r["ev"] == "DONE" and r["reason"] == "CAPACITY":
            assert last.get(r["id"]) in (None, "ARMED", "REJECT", "BREAK_FAIL"), r
            n += last.get(r["id"]) is not None
        last[r["id"]] = r["ev"]
    assert n > 20


def test_rev_fvg_leaves_the_continuation_alone(exe, tmp_path):
    for seed in (81, 82):
        a, _ = run(exe, tmp_path, _bars(seed, 3000), hold=60, setup_type=CONT, anticipate=1, t1_wait=0, rev_fvg=0)
        b, _ = run(exe, tmp_path, _bars(seed, 3000), hold=60, setup_type=CONT, anticipate=1, t1_wait=0, rev_fvg=1)
        assert a == b


@pytest.mark.parametrize("kv", [dict(setup_type=BOTH, touch_entry=1, **EA8), dict(setup_type=REV, t1_wait=40,
                                                                                  anticipate=1, rev_fvg=0)],
                         ids=["both+touch", "rev-t1wait40"])
def test_v8_rules_are_causal(exe, tmp_path, kv):
    """CLAUDE.md causality rule: the records up to bar t do not depend on later bars."""
    bars = _bars(47, 1500)
    full, _ = run(exe, tmp_path, bars, hold=60, **kv)
    other = _bars(91, 1500)
    for t in (300, 701, 1111):
        cut, _ = run(exe, tmp_path, bars[:t + 1], hold=60, **kv)
        assert full[:len(cut)] == cut, t
        sh = bars[t][3] - other[t + 1][0]
        alt, _ = run(exe, tmp_path, bars[:t + 1] + [tuple(x + sh for x in b) for b in other[t + 1:]], hold=60, **kv)
        assert alt[:len(cut)] == cut, t
