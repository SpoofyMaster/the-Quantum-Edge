import numpy as np
import pandas as pd
import pytest

from qe import backtest
from qe.labels import OUTCOME_STOP, OUTCOME_TARGET, OUTCOME_TIME, Arrays, simulate_trade


def _bars(rows):
    idx = pd.date_range("2024-01-16 10:00", periods=len(rows), freq="1min", tz="UTC")
    df = pd.DataFrame(rows, columns=["bo", "bh", "bl", "bc"], index=idx)
    for s in "ohlc":
        df["a" + s] = df["b" + s] + 0.0001
    df["volume"] = 1.0
    return df


def test_entry_is_next_bar_ask_and_stop_first():
    df = _bars([[1.0, 1.0, 1.0, 1.0], [1.0, 1.0, 1.0, 1.0], [1.0, 1.01, 0.99, 1.0], [1.0, 1.0, 1.0, 1.0]])
    r = simulate_trade(Arrays.from_df(df), 0, +1, 0.005, 0.005, 10)
    e, x, ep, xp, oc, pnl = r
    assert e == 1 and ep == pytest.approx(1.0001)
    assert x == 2 and oc == OUTCOME_STOP  # both hit in bar 2 -> stop assumed first
    assert pnl == pytest.approx(-0.005)


def test_short_target_and_time_exit():
    df = _bars([[1.0, 1.0, 1.0, 1.0], [1.0, 1.0, 1.0, 1.0], [1.0, 1.0, 0.99, 0.99], [1.0, 1.0, 1.0, 1.0]])
    e, x, ep, xp, oc, pnl = simulate_trade(Arrays.from_df(df), 0, -1, 0.02, 0.0095, 10)
    assert ep == 1.0 and oc == OUTCOME_TARGET and pnl == pytest.approx(0.0095)
    e, x, ep, xp, oc, pnl = simulate_trade(Arrays.from_df(df), 0, -1, 0.02, None, 2)
    assert oc == OUTCOME_TIME and x == 2 and pnl == pytest.approx(1.0 - (0.99 + 0.0001))


def test_gap_through_stop_fills_at_open():
    df = _bars([[1.0, 1.0, 1.0, 1.0], [1.0, 1.0, 1.0, 1.0], [0.98, 0.98, 0.97, 0.975]])
    e, x, ep, xp, oc, pnl = simulate_trade(Arrays.from_df(df), 0, +1, 0.005, None, 10)
    assert oc == OUTCOME_STOP and xp == pytest.approx(0.98) and pnl < -0.005


def test_backtest_respects_daily_loss_limit(small_bars, instruments, cfg):
    # always-long signal every 10 minutes with a tight stop: most days should hit the lockout
    sig = pd.DataFrame(index=small_bars.index[500::10])
    sig["direction"] = 1
    sig["stop_dist"] = 0.0003
    sig["target_dist"] = np.nan
    trades, rm = backtest.run({"EURUSD": small_bars}, {"EURUSD": sig}, instruments, cfg, backtest.BacktestConfig())
    assert len(trades)
    daily = trades.groupby("fx_day").pnl_usd.sum()
    # planned daily loss <= 1% of day-start equity; allow slippage/gap overshoot of 15% of one trade
    assert daily.min() > -1000 - 0.15 * 200
    assert (trades.planned_risk_usd <= 200 + 1e-6).all()
    assert (trades.bars <= 120).all()
    assert trades.attrs["rejects"]  # lockouts / overlapping signals were rejected
