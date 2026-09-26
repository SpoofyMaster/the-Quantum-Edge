"""Transaction-cost model for IC Markets Raw Spread style pricing (spread + commission + slippage).

All monetary values are in the account currency (USD). Prices are in quote currency.
"""
from __future__ import annotations

from .config import Instrument


def usd_per_quote_unit(inst: Instrument, price: float) -> float:
    """USD value of one unit of quote currency.

    USD-quoted pairs/metals: 1. USDJPY-style (USD base, non-USD quote): 1 / price.
    Other crosses need an external conversion rate and are not supported yet.
    """
    if inst.quote_ccy == "USD":
        return 1.0
    if inst.symbol.startswith("USD"):
        return 1.0 / price
    raise NotImplementedError(f"quote conversion for {inst.symbol} needs a {inst.quote_ccy}USD rate")


def value_per_price_unit(inst: Instrument, lots: float, price: float) -> float:
    """USD P&L for a 1.0 move in price with `lots` lots."""
    return lots * inst.contract_size * usd_per_quote_unit(inst, price)


def commission_round_trip(inst: Instrument, lots: float) -> float:
    return 2.0 * lots * inst.commission_per_lot_side_usd


def commission_in_price_units(inst: Instrument, price: float) -> float:
    """Round-trip commission expressed as an equivalent adverse price move (lot-size independent)."""
    return commission_round_trip(inst, 1.0) / value_per_price_unit(inst, 1.0, price)


def round_trip_cost_price(inst: Instrument, price: float, spread: float, slippage_ticks: float = 0.0) -> float:
    """Total round-trip cost as a price distance: spread (paid once) + commission + slippage on both legs."""
    return spread + commission_in_price_units(inst, price) + 2.0 * slippage_ticks * inst.tick_size


def cost_in_R(inst: Instrument, price: float, spread: float, stop_distance: float, slippage_ticks: float = 0.0) -> float:
    """Round-trip cost as a fraction of the risk unit R (= stop distance)."""
    return round_trip_cost_price(inst, price, spread, slippage_ticks) / stop_distance


def breakeven_win_rate(reward_R: float, cost_R: float) -> float:
    """Win rate needed for zero expectancy with a fixed target of `reward_R` and stop of 1R, both net of cost.

    Win nets (reward_R - cost_R), loss nets -(1 + cost_R).  p*(rw - c) = (1-p)*(1 + c).
    """
    return (1.0 + cost_R) / (reward_R + 1.0)
