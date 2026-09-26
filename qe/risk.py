"""Pre-trade risk engine: position sizing, daily loss lockout, exposure caps, correlation guard,
execution-health circuit breaker.

Design choices (documented in docs/research/risk_framework.md):
* Planned trade risk = stop distance + adverse slippage, valued at the lot size, PLUS round-trip
  commission. Spread is already inside the stop distance because stops are evaluated on the
  exit side of the book (bid for longs, ask for shorts).
* Daily budget check is conservative: realized P&L today + gross risk of all open positions +
  risk of the new order must stay within the daily limit (worst case: every stop is hit).
* Correlation guard: a new position is rejected when an open position on a different symbol
  has sign-adjusted correlation >= threshold (it would express the same exposure).
* No rule can ever increase size after a loss. Size depends only on equity and stop distance.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .config import Instrument
from .costs import commission_round_trip, value_per_price_unit


@dataclass(frozen=True)
class SizeResult:
    lots: float
    planned_risk_usd: float
    reason: str = ""


def size_position(
    inst: Instrument,
    equity: float,
    risk_pct: float,
    entry: float,
    stop: float,
    slippage_ticks: float = 0.0,
) -> SizeResult:
    """Largest lot size (rounded DOWN to the lot step) whose total planned loss incl. costs <= budget."""
    stop_dist = abs(entry - stop)
    if stop_dist <= 0:
        return SizeResult(0.0, 0.0, "invalid_stop")
    budget = equity * risk_pct / 100.0
    per_lot = value_per_price_unit(inst, 1.0, entry) * (stop_dist + slippage_ticks * inst.tick_size) \
        + commission_round_trip(inst, 1.0)
    raw = budget / per_lot
    lots = math.floor(raw / inst.lot_step + 1e-9) * inst.lot_step
    lots = round(lots, 8)
    if lots < inst.min_lot:
        return SizeResult(0.0, 0.0, "below_min_lot")
    return SizeResult(lots, lots * per_lot, "")


@dataclass
class OpenPosition:
    symbol: str
    direction: int  # +1 long, -1 short
    lots: float
    planned_risk_usd: float


@dataclass
class RiskManager:
    equity: float
    risk_per_trade_pct: float = 0.20
    max_daily_loss_pct: float = 1.00
    max_open_risk_pct: float = 0.60
    max_positions: int = 3
    correlation_threshold: float = 0.60
    correlations: dict[tuple[str, str], float] = field(default_factory=dict)
    exec_health_max_consecutive_rejects: int = 3

    trading_day: object = None
    day_start_equity: float = 0.0
    realized_today: float = 0.0
    locked_out: bool = False
    consecutive_rejects: int = 0
    breaker_tripped: bool = False
    open_positions: dict[str, OpenPosition] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.day_start_equity = self.equity

    # ---- day handling -------------------------------------------------------------------
    def new_day(self, day) -> None:
        if day != self.trading_day:
            self.trading_day = day
            self.day_start_equity = self.equity
            self.realized_today = 0.0
            self.locked_out = False

    # ---- helpers ------------------------------------------------------------------------
    def corr(self, a: str, b: str) -> float:
        if a == b:
            return 1.0
        return self.correlations.get((a, b), self.correlations.get((b, a), 0.0))

    def open_risk(self) -> float:
        return sum(p.planned_risk_usd for p in self.open_positions.values())

    def daily_limit_usd(self) -> float:
        return self.day_start_equity * self.max_daily_loss_pct / 100.0

    def remaining_daily_budget(self) -> float:
        loss_so_far = max(0.0, -self.realized_today)
        return self.daily_limit_usd() - loss_so_far - self.open_risk()

    # ---- pre-trade check ----------------------------------------------------------------
    def check_new_order(self, symbol: str, direction: int, planned_risk_usd: float) -> tuple[bool, str]:
        if self.breaker_tripped:
            return False, "execution_breaker"
        if self.locked_out:
            return False, "daily_lockout"
        if planned_risk_usd <= 0:
            return False, "zero_size"
        if symbol in self.open_positions:
            return False, "symbol_already_open"
        if len(self.open_positions) >= self.max_positions:
            return False, "max_positions"
        for p in self.open_positions.values():
            if self.corr(symbol, p.symbol) * direction * p.direction >= self.correlation_threshold:
                return False, f"correlated_with_{p.symbol}"
        if self.open_risk() + planned_risk_usd > self.equity * self.max_open_risk_pct / 100.0 + 1e-9:
            return False, "max_open_risk"
        # the remaining budget must cover a FULL nominal position, not just the rounded-down size
        nominal = self.equity * self.risk_per_trade_pct / 100.0
        if max(planned_risk_usd, nominal) > self.remaining_daily_budget() + 1e-9:
            return False, "daily_budget_insufficient"
        return True, "ok"

    # ---- state updates ------------------------------------------------------------------
    def on_open(self, pos: OpenPosition) -> None:
        self.open_positions[pos.symbol] = pos

    def on_close(self, symbol: str, pnl_usd: float) -> None:
        self.open_positions.pop(symbol, None)
        self.realized_today += pnl_usd
        self.equity += pnl_usd
        if -self.realized_today >= self.daily_limit_usd() - 1e-9:
            self.locked_out = True

    def on_execution_result(self, ok: bool) -> None:
        self.consecutive_rejects = 0 if ok else self.consecutive_rejects + 1
        if self.consecutive_rejects >= self.exec_health_max_consecutive_rejects:
            self.breaker_tripped = True

    def spread_breaker(self, spread: float, median_spread: float, max_mult: float) -> bool:
        """True if trading should be suspended because the spread is abnormally wide."""
        return median_spread > 0 and spread > max_mult * median_spread
