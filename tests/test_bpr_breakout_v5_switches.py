"""BprFvgEA v5 entry switches, checked on the C++ transliteration of the MQL5 detector only.

The owner asked for v5 in MQL5 only (2026-10-11), so the Python reference qe/strategies/bpr_breakout.py has no
counterpart for these two detector parameters (BfParams in mql5/BprFvgEA/include/BfDefines.mqh):

- ``anticipate`` (InpAnticipateEntries): decide on the confirmation bar and on every leg bar (FVG condition still
  required) instead of waiting for a pullback candle; a new extreme while the limits are pending cancels them and
  decides again on the same bar (the slot its own limits held is given back through env.slotOwner);
- ``leg_break_on_close`` (InpLegBreakOnClose): LEG_BROKEN only when a candle CLOSES beyond the leg origin.

With both off the parity harness (tests/test_bpr_breakout_ea_harness.py) still compares every record with the Python
reference. Here the switched-on rules are checked against hand-computed expectations (spec
research/indicators/BPR_BREAKOUT_FIB_SPEC.md section 4 and its v5 notes), invariants on random series, and the
causality (prefix) property. This checks decision logic, not MetaEditor compilation and not MT5 order execution.
Skipped without g++.
"""
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from bk_scenarios import base, mirror, scenarios, v5_sequences

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools/mql5_cpp_harness"
INC = ROOT / "mql5/BprFvgEA/include"
GXX = shutil.which("g++")
pytestmark = pytest.mark.skipif(GXX is None, reason="g++ not installed")

SP = 0.1            # constant spread of the harness runs
TICK = 0.01
FVG = {"LUXALGO": 0, "ANY_GAP": 1, "NONE": 2}   # ENUM_BF_FVGRULE order
# the last 14 counters of the STATS line, in BF_STAT_* order (tests/test_bpr_breakout_ea_harness.py STAT_KEYS)
STAT_TAIL = ["BLOCKED_SLOT", "BLOCKED_SESSION", "BLOCKED_RISK", "BLOCKED_SPREAD", "WAIT_NO_FVG", "REANCHOR", "RETRY",
             "BREAK_FAIL", "CONFIRM", "PLACE_LIMIT", "ARMED", "CLOSED", "TOUCH", "BREAKOUT"]


def stat(st, name):
    return st[len(st) - len(STAT_TAIL) + STAT_TAIL.index(name)]


@pytest.fixture(scope="module")
def exe(tmp_path_factory):
    d = tmp_path_factory.mktemp("bk5")
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


def run(exe, tmp_path, bars, **kv):
    """-> (records, stats list). kv are bk_main keys (anticipate=1, fvg_rule=1, ...)."""
    bf = tmp_path / "bars.txt"
    bf.write_text("".join(" ".join(repr(float(x)) for x in b) + "\n" for b in bars))
    args = [f"sp={SP}", "hold_bars=3"] + [f"{k}={v}" for k, v in kv.items()]
    res = subprocess.run([str(exe), str(bf), *args], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert "lost events 0 intents 0" in res.stderr, res.stderr
    lines = res.stdout.splitlines()
    assert lines[-1].startswith("STATS")
    return [json.loads(ln) for ln in lines[:-1]], [int(x) for x in lines[-1].split()[1:]]


def main_id(recs):
    """the traded setup of a hand-built sequence: the first one confirmed (id 1 long; the mirrored bars also arm a
    second short BPR first, so the short one is id 2)"""
    return next(r["id"] for r in recs if r["ev"] == "CONFIRM")


def at(recs, n, ev=None):
    """records of the traded setup on bar n (optionally of one event type)"""
    sid = main_id(recs) if any(r["ev"] == "CONFIRM" for r in recs) else 1
    return [r for r in recs if r["n"] == n and r["id"] == sid and (ev is None or r["ev"] == ev)]


def fib_prices(O, X, d, sp=SP, fibs=(50.0, 61.8, 71.0)):  # noqa: E741
    """Expected limit prices of the detector (spec s.5), rounded to the tick like RoundTick."""
    L = d * (X - O)
    out = []
    for f in fibs:
        P = X - d * (f / 100.0) * L
        if d > 0:
            P += sp
        out.append(round(round(P / TICK) * TICK, 2))
    return out


# hand-built sequences: tests/bk_scenarios.py v5_sequences() (long; the short side is mirror() of each). They are
# also in the parity set (tests/test_bpr_breakout_ea_harness.py), where the switches-off EA must equal the v4 Python
# reference on them.
V5 = v5_sequences()


def seq(name, d):
    return V5[name] if d > 0 else mirror(V5[name])


# ---------------------------------------------------------------------------------------------------------------
def test_explicit_zero_equals_default(exe, tmp_path):
    """anticipate=0 / leg_break_on_close=0 are the defaults (records and counters). That the defaults equal v4 is
    checked against the Python reference on the same sequences in tests/test_bpr_breakout_ea_harness.py."""
    seqs = dict(scenarios())
    seqs.update(V5)
    for name, bars in seqs.items():
        for rule in FVG.values():
            a = run(exe, tmp_path, bars, fvg_rule=rule)
            b = run(exe, tmp_path, bars, fvg_rule=rule, anticipate=0, leg_break_on_close=0)
            assert a == b, name


@pytest.mark.parametrize("d", [1, -1], ids=["long", "short"])
def test_anticipate_decides_on_the_confirmation_bar(exe, tmp_path, d):
    """ANY_GAP: the gap on the confirmation candle 17 is an FVG after the reference candle 14, so the three limits
    are decided on 17 itself (default: on the first pullback candle 19). 18 makes a new extreme: the pending limits
    are cancelled (NEW_EXTREME) and decided again on the same bar 18 at the new extreme."""
    bars = base() if d > 0 else mirror(base())
    O, X17, X18 = (99.5, 101.3, 101.6) if d > 0 else (100.5, 98.7, 98.4)  # noqa: E741
    dflt, _ = run(exe, tmp_path, bars, fvg_rule=FVG["ANY_GAP"])
    assert at(dflt, 17, "PLACE_LIMIT") == [] and len(at(dflt, 19, "PLACE_LIMIT")) == 3
    recs, _ = run(exe, tmp_path, bars, fvg_rule=FVG["ANY_GAP"], anticipate=1)
    p17 = at(recs, 17, "PLACE_LIMIT")
    assert [r["k"] for r in p17] == [1, 2, 3]
    assert all(r["O"] == pytest.approx(O) and r["X"] == pytest.approx(X17) for r in p17)
    if d > 0:
        assert [r["P"] for r in p17] == pytest.approx(fib_prices(O, X17, d))
    r18 = at(recs, 18)
    assert [(r["ev"], r["k"], r["reason"]) for r in r18] == \
        [("CANCEL", 1, "NEW_EXTREME"), ("CANCEL", 2, "NEW_EXTREME"), ("CANCEL", 3, "NEW_EXTREME"),
         ("PLACE_LIMIT", 1, None), ("PLACE_LIMIT", 2, None), ("PLACE_LIMIT", 3, None)]
    assert all(r["X"] == pytest.approx(X18) for r in r18 if r["ev"] == "PLACE_LIMIT")
    assert at(recs, 19, "PLACE_LIMIT") == []        # nothing new on the pullback candle: the limits already wait


def test_anticipate_prices_long_match_formula(exe, tmp_path):
    recs, _ = run(exe, tmp_path, base(), fvg_rule=FVG["ANY_GAP"], anticipate=1)
    p18 = at(recs, 18, "PLACE_LIMIT")
    assert [r["P"] for r in p18] == pytest.approx(fib_prices(99.5, 101.6, 1))
    assert all(r["SL"] == pytest.approx(99.4) and r["TP"] == pytest.approx(101.6) for r in p18)


@pytest.mark.parametrize("d", [1, -1], ids=["long", "short"])
def test_anticipate_still_needs_the_fvg(exe, tmp_path, d):
    """LUXALGO: the engine's first FVG after the reference candle is on 18, so the confirmation bar 17 does not
    decide (counted as a bar without an FVG); 18 does."""
    bars = base() if d > 0 else mirror(base())
    recs, st = run(exe, tmp_path, bars, fvg_rule=FVG["LUXALGO"], anticipate=1)
    assert at(recs, 17, "PLACE_LIMIT") == []
    assert len(at(recs, 18, "PLACE_LIMIT")) == 3
    _, st0 = run(exe, tmp_path, bars, fvg_rule=FVG["LUXALGO"])
    # the confirmation bar 17 is a decision bar without an FVG: one more WAIT_NO_FVG than the default run
    assert stat(st, "WAIT_NO_FVG") == stat(st0, "WAIT_NO_FVG") + 1


@pytest.mark.parametrize("d", [1, -1], ids=["long", "short"])
def test_fast_pullback_is_filled_instead_of_leg_broken(exe, tmp_path, d):
    """The owner's case. Default: the limits are cancelled on the new high (20) and only decided again on a pullback
    candle; the pullback candle 21 already broke the origin -> DONE(LEG_BROKEN), no trade. Anticipated: the limits are
    moved on 20 and wait in the book, 21 fills them, 22 hits the stop -> CLOSED, never LEG_BROKEN."""
    bars = seq("fast_pullback", d)
    dflt, _ = run(exe, tmp_path, bars, fvg_rule=FVG["LUXALGO"])
    assert [(r["ev"], r["reason"]) for r in at(dflt, 21)] == [("DONE", "LEG_BROKEN")]
    assert at(dflt, 20, "PLACE_LIMIT") == []
    recs, _ = run(exe, tmp_path, bars, fvg_rule=FVG["LUXALGO"], anticipate=1)
    assert len(at(recs, 20, "PLACE_LIMIT")) == 3
    assert not [r for r in recs if r["reason"] == "LEG_BROKEN"]
    assert [r["ev"] for r in recs if r["n"] >= 21 and r["id"] == main_id(recs)] == ["CLOSED"]


@pytest.mark.parametrize("d", [1, -1], ids=["long", "short"])
def test_leg_break_on_close(exe, tmp_path, d):
    """No order is decided (no FVG). Default: the wick on 20 breaks the leg. On close: 20 survives, the close on 21
    breaks it."""
    bars = seq("wick_below_origin", d)
    dflt, _ = run(exe, tmp_path, bars, fvg_rule=FVG["LUXALGO"])
    assert [(r["ev"], r["reason"]) for r in at(dflt, 20)] == [("DONE", "LEG_BROKEN")]
    recs, _ = run(exe, tmp_path, bars, fvg_rule=FVG["LUXALGO"], leg_break_on_close=1)
    assert at(recs, 20) == []
    assert [(r["ev"], r["reason"]) for r in at(recs, 21)] == [("DONE", "LEG_BROKEN")]


@pytest.mark.parametrize("d", [1, -1], ids=["long", "short"])
def test_leg_break_on_close_boundary(exe, tmp_path, d):
    """A close exactly on the origin does not break the leg; one tick beyond it does."""
    bars = seq("close_on_origin", d)
    recs, _ = run(exe, tmp_path, bars, fvg_rule=FVG["LUXALGO"], leg_break_on_close=1)
    assert at(recs, 20) == []
    assert [(r["ev"], r["reason"]) for r in at(recs, 21)] == [("DONE", "LEG_BROKEN")]


@pytest.mark.parametrize("d", [1, -1], ids=["long", "short"])
def test_leg_break_on_close_then_decides_below_the_close(exe, tmp_path, d):
    """The pullback candle 19 wicks below the origin and closes at 100.3: default -> LEG_BROKEN; on close -> it is a
    pullback bar with an FVG: 50 % and 61.8 % are above the close (MISSED), the 71 % limit is placed."""
    bars = seq("wick_then_decide", d)
    dflt, _ = run(exe, tmp_path, bars, fvg_rule=FVG["LUXALGO"])
    assert [(r["ev"], r["reason"]) for r in at(dflt, 19)] == [("DONE", "LEG_BROKEN")]
    recs, _ = run(exe, tmp_path, bars, fvg_rule=FVG["LUXALGO"], leg_break_on_close=1)
    assert [(r["ev"], r["k"], r["reason"]) for r in at(recs, 19)] == \
        [("SKIP", 1, "MISSED"), ("SKIP", 2, "MISSED"), ("PLACE_LIMIT", 3, None)]


@pytest.mark.parametrize("d", [1, -1], ids=["long", "short"])
def test_move_respects_the_leg_expiry(exe, tmp_path, d):
    """leg_expiry_bars=2, confirmation on 17: the new high on 18 (1 bar after) moves the limits; the new high on 20
    (3 bars after) only cancels them, as in v4, and 21 ends the setup EXPIRED. No order after the expiry."""
    recs, _ = run(exe, tmp_path, seq("late_high", d), fvg_rule=FVG["ANY_GAP"], anticipate=1, leg_expiry_bars=2)
    assert len(at(recs, 18, "PLACE_LIMIT")) == 3
    assert [(r["ev"], r["reason"]) for r in at(recs, 20)] == [("CANCEL", "NEW_EXTREME")] * 3
    assert [(r["ev"], r["reason"]) for r in at(recs, 21)] == [("DONE", "EXPIRED")]


@pytest.mark.parametrize("d", [1, -1], ids=["long", "short"])
def test_move_on_the_last_bar_of_the_leg_window(exe, tmp_path, d):
    """Boundary: leg_expiry_bars=1, the new high on 18 is exactly 1 bar after the confirmation, so the limits are
    still moved on 18; 19 is past the window: they are cancelled (EXPIRED)."""
    recs, _ = run(exe, tmp_path, seq("late_high", d), fvg_rule=FVG["ANY_GAP"], anticipate=1, leg_expiry_bars=1)
    assert len(at(recs, 18, "PLACE_LIMIT")) == 3
    assert [(r["ev"], r["reason"]) for r in at(recs, 19)] == [("CANCEL", "EXPIRED")] * 3 + [("DONE", "EXPIRED")]


@pytest.mark.parametrize("d", [1, -1], ids=["long", "short"])
def test_no_move_on_a_session_cancel_bar(exe, tmp_path, d):
    """A new high on a bar whose next open is after the last entry time (env.sessionCancel, bar 18): the limits are
    cancelled and not sent again on that bar; the next bar (inside the window again) decides."""
    recs, st = run(exe, tmp_path, seq("late_high", d), fvg_rule=FVG["ANY_GAP"], anticipate=1, sess_cancel=18)
    assert [(r["ev"], r["reason"]) for r in at(recs, 18)] == [("CANCEL", "NEW_EXTREME")] * 3
    assert len(at(recs, 19, "PLACE_LIMIT")) == 3


@pytest.mark.parametrize("d", [1, -1], ids=["long", "short"])
def test_move_blocked_by_the_entry_window(exe, tmp_path, d):
    """The owner's same-bar decision still needs the other gates: with the entry window closed on 18 the limits are
    cancelled, the setup counts one BLOCKED_SESSION, and it decides on 19."""
    recs, st = run(exe, tmp_path, seq("late_high", d), fvg_rule=FVG["ANY_GAP"], anticipate=1, sess_off=18)
    _, st0 = run(exe, tmp_path, seq("late_high", d), fvg_rule=FVG["ANY_GAP"], anticipate=1)
    assert [(r["ev"], r["reason"]) for r in at(recs, 18)] == [("CANCEL", "NEW_EXTREME")] * 3
    assert len(at(recs, 19, "PLACE_LIMIT")) == 3
    assert stat(st, "BLOCKED_SESSION") == stat(st0, "BLOCKED_SESSION") + 1


@pytest.mark.parametrize("name,bar_n", [("spike_confirm", 18), ("spike_reanchor", 21)])
@pytest.mark.parametrize("d", [1, -1], ids=["long", "short"])
def test_spike_beyond_every_entry_waits(exe, tmp_path, d, name, bar_n):
    """A spike candle that only anticipation makes a decision bar (the confirmation candle 17 / the new-extreme candle
    20) closes beyond every entry: no record and no DONE(NO_LEVEL); the setup decides on the next candle exactly as
    v4 does on its pullback candle."""
    bars = seq(name, d)
    dflt, _ = run(exe, tmp_path, bars, fvg_rule=FVG["ANY_GAP"])
    recs, _ = run(exe, tmp_path, bars, fvg_rule=FVG["ANY_GAP"], anticipate=1)
    assert not [r for r in recs if r["ev"] == "DONE" and r["reason"] == "NO_LEVEL"]
    key = lambda r: (r["ev"], r["k"], r["reason"], r["P"], r["SL"], r["TP"])  # noqa: E731
    assert [key(r) for r in at(recs, bar_n)] == [key(r) for r in at(dflt, bar_n)]
    assert any(r["ev"] == "PLACE_LIMIT" for r in at(recs, bar_n))
    assert [r for r in at(recs, bar_n - 1) if r["ev"] in ("SKIP", "PLACE_LIMIT", "DONE")] == []


@pytest.mark.parametrize("d", [1, -1], ids=["long", "short"])
def test_all_missed_on_a_pullback_candle_still_ends_the_setup(exe, tmp_path, d):
    """Only the bars that anticipation adds are forgiving: on the ordinary pullback candle 18, entries all beyond the
    close end the setup DONE(NO_LEVEL), as in v4."""
    bars = seq("spike_then_low", d)
    dflt, _ = run(exe, tmp_path, bars, fvg_rule=FVG["ANY_GAP"])
    recs, _ = run(exe, tmp_path, bars, fvg_rule=FVG["ANY_GAP"], anticipate=1)
    assert at(recs, 17, "SKIP") == []
    assert [(r["ev"], r["reason"]) for r in at(recs, 18)] == [(r["ev"], r["reason"]) for r in at(dflt, 18)]
    assert at(recs, 18)[-1]["ev"] == "DONE" and at(recs, 18)[-1]["reason"] == "NO_LEVEL"


@pytest.mark.parametrize("d", [1, -1], ids=["long", "short"])
def test_mixed_skips_on_an_early_bar_end_the_setup(exe, tmp_path, d):
    """Only an all-MISSED early bar waits. On the confirmation candle 17 the 50 % entry is MISSED and the other two
    fail the cost filter (max_cost_r=0.01): nothing can be placed -> DONE(NO_LEVEL) on 17."""
    recs, _ = run(exe, tmp_path, seq("spike_confirm_mid", d), fvg_rule=FVG["ANY_GAP"], anticipate=1, max_cost_r=0.01)
    assert [(r["ev"], r["k"], r["reason"]) for r in at(recs, 17) if r["ev"] != "CONFIRM"] == \
        [("SKIP", 1, "MISSED"), ("SKIP", 2, "COST"), ("SKIP", 3, "COST"), ("DONE", 0, "NO_LEVEL")]


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
    # seed, keys
    (11, dict(anticipate=1)),
    (12, dict(anticipate=1, fvg_rule=FVG["ANY_GAP"])),
    (13, dict(anticipate=1, fvg_rule=FVG["NONE"], confirm_closes=1, max_cost_r=0)),
    (14, dict(leg_break_on_close=1)),
    (15, dict(anticipate=1, leg_break_on_close=1, max_touches=3, leg_expiry_bars=20)),
    (16, dict(anticipate=1, leg_break_on_close=1, direction=1, fvg_rule=FVG["ANY_GAP"], max_cost_r=0)),
    (17, dict(anticipate=1, direction=2, stop_fib=110.0, target_fib=-27.0, trade_from=300)),
    # series where another setup is ready on a bar on which the slot owner re-anchors (found by searching seeds
    # 100-400 for a difference between the detector and a copy in which that other setup may decide)
    (241, dict(anticipate=1, fvg_rule=FVG["NONE"], max_cost_r=0)),
    (305, dict(anticipate=1, fvg_rule=FVG["ANY_GAP"])),
]


def _check_invariants(recs, leg_expiry=60):
    """one setup with orders at a time; a new decision only once the setup's own limits are gone; on a bar where a
    setup re-anchored its pending limits (the slot was busy when the bar closed) only that setup may decide; geometry."""
    live: dict[int, set] = {}          # id -> levels pending or filled (never cancelled / dropped)
    ended: set = set()
    prev = None
    reanchored: dict[int, int] = {}    # bar -> setup that cancelled its pending limits for NEW_EXTREME on that bar
    confirm: dict[int, int] = {}       # id -> confirmation bar
    for r in recs:
        i, ev, k = r["id"], r["ev"], r["k"]
        if ev == "CONFIRM":
            confirm[i] = r["n"]
        if ev == "CANCEL" and r["reason"] == "NEW_EXTREME":
            reanchored[r["n"]] = i
        if ev == "PLACE_LIMIT":
            assert r["n"] - confirm[i] <= leg_expiry, ("order after the leg expiry", r)
            if r["n"] in reanchored:
                assert reanchored[r["n"]] == i, ("a setup decided while another one owned the slot", r)
            new_batch = prev is None or not (prev["ev"] == "PLACE_LIMIT" and prev["id"] == i and prev["n"] == r["n"])
            if new_batch:
                assert not live.get(i), ("new decision while its own levels are live", r)
                others = [j for j, s in live.items() if j != i and s and j not in ended]
                assert not others, ("two setups with orders", r, others)
            live.setdefault(i, set()).add(k)
            if r["dir"] > 0:
                assert r["SL"] < r["P"] < r["TP"], r
            else:
                assert r["TP"] < r["P"] < r["SL"], r
        elif ev in ("CANCEL", "DROP"):
            live.get(i, set()).discard(k)
        elif ev in ("DONE", "CLOSED"):
            ended.add(i)
            live.pop(i, None)
        prev = r


@pytest.mark.parametrize("case", RANDOM, ids=[f"seed{c[0]}" for c in RANDOM])
def test_random_series_invariants(exe, tmp_path, case):
    seed, kv = case
    recs, _ = run(exe, tmp_path, _bars(seed, 4000), **kv)
    assert {"CONFIRM", "PLACE_LIMIT"} <= {r["ev"] for r in recs}
    _check_invariants(recs, kv.get("leg_expiry_bars", 60))


def test_random_series_cover_the_new_paths(exe, tmp_path):
    """Across the cases: same-bar re-decisions after a re-anchor, decisions on the confirmation bar, fills that end in
    CLOSED, and setups blocked while another one holds the slot."""
    same_bar = on_confirm = closed = blocked = 0
    for seed, kv in RANDOM:
        recs, st = run(exe, tmp_path, _bars(seed, 4000), **kv)
        blocked += stat(st, "BLOCKED_SLOT")
        closed += sum(r["ev"] == "CLOSED" for r in recs)
        conf = {(r["id"], r["n"]) for r in recs if r["ev"] == "CONFIRM"}
        on_confirm += sum(r["ev"] == "PLACE_LIMIT" and (r["id"], r["n"]) in conf for r in recs)
        canc = {(r["id"], r["n"]) for r in recs if r["ev"] == "CANCEL" and r["reason"] == "NEW_EXTREME"}
        same_bar += sum(r["ev"] == "PLACE_LIMIT" and (r["id"], r["n"]) in canc for r in recs)
    assert same_bar > 0 and on_confirm > 0 and closed > 0 and blocked > 0, (same_bar, on_confirm, closed, blocked)


@pytest.mark.parametrize("kv", [dict(anticipate=1), dict(anticipate=1, leg_break_on_close=1, fvg_rule=1)],
                         ids=["anticipate", "anticipate+close"])
def test_new_rules_are_causal(exe, tmp_path, kv):
    """CLAUDE.md causality rule: the records produced up to bar t do not depend on later bars. A run on bars[:t+1]
    and a run whose bars after t are replaced by another series both start with the same records."""
    bars = _bars(21, 1500)
    full, _ = run(exe, tmp_path, bars, **kv)
    other_future = _bars(99, 1500)
    for t in (300, 701, 1111):
        cut, _ = run(exe, tmp_path, bars[:t + 1], **kv)
        assert full[:len(cut)] == cut, t
        assert all(r["n"] <= t for r in cut)
        tail = [(o - other_future[t + 1][0] + bars[t][3], h - other_future[t + 1][0] + bars[t][3],
                 lo - other_future[t + 1][0] + bars[t][3], c - other_future[t + 1][0] + bars[t][3])
                for (o, h, lo, c) in other_future[t + 1:]]
        alt, _ = run(exe, tmp_path, bars[:t + 1] + tail, **kv)
        assert alt[:len(cut)] == cut, t

