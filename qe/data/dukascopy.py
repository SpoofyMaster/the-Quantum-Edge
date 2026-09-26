"""Dukascopy historical tick feed (.bi5) decoder and M1 aggregation.

File layout (as implemented by widely used open-source downloaders; verify on first real download):
    URL  https://datafeed.dukascopy.com/datafeed/{SYMBOL}/{YYYY}/{MM-1:02d}/{DD:02d}/{HH:02d}h_ticks.bi5
         (month is ZERO-based)
    body LZMA-compressed sequence of 20-byte big-endian records:
         uint32 ms_since_hour, uint32 ask_points, uint32 bid_points, float32 ask_vol, float32 bid_vol
    price = points / POINT[symbol]

Dukascopy is an ECN/bank quote stream, NOT IC Markets. Its spreads are a proxy only.
Licensing: check Dukascopy's terms before redistributing any downloaded data. Raw data is never
committed to this repository (see .gitignore); only derived statistics and provenance hashes.
"""
from __future__ import annotations

import lzma
import struct
from datetime import datetime, timezone

import numpy as np
import pandas as pd

POINT = {"EURUSD": 1e5, "GBPUSD": 1e5, "USDJPY": 1e3, "XAUUSD": 1e3, "XAGUSD": 1e3,
         "AUDUSD": 1e5, "USDCAD": 1e5, "USDCHF": 1e5, "NZDUSD": 1e5, "EURJPY": 1e3, "GBPJPY": 1e3}

_REC = struct.Struct(">IIIff")


def url_for(symbol: str, hour: datetime) -> str:
    return (f"https://datafeed.dukascopy.com/datafeed/{symbol}/{hour.year}/{hour.month - 1:02d}/"
            f"{hour.day:02d}/{hour.hour:02d}h_ticks.bi5")


def decode_bi5(payload: bytes, symbol: str, hour: datetime) -> pd.DataFrame:
    """Decode one hourly .bi5 file into a tick DataFrame indexed by UTC timestamp."""
    if hour.tzinfo is None:
        hour = hour.replace(tzinfo=timezone.utc)
    if not payload:
        return pd.DataFrame(columns=["ask", "bid", "ask_vol", "bid_vol"],
                            index=pd.DatetimeIndex([], tz="UTC"))
    raw = lzma.decompress(payload)
    if len(raw) % _REC.size:
        raise ValueError("corrupt bi5 payload: length not a multiple of 20")
    arr = np.frombuffer(raw, dtype=np.dtype([("ms", ">u4"), ("ask", ">u4"), ("bid", ">u4"),
                                             ("av", ">f4"), ("bv", ">f4")]))
    p = POINT[symbol]
    ts = pd.Timestamp(hour).floor("h") + pd.to_timedelta(arr["ms"].astype(np.int64), unit="ms")
    return pd.DataFrame({"ask": arr["ask"] / p, "bid": arr["bid"] / p,
                         "ask_vol": arr["av"].astype(float), "bid_vol": arr["bv"].astype(float)},
                        index=pd.DatetimeIndex(ts, name="time"))


def encode_bi5(ticks: pd.DataFrame, symbol: str, hour: datetime) -> bytes:
    """Inverse of decode_bi5 (used for round-trip tests)."""
    p = POINT[symbol]
    base = pd.Timestamp(hour).floor("h")
    ms = ((ticks.index - base) / pd.Timedelta(milliseconds=1)).astype(np.int64)
    body = b"".join(_REC.pack(int(m), int(round(a * p)), int(round(b * p)), float(av), float(bv))
                    for m, a, b, av, bv in zip(ms, ticks.ask, ticks.bid, ticks.ask_vol, ticks.bid_vol))
    return lzma.compress(body, format=lzma.FORMAT_ALONE)


def ticks_to_m1(ticks: pd.DataFrame) -> pd.DataFrame:
    """Aggregate ticks into canonical M1 bid/ask bars (bar-open labels). Minutes without ticks are dropped."""
    g = ticks.resample("1min", label="left", closed="left")
    b = g["bid"].ohlc()
    a = g["ask"].ohlc()
    out = pd.DataFrame({"bo": b.open, "bh": b.high, "bl": b.low, "bc": b.close,
                        "ao": a.open, "ah": a.high, "al": a.low, "ac": a.close,
                        "volume": g["bid"].count().astype(float)})
    out = out.dropna(subset=["bo"])
    out["spread_source"] = "quoted"
    return out
