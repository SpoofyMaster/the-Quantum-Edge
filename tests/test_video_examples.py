"""Phase-19 regression tests: the six chart examples of the video, replayed as synthetic bar sequences
(qe/video_strategy/fixtures.py; research/VIDEO_REPLICATION_TEST.md). Expected decisions follow the author's."""
from dataclasses import replace

import pytest

from qe.video_strategy import Params, m15_preset
from qe.video_strategy import fixtures as fx
from qe.video_strategy.engine import run


def _run(ex, cfg, instruments, params=None):
    return run(ex.gold, ex.dxy, params or ex.params, instruments["XAUUSD"], cfg)


def _with_strength(params, n):
    return [replace(p, pivot_strength=n) for p in params]


@pytest.mark.parametrize("n", [1, 2, 3])
@pytest.mark.parametrize("name", sorted(fx.ALL))
def test_video_example_decision(name, n, cfg, instruments):
    ex = fx.ALL[name]()
    r = _run(ex, cfg, instruments, _with_strength(ex.params, n))
    exp = ex.expect
    in_candle = r.trades[r.trades.signal_time >= ex.candle_open] if len(r.trades) else r.trades
    if exp["trade"]:
        assert len(in_candle) == 1, (name, n, r.setups[["candle_open", "reason", "notes"]].tail(3))
        tr = in_candle.iloc[0]
        assert tr.direction == exp["direction"]
        assert tr.outcome == exp["outcome"]
        # stop beyond the extension extreme, target = 50% of the extension (spec 8)
        if tr.direction < 0:
            assert tr.sl > tr.ext_E and tr.tp == pytest.approx(tr.ext_O + 0.5 * (tr.ext_E - tr.ext_O) + tr.spread)
        else:
            assert tr.sl < tr.ext_E and tr.tp == pytest.approx(tr.ext_O + 0.5 * (tr.ext_E - tr.ext_O))
        # BREAK: entry on the bar after the shift bar
        assert (tr.entry_time - tr.signal_time).total_seconds() == 60
    else:
        assert in_candle.empty
        row = r.setups[r.setups.candle_open == ex.candle_open].iloc[0]
        assert row.reason == exp["reason"]


def test_t02_needs_the_m15_candle(cfg, instruments):
    """Finding 2 of VIDEO_REPLICATION_TEST.md: an H1-only tracker does not reproduce T-02; H1_AND_M15 does."""
    ex = fx.t02()
    h1 = _run(ex, cfg, instruments, [Params()])
    assert h1.trades.empty
    both = _run(ex, cfg, instruments, [Params(), m15_preset()])
    assert len(both.trades) == 1 and both.trades.iloc[0].tf == 15


def test_t03_is_rejected_only_because_of_dxy(cfg, instruments):
    ex = fx.t03()
    off = _run(ex, cfg, instruments, [replace(p, dxy_mode="OFF") for p in ex.params])
    assert len(off.trades) == 1 and off.trades.iloc[0].direction == -1      # the gold side alone would trade
    mirror_only = _run(ex, cfg, instruments, [replace(p, dxy_mode="MIRROR_DIRECTION") for p in ex.params])
    assert mirror_only.trades.empty


def test_t06_pullback_entry_is_better_than_break(cfg, instruments):
    ex = fx.t06()
    brk = _run(ex, cfg, instruments).trades.iloc[0]
    pb = _run(ex, cfg, instruments, [Params(entry_mode="PULLBACK_50")]).trades.iloc[0]
    assert pb.direction == brk.direction == 1
    assert pb.entry < brk.entry and pb.entry_time > brk.entry_time
    assert pb.outcome == 1


def test_t06_dxy_shift_is_required_in_full_mode(cfg, instruments):
    """COR-3: without the bearish DXY shift (DXY keeps rising), FULL rejects, MIRROR_DIRECTION accepts."""
    ex = fx.t06()
    rising = [(m, p) for m, p in fx.T06_DXY if m <= 29] + [(31, 104.18), (40, 104.20), (150, 104.25)]
    ex2 = fx._build("T-06b", ex.candle_open, fx.MTF_BEAR_TR[:-1] + [(0, 2012.0)], fx.T06_CANDLE,
                    fx.mirror(fx.MTF_BEAR_TR, 2012.0, 104.0), rising, [Params()], {})
    full = _run(ex2, cfg, instruments)
    row = full.setups[full.setups.candle_open == ex.candle_open].iloc[0]
    assert full.trades.empty and row.reason == "INV_DXY_NO_INVERSION"
    mirror_only = _run(ex2, cfg, instruments, [Params(dxy_mode="MIRROR_DIRECTION")])
    assert len(mirror_only.trades) == 1
