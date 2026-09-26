import numpy as np
import pandas as pd

from qe.events import all_events
from qe.features import build_features
from qe.sessions import session_frame
from qe.synthetic import generate


def test_events_are_causal(cfg):
    """Perturbing bars after t must not change any event flag or direction at or before t."""
    df = generate(start="2021-01-03", end="2021-03-01", seed=9)
    cut = int(len(df) * 0.7)
    pert = df.copy()
    cols = ["bo", "bh", "bl", "bc", "ao", "ah", "al", "ac"]
    pert.iloc[cut + 1:, [pert.columns.get_loc(c) for c in cols]] *= 0.97
    a = all_events(df, build_features(df), session_frame(df.index, cfg), "EURUSD")
    b = all_events(pert, build_features(pert), session_frame(pert.index, cfg), "EURUSD")
    assert a.keys() == b.keys()
    for k in a:
        ma, da = a[k]
        mb, db = b[k]
        ma, mb = ma.fillna(False).iloc[: cut + 1], mb.fillna(False).iloc[: cut + 1]
        assert (ma == mb).all(), k
        da = pd.Series(np.asarray(da, float) if not np.isscalar(da) else da, index=df.index).iloc[: cut + 1]
        db = pd.Series(np.asarray(db, float) if not np.isscalar(db) else db, index=df.index).iloc[: cut + 1]
        assert np.allclose(da[ma].to_numpy(), db[ma].to_numpy(), equal_nan=True), k
