"""BprFvgEA v10: the pending-order time limit and several setups at a time, checked on the C++ transliteration of the
MQL5 detector (the executor part, BprFvgEA.mq5, is checked by reading and the static check).

The owner's request of 2026-10-19: "first you have to set a limit time to configure on the input for how many time
the EA should let the limit orders before canceling them, and second thing the EA should trade all the setups
confirmed, for the moment when a setup is confirmed the EA place the limit orders but if on the same time another
setup is also confirmed the EA skip it and continue monitoring and tracking the first trade".

- ``pend_max_sec`` (InpPendingMaxMin x 60): a setup's limit orders are cancelled (EXPIRED, record flag ``pt``) on the
  first bar close at or after its first placement + the limit (env.now = the next bar's open; harness:
  ``(n + 1) * bar_sec``). A move at a new extreme does not restart it, a filled part runs on, a setup that waits to
  move its orders ends with it, and a decision the executor could not send (NotifyRetry) does not start it.
- ``max_setups`` (InpMaxSetups): every ready setup decides on its bar while a slot is free (env.freeSlots); a setup
  that moves its own orders on that bar keeps its slot; one touch entry at a time.

Harness keys (tools/mql5_cpp_harness/bk_main.cpp): ``fills`` (H_FILL lines), ``slots`` (one H_SLOTS line per bar: the
setups busy before the decisions, env.freeSlots, the BLOCKED_SLOT count of the bar, the busy count after it),
``retry_bar`` (the executor answers the decisions of that bar with NotifyRetry), ``bar_sec``. Skipped without g++.
"""
import shutil
import subprocess

import pytest

from bk_scenarios import bar, mirror, scenarios, v5_sequences, v6_sequences, v9_sequences
from test_bpr_breakout_v6_setups import BOTH, CONT, REV, SP, _bars, stat
from test_bpr_breakout_v6_setups import exe as _exe_fixture  # noqa: F401 (module-scoped harness build)
from test_bpr_breakout_v6_setups import run as _run6

exe = _exe_fixture
pytestmark = pytest.mark.skipif(shutil.which("g++") is None, reason="g++ not installed")
EA9 = dict(anticipate=1, t1_wait=0, rev_fvg=0, rev_rej_c=2)
D = pytest.mark.parametrize("d", [1, -1], ids=["bullish-BPR", "bearish-BPR"])
MS = pytest.mark.parametrize("ms", [1, 5], ids=["one-setup", "five-setups"])

# the owner's C1 / C2 example up to its limits (placed on 23: sell 99.90 / 100.30 / 100.61, 0 % = 98.20), then:
C1C2 = v9_sequences()["c1c2"][:24]
FLAT = [bar(98.6, 98.9, 98.4, 98.7)] * 12          # no new low, no fill
NEW_LOW = bar(98.3, 98.5, 97.6, 97.7)              # 24: a new low, the limits move (99.60 / 100.07 / 100.44)
FLAT2 = [bar(97.9, 98.2, 97.8, 98.0)] * 12         # after the new low: no new low, no fill
FILL = [bar(98.5, 99.95, 98.45, 99.8), bar(99.8, 99.85, 98.1, 98.2), bar(98.1, 98.2, 97.2, 97.3)]  # 25 fills L1


def run(exe, tmp_path, bars, **kv):
    kv.setdefault("ext", 1)
    return _run6(exe, tmp_path, bars, hold=50, **kv)


def run_err(exe, tmp_path, bars, hold=60, **kv):
    """-> (records, stats, MAXBUSY) for the random series (fvg_rule ANY_GAP, ext=1 as in the v6 helper)."""
    kv.setdefault("ext", 1)
    kv.setdefault("fvg_rule", 1)
    bf = tmp_path / "bars.txt"
    bf.write_text("".join(" ".join(repr(float(x)) for x in b) + "\n" for b in bars))
    res = subprocess.run([str(exe), str(bf), f"sp={SP}", f"hold_bars={hold}"] + [f"{k}={v}" for k, v in kv.items()],
                         capture_output=True, text=True)
    assert res.returncode == 0 and "lost events 0 intents 0" in res.stderr, res.stderr
    import json
    lines = res.stdout.splitlines()
    mb = next(int(x.split()[1]) for x in res.stderr.splitlines() if x.startswith("MAXBUSY"))
    return [json.loads(ln) for ln in lines[:-1]], [int(x) for x in lines[-1].split()[1:]], mb


def side(bars, d):
    return bars if d > 0 else mirror(bars)


def rev_id(recs, d):
    return next(r["id"] for r in recs if r["ev"] == "ARMED" and r["n"] == 13 and r["dir"] == d)


def of(recs, i, *evs):
    return [(r["n"], r["ev"], r["k"], r["reason"], r["pt"]) for r in recs if r["id"] == i and r["ev"] in evs]


# ---------------------------------------------------------------------------------------------------------------
# the pending-order time limit
# ---------------------------------------------------------------------------------------------------------------
@D
@pytest.mark.parametrize("m", [1, 2, 3, 5, 9])
def test_time_limit_cancels_the_unfilled_orders(exe, tmp_path, d, m):
    """Placed on 23 (in the book from the open of 24), no fill: cancelled on the close of 23 + m (the open of 24 + m),
    EXPIRED with the time-limit flag, and the setup ends. The cancel intents carry the flag too (the EA's log text).
    Without the limit the orders stay."""
    bars = side(C1C2 + FLAT, d)
    recs, _ = run(exe, tmp_path, bars, setup_type=REV, pend_max_sec=60 * m, intents=1, **EA9)
    i = rev_id(recs, d)
    assert of(recs, i, "PLACE_LIMIT", "CANCEL", "DONE") == \
        [(23, "PLACE_LIMIT", k, None, 0) for k in (1, 2, 3)] + \
        [(23 + m, "CANCEL", k, "EXPIRED", 1) for k in (1, 2, 3)] + [(23 + m, "DONE", 0, "EXPIRED", 1)]
    assert of(recs, i, "H_CANCEL") == [(23 + m, "H_CANCEL", k, "EXPIRED", 1) for k in (1, 2, 3)]
    recs = [r for r in recs if r["ev"] != "H_CANCEL"]
    base, _ = run(exe, tmp_path, bars, setup_type=REV, **EA9)
    assert of(base, i, "PLACE_LIMIT", "CANCEL", "DONE") == [(23, "PLACE_LIMIT", k, None, 0) for k in (1, 2, 3)]
    # everything before the cancel is the same as without the limit
    assert [r for r in recs if r["n"] < 23 + m] == [r for r in base if r["n"] < 23 + m]


@D
def test_time_limit_is_clock_time(exe, tmp_path, d):
    """M5 bars (bar_sec 300): a 10-minute limit is two bars."""
    recs, _ = run(exe, tmp_path, side(C1C2 + FLAT, d), setup_type=REV, pend_max_sec=600, bar_sec=300, **EA9)
    i = rev_id(recs, d)
    assert of(recs, i, "CANCEL", "DONE") == [(25, "CANCEL", k, "EXPIRED", 1) for k in (1, 2, 3)] + \
        [(25, "DONE", 0, "EXPIRED", 1)]


@D
def test_a_move_does_not_restart_the_time_limit(exe, tmp_path, d):
    """The new low on 24 moves the limits (cancel + place again on 24); the 3-minute limit still counts from 23."""
    recs, _ = run(exe, tmp_path, side(C1C2 + [NEW_LOW] + FLAT2, d), setup_type=REV, pend_max_sec=180, **EA9)
    i = rev_id(recs, d)
    assert of(recs, i, "PLACE_LIMIT", "CANCEL", "DONE") == \
        [(23, "PLACE_LIMIT", k, None, 0) for k in (1, 2, 3)] + \
        [(24, "CANCEL", k, "NEW_EXTREME", 0) for k in (1, 2, 3)] + \
        [(24, "PLACE_LIMIT", k, None, 0) for k in (1, 2, 3)] + \
        [(26, "CANCEL", k, "EXPIRED", 1) for k in (1, 2, 3)] + [(26, "DONE", 0, "EXPIRED", 1)]


@D
@MS
def test_time_limit_also_cancels_kept_orders(exe, tmp_path, d, ms):
    """9.01 InpCancelAtSessionEnd = false: from 24 no order can be sent, so the new low on 24 does not move the limits
    (keepOrders). The time limit is a cancel the owner asked for: it still ends them, on 23 + 3. The move's own
    cancel intents never carry the flag."""
    bars = side(C1C2 + [NEW_LOW] + FLAT2, d)
    kv = dict(setup_type=REV, sess_off_from=24, keep_orders=1, max_setups=ms, **EA9)
    recs, _ = run(exe, tmp_path, bars, pend_max_sec=180, intents=1, **kv)
    i = rev_id(recs, d)
    assert of(recs, i, "PLACE_LIMIT", "CANCEL", "DONE") == \
        [(23, "PLACE_LIMIT", k, None, 0) for k in (1, 2, 3)] + \
        [(26, "CANCEL", k, "EXPIRED", 1) for k in (1, 2, 3)] + [(26, "DONE", 0, "EXPIRED", 1)]
    assert of(recs, i, "H_CANCEL") == [(26, "H_CANCEL", k, "EXPIRED", 1) for k in (1, 2, 3)]
    base, _ = run(exe, tmp_path, bars, **kv)
    assert of(base, i, "CANCEL", "DONE") == []
    moved, _ = run(exe, tmp_path, side(C1C2 + [NEW_LOW] + FLAT2, d), setup_type=REV, pend_max_sec=180, intents=1,
                   max_setups=ms, **EA9)
    assert of(moved, i, "H_CANCEL")[:3] == [(24, "H_CANCEL", k, "NEW_EXTREME", 0) for k in (1, 2, 3)]


@D
def test_a_filled_part_runs_on(exe, tmp_path, d):
    """L1 fills on 25 = the end of a 2-minute limit (placed on 23): L2 / L3 are cancelled on 25 (EXPIRED, flag), the
    filled position runs on to its target (97.70), reached in bar 27: the harness reports the exit with the last
    closed bar, so the setup's CLOSED record is on 26. Without the limit L2 / L3 stay until the target cancels them on
    27 (CLOSED on 27)."""
    bars = side(C1C2 + [NEW_LOW] + FILL, d)
    recs, _ = run(exe, tmp_path, bars, setup_type=REV, pend_max_sec=120, fills=1, **EA9)
    i = rev_id(recs, d)
    assert [(r["n"], r["k"]) for r in recs if r["id"] == i and r["ev"] == "H_FILL"] == [(25, 1)]
    assert of(recs, i, "CANCEL", "CLOSED", "DONE") == \
        [(24, "CANCEL", k, "NEW_EXTREME", 0) for k in (1, 2, 3)] + \
        [(25, "CANCEL", k, "EXPIRED", 1) for k in (2, 3)] + [(26, "CLOSED", 0, None, 1)]
    base, _ = run(exe, tmp_path, bars, setup_type=REV, fills=1, **EA9)
    assert of(base, i, "CANCEL", "CLOSED", "DONE")[3:] == [(27, "CANCEL", k, "TARGET", 0) for k in (2, 3)] + \
        [(27, "CLOSED", 0, None, 0)]


@D
def test_a_setup_waiting_to_move_its_orders_ends_with_the_limit(exe, tmp_path, d):
    """The entry window closes from 24: the new low cancels the limits to move them, and they cannot be sent again.
    The setup waits in LEG; the 3-minute limit (from 23) ends it on 26. Without the limit it keeps waiting."""
    bars = side(C1C2 + [NEW_LOW] + FLAT2, d)
    recs, _ = run(exe, tmp_path, bars, setup_type=REV, pend_max_sec=180, sess_off_from=24, **EA9)
    i = rev_id(recs, d)
    assert of(recs, i, "CANCEL", "DONE") == [(24, "CANCEL", k, "NEW_EXTREME", 0) for k in (1, 2, 3)] + \
        [(26, "DONE", 0, "EXPIRED", 1)]
    base, _ = run(exe, tmp_path, bars, setup_type=REV, sess_off_from=24, **EA9)
    assert of(base, i, "DONE") == []


@D
@MS
def test_no_time_limit_before_the_first_placement(exe, tmp_path, d, ms):
    """(a) The entry window is closed from 23: the setup never places, so the time limit never ends it. (b) The
    executor cannot send the decision of 23 (NotifyRetry): the limit starts at the decision of 24 that was sent."""
    bars = side(C1C2 + FLAT, d)
    never, _ = run(exe, tmp_path, bars, setup_type=REV, pend_max_sec=60, sess_off_from=23, max_setups=ms, **EA9)
    assert not [r for r in never if r.get("pt")] and not [r for r in never if r["ev"] == "PLACE_LIMIT"]
    retry, _ = run(exe, tmp_path, bars, setup_type=REV, pend_max_sec=180, retry_bar=23, max_setups=ms, **EA9)
    i = rev_id(retry, d)
    assert of(retry, i, "PLACE_LIMIT", "CANCEL", "DONE") == \
        [(n, "PLACE_LIMIT", k, None, 0) for n in (23, 24) for k in (1, 2, 3)] + \
        [(27, "CANCEL", k, "EXPIRED", 1) for k in (1, 2, 3)] + [(27, "DONE", 0, "EXPIRED", 1)]


@D
@MS
def test_a_move_the_executor_could_not_send_keeps_the_time_limit(exe, tmp_path, d, ms):
    """The orders of 23 are in the book; the move of 24 cannot be sent (NotifyRetry on 24), the setup sends it on 25.
    The limit still counts from 23 (cancel on 26), not from the move."""
    bars = side(C1C2 + [NEW_LOW] + FLAT2, d)
    recs, _ = run(exe, tmp_path, bars, setup_type=REV, pend_max_sec=180, retry_bar=24, max_setups=ms, **EA9)
    i = rev_id(recs, d)
    assert of(recs, i, "PLACE_LIMIT", "CANCEL", "DONE") == \
        [(23, "PLACE_LIMIT", k, None, 0) for k in (1, 2, 3)] + \
        [(24, "CANCEL", k, "NEW_EXTREME", 0) for k in (1, 2, 3)] + \
        [(n, "PLACE_LIMIT", k, None, 0) for n in (24, 25) for k in (1, 2, 3)] + \
        [(26, "CANCEL", k, "EXPIRED", 1) for k in (1, 2, 3)] + [(26, "DONE", 0, "EXPIRED", 1)]


def test_explicit_defaults_equal_default(exe, tmp_path):
    """max_setups=1 and pend_max_sec=0 are the detector's defaults: given explicitly they change nothing. (That these
    defaults reproduce 9.01 was checked once against a 9.01 build, journal day 14; the parity harness keeps checking the
    defaults against the v4 Python reference.)"""
    seqs = dict(scenarios())
    seqs.update(v5_sequences())
    seqs.update(v6_sequences())
    seqs.update(v9_sequences())
    for name, bars in seqs.items():
        for kv in (dict(), dict(setup_type=BOTH, touch_entry=1, **EA9)):
            a = run(exe, tmp_path, bars, **kv)
            b = run(exe, tmp_path, bars, max_setups=1, pend_max_sec=0, bar_sec=300, **kv)
            assert a == b, (name, kv)


TL_CASES = [(61, dict(setup_type=CONT)), (62, dict(setup_type=REV, **EA9)), (63, dict(setup_type=BOTH, **EA9)),
            (64, dict(setup_type=CONT, anticipate=1, max_setups=4))]


@pytest.mark.parametrize("case", TL_CASES, ids=[f"seed{c[0]}" for c in TL_CASES])
@pytest.mark.parametrize("m", [2, 7, 15])
def test_random_series_time_limit(exe, tmp_path, case, m):
    """Random series, the limit recomputed from the records: for every setup with orders, no order is placed and none
    is left in the book from its first placement + m on; every time-limit cancel / end comes exactly then, and only
    there; the records before the first one are those of the run without the limit."""
    seed, kv = case
    bars = _bars(seed, 3000)
    recs, _, _ = run_err(exe, tmp_path, bars, pend_max_sec=60 * m, fills=1, **kv)
    base, _, _ = run_err(exe, tmp_path, bars, fills=1, **kv)
    # the harness prints a bar's fills (n = u) before the records of the exits checked on that bar (n = u - 1)
    recs = sorted(recs, key=lambda r: r["n"])
    base = sorted(base, key=lambda r: r["n"])
    first: dict[int, int] = {}
    live: dict[int, set] = {}                      # id -> levels in the book
    n_pt = 0

    def book_empty_after(n):                       # at the end of bar n
        for j, f in first.items():
            if n >= f + m:
                assert not live.get(j), ("an order is still in the book after its time limit", j, n, live[j])

    last_n = -1
    for r in recs:
        i, ev, n = r["id"], r["ev"], r["n"]
        if n != last_n and last_n >= 0:
            book_empty_after(last_n)
        last_n = n
        if ev == "PLACE_LIMIT":
            first.setdefault(i, n)
            assert n < first[i] + m, ("placed after the time limit", r)
            live.setdefault(i, set()).add(r["k"])
        elif ev in ("CANCEL", "DROP", "H_FILL"):
            assert ev != "H_FILL" or n <= first[i] + m, ("a fill after the time limit", r)
            live.get(i, set()).discard(r["k"])
        if r.get("pt") and r["reason"] == "EXPIRED" and ev in ("CANCEL", "DONE"):
            assert n == first[i] + m, r
            n_pt += 1
        elif r["reason"] == "EXPIRED" and ev == "CANCEL" and i in first:
            assert n <= first[i] + m, ("an EXPIRED cancel after the time limit without the flag", r)
    book_empty_after(last_n)
    assert n_pt > 0
    t0 = min(r["n"] for r in recs if r.get("pt"))
    assert [r for r in recs if r["n"] < t0] == [r for r in base if r["n"] < t0]


# ---------------------------------------------------------------------------------------------------------------
# several setups at a time
# ---------------------------------------------------------------------------------------------------------------
def _check_cap(recs, kv, cap):
    """v6's invariants with InpMaxSetups: at most cap setups with orders / positions (limits, touch positions); one
    touch position at a time, only into a free slot; no new decision while the setup's own levels are live; one trade
    per leg: no two setups with live levels in the same direction with the same stop (the same leg origin), and a
    setup ended as a duplicate names a setup that is trading in its direction."""
    allowed = {0: (1, -1), 1: (1,), 2: (-1,)}[kv.get("direction", 0)]
    live: dict[int, set] = {}
    leg: dict[int, tuple] = {}                     # id -> (dir, SL) of its live levels
    legO: dict[int, float] = {}                    # id -> leg origin of its orders (PLACE_LIMIT O)
    confO: dict[int, float] = {}                   # id -> leg origin at its confirmation (fixed from then on)
    touch: dict[int, str] = {}
    trade: dict[int, int] = {}
    prev = None

    def busy(excl=None):
        return {j for j, s in live.items() if s and j != excl} | {j for j in touch if j != excl}

    for r in recs:
        if r["ev"] == "H_SLOTS":
            continue
        i, ev, k, d = r["id"], r["ev"], r["k"], r["dir"]
        if ev == "CONFIRM":
            trade[i] = d
            confO[i] = r["O"]
            assert d in allowed, r
        elif ev == "TOUCH_ENTRY":
            assert not touch, ("a second touch position", r, touch)
            assert len(busy()) < cap, ("touch entry without a free slot", r, busy())
            touch[i] = "pending"
        elif ev == "H_TOUCH_OPEN":
            touch[i] = "open"
        elif ev in ("H_TOUCH_CLOSE", "H_TOUCH_SKIP"):
            touch.pop(i, None)
        elif ev == "PLACE_LIMIT":
            assert d == trade[i], r
            new_batch = prev is None or not (prev["ev"] == "PLACE_LIMIT" and prev["id"] == i and prev["n"] == r["n"])
            if new_batch:
                assert not live.get(i), ("new decision while its own levels are live", r)
                assert len(busy(excl=i)) < cap, ("more setups with orders / positions than max_setups", r, busy(i))
                same = [j for j, s in live.items() if s and j != i and leg.get(j) == (d, r["SL"])]
                assert not same, ("two setups trade the same leg", r, same)
                leg[i] = (d, r["SL"])
                legO[i] = r["O"]
            live.setdefault(i, set()).add(k)
            assert (r["SL"] < r["P"] < r["TP"]) if d > 0 else (r["TP"] < r["P"] < r["SL"]), r
        elif ev in ("CANCEL", "DROP"):
            live.get(i, set()).discard(k)
        elif ev in ("DONE", "CLOSED"):
            if ev == "DONE" and r.get("dup"):
                # the named setup holds the same leg: it has traded it (its levels may be moving on this bar, or held
                # in its EA context), in the same direction, from the same origin
                j = r["dup"]
                assert r["reason"] == "NO_LEVEL" and j in leg and leg[j][0] == trade[i], ("duplicate of what?", r)
                assert abs(legO[j] - confO[i]) < 0.005, ("a different leg ended as a duplicate", r, legO[j], confO[i])
            live.pop(i, None)
        prev = r


def _slots(recs):
    return {r["n"]: r for r in recs if r["ev"] == "H_SLOTS"}


def _check_slots(recs, cap):
    """Per bar (H_SLOTS, no touch entry): the setups that place without having been busy before the bar take the free
    slots, never more; a BLOCKED_SLOT only when they took them all; the busy count never exceeds cap. A ghost (a setup
    whose EA context is still busy, ghost_bars) holds its slot and never takes another one."""
    placed: dict[int, set] = {}
    for r in recs:
        if r["ev"] == "PLACE_LIMIT":
            placed.setdefault(r["n"], set()).add(r["id"])
    n_full = 0
    for n, s in _slots(recs).items():
        busy, ghosts = set(s["busy"]), set(s.get("ghosts", []))
        new = placed.get(n, set()) - busy - ghosts
        assert s["after"] <= cap and len(busy | ghosts) <= cap, s
        assert s["free"] == max(0, cap - len(busy | ghosts)), s
        assert len(new) <= s["free"], (s, new)
        if s["blk"] > 0:
            assert len(new) == s["free"], ("a setup was kept out while a slot was free", s, new)
            n_full += 1
    return n_full


# continuation setups rarely overlap in these series (seed 101 does); reversal setups often do
MULTI = [(101, dict(setup_type=CONT)), (72, dict(setup_type=REV, **EA9)), (73, dict(setup_type=BOTH, **EA9)),
         (101, dict(setup_type=CONT, anticipate=1)), (75, dict(setup_type=BOTH, anticipate=1, fvg_rule=2)),
         (76, dict(setup_type=BOTH, **EA9, pend_max_sec=600)),
         # without anticipation: a re-anchored setup decides again only on a later bar, so it needs a free slot then
         (72, dict(setup_type=BOTH, t1_wait=0, rev_fvg=0, rev_rej_c=2)),
         (73, dict(setup_type=BOTH, t1_wait=0, rev_fvg=0, rev_rej_c=2))]


@pytest.mark.parametrize("case", MULTI, ids=[f"case{j}-seed{c[0]}" for j, c in enumerate(MULTI)])
@pytest.mark.parametrize("cap", [2, 3, 5])
def test_random_series_several_setups(exe, tmp_path, case, cap):
    """Random series with max_setups = cap: the invariants above hold, the busy count reaches at least 2 and never
    exceeds cap, and more setups trade than with one at a time. With 2 slots the reversal series fill them and keep
    ready setups out (BLOCKED_SLOT)."""
    seed, kv = case
    bars = _bars(seed, 4000)
    recs, st, mb = run_err(exe, tmp_path, bars, max_setups=cap, slots=1, **kv)
    _check_cap(recs, kv, cap)
    n_full = _check_slots(recs, cap)
    assert mb == max(s["after"] for s in _slots(recs).values()) and 2 <= mb <= cap
    if cap == 2 and kv["setup_type"] != CONT:
        assert mb == 2 and n_full > 0 and stat(st, "BLOCKED_SLOT") > 0
    one, _, mb1 = run_err(exe, tmp_path, bars, **kv)
    assert mb1 == 1
    traded = {r["id"] for r in recs if r["ev"] == "PLACE_LIMIT"}
    traded1 = {r["id"] for r in one if r["ev"] == "PLACE_LIMIT"}
    assert len(traded) > len(traded1)


@pytest.mark.parametrize("case", MULTI, ids=[f"case{j}-seed{c[0]}" for j, c in enumerate(MULTI)])
def test_the_skipped_setup_now_trades_and_the_first_trade_is_unchanged(exe, tmp_path, case):
    """One at a time vs max_setups=5 on the same series: the records are the same up to the first bar where one at a
    time kept a ready setup out (the only link between setups is the slot). On that bar the multi run places every
    setup the single run placed plus the one(s) it skipped. The first setup that trades is followed exactly as before.
    In the first three cases that bar is the owner's case: two setups decide on the same bar."""
    seed, kv = case
    bars = _bars(seed, 4000)
    one, _, _ = run_err(exe, tmp_path, bars, **kv)
    multi, _, _ = run_err(exe, tmp_path, bars, max_setups=5, **kv)
    j = next(j for j, (a, b) in enumerate(zip(one, multi)) if a != b)
    n0 = min(one[j]["n"], multi[j]["n"])
    assert [r for r in one if r["n"] < n0] == [r for r in multi if r["n"] < n0]
    p1 = {r["id"] for r in one if r["n"] == n0 and r["ev"] == "PLACE_LIMIT"}
    pm = {r["id"] for r in multi if r["n"] == n0 and r["ev"] == "PLACE_LIMIT"}
    assert p1 < pm, (n0, p1, pm)
    if MULTI.index(case) < 3:
        assert len(p1) == 1 and len(pm) >= 2, (n0, p1, pm)
    f1 = next(r["id"] for r in one if r["ev"] == "PLACE_LIMIT")
    assert f1 == next(r["id"] for r in multi if r["ev"] == "PLACE_LIMIT")
    assert [r for r in one if r["id"] == f1] == [r for r in multi if r["id"] == f1]


def test_same_bar_decisions_are_frequent_with_reversals(exe, tmp_path):
    """With one setup at a time no bar has two deciding setups; with max_setups=5 many bars do (reversal setups)."""
    for seed, kv in MULTI[1:3]:
        bars = _bars(seed, 4000)
        for cap, lo, hi in ((1, 1, 1), (5, 2, 5)):
            recs, _, _ = run_err(exe, tmp_path, bars, max_setups=cap, **kv)
            per: dict[int, set] = {}
            for r in recs:
                if r["ev"] == "PLACE_LIMIT":
                    per.setdefault(r["n"], set()).add(r["id"])
            most = max(len(v) for v in per.values())
            assert lo <= most <= hi, (seed, cap, most)
            if cap > 1:
                assert sum(len(v) >= 2 for v in per.values()) >= 20


@pytest.mark.parametrize("seed", [81, 82, 83])
def test_a_setup_moving_its_orders_keeps_its_slot(exe, tmp_path, seed):
    """max_setups=2, anticipated entries: a busy setup that moves its orders at a new extreme places them again on the
    same bar even when no slot is free (the slots are full: free = 0). And a busy setup's records do not depend on the
    other setups: every setup that places first on the same bar after the same history is followed identically with
    2 and with 10 slots (except a setup the one-trade-per-leg rule ends in either run)."""
    kv = dict(setup_type=BOTH, anticipate=1, max_cost_r=0)
    bars = _bars(seed, 4000)
    recs, _, _ = run_err(exe, tmp_path, bars, max_setups=2, slots=1, **kv)
    wide, _, _ = run_err(exe, tmp_path, bars, max_setups=10, **kv)
    sl = _slots(recs)
    moved_full = 0
    for r in recs:
        if r["ev"] == "CANCEL" and r["reason"] == "NEW_EXTREME" and r["k"] == 1 and sl[r["n"]]["free"] == 0:
            if any(x["id"] == r["id"] and x["n"] == r["n"] and x["ev"] == "PLACE_LIMIT" for x in recs):
                moved_full += 1
    assert moved_full > 0
    by = lambda rs, i: [r for r in rs if r["id"] == i]  # noqa: E731
    same = 0
    for i in {r["id"] for r in recs if r["ev"] == "PLACE_LIMIT"}:
        a, b = by(recs, i), by(wide, i)
        fa = next(r for r in a if r["ev"] == "PLACE_LIMIT")
        fb = next((r for r in b if r["ev"] == "PLACE_LIMIT"), None)
        if fb is None or fa["n"] != fb["n"] or [r for r in a if r["n"] < fa["n"]] != [r for r in b if r["n"] < fa["n"]]:
            continue
        if any(r.get("dup") for r in a + b):
            continue                               # one trade per leg links it to another setup (its duplicate rule)
        # after the first placement: identical until the setup is back in LEG without orders after a move it could
        # not place (it then competes for a slot again), i.e. compare up to its first move without a same-bar placement
        stop = next((r["n"] for r in a if r["ev"] == "CANCEL" and r["reason"] == "NEW_EXTREME" and
                     not any(x["n"] == r["n"] and x["ev"] == "PLACE_LIMIT" for x in a)), None)
        cut = (lambda rs: [r for r in rs if stop is None or r["n"] <= stop])
        assert cut(a) == cut(b), i
        same += 1
    assert same >= 5


GHOST = [(72, dict(setup_type=BOTH, **EA9)), (73, dict(setup_type=REV, **EA9)), (75, dict(setup_type=CONT, anticipate=1))]


@pytest.mark.parametrize("case", GHOST, ids=[f"seed{c[0]}" for c in GHOST])
@pytest.mark.parametrize("cap", [2, 3])
def test_a_setup_whose_context_is_busy_takes_no_other_slot(exe, tmp_path, case, cap):
    """The EA cannot send a setup's orders while its context still holds its earlier ones (a delete that failed, a
    fill that raced its cancel; harness ghost_bars: the first move of each setup leaves its context busy for 60 bars).
    That context counts as used; the setup waits without taking a second slot, so it keeps no other setup out: the
    slot invariants hold with the ghosts, and a ghost's setup decides only on the bar of its own move."""
    seed, kv = case
    recs, _, _ = run_err(exe, tmp_path, _bars(seed, 4000), max_setups=cap, slots=1, ghost_bars=60, **kv)
    _check_slots(recs, cap)
    # one trade per leg also against a busy context: no setup places on a ghost's leg (same direction and stop)
    legs: dict[int, tuple] = {}
    for r in recs:
        if r["ev"] == "PLACE_LIMIT":
            legs.setdefault(r["id"], (r["dir"], r["SL"]))
    for s in _slots(recs).values():
        held = {legs[g] for g in s["ghosts"] if g in legs}
        for r in recs:
            if r["n"] == s["n"] and r["ev"] == "PLACE_LIMIT" and r["id"] not in s["ghosts"]:
                assert (r["dir"], r["SL"]) not in held, ("a setup placed on a busy context's leg", r)
    sl = _slots(recs)
    assert sum(1 for s in sl.values() if s["ghosts"]) > 100
    moved = {(r["n"], r["id"]) for r in recs if r["ev"] == "CANCEL" and r["reason"] == "NEW_EXTREME"}
    for r in recs:
        if r["ev"] == "PLACE_LIMIT" and r["id"] in sl[r["n"]]["ghosts"]:
            assert (r["n"], r["id"]) in moved, ("a setup with a busy context decided", r)


@pytest.mark.parametrize("cap", [2, 5])
@pytest.mark.parametrize("seed", [62, 72, 73])
def test_the_trade_holding_a_leg_keeps_it_while_it_moves(exe, tmp_path, seed, cap):
    """A setup that trades a leg and moves its orders at a new extreme is in LEG on that bar. A newer setup that
    confirms the same leg on the same bar must not take the leg (or the slot) from it: the newcomer ends as the
    duplicate, and the first trade places its moved orders. No setup that has placed orders ever ends as a duplicate
    on the bar of its own move."""
    kv = dict(setup_type=REV, **EA9)
    recs, _, _ = run_err(exe, tmp_path, _bars(seed, 4000), max_setups=cap, **kv)
    _check_cap(recs, kv, cap)
    moved = {(r["n"], r["id"]) for r in recs if r["ev"] == "CANCEL" and r["reason"] == "NEW_EXTREME"}
    assert moved
    for r in recs:
        if r["ev"] == "DONE" and r.get("dup"):
            assert (r["n"], r["id"]) not in moved, ("the moving trade lost its leg", r)


@pytest.mark.parametrize("case", [(72, REV), (73, BOTH), (74, REV)], ids=["seed72-REV", "seed73-BOTH", "seed74-REV"])
def test_one_trade_per_leg(exe, tmp_path, case):
    """Stacked BPRs often give their reversal setups the same leg (the same origin and extreme). Each would send the
    same three limits with the same stop: up to 5 times the risk on one trade. A setup whose leg (direction and origin,
    so its stop) another setup already trades ends DONE(NO_LEVEL), naming that setup (dup); no two setups ever hold
    live orders in the same direction with the same stop. One setup at a time is unchanged (no duplicate records)."""
    seed, st = case
    kv = dict(setup_type=st, **EA9)
    bars = _bars(seed, 4000)
    recs, _, _ = run_err(exe, tmp_path, bars, max_setups=5, **kv)
    _check_cap(recs, kv, 5)
    assert sum(1 for r in recs if r["ev"] == "DONE" and r.get("dup")) >= 3
    one, _, _ = run_err(exe, tmp_path, bars, **kv)
    assert not [r for r in one if r.get("dup")]


@pytest.mark.parametrize("gate", ["sess_off_from", "risk_off_from", "spread_off_from"])
@pytest.mark.parametrize("cap", [1, 3])
def test_several_setups_respect_the_gates(exe, tmp_path, cap, gate):
    """No order is placed while the entry window is closed, the daily risk is used up (env.riskOk) or the spread is
    too wide (env.spreadOk), from bar 1500 on: one at a time or several."""
    kv = dict(setup_type=BOTH, **EA9)
    recs, st, _ = run_err(exe, tmp_path, _bars(72, 3000), max_setups=cap, **{gate: 1500}, **kv)
    assert [r for r in recs if r["ev"] == "PLACE_LIMIT" and r["n"] < 1500]
    assert not [r for r in recs if r["ev"] == "PLACE_LIMIT" and r["n"] >= 1500]
    counters = {"sess_off_from": "BLOCKED_SESSION", "risk_off_from": "BLOCKED_RISK", "spread_off_from": "BLOCKED_SPREAD"}
    for g, name in counters.items():
        assert (stat(st, name) > 0) == (g == gate), (name, stat(st, name))


@pytest.mark.parametrize("seed", [92, 96, 98])
@pytest.mark.parametrize("cap", [2, 3])
def test_one_touch_entry_at_a_time(exe, tmp_path, seed, cap):
    """Touch entries with max_setups = cap: at most one touch position, at most one touch entry per bar, only into a
    free slot, and the touch position holds a slot. The setup of the open touch position places its own limits without
    another slot: also when every slot is taken (free = 0 before the bar)."""
    kv = dict(setup_type=BOTH, touch_entry=1, max_cost_r=0, **EA9)
    recs, _, _ = run_err(exe, tmp_path, _bars(seed, 4000), max_setups=cap, slots=1, **kv)
    _check_cap(recs, kv, cap)
    per_bar: dict[int, int] = {}
    for r in recs:
        if r["ev"] == "TOUCH_ENTRY":
            per_bar[r["n"]] = per_bar.get(r["n"], 0) + 1
    assert per_bar and max(per_bar.values()) == 1
    placed = {(r["n"], r["id"]) for r in recs if r["ev"] == "PLACE_LIMIT"}
    full = [s for s in _slots(recs).values() if s["owner"] > 0 and s["free"] == 0 and s["owner"] not in s["busy"] and
            (s["n"], s["owner"]) in placed]
    assert full


@pytest.mark.parametrize("kv", [dict(setup_type=BOTH, max_setups=3, pend_max_sec=420, **EA9),
                                dict(setup_type=CONT, anticipate=1, max_setups=5, pend_max_sec=120)])
def test_v10_is_causal(exe, tmp_path, kv):
    """CLAUDE.md causality rule: the records up to bar t do not depend on later bars."""
    bars = _bars(57, 1500)
    full, _, _ = run_err(exe, tmp_path, bars, **kv)
    other = _bars(93, 1500)
    for t in (300, 701, 1111):
        cut, _, _ = run_err(exe, tmp_path, bars[:t + 1], **kv)
        assert full[:len(cut)] == cut, t
        sh = bars[t][3] - other[t + 1][0]
        alt, _, _ = run_err(exe, tmp_path, bars[:t + 1] + [tuple(x + sh for x in b) for b in other[t + 1:]], **kv)
        assert alt[:len(cut)] == cut, t
