"""DXY series for the correlation gate (COR-5, A-10).

The ICE US Dollar Index formula: 50.14348112 * EURUSD^-0.576 * USDJPY^0.136 * GBPUSD^-0.119 * USDCAD^0.091
* USDSEK^0.042 * USDCHF^0.036. The synthetic bar is built from closes only ("line chart"): o = previous close,
c = close, h = max(o, c), l = min(o, c). The MQL5 EA builds it the same way.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DXY_CONST = 50.14348112
DXY_WEIGHTS = {"EURUSD": -0.576, "USDJPY": 0.136, "GBPUSD": -0.119, "USDCAD": 0.091, "USDSEK": 0.042,
               "USDCHF": 0.036}


def synthetic_dxy_close(closes: dict[str, pd.Series]) -> pd.Series:
    """DXY close per minute where all six components have a close (inner join, no forward fill)."""
    missing = set(DXY_WEIGHTS) - set(closes)
    if missing:
        raise ValueError(f"missing DXY components: {sorted(missing)}")
    df = pd.concat({k: closes[k] for k in DXY_WEIGHTS}, axis=1, join="inner").dropna()
    logv = np.log(DXY_CONST) + sum(w * np.log(df[k]) for k, w in DXY_WEIGHTS.items())
    return pd.Series(np.exp(logv), index=df.index, name="dxy")


def line_bars(close: pd.Series) -> pd.DataFrame:
    """Close-only bars: o = previous close, h = max(o, c), l = min(o, c)."""
    c = close.astype(float)
    o = c.shift(1).fillna(c)
    return pd.DataFrame({"o": o, "h": np.fmax(o, c), "l": np.fmin(o, c), "c": c}, index=close.index)


def ohlc_from_bid_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Use a bid/ask frame (columns bo, bh, bl, bc) of a real dollar-index series as DXY bars."""
    return pd.DataFrame({"o": df["bo"], "h": df["bh"], "l": df["bl"], "c": df["bc"]}, index=df.index)
