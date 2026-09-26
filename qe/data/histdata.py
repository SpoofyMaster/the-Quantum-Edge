"""HistData.com 'Generic ASCII' M1 bar parser.

Format (per HistData documentation, to be re-checked on first download):
    YYYYMMDD HHMMSS;OPEN;HIGH;LOW;CLOSE;VOLUME
Timestamps are Eastern Standard Time WITHOUT daylight saving (fixed UTC-05:00). Prices are BID.
Because the source has no ask, the canonical ask side is modelled as bid + assumed spread and the
frame is flagged spread_source='assumed'. Never treat these spreads as observed broker spreads.
"""
from __future__ import annotations

import io

import pandas as pd

EST_FIXED = pd.Timedelta(hours=5)


def parse_ascii_m1(text: str | io.IOBase, assumed_spread: float) -> pd.DataFrame:
    df = pd.read_csv(io.StringIO(text) if isinstance(text, str) else text, sep=";", header=None,
                     names=["ts", "o", "h", "l", "c", "v"], dtype={"ts": str})
    ts = pd.to_datetime(df.ts, format="%Y%m%d %H%M%S") + EST_FIXED
    idx = pd.DatetimeIndex(ts).tz_localize("UTC")
    out = pd.DataFrame({"bo": df.o.values, "bh": df.h.values, "bl": df.l.values, "bc": df.c.values}, index=idx)
    for s in "ohlc":
        out["a" + s] = out["b" + s] + assumed_spread
    out["volume"] = df.v.astype(float).values
    out["spread_source"] = "assumed"
    out.index.name = "time"
    return out[~out.index.duplicated(keep="first")].sort_index()
