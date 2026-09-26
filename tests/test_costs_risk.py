import math

import pytest

from qe.costs import breakeven_win_rate, commission_in_price_units, cost_in_R, value_per_price_unit
from qe.risk import OpenPosition, RiskManager, size_position


def test_eurusd_commission_equivalent(instruments):
    eu = instruments["EURUSD"]
    # $7 round trip on 100k EUR -> 0.00007 price units (0.7 pip)
    assert commission_in_price_units(eu, 1.10) == pytest.approx(0.00007)


def test_usdjpy_value_conversion(instruments):
    uj = instruments["USDJPY"]
    # 1 lot, 1.0 JPY move = 100000 JPY = 100000/150 USD
    assert value_per_price_unit(uj, 1.0, 150.0) == pytest.approx(100000 / 150)


def test_size_never_exceeds_budget_including_costs(instruments):
    for sym, price, stop in [("EURUSD", 1.1, 0.0008), ("XAUUSD", 2400.0, 3.0), ("USDJPY", 150.0, 0.12),
                             ("XAGUSD", 30.0, 0.08), ("GBPUSD", 1.27, 0.0005)]:
        inst = instruments[sym]
        res = size_position(inst, 100_000, 0.20, price, price - stop, slippage_ticks=1)
        assert res.lots > 0
        assert res.planned_risk_usd <= 200.0 + 1e-6
        # one more lot step would breach the budget
        per_lot = res.planned_risk_usd / res.lots
        assert (res.lots + inst.lot_step) * per_lot > 200.0
        assert math.isclose(round(res.lots / inst.lot_step), res.lots / inst.lot_step, abs_tol=1e-6)


def test_tiny_account_rejected(instruments):
    res = size_position(instruments["XAUUSD"], 500, 0.20, 2400.0, 2390.0)
    assert res.lots == 0 and res.reason == "below_min_lot"


def test_breakeven_win_rate():
    assert breakeven_win_rate(1.0, 0.0) == pytest.approx(0.5)
    assert breakeven_win_rate(2.0, 0.1) == pytest.approx(1.1 / 3.0)


def test_cost_in_R_grows_as_stop_shrinks(instruments):
    eu = instruments["EURUSD"]
    assert cost_in_R(eu, 1.1, 0.00002, 0.0003) > cost_in_R(eu, 1.1, 0.00002, 0.0010)


def test_daily_lockout_and_budget():
    rm = RiskManager(equity=100_000)
    rm.new_day("d1")
    for _ in range(4):
        ok, _ = rm.check_new_order("EURUSD", 1, 200.0)
        assert ok
        rm.on_open(OpenPosition("EURUSD", 1, 1.0, 200.0))
        rm.on_close("EURUSD", -200.0)
    # 800 lost -> 200 left: exactly one more nominal position allowed
    ok, _ = rm.check_new_order("EURUSD", 1, 200.0)
    assert ok
    rm.on_open(OpenPosition("EURUSD", 1, 1.0, 200.0))
    ok, why = rm.check_new_order("GBPUSD", -1, 200.0)
    assert not ok and why == "daily_budget_insufficient"
    rm.on_close("EURUSD", -200.0)
    assert rm.locked_out
    ok, why = rm.check_new_order("USDJPY", 1, 200.0)
    assert not ok and why == "daily_lockout"
    rm.new_day("d2")
    assert rm.check_new_order("USDJPY", 1, 200.0)[0]


def test_partial_budget_blocks_rounded_down_order():
    rm = RiskManager(equity=100_000)
    rm.new_day("d")
    rm.on_close("X", -850.0)  # 150 left, less than a nominal 200 position
    ok, why = rm.check_new_order("EURUSD", 1, 140.0)
    assert not ok and why == "daily_budget_insufficient"


def test_correlation_guard():
    rm = RiskManager(equity=100_000, correlations={("EURUSD", "GBPUSD"): 0.8})
    rm.new_day("d")
    rm.on_open(OpenPosition("EURUSD", 1, 1.0, 200.0))
    assert rm.check_new_order("GBPUSD", 1, 200.0) == (False, "correlated_with_EURUSD")
    # opposite direction is a hedge, not a duplicate exposure
    assert rm.check_new_order("GBPUSD", -1, 200.0)[0]


def test_execution_breaker():
    rm = RiskManager(equity=100_000)
    for _ in range(3):
        rm.on_execution_result(False)
    assert rm.check_new_order("EURUSD", 1, 200.0) == (False, "execution_breaker")
