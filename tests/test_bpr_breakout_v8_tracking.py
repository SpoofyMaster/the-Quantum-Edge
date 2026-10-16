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
import pytest

from bk_scenarios import bar, mirror, v7_sequences, v8_sequences
from test_bpr_breakout_v6_setups import BOTH, CONT, FVG, REV, SP, _bars, _check, short_fib
from test_bpr_breakout_v6_setups import exe as _exe_fixture  # noqa: F401 (module-scoped harness build)
from test_bpr_breakout_v6_setups import run as _run6
from test_bpr_breakout_v7_reversal import _check7

exe = _exe_fixture
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


def ladder(nblocks, step=3.0):
    """BPRs that price never comes back to: the prefix's BPR pattern repeated, each block 3.0 higher (its lows stay
    above every earlier zone). One bullish BPR per block (10 bars)."""
    out = []
    for b in range(nblocks):
        k = b * step
        for i in range(4):
            o = 100.0 + k + (0.1 if i % 2 else 0.0)
            c = o + (0.1 if i % 2 == 0 else -0.1)
            out.append(bar(o, max(o, c) + 0.02, min(o, c) - 0.02, c))
        out += [bar(100.0 + k, 100.05 + k, 99.9 + k, 99.95 + k), bar(99.95 + k, 99.97 + k, 97.98 + k, 98.0 + k),
                bar(97.4 + k, 97.5 + k, 97.0 + k, 97.1 + k), bar(97.1 + k, 98.0 + k, 97.05 + k, 97.9 + k),
                bar(97.9 + k, 99.92 + k, 97.88 + k, 99.9 + k), bar(99.95 + k, 100.3 + k, 99.95 + k, 100.2 + k)]
    return out


# ---------------------------------------------------------------------------------------------------------------
# the owner's drawing: tap from above, reaction, break of the T1 wick
# ---------------------------------------------------------------------------------------------------------------
@D
def test_tap_from_above_limits_at_the_second_close(exe, tmp_path, d):
    """REVERSAL with the EA's v8 defaults. The BPR forms on 13, price goes up and comes back: T1 on 17 (wick 99.0),
    rejection 19, the T1 wick broken on 23 and again on 24. The sell limits go in on 24, the second close (100 % = 101.6,
    0 % = 98.2), move on 25 to the new low 97.6, the 50 % (99.6) fills on 27, the target is reached on 28."""
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
def test_breakout_window_counts_from_t1(exe, tmp_path, d):
    """setup_expiry_bars 2. v8: a continuation setup counts from T1 (315) and expires on 318; the v7 rules count from
    the creation (13) and end it on 16."""
    v8, _ = run(exe, tmp_path, seq("late_t1", d), setup_type=CONT, setup_expiry_bars=2, **EA8)
    assert key(of(v8, main(v8, d)[0], ev="DONE")) == [(318, "DONE", d, 0, "EXPIRED")]
    v7, _ = run(exe, tmp_path, seq("late_t1", d), setup_type=CONT, setup_expiry_bars=2, **V7R)
    assert key(of(v7, main(v7, d)[0], ev="DONE")) == [(16, "DONE", d, 0, "EXPIRED")]


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


def test_capacity_keeps_touched_setups(exe, tmp_path):
    """The first BPR is touched once (bar 10, T1) before the ladder goes on up: its reversal setup (id 2) stays in ZONE
    (long breakout window), its continuation setup (id 1) trades the move up and ends. At capacity the untouched
    setups make room (ids 3, 4, ...), never the touched one."""
    bars = ladder(80)
    bars = bars[:10] + [bar(100.2, 100.25, 99.8, 100.1)] + bars[10:]
    recs, _ = run(exe, tmp_path, bars, setup_type=BOTH, setup_expiry_bars=100000, **EA8)
    assert [r["n"] for r in recs if r["ev"] == "TOUCH" and r["id"] == 2] == [10]
    cap = [r["id"] for r in recs if r["ev"] == "DONE" and r["reason"] == "CAPACITY"]
    assert cap and 2 not in cap and cap[0] == 3 and len([r for r in recs if r["ev"] == "ARMED"]) == 160


@D
def test_warmup_setups_go_on_until_confirmed(exe, tmp_path, d):
    """trade_from 16: the BPR forms on 13, during the warm-up. v8: its setup goes on and trades the reversal (T1 on
    17, limits on 24). v7 rules: DONE(WARMUP) when the warm-up ends. A setup already confirmed during the warm-up
    (trade_from 25: confirmation on 24) ends in both."""
    v8, _ = run(exe, tmp_path, seq("tap_from_above", d), setup_type=REV, trade_from=16, **EA8)
    assert of(v8, sid(v8, 1), n=24, ev="PLACE_LIMIT")
    # warm-up ending between T1 (17) and the rejection (19): the setup is in ZONE and goes on as well
    zn, _ = run(exe, tmp_path, seq("tap_from_above", d), setup_type=REV, trade_from=19, **EA8)
    assert of(zn, main(zn, d)[0], n=24, ev="PLACE_LIMIT")
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
    was never touched."""
    seed, kv = case
    bars = _bars(seed, 4000)
    recs, _ = run(exe, tmp_path, bars, hold=60, **kv)
    assert {"CONFIRM", "PLACE_LIMIT"} <= {r["ev"] for r in recs}
    _check(recs, kv)
    _check7(recs, bars, kv)
    touched = {r["id"] for r in recs if r["ev"] == "TOUCH"}
    created = {r["id"]: r["n"] for r in recs if r["ev"] == "ARMED"}
    for r in recs:
        if r["ev"] == "DONE" and r["reason"] == "EXPIRED" and r["id"] not in touched:
            assert kv["t1_wait"] > 0 and r["n"] - created[r["id"]] == kv["t1_wait"] + 1, r
        if r["ev"] == "DONE" and r["reason"] == "CAPACITY":
            assert r["id"] not in touched, r


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
