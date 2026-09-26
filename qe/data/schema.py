"""Canonical M1 bar schema and data-quality report.

Canonical frame: tz-aware UTC DatetimeIndex (bar OPEN time, 1-minute frequency) with columns
    bo, bh, bl, bc  -- bid OHLC
    ao, ah, al, ac  -- ask OHLC
    volume          -- tick count or source volume (a liquidity PROXY, not traded volume)
    spread_source   -- 'quoted' (real bid/ask) or 'assumed' (bid-only source + modelled spread)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

PRICE_COLS = ["bo", "bh", "bl", "bc", "ao", "ah", "al", "ac"]
COLS = PRICE_COLS + ["volume"]


def mid(df: pd.DataFrame, col: str = "c") -> pd.Series:
    return (df["b" + col] + df["a" + col]) / 2.0


def spread(df: pd.DataFrame, col: str = "c") -> pd.Series:
    return df["a" + col] - df["b" + col]


def validate(df: pd.DataFrame) -> None:
    """Raise on structural violations. Use `quality_report` for softer diagnostics."""
    missing = [c for c in COLS if c not in df.columns]
    if missing:
        raise ValueError(f"missing columns {missing}")
    idx = df.index
    if not isinstance(idx, pd.DatetimeIndex) or idx.tz is None or str(idx.tz) != "UTC":
        raise ValueError("index must be a UTC tz-aware DatetimeIndex")
    if not idx.is_monotonic_increasing or idx.has_duplicates:
        raise ValueError("index must be strictly increasing without duplicates")
    if (idx.second != 0).any():
        raise ValueError("bar timestamps must be whole minutes")


def quality_report(df: pd.DataFrame, spike_mad_k: float = 15.0) -> dict:
    """Diagnostics: gaps inside trading hours, OHLC inconsistencies, crossed quotes, spikes."""
    validate(df)
    idx = df.index
    d = np.diff(idx.as_unit("ns").asi8) // 60_000_000_000
    gaps = d[d > 1]
    # weekend gaps (Fri close -> Sun open) are expected: count only gaps < 36h as intra-week
    intraweek = gaps[gaps < 36 * 60]
    ohlc_bad = int(((df.bh < df[["bo", "bc"]].max(axis=1) - 1e-12) | (df.bl > df[["bo", "bc"]].min(axis=1) + 1e-12)).sum())
    ohlc_bad += int(((df.ah < df[["ao", "ac"]].max(axis=1) - 1e-12) | (df.al > df[["ao", "ac"]].min(axis=1) + 1e-12)).sum())
    crossed = int((df.ac < df.bc).sum())
    r = np.log(mid(df)).diff().dropna()
    mad = float(np.median(np.abs(r - r.median()))) or 1e-12
    spikes = int((np.abs(r - r.median()) > spike_mad_k * 1.4826 * mad).sum())
    sp = spread(df)
    return {
        "bars": int(len(df)),
        "start": str(idx[0]) if len(df) else None,
        "end": str(idx[-1]) if len(df) else None,
        "intraweek_gaps": int(len(intraweek)),
        "intraweek_missing_minutes": int((intraweek - 1).sum()),
        "largest_intraweek_gap_min": int(intraweek.max()) if len(intraweek) else 0,
        "ohlc_inconsistent_bars": ohlc_bad,
        "crossed_quote_bars": crossed,
        "return_spikes": spikes,
        "zero_volume_bars": int((df.volume <= 0).sum()),
        "spread_median": float(sp.median()),
        "spread_p99": float(sp.quantile(0.99)),
    }
