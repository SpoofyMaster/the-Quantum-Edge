import numpy as np

from qe.features import seasonal_sigma
from qe.pine_parity import pine_seasonal_sigma
from qe.synthetic import generate


def test_pine_seasonal_algorithm_matches_python():
    # bid-only-style frame (ask = bid) so that log(close) returns equal log(mid) returns
    df = generate(start="2021-01-03", end="2021-03-15", seed=21)
    for s in "ohlc":
        df["a" + s] = df["b" + s]
    py = seasonal_sigma(df).to_numpy()
    pine = pine_seasonal_sigma(df.bc)
    both = ~np.isnan(py) & ~np.isnan(pine)
    assert both.sum() > 10000
    assert (np.isnan(py) == np.isnan(pine)).mean() > 0.999
    np.testing.assert_allclose(pine[both], py[both], rtol=1e-9)
