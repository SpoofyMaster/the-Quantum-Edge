"""Synthetic bar sequences that reproduce the *geometry* of the six chart examples in the video
(research/VIDEO_TRADE_DATABASE.md). Prices are not readable in the video, so levels here are illustrative; what is
encoded is the sequence: MTF condition and legs, the candle's drive, the protected swing, the shift minute and the
DXY path. Used by tests/test_video_examples.py (Phase 19 regression tests).

Bar k of a path covers minute m_k: open = P(m_k), close = P(m_k + 1), high/low = max/min(open, close) +/- wiggle,
where P is the piecewise-linear interpolation of the waypoints (minute offset from the candle open, price).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .params import Params, m15_preset

GOLD_SPREAD = 0.10
GOLD_WIGGLE = 0.02
DXY_WIGGLE = 0.0004


def path_frame(candle_open: pd.Timestamp, waypoints: list[tuple[int, float]], wiggle: float) -> pd.DataFrame:
    m0, m1 = waypoints[0][0], waypoints[-1][0]
    xs = np.array([w[0] for w in waypoints], float)
    ys = np.array([w[1] for w in waypoints], float)
    minutes = np.arange(m0, m1)
    o = np.interp(minutes, xs, ys)
    c = np.interp(minutes + 1, xs, ys)
    idx = candle_open + pd.to_timedelta(minutes, unit="min")
    return pd.DataFrame({"o": o, "h": np.maximum(o, c) + wiggle, "l": np.minimum(o, c) - wiggle, "c": c}, index=idx)


def gold_frame(candle_open: pd.Timestamp, waypoints, spread: float = GOLD_SPREAD) -> pd.DataFrame:
    b = path_frame(candle_open, waypoints, GOLD_WIGGLE)
    out = pd.DataFrame({"bo": b.o, "bh": b.h, "bl": b.l, "bc": b.c}, index=b.index)
    for s in "ohlc":
        out["a" + s] = out["b" + s] + spread
    out.index.name = "time"
    return out


def mirror(waypoints, pivot_gold: float, pivot_dxy: float, scale: float = 0.03):
    """DXY waypoints that mirror gold's (inverse correlation)."""
    return [(m, pivot_dxy - (p - pivot_gold) * scale) for m, p in waypoints]


# middle-timeframe histories (minutes -300..0)
MTF_RANGE = [(-330, 2000.0), (-300, 2000.0), (-250, 2006.0), (-190, 2000.0), (-130, 2006.0), (-70, 2000.0),
             (-20, 2000.6), (0, 2000.0)]
MTF_BEAR_TR = [(-330, 2030.0), (-300, 2030.0), (-240, 2020.0), (-190, 2026.0), (-130, 2016.0), (-80, 2022.0),
               (-20, 2012.0), (0, 2012.5)]
MTF_BULL_TR = [(-330, 1982.0), (-300, 1982.0), (-240, 1992.0), (-190, 1986.0), (-130, 1996.0), (-80, 1990.0),
               (-20, 2000.0), (0, 2000.0)]
MTF_TREND_UP = [(-330, 1950.0), (-300, 1950.0), (-250, 1962.0), (-230, 1959.0), (-180, 1971.0), (-160, 1968.0),
                (-110, 1980.0), (-90, 1977.0), (-40, 1989.0), (-20, 1986.0), (0, 1988.0)]


@dataclass
class Example:
    name: str
    candle_open: pd.Timestamp
    gold: pd.DataFrame
    dxy: pd.DataFrame
    params: list[Params]
    expect: dict


def _build(name, candle_open, mtf, candle_path, dxy_mtf, dxy_candle, params, expect) -> Example:
    gold = gold_frame(candle_open, mtf[:-1] + candle_path)
    dxy = path_frame(candle_open, dxy_mtf[:-1] + dxy_candle, DXY_WIGGLE)
    return Example(name, candle_open, gold, dxy, params, expect)


# ---- T-02: M15 sell at the high of a small range, DXY mirror -> trade (win) -----------------------------
# plateau at the first top so that the dip is a pivot low for pivot strengths 1..3
T02_CANDLE = [(0, 2000.0), (4, 2004.0), (6, 2004.0), (8, 2003.4), (11, 2004.6), (13, 2003.0), (15, 2002.6),
              (25, 2001.5), (90, 2001.0)]


def t02(params: list[Params] | None = None) -> Example:
    co = pd.Timestamp("2024-03-05 02:15", tz="UTC")        # Tuesday, inside the Asia window
    dxy_mtf = mirror(MTF_RANGE, 2000.0, 104.0)
    dxy_c = mirror(T02_CANDLE, 2000.0, 104.0)
    return _build("T-02", co, MTF_RANGE, T02_CANDLE, dxy_mtf, dxy_c, params or [m15_preset()],
                  {"trade": True, "direction": -1, "outcome": 1})


# ---- T-03: same gold geometry, DXY rises with gold -> INV_DXY_SAME_DIRECTION ----------------------------------
def t03(params: list[Params] | None = None) -> Example:
    co = pd.Timestamp("2024-03-05 02:15", tz="UTC")
    dxy_mtf = mirror(MTF_RANGE, 2000.0, 104.0)
    dxy_c = [(m, 104.0 + (p - 2000.0) * 0.03) for m, p in T02_CANDLE]
    return _build("T-03", co, MTF_RANGE, T02_CANDLE, dxy_mtf, dxy_c, params or [m15_preset()],
                  {"trade": False, "reason": "INV_DXY_SAME_DIRECTION"})


# ---- T-04: M15 sell, pullback into 50% of the previous bearish move (bearish trending range) -------------------
T04_CANDLE = [(0, 2012.5), (4, 2016.5), (6, 2016.5), (8, 2015.9), (11, 2017.6), (13, 2015.5), (15, 2015.0),
              (25, 2013.0), (90, 2012.0)]


def t04(params: list[Params] | None = None) -> Example:
    co = pd.Timestamp("2024-03-04 02:30", tz="UTC")        # Monday
    dxy_mtf = mirror(MTF_BEAR_TR, 2012.5, 104.0)
    dxy_c = mirror(T04_CANDLE, 2012.5, 104.0)
    return _build("T-04", co, MTF_BEAR_TR, T04_CANDLE, dxy_mtf, dxy_c, params or [m15_preset()],
                  {"trade": True, "direction": -1, "outcome": 1})


# ---- T-05: H1 gold drive up, DXY also rising at the top of its bullish range -> no trade -----------------------
T05_CANDLE = [(0, 2000.0), (12, 2004.5), (16, 2003.3), (24, 2007.0), (27, 2005.8), (30, 2007.5), (33, 2005.4),
              (60, 2008.5), (150, 2010.0)]


def t05(params: list[Params] | None = None) -> Example:
    co = pd.Timestamp("2024-03-07 02:00", tz="UTC")        # Thursday
    dxy_mtf = mirror(MTF_RANGE, 2000.0, 104.0)
    dxy_c = [(m, 104.0 + (p - 2000.0) * 0.03) for m, p in T05_CANDLE]
    return _build("T-05", co, MTF_RANGE, T05_CANDLE, dxy_mtf, dxy_c, params or [Params()],
                  {"trade": False, "reason": "INV_DXY_SAME_DIRECTION"})


# ---- T-06: H1 buy, hourly candle drives down into the lower half (bearish TR); DXY drives up (choppy, "low
#            volume"), then a bearish DXY shift before gold's bullish shift -> trade (win) -------------------------
# bounces last >= 3 bars so the swing points are pivots for strengths 1..3; a pullback after the break (PULLBACK_50)
T06_CANDLE = [(0, 2012.0), (12, 2007.5), (16, 2008.7), (24, 2005.0), (27, 2006.2), (30, 2004.5), (33, 2006.6),
              (35, 2007.0), (38, 2005.6), (47, 2009.0), (150, 2009.5)]
# DXY drives up with a deep (> 50%) pullback ("a little bit low volume"), then shifts down before gold shifts up
T06_DXY = [(0, 104.00), (8, 104.10), (14, 104.04), (24, 104.15), (27, 104.11), (29, 104.17), (31, 104.09),
           (40, 104.02), (150, 104.0)]


def t06(params: list[Params] | None = None) -> Example:
    co = pd.Timestamp("2024-03-06 02:00", tz="UTC")        # Wednesday, 11:00 Tokyo
    dxy_mtf = mirror(MTF_BEAR_TR, 2012.0, 104.0)
    return _build("T-06", co, MTF_BEAR_TR[:-1] + [(0, 2012.0)], T06_CANDLE, dxy_mtf, T06_DXY, params or [Params()],
                  {"trade": True, "direction": 1, "outcome": 1})


# ---- T-01: H1 continuation buy: bullish TR, candle drives down into 50% of the previous bullish move ------------
T01_CANDLE = [(0, 2000.0), (12, 1995.5), (16, 1996.7), (24, 1993.0), (27, 1994.2), (30, 1992.5), (33, 1994.6),
              (35, 1995.0), (38, 1993.6), (47, 1997.0), (150, 1997.5)]


def t01(params: list[Params] | None = None) -> Example:
    co = pd.Timestamp("2024-03-06 03:00", tz="UTC")
    dxy_mtf = mirror(MTF_BULL_TR, 2000.0, 104.0)
    dxy_c = mirror(T01_CANDLE, 2000.0, 104.0)
    return _build("T-01", co, MTF_BULL_TR, T01_CANDLE, dxy_mtf, dxy_c, params or [Params()],
                  {"trade": True, "direction": 1, "outcome": 1})


ALL = {"T-01": t01, "T-02": t02, "T-03": t03, "T-04": t04, "T-05": t05, "T-06": t06}
