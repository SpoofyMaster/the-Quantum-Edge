"""BprFvgEA v9: the reversal needs a rejection of at least 2 candles in the BPR's direction after T1, checked on the
C++ transliteration of the MQL5 detector only (EA only, like v5-v8).

The owner's example of 2026-10-17 (a screenshot of the v7 chart with a drawing: T1, then C1 and C2): "the EA is
considering reversal even when price make his T1 and the following candle made the breakout ... the real setup is when
after T1 price must absolutely make a rejection which a minimum 2 candles successive or not its not matter, the
important is they must be on the opposite direction before price comes back for breakout and confirme reversal ... a
minimum 2 Green candles for a bullish rejection and 2 RED candles for a bearish rejection".

Detector param revRejCandles (EA input InpRevRejCandles, harness key rev_rej_c; EA default 2, detector default 0 = v8):
after the T1 candle, a candle in the BPR's direction (bullish for a bullish BPR) that does not close beyond the
reversal level counts; candles of a breakout in progress (BREAK) neither count nor restart the count. A close beyond
the level that is not the breakout (price back too early) restarts the count and is no touch: it does not become T2
and its wick does not move the reversal level. A failed breakout (BREAK_FAIL) keeps the count. The reversal breakout
candle needs at least revRejCandles counted candles before it. The harness prints the count as "rc" (ext=1) on every
record: on a BREAKOUT it is the count the breakout used. Skipped without g++.
"""
import shutil

import pytest

from bk_scenarios import bar, mirror, v7_sequences, v8_sequences, v9_drop, v9_sequences, v9_t1
from test_bpr_breakout_v6_setups import BOTH, CONT, REV, SP, _bars, _check, short_fib
from test_bpr_breakout_v6_setups import exe as _exe_fixture  # noqa: F401 (module-scoped harness build)
from test_bpr_breakout_v6_setups import run as _run6
from test_bpr_breakout_v7_reversal import _check7

exe = _exe_fixture
pytestmark = pytest.mark.skipif(shutil.which("g++") is None, reason="g++ not installed")
V9 = v9_sequences()
EA9 = dict(anticipate=1, t1_wait=0, rev_fvg=0, rev_rej_c=2)      # the EA's v9 defaults for the EA-only switches
EA8 = dict(anticipate=1, t1_wait=0, rev_fvg=0)                   # v8 (rev_rej_c 0)
D = pytest.mark.parametrize("d", [1, -1], ids=["bullish-BPR", "bearish-BPR"])
C1 = bar(99.6, 100.3, 99.55, 100.2)                              # a green candle that closes back above the zone


def run(exe, tmp_path, bars, hold=50, **kv):
    kv.setdefault("ext", 1)
    return _run6(exe, tmp_path, bars, hold=hold, **kv)


def side(bars, d):
    return bars if d > 0 else mirror(bars)


def px(d, x):
    return x if d > 0 else round(200.0 - x, 2)


def main(recs, d):
    """the ids of the hand-built BPR's setups: ARMED on bar 13 in the BPR's direction d"""
    return [r["id"] for r in recs if r["ev"] == "ARMED" and r["n"] == 13 and r["dir"] == d]


def of(recs, i, ev=None, n=None):
    return [r for r in recs if r["id"] == i and (ev is None or r["ev"] == ev) and (n is None or r["n"] == n)]


def rev_id(recs, d):
    return next(i for i in main(recs, d) if of(recs, i, "ARMED")[0]["kind"] == 1)


def breakouts(recs, i):
    return [(r["n"], r["rc"]) for r in of(recs, i, "BREAKOUT")]


def t1_then(x, last_close):
    """T1 on 17 (the owner's tap from above), then the candles x (from 18), then the drop from last_close"""
    return v9_t1() + x + v9_drop(last_close)


# ---------------------------------------------------------------------------------------------------------------
# the owner's drawing and complaint
# ---------------------------------------------------------------------------------------------------------------
@D
def test_c1_c2_then_the_reversal(exe, tmp_path, d):
    """T1 on 17, C1 18 and C2 19 (two candles in the BPR's direction), the top of the reaction 101.6 on 20, the drop:
    22 closes beyond the T1 wick (BREAKOUT, 2 rejection candles), 23 again: CONFIRM and the limits at once
    (100 % = 101.6, 0 % = 98.2), moved on the new low 24, the target on 27."""
    recs, _ = run(exe, tmp_path, side(V9["c1c2"], d), setup_type=REV, **EA9)
    i = rev_id(recs, d)
    assert [r["n"] for r in of(recs, i, "TOUCH")] == [17] and [r["n"] for r in of(recs, i, "REJECT")] == [18]
    assert of(recs, i, "REJECT")[0]["rc"] == 1
    assert breakouts(recs, i) == [(22, 2)] and of(recs, i, "BREAKOUT")[0]["lvl"] == pytest.approx(px(d, 99.0))
    pl = of(recs, i, "PLACE_LIMIT", 23)
    assert len(pl) == 3 and pl[0]["O"] == pytest.approx(px(d, 101.6)) and pl[0]["X"] == pytest.approx(px(d, 98.2))
    if d > 0:
        assert [r["P"] for r in pl] == pytest.approx(short_fib(101.6, 98.2))
        assert all(r["SL"] == pytest.approx(101.6 + 0.1 + SP) for r in pl)
    assert of(recs, i, "CLOSED", 27)


@D
@pytest.mark.parametrize("st", [REV, BOTH])
@pytest.mark.parametrize("lv", [0, 2], ids=["DEEPEST", "LAST"])
def test_t1_one_candle_then_the_break_is_no_reversal(exe, tmp_path, d, st, lv):
    """The owner's complaint: T1 on 17, ONE candle in the BPR's direction (18), then the drop at once (19 / 20). v8 took
    it as the reversal (BREAKOUT 19, CONFIRM 20); v9 does not, and the later green candle back above the T1 wick (23)
    is one rejection candle since the last close below it: 24 is no reversal either."""
    v8, _ = run(exe, tmp_path, side(V9["one_green_then_break"], d), setup_type=st, rev_level=lv, **EA8)
    assert breakouts(v8, rev_id(v8, d))[0] == (19, 1)
    v9, _ = run(exe, tmp_path, side(V9["one_green_then_break"], d), setup_type=st, rev_level=lv, **EA9)
    i = rev_id(v9, d)
    assert not of(v9, i, "BREAKOUT") and not of(v9, i, "CONFIRM") and not of(v9, i, "PLACE_LIMIT")


@D
def test_rejection_candles_need_not_follow_each_other(exe, tmp_path, d):
    """C1 18, a red candle above the zone (19), C2 20: two rejection candles, the reversal breakout on 23."""
    recs, _ = run(exe, tmp_path, side(V9["green_red_green"], d), setup_type=REV, **EA9)
    i = rev_id(recs, d)
    assert breakouts(recs, i) == [(23, 2)] and of(recs, i, "CONFIRM", 24) and of(recs, i, "PLACE_LIMIT", 24)


@D
@pytest.mark.parametrize("lv", [0, 1, 2], ids=["DEEPEST", "T1", "LAST"])
def test_a_close_beyond_the_level_restarts_the_count(exe, tmp_path, d, lv):
    """C1 18; 19 closes below the T1 wick 99.0 (1 rejection candle: no reversal); 20 back above (1, counted from 19);
    21 below again (no reversal); 22 and 23 above (2 since 21); 24 the reversal breakout at the T1 wick, 25 confirms
    with the 100 % at the last bounce (100.6). 19 and 21 are no touches, so with every InpRevLevel the level stays the
    T1 wick. v8 broke out on 19 and 21 (each failed) before 24."""
    recs, _ = run(exe, tmp_path, side(V9["reset_after_early_break"], d), setup_type=REV, rev_level=lv, **EA9)
    i = rev_id(recs, d)
    assert breakouts(recs, i) == [(24, 2)] and not of(recs, i, "BREAK_FAIL")
    assert of(recs, i, "BREAKOUT")[0]["lvl"] == pytest.approx(px(d, 99.0))
    assert [r["n"] for r in of(recs, i, "TOUCH")] == [17]
    pl = of(recs, i, "PLACE_LIMIT", 25)
    assert len(pl) == 3 and pl[0]["O"] == pytest.approx(px(d, 100.6))
    v8, _ = run(exe, tmp_path, side(V9["reset_after_early_break"], d), setup_type=REV, rev_level=lv, **EA8)
    assert [n for n, _ in breakouts(v8, rev_id(v8, d))] == [19, 21, 24]


@D
def test_a_failed_breakout_keeps_the_count(exe, tmp_path, d):
    """T1 17, C1 18, C2 19: the breakout on 22 (2 rejection candles). 23 closes back above the T1 wick (BREAK_FAIL);
    the rejection came before price came back, so the count stays: 24 closes below the wick again, the breakout (still
    2), 25 confirms, the trade reaches its target on 28, as in v8."""
    bars = V9["failed_break_keeps_count"]
    assert bars[:22] == V9["c1c2"][:22]
    for kv in (EA9, EA8):
        recs, _ = run(exe, tmp_path, side(bars, d), setup_type=REV, **kv)
        i = rev_id(recs, d)
        assert [n for n, _ in breakouts(recs, i)] == [22, 24] and [r["n"] for r in of(recs, i, "BREAK_FAIL")] == [23]
        assert of(recs, i, "CONFIRM", 25) and of(recs, i, "PLACE_LIMIT", 25) and of(recs, i, "CLOSED", 28), kv
    recs, _ = run(exe, tmp_path, side(bars, d), setup_type=REV, **EA9)
    assert breakouts(recs, rev_id(recs, d)) == [(22, 2), (24, 2)]


@D
@pytest.mark.parametrize("lv", [0, 2], ids=["DEEPEST", "LAST"])
def test_a_close_through_the_bpr_is_no_touch(exe, tmp_path, d, lv):
    """T1 17 (wick 99.0), C1 18, then 19 crashes through the whole BPR and closes below it (97.6): one rejection
    candle, so no reversal; it is no T2 either, so its low (97.5) never becomes the level. 20 and 21 come back above
    the zone (2 rejection candles), 22 closes below the T1 wick: the reversal breakout at 99.0, limits on 23."""
    bars = v9_t1() + [C1, bar(100.2, 100.25, 97.5, 97.6), bar(97.6, 99.2, 97.55, 99.1), bar(99.1, 100.4, 99.05, 100.3),
                      bar(100.3, 100.35, 98.6, 98.7), bar(98.7, 98.75, 98.3, 98.4), bar(98.4, 98.5, 97.9, 98.0),
                      bar(98.0, 99.6, 97.95, 99.5), bar(99.5, 99.55, 97.4, 97.5)]
    recs, _ = run(exe, tmp_path, side(bars, d), setup_type=REV, rev_level=lv, **EA9)
    i = rev_id(recs, d)
    assert [r["n"] for r in of(recs, i, "TOUCH")] == [17]
    assert breakouts(recs, i) == [(22, 2)] and of(recs, i, "BREAKOUT")[0]["lvl"] == pytest.approx(px(d, 99.0))
    assert of(recs, i, "CONFIRM", 23) and of(recs, i, "PLACE_LIMIT", 23)


@D
def test_v8_mode_keeps_the_v8_touch(exe, tmp_path, d):
    """rev_rej_c 0 is v8 exactly. A REVERSAL setup kept for its touch entry only (the reversal's direction is filtered
    out) takes the close below the T1 wick on 19 as T2, as v8 did. With 2 rejection candles needed, that close is no
    touch."""
    kv = dict(setup_type=REV, touch_entry=1, direction=1 if d > 0 else 2)
    v8, _ = run(exe, tmp_path, side(V9["one_green_then_break"], d), **kv, **EA8)
    assert [r["n"] for r in of(v8, rev_id(v8, d), "TOUCH")] == [17, 19]
    v9, _ = run(exe, tmp_path, side(V9["one_green_then_break"], d), **kv, **EA9)
    assert [r["n"] for r in of(v9, rev_id(v9, d), "TOUCH")] == [17]


# ---------------------------------------------------------------------------------------------------------------
# what counts as a rejection candle (bullish BPR; the mirrored bars check the bearish side)
# ---------------------------------------------------------------------------------------------------------------
G2 = bar(100.2, 100.8, 100.15, 100.7)                       # a second green candle above the zone
CASES = [
    # (name, candles after T1, last close, number of rejection candles needed, breakout bar or None)
    ("two-green", [C1, G2], 100.7, 2, 20),
    ("one-green", [C1], 100.2, 2, None),
    ("one-green-n1", [C1], 100.2, 1, 19),
    ("two-green-n3", [C1, G2], 100.7, 3, None),
    ("three-green-n3", [C1, G2, bar(100.7, 101.2, 100.65, 101.1)], 101.1, 3, 21),
    # a doji (close = open) is no rejection candle
    ("green-doji", [C1, bar(100.2, 100.5, 100.0, 100.2)], 100.2, 2, None),
    # a red candle is none either
    ("green-red", [C1, bar(100.2, 100.3, 100.0, 100.05)], 100.05, 2, None),
    # a green candle that closes exactly at the T1 wick (99.0) is not beyond it: it counts
    ("green-red-green-at-level", [C1, bar(100.2, 100.25, 99.0, 99.05), bar(98.95, 99.05, 98.9, 99.0)], 99.0, 2, 21),
    # 1 tick lower it closes beyond the wick: it does not count and restarts the count
    ("green-red-green-below-level", [C1, bar(100.2, 100.25, 99.0, 99.05), bar(98.95, 99.05, 98.9, 98.99)], 98.99, 2,
     None),
]


@D
@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
def test_rejection_candle_rules(exe, tmp_path, d, case):
    _, x, last, n, brk = case
    recs, _ = run(exe, tmp_path, side(t1_then(x, last), d), setup_type=REV, rev_level=1, anticipate=1, t1_wait=0,
                  rev_fvg=0, rev_rej_c=n)
    got = breakouts(recs, rev_id(recs, d))
    assert [b for b, _ in got][:1] == ([brk] if brk else []), got
    if brk:
        assert got[0][1] >= n


@D
def test_the_t1_candle_itself_does_not_count(exe, tmp_path, d):
    """A green T1 candle (17, wick 99.0, closes inside the zone) and one green candle after it: one rejection candle,
    so no reversal with 2; with 1 the breakout is on 19."""
    t1 = v9_t1()[:17] + [bar(99.3, 99.8, 99.0, 99.7)]
    bars = side(t1 + [C1] + v9_drop(100.2), d)
    two, _ = run(exe, tmp_path, bars, setup_type=REV, **EA9)
    assert not of(two, rev_id(two, d), "BREAKOUT")
    one, _ = run(exe, tmp_path, bars, setup_type=REV, anticipate=1, t1_wait=0, rev_fvg=0, rev_rej_c=1)
    assert breakouts(one, rev_id(one, d)) == [(19, 1)]


@D
def test_the_rejection_is_still_needed(exe, tmp_path, d):
    """Two green candles that stay inside the zone after T1 (no candle leaves it, no close above it): no rejection,
    so no reversal, whatever the count (InpRevNeedRejection)."""
    x = [bar(99.6, 99.85, 99.5, 99.8), bar(99.8, 99.88, 99.7, 99.85)]
    recs, _ = run(exe, tmp_path, side(t1_then(x, 99.85), d), setup_type=REV, **EA9)
    i = rev_id(recs, d)
    assert not of(recs, i, "REJECT") and not of(recs, i, "BREAKOUT")


# ---------------------------------------------------------------------------------------------------------------
# the owner's earlier examples, the continuation, random series, causality
# ---------------------------------------------------------------------------------------------------------------
@D
@pytest.mark.parametrize("name,seqs,brk,lim", [
    ("tap_from_above", "v8", 23, 24),                 # T1 17, then 3 green candles (18-20)
    ("late_break", "v8", 323, 324),                   # the same, the drop 300 bars later
    ("late_t2", "v8", 324, 325),
    ("owner_example", "v7", 28, 31),                  # the v7 example (T1 14, T2 17): green candles 15, 19, 20, ...
])
def test_earlier_examples_still_trade(exe, tmp_path, d, name, seqs, brk, lim):
    bars = (v8_sequences() if seqs == "v8" else v7_sequences())[name]
    kv = EA9 if seqs == "v8" else dict(rev_rej_c=2)
    recs, _ = run(exe, tmp_path, side(bars, d), setup_type=REV, **kv)
    i = rev_id(recs, d)
    assert breakouts(recs, i)[0][0] == brk and breakouts(recs, i)[0][1] >= 2 and of(recs, i, "PLACE_LIMIT", lim)


@D
@pytest.mark.parametrize("name", ["late_t1", "one_candle_reaction"])
def test_earlier_one_candle_examples_no_longer_trade(exe, tmp_path, d, name):
    """v8 sequences with a single candle in the BPR's direction between T1 and the drop: v8 traded them; v9 does not."""
    bars = side(v8_sequences()[name], d)
    v8, _ = run(exe, tmp_path, bars, setup_type=REV, **EA8)
    assert of(v8, rev_id(v8, d), "PLACE_LIMIT")
    v9, _ = run(exe, tmp_path, bars, setup_type=REV, **EA9)
    assert not of(v9, rev_id(v9, d), "BREAKOUT")


@D
def test_warmup_keeps_the_count(exe, tmp_path, d):
    """trade_from 20: T1 and C1 / C2 come during the warm-up; the setup goes on with its count and trades (22 / 23)."""
    recs, _ = run(exe, tmp_path, side(V9["c1c2"], d), setup_type=REV, trade_from=20, **EA9)
    i = rev_id(recs, d)
    assert breakouts(recs, i) == [(22, 2)] and of(recs, i, "PLACE_LIMIT", 23)


def test_the_continuation_is_unchanged(exe, tmp_path):
    """rev_rej_c changes nothing for continuation setups (CONTINUATION, and the continuation setups of BOTH)."""
    for seed in (91, 92):
        bars = _bars(seed, 3000)
        a, _ = run(exe, tmp_path, bars, hold=60, setup_type=CONT, **EA8)
        b, _ = run(exe, tmp_path, bars, hold=60, setup_type=CONT, **EA9)
        assert all(r["rc"] == 0 for r in b)                     # a continuation setup never counts
        assert [{k: v for k, v in r.items() if k != "rc"} for r in a] == [{k: v for k, v in r.items() if k != "rc"}
                                                                           for r in b]
        a, _ = run(exe, tmp_path, bars, hold=60, setup_type=BOTH, **EA8)
        b, _ = run(exe, tmp_path, bars, hold=60, setup_type=BOTH, **EA9)
        ca = {r["id"] for r in a if r["ev"] == "ARMED" and r["kind"] == 0}
        cb = {r["id"] for r in b if r["ev"] == "ARMED" and r["kind"] == 0}
        # ids are shared by both kinds, so compare the continuation records by their bar, event and prices
        def key(rs, ids):
            return [(r["n"], r["ev"], r["k"], r["P"], r["O"], r["X"]) for r in rs if r["id"] in ids]
        sa, sb = key(a, ca), key(b, cb)
        # the reversal setups take the slot at other times in v8 and v9, so only the records before any decision are
        # comparable one to one: every continuation BREAKOUT / CONFIRM of v8 exists in v9 at the same bar
        brk = lambda s: [(n, e) for n, e, *_ in s if e in ("TOUCH", "REJECT", "BREAKOUT", "CONFIRM")]  # noqa: E731
        assert brk(sa) == brk(sb)


def expected_count(bars, recs, i, brk, lvl, zd):
    """the rejection candles before the breakout on bar brk, recounted from the bars and the setup's own breakout
    records: after T1, outside a breakout in progress (the bars after a BREAKOUT up to its BREAK_FAIL), in the BPR's
    direction and not closing beyond lvl; a close beyond lvl that is not a breakout restarts the count"""
    beyond = (lambda c: c < lvl) if zd > 0 else (lambda c: c > lvl)
    t1 = next(x["n"] for x in recs if x["id"] == i and x["ev"] == "TOUCH")
    brks = {x["n"] for x in recs if x["id"] == i and x["ev"] == "BREAKOUT"}
    fails = sorted(x["n"] for x in recs if x["id"] == i and x["ev"] == "BREAK_FAIL")
    in_break = set()
    for b in brks:
        f = next((f for f in fails if f > b), None)
        in_break |= set(range(b + 1, (f if f is not None else brk) + 1))
    n = 0
    for u in range(t1 + 1, brk):
        o, _, _, c = bars[u]
        if u in in_break or u in brks:
            continue
        if beyond(c):
            n = 0
        elif (c > o) if zd > 0 else (c < o):
            n += 1
    return n


RANDOM9 = [
    (101, dict(setup_type=REV, rev_level=1, **EA9)),
    (102, dict(setup_type=BOTH, rev_level=1, **EA9)),
    (103, dict(setup_type=REV, rev_level=1, rev_rej_c=3, anticipate=1, t1_wait=0, rev_fvg=0)),
    (104, dict(setup_type=BOTH, rev_level=1, touch_entry=1, **EA9)),
    (105, dict(setup_type=REV, rev_level=0, **EA9)),
    (106, dict(setup_type=BOTH, rev_level=2, **EA9)),
]


@pytest.mark.parametrize("case", RANDOM9, ids=[f"seed{c[0]}" for c in RANDOM9])
def test_random_series_rejection_count(exe, tmp_path, case):
    """Every reversal BREAKOUT has at least revRejCandles rejection candles. With InpRevLevel = T1 the level is fixed
    at the T1 wick, so the count is also recomputed from the bars and must equal the one the breakout carries. A T2
    (any InpRevLevel) never closes beyond the T1 wick: such a close is no touch. The v6 / v7 invariants hold."""
    seed, kv = case
    bars = _bars(seed, 4000)
    recs, _ = run(exe, tmp_path, bars, hold=60, **kv)
    _check(recs, kv)
    _check7(recs, bars, kv)
    n = 0
    for r in recs:
        if r.get("kind") != 1:              # the touch entry's fill records carry no kind
            continue
        if r["ev"] == "BREAKOUT":
            assert r["rc"] >= kv["rev_rej_c"], r
            if kv["rev_level"] == 1:
                want = expected_count(bars, recs, r["id"], r["n"], r["lvl"], r["zdir"])
                assert r["rc"] == want, (r, want)
            n += 1
        if r["ev"] == "TOUCH" and r["k"] == 2:
            t1 = next(x["n"] for x in recs if x["id"] == r["id"] and x["ev"] == "TOUCH")
            w = bars[t1][2] if r["zdir"] > 0 else bars[t1][1]
            c = bars[r["n"]][3]
            assert (c >= w) if r["zdir"] > 0 else (c <= w), (r, w, c)
    assert n >= 5


@pytest.mark.parametrize("kv", [dict(setup_type=BOTH, **EA9), dict(setup_type=REV, rev_level=1, **EA9)],
                         ids=["both", "rev-t1"])
def test_v9_rule_is_causal(exe, tmp_path, kv):
    """CLAUDE.md causality rule: the records up to bar t do not depend on later bars."""
    bars = _bars(57, 1500)
    full, _ = run(exe, tmp_path, bars, hold=60, **kv)
    other = _bars(93, 1500)
    for t in (300, 701, 1111):
        cut, _ = run(exe, tmp_path, bars[:t + 1], hold=60, **kv)
        assert full[:len(cut)] == cut, t
        sh = bars[t][3] - other[t + 1][0]
        alt, _ = run(exe, tmp_path, bars[:t + 1] + [tuple(x + sh for x in b) for b in other[t + 1:]], hold=60, **kv)
        assert alt[:len(cut)] == cut, t
