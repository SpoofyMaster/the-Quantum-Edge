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


# ---------------------------------------------------------------------------------------------
# Daily M1 candle files (one request per day and side instead of 24 hourly tick files).
#   URL  .../{SYMBOL}/{YYYY}/{MM-1:02d}/{DD:02d}/{BID|ASK}_candles_min_1.bi5
#   body LZMA stream of 24-byte big-endian records:
#        uint32 seconds_since_day_start, uint32 open, uint32 close, uint32 low, uint32 high, float32 volume
# The field order (open, close, low, high) is validated on every decoded file by
# `check_candle_order`; a violation aborts the download instead of silently corrupting bars.
# ---------------------------------------------------------------------------------------------
_CANDLE = np.dtype([("s", ">u4"), ("o", ">u4"), ("c", ">u4"), ("l", ">u4"), ("h", ">u4"), ("v", ">f4")])


def _utc_day(day) -> pd.Timestamp:
    ts = pd.Timestamp(day)
    return (ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")).normalize()


def candle_url(symbol: str, day: datetime, side: str) -> str:
    return (f"https://datafeed.dukascopy.com/datafeed/{symbol}/{day.year}/{day.month - 1:02d}/"
            f"{day.day:02d}/{side.upper()}_candles_min_1.bi5")


def decode_candles_bi5(payload: bytes, symbol: str, day: datetime) -> pd.DataFrame:
    cols = ["open", "high", "low", "close", "volume"]
    if not payload:
        return pd.DataFrame(columns=cols, index=pd.DatetimeIndex([], tz="UTC", name="time"))
    raw = lzma.decompress(payload)
    if len(raw) % _CANDLE.itemsize:
        raise ValueError("corrupt candle payload: length not a multiple of 24")
    arr = np.frombuffer(raw, dtype=_CANDLE)
    p = POINT[symbol]
    base = _utc_day(day)
    idx = pd.DatetimeIndex(base + pd.to_timedelta(arr["s"].astype(np.int64), unit="s"), name="time")
    return pd.DataFrame({"open": arr["o"] / p, "high": arr["h"] / p, "low": arr["l"] / p,
                         "close": arr["c"] / p, "volume": arr["v"].astype(float)}, index=idx)[cols]


def encode_candles_bi5(df: pd.DataFrame, symbol: str, day: datetime) -> bytes:
    """Inverse of decode_candles_bi5 (tests only)."""
    p = POINT[symbol]
    base = _utc_day(day)
    secs = ((df.index - base) / pd.Timedelta(seconds=1)).astype(np.int64)
    rec = np.empty(len(df), dtype=_CANDLE)
    rec["s"] = secs
    for k, col in (("o", "open"), ("c", "close"), ("l", "low"), ("h", "high")):
        rec[k] = np.round(df[col].to_numpy() * p).astype(np.uint32)
    rec["v"] = df["volume"].to_numpy(np.float32)
    return lzma.compress(rec.tobytes(), format=lzma.FORMAT_ALONE)


def check_candle_order(df: pd.DataFrame, tol: float = 1e-9) -> float:
    """Fraction of bars violating low <= min(open, close) <= max(open, close) <= high."""
    if df.empty:
        return 0.0
    bad = (df.high + tol < df[["open", "close"]].max(axis=1)) | (df.low - tol > df[["open", "close"]].min(axis=1))
    return float(bad.mean())


def candles_to_canonical(bid: pd.DataFrame, ask: pd.DataFrame) -> pd.DataFrame:
    """Join BID and ASK candles into the canonical schema; drop filler bars (zero bid volume)."""
    j = bid.join(ask, how="inner", lsuffix="_b", rsuffix="_a")
    out = pd.DataFrame({"bo": j.open_b, "bh": j.high_b, "bl": j.low_b, "bc": j.close_b,
                        "ao": j.open_a, "ah": j.high_a, "al": j.low_a, "ac": j.close_a,
                        "volume": j.volume_b + j.volume_a}, index=j.index)
    out = out[(j.volume_b > 0) | (j.volume_a > 0)]
    out["spread_source"] = "quoted"
    return out
