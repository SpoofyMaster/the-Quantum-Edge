"""Event-driven portfolio backtester with pre-trade risk checks and full transaction costs.

Input per symbol: bid/ask M1 bars and a signal frame indexed by decision-bar time with columns
    direction   (+1 / -1)
    stop_dist   (price distance, > 0)
    target_dist (price distance or NaN for no fixed target)
Positions are force-closed before the FX rollover blackout and never held > max_holding_minutes.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import Instrument
from .costs import commission_round_trip, value_per_price_unit
from .labels import Arrays, simulate_trade
from .risk import OpenPosition, RiskManager, size_position
from .sessions import session_frame


@dataclass
class BacktestConfig:
    risk_per_trade_pct: float = 0.20
    max_daily_loss_pct: float = 1.00
    max_open_risk_pct: float = 0.60
    max_positions: int = 3
    max_holding_minutes: int = 120
    slippage_ticks: float = 1.0
    latency_bars: int = 0
    correlation_threshold: float = 0.60


def _bars_to_blackout(blackout: np.ndarray) -> np.ndarray:
    n = len(blackout)
    out = np.full(n, n, dtype=np.int64)
    nxt = n
    for i in range(n - 1, -1, -1):
        if blackout[i]:
            nxt = i
        out[i] = nxt - i
    return out


def run(bars: dict[str, pd.DataFrame], signals: dict[str, pd.DataFrame], instruments: dict[str, Instrument],
        research_cfg: dict, bt: BacktestConfig, equity: float = 100_000.0,
        correlations: dict | None = None) -> tuple[pd.DataFrame, RiskManager]:
    rm = RiskManager(equity=equity, risk_per_trade_pct=bt.risk_per_trade_pct,
                     max_daily_loss_pct=bt.max_daily_loss_pct, max_open_risk_pct=bt.max_open_risk_pct,
                     max_positions=bt.max_positions, correlation_threshold=bt.correlation_threshold,
                     correlations=correlations or {})
    prep = {}
    queue = []
    for sym, df in bars.items():
        ses = session_frame(df.index, research_cfg)
        prep[sym] = (Arrays.from_df(df), df.index, ses["fx_day"].to_numpy(),
                     ses["rollover_blackout"].to_numpy(), _bars_to_blackout(ses["rollover_blackout"].to_numpy()))
        sig = signals.get(sym)
        if sig is None or sig.empty:
            continue
        pos = df.index.get_indexer(sig.index)
        for ts, t, row in zip(sig.index, pos, sig.itertuples()):
            if t >= 0:
                queue.append((ts, 1, sym, int(t), row))  # kind 1 = entry (exits use kind 0 -> processed first)
    queue.sort(key=lambda x: (x[0], x[1], x[2]))
    exits: list = []
    trades = []
    rejects: dict[str, int] = {}

    def process_exits(until):
        while exits and exits[0][0] <= until:
            _, _, sym, pnl, rec = heapq.heappop(exits)
            rm.on_close(sym, pnl)
            rec["equity_after"] = rm.equity
            trades.append(rec)

    seq = 0
    for ts, _, sym, t, row in queue:
        process_exits(ts)
        a, idx, fxday, blackout, to_bo = prep[sym]
        rm.new_day(fxday[t])
        if blackout[t] or t + 1 >= len(idx):
            rejects["rollover_blackout"] = rejects.get("rollover_blackout", 0) + 1
            continue
        inst = instruments[sym]
        d = int(row.direction)
        entry_est = a.ao[t + 1] if d > 0 else a.bo[t + 1]
        stop_dist = float(row.stop_dist)
        size = size_position(inst, rm.equity, bt.risk_per_trade_pct, entry_est,
                             entry_est - d * stop_dist, bt.slippage_ticks)
        ok, why = rm.check_new_order(sym, d, size.planned_risk_usd)
        if not ok or size.lots <= 0:
            key = why if not ok else size.reason
            rejects[key] = rejects.get(key, 0) + 1
            continue
        max_bars = int(min(bt.max_holding_minutes, max(1, to_bo[t + 1])))
        tgt = row.target_dist if np.isfinite(row.target_dist) else None
        res = simulate_trade(a, t, d, stop_dist, tgt, max_bars, bt.slippage_ticks * inst.tick_size, bt.latency_bars)
        if res is None:
            continue
        e, x, ep, xp, oc, pnl_px = res
        comm = commission_round_trip(inst, size.lots)
        pnl = pnl_px * value_per_price_unit(inst, size.lots, ep) - comm
        rm.on_open(OpenPosition(sym, d, size.lots, size.planned_risk_usd))
        rec = dict(symbol=sym, decision_time=ts, entry_time=idx[e], exit_time=idx[x], direction=d,
                   lots=size.lots, entry=ep, exit=xp, outcome=oc, bars=x - e + 1,
                   pnl_usd=pnl, commission_usd=comm, planned_risk_usd=size.planned_risk_usd,
                   R=pnl / size.planned_risk_usd, fx_day=fxday[t])
        seq += 1
        # a position exits at the close of bar x -> it is released at the open of bar x+1
        heapq.heappush(exits, (idx[x] + pd.Timedelta(minutes=1), seq, sym, pnl, rec))
    process_exits(pd.Timestamp.max.tz_localize("UTC"))
    out = pd.DataFrame(trades)
    out.attrs["rejects"] = rejects
    return out, rm
