"""Chronological splits, purged + embargoed walk-forward folds, and the final-test lock."""
from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
import pandas as pd

UNLOCK_ENV = "QE_UNLOCK_FINAL_TEST"


class FinalTestLocked(RuntimeError):
    pass


def final_test_start(cfg: dict) -> pd.Timestamp:
    return pd.Timestamp(cfg["splits"]["final_test_start"], tz="UTC")


def guard_final_test(index: pd.DatetimeIndex, cfg: dict) -> None:
    """Raise if data reaches into the locked final-test period.

    Unlock only after a strategy freeze is recorded in the journal, by setting the environment
    variable QE_UNLOCK_FINAL_TEST to the freeze id (e.g. 'FREEZE-2026-10-20-a').
    """
    if len(index) and index.max() >= final_test_start(cfg) and not os.environ.get(UNLOCK_ENV):
        raise FinalTestLocked(
            f"data reaches {index.max()} >= final_test_start {final_test_start(cfg)}; "
            f"set {UNLOCK_ENV}=<freeze-id> only after a journaled strategy freeze")


def research_window(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Slice to the development+validation period (everything before the final test)."""
    return df.loc[df.index < final_test_start(cfg)]


@dataclass(frozen=True)
class Fold:
    train_start: pd.Timestamp
    train_end: pd.Timestamp   # exclusive
    test_start: pd.Timestamp
    test_end: pd.Timestamp    # exclusive


def walk_forward_folds(start, end, train_days: int | None, test_days: int, step_days: int | None = None,
                       min_train_days: int = 90) -> list[Fold]:
    """Anchored (train_days=None) or rolling walk-forward folds on calendar boundaries."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    step = pd.Timedelta(days=step_days or test_days)
    folds = []
    ts = start + pd.Timedelta(days=min_train_days if train_days is None else train_days)
    while ts + pd.Timedelta(days=test_days) <= end:
        tr0 = start if train_days is None else ts - pd.Timedelta(days=train_days)
        folds.append(Fold(tr0, ts, ts, ts + pd.Timedelta(days=test_days)))
        ts += step
    return folds


def purged_train_mask(event_times: pd.DatetimeIndex, label_end: pd.Series, fold: Fold,
                      embargo: pd.Timedelta) -> np.ndarray:
    """Training mask: event inside the train window and its label window [event, label_end]
    does not overlap the test window widened by `embargo` on both sides (purging + embargo).
    """
    le = pd.DatetimeIndex(label_end.reindex(event_times))
    in_train = (event_times >= fold.train_start) & (event_times < fold.train_end)
    overlaps_test = (le >= fold.test_start - embargo) & (event_times < fold.test_end + embargo)
    return np.asarray(in_train & ~overlaps_test)


def oos_mask(event_times: pd.DatetimeIndex, fold: Fold) -> np.ndarray:
    return np.asarray((event_times >= fold.test_start) & (event_times < fold.test_end))
