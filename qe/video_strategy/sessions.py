"""Trading-hours filter for the trade candle (MKT-5, spec section 1). DST-correct via zoneinfo."""
from __future__ import annotations

from datetime import datetime, time, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

import pandas as pd

TOKYO = ZoneInfo("Asia/Tokyo")
LONDON = ZoneInfo("Europe/London")
NEW_YORK = ZoneInfo("America/New_York")


@lru_cache(maxsize=None)
def _day_bounds(d) -> tuple[datetime, datetime, datetime]:
    start = datetime.combine(d, time(10, 0), TOKYO).astimezone(timezone.utc)          # 2nd hour of Tokyo
    london_open = datetime.combine(d, time(8, 0), LONDON).astimezone(timezone.utc)
    end = datetime.combine(d, time(11, 0), LONDON).astimezone(timezone.utc)           # 4th hour of London
    return start, london_open, end


def in_rollover_blackout(ts_utc: pd.Timestamp) -> bool:
    ny = ts_utc.tz_convert(NEW_YORK)
    m = ny.hour * 60 + ny.minute
    return 16 * 60 + 45 <= m < 17 * 60 + 30


def is_trading_candle(candle_open_utc: pd.Timestamp, preset: str) -> bool:
    """True if a candle opening at this UTC time may be traded."""
    ts = candle_open_utc.to_pydatetime()
    if preset == "ALL":
        return not in_rollover_blackout(candle_open_utc)
    d = ts.date()
    if d.weekday() >= 5:
        return False
    start, london_open, end = _day_bounds(d)
    if preset == "STRICT":
        return ts == start or ts == london_open
    return start <= ts <= end
