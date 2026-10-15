"""BprFvgEA v7: the reversal setup as in the owner's example (2026-10-15), checked on the C++ transliteration of the
MQL5 detector only (EA only, like v5 / v6; the Python reference has no reversal).

The owner's screenshot is the v2 example ('two_touches') with the reversal drawn on it: after T1 / T2 and a rejection
from the BPR, price comes back and closes twice below the T1 wick; the Fibonacci runs from the top of the move (100 %,
stop) to the new low (0 %, target), entries at 50 / 61.8 / 71 %. Owner's words: "t1 + rejection from it and pullback
with breakout of T1 or T2 wick with closing below or above it. entry on Fib levels 50, 61 and 71".

v7 rules (detector params; harness keys in brackets):
- the reversal level (rev_level, InpRevLevel): 0 the DEEPEST wick of the T1 / T2 candles (default; the T1 wick in the
  example), 1 the T1 candle's wick, 2 the LAST touch candle's wick (v6);
- a rejection after T1 must come before the reversal breakout (rev_reject, InpRevNeedRejection; default on);
- a visit of the zone after the last touch is the pullback, not a third touch: it neither ends the reversal setup nor
  moves its level. If it is rejected, its bounce's top becomes the 100 % (the leg origin); if it turns into the
  breakout, the earlier top stays;
- setup_type BOTH follows each BPR as two setups (continuation first, then reversal), each on its own, so the reversal
  can trade after the continuation did; the touch entry belongs to the continuation one.
ext=1 makes the harness print kind / zdir / lvl / lvlBar. This checks decision logic, not MetaEditor compilation and
not MT5 order execution. Skipped without g++.
"""
import pytest

from bk_scenarios import base, mirror, scenarios, v6_sequences, v7_sequences
from test_bpr_breakout_v6_setups import CONT, REV, BOTH, FVG, SP, _bars, _check, short_fib
from test_bpr_breakout_v6_setups import exe as _exe_fixture  # noqa: F401 (module-scoped harness build)
from test_bpr_breakout_v6_setups import run as _run6

exe = _exe_fixture
V7 = v7_sequences()
V6 = v6_sequences()


def run(exe, tmp_path, bars, hold=50, **kv):
    kv.setdefault("ext", 1)
    return _run6(exe, tmp_path, bars, hold=hold, **kv)


def seq(name, d):
    return V7[name] if d > 0 else mirror(V7[name])


def sid(recs, kind):
    """the first touched setup of that kind (the hand-built BPR; the mirrored bars arm a second BPR first)"""
    return next(r["id"] for r in recs if r["ev"] == "TOUCH" and r["kind"] == kind)


def of(recs, kind, n=None, ev=None):
    i = sid(recs, kind)
    return [r for r in recs if r["id"] == i and (n is None or r["n"] == n) and (ev is None or r["ev"] == ev)]


def key(rs):
    return [(r["n"], r["ev"], r["dir"], r["k"], r["reason"]) for r in rs]


def px(d, x):
    """a bullish-side price on the side of BPR direction d (mirror: 200 - x)"""
    return x if d > 0 else round(200.0 - x, 2)


D = pytest.mark.parametrize("d", [1, -1], ids=["bullish-BPR", "bearish-BPR"])


# ---------------------------------------------------------------------------------------------------------------
# the owner's example
# ---------------------------------------------------------------------------------------------------------------
@D
def test_owner_example_reversal(exe, tmp_path, d):
    """REVERSAL: T1 14 (wick 99.5), T2 17 (wick 99.7), rejections 15 / 18; the drop: 28 is the first close below the
    T1 wick (BREAKOUT at 99.5, the T1 candle's), 29 the second (CONFIRM: 100 % = 101.6, the top of the move);
    30 makes the low 96.4 (0 %); 31 pulls back -> sell limits at 50 / 61.8 / 71 % of 101.6 -> 96.4, stop above
    101.6, target 96.4; 34 reaches the target."""
    recs, _ = run(exe, tmp_path, seq("owner_example", d), setup_type=REV)
    t = -d
    # before the breakout the reversal setup's records carry its level so far (CSV): after T2 the T1 wick still
    rj = of(recs, 1, n=18, ev="REJECT")[0]
    assert rj["lvl"] == pytest.approx(px(d, 99.5)) and rj["lvlBar"] == 14
    br = of(recs, 1, ev="BREAKOUT")
    assert key(br) == [(28, "BREAKOUT", t, 0, None)]
    assert br[0]["lvl"] == pytest.approx(px(d, 99.5)) and br[0]["lvlBar"] == 14
    conf = of(recs, 1, ev="CONFIRM")
    assert key(conf) == [(29, "CONFIRM", t, 0, None)]
    assert conf[0]["O"] == pytest.approx(px(d, 101.6))
    pl = of(recs, 1, n=31, ev="PLACE_LIMIT")
    assert [r["k"] for r in pl] == [1, 2, 3] and all(r["dir"] == t for r in pl)
    assert all(r["O"] == pytest.approx(px(d, 101.6)) and r["X"] == pytest.approx(px(d, 96.4)) for r in pl)
    if d > 0:
        assert [r["P"] for r in pl] == pytest.approx(short_fib(101.6, 96.4))
        assert all(r["SL"] == pytest.approx(101.6 + 0.1 + SP) and r["TP"] == pytest.approx(96.4 + SP) for r in pl)
    for r in pl:
        assert (r["SL"] < r["P"] < r["TP"]) if t > 0 else (r["TP"] < r["P"] < r["SL"])
    assert of(recs, 1, n=34, ev="CLOSED")


@D
def test_owner_example_both_trades_the_continuation_then_the_reversal(exe, tmp_path, d):
    """BOTH: the continuation setup trades the breakout up first (CONFIRM 20, limits 22, closed at the target 25), as
    with CONTINUATION; the BPR's reversal setup then trades the drop exactly as with REVERSAL."""
    bo, _ = run(exe, tmp_path, seq("owner_example", d), setup_type=BOTH)
    ct, _ = run(exe, tmp_path, seq("owner_example", d), setup_type=CONT)
    rv, _ = run(exe, tmp_path, seq("owner_example", d), setup_type=REV)
    strip = lambda rs: [{k: v for k, v in r.items() if k != "id"} for r in rs]  # noqa: E731
    assert strip(of(bo, 0)) == strip(of(ct, 0))
    assert [r["n"] for r in of(bo, 0, ev="CONFIRM")] == [20] and of(bo, 0, n=25, ev="CLOSED")
    assert strip(of(bo, 1)) == strip(of(rv, 1))
    assert [r["n"] for r in of(bo, 1, ev="PLACE_LIMIT")] == [31, 31, 31]
    assert of(bo, 0)[0]["id"] + 1 == of(bo, 1)[0]["id"]          # one BPR, two setups: continuation first


def test_owner_example_continuation_only(exe, tmp_path):
    """CONTINUATION (the default) trades the breakout up only, as in v2-v6."""
    recs, _ = run(exe, tmp_path, V7["owner_example"])
    assert all(r["kind"] == 0 for r in recs if "kind" in r)
    assert [r["dir"] for r in of(recs, 0, ev="CONFIRM")] == [1]


# ---------------------------------------------------------------------------------------------------------------
# the reversal level
# ---------------------------------------------------------------------------------------------------------------
@D
def test_level_deepest_t1_wick_when_t2_is_shallower(exe, tmp_path, d):
    """T1 wick 99.5, T2 wick 99.7. 18 closes at 99.6 (between): DEEPEST and T1 -> no breakout (18 is a pullback
    visit: no third touch, no DONE); 19 closes below 99.5 -> BREAKOUT at the T1 wick. LAST (v6) -> 18 breaks out at
    the T2 wick 99.7."""
    for lv in (0, 1):
        recs, _ = run(exe, tmp_path, seq("rev_level_between", d), setup_type=REV, rev_level=lv)
        assert key(of(recs, 1, n=18)) == [], lv
        br = of(recs, 1, ev="BREAKOUT")[0]
        assert (br["n"], br["lvl"], br["lvlBar"]) == (19, pytest.approx(px(d, 99.5)), 14), lv
    recs, _ = run(exe, tmp_path, seq("rev_level_between", d), setup_type=REV, rev_level=2)
    br = of(recs, 1, ev="BREAKOUT")[0]
    assert (br["n"], br["lvl"], br["lvlBar"]) == (18, pytest.approx(px(d, 99.7)), 16)


@D
def test_level_deepest_t2_wick_when_t2_is_deeper(exe, tmp_path, d):
    """T1 wick 99.6, T2 wick 99.4. 18 closes at 99.5 (between): DEEPEST and LAST -> no breakout, 19 breaks out at the
    T2 wick 99.4; T1 -> 18 breaks out at the T1 wick 99.6."""
    for lv in (0, 2):
        recs, _ = run(exe, tmp_path, seq("rev_level_deeper_t2", d), setup_type=REV, rev_level=lv)
        br = of(recs, 1, ev="BREAKOUT")[0]
        assert (br["n"], br["lvl"], br["lvlBar"]) == (19, pytest.approx(px(d, 99.4)), 16), lv
    recs, _ = run(exe, tmp_path, seq("rev_level_deeper_t2", d), setup_type=REV, rev_level=1)
    br = of(recs, 1, ev="BREAKOUT")[0]
    assert (br["n"], br["lvl"], br["lvlBar"]) == (18, pytest.approx(px(d, 99.6)), 14)


@D
def test_level_equal_wicks_keep_the_t1_candle(exe, tmp_path, d):
    """T1 and T2 wicks both 99.5: DEEPEST keeps the T1 candle (a strictly deeper wick only moves it); LAST takes T2."""
    recs, _ = run(exe, tmp_path, seq("rev_level_equal", d), setup_type=REV)
    br = of(recs, 1, ev="BREAKOUT")[0]
    assert (br["n"], br["lvl"], br["lvlBar"]) == (18, pytest.approx(px(d, 99.5)), 14)
    recs, _ = run(exe, tmp_path, seq("rev_level_equal", d), setup_type=REV, rev_level=2)
    assert of(recs, 1, ev="BREAKOUT")[0]["lvlBar"] == 16


@D
def test_one_touch_allowed_makes_t2_a_pullback(exe, tmp_path, d):
    """max_touches 1: the second visit (16, wick 99.4) is the pullback, not T2: the level stays the T1 wick 99.6 even
    with LAST, so 18 (close 99.5) breaks out."""
    recs, _ = run(exe, tmp_path, seq("rev_level_deeper_t2", d), setup_type=REV, rev_level=2, max_touches=1)
    assert [r["k"] for r in of(recs, 1, ev="TOUCH")] == [1]
    br = of(recs, 1, ev="BREAKOUT")[0]
    assert (br["n"], br["lvl"], br["lvlBar"]) == (18, pytest.approx(px(d, 99.6)), 14)


# ---------------------------------------------------------------------------------------------------------------
# rejection first
# ---------------------------------------------------------------------------------------------------------------
@D
def test_rejection_needed_before_the_reversal(exe, tmp_path, d):
    """v6 'reversal': 15 and 16 close below the T1 wick right after T1, without a rejection: no reversal by default
    (the BPR is then broken and the setup waits); with rev_reject=0 (v6) 15 is the breakout."""
    bars = V6["reversal"] if d > 0 else mirror(V6["reversal"])
    dflt, _ = run(exe, tmp_path, bars, setup_type=REV)
    assert not of(dflt, 1, ev="BREAKOUT") and not of(dflt, 1, ev="REJECT")
    v6, _ = run(exe, tmp_path, bars, setup_type=REV, rev_reject=0)
    assert key(of(v6, 1, n=15)) == [(15, "BREAKOUT", -d, 0, None)]


# ---------------------------------------------------------------------------------------------------------------
# the pullback into the zone and the 100 %
# ---------------------------------------------------------------------------------------------------------------
@D
def test_pullback_into_the_zone_is_not_a_third_touch(exe, tmp_path, d):
    """T1 14, R 15, T2 16, R 17 (top 100.9), 18 comes back into the zone and closes inside it: a continuation setup
    ends there (TOUCH_LIMIT); the reversal setup does not count it as a touch. 19 closes below the T1 wick (BREAKOUT),
    20 confirms. 18 was not rejected, so the 100 % stays the top 100.9 (not 18's high 100.12); 0 % = 98.9. 21 pulls
    back -> limits on 100.9 -> 98.9."""
    rv, _ = run(exe, tmp_path, seq("pullback_in_zone", d), setup_type=REV)
    assert key(of(rv, 1, n=18)) == []
    assert [r["k"] for r in of(rv, 1, ev="TOUCH")] == [1, 2]
    assert key(of(rv, 1, n=19)) == [(19, "BREAKOUT", -d, 0, None)]
    conf = of(rv, 1, n=20, ev="CONFIRM")[0]
    assert conf["O"] == pytest.approx(px(d, 100.9)) and conf["X"] == pytest.approx(px(d, 98.9))
    pl = of(rv, 1, n=21, ev="PLACE_LIMIT")
    assert len(pl) == 3
    if d > 0:
        assert [r["P"] for r in pl] == pytest.approx(short_fib(100.9, 98.9))
    ct, _ = run(exe, tmp_path, seq("pullback_in_zone", d), setup_type=CONT)
    assert key(of(ct, 0, n=18)) == [(18, "DONE", d, 0, "TOUCH_LIMIT")]
    bo, _ = run(exe, tmp_path, seq("pullback_in_zone", d), setup_type=BOTH)
    assert key(of(bo, 0, n=18)) == [(18, "DONE", d, 0, "TOUCH_LIMIT")]
    assert key(of(bo, 1, n=19)) == [(19, "BREAKOUT", -d, 0, None)]
    assert of(bo, 1, n=20, ev="CONFIRM")[0]["O"] == pytest.approx(px(d, 100.9))


@D
def test_rejected_bounce_top_is_the_100(exe, tmp_path, d):
    """15 wicks up to 101.6 after T1; T2 16 is rejected by 17 (top 100.6): the last bounce from the BPR is 100.6, so
    the 100 % after the breakout on 18 is 100.6, not 101.6."""
    recs, _ = run(exe, tmp_path, seq("bounce_origin", d), setup_type=REV)
    assert key(of(recs, 1, n=18)) == [(18, "BREAKOUT", -d, 0, None)]
    conf = of(recs, 1, n=19, ev="CONFIRM")[0]
    assert conf["O"] == pytest.approx(px(d, 100.6)) and conf["X"] == pytest.approx(px(d, 99.0))


@D
def test_rejected_pullback_bounce_is_the_100(exe, tmp_path, d):
    """After T1 / T2 (top 101.4 on 17) a third visit (18, the pullback) is rejected by 19 (bounce top 100.7): the
    breakout on 20 trades from the last bounce, 100 % = 100.7, not 101.4."""
    recs, _ = run(exe, tmp_path, seq("pullback_bounce", d), setup_type=REV)
    assert [r["k"] for r in of(recs, 1, ev="TOUCH")] == [1, 2]
    assert key(of(recs, 1, n=20)) == [(20, "BREAKOUT", -d, 0, None)]
    conf = of(recs, 1, n=21, ev="CONFIRM")[0]
    assert conf["O"] == pytest.approx(px(d, 100.7)) and conf["X"] == pytest.approx(px(d, 99.0))


@D
def test_unrejected_t2_spike_is_the_100(exe, tmp_path, d):
    """T2 16 spikes to 101.2 and falls into the zone; the breakout 17 comes from that visit (not rejected): the 100 %
    is the highest high since T1, the T2 candle's 101.2."""
    recs, _ = run(exe, tmp_path, seq("t2_spike", d), setup_type=REV)
    assert key(of(recs, 1, n=17)) == [(17, "BREAKOUT", -d, 0, None)]
    conf = of(recs, 1, n=18, ev="CONFIRM")[0]
    assert conf["O"] == pytest.approx(px(d, 101.2)) and conf["X"] == pytest.approx(px(d, 99.0))


@D
def test_zero_is_the_lowest_low_after_the_100(exe, tmp_path, d):
    """The T2 visit (top 100.9 on 16) has a wick to 99.25 on 17 before its rejection 18: after the breakout 19 and the
    confirmation 20 (lows 99.3 / 99.28) the 0 % is 99.25, the lowest low after the 100 %."""
    recs, _ = run(exe, tmp_path, seq("visit_deep_wick", d), setup_type=REV)
    assert key(of(recs, 1, n=19)) == [(19, "BREAKOUT", -d, 0, None)]
    conf = of(recs, 1, n=20, ev="CONFIRM")[0]
    assert conf["O"] == pytest.approx(px(d, 100.9)) and conf["X"] == pytest.approx(px(d, 99.25))


@D
def test_reversal_setup_still_expires(exe, tmp_path, d):
    """setup_expiry_bars 4 (armed on 13): the reversal setup ends EXPIRED on 18 like any setup before its
    confirmation, pullback or not."""
    recs, _ = run(exe, tmp_path, seq("pullback_in_zone", d), setup_type=REV, setup_expiry_bars=4)
    assert key(of(recs, 1, n=18)) == [(18, "DONE", d, 0, "EXPIRED")]


# ---------------------------------------------------------------------------------------------------------------
# BOTH: two setups per BPR
# ---------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("te", [0, 1], ids=["no-touch-entry", "touch-entry"])
@pytest.mark.parametrize("direction,kinds", [(0, [0, 1]), (1, [0]), (2, [1])], ids=["BOTH-dirs", "LONG_ONLY",
                                                                                    "SHORT_ONLY"])
def test_both_creates_a_setup_per_allowed_trade(exe, tmp_path, direction, kinds, te):
    """A bullish BPR: the continuation setup trades long, the reversal setup short; the direction filter removes the
    setup whose trade it forbids (with BOTH the touch entry is the continuation setup's, so it keeps no reversal
    setup). The continuation one is created first."""
    recs, _ = run(exe, tmp_path, V7["owner_example"], setup_type=BOTH, direction=direction, touch_entry=te)
    armed = [r for r in recs if r["ev"] == "ARMED" and r["n"] == 13]
    assert [r["kind"] for r in armed] == kinds and all(r["dir"] == 1 for r in armed)


@pytest.mark.parametrize("st,kind", [(CONT, 0), (BOTH, 0), (REV, 1)])
def test_touch_entry_sent_once_per_bpr(exe, tmp_path, st, kind):
    """The touch entry belongs to the continuation setup (CONTINUATION / BOTH) or to the reversal setup (REVERSAL, no
    continuation setup): one per BPR."""
    recs, _ = run(exe, tmp_path, base(), touch_entry=1, setup_type=st)
    te = [r for r in recs if r["ev"] == "TOUCH_ENTRY"]
    assert len(te) == 1 and te[0]["kind"] == kind and te[0]["n"] == 14
    # skipped (cost filter): one SKIP record, the owner's - the other setup of the BPR is no candidate
    sk, _ = run(exe, tmp_path, base(), touch_entry=1, setup_type=st, max_cost_r=0.01)
    sk = [r for r in sk if r["ev"] == "SKIP" and r["k"] == 0]
    assert [(r["n"], r["kind"], r["reason"]) for r in sk] == [(14, kind, "COST")]


# ---------------------------------------------------------------------------------------------------------------
# random series: invariants, coverage, causality
# ---------------------------------------------------------------------------------------------------------------
RANDOM7 = [
    (51, dict(setup_type=BOTH)),
    (52, dict(setup_type=REV)),
    (53, dict(setup_type=REV, rev_level=1)),
    (54, dict(setup_type=REV, rev_level=2, rev_reject=0)),
    (55, dict(setup_type=BOTH, touch_entry=1, max_touches=1)),
    (56, dict(setup_type=BOTH, touch_entry=1, anticipate=1, fvg_rule=FVG["LUXALGO"])),
    (57, dict(setup_type=BOTH, direction=1)),
    (58, dict(setup_type=BOTH, direction=2, max_touches=3, rev_level=2)),
]


def _check7(recs, bars, kv):
    """v7 per setup: its kind fits the setup type and the direction filter; a reversal setup counts at most
    max_touches touches and never ends with TOUCH_LIMIT; its breakout is against the BPR, after a rejection (default),
    at the level its option names (computed from the touch candles' wicks), on a close beyond it; confirmations follow
    the kind; touch entries come from the owning kind only."""
    st = kv.get("setup_type", CONT)
    lv, rj, mt = kv.get("rev_level", 0), kv.get("rev_reject", 1), kv.get("max_touches", 2)
    allowed = {0: (1, -1), 1: (1,), 2: (-1,)}[kv.get("direction", 0)]
    kind, zone, tch, rejected = {}, {}, {}, {}
    for r in recs:
        i, ev = r["id"], r["ev"]
        if ev.startswith("H_"):
            continue
        if ev == "ARMED":
            kind[i], zone[i], tch[i], rejected[i] = r["kind"], r["dir"], [], False
            assert r["kind"] in {CONT: (0,), REV: (1,), BOTH: (0, 1)}[st], r
            trade = r["dir"] if r["kind"] == 0 else -r["dir"]
            assert trade in allowed or (st == REV and kv.get("touch_entry") and r["dir"] in allowed), r
        elif ev == "TOUCH":
            tch[i].append(r["n"])
            assert r["k"] == len(tch[i]) <= mt, r
        elif ev == "REJECT":
            rejected[i] = True
        elif ev == "DONE" and r["reason"] == "TOUCH_LIMIT":
            assert kind[i] == 0, r
        elif ev == "BREAKOUT":
            z = zone[i]
            if kind[i] == 0:
                assert r["dir"] == z, r
                continue
            assert r["dir"] == -z and (rejected[i] or not rj), r
            wick = [bars[n][2] if z > 0 else bars[n][1] for n in tch[i]]
            exp = {0: min(wick) if z > 0 else max(wick), 1: wick[0], 2: wick[-1]}[lv]
            assert r["lvl"] == pytest.approx(exp), (r, wick)
            c = bars[r["n"]][3]
            assert (c < r["lvl"]) if z > 0 else (c > r["lvl"]), r
        elif ev == "CONFIRM":
            assert r["dir"] == (zone[i] if kind[i] == 0 else -zone[i]), r
        elif ev == "TOUCH_ENTRY":
            assert kind[i] == 0 or st == REV, r


@pytest.mark.parametrize("case", RANDOM7, ids=[f"seed{c[0]}" for c in RANDOM7])
def test_random_series_invariants(exe, tmp_path, case):
    seed, kv = case
    bars = _bars(seed, 4000)
    recs, _ = run(exe, tmp_path, bars, hold=60, **kv)
    assert {"CONFIRM", "PLACE_LIMIT"} <= {r["ev"] for r in recs}
    _check(recs, kv)                    # v6: one setup with orders / positions at a time, order geometry, ...
    _check7(recs, bars, kv)


def test_random_series_cover_the_new_paths(exe, tmp_path):
    """Across the cases: a reversal confirmed after its BPR's continuation setup confirmed (BOTH), a DEEPEST level
    taken from T2 (deeper than T1), and reversal breakouts under each level option."""
    after_cont = deepest_t2 = 0
    by_level = {0: 0, 1: 0, 2: 0}
    for seed, kv in RANDOM7:
        bars = _bars(seed, 4000)
        recs, _ = run(exe, tmp_path, bars, hold=60, **kv)
        kind, zone, tch, conf = {}, {}, {}, set()
        for r in recs:
            i, ev = r["id"], r["ev"]
            if ev == "ARMED":
                kind[i], zone[i], tch[i] = r["kind"], r["dir"], []
            elif ev == "TOUCH":
                tch[i].append(r["n"])
            elif ev == "CONFIRM":
                if kind[i] == 1 and kind.get(i - 1) == 0 and (i - 1) in conf and zone[i - 1] == zone[i]:
                    after_cont += 1
                conf.add(i)
            elif ev == "BREAKOUT" and kind[i] == 1:
                by_level[kv.get("rev_level", 0)] += 1
                if kv.get("rev_level", 0) == 0 and r["lvlBar"] != tch[i][0]:
                    deepest_t2 += 1
    assert after_cont > 0 and deepest_t2 > 0 and min(by_level.values()) > 0, (after_cont, deepest_t2, by_level)


@pytest.mark.parametrize("kv", [dict(setup_type=BOTH, touch_entry=1),
                                dict(setup_type=REV, rev_level=1, max_touches=1, fvg_rule=FVG["LUXALGO"])],
                         ids=["both+touch", "rev-T1-one-touch"])
def test_v7_rules_are_causal(exe, tmp_path, kv):
    """CLAUDE.md causality rule: the records up to bar t do not depend on later bars."""
    bars = _bars(43, 1500)
    full, _ = run(exe, tmp_path, bars, hold=60, **kv)
    other = _bars(99, 1500)
    for t in (300, 701, 1111):
        cut, _ = run(exe, tmp_path, bars[:t + 1], hold=60, **kv)
        assert full[:len(cut)] == cut, t
        sh = bars[t][3] - other[t + 1][0]
        alt, _ = run(exe, tmp_path, bars[:t + 1] + [tuple(x + sh for x in b) for b in other[t + 1:]], hold=60, **kv)
        assert alt[:len(cut)] == cut, t


def test_defaults_ignore_the_v7_inputs(exe, tmp_path):
    """CONTINUATION: the reversal inputs change nothing (the parity set compares the defaults with the v4 Python
    reference, the owner's example included)."""
    a, _ = run(exe, tmp_path, V7["owner_example"])
    b, _ = run(exe, tmp_path, V7["owner_example"], rev_level=2, rev_reject=0)
    assert a == b
    c, _ = run(exe, tmp_path, scenarios()["two_touches"], rev_level=1)
    e, _ = run(exe, tmp_path, scenarios()["two_touches"])
    assert c == e
