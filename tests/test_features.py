import numpy as np
import pandas as pd

from qe.features import build_features


def test_features_are_causal(small_bars):
    """Perturbing bars AFTER t must not change any feature at or before t."""
    base = build_features(small_bars)
    cut = len(small_bars) // 2
    pert = small_bars.copy()
    rng = np.random.default_rng(0)
    cols = ["bo", "bh", "bl", "bc", "ao", "ah", "al", "ac"]
    pert.iloc[cut + 1:, [pert.columns.get_loc(c) for c in cols]] *= (1 + rng.normal(0, 0.01, (len(pert) - cut - 1, 1)))
    pert.iloc[cut + 1:, pert.columns.get_loc("volume")] *= 3
    new = build_features(pert)
    pd.testing.assert_frame_equal(base.iloc[: cut + 1], new.iloc[: cut + 1])


def test_features_finite_after_warmup(small_bars):
    # seasonal features need >= 4 prior weeks; small_bars has < 3 weeks, so test the rest here
    f = build_features(small_bars, seasonal=False).iloc[3000:]
    assert f.notna().mean().min() > 0.95
