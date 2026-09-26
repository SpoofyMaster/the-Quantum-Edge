"""DST-correct trading-session labels for a UTC minute index.

Each session is defined in its own local wall-clock time and converted with zoneinfo, so the
London/New York overlap correctly shifts during the weeks when US and UK DST dates differ.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _hm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def _local_minutes(idx: pd.DatetimeIndex, tz: str) -> np.ndarray:
    loc = idx.tz_convert(tz)
    return np.asarray(loc.hour * 60 + loc.minute)


def _in_window(minutes: np.ndarray, start: int, end: int) -> np.ndarray:
    if start <= end:
        return (minutes >= start) & (minutes < end)
    return (minutes >= start) | (minutes < end)  # wraps midnight


def fx_trading_day(idx: pd.DatetimeIndex, rollover_tz: str = "America/New_York", rollover_time: str = "17:00") -> pd.Index:
    """FX trading date: bars at/after 17:00 New York belong to the next date."""
    loc = idx.tz_convert(rollover_tz)
    shift = pd.Timedelta(minutes=24 * 60 - _hm(rollover_time))
    return pd.Index((loc + shift).date, name="fx_day")


def session_frame(idx: pd.DatetimeIndex, cfg: dict) -> pd.DataFrame:
    """Boolean session flags + FX trading day for a tz-aware UTC DatetimeIndex (bar-open labels)."""
    if idx.tz is None:
        raise ValueError("index must be timezone-aware (UTC)")
    s = cfg["sessions"]
    out = pd.DataFrame(index=idx)
    for name in ("asia", "london", "newyork"):
        m = _local_minutes(idx, s[f"{name}_tz"])
        out[name] = _in_window(m, _hm(s[f"{name}_open"]), _hm(s[f"{name}_close"]))
    out["overlap"] = out["london"] & out["newyork"]
    m = _local_minutes(idx, s["rollover_tz"])
    r = _hm(s["rollover_time"])
    out["rollover_blackout"] = _in_window(
        m, (r - s["rollover_blackout_before_min"]) % 1440, (r + s["rollover_blackout_after_min"]) % 1440
    )
    out["fx_day"] = fx_trading_day(idx, s["rollover_tz"], s["rollover_time"])
    return out
