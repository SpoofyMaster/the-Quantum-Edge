"""Execution-aware trade path simulation and triple-barrier labels on bid/ask M1 bars.

Conventions (see config/research.toml [execution]):
* Decision at the CLOSE of bar t. Fill at the OPEN of bar t+1+latency: long at ask, short at bid,
  plus `slippage` (price units) adverse.
* A long is exited on the bid; a short on the ask. Stops/targets are checked on the exit side.
* If stop and target are both inside the same bar, the STOP is assumed first (pessimistic).
* If a bar opens beyond the stop (gap), the fill is the bar open (worse than the stop).
* Time exit at the close of the bar `max_bars` after entry (inclusive of the entry bar).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

OUTCOME_TARGET, OUTCOME_STOP, OUTCOME_TIME = 1, -1, 0


@dataclass(frozen=True)
class Arrays:
    bo: np.ndarray
    bh: np.ndarray
    bl: np.ndarray
    bc: np.ndarray
    ao: np.ndarray
    ah: np.ndarray
    al: np.ndarray
    ac: np.ndarray

    @classmethod
    def from_df(cls, df: pd.DataFrame) -> "Arrays":
        return cls(*(df[c].to_numpy(float) for c in ("bo", "bh", "bl", "bc", "ao", "ah", "al", "ac")))


def simulate_trade(a: Arrays, t: int, direction: int, stop_dist: float, target_dist: float | None,
                   max_bars: int, slippage: float = 0.0, latency: int = 0):
    """Simulate one trade decided at close of bar t.

    Returns (entry_idx, exit_idx, entry_price, exit_price, outcome, pnl_price) or None if the
    entry bar is beyond the data. pnl_price is signed, per unit, net of spread and slippage
    (commission is added by the caller because it depends on lot size).
    """
    n = len(a.bo)
    e = t + 1 + latency
    if e >= n:
        return None
    if direction > 0:
        entry = a.ao[e] + slippage
        stop, tgt = entry - stop_dist, (entry + target_dist if target_dist else np.inf)
        hi, lo, op, cl = a.bh, a.bl, a.bo, a.bc
    else:
        entry = a.bo[e] - slippage
        stop, tgt = entry + stop_dist, (entry - target_dist if target_dist else -np.inf)
        hi, lo, op, cl = a.ah, a.al, a.ao, a.ac
    last = min(e + max_bars - 1, n - 1)
    for j in range(e, last + 1):
        if direction > 0:
            if j > e and op[j] <= stop:
                return e, j, entry, op[j] - slippage, OUTCOME_STOP, op[j] - slippage - entry
            if lo[j] <= stop:
                px = stop - slippage
                return e, j, entry, px, OUTCOME_STOP, px - entry
            if hi[j] >= tgt:
                return e, j, entry, tgt, OUTCOME_TARGET, tgt - entry
        else:
            if j > e and op[j] >= stop:
                return e, j, entry, op[j] + slippage, OUTCOME_STOP, entry - op[j] - slippage
            if hi[j] >= stop:
                px = stop + slippage
                return e, j, entry, px, OUTCOME_STOP, entry - px
            if lo[j] <= tgt:
                return e, j, entry, tgt, OUTCOME_TARGET, entry - tgt
    px = cl[last] - direction * slippage
    return e, last, entry, px, OUTCOME_TIME, direction * (px - entry)


def triple_barrier_labels(df: pd.DataFrame, events: pd.DatetimeIndex, direction: int,
                          stop_dist: pd.Series, target_mult: float, max_bars: int,
                          slippage: float = 0.0) -> pd.DataFrame:
    """Label each event for a given direction. stop_dist is a per-event price distance series."""
    a = Arrays.from_df(df)
    pos = df.index.get_indexer(events)
    rows = []
    for ev, t in zip(events, pos):
        sd = float(stop_dist.loc[ev])
        if t < 0 or not np.isfinite(sd) or sd <= 0:
            continue
        res = simulate_trade(a, t, direction, sd, target_mult * sd, max_bars, slippage)
        if res is None:
            continue
        e, x, ep, xp, oc, pnl = res
        rows.append((ev, df.index[x], oc, pnl, pnl / sd, x - e + 1))
    return pd.DataFrame(rows, columns=["event", "exit_time", "outcome", "pnl_price", "pnl_R", "bars"]).set_index("event")
