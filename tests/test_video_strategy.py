"""Engine-level tests: sessions (DST), DXY formula, exit simulation, risk sizing and causality (no look-ahead)."""
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from qe.video_strategy import Params
from qe.video_strategy.dxy import DXY_WEIGHTS, line_bars, synthetic_dxy_close
from qe.video_strategy.engine import Book, run, run_exit
from qe.video_strategy.fixtures import MTF_TREND_UP, T05_CANDLE, _build, mirror
from qe.video_strategy.sessions import is_trading_candle


def ts(s):
    return pd.Timestamp(s, tz="UTC")


def test_session_window_is_dst_correct():
    # Tokyo 10:00 = 01:00 UTC all year; London 11:00 = 11:00 UTC in winter, 10:00 UTC in summer
    assert is_trading_candle(ts("2024-01-10 01:00"), "ASIA2_TO_LONDON4")
    assert not is_trading_candle(ts("2024-01-10 00:00"), "ASIA2_TO_LONDON4")
    assert is_trading_candle(ts("2024-01-10 11:00"), "ASIA2_TO_LONDON4")
    assert not is_trading_candle(ts("2024-01-10 12:00"), "ASIA2_TO_LONDON4")
    assert is_trading_candle(ts("2024-07-10 10:00"), "ASIA2_TO_LONDON4")
    assert not is_trading_candle(ts("2024-07-10 11:00"), "ASIA2_TO_LONDON4")
    assert not is_trading_candle(ts("2024-07-13 02:00"), "ASIA2_TO_LONDON4")          # Saturday
    assert not is_trading_candle(ts("2024-07-10 14:00"), "ASIA2_TO_LONDON4")          # New York: never
    # STRICT: 2nd hour of Tokyo and the London open only
    assert is_trading_candle(ts("2024-07-10 01:00"), "STRICT")
    assert is_trading_candle(ts("2024-07-10 07:00"), "STRICT")       # 08:00 BST
    assert is_trading_candle(ts("2024-01-10 08:00"), "STRICT")       # 08:00 GMT
    assert not is_trading_candle(ts("2024-07-10 02:00"), "STRICT")
    # ALL: anything except the rollover blackout (16:45-17:30 New York)
    assert is_trading_candle(ts("2024-07-10 14:00"), "ALL")
    assert not is_trading_candle(ts("2024-07-10 21:00"), "ALL")      # 17:00 EDT


def test_synthetic_dxy_formula():
    idx = pd.date_range("2024-01-02", periods=3, freq="1min", tz="UTC")
    vals = {"EURUSD": 1.08, "USDJPY": 150.0, "GBPUSD": 1.27, "USDCAD": 1.35, "USDSEK": 10.5, "USDCHF": 0.88}
    closes = {k: pd.Series(v, index=idx) for k, v in vals.items()}
    expect = 50.14348112 * np.prod([vals[k] ** w for k, w in DXY_WEIGHTS.items()])
    got = synthetic_dxy_close(closes)
    assert got.iloc[0] == pytest.approx(expect, rel=1e-12)
    assert 95 < expect < 115
    with pytest.raises(ValueError):
        synthetic_dxy_close({k: closes[k] for k in list(closes)[:5]})
    bars = line_bars(pd.Series([1.0, 2.0, 1.5], index=idx))
    assert bars.o.tolist() == [1.0, 1.0, 2.0] and bars.h.tolist() == [1.0, 2.0, 2.0] and bars.l.tolist() == [1.0, 1.0, 1.5]


def _book(rows):
    a = np.array(rows, float)   # columns: bo bh bl bc, spread 0.1
    return Book(a[:, 0], a[:, 1], a[:, 2], a[:, 3], a[:, 0] + .1, a[:, 1] + .1, a[:, 2] + .1, a[:, 3] + .1)


def test_run_exit_stop_first_gap_and_time():
    b = _book([[10, 10.5, 9.5, 10], [10, 12, 8, 10], [10, 10, 10, 10]])
    # long: bar 1 touches both 8.5 stop and 11.5 target -> stop first
    assert run_exit(b, 1, 1, 10.0, 8.5, 11.5, 2, 0.01) == (1, 8.5 - 0.01, -1)
    # short exits on the ask: target at 9.0 needs ask low <= 9 (bar 1 ask low 8.1)
    assert run_exit(b, 1, -1, 10.0, 20.0, 9.0, 2, 0.01) == (1, 9.0, 1)
    # gap through the stop on a later bar fills at that bar's open
    g = _book([[10, 10, 10, 10], [7, 7.2, 6.9, 7], [7, 7, 7, 7]])
    assert run_exit(g, 0, 1, 10.0, 8.0, 12.0, 2, 0.0) == (1, 7.0, -1)
    # time exit at the close of the last bar
    assert run_exit(g, 0, 1, 10.0, 1.0, 20.0, 0, 0.0) == (0, 10.0, 0)


def test_trend_context_is_rejected(cfg, instruments):
    co = ts("2024-03-07 02:00")
    candle = [(m, p - 12.0) for m, p in T05_CANDLE]            # continue from the history's last price (1988)
    ex = _build("trend", co, MTF_TREND_UP, candle,
                mirror(MTF_TREND_UP, 1988.0, 104.0), mirror(candle, 1988.0, 104.0), [Params()], {})
    r = run(ex.gold, ex.dxy, ex.params, instruments["XAUUSD"], cfg)
    row = r.setups[r.setups.candle_open == co].iloc[0]
    assert row.reason == "INV_CONTEXT_TREND" and r.trades.empty


def _random_market(seed, days=4):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-03-04 00:00", periods=days * 1440, freq="1min", tz="UTC")
    step = rng.normal(0, 0.25, len(idx))
    c = 2000 + np.cumsum(step)
    o = np.concatenate([[2000.0], c[:-1]])
    h = np.maximum(o, c) + np.abs(rng.normal(0, 0.05, len(idx)))
    l = np.minimum(o, c) - np.abs(rng.normal(0, 0.05, len(idx)))
    gold = pd.DataFrame({"bo": o, "bh": h, "bl": l, "bc": c}, index=idx)
    for s in "ohlc":
        gold["a" + s] = gold["b" + s] + 0.10
    xc = 104 - 0.01 * (c - 2000) + np.cumsum(rng.normal(0, 0.002, len(idx)))
    xo = np.concatenate([[xc[0]], xc[:-1]])
    dxy = pd.DataFrame({"o": xo, "h": np.maximum(xo, xc) + 0.001, "l": np.minimum(xo, xc) - 0.001, "c": xc}, index=idx)
    return gold, dxy


RELAXED = Params(session_preset="ALL", min_ext_minutes=5, max_ext_pullback=0.9, shift_start_min=1,
                 shift_end_min=60, trend_max_ratio=0.0, min_location_retrace=0.0, pivot_strength=2)


def _signals(res, cut_time):
    if res.trades.empty:
        return []
    t = res.trades[res.trades.entry_time < cut_time]
    return list(zip(t.signal_time, t.direction, t.entry.round(6), t.sl.round(6), t.tp.round(6)))


@pytest.mark.parametrize("dxy_mode, entry_mode", [("OFF", "BREAK"), ("MIRROR_DIRECTION", "BREAK"), ("OFF", "PULLBACK_50")])
def test_no_lookahead_truncation_and_future_scramble(cfg, instruments, dxy_mode, entry_mode):
    gold, dxy = _random_market(5)
    p = replace(RELAXED, dxy_mode=dxy_mode, entry_mode=entry_mode)
    inst = instruments["XAUUSD"]
    full = run(gold, dxy, [p], inst, cfg)
    assert len(full.trades) >= 5, "fixture must produce trades for the test to be meaningful"
    for cut in (1500, 3100, 4700):
        cut_time = gold.index[cut - 3]                      # decisions and entries strictly before this time
        trunc = run(gold.iloc[:cut], dxy.iloc[:cut], [p], inst, cfg)
        assert _signals(full, cut_time) == _signals(trunc, cut_time)
        g2, x2 = _random_market(99)
        g2 = g2.iloc[cut:] - g2.iloc[cut] + gold.iloc[cut - 1].bc
        x2 = x2.iloc[cut:] - x2.iloc[cut] + dxy.iloc[cut - 1].c
        g2.index, x2.index = gold.index[cut:], dxy.index[cut:]
        scr = run(pd.concat([gold.iloc[:cut], g2]), pd.concat([dxy.iloc[:cut], x2]), [p], inst, cfg)
        assert _signals(full, cut_time) == _signals(scr, cut_time)


def test_risk_per_trade_and_one_position(cfg, instruments):
    gold, dxy = _random_market(7)
    r = run(gold, dxy, [replace(RELAXED, dxy_mode="OFF")], instruments["XAUUSD"], cfg, equity=100_000)
    assert len(r.trades) > 0
    assert (r.trades.planned_risk_usd <= 0.0020 * 100_000 * 1.10 + 1e-6).all()   # equity grows a little
    t = r.trades.sort_values("entry_time")
    assert (t.entry_time.iloc[1:].values > t.exit_time.iloc[:-1].values).all()    # never two positions at once
    assert (t.minutes <= 120).all()


def test_performance_report_fields():
    from qe.video_strategy.report import performance
    et = pd.date_range("2024-01-02 02:00", periods=6, freq="1D", tz="UTC")
    tr = pd.DataFrame({"entry_time": et, "exit_time": et + pd.Timedelta(minutes=9), "direction": [1, -1, 1, 1, -1, 1],
                       "pnl_usd": [200.0, -200.0, -200.0, 150.0, -200.0, 300.0], "R": [1.0, -1.0, -1.0, 0.75, -1.0, 1.5]})
    p = performance(tr)
    assert p["trades"] == 6 and p["win_rate"] == pytest.approx(0.5)
    assert p["gross_profit"] == 650 and p["gross_loss"] == 600 and p["profit_factor"] == pytest.approx(650 / 600)
    assert p["max_consecutive_losses"] == 2 and p["avg_duration_min"] == pytest.approx(10)
    assert p["max_drawdown_usd"] == pytest.approx(450)          # equity path 200, 0, -200, -50, -250, 50
    assert p["by_session"]["ASIA"]["trades"] == 6 and set(p["by_year"]) == {"2024"}
