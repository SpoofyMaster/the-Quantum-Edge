"""Line-by-line Python mirror of the time functions in mql5/QuantumEdgeImpulseReversion.mq5
(NthSunday, LastSunday, IsUSDST_UTC, IsUKDST_UTC, ServerToUTC, UTCToNY, UTCToLondon, Sessions).
Times are integer seconds since 1970 (MQL5 datetime). Tested against zoneinfo in
tests/test_mql5_parity.py. Cannot test MQL5 syntax (no MetaEditor in the sandbox)."""
from __future__ import annotations

import calendar
import math
from datetime import datetime, timezone

NY_PLUS_7, EU_DST, FIXED = 0, 1, 2


def make_date(y, m, d, hh=0, mm=0):
    return calendar.timegm((y, m, d, hh, mm, 0))


def day_of_week(t):                       # 0 = Sunday (MqlDateTime.day_of_week)
    return (datetime.fromtimestamp(t, timezone.utc).weekday() + 1) % 7


def year_of(t):
    return datetime.fromtimestamp(t, timezone.utc).year


def nth_sunday(y, m, n):
    first = make_date(y, m, 1)
    add = (7 - day_of_week(first)) % 7
    return first + (add + 7 * (n - 1)) * 86400


def last_sunday(y, m):
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    last = make_date(ny, nm, 1) - 86400
    return last - day_of_week(last) * 86400


def is_us_dst_utc(utc):
    y = year_of(utc)
    return nth_sunday(y, 3, 2) + 7 * 3600 <= utc < nth_sunday(y, 11, 1) + 6 * 3600


def is_uk_dst_utc(utc):
    y = year_of(utc)
    return last_sunday(y, 3) + 3600 <= utc < last_sunday(y, 10) + 3600


def server_to_utc(server, mode=NY_PLUS_7, fixed_h=0):
    if mode == NY_PLUS_7:
        ny = server - 7 * 3600
        cand = ny + 5 * 3600
        return ny + 4 * 3600 if is_us_dst_utc(cand - 3600) else cand
    if mode == EU_DST:
        cand = server - 2 * 3600
        return server - 3 * 3600 if is_uk_dst_utc(cand - 3600) else cand
    return server - fixed_h * 3600


def utc_to_ny(utc):
    return utc - (4 if is_us_dst_utc(utc) else 5) * 3600


def utc_to_london(utc):
    return utc + (1 if is_uk_dst_utc(utc) else 0) * 3600


def minute_of_day(t):
    return (t % 86400) // 60


def in_window(m, a, b):
    return a <= m < b if a <= b else (m >= a or m < b)


def sessions(server_bar_open, mode=NY_PLUS_7):
    utc = server_to_utc(server_bar_open, mode)
    ny, ldn = utc_to_ny(utc), utc_to_london(utc)
    ny_m, ld_m = minute_of_day(ny), minute_of_day(ldn)
    dow = day_of_week(ny)
    return {"utc": utc,
            "london": in_window(ld_m, 480, 990), "newyork": in_window(ny_m, 480, 1020),
            "blackout": in_window(ny_m, 1005, 1050), "fx_day": (ny + 7 * 3600) // 86400,
            "bucket": dow * 288 + ny_m // 5, "week_id": math.floor((math.floor(ny / 86400) - 10958) / 7),
            "hour_of_week": dow * 24 + ny_m // 60}
