"""Smoke test of the EXP010 pipeline (experiments/exp010_bpr_fvg_ea.py) on SYNTHETIC bars. This checks only that the
plumbing works before the pre-registered run on market data: frames, M5 resampling, session arrays, simulator call
and trade table. It makes no claim about performance."""
import importlib.util
from pathlib import Path

import pandas as pd

from qe.strategies.bpr_fvg import StrategyParams
from qe.synthetic import generate

ROOT = Path(__file__).resolve().parents[1]


def _exp():
    spec = importlib.util.spec_from_file_location("exp010", ROOT / "experiments/exp010_bpr_fvg_ea.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_session_arrays_follow_the_spec_window():
    exp = _exp()
    idx = pd.DatetimeIndex(["2024-07-10 07:00", "2024-07-10 06:59", "2024-07-10 18:44", "2024-07-10 18:45",
                            "2024-07-10 20:44", "2024-07-13 12:00"], tz="UTC")
    entry_ok, cancel_now, flat_now, fx = exp.session_arrays(idx)
    # 07:00 UTC = 08:00 London (BST); 18:44 UTC = 14:44 New York (EDT); 18:45 = 14:45; 20:44 = 16:44; Saturday
    assert entry_ok == [True, False, True, False, False, False]
    assert cancel_now == [not x for x in entry_ok]
    assert flat_now == [False, False, False, False, True, False]
    assert len(fx) == len(idx)


def test_pipeline_runs_on_synthetic_bars():
    exp = _exp()
    # sigma_min is a per-minute log return: 0.0002 is about 0.4 USD per minute at 2000
    m1 = generate(start="2021-03-01", end="2021-03-20", price0=2000.0, sigma_min=0.0002, base_spread=0.10, seed=3)
    m1 = m1.assign(sp=m1["ao"] - m1["bo"])
    frame = m1[["bo", "bh", "bl", "bc", "sp"]]
    for f in (frame, exp.to_m5(m1)):
        trades, diag = exp.run_variant(f, StrategyParams(**exp.BASE))
        assert diag["counters"]["bars"] == len(f)
        assert diag["setup_outcomes"]
        if len(trades):
            assert {"entry_time", "exit_time", "direction", "R", "pnl_usd", "outcome"} <= set(trades.columns)
            assert (trades.exit_time >= trades.entry_time).all()
            hold = (trades.exit_time - trades.entry_time).dt.total_seconds() / 60
            assert (hold <= 120 + 5).all()  # 120 min cap (an M5 bar of slack)
    m5 = exp.to_m5(m1)
    assert m5.index[1] - m5.index[0] == pd.Timedelta("5min")
    eps = 1e-9  # the synthetic generator's high/low can sit one ulp inside open/close (separate log sums)
    assert (m5.bh >= m5[["bo", "bc"]].max(axis=1) - eps).all() and (m5.bl <= m5[["bo", "bc"]].min(axis=1) + eps).all()
