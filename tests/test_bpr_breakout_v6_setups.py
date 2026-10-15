"""BprFvgEA v6: the reversal setup and the touch entry, checked on the C++ transliteration of the MQL5 detector only.

v6 (owner request 2026-10-12) adds three detector parameters that the Python reference does not have (EA only, like v5):
- ``setup_type`` (InpSetupType): 0 CONTINUATION (v1-v5), 1 REVERSAL, 2 BOTH. The reversal setup trades the breakout
  THROUGH the BPR: after T1 / T2, a close beyond the opposite extreme of the candle that made the touch (below its low
  for a bullish BPR), confirmed by the next close(s), starts a trade against the BPR's direction; the leg runs from the
  touch's opposite extreme (highest high since the touch began, for a bullish BPR) to the new extreme, and the entries
  are the same Fibonacci pullback limits. With REVERSAL / BOTH a broken BPR only ends the continuation.
- ``touch_entry`` (InpTouchEntry) and ``touch_rr`` (InpTouchTargetRR): on the close of the T1 candle (if it did not
  break the BPR) a market entry in the BPR's direction at the next open, stop beyond the BPR's far edge + the stop
  buffer, target touch_rr x the risk. The setup goes on; its own touch position does not stop it from placing its
  limits (env.slotOwner), but it keeps every other setup out.

v7 (owner's example, 2026-10-15) changed three reversal rules and BOTH; tests/test_bpr_breakout_v7_reversal.py checks
them. Here the v6 reversal sequences break down right after T1, so they run with V6R (no rejection needed, level = the
latest touch candle's wick, as in v6). BOTH now follows each BPR as two setups, a continuation one (kind 0) and a
reversal one (kind 1); the tests pick a setup by its kind (the harness prints it with ext=1).

The harness (tools/mql5_cpp_harness/bk_main.cpp) opens a touch entry at the next bar's open and prints it as
H_TOUCH_OPEN / H_TOUCH_CLOSE / H_TOUCH_SKIP lines. With the defaults the parity harness still compares every record with
the v4 Python reference, on these sequences too. This checks decision logic, not MetaEditor compilation and not MT5
order execution. Skipped without g++.
"""
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from bk_scenarios import base, mirror, scenarios, v5_sequences, v6_sequences

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools/mql5_cpp_harness"
INC = ROOT / "mql5/BprFvgEA/include"
GXX = shutil.which("g++")
pytestmark = pytest.mark.skipif(GXX is None, reason="g++ not installed")

SP = 0.1
TICK = 0.01
CONT, REV, BOTH = 0, 1, 2
V6R = dict(rev_reject=0, rev_level=2)   # the v6 reversal rules (v7 inputs InpRevNeedRejection = false, InpRevLevel = LAST)
FVG = {"LUXALGO": 0, "ANY_GAP": 1, "NONE": 2}
STAT_TAIL = ["BLOCKED_SLOT", "BLOCKED_SESSION", "BLOCKED_RISK", "BLOCKED_SPREAD", "WAIT_NO_FVG", "REANCHOR", "RETRY",
             "BREAK_FAIL", "CONFIRM", "PLACE_LIMIT", "ARMED", "CLOSED", "TOUCH", "BREAKOUT"]
V6 = v6_sequences()


def stat(st, name):
    return st[len(st) - len(STAT_TAIL) + STAT_TAIL.index(name)]


@pytest.fixture(scope="module")
def exe(tmp_path_factory):
    d = tmp_path_factory.mktemp("bk6")
    sys.path.insert(0, str(HARNESS))
    try:
        from mq5_to_cpp import transform_pure
    finally:
        sys.path.pop(0)
    src = [(INC / f).read_text(encoding="utf-8") for f in ("BfDefines.mqh", "BfEngine.mqh", "BfDetector.mqh")]
    (d / "bf_pure.cpp").write_text(transform_pure(src))
    shutil.copy(HARNESS / "shim.h", d / "shim.h")
    shutil.copy(HARNESS / "bk_main.cpp", d / "bk_main.cpp")
    out = d / "bk_harness"
    res = subprocess.run([GXX, "-std=c++17", "-O1", "-w", "-o", str(out), str(d / "bk_main.cpp")],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr[-4000:]
    return out


def run(exe, tmp_path, bars, hold=50, **kv):
    """-> (records incl. H_TOUCH_* lines, stats). Default here: ANY_GAP FVG rule, positions held 50 bars."""
    kv.setdefault("fvg_rule", FVG["ANY_GAP"])
    kv.setdefault("ext", 1)
    bf = tmp_path / "bars.txt"
    bf.write_text("".join(" ".join(repr(float(x)) for x in b) + "\n" for b in bars))
    args = [f"sp={SP}", f"hold_bars={hold}"] + [f"{k}={v}" for k, v in kv.items()]
    res = subprocess.run([str(exe), str(bf), *args], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert "lost events 0 intents 0" in res.stderr, res.stderr
    lines = res.stdout.splitlines()
    assert lines[-1].startswith("STATS")
    return [json.loads(ln) for ln in lines[:-1]], [int(x) for x in lines[-1].split()[1:]]


def main_id(recs, kind=None):
    """the setup of a hand-built sequence: the first one touched (id 1 on the bullish side; the mirrored bars also arm
    a second BPR first, so there it is id 2). v7: with kind, the first touched setup of that kind (0 continuation, 1
    reversal: BOTH has one of each per BPR)."""
    return next((r["id"] for r in recs if r["ev"] == "TOUCH" and (kind is None or r["kind"] == kind)), 1)


def recs_of(recs, n=None, ev=None, kind=None):
    sid = main_id(recs, kind)
    return [r for r in recs if r["id"] == sid and (n is None or r["n"] == n) and (ev is None or r["ev"] == ev)]


def key(rs):
    return [(r["n"], r["ev"], r["dir"], r["k"], r["reason"]) for r in rs]


def seq(name, d):
    return V6[name] if d > 0 else mirror(V6[name])


def short_fib(O, X, sp=SP, fibs=(50.0, 61.8, 71.0)):  # noqa: E741
    """Sell-limit prices of a short leg O (100 %) -> X (0 %): F(f) = X + f/100 * (O - X), bid levels."""
    return [round(round((X + f / 100.0 * (O - X)) / TICK) * TICK, 2) for f in fibs]


# ---------------------------------------------------------------------------------------------------------------
# defaults
# ---------------------------------------------------------------------------------------------------------------
def test_explicit_defaults_equal_default(exe, tmp_path):
    """setup_type=0 / touch_entry=0 are the defaults; that the defaults equal v4 is checked against the Python
    reference on the same sequences in tests/test_bpr_breakout_ea_harness.py."""
    seqs = dict(scenarios())
    seqs.update(v5_sequences())
    seqs.update(V6)
    for name, bars in seqs.items():
        for rule in FVG.values():
            a = run(exe, tmp_path, bars, hold=3, fvg_rule=rule)
            b = run(exe, tmp_path, bars, hold=3, fvg_rule=rule, setup_type=CONT, touch_entry=0, touch_rr=1.5)
            assert a == b, name


@pytest.mark.parametrize("name", ["base", "fill_target", "reanchor", "two_touches", "touch_limit", "break_fail"])
def test_both_equals_continuation_without_a_reversal(exe, tmp_path, name):
    """No candle closes beyond the touch candle's opposite extreme of the traded setup in these sequences: BOTH trades
    it exactly as CONTINUATION does. (Other BPRs may differ: one that breaks ends BROKEN with CONTINUATION but stays
    tracked for its reversal with BOTH - two_touches' bearish BPR on 24-25.)"""
    bars = scenarios()[name]
    for rule in FVG.values():
        a, _ = run(exe, tmp_path, bars, hold=3, fvg_rule=rule)
        b, _ = run(exe, tmp_path, bars, hold=3, fvg_rule=rule, setup_type=BOTH)
        assert [r for r in a if r["id"] == main_id(a)] == [r for r in b if r["id"] == main_id(b)], (name, rule)


# ---------------------------------------------------------------------------------------------------------------
# reversal
# ---------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("d", [1, -1], ids=["bullish-BPR-short", "bearish-BPR-long"])
@pytest.mark.parametrize("st", [REV, BOTH], ids=["REVERSAL", "BOTH"])
def test_reversal_trade(exe, tmp_path, d, st):
    """T1 on 14 (low 99.5 / leg origin 100.2); 15 and 16 close below 99.5 -> BREAKOUT and CONFIRM against the BPR;
    17 new extreme 98.4; 18 pullback -> three limits at 50 / 61.8 / 71 % of 100.2 -> 98.4; 19 fills the 50 %; 20
    touches the target: the other two are cancelled and the setup closes."""
    recs, _ = run(exe, tmp_path, seq("reversal", d), setup_type=st, **V6R)
    recs = recs_of(recs, kind=1)                           # BOTH: the reversal setup of the BPR
    t = -d                                                 # trade direction: against the BPR
    assert recs_of(recs, ev="ARMED")[0]["dir"] == d
    assert key(recs_of(recs, n=15)) == [(15, "BREAKOUT", t, 0, None)]
    conf = recs_of(recs, n=16, ev="CONFIRM")[0]
    O, X = (100.2, 98.8) if d > 0 else (99.8, 101.2)      # noqa: E741
    assert conf["dir"] == t and conf["O"] == pytest.approx(O) and conf["X"] == pytest.approx(X)
    pl = recs_of(recs, n=18, ev="PLACE_LIMIT")
    assert [r["k"] for r in pl] == [1, 2, 3] and all(r["dir"] == t for r in pl)
    assert all(r["O"] == pytest.approx(O) for r in pl)
    if d > 0:
        assert [r["P"] for r in pl] == pytest.approx(short_fib(100.2, 98.4))
        assert all(r["SL"] == pytest.approx(100.2 + 0.1 + SP) and r["TP"] == pytest.approx(98.4 + SP) for r in pl)
    for r in pl:
        assert (r["SL"] < r["P"] < r["TP"]) if t > 0 else (r["TP"] < r["P"] < r["SL"])
    assert [r["ev"] for r in recs_of(recs, n=20)] == ["CANCEL", "CANCEL", "CLOSED"]


@pytest.mark.parametrize("d", [1, -1], ids=["long-BPR", "short-BPR"])
def test_continuation_does_not_trade_the_reversal(exe, tmp_path, d):
    recs, _ = run(exe, tmp_path, seq("reversal", d))
    assert not recs_of(recs, ev="BREAKOUT") and not recs_of(recs, ev="PLACE_LIMIT")


@pytest.mark.parametrize("d", [1, -1], ids=["long-BPR", "short-BPR"])
def test_reversal_after_t2_uses_the_t2_candle(exe, tmp_path, d):
    """LAST level (v6): T1 14 (low 99.5), rejection 15, T2 16 (low 99.6): 17 closes at 99.55 - below the T2 candle's
    low only - and starts the reversal. v7: T2 was not rejected before that breakout, so the leg origin stays the
    highest high since T1 (14: 100.2; v6 restarted it at T2: 100.12). With the v7 default level (the deepest wick,
    99.5) 17 is no breakout; 18 is."""
    recs, _ = run(exe, tmp_path, seq("rev_t2", d), setup_type=REV, **V6R)
    assert key(recs_of(recs, n=16)) == [(16, "TOUCH", d, 2, None)]
    assert key(recs_of(recs, n=17)) == [(17, "BREAKOUT", -d, 0, None)]
    conf = recs_of(recs, n=18, ev="CONFIRM")[0]
    assert conf["O"] == pytest.approx(100.2 if d > 0 else 99.8)
    dp, _ = run(exe, tmp_path, seq("rev_t2", d), setup_type=REV)
    assert not recs_of(dp, n=17, ev="BREAKOUT") and key(recs_of(dp, n=18)) == [(18, "BREAKOUT", -d, 0, None)]


@pytest.mark.parametrize("d", [1, -1], ids=["long-BPR", "short-BPR"])
def test_failed_reversal_then_continuation(exe, tmp_path, d):
    """15 starts a reversal, 16 closes back above 99.5 (BREAK_FAIL; the direction goes back to the BPR's). REVERSAL:
    nothing more (17 is a rejection). BOTH: 17 does not touch and closes above the touch level -> continuation
    breakout, 18 confirms; its leg origin includes the failed reversal candle's low (99.2)."""
    rv, _ = run(exe, tmp_path, seq("rev_fail_then_cont", d), setup_type=REV, **V6R)
    assert key(recs_of(rv, n=16)) == [(16, "BREAK_FAIL", -d, 0, None)]
    assert key(recs_of(rv, n=17)) == [(17, "REJECT", d, 0, None)]
    bo, _ = run(exe, tmp_path, seq("rev_fail_then_cont", d), setup_type=BOTH, **V6R)
    assert key(recs_of(bo, n=16, kind=1)) == [(16, "BREAK_FAIL", -d, 0, None)]
    assert key(recs_of(bo, n=17, kind=0)) == [(17, "BREAKOUT", d, 0, None)]
    conf = recs_of(bo, n=18, ev="CONFIRM", kind=0)[0]
    assert conf["dir"] == d and conf["O"] == pytest.approx(99.2 if d > 0 else 100.8)


@pytest.mark.parametrize("d", [1, -1], ids=["long-BPR", "short-BPR"])
def test_broken_bpr_only_ends_the_continuation(exe, tmp_path, d):
    """'broken': 15 goes below the BPR. CONTINUATION: DONE(BROKEN). BOTH: the continuation setup ends the same way;
    the reversal setup goes on (15 closes below the T1 candle's low -> reversal breakout, V6R: no rejection needed)."""
    bars = scenarios()["broken"] if d > 0 else mirror(scenarios()["broken"])
    ct, _ = run(exe, tmp_path, bars)
    assert key(recs_of(ct, n=15)) == [(15, "DONE", d, 0, "BROKEN")]
    bo, _ = run(exe, tmp_path, bars, setup_type=BOTH, **V6R)
    assert key(recs_of(bo, n=15, kind=0)) == [(15, "DONE", d, 0, "BROKEN")]
    assert key(recs_of(bo, n=15, kind=1)) == [(15, "BREAKOUT", -d, 0, None)]


@pytest.mark.parametrize("d", [1, -1], ids=["long-BPR", "short-BPR"])
def test_no_continuation_once_the_bpr_is_broken(exe, tmp_path, d):
    """BOTH (v7: two setups). broken_then_up: 15 breaks the BPR without a reversal close: the continuation setup
    ends BROKEN as with CONTINUATION, so 16 is no continuation breakout; the reversal setup sees a rejection.
    broken_in_break: the continuation breakout on 15 is not confirmed by 16, whose low breaks the BPR (v7:
    DONE(BROKEN) of the continuation setup)."""
    up, _ = run(exe, tmp_path, seq("broken_then_up", d), setup_type=BOTH)
    assert not [r for r in up if r["ev"] == "BREAKOUT" and r["id"] <= 2]
    assert key(recs_of(up, n=15, kind=0)) == [(15, "DONE", d, 0, "BROKEN")]
    assert key(recs_of(up, n=16, kind=1)) == [(16, "REJECT", d, 0, None)]
    ct, _ = run(exe, tmp_path, seq("broken_then_up", d), setup_type=CONT)
    assert key(recs_of(ct, n=15)) == [(15, "DONE", d, 0, "BROKEN")]
    br, _ = run(exe, tmp_path, seq("broken_in_break", d), setup_type=BOTH)
    assert key(recs_of(br, n=15, kind=0)) == [(15, "BREAKOUT", d, 0, None)]
    assert key(recs_of(br, n=16, kind=0)) == [(16, "DONE", d, 0, "BROKEN")]
    assert not recs_of(br, ev="CONFIRM", kind=0)


@pytest.mark.parametrize("d", [1, -1], ids=["long-BPR", "short-BPR"])
def test_reversal_close_on_the_level_is_not_a_breakout(exe, tmp_path, d):
    """A close exactly on the T1 candle's low (15) is no reversal breakout; one beyond it (16) is."""
    recs, _ = run(exe, tmp_path, seq("rev_close_on_level", d), setup_type=REV, **V6R)
    assert not recs_of(recs, n=15, ev="BREAKOUT")
    assert key(recs_of(recs, n=16)) == [(16, "BREAKOUT", -d, 0, None)]


@pytest.mark.parametrize("d", [1, -1], ids=["long-BPR", "short-BPR"])
def test_reversal_leg_restarts_at_a_new_high(exe, tmp_path, d):
    """The reversal leg runs from the touch's highest high to the lowest low AFTER it: 16's new high (100.3) restarts
    it, so 15's low (99.3) is not its extreme; the confirmation on 18 has O = 100.3, X = 99.4."""
    recs, _ = run(exe, tmp_path, seq("rev_new_origin", d), setup_type=REV, **V6R)
    conf = recs_of(recs, n=18, ev="CONFIRM")[0]
    assert conf["dir"] == -d
    assert conf["O"] == pytest.approx(100.3 if d > 0 else 99.7) and conf["X"] == pytest.approx(99.4 if d > 0 else 100.6)


@pytest.mark.parametrize("d", [1, -1], ids=["long-BPR", "short-BPR"])
def test_both_failed_continuation_candle_can_start_the_reversal(exe, tmp_path, d):
    """BOTH, bull trap: the continuation breakout on 17 fails on 18, and 18 closes below the T1 / T2 wicks: the
    reversal setup's breakout on the same candle (v7 defaults: rejections on 15 and 17), confirmed on 19 exactly as
    with REVERSAL."""
    bo, _ = run(exe, tmp_path, seq("cont_fail_then_rev", d), setup_type=BOTH)
    assert key(recs_of(bo, n=17, kind=0)) == [(17, "BREAKOUT", d, 0, None)]
    # the continuation setup: the failing candle touches the zone, a third touch (as with CONTINUATION)
    assert key(recs_of(bo, n=18, kind=0)) == [(18, "BREAK_FAIL", d, 0, None), (18, "DONE", d, 0, "TOUCH_LIMIT")]
    ct, _ = run(exe, tmp_path, seq("cont_fail_then_rev", d), setup_type=CONT)
    assert key(recs_of(ct, n=18)) == key(recs_of(bo, n=18, kind=0))
    assert key(recs_of(bo, n=18, kind=1)) == [(18, "BREAKOUT", -d, 0, None)]
    rv, _ = run(exe, tmp_path, seq("cont_fail_then_rev", d), setup_type=REV)
    assert key(recs_of(rv, n=18)) == [(18, "BREAKOUT", -d, 0, None)]
    cb, cr = recs_of(bo, n=19, ev="CONFIRM", kind=1)[0], recs_of(rv, n=19, ev="CONFIRM")[0]
    assert (cb["dir"], cb["O"], cb["X"]) == (cr["dir"], cr["O"], cr["X"]) and cb["dir"] == -d


@pytest.mark.parametrize("d", [1, -1], ids=["long-BPR", "short-BPR"])
def test_both_failed_reversal_candle_can_start_the_continuation(exe, tmp_path, d):
    """BOTH (V6R): the reversal breakout on 15 fails on 16, which does not touch and closes above the touch level: the
    continuation setup's breakout on the same candle, confirmed on 17."""
    bo, _ = run(exe, tmp_path, seq("rev_fail_then_cont_bar", d), setup_type=BOTH, **V6R)
    assert key(recs_of(bo, n=16, kind=1)) == [(16, "BREAK_FAIL", -d, 0, None), (16, "REJECT", d, 0, None)]
    assert key(recs_of(bo, n=16, kind=0)) == [(16, "BREAKOUT", d, 0, None)]
    assert recs_of(bo, n=17, ev="CONFIRM", kind=0)[0]["dir"] == d


@pytest.mark.parametrize("d,direction", [(1, 1), (-1, 2)], ids=["bullish-LONG_ONLY", "bearish-SHORT_ONLY"])
def test_broken_bpr_ends_when_its_reversal_is_filtered_out(exe, tmp_path, d, direction):
    """BOTH but the reversal's direction is not allowed: a broken BPR cannot trade any more -> DONE(BROKEN) as in v5."""
    bars = scenarios()["broken"] if d > 0 else mirror(scenarios()["broken"])
    recs, _ = run(exe, tmp_path, bars, setup_type=BOTH, direction=direction)
    assert key(recs_of(recs, n=15)) == [(15, "DONE", d, 0, "BROKEN")]


def test_touch_entry_keeps_a_bpr_whose_reversal_is_filtered_out(exe, tmp_path):
    """REVERSAL + LONG_ONLY + touch entry: the bullish BPR is tracked for its touch entry (a buy), which is taken on
    T1; its reversal (a short) is not traded."""
    recs, _ = run(exe, tmp_path, V6["reversal"], setup_type=REV, direction=1, touch_entry=1)
    assert recs_of(recs, n=14, ev="TOUCH_ENTRY")[0]["dir"] == 1
    assert not recs_of(recs, ev="BREAKOUT")


@pytest.mark.parametrize("direction,armed,trade", [(1, False, None), (2, True, -1)], ids=["LONG_ONLY", "SHORT_ONLY"])
def test_direction_filter_applies_to_the_trade(exe, tmp_path, direction, armed, trade):
    """A bullish BPR's reversal is a short: LONG_ONLY + REVERSAL does not even track it; SHORT_ONLY does."""
    recs, _ = run(exe, tmp_path, V6["reversal"], setup_type=REV, direction=direction, **V6R)
    assert bool(recs_of(recs, ev="ARMED")) == armed
    if trade:
        assert recs_of(recs, n=16, ev="CONFIRM")[0]["dir"] == trade


def test_both_with_long_only_keeps_the_continuation_only(exe, tmp_path):
    """BOTH + LONG_ONLY on a bullish BPR: tracked (the continuation is allowed), but no reversal breakout."""
    recs, _ = run(exe, tmp_path, V6["reversal"], setup_type=BOTH, direction=1)
    assert recs_of(recs, ev="ARMED") and not recs_of(recs, ev="BREAKOUT")


# ---------------------------------------------------------------------------------------------------------------
# touch entry
# ---------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("d", [1, -1], ids=["long", "short"])
def test_touch_entry_on_t1(exe, tmp_path, d):
    """base: T1 on 14 (close 100.0) -> TOUCH_ENTRY on 14: buy at the ask (100.1), stop 98.0 - 10 ticks, target 1.5 R;
    the harness opens it at 15's open. The continuation goes on and places its limits on 19 while the touch position
    is still open (its own slot)."""
    bars = base() if d > 0 else mirror(base())
    recs, _ = run(exe, tmp_path, bars, touch_entry=1)
    te = recs_of(recs, n=14, ev="TOUCH_ENTRY")
    assert len(te) == 1 and te[0]["dir"] == d and te[0]["k"] == 0
    if d > 0:
        assert te[0]["P"] == pytest.approx(100.1) and te[0]["SL"] == pytest.approx(97.9)
        assert te[0]["TP"] == pytest.approx(100.1 + 1.5 * 2.2)
    else:
        # sell at the bid 100.0, stop (an ask level) 102.0 + 10 ticks + spread
        assert te[0]["P"] == pytest.approx(100.0) and te[0]["SL"] == pytest.approx(102.2)
        assert te[0]["TP"] == pytest.approx(100.0 - 1.5 * 2.2)
    assert recs_of(recs, n=15, ev="H_TOUCH_OPEN")
    assert not recs_of(recs, ev="H_TOUCH_CLOSE")             # still open at the end
    assert len(recs_of(recs, n=19, ev="PLACE_LIMIT")) == 3


def test_touch_entry_target_rr(exe, tmp_path):
    recs, _ = run(exe, tmp_path, base(), touch_entry=1, touch_rr=2.0)
    assert recs_of(recs, ev="TOUCH_ENTRY")[0]["TP"] == pytest.approx(100.1 + 2.0 * 2.2)


def test_touch_entry_only_on_t1(exe, tmp_path):
    """hold 2: the T1 touch position (opened on 15) is closed on 17, so the slot is free on T2 (17): still no touch
    entry there."""
    recs, _ = run(exe, tmp_path, scenarios()["two_touches"], hold=2, touch_entry=1)
    assert recs_of(recs, n=17, ev="H_TOUCH_CLOSE")
    assert [r["n"] for r in recs_of(recs, ev="TOUCH_ENTRY")] == [14]
    assert [r["n"] for r in recs_of(recs, ev="TOUCH")] == [14, 17]


@pytest.mark.parametrize("st", [CONT, BOTH, REV])
def test_no_touch_entry_when_the_t1_candle_breaks_the_bpr(exe, tmp_path, st):
    """CONTINUATION / BOTH: the continuation setup ends BROKEN on that candle; REVERSAL: the reversal setup goes on
    (it owns the touch entry), but a T1 candle that broke the BPR sends none."""
    recs, _ = run(exe, tmp_path, V6["t1_breaks"], touch_entry=1, setup_type=st)
    assert not recs_of(recs, ev="TOUCH_ENTRY")


def test_touch_entry_cost_filter(exe, tmp_path):
    """max_cost_r 0.01: the touch entry is skipped (SKIP level 0, COST); nothing is opened; the setup goes on."""
    recs, _ = run(exe, tmp_path, base(), touch_entry=1, max_cost_r=0.01)
    assert key(recs_of(recs, n=14)) == [(14, "TOUCH", 1, 1, None), (14, "SKIP", 1, 0, "COST")]
    assert not [r for r in recs if r["ev"].startswith("H_TOUCH")]
    assert recs_of(recs, ev="CONFIRM")


def test_touch_entry_respects_the_direction_filter(exe, tmp_path):
    """SHORT_ONLY + REVERSAL on a bullish BPR: the touch entry would be a buy -> not taken; the reversal short is."""
    recs, _ = run(exe, tmp_path, V6["reversal"], setup_type=REV, direction=2, touch_entry=1, **V6R)
    assert not recs_of(recs, ev="TOUCH_ENTRY") and recs_of(recs, ev="PLACE_LIMIT")


@pytest.mark.parametrize("d", [1, -1], ids=["bullish-BPR", "bearish-BPR"])
def test_touch_entry_then_reversal(exe, tmp_path, d):
    """REVERSAL + touch entry: the touch entry follows the BPR (a buy on a bullish BPR); the reversal trade goes the
    other way and places its limits on 18 while the touch position is open (hedging; one setup)."""
    recs, _ = run(exe, tmp_path, seq("reversal", d), setup_type=REV, touch_entry=1, **V6R)
    assert recs_of(recs, n=14, ev="TOUCH_ENTRY")[0]["dir"] == d
    pl = recs_of(recs, n=18, ev="PLACE_LIMIT")
    assert len(pl) == 3 and all(r["dir"] == -d for r in pl)


def test_touch_position_closed_frees_the_slot(exe, tmp_path):
    """hold 3: the touch position is closed on 18 (time stop of the harness), before the limits on 19."""
    recs, _ = run(exe, tmp_path, base(), hold=3, touch_entry=1)
    assert recs_of(recs, n=18, ev="H_TOUCH_CLOSE") and len(recs_of(recs, n=19, ev="PLACE_LIMIT")) == 3


# ---------------------------------------------------------------------------------------------------------------
# random series: invariants, coverage, causality
# ---------------------------------------------------------------------------------------------------------------
def _bars(seed, n, tick=0.01):
    """The parity test's generator (tests/test_bpr_breakout_ea_harness.py::_bars)."""
    rnd = random.Random(seed)
    q = lambda x: round(round(x / tick) * tick, 2)  # noqa: E731
    out, c, anchor = [], 2000.0, 2000.0
    for _ in range(n):
        o = c
        if rnd.random() < 0.18:
            body = rnd.choice([-1, 1]) * rnd.uniform(1.5, 3.5)
            wick = 0.05
        else:
            body = rnd.gauss(0, 0.7) + (anchor - o) * 0.03
            wick = 0.6
        c = q(o + body)
        out.append((o, q(max(o, c) + abs(rnd.gauss(0, wick))), q(min(o, c) - abs(rnd.gauss(0, wick))), c))
    return out


RANDOM = [
    (31, dict(setup_type=REV)),
    (32, dict(setup_type=BOTH)),
    (33, dict(setup_type=BOTH, touch_entry=1)),
    (34, dict(setup_type=REV, touch_entry=1, anticipate=1)),
    (35, dict(setup_type=CONT, touch_entry=1)),
    (36, dict(setup_type=BOTH, touch_entry=1, fvg_rule=FVG["LUXALGO"], leg_expiry_bars=20)),
    (37, dict(setup_type=BOTH, touch_entry=1, fvg_rule=FVG["NONE"], max_cost_r=0, confirm_closes=1)),
    (38, dict(setup_type=REV, direction=1, touch_entry=1, anticipate=1, leg_break_on_close=1)),
    (39, dict(setup_type=BOTH, direction=2, touch_entry=1, touch_rr=3.0, max_touches=3)),
    # two T1 touches on one bar whose touch entries both fail the cost filter (found by searching seeds 100-600 for a
    # difference between the detector and a copy that stops deciding after a skipped touch entry)
    (101, dict(touch_entry=1, max_cost_r=0.08, fvg_rule=FVG["NONE"])),
]


def _check(recs, kv):
    """one setup with orders / positions at a time (limits and touch positions); a touch entry only into an empty
    slot; directions (BPR vs trade); leg geometry; geometry of every order; no order after the leg expiry."""
    st = kv.get("setup_type", CONT)
    allowed = {0: (1, -1), 1: (1,), 2: (-1,)}[kv.get("direction", 0)]
    leg_exp = kv.get("leg_expiry_bars", 60)
    live: dict[int, set] = {}
    touch: dict[int, str] = {}                     # id -> "pending" / "open"
    zone: dict[int, int] = {}
    trade: dict[int, int] = {}
    confirm: dict[int, int] = {}
    prev = None

    def busy(excl=None):
        return [j for j, s in live.items() if s and j != excl] + [j for j in touch if j != excl]

    for r in recs:
        i, ev, k, d = r["id"], r["ev"], r["k"], r["dir"]
        if ev == "ARMED":
            zone[i] = d
        elif ev == "CONFIRM":
            confirm[i] = r["n"]
            trade[i] = d
            assert d in allowed, r
            assert d == zone[i] or (d == -zone[i] and st != CONT), r
            assert d == zone[i] or st != CONT
            assert (r["O"] < r["X"]) if d > 0 else (r["O"] > r["X"]), r
        elif ev == "BREAKOUT":
            assert d in (zone[i], -zone[i]) and (d == zone[i] or st != CONT), r
        elif ev == "TOUCH_ENTRY":
            assert kv.get("touch_entry") and d == zone[i] and d in allowed, r
            assert not busy(), ("touch entry into a busy slot", r, busy())
            assert (r["SL"] < r["P"] < r["TP"]) if d > 0 else (r["TP"] < r["P"] < r["SL"]), r
            touch[i] = "pending"
        elif ev == "H_TOUCH_OPEN":
            touch[i] = "open"
        elif ev in ("H_TOUCH_CLOSE", "H_TOUCH_SKIP"):
            touch.pop(i, None)
        elif ev == "PLACE_LIMIT":
            assert d == trade[i] and r["n"] - confirm[i] <= leg_exp, r
            new_batch = prev is None or not (prev["ev"] == "PLACE_LIMIT" and prev["id"] == i and prev["n"] == r["n"])
            if new_batch:
                assert not live.get(i), ("new decision while its own levels are live", r)
                assert not busy(excl=i), ("two setups with orders / positions", r, busy(excl=i))
            live.setdefault(i, set()).add(k)
            assert (r["SL"] < r["P"] < r["TP"]) if d > 0 else (r["TP"] < r["P"] < r["SL"]), r
        elif ev in ("CANCEL", "DROP"):
            live.get(i, set()).discard(k)
        elif ev in ("DONE", "CLOSED"):
            live.pop(i, None)
        prev = r
    # a skipped touch entry does not end the decisions of the bar: every later T1 candidate of that bar (creation
    # order) is tried too, unless a decision came first (CONTINUATION, both directions: every T1 record is eligible)
    if kv.get("touch_entry") and st == CONT and kv.get("direction", 0) == 0:
        by_bar: dict[int, list] = {}
        for r in recs:
            by_bar.setdefault(r["n"], []).append(r)
        for n, rs in by_bar.items():
            skipped = sorted(r["id"] for r in rs if r["ev"] == "SKIP" and r["k"] == 0)
            if not skipped:
                continue
            a = skipped[0]
            decided = [r["id"] for r in rs if r["ev"] in ("PLACE_LIMIT", "TOUCH_ENTRY")]
            for b in sorted(r["id"] for r in rs if r["ev"] == "TOUCH" and r["k"] == 1 and r["id"] > a):
                if any(a < c < b for c in decided):
                    break
                assert any(r["id"] == b and r["k"] == 0 and r["ev"] in ("SKIP", "TOUCH_ENTRY") for r in rs), \
                    ("a T1 candidate was not tried after a skipped touch entry", n, a, b)


@pytest.mark.parametrize("case", RANDOM, ids=[f"seed{c[0]}" for c in RANDOM])
def test_random_series_invariants(exe, tmp_path, case):
    seed, kv = case
    recs, _ = run(exe, tmp_path, _bars(seed, 4000), hold=60, **kv)
    assert {"CONFIRM", "PLACE_LIMIT"} <= {r["ev"] for r in recs}
    _check(recs, kv)


def test_random_series_cover_the_new_paths(exe, tmp_path):
    """Across the cases: reversal and continuation confirmations (BOTH has both), touch entries opened and closed,
    limits placed while the setup's own touch position is open, and a touch entry kept out by a busy slot."""
    rev_conf = cont_conf_both = touch_open = owner = blocked_touch = 0
    for seed, kv in RANDOM:
        recs, st = run(exe, tmp_path, _bars(seed, 4000), hold=60, **kv)
        zone, open_ = {}, set()
        for r in recs:
            if r["ev"] == "ARMED":
                zone[r["id"]] = r["dir"]
            elif r["ev"] == "CONFIRM":
                if r["dir"] == -zone[r["id"]]:
                    rev_conf += 1
                elif kv.get("setup_type") == BOTH:
                    cont_conf_both += 1
            elif r["ev"] == "H_TOUCH_OPEN":
                touch_open += 1
                open_.add(r["id"])
            elif r["ev"] in ("H_TOUCH_CLOSE", "H_TOUCH_SKIP"):
                open_.discard(r["id"])
            elif r["ev"] == "PLACE_LIMIT" and r["id"] in open_:
                owner += 1
        if kv.get("touch_entry"):
            n_t1 = sum(1 for r in recs if r["ev"] == "TOUCH" and r["k"] == 1)
            n_te = sum(1 for r in recs if r["ev"] in ("TOUCH_ENTRY", "SKIP") and r["k"] == 0)
            blocked_touch += n_t1 - n_te
    assert rev_conf > 0 and cont_conf_both > 0 and touch_open > 0 and owner > 0 and blocked_touch > 0, \
        (rev_conf, cont_conf_both, touch_open, owner, blocked_touch)


@pytest.mark.parametrize("kv", [dict(setup_type=BOTH, touch_entry=1),
                                dict(setup_type=REV, touch_entry=1, anticipate=1, fvg_rule=FVG["LUXALGO"])],
                         ids=["both+touch", "rev+touch+anticipate"])
def test_new_rules_are_causal(exe, tmp_path, kv):
    """CLAUDE.md causality rule: the records up to bar t do not depend on later bars (a run on bars[:t+1] and a run
    with another future both start with the same records)."""
    bars = _bars(41, 1500)
    full, _ = run(exe, tmp_path, bars, hold=60, **kv)
    other = _bars(97, 1500)
    for t in (300, 701, 1111):
        cut, _ = run(exe, tmp_path, bars[:t + 1], hold=60, **kv)
        assert full[:len(cut)] == cut, t
        sh = bars[t][3] - other[t + 1][0]
        alt, _ = run(exe, tmp_path, bars[:t + 1] + [tuple(x + sh for x in b) for b in other[t + 1:]], hold=60, **kv)
        assert alt[:len(cut)] == cut, t
