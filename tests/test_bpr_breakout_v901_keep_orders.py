"""BprFvgEA 9.01: InpCancelAtSessionEnd = false keeps the pending orders, checked on the C++ transliteration of the MQL5
detector (the EA-only part of the fix: no session cancel, no 16:44 rollover delete, no 16:44 server-side expiry, is in
BprFvgEA.mq5 and is checked by reading).

The owner's report of 2026-10-18: "when i set on the input: cancel pending orders at 14:45 New York rollover on FALSE,
it keeps canceling pending orders ... focus only to fix this bug making the EA not canceling pending orders".

Besides the time-based cancels in the executor, the detector lost the orders in one more way: when the entry window
was closed, a new extreme cancelled them to move them (re-anchor) and the move could not be sent again. With the
switch off, the EA now sets env.keepOrders whenever no order can be sent (outside the entry window, near or in the
rollover): a new extreme then leaves the pending orders where they are. Harness keys: sess_off_from (the entry window
closed from that bar on) and keep_orders (env.keepOrders = !env.sessionEntryOk, the EA's mapping without its rollover
timing). Skipped without g++.
"""
import shutil

import pytest

from bk_scenarios import bar, mirror, v9_sequences
from test_bpr_breakout_v6_setups import CONT, REV, _bars, _check
from test_bpr_breakout_v6_setups import exe as _exe_fixture  # noqa: F401 (module-scoped harness build)
from test_bpr_breakout_v6_setups import run as _run6

exe = _exe_fixture
pytestmark = pytest.mark.skipif(shutil.which("g++") is None, reason="g++ not installed")
EA9 = dict(anticipate=1, t1_wait=0, rev_fvg=0, rev_rej_c=2)
D = pytest.mark.parametrize("d", [1, -1], ids=["bullish-BPR", "bearish-BPR"])


def run(exe, tmp_path, bars, **kv):
    kv.setdefault("ext", 1)
    return _run6(exe, tmp_path, bars, hold=50, **kv)


def side(bars, d):
    return bars if d > 0 else mirror(bars)


def of(recs, i, ev):
    return [r for r in recs if r["id"] == i and r["ev"] == ev]


def rev_id(recs, d):
    return next(r["id"] for r in recs if r["ev"] == "ARMED" and r["n"] == 13 and r["dir"] == d)


# the owner's C1 / C2 example up to its limits (placed on 23: sell 99.90 / 100.30 / 100.61, TP 98.30), then the entry
# window closes (from 24): 24 a new low (97.6), 25 a pullback to 99.95 that reaches the 50 % (99.90), 26 the target
KEPT = v9_sequences()["c1c2"][:24] + [bar(98.3, 98.5, 97.6, 97.7), bar(98.5, 99.95, 98.45, 99.8),
                                      bar(99.8, 99.85, 98.1, 98.2), bar(98.2, 98.25, 98.0, 98.1)]


@D
def test_kept_orders_are_not_cancelled_by_a_new_extreme(exe, tmp_path, d):
    """The entry window closes from bar 24. Without keepOrders (the bug), the new low on 24 cancels the three limits
    (NEW_EXTREME) and they cannot be sent again: no fill, no trade. With keepOrders they stay at their levels: the 50 %
    fills on 25 and the trade reaches its target (98.30) on 26."""
    bug, _ = run(exe, tmp_path, side(KEPT, d), setup_type=REV, sess_off_from=24, **EA9)
    i = rev_id(bug, d)
    assert [r["n"] for r in of(bug, i, "CANCEL")] == [24, 24, 24] and not of(bug, i, "CLOSED")
    assert [r["n"] for r in of(bug, i, "PLACE_LIMIT")] == [23, 23, 23]
    kept, _ = run(exe, tmp_path, side(KEPT, d), setup_type=REV, sess_off_from=24, keep_orders=1, **EA9)
    i = rev_id(kept, d)
    assert [r["n"] for r in of(kept, i, "PLACE_LIMIT")] == [23, 23, 23]
    assert {r["reason"] for r in of(kept, i, "CANCEL")} <= {"TARGET"}
    assert [r["n"] for r in of(kept, i, "CLOSED")] == [26]


@D
def test_inside_the_entry_window_the_orders_still_follow_the_fibonacci(exe, tmp_path, d):
    """keepOrders only acts when no order can be sent. Inside the entry window a new low still moves the limits
    (cancel + place again on 24), with or without the switch."""
    a, _ = run(exe, tmp_path, side(KEPT, d), setup_type=REV, keep_orders=1, **EA9)
    b, _ = run(exe, tmp_path, side(KEPT, d), setup_type=REV, **EA9)
    assert a == b
    i = rev_id(a, d)
    assert [r["n"] for r in of(a, i, "PLACE_LIMIT")] == [23, 23, 23, 24, 24, 24]


@pytest.mark.parametrize("st", [CONT, REV])
def test_random_series_kept_orders(exe, tmp_path, st):
    """Random series: the entry window closes right after a decision (the bar after a PLACE_LIMIT, for the first 12
    decisions). With keepOrders no pending order is cancelled by a new extreme or a session cancel after that, and
    the v6 invariants hold. Without it (the bug) at least one of these runs loses its orders to a new extreme."""
    bars = _bars(121, 3000)
    kv = dict(setup_type=st, **EA9)
    base, _ = run(exe, tmp_path, bars, **kv)
    offs = sorted({r["n"] + 1 for r in base if r["ev"] == "PLACE_LIMIT"})[:12]
    assert len(offs) >= 5
    lost = 0
    for off in offs:
        recs, _ = run(exe, tmp_path, bars, sess_off_from=off, keep_orders=1, **kv)
        _check(recs, kv)
        assert not [r for r in recs if r["ev"] == "CANCEL" and r["n"] >= off and
                    r["reason"] in ("NEW_EXTREME", "SESSION_END")], off
        bug, _ = run(exe, tmp_path, bars, sess_off_from=off, **kv)
        lost += any(r["ev"] == "CANCEL" and r["n"] >= off and r["reason"] == "NEW_EXTREME" for r in bug)
    assert lost >= 1
