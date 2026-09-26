import numpy as np
import pandas as pd
import pytest

from qe.stats import (bootstrap_ci, deflated_sharpe, expected_max_sharpe, max_drawdown, probabilistic_sharpe,
                      reliability, stationary_bootstrap_indices)
from qe.validation import FinalTestLocked, guard_final_test, purged_train_mask, walk_forward_folds


def test_final_test_lock(cfg, monkeypatch):
    monkeypatch.delenv("QE_UNLOCK_FINAL_TEST", raising=False)
    ok = pd.date_range("2025-06-29", "2025-06-30 23:59", freq="1min", tz="UTC")
    guard_final_test(ok, cfg)
    bad = pd.date_range("2025-06-30", "2025-07-01 00:00", freq="1min", tz="UTC")
    with pytest.raises(FinalTestLocked):
        guard_final_test(bad, cfg)


def test_purging_removes_overlapping_labels():
    f = walk_forward_folds("2021-01-01", "2021-03-01", None, 10, min_train_days=30)[0]
    ev = pd.date_range("2021-01-25", "2021-02-15", freq="1h", tz="UTC")
    fold = type(f)(*(t.tz_localize("UTC") for t in (f.train_start, f.train_end, f.test_start, f.test_end)))
    label_end = pd.Series(ev + pd.Timedelta(minutes=120), index=ev)
    m = purged_train_mask(ev, label_end, fold, pd.Timedelta(minutes=240))
    kept = ev[m]
    assert kept.max() + pd.Timedelta(minutes=120) < fold.test_start - pd.Timedelta(minutes=240) + pd.Timedelta(hours=1)
    assert (label_end[kept] < fold.test_start - pd.Timedelta(minutes=240)).all()


def test_walk_forward_folds_are_chronological():
    folds = walk_forward_folds("2020-01-01", "2021-01-01", 180, 30)
    assert all(a.test_end <= b.test_end for a, b in zip(folds, folds[1:]))
    assert all(f.train_end <= f.test_start for f in folds)


def test_stationary_bootstrap_indices_valid():
    idx = stationary_bootstrap_indices(1000, 10, np.random.default_rng(0))
    assert idx.min() >= 0 and idx.max() < 1000
    # average run length of consecutive indices ~ mean block
    runs = np.sum(np.diff(idx) != 1) + 1
    assert 60 < runs < 160


def test_bootstrap_ci_covers_zero_for_noise():
    x = np.random.default_rng(1).standard_normal(3000)
    p, lo, hi = bootstrap_ci(x, B=500)
    assert lo < 0 < hi


def test_psr_and_dsr():
    rng = np.random.default_rng(2)
    good = rng.normal(0.15, 1, 2000)
    assert probabilistic_sharpe(good) > 0.99
    # deflating for many trials lowers confidence
    assert deflated_sharpe(good, 1000, 0.002) < probabilistic_sharpe(good)
    assert expected_max_sharpe(1, 0.01) == 0.0


def test_max_drawdown():
    assert max_drawdown([1, -2, -1, 3, -5]) == pytest.approx(5)


def test_reliability_perfectly_calibrated():
    rng = np.random.default_rng(3)
    p = rng.random(20000)
    y = rng.random(20000) < p
    _, ece = reliability(p, y)
    assert ece < 0.02
