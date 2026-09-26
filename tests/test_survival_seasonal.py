import numpy as np
import pandas as pd
import pytest

from qe.features import build_features, seasonal_sigma
from qe.survival import cumulative_incidence
from qe.synthetic import generate


def test_cif_no_censoring_matches_empirical():
    rng = np.random.default_rng(0)
    d = rng.integers(1, 30, 5000)
    c = rng.choice([1, -1], 5000, p=[0.4, 0.6])
    cif = cumulative_incidence(d, c)
    assert cif.cif_target.iloc[-1] == pytest.approx(0.4, abs=0.02)
    assert cif.cif_target.iloc[-1] + cif.cif_stop.iloc[-1] == pytest.approx(1.0)
    t10 = ((d <= 10) & (c == 1)).mean()
    assert cif.cif_target.loc[10] == pytest.approx(t10, abs=1e-12)


def test_cif_handles_censoring_without_bias():
    rng = np.random.default_rng(1)
    n = 20000
    d = rng.integers(1, 60, n)
    c = rng.choice([1, -1], n, p=[0.5, 0.5])
    cens_time = rng.integers(1, 80, n)
    obs_d = np.minimum(d, cens_time)
    obs_c = np.where(d <= cens_time, c, 0)
    cif = cumulative_incidence(obs_d, obs_c, horizon=59)
    true = ((d <= 30) & (c == 1)).mean()
    assert cif.cif_target.loc[30] == pytest.approx(true, abs=0.015)


@pytest.fixture(scope="module")
def long_bars():
    return generate(start="2021-01-03", end="2021-04-01", seed=5)


def test_seasonal_sigma_tracks_intraday_pattern(long_bars):
    e = seasonal_sigma(long_bars, weeks=8, min_weeks=3)
    late = e[long_bars.index >= "2021-03-01"].dropna()
    assert len(late) > 10000
    by_hour = late.groupby(late.index.hour).median()
    # synthetic seasonality peaks near 13:30 UTC and is lowest around 20-23 UTC
    assert by_hour.loc[13] > 1.8 * by_hour.loc[21]


def test_seasonal_features_are_causal(long_bars):
    base = build_features(long_bars)
    cut = int(len(long_bars) * 0.7)
    pert = long_bars.copy()
    cols = ["bo", "bh", "bl", "bc", "ao", "ah", "al", "ac"]
    pert.iloc[cut + 1:, [pert.columns.get_loc(c) for c in cols]] *= 1.03
    new = build_features(pert)
    pd.testing.assert_frame_equal(base.iloc[: cut + 1], new.iloc[: cut + 1])
