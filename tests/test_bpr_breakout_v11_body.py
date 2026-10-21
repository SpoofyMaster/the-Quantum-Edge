"""BprFvgEA v11: the bodies of the T1 / T2 candles and of the rejection candles C1, C2 must stay in the BPR box, checked
on the C++ transliteration of the MQL5 detector (the EA's log text and chart label are checked by reading).

The owner's rule of 2026-10-21 (his drawing on the v9 chart: a T1 whose body stays in the box "YES", a T1 whose body
closes below it "NO"): "on T1 or T2, the body of those candles must not go out of BPR rectangle ... for a BPR who is
tested by price from above, T1 Candles body must not close out of the BPR box, after that C1 and C2 must also above or
on the box, if they close out of the BPR box no trade, and same for a tape from below the BPR."

Read as (detector param revBodyInBox, EA input InpRevBodyInBox, harness key rev_body_box): for a reversal setup on a
bullish BPR (tapped from above), the body - open and close - of every candle of the T1 / T2 touch and of every counted
rejection candle (C1, C2, ...) must be in the box or above it; on the edge counts as in the box; the wicks may go out.
Otherwise the setup ends DONE(BROKEN) with bodyOut (harness "bo": n = the Tn candle, 10 + n = Cn). A bearish BPR
(tapped from below) is the mirror image. Continuation setups already end BROKEN at a wick beyond the box. The bars are
tests/bk_scenarios.py v11_sequences(). Skipped without g++.
"""
import shutil

import pytest

from bk_scenarios import bar, mirror, v9_sequences, v11_drop, v11_sequences, v11_up
from test_bpr_breakout_v6_setups import BOTH, CONT, REV, _bars
from test_bpr_breakout_v6_setups import exe as _exe_fixture  # noqa: F401 (module-scoped harness build)
from test_bpr_breakout_v6_setups import run as _run6

exe = _exe_fixture
pytestmark = pytest.mark.skipif(shutil.which("g++") is None, reason="g++ not installed")
EA = dict(anticipate=1, t1_wait=0, rev_fvg=0, rev_rej_c=2, fvg_rule=0)
V11 = v11_sequences()
D = pytest.mark.parametrize("d", [1, -1], ids=["tapped-from-above", "tapped-from-below"])


def run(exe, tmp_path, bars, **kv):
    kv.setdefault("ext", 1)
    return _run6(exe, tmp_path, bars, hold=50, **kv)[0]


def side(bars, d):
    return bars if d > 0 else mirror(bars)


def sid(recs, kind=1):
    """the setup of the BPR formed on bar 13 (the mirrored bars arm another BPR earlier)"""
    return next(r["id"] for r in recs if r["ev"] == "ARMED" and r["n"] == 13 and r["kind"] == kind)


def mine(recs, i):
    return [r for r in recs if r["id"] == i]


def of(recs, i, *evs):
    return [(r["n"], r["ev"], r["k"], r["reason"], r["bo"]) for r in recs if r["id"] == i and r["ev"] in evs]


def body_out(b, zd, zb, zt):
    o, _, _, c = b
    return min(o, c) < zb if zd > 0 else max(o, c) > zt


# name -> (bar of the end, bodyOut, v10's first PLACE_LIMIT bar on the tapped-from-above side)
NO_TRADE = {
    "t1_body_out": (17, 1, 23),
    "c2_body_out": (20, 12, 25),
    "c1_body_out": (18, 11, 24),
    "t1_next_candle_out": (18, 1, 24),
    "t2_body_out": (21, 2, 25),
}


@D
@pytest.mark.parametrize("name", list(NO_TRADE))
def test_a_body_out_of_the_box_means_no_trade(exe, tmp_path, d, name):
    """Each case ends on the candle whose body leaves the box, DONE(BROKEN) with bo naming it, and never places an
    order. Before that candle the records are the v10 ones; v10 (rev_body_box=0) went on to a breakout (and, tapped
    from above, to limits)."""
    end, bo, pl10 = NO_TRADE[name]
    bars = side(V11[name], d)
    recs = run(exe, tmp_path, bars, setup_type=REV, rev_body_box=1, **EA)
    i = sid(recs)
    assert of(recs, i, "DONE") == [(end, "DONE", 0, "BROKEN", bo)]
    assert not of(recs, i, "BREAKOUT", "PLACE_LIMIT")
    zd = next(r["zdir"] for r in recs if r["id"] == i)
    zb, zt = next((r["zb"], r["zt"]) for r in recs if r["id"] == i and r["ev"] == "DONE")
    assert zd == d and body_out(bars[end], zd, zb, zt)
    v10 = run(exe, tmp_path, bars, setup_type=REV, **EA)
    assert [r for r in v10 if r["n"] < end] == [r for r in recs if r["n"] < end]
    assert of(v10, i, "BREAKOUT") and not of(v10, i, "DONE")[:1] == [(end, "DONE", 0, "BROKEN", 0)]
    if d > 0:
        assert of(v10, i, "PLACE_LIMIT")[0][0] == pl10


@D
@pytest.mark.parametrize("name", ["t1_wick_out_ok", "t1_close_on_edge"])
def test_wicks_out_and_bodies_on_the_edge_still_trade(exe, tmp_path, d, name):
    """A T1 wick below the box (body in it), and a T1 body that closes exactly on the box's edge with a C1 opening
    there: allowed, the setup's records are those of v10, and it trades (limits on 23 when tapped from above)."""
    bars = side(V11[name], d)
    recs = run(exe, tmp_path, bars, setup_type=REV, rev_body_box=1, **EA)
    i = sid(recs)
    assert mine(recs, i) == mine(run(exe, tmp_path, bars, setup_type=REV, **EA), i)
    assert of(recs, i, "BREAKOUT") and not [r for r in recs if r["id"] == i and r.get("bo")]
    if d > 0:
        assert of(recs, i, "PLACE_LIMIT")[0][0] == 23


@D
def test_one_tick_below_the_edge_is_out(exe, tmp_path, d):
    """The boundary: T1 closing at 98.00 (the box's bottom) is in the box; at 97.99 it is out."""
    seq = V11["t1_close_on_edge"]
    o, h, l_, _ = seq[17]
    out = seq[:17] + [bar(o, h, l_, 97.99)] + seq[18:]
    recs = run(exe, tmp_path, side(out, d), setup_type=REV, rev_body_box=1, **EA)
    assert of(recs, sid(recs), "DONE") == [(17, "DONE", 0, "BROKEN", 1)]


@D
def test_a_c_candle_opening_below_the_box_is_out(exe, tmp_path, d):
    """The whole body counts, not only the close: C1 opening below the box and closing in it ends the setup."""
    seq = V11["t1_wick_out_ok"]
    c1 = bar(97.9, 99.1, 97.85, 99.0)                          # 18: opens below the box (97.90), closes in it
    out = seq[:18] + [c1] + seq[19:]
    recs = run(exe, tmp_path, side(out, d), setup_type=REV, rev_body_box=1, **EA)
    assert of(recs, sid(recs), "DONE") == [(18, "DONE", 0, "BROKEN", 11)]


@D
def test_the_owners_c1c2_example_is_unchanged(exe, tmp_path, d):
    """The v9 example (T1 body in the box, C1 and C2 above it) trades exactly as before."""
    bars = side(v9_sequences()["c1c2"], d)
    a = run(exe, tmp_path, bars, setup_type=REV, rev_body_box=1, **EA)
    b = run(exe, tmp_path, bars, setup_type=REV, **EA)
    i = sid(a)
    assert mine(a, i) == mine(b, i) and of(a, i, "PLACE_LIMIT")


@pytest.mark.parametrize("name", list(V11))
def test_continuation_setups_are_not_affected(exe, tmp_path, name):
    """CONTINUATION: the same records with and without the rule (a continuation setup already ends at a wick beyond
    the box). With BOTH, the continuation setups' records are unchanged too."""
    for bars in (V11[name], mirror(V11[name])):
        assert run(exe, tmp_path, bars, rev_body_box=1, **EA) == run(exe, tmp_path, bars, **EA)
        a = run(exe, tmp_path, bars, setup_type=BOTH, rev_body_box=1, **EA)
        b = run(exe, tmp_path, bars, setup_type=BOTH, **EA)
        assert [r for r in a if r.get("kind") == 0] == [r for r in b if r.get("kind") == 0]


def test_a_pullback_visit_is_not_a_touch(exe, tmp_path):
    """Only the touches (T1, T2) are checked, not a later pullback visit: after T1 (17, wick 97.5), C1, C2 and the
    rejection, a red candle comes back into the box and closes below it without closing below the T1 wick: with
    max_touches = 1 that visit is the pullback, not T2, and the setup goes on."""
    up = v11_up()
    seq = up + [bar(100.1, 100.15, 97.5, 98.2), bar(98.2, 99.1, 98.15, 99.0), bar(99.0, 100.6, 98.95, 100.5),
                bar(100.5, 100.6, 100.0, 100.1), bar(100.1, 100.15, 97.7, 97.8), bar(98.0, 100.6, 97.95, 100.5),
                bar(100.5, 101.6, 100.4, 100.45), bar(100.45, 100.5, 100.0, 100.1)] + v11_drop(100.1)
    recs = run(exe, tmp_path, seq, setup_type=REV, rev_body_box=1, max_touches=1, **EA)
    i = sid(recs)
    assert [r["n"] for r in recs if r["id"] == i and r["ev"] == "TOUCH"] == [17]
    assert not of(recs, i, "DONE") and of(recs, i, "BREAKOUT")
    # a pullback visit of two candles: the second one (22) closes below the box; still not checked
    two_c = up + [bar(100.1, 100.15, 97.5, 98.2), bar(98.2, 99.1, 98.15, 99.0), bar(99.0, 100.6, 98.95, 100.5),
                  bar(100.5, 100.6, 100.0, 100.1), bar(100.1, 100.15, 97.7, 98.1), bar(98.1, 98.2, 97.6, 97.8),
                  bar(98.0, 100.6, 97.95, 100.5), bar(100.5, 101.6, 100.4, 100.45),
                  bar(100.45, 100.5, 100.0, 100.1)] + v11_drop(100.1)
    for b in (two_c, mirror(two_c)):
        rr = run(exe, tmp_path, b, setup_type=REV, rev_body_box=1, max_touches=1, **EA)
        assert not of(rr, sid(rr), "DONE") and of(rr, sid(rr), "BREAKOUT")
    two = run(exe, tmp_path, seq, setup_type=REV, rev_body_box=1, **EA)       # max_touches = 2: that visit is T2
    assert of(two, sid(two), "DONE") == [(21, "DONE", 0, "BROKEN", 2)]


@D
def test_only_the_needed_rejection_candles_are_checked(exe, tmp_path, d):
    """"C1 and C2": T1 (17), C1 (18) in the box, C2 (19) above it, away (20), a pullback visit (21, one touch allowed)
    that closes below the box, then a green candle (22, C3) that opens below the box. With InpRevRejCandles = 2, C3 is
    not one of the needed candles and the setup goes on; with InpRevRejCandles = 3 it is, and the setup ends."""
    up = v11_up()
    seq = up + [bar(100.1, 100.15, 97.5, 98.2), bar(98.2, 99.1, 98.15, 99.0), bar(99.0, 100.6, 98.95, 100.5),
                bar(100.5, 100.6, 100.0, 100.1), bar(100.1, 100.15, 97.7, 97.8), bar(97.8, 100.6, 97.75, 100.5),
                bar(100.5, 101.6, 100.4, 100.45), bar(100.45, 100.5, 100.0, 100.1)] + v11_drop(100.1)
    bars = side(seq, d)
    kv = dict(setup_type=REV, rev_body_box=1, max_touches=1)
    two = run(exe, tmp_path, bars, **kv, **EA)
    assert not of(two, sid(two), "DONE") and of(two, sid(two), "BREAKOUT")
    three = run(exe, tmp_path, bars, **kv, **{**EA, "rev_rej_c": 3})
    assert of(three, sid(three), "DONE") == [(22, "DONE", 0, "BROKEN", 13)]


RANDOM = [(111, dict(setup_type=REV)), (112, dict(setup_type=BOTH)), (113, dict(setup_type=REV, max_setups=5)),
          (114, dict(setup_type=REV, rev_level=1)), (115, dict(setup_type=BOTH, rev_level=2)),
          (116, dict(setup_type=REV, anticipate=0))]


@pytest.mark.parametrize("case", RANDOM, ids=[f"seed{c[0]}" for c in RANDOM])
def test_random_series(exe, tmp_path, case):
    """Random series, recomputed from the bars:
    - every DONE with bo names a candle whose body is out of the box on the far side, on a reversal setup;
    - every touch candle of a reversal setup that goes on has its body in the box (or on its near side);
    - no reversal setup breaks out after a touch candle with its body out;
    - the records before the first body-out end equal those without the rule."""
    seed, kv = case
    kv = {**EA, **kv}
    bars = _bars(seed, 4000)
    recs = run(exe, tmp_path, bars, rev_body_box=1, **kv)
    base = run(exe, tmp_path, bars, **kv)
    ends = [r for r in recs if r["ev"] == "DONE" and r.get("bo")]
    assert len(ends) >= 5
    for r in ends:
        assert r["kind"] == 1 and r["reason"] == "BROKEN" and body_out(bars[r["n"]], r["zdir"], r["zb"], r["zt"]), r
        if r["bo"] < 10:
            assert any(x["id"] == r["id"] and x["ev"] == "TOUCH" and x["k"] == r["bo"] for x in recs), r
    ended = {r["id"]: r["n"] for r in recs if r["ev"] in ("DONE", "CLOSED")}
    for r in recs:
        if r["ev"] == "TOUCH" and r["kind"] == 1 and ended.get(r["id"]) != r["n"]:
            assert not body_out(bars[r["n"]], r["zdir"], r["zb"], r["zt"]), r
    t0 = min(r["n"] for r in ends)
    assert [r for r in recs if r["n"] < t0] == [r for r in base if r["n"] < t0]
    assert len(base) != len(recs) or base != recs


@pytest.mark.parametrize("kv", [dict(setup_type=REV, max_setups=3), dict(setup_type=BOTH)])
def test_v11_is_causal(exe, tmp_path, kv):
    """CLAUDE.md causality rule: the records up to bar t do not depend on later bars."""
    kv = {**EA, **kv, "rev_body_box": 1}
    bars = _bars(57, 1500)
    full = run(exe, tmp_path, bars, **kv)
    other = _bars(93, 1500)
    for t in (300, 701, 1111):
        cut = run(exe, tmp_path, bars[:t + 1], **kv)
        assert full[:len(cut)] == cut, t
        sh = bars[t][3] - other[t + 1][0]
        alt = run(exe, tmp_path, bars[:t + 1] + [tuple(x + sh for x in b) for b in other[t + 1:]], **kv)
        assert alt[:len(cut)] == cut, t
