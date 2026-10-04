"""Unit tests for qe/video_strategy/structure.py and the incremental extension tracker (spec sections 2-5)."""
import numpy as np
import pandas as pd
import pytest

from qe.video_strategy import Params
from qe.video_strategy.engine import ExtTracker
from qe.video_strategy.fixtures import MTF_BEAR_TR, MTF_BULL_TR, MTF_RANGE, MTF_TREND_UP, gold_frame
from qe.video_strategy.structure import (BEAR, BULL, RANGE, TREND, TRENDING_RANGE, UNDEFINED, atr_sma,
                                         location_level, mtf_context, pivot_flags, prev_index, zigzag)


def test_atr_sma_is_simple_mean_of_true_range():
    h = np.array([10, 11, 12, 11, 13.0])
    l = np.array([9, 10, 10, 9, 11.0])
    c = np.array([9.5, 10.5, 11.5, 10, 12.5])
    tr = np.array([1, max(11, 9.5) - min(10, 9.5), 12 - 10, max(11, 11.5) - 9, 13 - 10])
    a = atr_sma(h, l, c, 3)
    assert np.isnan(a[:2]).all()
    assert a[2] == pytest.approx(tr[:3].mean())
    assert a[4] == pytest.approx(tr[2:5].mean())


def test_pivots_are_causal_and_defined_as_specified():
    rng = np.random.default_rng(1)
    h = 100 + np.cumsum(rng.normal(0, 1, 400))
    l = h - rng.uniform(0.1, 1.0, 400)
    for n in (1, 2, 3):
        ph, pl = pivot_flags(h, l, n)
        for k in range(n, 400 - n):
            exp_h = all(h[k] > h[k - i] for i in range(1, n + 1)) and all(h[k] >= h[k + i] for i in range(1, n + 1))
            exp_l = all(l[k] < l[k - i] for i in range(1, n + 1)) and all(l[k] <= l[k + i] for i in range(1, n + 1))
            assert ph[k] == exp_h and pl[k] == exp_l
        # changing bars after k+n never changes the flag at k
        h2, l2 = h.copy(), l.copy()
        h2[250:] += rng.normal(0, 5, 150)
        l2[250:] = h2[250:] - 0.5
        ph2, pl2 = pivot_flags(h2, l2, n)
        assert (ph2[: 250 - n] == ph[: 250 - n]).all() and (pl2[: 250 - n] == pl[: 250 - n]).all()


def test_prev_index():
    f = np.array([False, True, False, False, True, False])
    assert prev_index(f).tolist() == [-1, 1, 1, 1, 4, 4]


def test_zigzag_simple_sequence():
    # up 10, down 6, up 10 with theta 3 -> pivots LOW(0), HIGH, LOW and an up leg in progress
    c = np.concatenate([np.linspace(100, 110, 11), np.linspace(109.4, 104, 10), np.linspace(105, 114, 10)])
    o = np.concatenate([[100], c[:-1]])
    h, l = np.maximum(o, c), np.minimum(o, c)
    piv, tent, d = zigzag(o, h, l, c, 3.0)
    assert [k for _, _, k in piv] == [-1, 1, -1]
    assert piv[1][1] == pytest.approx(110) and piv[2][1] == pytest.approx(104)
    assert d == 1 and tent[1] == pytest.approx(114)


@pytest.mark.parametrize("mtf, cond, direction", [(MTF_RANGE, RANGE, None), (MTF_BEAR_TR, TRENDING_RANGE, BEAR),
                                                  (MTF_BULL_TR, TRENDING_RANGE, BULL), (MTF_TREND_UP, TREND, None)])
def test_mtf_condition_classification(mtf, cond, direction):
    co = pd.Timestamp("2024-03-06 02:00", tz="UTC")
    g = gold_frame(co, mtf + [(30, mtf[-1][1])])
    t = g.index.as_unit("ns").asi8
    ctx = mtf_context(t, g.bo.to_numpy(), g.bh.to_numpy(), g.bl.to_numpy(), g.bc.to_numpy(), co.value, Params())
    assert ctx.condition == cond
    if direction:
        assert ctx.direction == direction
    assert ctx.tradable == (cond != TREND)


def test_mtf_context_undefined_without_enough_history():
    co = pd.Timestamp("2024-03-06 02:00", tz="UTC")
    g = gold_frame(co, [(-100, 2000.0), (0, 2001.0), (10, 2001.0)])
    ctx = mtf_context(g.index.as_unit("ns").asi8, g.bo.to_numpy(), g.bh.to_numpy(), g.bl.to_numpy(), g.bc.to_numpy(), co.value,
                      Params())
    assert ctx.condition == UNDEFINED and not ctx.tradable


def test_location_levels_half_and_condition_aware():
    co = pd.Timestamp("2024-03-06 02:00", tz="UTC")
    g = gold_frame(co, MTF_BEAR_TR + [(30, 2012.5)])
    ctx = mtf_context(g.index.as_unit("ns").asi8, g.bo.to_numpy(), g.bh.to_numpy(), g.bl.to_numpy(), g.bc.to_numpy(), co.value,
                      Params())
    hs, le = ctx.last_down_leg
    ls, he = ctx.last_up_leg
    assert hs == pytest.approx(2022.02, abs=0.05) and le == pytest.approx(2011.98, abs=0.05)
    assert location_level(ctx, -1, Params()) == pytest.approx(le + 0.5 * (hs - le))
    assert location_level(ctx, 1, Params()) == pytest.approx(he - 0.5 * (he - ls))
    ca = Params(location_mode="CONDITION_AWARE")
    # bearish trending range: a sell is with the MTF direction (0.50), a buy is against it (1.00)
    assert location_level(ctx, -1, ca) == pytest.approx(le + 0.5 * (hs - le))
    assert location_level(ctx, 1, ca) == pytest.approx(ls)


def _brute(h, l, t, sign):
    hh, ll = h[: t + 1], l[: t + 1]
    if sign > 0:
        E = hh.max(); e = int(np.argmax(hh))
        O = ll[: e + 1].min(); o = int(np.flatnonzero(ll[: e + 1] == O)[-1])
        pb = max([max(0.0, hh[o:k].max() - ll[k]) for k in range(o + 1, e + 1)] or [0.0])
        size = E - O
    else:
        E = ll.min(); e = int(np.argmin(ll))
        O = hh[: e + 1].max(); o = int(np.flatnonzero(hh[: e + 1] == O)[-1])
        pb = max([max(0.0, hh[k] - ll[o:k].min()) for k in range(o + 1, e + 1)] or [0.0])
        size = O - E
    return E, e, O, o, (pb / size if size > 0 else 0.0)


@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_extension_tracker_matches_bruteforce(seed):
    rng = np.random.default_rng(seed)
    c = 100 + np.round(np.cumsum(rng.normal(0, 1, 80)), 1)       # rounding creates equal highs/lows (tie rules)
    o = np.concatenate([[100], c[:-1]])
    h = np.maximum(o, c) + np.round(rng.uniform(0, 0.5, 80), 1)
    l = np.minimum(o, c) - np.round(rng.uniform(0, 0.5, 80), 1)
    for sign in (1, -1):
        tr = ExtTracker(sign)
        for t in range(80):
            tr.update(t, h[t], l[t])
            E, e, O, oo, pb = _brute(h, l, t, sign)
            assert (tr.E, tr.e, tr.O, tr.o) == (E, e, O, oo)
            assert tr.PB == pytest.approx(pb)
